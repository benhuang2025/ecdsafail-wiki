# 6abbe60 — Narrow the dialog-GCD branch compare from 48 to 47 bits, paying one width-slope notch back (1.010 → 1.009) for a clean island

| | |
| --- | --- |
| Contestant | robertkodra |
| Date | 2026-06-05 |
| Submission | `2a0f9ee` |
| Commit | `6abbe6005845b835fc2e776623365e95d9574087` |
| Result | 1320 qubits × 1,553,327 Toffoli = **2,050,391,640** |
| Base | `cf5e390` (the author's previous submission): 1320 qubits × 1,553,603 Toffoli = 2,050,755,960 |
| Change vs base | qubits ±0, Toffoli −276, score −364,320 (leaderboard Δ −364,320) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit moves two knobs in opposite directions:

- It narrows the dialog-GCD branch comparator by one more bit, from 48 to 47.
  That saves about 870 Toffoli.
- It loosens the GCD width envelope by one notch, slope 1.010 → 1.009 bits
  per step. That makes the late GCD steps slightly wider again and costs
  about 590 Toffoli.

The net is −276 average Toffoli at the same 1320 qubits. The looser slope
removes some hard inputs, which makes room for the tighter comparator under
one clean nonce. Two commits later, [`8a9d274`](8a9d274.md) (after
[`2f24e2f`](2f24e2f.md)), puts the slope back to 1.010 for −592.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_COMPARE_BITS`: 48 → 47.**
   - The branch comparator `dialog_gcd_ccx_cmp_gt_truncated_into_width(_hosted)`
     decides `u > v` from the top `min(COMPARE_BITS, active_width)` bits of
     the step's window.
   - It makes one carry CCX per bit and erases the carries by measurement
     (`hmr` plus `cz_if`), which costs no Toffoli.
   - One fewer bit saves one Toffoli on each of about 870 calls per shot.
     Those calls are the forward and reverse transcript passes of both GCD
     uses.
2. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 1010 → 1009 (looser).**
   - `dialog_gcd_tobitvector_active_width(step)` is
     `256 − step × slope + WIDTH_MARGIN` (margin 10), rounded up to even. With
     a smaller slope, step `s` gets `0.001 × s` more bits, and some late steps
     round up by 2 bits.
   - Those steps pay more in the cswap and the controlled subtract, in every
     pass. The cost is about +590 Toffoli, the reverse of the −592 measured in
     [`8a9d274`](8a9d274.md).
   - A wider window means fewer inputs overflow the envelope, so the number
     of hard inputs drops.
3. **`DIALOG_TAIL_NONCE`: 145815044552559 → 256973122702329.** The 48 `X;X`
   identity pairs at the end of `build_builder()` only reseed the 9,024 test
   inputs.

## Why it is still correct, and what it risks

- **47-bit comparator.** It mis-decides a branch when `u` and `v` agree on
  the top 47 window bits but differ below. That can stop the GCD from
  converging in 259 steps, which gives a classical failure or phase garbage.
- **Slope.** Loosening the slope only removes failure modes: the window
  covers more bits.
- Nonce 256973122702329 draws a clean set: 9,024 of 9,024 shots, with
  0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from a narrower comparator, which is comparator/width
truncation. The slope change goes the other way. It spends Toffoli to lower
the hard-input rate, not to save Toffoli.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout cf5e390 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol cf5e390 6abbe60 -- src/point_add` is 6 lines
   in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 6abbe60 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*`, `DIALOG_*` or `SUB4_*` environment variables set, because they
   override the defaults. Expect:
   - 1320 qubits
   - 1,553,327 average Toffoli (rounded)
   - score 2,050,391,640
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `256973122702329` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a00036c..dea4016 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31601,7 +31601,7 @@ fn configure_ecdsafail_submission_route() {
     // 52 -> 51: reclaimed on the 1320q base (the structural five-chunk-apply cut
     // reverted the GCD branch comparator to 52). The comparator never mis-decides
     // a branch at 51 on the verifier support; pure -T, peak-neutral.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "48");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "47");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
@@ -31795,7 +31795,7 @@ fn configure_ecdsafail_submission_route() {
     // widths stay within the provably-|0> converged GCD region. ~-512 avg-T.
     // 1009 -> 1010: one further notch, stacked with the band-trim late-band
     // deepening below under one shared island. Peak-neutral at 1320q.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1010");
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1009");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
     set_default_env("DIALOG_REROLL", "506906");
@@ -31826,7 +31826,7 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled again for the added WIDTH_SLOPE=1010 + band-late-trim=2 notches:
     // nonce=22000964 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1320q x 1,556,187 T = 2,054,166,840.
-    set_default_env("DIALOG_TAIL_NONCE", "145815044552559");
+    set_default_env("DIALOG_TAIL_NONCE", "256973122702329");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

