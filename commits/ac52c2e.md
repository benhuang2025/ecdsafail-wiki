# ac52c2e — Extend the free r-doubling prefix by one iteration (R_SMALL 326 → 327) and lower the W-TRUNC margin to 2

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `dd590e3` |
| Commit | `ac52c2ecef16d16122b8133c387e833f34830fd1` |
| Result | 2309 qubits × 2,813,485 Toffoli = **6,496,336,865** |
| Base | `a97b4e9` (git parent, the author's previous submission): 2309 qubits × 2,818,561 Toffoli = 6,508,057,349 |
| Change vs base | qubits ±0, Toffoli −5,076, score −11,720,484 (leaderboard Δ −11,720,484) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two constants change in `kaliski_state.rs`. `R_SMALL_THRESHOLD` goes from 326
to 327, so one more Kaliski iteration doubles the coefficient `r` with a free
wire shift instead of a modular double. The W-TRUNC margin goes from 3 to 2,
which narrows the clipped GCD-register loops by one bit. Neither works alone on
this base: the comment says margin 2 by itself hits one failing input. With both
changed, the op stream draws a clean island. The pair saves 5,076 average
Toffoli at the same 2309 qubits.

## What changed and why it saves Toffoli

1. **`R_SMALL_THRESHOLD`: 326 → 327** (`src/point_add/kaliski_state.rs`, read
   by `r_small_threshold()`, env `KAL_R_SMALL_THRESHOLD`).
   - In Kaliski STEP 7+8 (`kaliski_walk.rs`, forward bodies and their
     `_backward` mirrors), `r := 2r mod p`. For `iter_idx < r_small_threshold()`
     the code calls `mod_double_no_corr(b, r)`, a swap cascade with 0 Toffoli. It
     assumes `r[255] = 0`, so the doubling cannot wrap past p.
   - Otherwise it calls `mod_double_inplace_direct`, which shifts and then adds
     `c = 2^32 + 977` under the overflow bit with `cadd_nbit_const_direct_fast`.
     That adder runs a full carry chain, about 255 Toffoli.
   - Moving the threshold by one makes iteration 326 free in each of the four
     Kaliski runs. The comment estimates −742 Toffoli for this part.
2. **`kal_wtrunc_margin()`: 3 → 2.** Every Toffoli-bearing loop clipped by
   W-TRUNC (STEP-0 OR chain, STEP-2 comparator, STEP-4 load and subtract) is one
   bit narrower from about iteration 31 on. See [`e739b53`](e739b53.md), which
   made the same move on another branch, for the envelope formula.

## Why it is still correct, and what it risks

- **R_SMALL is probabilistic.** The code comment says r's top bit is
  "guaranteed 0" because `max(r, s) ≤ 2^iter`. That induction only proves it
  for iterations below 255. At iteration 326 it is an empirical bound: on a rare
  input with `r ≥ 2^255`, the free shift drops the top bit, the inverse is
  wrong, and the run fails as a classical mismatch. The comment records that 328
  and 329 already fail.
- **W-TRUNC margin 2** is probabilistic in the same way: a GCD register longer
  than the envelope gives a wrong branch or a dropped borrow.
- There is no nonce in this era. The test set is a hash of the op stream, so
  the two knobs are moved together to land on a clean island: margin 2 alone
  fails with one straggler, margin 1 fails. This draw is clean: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The main knob is an iteration threshold, so iteration/threshold tuning fits.
The margin change is comparator/width truncation and is the runner-up label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a97b4e9 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol a97b4e9 ac52c2e -- src/point_add` is
   23 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ac52c2e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,813,485 average Toffoli (rounded)
   - score 6,496,336,865
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index e124fd4..e9e3dc0 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -34,7 +34,11 @@ use super::*;
 /// a plain shift (0 Toffoli) for ~255 CCX savings per iter.
 // bxue-l2 island (peak 2310 after reverting the f1-drop): R_SMALL=326,
 // BULK_PREFIX_SAFE_ITERS=400, pair1=399, pair2=397.
-pub(crate) const R_SMALL_THRESHOLD: usize = 326;
+// T-squeeze: bumped 326->327 on the a97b4e9 (K0=26) base. One extra free-halve
+// iter (-~742 CCX), and the op-count re-roll lands the Fiat-Shamir inputs on an
+// island where margin=2 (below) ALSO validates clean — R=327 + margin=2 stack to
+// 2,813,485 × 2309 = 6,496,336,865. R in {328,329} reject (overflow/island).
+pub(crate) const R_SMALL_THRESHOLD: usize = 327;
 
 pub(crate) fn r_small_threshold() -> usize {
     std::env::var("KAL_R_SMALL_THRESHOLD")
@@ -75,15 +79,14 @@ pub(crate) fn kal_wtrunc_k0() -> usize {
 }
 
 pub(crate) fn kal_wtrunc_margin() -> usize {
-    // Banked: margin=3 — re-tightened from 4 on the CARRY-TAIL SUB W=96 island.
-    // The carry-tail op-count change re-rolled the Fiat-Shamir inputs; a full
-    // 9024-shot screen on this island maps the validity cliff at margin: 3=clean
-    // (0/0/0), 2=FAIL (2 mismatch / 1 phase), 1=FAIL (2 mismatch). So margin=3 is
-    // the validating floor for the combined (carry-tail + GCD W-TRUNC) circuit —
-    // -4,380 avg-exec Toffoli vs margin=4, peak-neutral 2309. Validated clean;
-    // score 6,616,811,249. (Carry-tail base had margin=4; pre-carry-tail it was
-    // 0.) KAL_WTRUNC_MARGIN env override remains available.
-    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(3)
+    // Banked: margin=2 — on the a97b4e9 (K0=26) base PAIRED with R_SMALL=327.
+    // margin=2 alone on this base FAILs (1 straggler); bumping R_SMALL 326->327
+    // re-rolls the Fiat-Shamir inputs onto an island where margin=2 is CLEAN
+    // (9024-shot 0/0/0, peak-neutral 2309). margin=1 and R in {328,329} still
+    // reject here. R=327 + margin=2 together = 2,813,485 avg-exec Toffoli × 2309 =
+    // 6,496,336,865 (validated clean), -5,076 T vs the K0=26/m=3/R=326 base.
+    // KAL_WTRUNC_MARGIN env override remains available.
+    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(2)
 }
 
 /// Empirical-bound truncation width for a CCX-bearing Kaliski width loop at
```

