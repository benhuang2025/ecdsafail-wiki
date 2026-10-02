# 5a08ebd — Known-output receivers: run reverse adds whose result is already known with no Toffoli, plus bridges, signed-average rounds and protection buys

| | |
| --- | --- |
| Contestant | mochimodev |
| Date | 2026-09-26 |
| Submission | `d6747e4` |
| Commit | `5a08ebdacf922f1e3df54156bd23b778eac5995b` |
| Result | 1251 qubits × 891,823 Toffoli = **1,115,670,573** |
| Base | `902ec7b` (dysnasia's SQ_ROW0_COPY tree): 1251 qubits × 893,854 Toffoli = 1,118,211,354 |
| Change vs base | qubits ±0, Toffoli −2,031, score −2,540,781 |
| Leaderboard Δ | −2,064,150, measured against the frontier at the time, `3019006` (1251 × 893,473 = 1,117,734,723), which is **not** this commit's base |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [adders-and-carries](../concepts/adders-and-carries.md), [pingpong-division](../concepts/pingpong-division.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change (about 1,000 changed lines; no single file is large enough to copy) |

## Summary

This is a package of many levers. The main new idea is a **known-output
receiver**. A ripple adder needs a Toffoli per carry because the carries
depend nonlinearly on the inputs. But in a reverse (uncompute) step the
adder's *result* is often already known: it is a fixed affine function (XORs
and constants) of wires that are still live. Then every carry follows from
the identity `carry[i-1] = a[i] ⊕ b[i] ⊕ sum[i]` and can be written with CX
gates alone. The receiver writes the carries that way, finishes the sum with
CX gates, then erases each carry with `hmr` and a Clifford phase repair. The
whole add costs no Toffoli.

The commit applies this in four places: the reverse of ping-pong round 2,
the reverse constants of round 1, the top carry of most walk-back rounds, and
the inverse row 1 of each square leaf. Around it come four other levers:
"bridge" adder stages that lend the replay one or two extra wires, an exact
signed-average walk step on 37 rounds (14 of them made one bit narrower), an
exact CCX→CX post-pass, and hand-set replay batch schedules. Several knobs go
the other way and buy back failure rate. Net: −2,031 Toffoli at the same 1251
qubits against the base, −1,650 against the leaderboard frontier `3019006`.

## What changed and why it saves Toffoli

All knobs are fixed entries of `env_raw()` in `src/point_add/mod.rs`. The new
ones carry `I…` prefixes (the author's internal lever numbers).

### 1. The receiver primitives (new files)

- **`affine_constant.rs::add_known(b, a, out)`**: `b += a` for a constant `a`,
  given the desired sum `out[i]` as an affine expression of other live wires.
  It computes `carry[i] = b[i+1] ⊕ a[i+1] ⊕ out[i+1]` with CX/X first, then
  applies the sum with X and CX, then measures each carry out with `hmr`. The
  carry is a quadratic function of the completed sum and the incoming carry
  (`a_i=0: p ⊕ p·s`; `a_i=1: 1 ⊕ s ⊕ p·s`), so the repair is `cz_if`/`z_if`.
  No Toffoli.
- **`known_stream.rs::add(a, b, cin, out)`**: the same for a register-plus-
  register add. It walks from the top bit down and keeps only two carry wires
  live at a time: each incoming carry `p = a[i] ⊕ b[i] ⊕ out[i]` is made with
  CX, used, and the outgoing one is measured out with the phase polynomial
  `a·s ⊕ a ⊕ a·p ⊕ s·p ⊕ p`. No Toffoli.
- **`stream_wide.rs::add`**: `known_stream` with a zero-extended (shorter)
  source.

See [measurement-uncompute](../concepts/measurement-uncompute.md) for why
`hmr` plus a CZ repair is a valid erase, and
[adders-and-carries](../concepts/adders-and-carries.md) for the ripple it
replaces.

### 2. Reverse round 2 and round 1 of the ping-pong walk (`pingpong.rs`)

- In the walk, round 1 sets `u ← (p ± v)/2`, and round 2 sets
  `v ← (v ± u)/2`. In the walk-back, reversing round 2 restores `v`. That
  restored value is fixed by round 1's relation: it is `2X ⊕ signmask ⊕ 1`,
  where `X` is `u` with round 1's constants taken out. So the reverse
  round-2 subtraction has a known result.
- `walk_back_round_phase`, `round == 2` (non-quarter, no deferred phase):
  calls the new `round2_fused::receive(source, target, sign, round1_window(m),
  half_f_minus_one() >> 1, N − 2)`. It
  1. copies the bits of `u` that the constants touch into a buffer,
  2. applies round 1's inverse constants once with the ordinary paid
     `sub_const` / `add_const`, leaving `u` at `X`,
  3. runs the round-2 reverse add as `known_stream::add` (no Toffoli) instead
     of `walk_add` (a ripple of about 256 Toffoli),
  4. erases the buffer with `affine_constant::add_known` and CX copies (no
     Toffoli), and calls `round2_fused::mark()`.
- `round1_reverse`: if `round2_fused::take()` is set, it skips its own
  `sub_const` / `add_const`, which step 2 already did. Otherwise (the `I31`
  path) it uses two `affine_constant::add_known` calls with the known result
  "`u` = arithmetic half of `v ⊕ sign`". The old constant adders remain only
  behind `I31_DISABLE`.
- `round2_receiver.rs` is an unfused variant used only with `I33_DISABLE`,
  which is pinned to 0.
- The walk-back runs in both the divide and the multiply traversal, so this
  saves roughly one 256-bit ripple per traversal.

### 3. Known top bit in walk-back adds (`modular.rs`, `top_result_loan.rs`)

- In the forward walk, every halving ends with
  `cx(target[m-2], target[m-1])`: the top bit is a copy of the bit below
  (the sign extension). Reversing round `r` restores the target to round
  `r − 2`'s output, so when the width is unchanged the restored top bit is
  known to equal its neighbour. Round 3 restores round 1's output, whose top
  two bits are zero.
- `walk_back_round_phase` sets `known_top` for non-quarter rounds with
  `m ≥ 6` and either `round == 3` or `width == value_width(round − 2)` (and
  round `r − 2` not an `I41` round). It wraps `walk_add` in
  `modular::with_top_copy(target, known_top, …)`.
- Inside, `terminal_step` calls the new `terminal_top_copy`: instead of the
  final `ccx(a[n-2], b[n-2], b[n-1])`, it measures `b[n-1]` with `hmr`,
  repairs the phase with `z_if`/`cz_if`, and rewrites the top as
  `cx(b[n-2], b[n-1])`. One Toffoli saved per such round.
  `ripple_add_source_sign_loan` gets the same branch.
- `I74_RESULT_TOP_LOAN=1` (`ripple_add_result_top_loan`): do that `hmr`
  *before* the ladder and use the now-zero top wire as the last carry. The add
  then owns one fewer carry wire. `walk_low_chunk` and the `PP_Q1208_HELPERS`
  test count this wire, so fewer walk-back adds have to be split into chunks.
  `I76_SOURCE_TOP_LOAN=1` allows it together with the source-sign loan.

### 4. Inverse row 1 of each square leaf (`square.rs`)

- After `SQ_ROW0_COPY` ([`902ec7b`](902ec7b.md)), the product after row 0 is
  a Clifford function of the leaf input. So when the inverse square undoes
  row 1, the result it must reach is known.
- `tri_square_cin`, `inverse && i == 1` with `SQ_ROW1_INVERSE_CARRIES=1`:
  passes `row1_known_output(x)` to `row_addsub_cin`, which with
  `SQ_ROW1_STREAM=1` runs `stream_wide::add` instead of
  `ripple_add_proved`. The inverse row 1 of every leaf now costs no Toffoli.
  See [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md).

### 5. Bridges: one or two extra wires for the replay (`bridge.rs`)

- `bridge::add` / `bridge::run` are ripples in which some carry stages are
  in-place Cuccaro MAJ stages: the carry is stored in the source wire
  `a[i]` instead of a fresh wire. Each such stage costs one extra CCX on the
  way back but needs one fewer carry wire. With `I50_SPLIT_BRIDGE=1` the
  common small case instead splits the ripple after `bridges + 1` low bits
  and erases the boundary carry with an exact full-width `erase_with_compare`.
- `I35_PROFILE` gives a bridge budget per `(round, traversal)`: 1 on 80
  multiply-replay rounds (408–423, 512–535, 547, 574–591, 620–639, 646) and
  1 or 2 on divide rounds 609, 619 and 620. `replay_add_halve` and
  `replay_double_add` enter that budget with `bridge::enter`.
- `composition_bounds`, `retained_rebalance` and `chunked_add` now plan the
  replay chunk layout for `room + budget` wires. When a ripple then exceeds
  the cap by `missing ≤ budget` wires, `modular::ripple_add` and
  `ripple_add_consume` cover the shortfall with `missing` bridge stages, so
  the real peak stays at the cap. The point: a layout with more room needs
  fewer chunk boundaries, and each boundary costs a truncated compare
  (about 10 executed Toffoli) while a bridge costs about 1. See
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).

### 6. Exact signed average on chosen walk rounds (`average.rs`)

- The plain walk adds or subtracts in `m` bits, wrapping, then halves and
  copies the sum's bit `m − 2` up as the sign. That is right only if the
  sum did not overflow `m` bits.
- `average::forward` instead computes the halved sum with its true sign:
  carry out ⊕ both operand signs. So it is exact whenever the operands fit.
  `average::reverse` undoes it, measuring the discarded doubling bit with
  `hmr` and repairing its phase.
- `I41_ROUNDS` (37 rounds, from 20 to 687) use it in both the walk and the
  walk-back. On these rounds it removes the overflow failure mode, so it is a
  precision buy.
- `I45_NARROW_ROUNDS` (14 of those rounds, 549–553, 586–587, 640–641, 648,
  683–686) then get `value_width − 1`: one bit less of register, which saves
  Toffoli in every add on that round. `value_width` asserts each narrowed
  round is an `I41` round and that the plain schedule is flat over
  `r − 2 … r`. This part is a precision bet: those values must still fit in
  the narrower register.

### 7. Exact CCX → CX post-pass (`interned_witness.rs`, 352 lines)

- `build()` now calls `interned_witness::witnesses(ops)` after the existing
  `PP_SIMPLIFY` chain and before the nonce tail.
- It tracks every wire as an affine combination of immutable "atoms" (inputs,
  measurement outcomes, and interned AND products). When a CCX's product
  `a·b` is already held, as the same atom, by another live wire, the CCX is
  replaced by a CX from that wire. This is exact on every input. See
  [dead-gate-strip](../concepts/dead-gate-strip.md).

### 8. Replay batch schedules

- `I12_DIV_PROFILE`: explicit batch ends for divide rounds 192–684
  (mostly one round per batch, merged runs such as 250–392 and 433–496).
  It overrides the automatic `min_by_key` choice in `divide_traversal`.
- `I12_MUL_PROFILE`: explicit batch ranges `hi:lo` for the late multiply
  rounds (44 entries), overriding the footprint rule in `multiply_traversal`.
- `PP_TAIL_DIV` 684 → 682 and `PP_TAIL_MUL` 645 → 655. This is `plan.r2`:
  the trailing replay batch is rounds `r2 + 1` to the end.

### 9. Ported from `0a06121` (dysnasia)

- `PP_WALK_EXTRA_ROUNDS = "683:4:1"` with the `walk_extra()` function: one
  extra physical walk bit on rounds 683–686.
- `SQ_ASM_TAIL`: the square's cross-term add ripples its carry only `E` bits
  past the cross word (`add_cross`). `0a06121` used 21; this commit uses 24,
  which is wider and safer.

### 10. Protection buys (wider, so they cost Toffoli)

- `ERASE_COMPARE` 23 → 24 (modular add/sub overflow compare).
- `FOLD_GUARD` 24 → 25 (headroom of every truncated `f` fold, so `f_slice`
  goes 57 → 58 and `round1_window` 55 → 56). See
  [modular-fold](../concepts/modular-fold.md).
- `PP_FOLD_WIDEN` 76 → 242: replay fold window +1 bit on rounds below 242
  instead of below 76.
- `PP_RETAIN_EXACT_DIV` and `PP_RETAIN_EXACT_MUL` 0 → 1: retained folds use
  an exact carry prefix when it fits in 4 extra wires.
- `PP_RETAIN_LATE_WIDEN` 0 → 3: retained fold window +3 bits where the walk
  width is below 32.
- `PP_CHUNK_SHAPE` `38:0,25:-2,0:-4` → `64:0,38:1,25:-2,0:-4`: the replay
  chunk compare is one bit wider (22 instead of 21) on rounds whose walk
  width is 38 to 63.
- `I12_B_GUARD=4` in `retained_prebias.rs`: the chunk-boundary compare
  widens by 4 bits on divide rounds 589–620, 642–645 and 647–648.

### 11. Small edits

- `TAIL_NONCE` 14939365091 → 211106234700983.
- `PP_SEED_SHORT_MUL_F_COST`, `SQ_HIGH_CARRY_LOAN`, `SQ_HOLD_BOUNDARY`,
  `SQ_OWN_TOP_ZEROS` and `SQ_ROW0_COPY` move inside the table with unchanged
  values.
- `SQ_LEND_RETAINED_CROSS3 = 0` and the `I35_TRACE`, `I35_CELLS`,
  `I35_BUDGET` pins are read by nothing that changes the circuit.
- `builder.rs` gains `i35_cost()` (reads the cost model, which is off) and
  `i13_dims()` (unused).

## Why it is still correct, and what it risks

- **Exact parts.** All receivers (sections 1–4) are exact, given that the
  known result really holds. Each relies on a structural identity: round 1's
  relation, the sign-extension copy, or the row-0 copy. If the result were
  wrong, the CX-built carries would be wrong and the run would fail on the
  classical or ancilla channel. The bridge stages and the split bridge (an
  exact full-width compare), the signed average itself, and the witness
  post-pass are exact too.
- **Probabilistic parts.** The 14 `I45` narrowed rounds, `SQ_ASM_TAIL = 24`,
  and the existing truncated folds and compares. The replay layouts changed,
  so their truncated chunk compares sit in new places.
- **Protection.** Section 10 widens several of those windows, and `I41`
  removes the overflow risk on 37 rounds. These lower λ, the expected number
  of failing test shots, so that a clean nonce can be found.
- The shipped nonce `211106234700983` draws a clean test set: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The lever that is new and recurs in most of the sections replaces Toffoli
carry ladders in reverse steps with CX-built carries, an `hmr` erase and a
Clifford repair. That is measurement uncompute. It was a close call. The
bridges (section 5) are a register/scratch-allocation trade, the `I45`
narrowing and section 10 are width-truncation moves, and the witness pass is
a dead-gate strip. No single lever's share of the −2,031 Toffoli can be read
from the code alone.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 902ec7b -- src/point_add`.
   - The git parent is `3019006` (dysnasia), which is `902ec7b` plus
     `0a06121`'s two levers and two nonce changes. This commit re-ports those
     levers itself (section 9), at new places in the files.
   - Against the parent, the diff is 1,010 changed lines in 15 files. Most is
     the same as below, plus noise: `walk_extra()` is deleted next to
     `value_width` and re-added at the end of `pingpong.rs`, and the
     `PP_WALK_EXTRA_ROUNDS` and `SQ_ASM_TAIL` pins move.
   - Against `902ec7b`, `git diff --ignore-cr-at-eol 902ec7b 5a08ebd -- src/point_add`
     is 1,006 changed lines in 15 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base, including eight new
   files.
3. **Check the tree.** `git diff --ignore-cr-at-eol 5a08ebd -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. This tree reads
   no environment variables: every knob is a fixed entry in `env_raw()`, so
   `PP_*`, `SQ_*`, `I*` or `SUB4_*` overrides are ignored. Leave them unset
   anyway. Expect:
   - 1251 qubits
   - 891,823 average Toffoli (rounded)
   - score 1,115,670,573
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `211106234700983` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/affine_constant.rs b/src/point_add/affine_constant.rs
new file mode 100644
index 0000000..96cc041
--- /dev/null
+++ b/src/point_add/affine_constant.rs
@@ -0,0 +1,28 @@
+//! Add a constant on a proved subspace where the complete output is affine
+//! in unchanged, disjoint live wires. This is NOT an unrestricted adder.
+use super::Builder;
+use alloy_primitives::U256;
+use crate::circuit::QubitId;
+
+pub(crate) fn add_known(c:&mut Builder,b:&[QubitId],a:U256,out:&[(bool,Vec<QubitId>)]){
+    let n=b.len();assert!(n>=1 && n<=256);assert_eq!(n,out.len());
+    assert!(out.iter().all(|(_,qs)|qs.iter().all(|q|!b.contains(q))));
+    let carries=c.alloc_qubits(n-1);
+    // c_i = old_b[i+1] XOR a[i+1] XOR desired_sum[i+1].
+    // Compute all of them before touching the original accumulator.
+    for(i,&q)in carries.iter().enumerate(){
+        c.cx(b[i+1],q);if a.bit(i+1)^out[i+1].0{c.x(q);}
+        for &s in &out[i+1].1{c.cx(s,q);}
+    }
+    for(i,&q)in b.iter().enumerate(){if a.bit(i){c.x(q);}if i>0{c.cx(carries[i-1],q);}}
+    // Given the completed sum s and incoming p:
+    // a_i=0: c_i=p XOR p*s; a_i=1: c_i=1 XOR s XOR p*s.
+    // Both are quadratic, so measured carry repair uses Clifford gates only.
+    for i in(0..n-1).rev(){
+        let m=c.alloc_bit();c.hmr(carries[i],m);
+        if i>0{c.cz_if(carries[i-1],b[i],m);}
+        if a.bit(i){c.x(b[i]);c.z_if(b[i],m);c.x(b[i]);}
+        else if i>0{c.z_if(carries[i-1],m);}
+        c.free_bit(m);c.free(carries[i]);
+    }
+}
diff --git a/src/point_add/average.rs b/src/point_add/average.rs
new file mode 100644
index 0000000..c844792
--- /dev/null
+++ b/src/point_add/average.rs
@@ -0,0 +1,76 @@
+//! Exact signed high-word half-step, with its inverse; no persistent guard rail.
+use super::{Builder,bridge};
+use crate::circuit::QubitId;
+fn run(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:QubitId,cout:QubitId,bridges:usize,
+    consume:impl FnOnce(&mut Builder,Option<QubitId>,QubitId,QubitId,Option<QubitId>)) {
+    let n=a.len();let k=bridges+1;
+    if bridges>=2 && 2*k<=n {
+        // Both chunks and the full, exact repair fit the direct bridge budget.
+        let boundary=c.alloc_qubit();
+        bridge::run(c,&a[..k],&b[..k],Some(cin),Some(boundary),0,|_,_,_,_,_|{});
+        bridge::run(c,&a[k..],&b[k..],Some(boundary),Some(cout),0,consume);
+        // For s=(a+b+cin) mod 2^k, carry == borrow(s-a-cin).
+        // The source, completed low sum and original carry-in are still live.
+        super::compare::erase_with_compare(c,boundary,&b[..k],&a[..k],Some(cin));
+        c.free(boundary);
+    } else {bridge::run(c,a,b,Some(cin),Some(cout),bridges,consume);}
+}
+fn right(c:&mut Builder,b:&[QubitId]){for i in 0..b.len()-1{c.swap(b[i],b[i+1]);}}
+fn left(c:&mut Builder,b:&[QubitId]){for i in(0..b.len()-1).rev(){c.swap(b[i],b[i+1]);}}
+pub(crate) fn forward(c:&mut Builder,source:&[QubitId],target:&[QubitId],sign:QubitId,bridges:usize){
+    let m=source.len();assert_eq!(m,target.len());assert!(m>=4);
+    // sign=source[0] XOR target[0]. Complementing source makes the low
+    // operands equal; the low sum is1 and its outgoing carry is source[0].
+    c.cx_all(sign,source);c.cx(source[0],target[0]);
+    run(c,&source[1..],&target[1..],source[0],target[0],bridges,|c,o,_a,s,p|{
+        // Correct signed extension = unsigned carry XOR both original signs.
+        // Their XOR is completed top sum XOR its incoming carry.
+        let q=o.unwrap();c.cx(s,q);c.cx(p.unwrap(),q);
+    });
+    c.cx_all(sign,source);right(c,target);
+}
+// q is the old signed doubling bit. On the valid inverse image,
+// q = carry_out XOR source_top XOR sum_top. Measure q, then repair its
+// phase while the carry into the top is live. q itself hosts that carry.
+fn receive_single(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:QubitId,q:QubitId,bridges:usize) {
+    let n=a.len();assert!(n>=3 && bridges<n-2);assert_eq!(n,b.len());
+    let phase=c.alloc_bit();c.hmr(q,phase);
+    let first=n-2-bridges;
+    let is_bridge=|i:usize|i>=first && i<n-2;
+    let mut carries:Vec<_>=(0..n-2).map(|i|if is_bridge(i){a[i]}else{c.alloc_qubit()}).collect();
+    carries.push(q);
+    let previous=|i:usize|if i==0{cin}else{carries[i-1]};
+    for i in 0..n-1 {let p=previous(i);
+        if is_bridge(i){c.cx(a[i],b[i]);c.cx(a[i],p);c.ccx(b[i],p,a[i]);}
+        else {c.cx(p,a[i]);c.cx(p,b[i]);c.ccx(a[i],b[i],carries[i]);c.cx(p,carries[i]);}
+    }
+    c.cx(q,b[n-1]);c.cx(a[n-1],b[n-1]);
+    // In completed-top coordinates: q_old = a*s + a*p + s*p + p + s.
+    c.cz_if(a[n-1],b[n-1],phase);c.cz_if(a[n-1],q,phase);
+    c.cz_if(b[n-1],q,phase);c.z_if(q,phase);c.z_if(b[n-1],phase);c.free_bit(phase);
+    for i in(0..n-1).rev(){let p=previous(i);
+        if is_bridge(i){c.ccx(b[i],p,a[i]);c.cx(a[i],p);c.cx(p,b[i]);}
+        else {c.cx(p,carries[i]);let bit=c.alloc_bit();c.hmr(carries[i],bit);
+            c.cz_if(a[i],b[i],bit);c.free_bit(bit);if i<n-2{c.free(carries[i]);}
+            c.cx(p,a[i]);c.cx(a[i],b[i]);}
+    }
+}
+fn receive(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:QubitId,q:QubitId,bridges:usize) {
+    let n=a.len();let k=bridges+1;
+    if bridges>=2 && 2*k<n {
+        let boundary=c.alloc_qubit();
+        bridge::run(c,&a[..k],&b[..k],Some(cin),Some(boundary),0,|_,_,_,_,_|{});
+        receive_single(c,&a[k..],&b[k..],boundary,q,0);
+        super::compare::erase_with_compare(c,boundary,&b[..k],&a[..k],Some(cin));
+        c.free(boundary);
+    } else {receive_single(c,a,b,cin,q,bridges);}
+}
+pub(crate) fn reverse(c:&mut Builder,source:&[QubitId],target:&[QubitId],sign:QubitId,bridges:usize){
+    let m=source.len();assert_eq!(m,target.len());assert!(m>=4);
+    left(c,target);c.x(sign);c.cx_all(sign,source);
+    // target[0] holds the discarded signed doubling bit, not a clean zero.
+    // The final carry only XORs into it and is never consumed as a carry-in.
+    receive(c,&source[1..],&target[1..],source[0],target[0],bridges);
+    c.cx(source[0],target[0]);c.x(target[0]);
+    c.cx_all(sign,source);c.x(sign);
+}
diff --git a/src/point_add/bridge.rs b/src/point_add/bridge.rs
new file mode 100644
index 0000000..117fa2b
--- /dev/null
+++ b/src/point_add/bridge.rs
@@ -0,0 +1,70 @@
+//! A bounded number of Cuccaro carry stages inside a measured ripple.
+//! Each in-place stage trades one extra CCX for one fewer owned carry wire.
+use super::Builder;
+use crate::circuit::QubitId;
+pub(crate) fn add(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:Option<QubitId>,cout:Option<QubitId>,bridges:usize){
+    run(c,a,b,cin,cout,bridges,|_,_,_,_,_|{});
+}
+pub(crate) fn run(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:Option<QubitId>,cout:Option<QubitId>,bridges:usize,
+    consume:impl FnOnce(&mut Builder,Option<QubitId>,QubitId,QubitId,Option<QubitId>)){
+    let n=b.len();let owned=if cout.is_some(){n-1}else{n-2};let k=bridges+1;
+    if super::env_flag("I50_SPLIT_BRIDGE") && bridges>0 && bridges<owned
+        && k<=owned-bridges && n-k>=3 {
+        assert_eq!(a.len(),n);assert!(a.iter().all(|q|!b.contains(q)));
+        assert!(cin.is_none_or(|q|!a.contains(&q)&&!b.contains(&q)));
+        assert!(cout.is_none_or(|q|!a.contains(&q)&&!b.contains(&q)&&Some(q)!=cin));
+        let boundary=c.alloc_qubit();
+        // The low sum finishes before the high carry ladder is allocated.
+        // This also supports the useful two-bit low chunk for bridges=1.
+        super::modular::ripple_add_proved(c,&a[..k],&b[..k],cin,Some(boundary),
+            super::modular::Carry0::Full,super::modular::Carry1::Full,None,None,None,None);
+        raw_run(c,&a[k..],&b[k..],Some(boundary),cout,0,consume);
+        // Carry = borrow(completed low sum - original source - carry-in).
+        // Exact full-k-bit phase repair; no approximate comparator is used.
+        super::compare::erase_with_compare(c,boundary,&b[..k],&a[..k],cin);
+        c.free(boundary);
+    } else {raw_run(c,a,b,cin,cout,bridges,consume);}
+}
+fn raw_run(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:Option<QubitId>,cout:Option<QubitId>,bridges:usize,
+    consume:impl FnOnce(&mut Builder,Option<QubitId>,QubitId,QubitId,Option<QubitId>)){
+    let n=b.len();assert_eq!(a.len(),n);assert!(n>=3);
+    assert!(a.iter().all(|q|!b.contains(q)));assert!(cin.is_none_or(|q|!a.contains(&q)&&!b.contains(&q)));
+    assert!(cout.is_none_or(|q|!a.contains(&q)&&!b.contains(&q)&&Some(q)!=cin));
+    let owned=if cout.is_some(){n-1}else{n-2};assert!(bridges<owned);
+    let first=owned-bridges;
+    let is_bridge=|i:usize|i>=first&&i<owned;
+    let mut carries:Vec<_>=(0..owned).map(|i|if is_bridge(i){a[i]}else{c.alloc_qubit()}).collect();carries.extend(cout);
+    let previous=|i:usize|if i==0{cin}else{Some(carries[i-1])};
+    for i in 0..carries.len(){let p=previous(i);
+        if is_bridge(i){let p=p.unwrap();c.cx(a[i],b[i]);c.cx(a[i],p);c.ccx(b[i],p,a[i]);}
+        else{if let Some(p)=p{c.cx(p,a[i]);c.cx(p,b[i]);}c.ccx(a[i],b[i],carries[i]);if let Some(p)=p{c.cx(p,carries[i]);}}
+    }
+    if cout.is_some(){if let Some(p)=previous(n-1){c.cx(p,a[n-1]);}c.cx(a[n-1],b[n-1]);}
+    else{let i=n-2;let p=previous(i);if let Some(p)=p{c.cx(p,a[i]);c.cx(p,b[i]);}
+        c.ccx(a[i],b[i],b[n-1]);if let Some(p)=p{c.cx(p,b[n-1]);}c.cx(a[n-1],b[n-1]);
+        if let Some(p)=p{c.cx(p,a[i]);}c.cx(a[i],b[i]);
+    }
+    consume(c,cout,a[n-1],b[n-1],if cout.is_some(){previous(n-1)}else{None});
+    for i in(0..owned).rev(){let p=previous(i);
+        if is_bridge(i){let p=p.unwrap();c.ccx(b[i],p,a[i]);c.cx(a[i],p);c.cx(p,b[i]);}
+        else{if let Some(p)=p{c.cx(p,carries[i]);}let m=c.alloc_bit();c.hmr(carries[i],m);c.cz_if(a[i],b[i],m);c.free_bit(m);c.free(carries[i]);
+            if let Some(p)=p{c.cx(p,a[i]);}c.cx(a[i],b[i]);}
+    }
+}
+
+thread_local!{static CURRENT:std::cell::Cell<Option<usize>>=const{std::cell::Cell::new(None)};}
+pub(crate) fn budget()->usize{CURRENT.with(|v|v.get()).unwrap_or_else(||super::optional_env::<usize>("I35_BUDGET").unwrap_or(0))}
+pub(crate) struct Scope(Option<usize>);
+impl Drop for Scope{fn drop(&mut self){CURRENT.with(|v|v.set(self.0));}}
+pub(crate) fn enter(round:usize,multiply:bool)->Scope{
+    static PROFILE:std::sync::OnceLock<std::collections::BTreeMap<(usize,bool),usize>>=std::sync::OnceLock::new();
+    let profile=PROFILE.get_or_init(||{
+        let mut p=std::collections::BTreeMap::new();
+        if let Some(s)=super::env_raw("I35_PROFILE"){for item in s.split(',').filter(|s|!s.is_empty()){
+            let v:Vec<usize>=item.split(':').map(|x|x.parse().unwrap()).collect();assert_eq!(v.len(),3);assert!(v[1]<=1&&v[2]<=32);
+            assert!(p.insert((v[0],v[1]!=0),v[2]).is_none());
+        }}p
+    });
+    let b=profile.get(&(round,multiply)).copied().unwrap_or_else(||super::optional_env::<usize>("I35_BUDGET").unwrap_or(0));
+    Scope(CURRENT.with(|v|v.replace(Some(b))))
+}
diff --git a/src/point_add/builder.rs b/src/point_add/builder.rs
index 69979a6..a296acc 100644
--- a/src/point_add/builder.rs
+++ b/src/point_add/builder.rs
@@ -43,7 +43,8 @@ impl Builder {
     pub fn new() -> Self {
         Self {
             ops: Vec::new(),
-            model: false, // Always emit operations; no count-only research mode.
+            // Count-only model mode is disabled in this submission.
+            model: false,
             model_depth: 0, model_total: 0, model_weighted: 0.0,
             model_phase_native: 0, model_phase_weighted: 0.0, model_max: 0,
             phase_kind_ops: [0; OP_KINDS],
@@ -60,6 +61,8 @@ impl Builder {
             replay_sites: ReplaySites::new(),
         }
     }
+    pub(crate) fn i35_cost(&self)->f64{self.model_weighted}
+    pub fn i13_dims(&self)->(usize,usize){(self.next_qubit as usize,self.next_bit as usize)}
     pub fn take_ops(&mut self) -> Vec<Op> {
         if self.model {
             eprintln!("MODEL_PHASE {} {} {} {}", self.phase, self.peak_qubits,
diff --git a/src/point_add/interned_witness.rs b/src/point_add/interned_witness.rs
new file mode 100644
index 0000000..cc20e76
--- /dev/null
+++ b/src/point_add/interned_witness.rs
@@ -0,0 +1,352 @@
+//! I25: exact CCX support identities with immutable nonlinear interning. An atom denotes a Boolean
+//! function at its creation boundary, never a mutable wire or classical bit.
+//! Unknown products and oversized expressions get fresh, non-reused atoms.
+
+use crate::circuit::{analyze_ops, Op, OperationType, QubitId, QubitOrBit, NO_BIT};
+
+const ATOM_CAP: usize = 32;
+const PRODUCT_CAP: usize = 200_000;
+
+#[derive(Clone, PartialEq, Eq, Hash)]
+struct Affine {
+    constant: bool,
+    atoms: Vec<u64>,
+}
+
+impl Affine {
+    fn constant(value: bool) -> Self {
+        Self {
+            constant: value,
+            atoms: Vec::new(),
+        }
+    }
+
+    fn is_zero(&self) -> bool {
+        !self.constant && self.atoms.is_empty()
+    }
+
+    fn is_one(&self) -> bool {
+        self.constant && self.atoms.is_empty()
+    }
+
+    fn complement(&self) -> Self {
+        Self {
+            constant: !self.constant,
+            atoms: self.atoms.clone(),
+        }
+    }
+
+    fn complements(&self, other: &Self) -> bool {
+        self.constant != other.constant && self.atoms == other.atoms
+    }
+}
+
+pub(super) enum Rewrite {
+    Keep,
+    Drop,
+    X,
+    Cx(QubitId),
+}
+
+impl Rewrite {
+    pub(super) fn emit(self, op: Op, result: &mut Vec<Op>) {
+        match self {
+            Rewrite::Keep => result.push(op),
+            Rewrite::Drop => {}
+            rewrite => {
+                let mut replacement = Op::empty();
+                replacement.q_target = op.q_target;
+                replacement.c_condition = op.c_condition;
+                match rewrite {
+                    Rewrite::X => replacement.kind = OperationType::X,
+                    Rewrite::Cx(control) => {
+                        replacement.kind = OperationType::CX;
+                        replacement.q_control1 = control;
+                    }
+                    _ => unreachable!(),
+                }
+                replacement.validate();
+                result.push(replacement);
+            }
+        }
+    }
+}
+
+pub(super) struct Support {
+    qubits: Vec<Affine>,
+    bits: Vec<Affine>,
+    base_condition: Affine,
+    condition_stack: Vec<Affine>,
+    next_atom: u64,
+    products: std::collections::HashMap<(Vec<u64>,Vec<u64>),u64>,
+}
+
+impl Support {
+    pub(super) fn new(ops: &[Op]) -> Self {
+        let (nq, nb, _, registers) = analyze_ops(ops.iter());
+        let mut quantum_inputs = vec![false; nq as usize];
+        let mut classical_inputs = vec![false; nb as usize];
+        for register in registers {
+            for slot in register {
+                match slot {
+                    QubitOrBit::Qubit(q) => quantum_inputs[q.0 as usize] = true,
+                    QubitOrBit::Bit(b) => classical_inputs[b.0 as usize] = true,
+                }
+            }
+        }
+        let mut state = Self {
+            qubits: vec![Affine::constant(false); nq as usize],
+            bits: vec![Affine::constant(false); nb as usize],
+            base_condition: Affine::constant(true),
+            condition_stack: Vec::new(),
+            next_atom: 0,
+            products: std::collections::HashMap::new(),
+        };
+        // Both kinds of ABI slot are unknown. Repeated annotations for one
+        // physical slot still describe the same value.
+        for (q, input) in quantum_inputs.into_iter().enumerate() {
+            if input {
+                state.qubits[q] = state.fresh();
+            }
+        }
+        for (b, input) in classical_inputs.into_iter().enumerate() {
+            if input {
+                state.bits[b] = state.fresh();
+            }
+        }
+        state
+    }
+
+    fn fresh(&mut self) -> Affine {
+        let id = self.next_atom;
+        self.next_atom = id.checked_add(1).expect("affine atom identifier overflow");
+        Affine {
+            constant: false,
+            atoms: vec![id],
+        }
+    }
+
+    fn xor(&mut self, a: &Affine, b: &Affine) -> Affine {
+        let mut atoms = Vec::with_capacity(a.atoms.len() + b.atoms.len());
+        let (mut i, mut j) = (0, 0);
+        while i < a.atoms.len() || j < b.atoms.len() {
+            if j == b.atoms.len() || (i < a.atoms.len() && a.atoms[i] < b.atoms[j]) {
+                atoms.push(a.atoms[i]);
+                i += 1;
+            } else if i == a.atoms.len() || b.atoms[j] < a.atoms[i] {
+                atoms.push(b.atoms[j]);
+                j += 1;
+            } else {
+                i += 1;
+                j += 1;
+            }
+        }
+        if atoms.len() > ATOM_CAP {
+            // This fresh atom represents the entire XOR, including its
+            // constant. It must not be mistaken for zero or an older atom.
+            self.fresh()
+        } else {
+            Affine {
+                constant: a.constant ^ b.constant,
+                atoms,
+            }
+        }
+    }
+
+    fn and(&mut self, a: &Affine, b: &Affine) -> Affine {
+        if a.is_zero() || b.is_zero() || a.complements(b) {
+            Affine::constant(false)
+        } else if a.is_one() {
+            b.clone()
+        } else if b.is_one() || a == b {
+            a.clone()
+        } else {
+            // Keys denote complete immutable Boolean expressions, never wire
+            // slots. HashMap checks exact key equality, not just a hash value.
+            // (A^ca)(B^cb) = AB ^ ca*B ^ cb*A ^ ca*cb.
+            let ca=a.constant; let cb=b.constant;
+            let aa=Affine {constant:false, atoms:a.atoms.clone()};
+            let bb=Affine {constant:false, atoms:b.atoms.clone()};
+            let mut linear=Affine::constant(ca && cb);
+            if ca {linear=self.xor(&linear,&bb);}
+            if cb {linear=self.xor(&linear,&aa);}
+            let mut left=aa.atoms;let mut right=bb.atoms;
+            if left>right {std::mem::swap(&mut left,&mut right);}
+            let key=(left,right);
+            let id=if let Some(&id)=self.products.get(&key){id}else{
+                // Forgetting cache entries only loses proofs. No atom ID is
+                // recycled, and all live expressions keep their old meaning.
+                if self.products.len()>=PRODUCT_CAP {self.products.clear();}
+                let id=self.fresh().atoms[0];self.products.insert(key,id);id
+            };
+            self.xor(&linear,&Affine{constant:false,atoms:vec![id]})
+        }
+    }
+
+    fn ccx_rewrite(condition: &Affine, a: &Affine, b: &Affine, op: &Op) -> Rewrite {
+        if condition.is_zero() || a.is_zero() || b.is_zero() || a.complements(b) {
+            Rewrite::Drop
+        } else if a.is_one() && b.is_one() {
+            Rewrite::X
+        } else if a.is_one() {
+            Rewrite::Cx(op.q_control2)
+        } else if b.is_one() || a == b {
+            Rewrite::Cx(op.q_control1)
+        } else {
+            Rewrite::Keep
+        }
+    }
+
+    pub(super) fn step(&mut self, op: &Op) -> Rewrite {
+        if op.kind == OperationType::PushCondition {
+            self.condition_stack.push(self.base_condition.clone());
+            // Snapshot the current value, not a reference to the bit slot.
+            self.base_condition = self.and(
+                &self.base_condition.clone(),
+                &self.bits[op.c_condition.0 as usize].clone(),
+            );
+            return Rewrite::Keep;
+        }
+        if op.kind == OperationType::PopCondition {
+            if let Some(saved) = self.condition_stack.pop() {
+                self.base_condition = saved;
+            }
+            return Rewrite::Keep;
+        }
+
+        let mut condition = self.base_condition.clone();
+        if op.c_condition != NO_BIT {
+            condition = self.and(&condition, &self.bits[op.c_condition.0 as usize].clone());
+        }
+
+        match op.kind {
+            OperationType::CCX => {
+                let a = self.qubits[op.q_control1.0 as usize].clone();
+                let b = self.qubits[op.q_control2.0 as usize].clone();
+                let rewrite = Self::ccx_rewrite(&condition, &a, &b, op);
+                let product = self.and(&a, &b);
+                let toggle = self.and(&condition, &product);
+                let target = op.q_target.0 as usize;
+                self.qubits[target] = self.xor(&self.qubits[target].clone(), &toggle);
+                return rewrite;
+            }
+            OperationType::CX => {
+                let target = op.q_target.0 as usize;
+                let toggle = self.and(&condition, &self.qubits[op.q_control1.0 as usize].clone());
+                self.qubits[target] = self.xor(&self.qubits[target].clone(), &toggle);
+            }
+            OperationType::X => {
+                let target = op.q_target.0 as usize;
+                self.qubits[target] = self.xor(&self.qubits[target].clone(), &condition);
+            }
+            OperationType::Swap => {
+                let a = op.q_control1.0 as usize;
+                let b = op.q_target.0 as usize;
+                let difference = self.xor(&self.qubits[a].clone(), &self.qubits[b].clone());
+                let toggle = self.and(&condition, &difference);
+                // Both destinations share this same actual conditional delta.
+                let left = self.xor(&self.qubits[a].clone(), &toggle);
+                let right = self.xor(&self.qubits[b].clone(), &toggle);
+                self.qubits[a] = left;
+                self.qubits[b] = right;
+            }
+            OperationType::Hmr => {
+                let target = op.q_target.0 as usize;
+                let bit = op.c_target.0 as usize;
+                let outcome = self.fresh();
+                let difference = self.xor(&self.bits[bit].clone(), &outcome);
+                let toggle = self.and(&condition, &difference);
+                self.bits[bit] = self.xor(&self.bits[bit].clone(), &toggle);
+                self.qubits[target] =
+                    self.and(&self.qubits[target].clone(), &condition.complement());
+            }
+            OperationType::R => {
+                let target = op.q_target.0 as usize;
+                self.qubits[target] =
+                    self.and(&self.qubits[target].clone(), &condition.complement());
+            }
+            OperationType::BitInvert => {
+                let bit = op.c_target.0 as usize;
+                self.bits[bit] = self.xor(&self.bits[bit].clone(), &condition);
+            }
+            OperationType::BitStore0 => {
+                let bit = op.c_target.0 as usize;
+                self.bits[bit] = self.and(&self.bits[bit].clone(), &condition.complement());
+            }
+            OperationType::BitStore1 => {
+                let bit = op.c_target.0 as usize;
+                self.bits[bit] = self
+                    .and(&self.bits[bit].complement(), &condition.complement())
+                    .complement();
+            }
+            // Phase gates do not alter basis support. Preserve them, resets,
+            // classical operations and annotations verbatim in the output.
+            OperationType::Z
+            | OperationType::CZ
+            | OperationType::CCZ
+            | OperationType::Neg
+            | OperationType::Register
+            | OperationType::AppendToRegister
+            | OperationType::DebugPrint => {}
+            OperationType::PushCondition | OperationType::PopCondition => unreachable!(),
+        }
+        Rewrite::Keep
+    }
+}
+
+/// Derive one pass of exact CCX support identities from this stream's ABI and
+/// operations. No saved operation indices, nonce assumptions or legacy passes.
+pub(crate) fn simplify(ops: Vec<Op>) -> Vec<Op> {
+    let mut state = Support::new(&ops);
+    let mut result = Vec::with_capacity(ops.len());
+    for op in ops {
+        state.step(&op).emit(op, &mut result);
+    }
+    result
+}
+
+
+/// Exact CCX-to-CX witnesses. No new measurement, reset, or phase gate.
+pub(crate) fn witnesses(ops:Vec<Op>)->Vec<Op>{
+    use std::collections::{HashMap,BTreeSet};
+    let mut state=Support::new(&ops);
+    let mut index:HashMap<Affine,BTreeSet<usize>>=HashMap::new();
+    for (q,v) in state.qubits.iter().enumerate(){index.entry(v.clone()).or_default().insert(q);}
+    let(mut self_n,mut witness_n,mut self_t,mut witness_t,mut depth)=(0,0,0.0,0.0,0i32);
+    let mut examples=Vec::new();
+    let mut out=Vec::with_capacity(ops.len());
+    for (at,op) in ops.iter().enumerate(){
+        let mut replacement=None;
+        if op.kind==OperationType::PushCondition{depth+=1;}
+        if op.kind==OperationType::PopCondition{depth-=1;}
+        if op.kind==OperationType::CCX{
+            let a=state.qubits[op.q_control1.0 as usize].clone();
+            let b=state.qubits[op.q_control2.0 as usize].clone();
+            let product=state.and(&a,&b);
+            let target=op.q_target.0 as usize;
+            if !product.is_zero() && !product.is_one(){
+                let weight=2f64.powi(-depth-i32::from(op.c_condition!=NO_BIT));
+                let self_hit=state.qubits[target]==product;
+                let witness=index.get(&product).and_then(|s|s.iter().copied().find(|&q|q!=target));
+                if self_hit{self_n+=1;self_t+=weight;}
+                if witness.is_some(){witness_n+=1;witness_t+=weight;replacement=witness;}
+                if examples.len()<64 && (self_hit||witness.is_some()){
+                    examples.push(format!("{{\"op\":{at},\"target\":{target},\"self_uncompute\":{self_hit},\"witness\":{}}}",witness.map_or("null".to_string(),|q|q.to_string())));
+                }
+            }
+        }
+        let changed:Vec<usize>=match op.kind{
+            OperationType::CCX|OperationType::CX|OperationType::X|OperationType::R|OperationType::Hmr=>vec![op.q_target.0 as usize],
+            OperationType::Swap=>vec![op.q_control1.0 as usize,op.q_target.0 as usize],_=>vec![]};
+        for &q in &changed{let key=state.qubits[q].clone();let set=index.get_mut(&key).unwrap();assert!(set.remove(&q));if set.is_empty(){index.remove(&key);}}
+        state.step(op);
+        for &q in &changed{index.entry(state.qubits[q].clone()).or_default().insert(q);}
+        if let Some(q)=replacement{
+            assert_ne!(q,op.q_target.0 as usize);
+            let mut r=Op::empty();r.kind=OperationType::CX;r.q_control1=QubitId(q as u64);r.q_target=op.q_target;r.c_condition=op.c_condition;
+            r.validate();out.push(r);
+        }else{out.push(*op);}
+    }
+    println!("I25_WITNESSES {{\"self_uncompute_native\":{self_n},\"self_uncompute_expected_T\":{self_t},\"witness_native\":{witness_n},\"witness_expected_T\":{witness_t},\"examples\":[{}]}}",examples.join(","));
+    out
+}
diff --git a/src/point_add/known_stream.rs b/src/point_add/known_stream.rs
new file mode 100644
index 0000000..d3f2f93
--- /dev/null
+++ b/src/point_add/known_stream.rs
@@ -0,0 +1,25 @@
+//! Restricted known-output addition with two streaming carry wires.
+use super::Builder;
+use crate::circuit::QubitId;
+pub(crate) fn add(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:Option<QubitId>,out:&[(bool,Vec<QubitId>)]){
+ let n=b.len();assert!(n>=1);assert_eq!(a.len(),n);assert_eq!(out.len(),n);
+ assert!(a.iter().all(|q|!b.contains(q)));
+ assert!(out.iter().all(|(_,qs)|qs.iter().all(|q|!b.contains(q))));
+ let mut outgoing=None;
+ for i in(0..n).rev(){
+  let incoming=if i==0{cin}else{
+   let p=c.alloc_qubit();c.cx(a[i],p);c.cx(b[i],p);if out[i].0{c.x(p);}for &q in &out[i].1{c.cx(q,p);}Some(p)
+  };
+  c.cx(a[i],b[i]);if let Some(p)=incoming{c.cx(p,b[i]);}
+  if let Some(q)=outgoing{
+   let m=c.alloc_bit();c.hmr(q,m);
+   // Carry out, written in terms of completed sum s, source a, carry p:
+   // a*s XOR a XOR a*p XOR s*p XOR p.
+   c.cz_if(a[i],b[i],m);c.z_if(a[i],m);
+   if let Some(p)=incoming{c.cz_if(a[i],p,m);c.cz_if(b[i],p,m);c.z_if(p,m);}
+   c.free_bit(m);c.free(q);
+  }
+  outgoing=if i>0{incoming}else{None};
+ }
+ assert!(outgoing.is_none());
+}
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f7e92ce..0d7e4a3 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -12,6 +12,7 @@ use pingpong::{divide, multiply};
 use square::sub_square;
 
 mod affine_simplify;
+mod interned_witness;
 mod quadratic_simplify;
 mod truth_simplify;
 mod builder;
@@ -36,12 +37,31 @@ const SECP256K1_P: U256 = U256::from_limbs([
 /// The submission emits the same circuit regardless of inherited environment.
 fn env_raw(name: &str) -> Option<String> {
     let value = match name {
+        "I76_SOURCE_TOP_LOAN" => "1",
+        "I74_RESULT_TOP_LOAN" => "1",
+        "SQ_LEND_RETAINED_CROSS3" => "0",
+        "I45_NARROW_ROUNDS" => "549,550,551,552,553,586,587,640,641,648,683,684,685,686",
+        "I50_SPLIT_BRIDGE" => "1",
+        "I35_CELLS" => "0",
+        "I35_TRACE" => "0",
+        "I35_BUDGET" => "0",
+        "PP_WALK_EXTRA_ROUNDS" => "683:4:1",
+        "SQ_ASM_TAIL" => "24",
+        "SQ_ROW1_INVERSE_CARRIES" => "1",
+        "SQ_ROW1_STREAM" => "1",
+        "SQ_ROW0_COPY" => "1",
+        "I41_ROUNDS" => "20,61,62,68,71,80,89,95,100,129,135,161,165,182,512,525,528,533,536,549,550,551,552,553,586,587,616,640,641,648,655,658,683,684,685,686,687",
+        "I33_DISABLE" => "0",
+        "I35_PROFILE" => "408:1:1,409:1:1,410:1:1,411:1:1,412:1:1,413:1:1,414:1:1,415:1:1,416:1:1,417:1:1,418:1:1,419:1:1,420:1:1,421:1:1,422:1:1,423:1:1,512:1:1,513:1:1,514:1:1,515:1:1,516:1:1,517:1:1,518:1:1,519:1:1,520:1:1,521:1:1,522:1:1,523:1:1,524:1:1,525:1:1,526:1:1,527:1:1,528:1:1,529:1:1,530:1:1,531:1:1,532:1:1,533:1:1,534:1:1,535:1:1,547:1:1,574:1:1,575:1:1,576:1:1,577:1:1,578:1:1,579:1:1,580:1:1,581:1:1,582:1:1,583:1:1,584:1:1,585:1:1,586:1:1,587:1:1,588:1:1,589:1:1,590:1:1,591:1:1,609:0:1,619:0:2,620:0:2,620:1:1,621:1:1,622:1:1,623:1:1,624:1:1,625:1:1,626:1:1,627:1:1,628:1:1,629:1:1,630:1:1,631:1:1,632:1:1,633:1:1,634:1:1,635:1:1,636:1:1,637:1:1,638:1:1,639:1:1,646:1:1",
+        "I12_DIV_PROFILE" => "192:192,193:193,194:194,195:195,196:196,197:197,198:198,199:199,200:200,201:201,202:202,203:203,204:204,205:205,206:206,207:207,208:208,209:209,210:210,211:211,212:212,213:213,214:214,215:215,216:216,217:217,218:218,219:219,220:220,221:221,222:222,223:223,224:224,225:225,226:226,227:227,228:228,229:229,230:230,231:231,232:232,233:233,234:234,235:235,236:236,237:237,238:238,239:239,240:240,241:241,242:242,243:243,244:244,245:245,246:246,247:247,248:248,249:249,250:392,393:393,394:394,395:395,396:396,397:397,398:398,399:399,400:400,401:401,402:402,403:403,404:404,405:405,406:406,407:407,408:408,409:409,410:410,411:411,412:412,413:413,414:414,415:415,416:416,417:417,418:418,419:419,420:420,421:421,422:422,423:423,424:424,425:425,426:426,427:427,428:428,429:429,430:430,431:431,432:432,433:496,497:497,498:498,499:499,500:500,501:501,502:502,503:503,504:504,505:505,506:506,507:507,508:508,509:509,510:510,511:511,512:512,513:513,514:514,515:515,516:516,517:517,518:518,519:519,520:520,521:522,523:523,524:524,525:525,526:526,527:527,528:528,529:529,530:530,531:531,532:532,533:533,534:534,535:535,536:536,537:537,538:538,539:539,540:540,541:572,573:573,574:574,575:575,576:576,577:577,578:578,579:579,580:580,581:581,582:582,583:583,584:584,585:585,586:586,587:587,588:588,589:596,597:597,598:598,599:599,600:600,601:601,602:602,603:604,605:606,607:608,609:609,610:611,612:613,614:615,616:616,617:618,619:620,621:621,622:622,623:623,624:624,625:625,626:626,627:627,628:628,629:629,630:630,631:631,632:632,633:633,634:634,635:635,636:636,637:637,638:638,639:639,640:640,641:641,642:642,643:643,644:644,645:645,646:646,647:647,648:648,649:664,665:666,667:668,669:670,671:671,672:672,673:673,674:674,675:675,676:676,677:677,678:678,679:679,680:680,681:681,682:682,683:683,684:684",
+        "I12_MUL_PROFILE" => "654:653,652:651,650:649,648:648,647:647,646:646,645:640,639:639,638:638,637:625,624:620,619:618,617:616,615:609,608:602,601:595,594:592,591:586,585:585,584:584,583:579,578:574,573:571,570:567,566:548,547:547,546:542,541:539,538:536,535:533,532:528,527:525,524:512,511:503,502:502,501:495,494:424,423:423,422:420,419:415,414:410,409:409,408:408,407:403",
+        "I12_B_GUARD" => "4",
         "CMP_SEED_ALL" => "1",
-        "ERASE_COMPARE" => "23",
-        "FOLD_GUARD" => "24",
+        "ERASE_COMPARE" => "24",
+        "FOLD_GUARD" => "25",
         "PP_CF_DEFER_WALK_PHASE" => "1",
         "PP_CF_END_CHUNK" => "8",
-        "PP_CHUNK_SHAPE" => "38:0,25:-2,0:-4",
+        "PP_CHUNK_SHAPE" => "64:0,38:1,25:-2,0:-4",
         "PP_CUT_SQIDENT" => "1",
         "PP_CUT_WALKLOAN" => "1",
         "PP_DEPTH_PROFILE" => "0:0",
@@ -50,7 +70,7 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_FLAG_SHAPE" => "38:0,25:-1,0:-3",
         "PP_FLAG_WIDEN_DIV" => "38",
         "PP_FOLD_PROFILE" => "38:0,32:-1,19:-4,0:-4",
-        "PP_FOLD_WIDEN" => "76",
+        "PP_FOLD_WIDEN" => "242",
         "PP_HEAD_DIV" => "192",
         "PP_HEAD_MUL" => "403",
         "PP_JOINT_GUARD" => "0",
@@ -71,16 +91,15 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_REPLAY_FOLD_WINDOW_MUL" => "54",
         "PP_REPLAY_SIGN_LOAN" => "1",
         "PP_REPLAY_SIGN_LOAN_MUL" => "1",
-        "PP_RETAIN_EXACT_DIV" => "0",
+        "PP_RETAIN_EXACT_DIV" => "1",
         "PP_RETAIN_EXACT_EXTRA_DIV" => "4",
         "PP_RETAIN_EXACT_EXTRA_MUL" => "4",
-        "PP_RETAIN_EXACT_MUL" => "0",
-        "PP_RETAIN_LATE_WIDEN" => "0",
+        "PP_RETAIN_EXACT_MUL" => "1",
+        "PP_RETAIN_LATE_WIDEN" => "3",
         "PP_RETAIN_REBALANCE" => "1",
         "PP_REUSE_DIV_PARITY" => "1",
         "PP_REUSE_MUL_SELECTORS" => "1",
         "PP_ROUNDS_MUL" => "698",
-        "PP_SEED_SHORT_MUL_F_COST" => "1",
         "PP_SIMPLIFY" => "product,affine,quadratic,truth",
         "PP_SOURCE_SIGN_GROW" => "1",
         "PP_SOURCE_SIGN_LOAN" => "0",
@@ -88,8 +107,8 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_SPLIT_FOLD_OVERAGE" => "0",
         "PP_SPLIT_OVERLAP_BITS" => "1",
         "PP_SPRINT_MIXED" => "0",
-        "PP_TAIL_DIV" => "684",
-        "PP_TAIL_MUL" => "645",
+        "PP_TAIL_DIV" => "682",
+        "PP_TAIL_MUL" => "655",
         "PP_WALK_GUARD_BITS" => "1",
         "PP_WALK_GUARD_MAX_WIDTH" => "64",
         "PP_WALK_MAX_QUBITS" => "1251",
@@ -103,16 +122,12 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_DEFER_CROSS_PHASE" => "1",
         "SQ_DIAG_PRELOAD" => "1",
         "SQ_FIT_CROSS" => "1",
-        "SQ_HIGH_CARRY_LOAN" => "1",
-        "SQ_HOLD_BOUNDARY" => "1",
         "SQ_LEND_ASSEMBLY_ZEROS" => "1",
         "SQ_LEND_RETAINED_ANDS" => "2",
         "SQ_LEND_RETAINED_CROSS2" => "2",
         "SQ_LEND_RETAINED_ZEROS" => "1",
         "SQ_ODD_NODE_TOPS" => "1",
-        "SQ_OWN_TOP_ZEROS" => "1",
         "SQ_ROW0_CARRY" => "1",
-        "SQ_ROW0_COPY" => "1",
         "SQ_ROW0_INVERSE_CARRIES" => "1",
         "SQ_ROW_ALL_MEASURE_TOP" => "1",
         "SQ_SPARSE_CORRECTION" => "0",
@@ -122,7 +137,12 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_CROSS" => "1",
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
-        "TAIL_NONCE" => "14939365091",
+        // Accepted public-validation nonce from the production grind.
+        "TAIL_NONCE" => "211106234700983",
+        "PP_SEED_SHORT_MUL_F_COST" => "1",
+        "SQ_HIGH_CARRY_LOAN" => "1",
+        "SQ_HOLD_BOUNDARY" => "1",
+        "SQ_OWN_TOP_ZEROS" => "1",
         _ => return None,
     };
     Some(value.to_owned())
@@ -226,7 +246,7 @@ fn build_point_add() -> Vec<Op> {
     circ.take_ops()
 }
 
-/// Emit the fixed I10 circuit and accepted public-validation nonce 9444541598.
+/// Emit the fixed I10 circuit and accepted public-validation nonce 9342055114.
 pub fn build() -> Vec<Op> {
     let mut ops = build_point_add();
     // Exact op-stream post-passes, ported from the 2026-09-04 warpspeed
@@ -256,6 +276,7 @@ pub fn build() -> Vec<Op> {
             );
         }
     }
+    ops = interned_witness::witnesses(ops);
     let nonce: u64 = required_env("TAIL_NONCE");
     let mut x = Op::empty();
     x.kind = OperationType::X;
@@ -264,3 +285,17 @@ pub fn build() -> Vec<Op> {
     ops = apply_tail_nonce(ops, nonce);
     ops
 }
+
+
+mod affine_constant;
+
+mod known_stream;
+mod round2_receiver;
+
+mod round2_fused;
+
+mod bridge;
+
+mod average;
+
+mod stream_wide;
diff --git a/src/point_add/modular.rs b/src/point_add/modular.rs
index 9351869..623f596 100644
--- a/src/point_add/modular.rs
+++ b/src/point_add/modular.rs
@@ -59,6 +59,14 @@ pub fn ripple_add(
     carry_in: Option<QubitId>,
     carry_out: Option<QubitId>,
 ) {
+    if carry_out.is_none() && result_top_loan_enabled(acc) {ripple_add_result_top_loan(circ,addend,acc,carry_in,None,false);return;}
+    let owned=if carry_out.is_some(){acc.len().saturating_sub(1)}else{acc.len().saturating_sub(2)};
+    let missing=(circ.active_qubits()as usize+owned).saturating_sub(walk_max_qubits());
+    if addend.len()==acc.len() && acc.len()>=3 && !has_top_copy(acc)
+        && missing>0 && missing<=super::bridge::budget() && missing<owned {
+        if super::env_flag("I35_TRACE"){eprintln!("I35_BRIDGE plain {} {}",acc.len(),missing);}
+        super::bridge::add(circ,addend,acc,carry_in,carry_out,missing);return;
+    }
     ripple_add_proved(circ, addend, acc, carry_in, carry_out, Carry0::Full, Carry1::Full, None, None, None, None);
 }
 
@@ -75,6 +83,11 @@ pub(crate) fn ripple_add_consume(
     consumer: impl FnOnce(&mut Builder, QubitId, QubitId, QubitId, Option<QubitId>),
 ) {
     let n=acc.len(); assert!(n>=1); assert_eq!(addend.len(),n);
+    let missing=(circ.active_qubits()as usize+n-1).saturating_sub(walk_max_qubits());
+    if n>=3 && missing>0 && missing<=super::bridge::budget() && missing<n-1 {
+        if super::env_flag("I35_TRACE"){eprintln!("I35_BRIDGE consume {} {}",n,missing);}
+        super::bridge::run(circ,addend,acc,carry_in,Some(carry_out),missing,|c,o,a,s,p|consumer(c,o.unwrap(),a,s,p));return;
+    }
     let carries=circ.alloc_qubits(n-1);
     let previous=|i:usize|if i==0 {carry_in} else {Some(carries[i-1])};
     for i in 0..n {
@@ -114,6 +127,7 @@ pub fn ripple_add_with_deferred_phase(
     carry_out: Option<QubitId>,
     deferred: Option<(usize, BitId)>,
 ) {
+    if carry_out.is_none() && deferred.is_none() && result_top_loan_enabled(acc) {ripple_add_result_top_loan(circ,addend,acc,carry_in,None,false);return;}
     ripple_add_proved(
         circ, addend, acc, carry_in, carry_out, Carry0::Full, Carry1::Full, deferred, None, None, None,
     );
@@ -316,6 +330,7 @@ fn terminal_step(
     acc: &[QubitId],
     previous: Option<QubitId>,
 ) {
+    if has_top_copy(acc){terminal_top_copy(circ,addend,acc,previous);return;}
     let n = acc.len();
     let k = addend.len();
     let i = n - 2;
@@ -426,6 +441,7 @@ pub fn ripple_add_lent_with_deferred_phase(
 ) {
     let width = addend.len();
     assert_eq!(width, acc.len(), "ripple_add_lent: width mismatch");
+    if deferred.is_none() && result_top_loan_enabled(acc) {ripple_add_result_top_loan(circ,addend,acc,carry_in,Some(lent),false);return;}
     if width < 3 {
         ripple_add_with_deferred_phase(circ, addend, acc, carry_in, None, deferred);
         return;
@@ -497,6 +513,9 @@ pub(crate) fn ripple_add_source_sign_loan(
 ) {
     let n=addend.len();assert_eq!(n,acc.len());
     assert!(n>=3+usize::from(lent.is_some()));
+    if deferred.is_none() && result_top_loan_enabled(acc) && n>=4+usize::from(lent.is_some()) && super::env_flag("I76_SOURCE_TOP_LOAN") {
+        ripple_add_result_top_loan(circ,addend,acc,carry_in,lent,true);return;
+    }
     let owned=n-3-usize::from(lent.is_some());
     let high=addend[n-1];let copy=addend[n-2];
     assert!(!acc.contains(&high));
@@ -510,8 +529,14 @@ pub(crate) fn ripple_add_source_sign_loan(
     // original penultimate source before adding the identical top source bit.
     let i=n-2;
     circ.cx(high,copy);circ.cx(high,acc[i]);
-    circ.ccx(copy,acc[i],acc[n-1]);circ.cx(high,acc[n-1]);
-    circ.cx(high,copy);circ.cx(copy,acc[n-1]);circ.cx(copy,acc[i]);
+    if has_top_copy(acc){
+      let m=circ.alloc_bit();circ.hmr(acc[n-1],m);
+      circ.cz_if(copy,acc[i],m);circ.z_if(high,m);circ.z_if(acc[i],m);circ.free_bit(m);
+      circ.cx(high,copy);circ.cx(copy,acc[i]);circ.cx(acc[i],acc[n-1]);
+    }else{
+      circ.ccx(copy,acc[i],acc[n-1]);circ.cx(high,acc[n-1]);
+      circ.cx(high,copy);circ.cx(copy,acc[n-1]);circ.cx(copy,acc[i]);
+    }
     for i in (0..carries.len()).rev(){
         if deferred.as_ref().is_some_and(|(at,_)|*at==i){
             let(_,m)=deferred.take().unwrap();circ.z_if(carries[i],m);circ.free_bit(m);
@@ -699,3 +724,21 @@ pub fn addsub_wide_low(circ: &mut Builder, value: &[QubitId], acc: &[QubitId], i
     assert!(value.len() <= acc.len());
     addsub_full_low(circ, value, acc, inverse, c0, c1);
 }
+
+
+// Research: known final top is a copy of its neighboring output bit.
+thread_local! {static TOP_COPY:std::cell::Cell<Option<(QubitId,QubitId)>>=const{std::cell::Cell::new(None)};}
+pub(crate) fn with_top_copy(c:&mut Builder,acc:&[QubitId],enabled:bool,body:impl FnOnce(&mut Builder)){
+ let pair=enabled.then(||(acc[acc.len()-1],acc[acc.len()-2]));
+ TOP_COPY.with(|v|{assert!(v.replace(pair).is_none());});body(c);TOP_COPY.with(|v|v.set(None));
+}
+fn has_top_copy(acc:&[QubitId])->bool{acc.len()>=2 && TOP_COPY.with(|v|v.get()==Some((acc[acc.len()-1],acc[acc.len()-2])))}
+fn terminal_top_copy(c:&mut Builder,a:&[QubitId],b:&[QubitId],previous:Option<QubitId>){
+ let n=b.len();let i=n-2;assert_eq!(a.len(),n);
+ if let Some(p)=previous{c.cx(p,a[i]);c.cx(p,b[i]);}
+ let m=c.alloc_bit();c.hmr(b[n-1],m);
+ c.z_if(a[n-1],m);c.cz_if(a[i],b[i],m);c.z_if(a[i],m);c.z_if(b[i],m);c.free_bit(m);
+ if let Some(p)=previous{c.cx(p,a[i]);}c.cx(a[i],b[i]);c.cx(b[i],b[n-1]);
+}
+
+include!("top_result_loan.rs");
diff --git a/src/point_add/pingpong.rs b/src/point_add/pingpong.rs
index 5f37645..7cb9f1c 100644
--- a/src/point_add/pingpong.rs
+++ b/src/point_add/pingpong.rs
@@ -390,8 +390,14 @@ fn divide_traversal(
     }
     let mut next = plan.r1;
     while next<=plan.r2 {
-        let end=(next..=next.saturating_add(batch_span).min(plan.r2))
+        let mut end=(next..=next.saturating_add(batch_span).min(plan.r2))
             .min_by_key(|&r|(r+1+2*value_width((r+1).min(plan.rounds-1)),r)).unwrap();
+        if let Some(profile)=env_raw("I12_DIV_PROFILE") {
+            end=next;
+            for item in profile.split(',') {let(a,b)=item.split_once(':').unwrap();let a=a.parse::<usize>().unwrap();let b=b.parse::<usize>().unwrap();if a<=next&&next<=b {end=b.min(plan.r2);break;}}
+        }
+        if env_flag("I12_BATCH_TRACE") {eprintln!("I12_DIV_BATCH {} {}",next,end);}
+
         for r in next..=end {
             let (sign, depth, phase) = walk_round_phase(circ, u, v, r, defer_walk_phase());
             tape.push(sign);
@@ -524,6 +530,11 @@ fn multiply_traversal(
         for r in (lo..hi).rev() {
             if footprint(r)<footprint(hi) {lo=r+1;break;}
         }
+        if let Some(profile)=env_raw("I12_MUL_PROFILE") {
+            lo=hi;
+            for item in profile.split(',') {let(a,b)=item.split_once(':').unwrap();let a=a.parse::<usize>().unwrap();let b=b.parse::<usize>().unwrap();if b<=hi&&hi<=a {lo=b.max(plan.r1);break;}}
+        }
+        if env_flag("I12_BATCH_TRACE") {eprintln!("I12_MUL_BATCH {} {}",hi,lo);}
         for r in(lo..=hi).rev() {
             if c2fix[r].is_some() {
                 let s=c2_term_sign(circ,u,v);
@@ -755,14 +766,31 @@ fn parse_width_schedule(spec: &str) -> Vec<usize> {
     out
 }
 
-fn value_width(round: usize) -> usize {
+fn parent_value_width(round: usize) -> usize {
     let width=width_schedule()[round];
     let extra=super::optional_env::<usize>("PP_WALK_GUARD_BITS").unwrap_or(0);
     assert!(extra<=4,"bounded walk guard experiment");
     let threshold=super::optional_env::<usize>("PP_WALK_GUARD_MAX_WIDTH").unwrap_or(VALUE_WIDTH-1).min(VALUE_WIDTH-1);
     // Saturating at threshold+1 prevents an upward jump when a decreasing
     // schedule first enters the guarded band. Never exceed the initial rails.
-    if width<=threshold{(width+extra).min(threshold+1)}else{width}
+    let base=if width<=threshold{(width+extra).min(threshold+1)}else{width};
+    (base as isize+walk_extra(round)) as usize
+}
+
+// I45's independently checked compatibility rule: the corrected-round
+// set and one-bit narrower-round set are separate, explicit public schedules.
+fn i45_narrow(round:usize)->bool {
+    static SET:std::sync::OnceLock<std::collections::BTreeSet<usize>>=std::sync::OnceLock::new();
+    SET.get_or_init(||env_raw("I45_NARROW_ROUNDS").unwrap_or_default().split(',').filter(|s|!s.is_empty()).map(|s|s.parse().unwrap()).collect()).contains(&round)
+}
+
+fn value_width(round:usize)->usize {
+    let w=parent_value_width(round);
+    if i45_narrow(round) {
+        assert!(i41_corrected(round));
+        assert!(round>=5 && w==parent_value_width(round-1) && w==parent_value_width(round-2));
+        w-1
+    } else {w}
 }
 
 // A precision experiment must not silently change the replay's fold/compare
@@ -1587,6 +1615,22 @@ fn defer_walk_phase() -> bool {
     env_flag("PP_CF_DEFER_WALK_PHASE")
 }
 
+fn i41_corrected(round:usize)->bool {
+    static SET:std::sync::OnceLock<std::collections::BTreeSet<usize>>=std::sync::OnceLock::new();
+    SET.get_or_init(|| {
+        let mut set=std::collections::BTreeSet::new();
+        if let Some(text)=env_raw("I41_ROUNDS") {for v in text.split(',').filter(|s|!s.is_empty()) {
+            let r:usize=v.parse().unwrap();assert!(r>=3);assert!(set.insert(r));
+        }}set
+    }).contains(&round)
+}
+
+fn i41_bridges(c:&Builder,m:usize)->usize {
+    let room=walk_max_qubits().saturating_sub(c.active_qubits() as usize);
+    let bridges=m.saturating_sub(2+room);
+    assert!(bridges<m-2,"signed average needs one owned carry wire");bridges
+}
+
 fn walk_round_phase(
     circ: &mut Builder,
     u: &mut Vec<QubitId>,
@@ -1643,10 +1687,17 @@ fn walk_round_phase(
     } else {
         WalkRule::Quarter
     };
+    if i41_corrected(round) {
+        assert!(!quarter && guard.is_none());
+        let b=i41_bridges(circ,m);
+        if env_flag("I41_TRACE"){eprintln!("I41_AVG F {} {} {} {}",round,m,b,circ.active_qubits());}
+        super::average::forward(circ,source,target,sign,b);
+        return (sign,Vec::new(),None);
+    }
     // Previous forward target is now the source. Its halving explicitly copied
     // its sign bit; retain that promise only if this round did not shrink it.
     let source_sign_loan=env_flag("PP_SOURCE_SIGN_LOAN") && !quarter && round>=3
-        && m>=6 && width==value_width(round-1);
+        && !i41_corrected(round-1) && m>=6 && width==value_width(round-1);
     let phase = walk_add(circ, sign, source, target, true, rule, defer_boundary, None, source_sign_loan);
     let depth = if quarter {
         // C4-W: the register holds W = S/2, whose valuation is the halving depth
@@ -1754,6 +1805,14 @@ fn walk_back_round_phase(
         }
         None => sign,
     };
+    if i41_corrected(round) {
+        assert!(depth.is_empty() && deferred.is_none());
+        let room=walk_max_qubits().saturating_sub(circ.active_qubits()as usize);
+        let b=m.saturating_sub(3+room);
+        if env_flag("I41_TRACE"){eprintln!("I41_AVG B {} {} {} {}",round,m,b,circ.active_qubits());}
+        super::average::reverse(circ,source,target,sign,b);
+        circ.cx(target[0],sign);circ.cx(source[0],sign);circ.free(sign);return;
+    }
     // C4-W: a round is a quarter round exactly when it carries a record; the
     // guard wire is recomputed off that record (0 <=> the guard fired).
     let quarter = !depth.is_empty();
@@ -1786,7 +1845,28 @@ fn walk_back_round_phase(
     // grow_to has just created the source's top sign copy. This is a fresh
     // structural promise even on a path already affected by truncation.
     let source_sign_loan=env_flag("PP_SOURCE_SIGN_GROW") && source_grew && !quarter && m>=6;
-    let generated = walk_add(circ, sign, source, target, false, rule, false, deferred, source_sign_loan);
+    // The known-output top-copy receiver is fixed enabled in this submission.
+    let known_top=true
+        && !quarter && m>=6 && (round==3 || (round>=4 && !i41_corrected(round-2) && width==value_width(round-2)));
+    // I72: round1's disjoint high increment maps 000->001 or 111->000.
+    // Its top two output bits are zero, even with the original low truncation.
+    // Reverse round3 restores that output; complementing by sign preserves
+    // their equality. This uses the unchanged native-tested top-copy receiver.
+    if round==3 && known_top {assert!(m==N+1 && round1_window(m)<=N-2);}
+    let mut generated=None;
+    if round==2 && !quarter && deferred.is_none() && !super::env_flag("I32_DISABLE") {
+        if !super::env_flag("I33_DISABLE") {
+            assert!(!half_f_minus_one().bit(1)); // source[0] used by sign cleanup stays unchanged
+            super::round2_fused::receive(circ,source,target,sign,round1_window(m),half_f_minus_one()>>1,N-2);
+            super::round2_fused::mark();
+        } else {
+            super::round2_receiver::receive(circ,source,target,sign,round1_window(m),half_f_minus_one()>>1,N-2);
+        }
+    } else {
+        super::modular::with_top_copy(circ,target,known_top,|circ|{
+          generated=walk_add(circ,sign,source,target,false,rule,false,deferred,source_sign_loan);
+        });
+    }
     assert!(generated.is_none());
     circ.x(sign);
     if let Some(w) = guard {
@@ -1860,7 +1940,8 @@ fn walk_add(
 ) -> Option<DeferredWalkPhase> {
     assert!(!(defer_boundary && deferred.is_some()));
     let loan = cut_walkloan();
-    let split=walk_low_chunk(circ, source.len(), loan, source_sign_loan);
+    let result_loan=deferred.is_none() && (!source_sign_loan || env_flag("I76_SOURCE_TOP_LOAN")) && super::modular::result_top_loan_enabled(target);
+    let split=walk_low_chunk(circ, source.len(), loan, source_sign_loan,result_loan);
     if source_sign_loan && env_flag("PP_SOURCE_SIGN_LOAN_TRACE") {
         eprintln!("SOURCE_SIGN_LOAN {} {} {}",source.len(),circ.active_qubits(),split.unwrap_or(0));
     }
@@ -2034,7 +2115,7 @@ fn walk_add_single(
         let room = walk_max_qubits().saturating_sub(circ.active_qubits() as usize);
         if source_sign_loan {
             super::modular::ripple_add_source_sign_loan(circ,&source[2..],&target[2..],Some(carry2),Some(target[0]),deferred);
-        } else if env_flag("PP_Q1208_HELPERS") && source.len().saturating_sub(5) > room {
+        } else if env_flag("PP_Q1208_HELPERS") && source.len().saturating_sub(5+usize::from(deferred.is_none() && super::modular::result_top_loan_enabled(target))) > room {
             assert!(deferred.is_none(), "compact inverse ripple has no deferred-phase hook");
             let width=source.len()-2;
             super::compact_chunk_add::add(circ,&source[2..],&target[2..],Some(carry2),false,exact_walk_chunk_width(width,room));
@@ -2137,15 +2218,15 @@ fn walk_c2_term_drop(circ: &mut Builder, rule: WalkRule, source0: QubitId, g: Op
 /// narrower. The borrow needs a real ladder to lend into: below
 /// `MIN_WALK_WIDTH` the high ripple has no carry position to spare and the
 /// arithmetic is the pre-loan one.
-fn walk_low_chunk(circ: &Builder, m: usize, loan: bool, source_sign_loan: bool) -> Option<usize> {
+fn walk_low_chunk(circ: &Builder, m: usize, loan: bool, source_sign_loan: bool, result_loan:bool) -> Option<usize> {
     // `low` is a bit position, so it counts against the full value width.
     let n = m + 1;
     let low = (circ.active_qubits() as usize + m).saturating_sub(walk_max_qubits());
-    let single_fits_below = (if loan && m >= MIN_WALK_WIDTH { 5 } else { 4 })+usize::from(source_sign_loan);
+    let single_fits_below = (if loan && m >= MIN_WALK_WIDTH { 5 } else { 4 })+usize::from(source_sign_loan)+usize::from(result_loan);
     if n < 12 || low < single_fits_below {
         return None;
     }
-    let low = low-usize::from(loan)-usize::from(source_sign_loan);
+    let low = low-usize::from(loan)-usize::from(source_sign_loan)-usize::from(result_loan);
     (low + 2 <= n && low * 2 <= n).then_some(low)
 }
 
@@ -2565,8 +2646,19 @@ fn round1_forward(circ: &mut Builder, u: &[QubitId], v: &[QubitId]) -> QubitId {
 fn round1_reverse(circ: &mut Builder, u: &[QubitId], v: &[QubitId], sign: QubitId) {
     let m = u.len();
     assert_eq!(m, v.len());
-    sub_const(circ, &u[N - 2..], U256::from(1));
-    add_const(circ, &u[..round1_window(m)], half_f_minus_one() >> 1);
+    if super::round2_fused::take() {
+        // Round2 has already executed these exact inverse constants and left
+        // this source at X. Continue with the original affine round1 cleanup.
+    } else if !super::env_flag("I31_DISABLE") {
+        // After these two disjoint inverse constant operations, u is the
+        // arithmetic half of v XOR sign, before the existing affine cleanup.
+        let desired:Vec<_>=(0..m).map(|j|(false,vec![v[(j+1).min(m-1)],sign])).collect();
+        super::affine_constant::add_known(circ,&u[N-2..],U256::MAX,&desired[N-2..]);
+        super::affine_constant::add_known(circ,&u[..round1_window(m)],half_f_minus_one()>>1,&desired[..round1_window(m)]);
+    } else {
+        sub_const(circ, &u[N - 2..], U256::from(1));
+        add_const(circ, &u[..round1_window(m)], half_f_minus_one() >> 1);
+    }
     circ.cx_all(sign, u);
     circ.cx(v[m - 1], u[m - 1]);
     for j in (0..m - 1).rev() {
@@ -2836,6 +2928,19 @@ fn replay_add_halve(
     target: &[QubitId],
     fold_window: usize,
     round: usize,
+) {
+    let _scope=super::bridge::enter(round,false);
+    let before=circ.i35_cost();
+    replay_add_halve_impl(circ,sign,source,target,fold_window,round);
+    if env_flag("I35_CELLS"){eprintln!("I35_CELL {} {} {} {}",round,0,super::bridge::budget(),circ.i35_cost()-before);}
+}
+fn replay_add_halve_impl(
+    circ: &mut Builder,
+    sign: QubitId,
+    source: &[QubitId],
+    target: &[QubitId],
+    fold_window: usize,
+    round: usize,
 ) {
     if retained_prebias::try_replay(circ,sign,source,target,retained_window(fold_window,round),round) {return;}
     if env_flag("PP_JOINT_PREBIAS_DIV") && joint_prebias::eligible(circ,round) {
@@ -2932,6 +3037,19 @@ fn replay_double_add(
     target: &[QubitId],
     fold_window: usize,
     round: usize,
+) {
+    let _scope=super::bridge::enter(round,true);
+    let before=circ.i35_cost();
+    replay_double_add_impl(circ,sign,source,target,fold_window,round);
+    if env_flag("I35_CELLS"){eprintln!("I35_CELL {} {} {} {}",round,1,super::bridge::budget(),circ.i35_cost()-before);}
+}
+fn replay_double_add_impl(
+    circ: &mut Builder,
+    sign: QubitId,
+    source: &[QubitId],
+    target: &[QubitId],
+    fold_window: usize,
+    round: usize,
 ) {
     let f = f();
 
@@ -3173,7 +3291,7 @@ fn with_sign_copy_loans(circ:&mut Builder,loans:&[(QubitId,QubitId)],body:impl F
 fn forward_sign_copy_valid(w:usize,last:usize)->[bool;2] {
     if last<3{return[false,false];}
     let target=if last.is_multiple_of(2){1}else{0};let mut valid=[false,false];
-    valid[target]=w==value_width(last);valid[1-target]=w==value_width(last-1);valid
+    valid[target]=!i41_corrected(last) && w==value_width(last);valid[1-target]=!i41_corrected(last-1) && w==value_width(last-1);valid
 }
 fn with_forward_replay_sign_loans(circ:&mut Builder,u:&[QubitId],v:&[QubitId],last:usize,body:impl FnOnce(&mut Builder)) {
     if !env_flag("PP_REPLAY_SIGN_LOAN") || mod4_sign() || last<3 {body(circ);return;}
@@ -3468,7 +3586,7 @@ fn composition_bounds(c:&Builder,round:usize,multiply:bool)->Option<Vec<(usize,u
     if env_raw("PP_PIN_REPLAY_LAYOUT").is_some(){return None;}
     let room=walk_max_qubits().saturating_sub(c.active_qubits()as usize);
     let loans=REPLAY_SIGN_LOANS.with(|s|s.get());let old=room.saturating_sub(loans);
-    let layout=chunk_layout(N,old);
+    let layout=chunk_layout(N,old+super::bridge::budget());
     let fallback=layout.is_none() || old<replay_chunk_compare()+2;
     if env_flag("PP_NEW_REPLAY") {
         let extra=if fallback{2*N}else{layout.as_ref().unwrap()[..layout.as_ref().unwrap().len()-1]
@@ -3483,7 +3601,7 @@ fn composition_bounds(c:&Builder,round:usize,multiply:bool)->Option<Vec<(usize,u
     }
     if env_flag("PP_Q1208_HELPERS")&&fallback{return None;}
     let layout=layout?;
-    Some(loaned_chunk_bounds(&layout,room,loans,round,multiply))
+    Some(loaned_chunk_bounds(&layout,room+super::bridge::budget(),loans,round,multiply))
 }
 
 // Reserve final-frame room by filling spare earlier chunk capacity.
@@ -3492,7 +3610,7 @@ fn composition_bounds(c:&Builder,round:usize,multiply:bool)->Option<Vec<(usize,u
 // is an explicit phase-predicate change, requiring full-stream qualification.
 fn retained_rebalance(c:&Builder, old:&[(usize,usize)], round:usize, multiply:bool)->Vec<(usize,usize)> {
     if !env_flag("PP_RETAIN_REBALANCE") || old.len()<2 {return old.to_vec();}
-    let room=walk_max_qubits().saturating_sub(c.active_qubits()as usize);
+    let room=(walk_max_qubits()+super::bridge::budget()).saturating_sub(c.active_qubits()as usize);
     let mut sizes:Vec<_>=old.iter().map(|&(lo,hi)|hi-lo).collect();
     let last=sizes.len()-1;
     for j in 0..last {
@@ -3514,7 +3632,7 @@ fn chunked_add(circ: &mut Builder, addend: &[QubitId], acc: &[QubitId], round: u
     let loans=REPLAY_SIGN_LOANS.with(|s|s.get());
     let old_ladder=ladder.saturating_sub(loans);
     let pinned=pinned_replay_bounds(addend.len(),round,multiply);
-    let layout = pinned.clone().or_else(||chunk_layout(addend.len(), old_ladder));
+    let layout = pinned.clone().or_else(||chunk_layout(addend.len(), old_ladder+super::bridge::budget()));
     if pinned.is_none() && env_flag("PP_NEW_REPLAY") {
         let old_fallback=layout.is_none() || old_ladder<replay_chunk_compare()+2;
         let old_extra2=if old_fallback {2*addend.len()} else {
@@ -3540,7 +3658,7 @@ fn chunked_add(circ: &mut Builder, addend: &[QubitId], acc: &[QubitId], round: u
     let bounds = layout.unwrap_or_else(|| panic!("layout r={} mul={} live={} cap={} room={}", round, multiply, circ.active_qubits(), walk_max_qubits(), ladder));
     let adjusted=if pinned.is_some(){
         if env_flag("PP_PIN_REPLAY_RELAX_EXACT") {loaned_chunk_bounds(&bounds,ladder,addend.len(),round,multiply)}else{bounds.clone()}
-    }else{loaned_chunk_bounds(&bounds,ladder,loans,round,multiply)};
+    }else{loaned_chunk_bounds(&bounds,ladder+super::bridge::budget(),loans,round,multiply)};
     if loans>0 && env_flag("PP_REPLAY_SIGN_TRACE") {
         eprintln!("REPLAY_LOAN_LAYOUT {} {} {} {} {:?} {:?}",round,multiply as u8,old_ladder,ladder,bounds,adjusted);
     }
@@ -4101,3 +4219,20 @@ pub(crate) fn endpoint_sparse_sub(circ: &mut Builder, control: QubitId, value: &
 #[path="joint_lowfold.rs"] mod joint_lowfold;
 #[path="joint_prebias.rs"] mod joint_prebias;
 #[path="retained_prebias.rs"] mod retained_prebias;
+
+/// Per-round physical walk-width edits, `start:len:delta,...`
+/// (PP_WALK_EXTRA_ROUNDS). Physical rails only, like the guard bits; the
+/// policy width that shapes folds and compares is unchanged.
+fn walk_extra(round: usize) -> isize {
+    static SLOT: std::sync::OnceLock<Vec<(usize,usize,isize)>> = std::sync::OnceLock::new();
+    let edits=SLOT.get_or_init(|| {
+        let spec=super::optional_env::<String>("PP_WALK_EXTRA_ROUNDS").unwrap_or_default();
+        spec.split(',').map(str::trim).filter(|s| !s.is_empty()).map(|s| {
+            let f: Vec<&str>=s.split(':').collect();
+            assert!(f.len()==3,"PP_WALK_EXTRA_ROUNDS: {s:?} is not start:len:delta");
+            (f[0].parse().unwrap(),f[1].parse().unwrap(),f[2].parse().unwrap())
+        }).collect()
+    });
+    edits.iter().filter(|e| round>=e.0 && round<e.0+e.1).map(|e| e.2).sum()
+}
+
diff --git a/src/point_add/retained_prebias.rs b/src/point_add/retained_prebias.rs
index c674b17..ae3cb80 100644
--- a/src/point_add/retained_prebias.rs
+++ b/src/point_add/retained_prebias.rs
@@ -72,10 +72,14 @@ pub(super)fn try_replay(c:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId],fw
   }else{ripple_add(c,&a[at..hi],&b[at..hi],cin,Some(out));}
   if j==0{joint_prebias::erase_initial(c,initial,a[0],sign,b[0]);}
   if let Some((carry,plo,phi))=previous{
-   let(k,seed)=boundary_repair_spec(r,false,plo,phi);c.record_replay_site('B',r,phi,k);
+   let(k,seed)=boundary_repair_spec(r,false,plo,phi);
    let full=plo==0&&phi==k;
+   let guard=super::super::optional_env::<usize>("I12_B_GUARD").unwrap_or(0);
+   let protected=(589..=620).contains(&r)||(642..=645).contains(&r)||(647..=648).contains(&r);
+   let width=if protected&&!full {(k+guard).min(phi-plo)}else{k};
+   c.record_replay_site('B',r,phi,width);
    if full{c.cx(b[0],sign);}
-   erase_with_compare(c,carry,&b[phi-k..phi],&a[phi-k..phi],if full{Some(sign)}else{seed.then(||a[phi-k-1])});c.free(carry);
+   erase_with_compare(c,carry,&b[phi-width..phi],&a[phi-width..phi],if full{Some(sign)}else{seed.then(||a[phi-k-1])});c.free(carry);
    if full{c.cx(b[0],sign);}
   }
   cin=Some(out);previous=Some((out,lo,hi));
diff --git a/src/point_add/round2_fused.rs b/src/point_add/round2_fused.rs
new file mode 100644
index 0000000..f630124
--- /dev/null
+++ b/src/point_add/round2_fused.rs
@@ -0,0 +1,30 @@
+//! Keep the round1 source in its normalized frame after reversing round2.
+//! Round1 then performs only its existing affine cleanup and phase handling.
+use super::{Builder,const_arith::{add_const,sub_const},known_stream,affine_constant};
+use alloy_primitives::U256;
+use crate::circuit::QubitId;
+thread_local!{static NORMALIZED:std::cell::Cell<bool>=const{std::cell::Cell::new(false)};}
+pub(crate) fn mark(){NORMALIZED.with(|x|assert!(!x.replace(true)));}
+pub(crate) fn take()->bool{NORMALIZED.with(|x|x.replace(false))}
+pub(crate) fn receive(c:&mut Builder,u:&[QubitId],v:&[QubitId],r:QubitId,k:usize,h:U256,top:usize){
+ let n=u.len();assert_eq!(n,v.len());assert!(2<=k&&k<=top&&top+2<=n);
+ let first=(0..k).find(|&i|h.bit(i)).unwrap_or(k);let low=k-first;
+ let indices:Vec<_>=(first..k).chain(top..n).collect();let buf=c.alloc_qubits(indices.len());
+ let mut old_source=u.to_vec();
+ for(&i,&q)in indices.iter().zip(&buf){c.cx(u[i],q);old_source[i]=q;}
+ // A single paid inverse transform. U intentionally stays at X afterward.
+ sub_const(c,&u[top..],U256::from(1));add_const(c,&u[..k],h);
+ let mut out=Vec::with_capacity(n);out.push((true,vec![old_source[0]]));
+ for j in 1..n{out.push((false,vec![u[j-1],old_source[0]]));}
+ c.cx_all(r,v);known_stream::add(c,&old_source,v,Some(r),&out);
+ // The old low/high source copies have a structurally known result X:
+ // apply the restricted zero-Toffoli receiver and erase them by XOR copies.
+ if low>0{
+  let desired:Vec<_>=u[first..k].iter().map(|&q|(false,vec![q])).collect();
+  affine_constant::add_known(c,&buf[..low],h>>first,&desired);
+ }
+ let desired:Vec<_>=u[top..].iter().map(|&q|(false,vec![q])).collect();
+ affine_constant::add_known(c,&buf[low..],U256::MAX,&desired);
+ for(&i,&q)in indices.iter().zip(&buf){c.cx(u[i],q);c.free(q);}
+ c.cx_all(r,v);
+}
diff --git a/src/point_add/round2_receiver.rs b/src/point_add/round2_receiver.rs
new file mode 100644
index 0000000..14e07b9
--- /dev/null
+++ b/src/point_add/round2_receiver.rs
@@ -0,0 +1,29 @@
+use super::{Builder,const_arith::{add_const,sub_const},known_stream};
+use alloy_primitives::U256;
+use crate::circuit::QubitId;
+
+/// At inverse round2, sign is already inverted: R=1 XOR s2. The target is
+/// the restored pre-halving odd sum D. The source U is unchanged round1.
+/// Requires the finite round1 relation; no extra long-lived sign record.
+pub(crate) fn receive(c:&mut Builder,u:&[QubitId],v:&[QubitId],r:QubitId,k:usize,h:U256,top:usize){
+ let n=u.len();assert_eq!(n,v.len());assert!(2<=k && k<=top && top+2<=n);
+ let first=(0..k).find(|&i|h.bit(i)).unwrap_or(k);
+ let indices:Vec<_>=(0..n-1).filter(|&i|(first..k).contains(&i)||i>=top).collect();
+ let buf=c.alloc_qubits(indices.len());
+ // Compute only the non-affine portion of X, copy it, then restore U.
+ // Every constant operation, its scratch and the retained copies are paid.
+ sub_const(c,&u[top..],U256::from(1));add_const(c,&u[..k],h);
+ for(&i,&q)in indices.iter().zip(&buf){c.cx(u[i],q);}
+ sub_const(c,&u[..k],h);add_const(c,&u[top..],U256::from(1));
+ let mut out=Vec::with_capacity(n);out.push((true,vec![u[0]]));
+ for j in 1..n{
+  let i=j-1;let x=indices.iter().position(|&at|at==i).map_or(u[i],|at|buf[at]);
+  out.push((false,vec![x,u[0]]));
+ }
+ // s1=R XOR U0, so the inner sum V XOR R has no separate sign wire:
+ // desired=(2X) XOR signmask(U0) XOR1.
+ c.cx_all(r,v);known_stream::add(c,u,v,Some(r),&out);
+ // The newly restored target supplies every retained X bit for free cleanup.
+ for(&i,&q)in indices.iter().zip(&buf){c.cx(v[i+1],q);c.cx(u[0],q);c.free(q);}
+ c.cx_all(r,v);
+}
diff --git a/src/point_add/square.rs b/src/point_add/square.rs
index dd814d2..a72daa2 100644
--- a/src/point_add/square.rs
+++ b/src/point_add/square.rs
@@ -114,7 +114,11 @@ fn row_addsub_cin(circ:&mut Builder, xi:QubitId, operand:&[QubitId], acc:&[Qubit
     // Inverse rows restore a state that never reached bit i+m (see
     // SQ_ROW_ALL_MEASURE_TOP); in the subtraction frame that top reads 1.
     let top=(known_output.is_none() && inverse && super::env_flag("SQ_ROW_ALL_MEASURE_TOP")).then_some(true);
+    if let Some(out)=known_output.filter(|_|super::env_flag("SQ_ROW1_STREAM")) {
+        super::stream_wide::add(circ,operand,acc,Some(xi),out);
+    } else {
     super::modular::ripple_add_proved(circ,operand,acc,Some(xi),None,c0,Carry1::Full,None,known_output,top,borrowed);
+    }
     if inverse { circ.x_all(acc); }
     circ.x_all(&acc[..k]); circ.cx_all(xi,&acc[..k]);
     if !inverse { circ.x(acc[k]); circ.cx(xi,acc[k]); }
@@ -158,6 +162,12 @@ fn tri_square_cin(circ:&mut Builder, x:&[QubitId], product:&[QubitId], inverse:b
             for j in 0..m-1 { circ.cx(x[j+1],row[j]); circ.x(row[j]); circ.cx(x[0],row[j]); }
             continue;
         }
+        if inverse && i==1 && row0_copy() && super::env_flag("SQ_ROW1_INVERSE_CARRIES") {
+            let out=row1_known_output(x);
+            if super::env_flag("I48_TRACE"){eprintln!("I48_ROW1 {} {}",m,circ.active_qubits());}
+            row_addsub_cin(circ,x[1],&x[2..],row,true,false,Some(&out),borrowed);
+            continue;
+        }
         if inverse && i==0 && super::env_flag("SQ_ROW0_INVERSE_CARRIES") {
             // Before row 0 the product is all zero, so every framed output bit
             // is known: x0 on the k low bits, 1 on the top.
@@ -567,11 +577,16 @@ fn tri_square_k2r_flat(circ: &mut Builder, x: &[QubitId], product: &[QubitId]) -
 fn add_cross(circ:&mut Builder,cross:&[QubitId],acc:&[QubitId],inverse:bool,
     recover:Option<(super::width_composition::Plan,Vec<(usize,BitId)>)>,held:&mut Vec<QubitId>)
     ->Option<(super::width_composition::Plan,Vec<(usize,BitId)>)> {
+    // SQ_ASM_TAIL=E: ripple the carry only E bits past the cross word. The
+    // bits above hold b^2 and are random, so a carry reaches E bits in with
+    // probability about 2^-E. An approximate cut, priced as a sell.
+    let full=acc;
+    let acc=match super::optional_env::<usize>("SQ_ASM_TAIL"){Some(e)=>&full[..full.len().min(cross.len()+e)],None=>full};
     let mut room=super::pingpong::walk_max_qubits().saturating_sub(circ.active_qubits()as usize);
     if recover.is_some() || (super::env_flag("SQ_FIT_CROSS") && acc.len().saturating_sub(2)>room) {
         // SQ_OWN_TOP_ZEROS: this node's own top cross bits are zero for every
         // input (2ab < 2^(lo+hi+1)); add them as zero addend bits and lend them.
-        let tops=if super::env_flag("SQ_OWN_TOP_ZEROS"){own_top_zero_bits(cross,acc)}else{Vec::new()};
+        let tops=if super::env_flag("SQ_OWN_TOP_ZEROS"){own_top_zero_bits(cross,full)}else{Vec::new()};
         for &q in &tops{circ.release_clean(q);}
         room+=tops.len();
         if inverse {circ.x_all(acc);}
@@ -962,3 +977,19 @@ pub fn sub_square(circ: &mut Builder, out: &[QubitId], y: &[QubitId]) {
     circ.free(sum_carry);
 }
 
+
+// Before row1, only row0 ran. Physical product[j]=x[j]^1^x0 for1<=j<m,
+// and all higher bits are zero. In the inverse adder frame, low outputs
+// additionally XOR x1 and the top output is1.
+fn row1_known_output(x:&[QubitId])->Vec<(bool,Vec<QubitId>)> {
+    let m=x.len();assert!(m>=3);let k=m-2;
+    let mut out:Vec<_>=(0..k).map(|j|if j+3<m {(true,vec![x[j+3],x[0],x[1]])}else{(false,vec![x[1]])}).collect();
+    out.push((true,Vec::new()));out
+}
+pub(super) fn i48_row_fixture(c:&mut Builder,x:&[QubitId],product:&[QubitId]) {
+    let m=x.len();let row=&product[3..m+2];let out=row1_known_output(x);
+    row_addsub_cin(c,x[1],&x[2..],row,true,false,Some(&out),None);
+}
+pub(super) fn i48_leaf_fixture(c:&mut Builder,x:&[QubitId],product:&[QubitId],inverse:bool) {
+    tri_square_cin(c,x,product,inverse);
+}
diff --git a/src/point_add/stream_wide.rs b/src/point_add/stream_wide.rs
new file mode 100644
index 0000000..ad3200e
--- /dev/null
+++ b/src/point_add/stream_wide.rs
@@ -0,0 +1,26 @@
+//! Known-output addition, including zero-extended sources, with two carry wires.
+use super::Builder;
+use crate::circuit::QubitId;
+pub(crate) fn add(c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:Option<QubitId>,out:&[(bool,Vec<QubitId>)]) {
+    let n=b.len();assert!(n>=1&&a.len()<=n);assert_eq!(out.len(),n);
+    assert!(a.iter().all(|q|!b.contains(q)));
+    assert!(cin.is_none_or(|q|!b.contains(&q)));
+    assert!(out.iter().all(|(_,qs)|qs.iter().all(|q|!b.contains(q))));
+    let mut outgoing=None;
+    for i in(0..n).rev(){
+        let incoming=if i==0{cin}else{
+            let p=c.alloc_qubit();if let Some(&ai)=a.get(i){c.cx(ai,p);}c.cx(b[i],p);
+            if out[i].0{c.x(p);}for &q in &out[i].1{c.cx(q,p);}Some(p)
+        };
+        if let Some(&ai)=a.get(i){c.cx(ai,b[i]);}if let Some(p)=incoming{c.cx(p,b[i]);}
+        if let Some(q)=outgoing{
+            let m=c.alloc_bit();c.hmr(q,m);
+            // carry_out = a*s + a + a*p + s*p + p in GF(2).
+            if let Some(&ai)=a.get(i){c.cz_if(ai,b[i],m);c.z_if(ai,m);if let Some(p)=incoming{c.cz_if(ai,p,m);}}
+            if let Some(p)=incoming{c.cz_if(b[i],p,m);c.z_if(p,m);}
+            c.free_bit(m);c.free(q);
+        }
+        outgoing=if i>0{incoming}else{None};
+    }
+    assert!(outgoing.is_none());
+}
diff --git a/src/point_add/top_result_loan.rs b/src/point_add/top_result_loan.rs
new file mode 100644
index 0000000..c8b58c2
--- /dev/null
+++ b/src/point_add/top_result_loan.rs
@@ -0,0 +1,39 @@
+/// Move the existing known-copy terminal's X measurement before the ladder.
+/// Borrow its now-zero result wire for the final carry; defer the same
+/// Clifford phase repair until the terminal inputs exist, then restore the
+/// result copy only after all carry wires have been erased. No new precision.
+pub(crate) fn result_top_loan_enabled(acc:&[QubitId])->bool {
+    acc.len()>=4 && has_top_copy(acc) && super::env_flag("I74_RESULT_TOP_LOAN")
+}
+
+pub(crate) fn ripple_add_result_top_loan(
+    c:&mut Builder,a:&[QubitId],b:&[QubitId],cin:Option<QubitId>,lent:Option<QubitId>,source_loan:bool,
+) {
+    let n=b.len();assert_eq!(a.len(),n);assert!(n>=3+usize::from(lent.is_some())+usize::from(source_loan));
+    assert!(has_top_copy(b));assert!(a.iter().all(|q|!b.contains(q)));
+    if let Some(q)=lent {assert!(!a.contains(&q)&&!b.contains(&q));}
+    let top=b[n-1];let phase=c.alloc_bit();c.hmr(top,phase);
+    if source_loan {c.cx(a[n-2],a[n-1]);}
+    let owned=n-3-usize::from(lent.is_some())-usize::from(source_loan);
+    let mut carries=c.alloc_qubits(owned);carries.extend(lent);if source_loan {carries.push(a[n-1]);}carries.push(top);
+    let previous=|i:usize|if i==0{cin}else{Some(carries[i-1])};
+    for i in 0..carries.len(){carry_step(c,a[i],b[i],previous(i),carries[i]);}
+    let i=n-2;let p=*carries.last().unwrap();
+    c.cx(p,a[i]);c.cx(p,b[i]);
+    // Identical terminal_top_copy phase polynomial, evaluated in the same
+    // folded penultimate frame. The old top bit was measured earlier.
+    if source_loan {
+        // Original top source is the penultimate source before folding.
+        // Its Z cancels folded-a's Z, leaving Z of the incoming carry.
+        c.cz_if(a[i],b[i],phase);c.z_if(p,phase);c.z_if(b[i],phase);
+    }else{c.z_if(a[n-1],phase);c.cz_if(a[i],b[i],phase);c.z_if(a[i],phase);c.z_if(b[i],phase);}
+    c.free_bit(phase);
+    c.cx(p,a[i]);c.cx(a[i],b[i]);
+    // Keep top as the arithmetic carry until its loan has been paid back.
+    for i in (0..carries.len()).rev(){
+        if i<owned {unwind_carry_step(c,a[i],b[i],previous(i),carries[i]);}
+        else {unwind_carry_step_lent(c,a[i],b[i],previous(i),carries[i]);}
+    }
+    if source_loan {c.cx(a[n-2],a[n-1]);}
+    c.cx(b[n-2],top);
+}
```

