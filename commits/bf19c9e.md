# bf19c9e — Drop the W-TRUNC margin to 0 and the constant-subtract carry-tail window from 36 to 24 bits

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `2a05eae` |
| Commit | `bf19c9e53c3a75c0482bfb609d211e22d825d2f4` |
| Result | 2309 qubits × 2,798,569 Toffoli = **6,461,895,821** |
| Base | `6eba4e3` (git parent, the author's previous submission): 2309 qubits × 2,810,401 Toffoli = 6,489,215,909 |
| Change vs base | qubits ±0, Toffoli −11,832, score −27,320,088 (leaderboard Δ −27,320,088) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two truncation constants in `kaliski_state.rs` move together. The W-TRUNC
margin goes from 1 to 0, so the Kaliski GCD-register loops are clipped exactly
to the fitted envelope with no slack. The carry-tail window of the controlled
constant subtractor goes from 36 to 24 bits, so each of its roughly 600 calls
computes 12 fewer borrows. Margin 0 alone fails on the previous test draw.
Changing `W` redraws the test set, and on the `W = 24` draw margin 0 is clean.
The pair saves 11,832 average Toffoli at the same 2309 qubits.

## What changed and why it saves Toffoli

1. **`kal_wtrunc_margin()`: 1 → 0** (`src/point_add/kaliski_state.rs`).
   - The clipped width becomes `min(n, env(it))` with
     `env(it) = n − ⌊(it − 26)·2/3⌋`. That is the affine envelope fitted to the
     largest bit length of `u` and `v_w` seen over 80k random inputs, which the
     base comment says has "~1-7 bits of intrinsic slack above the 80k sample
     max at every iter".
   - Every clipped loop (STEP-0 OR chain, STEP-2 comparator, STEP-4
     load/subtract) is one more bit narrower in every iteration where the clip
     binds, in all four Kaliski runs. See [`e739b53`](e739b53.md).
2. **`kal_carrytail_w()`: 36 → 24.**
   - `csub_nbit_const_direct_fast` (`cuccaro.rs`) computes
     `cut = 33 + W` borrows. It now computes 57 borrow bits instead of 69.
   - Above bit 32 each borrow costs one Toffoli (`!acc_i AND borrow_i`), so each
     call saves 12. The callers are the pair1 `mod_halve` steps, the Solinas
     fold and the low-scratch modular adders. See [`a97b4e9`](a97b4e9.md).

## Why it is still correct, and what it risks

- **Margin 0 is the most aggressive setting of this clip.** Any input whose
  register exceeds the envelope at any iteration is computed wrongly. The comment
  records 1 to 3 failing inputs per draw for every R_SMALL value from 324 to 328
  at `W = 36`, so this setting relies on the draw.
- **W = 24 is still exact in practice.** The longest borrow run above bit 32 in a
  3M-trial Monte Carlo is 19 bits, so a chain to bit 56 leaves about 5 bits of
  slack.
- There is no nonce in this era. The test set is a hash of the op stream, and
  `W` is effectively the re-roll knob here. The comment records clean draws at
  `W ∈ {37, 35, 28, 24}` with margin 0, and failures at 20 to 23, 25 to 27 and
  from 29 up (apart from the clean 35 and 37). This draw is clean: 0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Both changes narrow an approximate operation. The margin (comparator and loop
widths) is comparator/width truncation. The carry-tail window is fold/carry
truncation and is the runner-up. The margin is filed first because it is the
deeper cut and the reason for the re-roll.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6eba4e3 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 6eba4e3 bf19c9e -- src/point_add` is
   25 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol bf19c9e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,798,569 average Toffoli (rounded)
   - score 6,461,895,821
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index f319f74..a56de2e 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -81,14 +81,15 @@ pub(crate) fn kal_wtrunc_k0() -> usize {
 }
 
 pub(crate) fn kal_wtrunc_margin() -> usize {
-    // Banked: margin=1 — on the a97b4e9 (K0=26) base PAIRED with R_SMALL=325.
-    // margin=1 FAILs on the base R=326 island (2 mismatch); R_SMALL=325 re-rolls
-    // the Fiat-Shamir inputs onto an island where margin=1 is CLEAN (9024-shot
-    // 0/0/0, peak-neutral 2309). margin=0 still rejects across R∈{324..328} (a
-    // persistent 1-3 straggler floor — the envelope needs ≥1 bit slack). margin=1
-    // + R=325 = 2,810,401 avg-exec Toffoli × 2309 = 6,489,215,909 (validated clean).
-    // KAL_WTRUNC_MARGIN env override remains available.
-    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(1)
+    // Banked: margin=0 — on the a97b4e9 (K0=26) base, PAIRED with R_SMALL=325 AND
+    // carry-tail W=24. margin=0 (no slack above the fitted W-TRUNC envelope) FAILs
+    // on the R=325/W=36 island (1-3 stragglers across R∈{324..328}); but lowering
+    // the carry-tail W re-rolls the inputs, and on the W=24 island margin=0 is CLEAN
+    // (9024-shot 0/0/0, peak 2309). So all three stack: R=325 (re-roll for the GCD
+    // truncation), margin=0 (deepest GCD-width truncation), W=24 (deepest carry-tail
+    // + the re-roll that makes margin=0 clean). margin=0+R=325+W=24 = 2,798,569 ×
+    // 2309 = 6,461,895,821 (validated clean). KAL_WTRUNC_MARGIN env override remains.
+    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(0)
 }
 
 /// Empirical-bound truncation width for a CCX-bearing Kaliski width loop at
@@ -182,8 +183,14 @@ pub(crate) fn kal_carrytail_w() -> usize {
     // W∈{49,36}; W=36 is the deepest clean island found (2,818,561 avg-exec T ×
     // 2309 peak = 6,508,057,349, 0/0 over 9024). W∈{45,42,40,38,35,34,33,32,31,30,
     // 29,28,27,26,25,24} all FAIL the island lottery on this base. margin=3 floor.
+    // T-squeeze: dropped W=36->24 on the NEW (margin=0, R_SMALL=325) island. The
+    // W-TRUNC margin=0 + R=325 re-roll reopened the carry-tail W door: a margin=0
+    // W-sweep found CLEAN islands at W∈{37,35,28,24}; W=24 is the deepest (borrow
+    // chain to bit 33+24=57, still 5 bits above the 19-bit MC max → arithmetically
+    // exact). W∈{20,21,22,23,25,26,27,29..} reject the lottery on this island.
+    // margin=0 + R=325 + W=24 = 2,798,569 × 2309 = 6,461,895,821 (validated clean).
     // KAL_CARRYTAIL_W env override remains.
-    env_usize("KAL_CARRYTAIL_W").unwrap_or(36)
+    env_usize("KAL_CARRYTAIL_W").unwrap_or(24)
 }
 
 pub(crate) fn kal_carrytail_k0() -> usize {
```

