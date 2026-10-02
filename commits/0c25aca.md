# 0c25aca — Start the W-TRUNC envelope one iteration earlier (K0 26 → 25) and trim the carry-tail window to 23 bits

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `66f1312` |
| Commit | `0c25aca746eecbbb37ee8d5cd631550b7997e455` |
| Result | 2309 qubits × 2,794,983 Toffoli = **6,453,615,747** |
| Base | `bf19c9e` (git parent, the author's previous submission): 2309 qubits × 2,798,569 Toffoli = 6,461,895,821 |
| Change vs base | qubits ±0, Toffoli −3,586, score −8,280,074 (leaderboard Δ −8,280,074) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two constants in `kaliski_state.rs`. `KAL_WTRUNC_K0`, the number of early
Kaliski iterations that run at full width, goes from 26 to 25, so the clipped
GCD-register loops start shrinking one iteration earlier. The carry-tail window
`W` goes from 24 to 23, mainly to redraw the test set: the comment says
`K0 = 25` alone has one failing input on the old draw. Together they save 3,586
average Toffoli at the same 2309 qubits.

## What changed and why it saves Toffoli

1. **`kal_wtrunc_k0()`: 26 → 25** (`src/point_add/kaliski_state.rs`, env
   `KAL_WTRUNC_K0`).
   - The envelope is `env(it) = n` for `it < K0`, else
     `n − ⌊(it − K0)·2/3⌋`. With the margin at 0 (from [`bf19c9e`](bf19c9e.md))
     the clipped width is `env(it)` itself.
   - Lowering `K0` by one adds 1 to `it − K0` in every later iteration, so the
     width drops by one bit in two of every three iterations. Every clipped loop
     (STEP-0 OR chain, STEP-2 comparator, STEP-4 load/subtract) in all four
     Kaliski runs gets that much cheaper. See [`e739b53`](e739b53.md) for the
     sites.
2. **`kal_carrytail_w()`: 24 → 23.** The constant subtractor's borrow chain
   ends at bit 55 instead of 56, one Toffoli less per call. Its main job is to
   re-roll the test draw.

## Why it is still correct, and what it risks

- **`K0 = 25` is probabilistic.** It tightens an empirical envelope that already
  has no margin. An input whose GCD registers have not shrunk by the scheduled
  amount gets a clipped comparison or subtraction, and the inversion fails as a
  classical mismatch or phase garbage. The comment says `K0 = 24` fails.
- **`W = 23` is exact in practice.** The chain still reaches 4 bits beyond the
  longest borrow run (19 bits above bit 32) seen in a 3M-trial Monte Carlo.
- There is no nonce in this era. The test set is a hash of the op stream, and
  the comment records that `K0 = 25` is one straggler short at `W = 24`, clean at
  `W = 23`, and that `W ∈ {20, 21, 22}` fail. This draw is clean: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving is a narrower Kaliski width clip, which is comparator/width
truncation. The carry-tail step is a one-bit re-roll.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout bf19c9e -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol bf19c9e 0c25aca -- src/point_add` is
   12 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 0c25aca -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,794,983 average Toffoli (rounded)
   - score 6,453,615,747
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index a56de2e..570e745 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -77,7 +77,12 @@ pub(crate) fn kal_wtrunc_enabled() -> bool {
 }
 
 pub(crate) fn kal_wtrunc_k0() -> usize {
-    env_usize("KAL_WTRUNC_K0").unwrap_or(26)
+    // T-squeeze: K0=25 (was 26) — paired with margin=0, R_SMALL=325, carry-tail W=23.
+    // On the margin=0/R=325 island, K0=25 alone is 1 straggler short; dropping the
+    // carry-tail W 24->23 re-rolls the inputs and K0=25 then validates CLEAN. Starts
+    // the W-TRUNC envelope decay 1 iter earlier (fewer CCX). K0=25+W=23 = 2,794,983
+    // × 2309 = 6,453,615,747 (validated clean). K0=24, and W∈{20,21,22} reject here.
+    env_usize("KAL_WTRUNC_K0").unwrap_or(25)
 }
 
 pub(crate) fn kal_wtrunc_margin() -> usize {
@@ -189,8 +194,11 @@ pub(crate) fn kal_carrytail_w() -> usize {
     // chain to bit 33+24=57, still 5 bits above the 19-bit MC max → arithmetically
     // exact). W∈{20,21,22,23,25,26,27,29..} reject the lottery on this island.
     // margin=0 + R=325 + W=24 = 2,798,569 × 2309 = 6,461,895,821 (validated clean).
+    // T-squeeze cont.: W=23 (was 24), paired with K0=25 — the W 24->23 re-roll is
+    // what makes K0=25 clean (and saves carry-tail CCX). borrow chain to bit 56,
+    // still 4 bits above the 19-bit MC max. K0=25+W=23 = 2,794,983 (validated clean).
     // KAL_CARRYTAIL_W env override remains.
-    env_usize("KAL_CARRYTAIL_W").unwrap_or(24)
+    env_usize("KAL_CARRYTAIL_W").unwrap_or(23)
 }
 
 pub(crate) fn kal_carrytail_k0() -> usize {
```

