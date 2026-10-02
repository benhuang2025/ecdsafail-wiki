# e4edca0 — Split the apply add/sub into three chunks and clear both boundary carries with one fused compare (1438 → 1434 qubits)

| | |
| --- | --- |
| Contestant | nikhiljha |
| Date | 2026-06-03 |
| Submission | `8119916` |
| Commit | `e4edca0a5ee5a78a71a2fd307b02736cea360ede` |
| Result | 1434 qubits × 1,739,149 Toffoli = **2,493,939,666** |
| Base | `f42ce5c` (git parent and frontier at the time, Sam-Scolari): 1438 qubits × 1,736,773 Toffoli = 2,497,479,574 |
| Change vs base | qubits −4, Toffoli +2,376, score −3,539,908 (leaderboard Δ −3,539,908) |
| Family | Fusion → gate/op fusion |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog GCD's apply pass adds and subtracts a controlled 256-bit value
into a 257-bit accumulator. Since the earlier peak work it has done this in
two chunks split at bit 128, so that only one chunk's scratch (a loaded
operand slice plus its carry lane) is live at a time. Those chunks set the
peak.

This commit splits the add into three chunks: `[0, 124)`, `[124, 130)` and
`[130, 257)`. Both large chunks are now narrower than before, and the peak
falls by 4 to 1434. A three-way split needs two boundary carries erased
afterwards. Done the old way, with one compare each, that would cost a whole
extra 124-bit comparison. The commit instead fuses both erasures into one
130-bit carry sweep that taps the running carry at bit 124 and at bit 130. The
only extra cost against the old two-chunk version is 3 Toffoli per call:
2 more compare bits and one more tap. Over the 792 apply calls that is
+2,376 Toffoli, exactly the measured change. A small exact reuse also lets
the middle chunk borrow the idle carry-in wire as its padding bit.

## What changed and why it saves qubits

All changes are in `src/point_add/mod.rs`.

Context: each apply-pass step runs `dialog_gcd_add_ctrl_chunked_low_to_ext`
(inside `dialog_gcd_cmod_add_materialized_pseudomersenne_chunked`) or its
subtract twin `dialog_gcd_sub_ctrl_chunked_low_to_ext`. For each chunk
`[lo, hi)` except the last, it:
- loads `f = ctrl & source[lo..hi]` into fresh wires (CCX);
- runs `cuccaro_add_fast` on `f ++ zero` into `acc[lo..hi] ++ cout`, with the
  previous chunk's carry-out as carry-in;
- clears `f` with `hmr` + `cz_if`.

The last chunk uses `cuccaro_add_fast_low_to_ext`. Each `cout` stays live
until the end. Then each `cout` is erased exactly by recomputing it as the
prefix comparison `acc[..hi] < source[..hi]` (for the subtract,
`¬source[..hi] < acc[..hi]`). Each chunk's scratch is about 2 × its width.

1. **Three chunks: `DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS` 2 → 3,
   `DIALOG_GCD_APPLY_CHUNKED_F_CUT` 128 → 124, new
   `DIALOG_GCD_APPLY_CHUNKED_F_CUT2 = 130`.**
   - `dialog_gcd_chunk_hi(blocks, block, ext_n)` now returns `F_CUT` for
     block 0 when `blocks ≤ 3`, and `F_CUT2` (default `2·ext_n/3`) for
     block 1 when `blocks = 3`.
   - Chunk widths go from 128 + 129 to 124 + 6 + 127. The two large chunks are
     4 and 2 bits narrower, so the apply pass's high-water mark drops. The
     global peak falls by 4, to the next binder at 1434.
2. **Fused boundary clears: new `ccx_cmp_lt_into_fast_prefix_targets(b, u, v, ctrl, targets)`,
   gated by `DIALOG_GCD_APPLY_CHUNKED_F_FUSE_BOUNDARY_CLEARS` (on unless `"0"`).**
   - `ccx_cmp_lt_into_fast` computes `u < v` with a ripple of MAJ-style steps.
     After step `i`, wire `u[i]` holds the borrow out of the low `i + 1` bits,
     which is the comparison of the `(i + 1)`-bit prefixes. One CCX with
     `ctrl` copies the final borrow into the target. The sweep is then undone
     with measured carry clears (`hmr` + `cz_if`), so it costs `n + 1`
     Toffoli.
   - The new function runs one sweep over the longest prefix
     (`n = 130`). At each prefix length `p` in `targets` (124 and 130) it does
     `ccx(ctrl, u[p − 1], target)`. Every boundary carry is the prefix
     comparison at its own cut, so one sweep serves all of them. It costs
     `n + #targets = 132` Toffoli.
   - Old two-chunk cost: one 128-bit compare, 129 Toffoli. Three chunks
     unfused would cost 125 + 131 = 256. Fused: 132, so +3 per call. There
     are 2 × 396 = 792 calls (the add and the subtract at each step), which
     gives +2,376.
   - When `KAL_VENT_MODADD=1` (not set on this route) it falls back to
     separate compares.
3. **Carry-in reuse: `DIALOG_GCD_APPLY_CHUNKED_F_REUSE_CIN_ZERO`** (on unless
   `"0"`). A non-first, non-last chunk needs a |0⟩ padding wire (`zero`) for
   its Cuccaro. The old code allocated one. The new code uses `c_in`, the
   first chunk's carry-in. It is |0⟩ and idle once the first chunk's Cuccaro
   has restored it. This saves one wire during the middle chunk.
4. **Reroll pair: `DIALOG_REROLL` 3 → 214, `DIALOG_POST_SUB_REROLL` 51 → 466.**
   These are the identity `X;X` counts that only re-draw the 9,024 test
   inputs.

## Why it is still correct, and what it risks

Everything here is exact. The chunked add and subtract give the same sum at
any cuts, because the carry crosses each boundary through its `cout`. The
fused clear computes the same prefix comparisons as the separate compares,
and its carries are restored by the same measured uncompute (see
[measurement-uncompute](../concepts/measurement-uncompute.md)). The reused
`c_in` is |0⟩ when it is borrowed and |0⟩ after. A wrong tap position would
leave a `cout` dirty, which shows up as ancilla garbage.

No approximation changes. The reroll pair (214, 466) draws a clean set for
the existing ones: 9,024 of 9,024 shots pass with 0 classical, 0 phase and
0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Filed as gate/op fusion: two boundary-carry erasures are merged into one
carry sweep with several taps. That fusion is what makes the three-way split
affordable. The qubits themselves come from the finer chunking, so
"Windowing → windowed carry/shift blocks" was the runner-up.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f42ce5c -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol f42ce5c e4edca0 -- src/point_add` is
   182 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol e4edca0 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`,
   `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set, because
   `set_default_env` keeps any value already in the environment. Expect:
   - 1434 qubits
   - 1,739,149 average Toffoli (rounded)
   - score 2,493,939,666
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the reroll pair `DIALOG_REROLL=214`,
`DIALOG_POST_SUB_REROLL=466` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 17ada9e..ab735fc 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -3551,6 +3551,79 @@ fn ccx_cmp_lt_into_fast(b: &mut B, u: &[QubitId], v: &[QubitId], ctrl: QubitId,
     b.free(c_in);
 }
 
+fn ccx_cmp_lt_into_fast_prefix_targets(
+    b: &mut B,
+    u: &[QubitId],
+    v: &[QubitId],
+    ctrl: QubitId,
+    targets: &[(QubitId, usize)],
+) {
+    if targets.is_empty() {
+        return;
+    }
+    if kal_vent_modadd_enabled() {
+        for &(target, n) in targets {
+            ccx_cmp_lt_into_fast(b, &u[..n], &v[..n], ctrl, target);
+        }
+        return;
+    }
+
+    let n = targets.last().expect("non-empty targets").1;
+    assert_eq!(u.len(), n);
+    assert_eq!(v.len(), n);
+    assert!(n > 0);
+    assert!(targets.iter().all(|&(_, p)| (1..=n).contains(&p)));
+    assert!(targets.windows(2).all(|w| w[0].1 < w[1].1));
+
+    let c_in = b.alloc_qubit();
+    let carries = b.alloc_qubits(n);
+    for &q in u {
+        b.x(q);
+    }
+
+    b.cx(u[0], v[0]);
+    b.cx(u[0], c_in);
+    b.ccx(c_in, v[0], carries[0]);
+    b.cx(carries[0], u[0]);
+    let mut next_target = 0;
+    while next_target < targets.len() && targets[next_target].1 == 1 {
+        b.ccx(ctrl, u[0], targets[next_target].0);
+        next_target += 1;
+    }
+    for i in 1..n {
+        b.cx(u[i], v[i]);
+        b.cx(u[i], u[i - 1]);
+        b.ccx(u[i - 1], v[i], carries[i]);
+        b.cx(carries[i], u[i]);
+        while next_target < targets.len() && targets[next_target].1 == i + 1 {
+            b.ccx(ctrl, u[i], targets[next_target].0);
+            next_target += 1;
+        }
+    }
+    assert_eq!(next_target, targets.len());
+
+    for i in (1..n).rev() {
+        b.cx(carries[i], u[i]);
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        b.cz_if(u[i - 1], v[i], m);
+        b.cx(u[i], u[i - 1]);
+        b.cx(u[i], v[i]);
+    }
+    b.cx(carries[0], u[0]);
+    let m0 = b.alloc_bit();
+    b.hmr(carries[0], m0);
+    b.cz_if(c_in, v[0], m0);
+    b.cx(u[0], c_in);
+    b.cx(u[0], v[0]);
+
+    for &q in u {
+        b.x(q);
+    }
+    b.free_vec(&carries);
+    b.free(c_in);
+}
+
 /// Like `mod_add_qq` but uses `cmp_lt_into_fast` for the flag uncompute.
 /// NOT safe inside emit_inverse blocks.
 fn mod_add_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
@@ -23417,6 +23490,27 @@ fn dialog_gcd_apply_chunked_f_cut() -> Option<usize> {
         .filter(|&cut| (1..N).contains(&cut))
 }
 
+fn dialog_gcd_apply_chunked_f_cut2() -> Option<usize> {
+    std::env::var("DIALOG_GCD_APPLY_CHUNKED_F_CUT2")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .filter(|&cut| (1..N).contains(&cut))
+}
+
+fn dialog_gcd_apply_chunked_f_reuse_cin_zero_enabled() -> bool {
+    std::env::var("DIALOG_GCD_APPLY_CHUNKED_F_REUSE_CIN_ZERO")
+        .ok()
+        .as_deref()
+        != Some("0")
+}
+
+fn dialog_gcd_apply_chunked_f_fuse_boundary_clears_enabled() -> bool {
+    std::env::var("DIALOG_GCD_APPLY_CHUNKED_F_FUSE_BOUNDARY_CLEARS")
+        .ok()
+        .as_deref()
+        != Some("0")
+}
+
 fn dialog_gcd_raw_tobitvector_fit_bench_enabled() -> bool {
     std::env::var(DIALOG_GCD_RAW_TOBITVECTOR_FIT_BENCH_ENV)
         .ok()
@@ -24614,9 +24708,14 @@ fn dialog_gcd_clear_controlled_slice_hmr(
 }
 
 fn dialog_gcd_chunk_hi(blocks: usize, block: usize, ext_n: usize) -> usize {
-    if blocks == 2 && block == 0 {
+    if block == 0 && blocks <= 3 {
         return dialog_gcd_apply_chunked_f_cut().unwrap_or(ext_n / 2).min(ext_n - 1);
     }
+    if blocks == 3 && block == 1 {
+        return dialog_gcd_apply_chunked_f_cut2()
+            .unwrap_or(2 * ext_n / 3)
+            .min(ext_n - 1);
+    }
     ((block + 1) * ext_n) / blocks
 }
 
@@ -24651,14 +24750,21 @@ fn dialog_gcd_add_ctrl_chunked_low_to_ext(
 
         assert!(hi <= n);
         let f = dialog_gcd_load_controlled_slice(b, ctrl, source, lo, hi);
-        let zero = b.alloc_qubit();
+        let owned_zero = if carry == c_in || !dialog_gcd_apply_chunked_f_reuse_cin_zero_enabled() {
+            Some(b.alloc_qubit())
+        } else {
+            None
+        };
+        let zero = owned_zero.unwrap_or(c_in);
         let cout = b.alloc_qubit();
         let mut a_block = f.clone();
         a_block.push(zero);
         let mut acc_block = acc_ext[lo..hi].to_vec();
         acc_block.push(cout);
         cuccaro_add_fast(b, &a_block, &acc_block, carry);
-        b.free(zero);
+        if let Some(zero) = owned_zero {
+            b.free(zero);
+        }
         dialog_gcd_clear_controlled_slice_hmr(b, ctrl, source, lo, &f);
         b.free_vec(&f);
         couts.push((cout, hi));
@@ -24666,8 +24772,22 @@ fn dialog_gcd_add_ctrl_chunked_low_to_ext(
         lo = hi;
     }
 
-    for &(cout, p) in couts.iter().rev() {
-        ccx_cmp_lt_into_fast(b, &acc_ext[..p], &source[..p], ctrl, cout);
+    if dialog_gcd_apply_chunked_f_fuse_boundary_clears_enabled() {
+        if let Some(&(_, p)) = couts.last() {
+            ccx_cmp_lt_into_fast_prefix_targets(
+                b,
+                &acc_ext[..p],
+                &source[..p],
+                ctrl,
+                &couts,
+            );
+        }
+    } else {
+        for &(cout, p) in couts.iter().rev() {
+            ccx_cmp_lt_into_fast(b, &acc_ext[..p], &source[..p], ctrl, cout);
+        }
+    }
+    for &(cout, _) in couts.iter().rev() {
         b.free(cout);
     }
 }
@@ -24703,14 +24823,21 @@ fn dialog_gcd_sub_ctrl_chunked_low_to_ext(
 
         assert!(hi <= n);
         let f = dialog_gcd_load_controlled_slice(b, ctrl, source, lo, hi);
-        let zero = b.alloc_qubit();
+        let owned_zero = if borrow == c_in || !dialog_gcd_apply_chunked_f_reuse_cin_zero_enabled() {
+            Some(b.alloc_qubit())
+        } else {
+            None
+        };
+        let zero = owned_zero.unwrap_or(c_in);
         let bout = b.alloc_qubit();
         let mut a_block = f.clone();
         a_block.push(zero);
         let mut acc_block = acc_ext[lo..hi].to_vec();
         acc_block.push(bout);
         cuccaro_sub_fast(b, &a_block, &acc_block, borrow);
-        b.free(zero);
+        if let Some(zero) = owned_zero {
+            b.free(zero);
+        }
         dialog_gcd_clear_controlled_slice_hmr(b, ctrl, source, lo, &f);
         b.free_vec(&f);
         bouts.push((bout, hi));
@@ -24718,14 +24845,34 @@ fn dialog_gcd_sub_ctrl_chunked_low_to_ext(
         lo = hi;
     }
 
-    for &(bout, p) in bouts.iter().rev() {
-        for i in 0..p {
-            b.x(source[i]);
+    if dialog_gcd_apply_chunked_f_fuse_boundary_clears_enabled() {
+        if let Some(&(_, p)) = bouts.last() {
+            for i in 0..p {
+                b.x(source[i]);
+            }
+            ccx_cmp_lt_into_fast_prefix_targets(
+                b,
+                &source[..p],
+                &acc_ext[..p],
+                ctrl,
+                &bouts,
+            );
+            for i in 0..p {
+                b.x(source[i]);
+            }
         }
-        ccx_cmp_lt_into_fast(b, &source[..p], &acc_ext[..p], ctrl, bout);
-        for i in 0..p {
-            b.x(source[i]);
+    } else {
+        for &(bout, p) in bouts.iter().rev() {
+            for i in 0..p {
+                b.x(source[i]);
+            }
+            ccx_cmp_lt_into_fast(b, &source[..p], &acc_ext[..p], ctrl, bout);
+            for i in 0..p {
+                b.x(source[i]);
+            }
         }
+    }
+    for &(bout, _) in bouts.iter().rev() {
         b.free(bout);
     }
 }
@@ -29859,7 +30006,7 @@ fn configure_ecdsafail_submission_route() {
     // 257-78) and drops the apply phase to 1543 == the ROUND84 floor. Global peak
     // 1558 -> 1543. F_CUT only reseeds + grows the boundary comparator (+~6,384
     // avg-executed Toffoli, 1,688,703 -> 1,695,087); peak-neutral for any cut>=78.
-    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS", "2");
+    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS", "3");
     // PEAK-QUBIT CUT 1542 -> 1500 (-42q). Two co-binders dropped together:
     //  (1) ROUND84 Karatsuba square (z0=lo^2 / z2=hi^2 schoolbook squares parked a
     //      ~130-wide cuccaro_add_fast carry lane, and the Solinas mid_sub/sub_add's
@@ -29915,11 +30062,12 @@ fn configure_ecdsafail_submission_route() {
     // 399 T/qubit, far inside break-even. Score 1446 x 1,740,263 = 2,516,420,298.
     set_default_env("DIALOG_GCD_BODY_HOST_CIN", "1");
     set_default_env("DIALOG_GCD_LATE_BORROW_UV_HIGH", "1");
-    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "128");
+    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "124");
+    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "130");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "3");
-    set_default_env("DIALOG_POST_SUB_REROLL", "51");
+    set_default_env("DIALOG_REROLL", "214");
+    set_default_env("DIALOG_POST_SUB_REROLL", "466");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

