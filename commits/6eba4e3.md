# 6eba4e3 — Lower the W-TRUNC margin from 3 to 1, paying one free-doubling iteration (R_SMALL 326 → 325) to land a clean island

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `bfe53b2` |
| Commit | `6eba4e3f23043c68691a01e0b8015077e745ae09` |
| Result | 2309 qubits × 2,810,401 Toffoli = **6,489,215,909** |
| Base | `a97b4e9` (the author's earlier submission): 2309 qubits × 2,818,561 Toffoli = 6,508,057,349 |
| Change vs base | qubits ±0, Toffoli −8,160, score −18,841,440 |
| Leaderboard Δ | −3,204,892, measured against the frontier at the time, `d4959a1` (2309 × 2,811,789), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two constants in `kaliski_state.rs`. The W-TRUNC safety margin goes from 3 to
1, so every loop clipped to the Kaliski bit-length envelope is two bits
narrower. That saves the Toffoli. On its own, margin 1 fails on this base's test
draw. To get a clean draw, `R_SMALL_THRESHOLD` goes the other way, from 326 to
325, which costs about 742 Toffoli but changes the op stream and so the test
set. Net, 8,160 fewer average Toffoli at the same 2309 qubits.

## What changed and why it saves Toffoli

1. **`kal_wtrunc_margin()`: 3 → 1** (`src/point_add/kaliski_state.rs`, env
   `KAL_WTRUNC_MARGIN`).
   - The clipped width is `min(n, env(it) + margin)` with
     `env(it) = n − ⌊(it − K0)·2/3⌋` and `K0 = 26` (see [`e739b53`](e739b53.md)
     for the sites it clips).
   - With margin 1, each STEP-0 OR chain, STEP-2 comparator and STEP-4
     load/subtract loop is 2 bits narrower than at margin 3, from about
     iteration 29 on, in all four Kaliski runs. This is the saving: about
     8,900 Toffoli, the net −8,160 plus the R_SMALL cost below.
2. **`R_SMALL_THRESHOLD`: 326 → 325.**
   - Below this iteration, Kaliski STEP 7+8 doubles `r` with a 0-Toffoli swap
     cascade (`mod_double_no_corr`). From it on, it uses
     `mod_double_inplace_direct`, which adds `c` under the overflow bit with a
     full carry chain. See [`ac52c2e`](ac52c2e.md).
   - Lowering it makes iteration 325 pay for a real modular double in each
     Kaliski run, about +742 Toffoli by the comment. The purpose is only to
     re-roll the test set.

## Why it is still correct, and what it risks

- **Margin 1 is probabilistic.** It leaves 1 bit of slack above an envelope
  fitted to 80k random inputs. An input whose GCD registers stay longer than
  that makes a clipped comparator or subtractor ignore a live high bit, and the
  inversion fails (a classical mismatch, or phase garbage). The comment says
  margin 0 still fails for every R in 324..328.
- **R_SMALL 325 is safer than 326.** It moves the empirical "r's top bit is 0"
  assumption one iteration earlier, so it can only remove failures.
- There is no nonce in this era. The test set is a hash of the op stream, and
  the comment records that margin 1 fails on the R = 326 draw (2 mismatches)
  but is clean on the R = 325 draw. R = 324 is also clean but costs more;
  R ∈ {323, 326, 327} fail at margin 1. This draw is clean: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from a narrower width clip, which is comparator/width
truncation. The R_SMALL change is an island re-roll that costs Toffoli, not a
lever of its own.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a97b4e9 -- src/point_add`.
   - Do not start from the git parent `d4959a1`. That is the author's parallel
     submission, with the MAJ-fold for the constant adder and the frame-reset
     fold.
   - Against the parent, the diff is 72 lines in 3 files. It would show those
     two gate folds being removed, which this commit never had.
   - Against `a97b4e9`, `git diff --ignore-cr-at-eol a97b4e9 6eba4e3 -- src/point_add`
     is 25 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 6eba4e3 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,810,401 average Toffoli (rounded)
   - score 6,489,215,909
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index e124fd4..f319f74 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -34,7 +34,13 @@ use super::*;
 /// a plain shift (0 Toffoli) for ~255 CCX savings per iter.
 // bxue-l2 island (peak 2310 after reverting the f1-drop): R_SMALL=326,
 // BULK_PREFIX_SAFE_ITERS=400, pair1=399, pair2=397.
-pub(crate) const R_SMALL_THRESHOLD: usize = 326;
+// T-squeeze: R_SMALL=325 paired with margin=1 (below). The deeper margin=1
+// W-TRUNC FAILs on the base R=326 island (2 mismatch); setting R_SMALL=325
+// re-rolls the Fiat-Shamir inputs onto an island where margin=1 is CLEAN. R=325
+// costs ~742 CCX vs R=326 but margin=1 (vs margin=2) saves ~3,000 more — net win.
+// margin=1 + R=325 = 2,810,401 × 2309 = 6,489,215,909 (validated clean). R=324 is
+// also clean (2,811,073, worse); R in {323,326,327} reject at margin=1.
+pub(crate) const R_SMALL_THRESHOLD: usize = 325;
 
 pub(crate) fn r_small_threshold() -> usize {
     std::env::var("KAL_R_SMALL_THRESHOLD")
@@ -75,15 +81,14 @@ pub(crate) fn kal_wtrunc_k0() -> usize {
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
+    // Banked: margin=1 — on the a97b4e9 (K0=26) base PAIRED with R_SMALL=325.
+    // margin=1 FAILs on the base R=326 island (2 mismatch); R_SMALL=325 re-rolls
+    // the Fiat-Shamir inputs onto an island where margin=1 is CLEAN (9024-shot
+    // 0/0/0, peak-neutral 2309). margin=0 still rejects across R∈{324..328} (a
+    // persistent 1-3 straggler floor — the envelope needs ≥1 bit slack). margin=1
+    // + R=325 = 2,810,401 avg-exec Toffoli × 2309 = 6,489,215,909 (validated clean).
+    // KAL_WTRUNC_MARGIN env override remains available.
+    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(1)
 }
 
 /// Empirical-bound truncation width for a CCX-bearing Kaliski width loop at
```

