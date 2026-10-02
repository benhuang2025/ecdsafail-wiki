# b788efc — Keep the square's cross-assembly boundary carries live until the inverse clears them, and seed the narrow multiply flag compares

| | |
| --- | --- |
| Contestant | dysnasia |
| Date | 2026-09-25 |
| Submission | `2faa506` |
| Commit | `b788efcd3edf01d320c646e1ae830e4095ae9d31` |
| Result | 1251 qubits × 894,789 Toffoli = **1,119,381,039** |
| Base | `f812a29` (git parent, the author's previous submission): 1251 qubits × 894,852 Toffoli = 1,119,459,852 |
| Change vs base | qubits ±0, Toffoli −63, score −78,813 |
| Leaderboard Δ | −78,813, measured against the base |
| Family | Uncompute Strategy → deferred coherent uncompute |
| Concepts | [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two small packages at 1251 qubits.

- **Square boundary hold (about −48 Toffoli, exact).** At the three root
  Karatsuba nodes the cross-term add is split into chunks to fit under the
  qubit cap. Each chunk boundary leaves a carry wire. Before, that wire was
  measured in the forward add and erased in the inverse with a conditional
  full-chunk compare. Now the carry stays live, and the inverse add, which
  recreates exactly the same carry, XORs it back to zero for free. The extra
  live wires are paid for by lending wires that are provably zero.
- **Multiply flag compares (about −9 Toffoli, approximate).** The 11
  plain-path flag compares in narrow multiply rounds become one bit shorter
  and are seeded with a source bit. The flag-compare width table is also
  reshaped.

## What changed and why it saves Toffoli

### 1. `SQ_HOLD_BOUNDARY=1` (`square.rs`, `width_composition.rs`)

Background: [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md).
`add_cross` adds the cross term `2ab` into `product[lo..]` for one node, and
subtracts it again in the node's inverse.

- **When the fitted path is used.** When the ripple's carry ladder does not
  fit in the room left under `PP_WALK_MAX_QUBITS` (`SQ_FIT_CROSS`, from
  [`cc7f10e`](cc7f10e.md)), the add is split into chunks by
  `width_composition::direct_plan` and run as a direct mapped add. By the
  room arithmetic in `cc7f10e`, this happens only at the three root nodes,
  with one boundary each (for example chunks `[32, 159]`).
- **Old flow** (`direct_add_phase_transport`, with `SQ_DEFER_CROSS_PHASE` on):
  - Forward: each boundary carry-out is measured with `hmr`. The outcome is
    kept as a classical bit, and no compare runs yet.
  - Inverse: the chunk ripple recreates the same carry and applies the stored
    `z_if`. It then measures the carry again and, conditioned on the outcome,
    erases its phase with `mapped_compare`.
  - `mapped_compare` is an **exact** full-chunk compare with the true incoming
    carry, about `w − 1` Toffoli for a chunk of `w` bits, run half the time.
- **New flow:**
  - Forward, `direct_add_hold`: the same chunks run through the new shared
    helper `direct_chunk`, but every non-final carry-out stays live. There is
    no `hmr`. The wires are returned and stored in the new field
    `K2Retained.held`.
  - Inverse, `direct_add_unhold`: it is called on the complemented
    accumulator with the forward's plan, so it has the same chunk carries. It
    runs chunks high to low, each with `out = held[j]`. That XORs the carry
    into a wire already holding it, which leaves `|0⟩`, and the wire is
    released.
  - High to low order matters: chunk `j` reads `held[j−1]` as its carry-in
    before that wire is cleared.
  - No measurement and no compare are needed. See
    [measurement-uncompute](../concepts/measurement-uncompute.md) for the
    measured alternative this replaces.
- **Size:** about one compare of ~31 bits at half rate per root, so about
  15–16 Toffoli each. The author measured the square patch at −47.6 Toffoli.

### 2. Wires that pay for the held carries (`square.rs`)

A held carry stays live from the forward assembly, through the consumer folds,
to the inverse assembly. Two loans keep the room the same:

- **`SQ_OWN_TOP_ZEROS=1`**, `own_top_zero_bits`. A node's cross word holds
  `2ab < 2^(lo+hi+1)` in `2(hi+1)` bits, so its top bit is always zero. When
  `lo < hi` the bit below is zero too.
  - During the node's own fitted assembly, those wires are dropped from the
    addend map and released.
  - `room` grows by their count.
  - They are reacquired afterwards.
- **`SQ_HIGH_CARRY_LOAN=1`**, in `square_b` / `square_b_inv`. The flat high
  child's sum carry `r.carry` is exactly `|0⟩` after `restore_square_sum`
  (because `t − a = b < 2^|b|`). It is released until `square_b_inv` re-forms
  the in-place sum.
- **`rehome_held` and `assembly_repay_held`.** A held carry can be allocated
  on a wire that is currently lent and must come back. These helpers move it
  to a fresh wire with 2 CX and no Toffoli.

### 3. `PP_SEED_SHORT_MUL_F_COST=1` (`pingpong.rs`, `joint_lowfold.rs`)

Background: [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).

- **Where.** In `replay_double_add`, the plain path erases the cell's overflow
  flag with a truncated, measurement-conditioned compare of width `k`. Before,
  narrow rounds (`policy_width < 38`) used it unseeded.
- **What changes.** The new branch sets `k −= 1` and seeds the compare with
  `source[N−k−1]`. That is the bit just below the shorter window, used as a
  borrow predictor, the same trick `CMP_SEED_ALL` already applies on the
  divide. The code comment says a seeded `k−1`-bit window has about the error
  of the unseeded `k`-bit one and costs one Toffoli less.
- **Planner.** `joint_lowfold::plan` prices those rounds with the shorter
  compare (`short_cost`), so the choice between the retained route and the
  plain route stays consistent.
- **Size.** The author's census found only 11 plain-path narrow multiply flag
  sites, about −0.5 Toffoli each on average.

### 4. `PP_FLAG_SHAPE`: `38:0,25:-2,0:-2` → `38:0,25:-1,0:-3`

- The band table offsets `flag_compare(round)` (base `PP_REPLAY_FLAG_COMPARE=20`)
  by the walk's policy width. Widths 25–37 (rounds 616–648) go from −2 to −1:
  one bit **wider**. Widths below 25 (rounds 649–697) go from −2 to −3: one bit
  **narrower**.
- Together with item 3 this is about −9 Toffoli (the author's measurement:
  894,804.0 → 894,794.8).
- **Tail nonce:** `TAIL_NONCE` 9342055114 → 9422592313.

## Why it is still correct, and what it risks

- **The hold is exact.** The inverse chunk ripple recomputes exactly the
  forward carry, because the product is unchanged between the two and the
  complemented subtraction has the same carries. XOR then clears it on every
  input. The loans use wires that are zero on every input.
- **Seeding and the flag shape are probabilistic.** A wrong compare
  prediction leaves a phase after the measured erase, which is a **phase**
  failure.
- **Measured λ:**
  - The square patch alone: 16.40 ± 0.36 over 128 nonces.
  - The full package: 16.74 ± 0.26 over 256 nonces, against 16.71 ± 0.36
    for the base.
  - The first 128-nonce block gave 17.34. Its estimate + 2 SE was 18.08,
    which fails the [`cc7f10e`](cc7f10e.md) contract gate. The author only
    ground a nonce after a second block brought the pooled estimate down.
- The shipped nonce draws a clean set: 9,024 of 9,024 shots, with 0
  classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- **Negative result from the same session:** `PP_REPLAY_CHUNK_COMPARE`
  21 → 20 would save 1,720 Toffoli but adds about +2.3 λ. No fold-window buy
  was cheap enough to pay for it, so it was not taken.

## Classification rationale

The main saving changes how a boundary carry is uncomputed. It stays coherent
until the mirror-image inverse clears it for free, instead of being measured
and erased with a conditional compare. That is the opposite of measurement
uncompute, hence the change-type "deferred coherent uncompute". The zero-wire
loans only make room for it. The runner-up reading is ancilla-lifetime
extension under Register and Scratch Allocation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f812a29 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol f812a29 b788efc -- src/point_add` is
   147 lines in 5 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol b788efc -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. This tree reads
   every knob from the fixed `env_raw` table in `mod.rs` and ignores the
   environment, so `SUB4_*`, `TLM_*`, `PP_*` or `HEO_*` variables have no
   effect. Expect:
   - 1251 qubits
   - 894,789 average Toffoli (894,788.753 before rounding)
   - score 1,119,381,039
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9422592313` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/joint_lowfold.rs b/src/point_add/joint_lowfold.rs
index e579a5d..5266510 100644
--- a/src/point_add/joint_lowfold.rs
+++ b/src/point_add/joint_lowfold.rs
@@ -31,8 +31,10 @@ fn plan(circ:&Builder,round:usize,multiply:bool,fw:usize)->Option<Plan> {
     if prefix+1>=hi-lo {return None;}
     let mut fk=if multiply {flag_compare(round)+usize::from(a5_policy()=="mul-f-plus1-early200"&&(2..202).contains(&round))}
         else {flag_compare(round)+usize::from(policy_width(round)>=flag_widen_div())};
-    let seeded=if multiply {policy_width(round)>=38 && matches!(a5_policy(),"mul-f-seed"|"mul-fb-seed")}else{env_flag("CMP_SEED_ALL")};
-    if !multiply && seeded {fk-=1;}
+    // EXP PP_SEED_SHORT_MUL_F_COST: the plain path's narrow multiply F compare is one bit shorter.
+    let short_cost=multiply && policy_width(round)<38 && env_flag("PP_SEED_SHORT_MUL_F_COST") && !env_flag("PP_SEED_SHORT_MUL_F_COST_NOPLAN");
+    let seeded=if multiply {(policy_width(round)>=38 && matches!(a5_policy(),"mul-f-seed"|"mul-fb-seed")) || short_cost}else{env_flag("CMP_SEED_ALL")};
+    if (!multiply && seeded) || short_cost {fk-=1;}
     if !seeded {fk=refined_unseeded_width(fk,N,"PP_REFINE_UNSEEDED_F");}
     let saving=(fk-1)as f64/2.0-missing as f64/2.0-(low as f64-33.0);
     if saving<=0.0 {return None;}
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 5a0d57a..6ef0cc3 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -47,7 +47,7 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_DEPTH_PROFILE" => "0:0",
         "PP_DIRECT_ENDPOINT" => "1",
         "PP_DIRECT_FOLD" => "1",
-        "PP_FLAG_SHAPE" => "38:0,25:-2,0:-2",
+        "PP_FLAG_SHAPE" => "38:0,25:-1,0:-3",
         "PP_FLAG_WIDEN_DIV" => "38",
         "PP_FOLD_PROFILE" => "38:0,32:-1,19:-4,0:-4",
         "PP_FOLD_WIDEN" => "0",
@@ -80,6 +80,7 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_REUSE_DIV_PARITY" => "1",
         "PP_REUSE_MUL_SELECTORS" => "1",
         "PP_ROUNDS_MUL" => "698",
+        "PP_SEED_SHORT_MUL_F_COST" => "1",
         "PP_SIMPLIFY" => "product,affine,quadratic,truth",
         "PP_SOURCE_SIGN_GROW" => "1",
         "PP_SOURCE_SIGN_LOAN" => "0",
@@ -102,11 +103,14 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_DEFER_CROSS_PHASE" => "1",
         "SQ_DIAG_PRELOAD" => "1",
         "SQ_FIT_CROSS" => "1",
+        "SQ_HIGH_CARRY_LOAN" => "1",
+        "SQ_HOLD_BOUNDARY" => "1",
         "SQ_LEND_ASSEMBLY_ZEROS" => "1",
         "SQ_LEND_RETAINED_ANDS" => "2",
         "SQ_LEND_RETAINED_CROSS2" => "2",
         "SQ_LEND_RETAINED_ZEROS" => "1",
         "SQ_ODD_NODE_TOPS" => "1",
+        "SQ_OWN_TOP_ZEROS" => "1",
         "SQ_ROW0_CARRY" => "1",
         "SQ_ROW0_INVERSE_CARRIES" => "1",
         "SQ_ROW_ALL_MEASURE_TOP" => "1",
@@ -117,7 +121,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_CROSS" => "1",
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
-        "TAIL_NONCE" => "9342055114",
+        "TAIL_NONCE" => "9422592313",
         _ => return None,
     };
     Some(value.to_owned())
@@ -221,7 +225,7 @@ fn build_point_add() -> Vec<Op> {
     circ.take_ops()
 }
 
-/// Emit the fixed I10 circuit and accepted public-validation nonce 9342055114.
+/// Emit the fixed I10 circuit and accepted public-validation nonce 9422592313.
 pub fn build() -> Vec<Op> {
     let mut ops = build_point_add();
     // Exact op-stream post-passes, ported from the 2026-09-04 warpspeed
diff --git a/src/point_add/pingpong.rs b/src/point_add/pingpong.rs
index ea673c5..5f37645 100644
--- a/src/point_add/pingpong.rs
+++ b/src/point_add/pingpong.rs
@@ -3032,6 +3032,17 @@ fn replay_double_add(
     let mut k = flag_compare(round) + usize::from(a5_policy() == "mul-f-plus1-early200" && (2..202).contains(&round));
     let borrow = if wide && matches!(a5_policy(), "mul-f-seed" | "mul-fb-seed") {
         Some(source[N - k - 1])
+    } else if !wide && env_flag("PP_SEED_SHORT_MUL_F_COST") {
+        // EXP PP_SEED_SHORT_MUL_F_COST: cost mode, as CMP_SEED_ALL on the divide.
+        // A seeded (k-1)-bit window has the error of the unseeded k-bit one and
+        // costs one Toffoli less. Excludes the keep-width variant and refinements.
+        assert!(!env_flag("PP_SEED_SHORT_MUL_F"),"short multiply seed: pick cost or keep-width mode");
+        for knob in ["PP_REFINE_UNSEEDED_F","PP_REFINE_SEEDED_F"] {
+            assert_eq!(super::optional_env::<usize>(knob).unwrap_or(0),0,
+                "short multiply cost seeding excludes flag refinement composition");
+        }
+        k -= 1;
+        Some(source[N-k-1])
     } else if !wide && env_flag("PP_SEED_SHORT_MUL_F") {
         // Extend source-bit prediction to the previously unseeded narrow
         // multiply flag sites. Keep the complete old comparison window;
diff --git a/src/point_add/square.rs b/src/point_add/square.rs
index 8bba62f..bb18dcb 100644
--- a/src/point_add/square.rs
+++ b/src/point_add/square.rs
@@ -428,6 +428,9 @@ struct K2Retained {
     /// The high half's own retained scratch, when [`sq_split_b_min`] split it.
     high: Option<Box<K2Retained>>,
     cross_phase: Option<(super::width_composition::Plan,Vec<(usize,BitId)>)>,
+    /// SQ_HOLD_BOUNDARY: live boundary carries of the fitted assembly, cleared
+    /// by the inverse assembly's high-to-low chunk ripple.
+    held: Vec<QubitId>,
 }
 
 /// Recursion policy: a sum half of at least this many bits is split again
@@ -489,6 +492,9 @@ fn square_b(circ: &mut Builder, bs: &[QubitId], b2: &[QubitId]) -> Option<Box<K2
     let mut t = inner.to_vec();
     t.push(r.carry);
     restore_square_sum(circ,a,&t);
+    // SQ_HIGH_CARRY_LOAN: t - a = b < 2^|b| left r.carry at exactly |0>, and
+    // nothing reads it until square_b_inv re-forms the in-place sum.
+    if super::env_flag("SQ_HIGH_CARRY_LOAN") {circ.release_clean(r.carry);}
     Some(Box::new(r))
 }
 
@@ -499,6 +505,7 @@ fn square_b_inv(circ: &mut Builder, bs: &[QubitId], b2: &[QubitId], retained: Op
     match retained {
         None => tri_square(circ, bs, b2, true),
         Some(r) => {
+            if super::env_flag("SQ_HIGH_CARRY_LOAN") {circ.reacquire(r.carry);}
             let (a, inner) = bs.split_at(bs.len() / 2);
             let mut t = inner.to_vec();
             t.push(r.carry);
@@ -545,18 +552,38 @@ fn tri_square_k2r_flat(circ: &mut Builder, x: &[QubitId], product: &[QubitId]) -
 /// Retain all internal boundary carries and pay their full phase cleanup.
 /// No fold/comparison truncation window is changed by this helper.
 fn add_cross(circ:&mut Builder,cross:&[QubitId],acc:&[QubitId],inverse:bool,
-    recover:Option<(super::width_composition::Plan,Vec<(usize,BitId)>)>)
+    recover:Option<(super::width_composition::Plan,Vec<(usize,BitId)>)>,held:&mut Vec<QubitId>)
     ->Option<(super::width_composition::Plan,Vec<(usize,BitId)>)> {
-    let room=super::pingpong::walk_max_qubits().saturating_sub(circ.active_qubits()as usize);
+    let mut room=super::pingpong::walk_max_qubits().saturating_sub(circ.active_qubits()as usize);
     if recover.is_some() || (super::env_flag("SQ_FIT_CROSS") && acc.len().saturating_sub(2)>room) {
+        // SQ_OWN_TOP_ZEROS: this node's own top cross bits are zero for every
+        // input (2ab < 2^(lo+hi+1)); add them as zero addend bits and lend them.
+        let tops=if super::env_flag("SQ_OWN_TOP_ZEROS"){own_top_zero_bits(cross,acc)}else{Vec::new()};
+        for &q in &tops{circ.release_clean(q);}
+        room+=tops.len();
         if inverse {circ.x_all(acc);}
         let n=acc.len()-1;
         let(plan,fixes)=recover.unwrap_or_else(||((room..=room.max(n)).find_map(|r|super::width_composition::direct_plan(n,r)).unwrap(),Vec::new()));
-        let map:Vec<Vec<QubitId>>=(1..acc.len()).map(|i|cross.get(i).copied().into_iter().collect()).collect();
+        let map:Vec<Vec<QubitId>>=(1..acc.len()).map(|i|cross.get(i).copied().filter(|q|!tops.contains(q)).into_iter().collect()).collect();
+        // SQ_HOLD_BOUNDARY: keep the chunk carry-outs live instead of measuring
+        // them. The inverse (forced onto this plan) recreates the same carries
+        // and XORs each back to zero, so no boundary phase ever needs repair.
+        if !inverse && super::env_flag("SQ_HOLD_BOUNDARY") {
+            *held=super::width_composition::direct_add_hold(circ,&map,&acc[1..],cross[0],&plan);
+            rehome_held(circ,held,&tops);
+            return Some((plan,Vec::new()));
+        }
+        if inverse && !held.is_empty() {
+            super::width_composition::direct_add_unhold(circ,&map,&acc[1..],cross[0],&plan,std::mem::take(held));
+            circ.x_all(acc);
+            for &q in &tops{circ.reacquire(q);}
+            return None;
+        }
         // bit0 of the source is zero, so acc[0] and the first carry stay put.
         let defer=!inverse && super::env_flag("SQ_DEFER_CROSS_PHASE");
         let pending=super::width_composition::direct_add_phase_transport(circ,&map,&acc[1..],cross[0],&plan,defer,&fixes);
         if inverse {circ.x_all(acc);}
+        for &q in &tops{circ.reacquire(q);}
         if super::env_flag("SQ_FIT_CROSS_TRACE") {eprintln!("FIT_CROSS {} {} {} {} {}",acc.len(),room,plan.peak,plan.extra2,inverse as u8);}
         if defer{return Some((plan,pending));}
     } else if cut_sqident() {
@@ -565,6 +592,31 @@ fn add_cross(circ:&mut Builder,cross:&[QubitId],acc:&[QubitId],inverse:bool,
     None
 }
 
+/// SQ_OWN_TOP_ZEROS: a node's retained cross holds 2ab in 2*(hi+1) bits, and
+/// 2ab < 2^(lo+hi+1): its top bit, and the one below when lo < hi, are zero.
+/// `acc` is product[lo..], of length 2m - lo = lo + 2hi.
+fn own_top_zero_bits(cross:&[QubitId],acc:&[QubitId])->Vec<QubitId>{
+    let n=cross.len();let hi=n/2-1;let lo=acc.len()-2*hi;
+    assert!(n%2==0 && lo<=hi && hi<=lo+1,"own_top_zero_bits: unexpected node shape");
+    if lo<hi{vec![cross[n-1],cross[n-2]]}else{vec![cross[n-1]]}
+}
+
+/// SQ_HOLD_BOUNDARY: a held carry may have been allocated on a wire that is
+/// currently lent (assembly loans, own top zeros). Reacquire every other lent
+/// wire, then move each such carry to a fresh wire (2 CX) so the lent wire is
+/// |0> and live again in its own role. No Toffoli, no measurement.
+fn rehome_held(circ:&mut Builder,held:&mut [QubitId],lent:&[QubitId]){
+    for &q in lent{if !held.contains(&q){circ.reacquire(q);}}
+    for h in held.iter_mut(){
+        if lent.contains(h){let f=circ.alloc_qubit();circ.cx(*h,f);circ.cx(f,*h);*h=f;}
+    }
+}
+fn assembly_repay_held(circ:&mut Builder,x:&[QubitId],product:&[QubitId],qs:Vec<QubitId>,held:&mut [QubitId]){
+    if held.is_empty(){assembly_repay(circ,x,product,qs);return;}
+    if qs.is_empty(){return;}
+    rehome_held(circ,held,&qs);circ.cx(x[0],product[0]);
+}
+
 /// The full sum is exactly a+b; removing a restores b and clears its extra
 /// top carry for every bitstring, independent of upstream field errors.
 fn restore_square_sum(circ:&mut Builder,a:&[QubitId],t:&[QubitId]) {
@@ -640,9 +692,10 @@ fn tri_square_k2r_inner(circ: &mut Builder, x: &[QubitId], product: &[QubitId],
     // product += 2ab << lo, exact full ripple to the top (x^2 < 2^(2m), so the
     // top never overflows).
     let loans=assembly_loans(circ,x,product,low.as_deref(),sum.as_deref(),high.as_deref());
-    let cross_phase=add_cross(circ,&cross,&product[lo..],false,None);
-    assembly_repay(circ,x,product,loans);
-    K2Retained { carry, cross, low, sum, high, cross_phase }
+    let mut held=Vec::new();
+    let cross_phase=add_cross(circ,&cross,&product[lo..],false,None,&mut held);
+    assembly_repay_held(circ,x,product,loans,&mut held);
+    K2Retained { carry, cross, low, sum, high, cross_phase, held }
 }
 
 /// Inverse of `tri_square_k2r`, consuming its retained scratch. Requires
@@ -655,7 +708,7 @@ fn tri_square_k2r_inv(
 ) {
     let m = x.len();
     assert_eq!(product.len(), 2 * m);
-    let K2Retained { carry, cross, low, sum, high, cross_phase } = retained;
+    let K2Retained { carry, cross, low, sum, high, cross_phase, mut held } = retained;
     let lo = m / 2;
     let (a, bs) = x.split_at(lo);
     let (a2, b2) = product.split_at(2 * lo);
@@ -663,7 +716,8 @@ fn tri_square_k2r_inv(
     t.push(carry);
     // product -= 2ab << lo: the halves are pure a^2 / b^2 again.
     let loans=assembly_loans(circ,x,product,low.as_deref(),sum.as_deref(),high.as_deref());
-    assert!(add_cross(circ,&cross,&product[lo..],true,cross_phase).is_none());
+    assert!(add_cross(circ,&cross,&product[lo..],true,cross_phase,&mut held).is_none());
+    assert!(held.is_empty(),"SQ_HOLD_BOUNDARY: held carries not cleared");
     assembly_repay(circ,x,product,loans);
     // cross: 2ab -> t^2, then clear it with the inverse square (which also
     // restores t if its own split modified it).
diff --git a/src/point_add/width_composition.rs b/src/point_add/width_composition.rs
index e24b156..6996f8b 100644
--- a/src/point_add/width_composition.rs
+++ b/src/point_add/width_composition.rs
@@ -191,3 +191,53 @@ pub(crate) fn direct_add_phase_transport(c:&mut Builder,map:&[Vec<QubitId>],b:&[
     assert_eq!(c.active_qubits(),base);
     pending
 }
+
+/// One chunk of the direct ripple, as in [`direct_add_phase_transport`]:
+/// carries chained from `prev`; a non-final chunk XORs its carry-out into
+/// `out`; the sum bits are finished in `b` and the ladder is unwound.
+fn direct_chunk(c:&mut Builder,map:&[Vec<QubitId>],b:&[QubitId],at:usize,w:usize,prev:QubitId,out:Option<QubitId>){
+    use super::pingpong::{fold_step,unwind_fold_step};
+    let end=at+w;
+    let work=c.alloc_qubits(if out.is_none(){w.saturating_sub(2)}else{w-1});
+    for i in 0..work.len(){let carry=if i==0{prev}else{work[i-1]};fold_step(c,b[at+i],carry,work[i],&map[at+i],false);}
+    let carry=work.last().copied().unwrap_or(prev);
+    if let Some(q)=out{fold_step(c,b[end-1],carry,q,&map[end-1],true);}else if w==1{
+        c.cx(prev,b[at]);for &s in &map[at]{c.cx(s,b[at]);}
+    }else{
+        fold_step(c,b[end-2],carry,b[end-1],&map[end-2],true);
+        for &s in &map[end-1]{c.cx(s,b[end-1]);}
+    }
+    for i in(0..work.len()).rev(){let carry=if i==0{prev}else{work[i-1]};unwind_fold_step(c,b[at+i],carry,work[i],&map[at+i]);}
+    c.free_vec(&work);
+}
+
+/// SQ_HOLD_BOUNDARY forward: the same exact chunked add, but every non-final
+/// chunk's carry-out stays live (no hmr, no compare). Returns those wires.
+pub(crate) fn direct_add_hold(c:&mut Builder,map:&[Vec<QubitId>],b:&[QubitId],incoming:QubitId,p:&Plan)->Vec<QubitId>{
+    assert_eq!(p.sizes.iter().sum::<usize>(),b.len());let base=c.active_qubits();
+    let k=p.sizes.len();let mut held=Vec::new();let mut at=0;let mut prev=incoming;
+    for(j,&w)in p.sizes.iter().enumerate(){
+        let out=if j+1<k{Some(c.alloc_qubit())}else{None};
+        direct_chunk(c,map,b,at,w,prev,out);
+        if let Some(q)=out{held.push(q);prev=q;}at+=w;
+    }
+    assert_eq!(c.active_qubits(),base+held.len() as u32);
+    held
+}
+
+/// SQ_HOLD_BOUNDARY inverse, called on the complemented accumulator with the
+/// forward's plan and map. The complemented add has the same chunk carries as
+/// the forward add, so chunk j run with out = held[j] returns it to zero.
+/// Chunks run high-to-low so each reads held[j-1] before it is cleared.
+pub(crate) fn direct_add_unhold(c:&mut Builder,map:&[Vec<QubitId>],b:&[QubitId],incoming:QubitId,p:&Plan,held:Vec<QubitId>){
+    assert_eq!(p.sizes.iter().sum::<usize>(),b.len());let base=c.active_qubits();
+    let k=p.sizes.len();assert_eq!(held.len(),k-1);
+    let starts:Vec<usize>=p.sizes.iter().scan(0,|s,&w|{let a=*s;*s+=w;Some(a)}).collect();
+    for j in(0..k).rev(){
+        let prev=if j==0{incoming}else{held[j-1]};
+        let out=if j+1<k{Some(held[j])}else{None};
+        direct_chunk(c,map,b,starts[j],p.sizes[j],prev,out);
+        if let Some(q)=out{c.release_clean(q);}
+    }
+    assert_eq!(c.active_qubits()+held.len() as u32,base);
+}
```

