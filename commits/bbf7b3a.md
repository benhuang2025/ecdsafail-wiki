# bbf7b3a — Narrow the dialog-GCD branch compare from 49 to 44 bits and back the late body-carry trims off from 2 to 1

| | |
| --- | --- |
| Contestant | AnalyticETH |
| Date | 2026-06-05 |
| Submission | `dd264ac` |
| Commit | `bbf7b3a6410665781b597059bace19b99aeb59e0` |
| Result | 1320 qubits × 1,550,539 Toffoli = **2,046,711,480** |
| Base | `c3cbcce` (newjordan, submission `d5ca1f7`): 1320 qubits × 1,554,467 Toffoli = 2,051,896,440 |
| Change vs base | qubits ±0, Toffoli −3,928, score −5,184,960 |
| Leaderboard Δ | −464,640, measured against the frontier at the time, `8c28287` (zuiris, 1320 × 1,550,891 = 2,047,176,120), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit trades two truncations against each other in the dialog GCD:

- It cuts the branch comparator by five bits, from 49 to 44. That saves
  about 870 Toffoli per bit.
- It loosens the controlled-subtract trim on the last four step bands from 2
  bits back to 1, which costs a few hundred Toffoli back.

The author found that with the tighter comparator, the 2-bit trim left too
many hard inputs to find a clean test set. The net is −3,928 average Toffoli
at the same 1320 qubits.

The author's note describes the comparator change as "46 → 44". That is
relative to zuiris's frontier tree. The tree this commit was actually built
on, newjordan's `c3cbcce`, has 49.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_COMPARE_BITS`: 49 → 44.**
   - Each forward GCD step computes `b0_and_b1 = b0 ∧ (u > v)` with
     `dialog_gcd_ccx_cmp_gt_truncated_into_width(_hosted)`. That comparator
     compares only the top `min(COMPARE_BITS, active_width)` bits of the step
     window.
   - It makes one carry CCX per bit and erases the carries by `hmr` plus
     `cz_if`, which costs no Toffoli. Five fewer bits save up to 5 Toffoli per
     call.
   - The calls are the forward and reverse transcript passes of both GCD uses,
     about 870 per shot (see [`cf5e390`](cf5e390.md)). That gives roughly
     −4,300.
2. **`DIALOG_GCD_BODY_CARRY_BAND_TRIMS`: `…,1,1,1,1,2,2,2,2` →
   `…,1,1,1,1,1,1,1,1` (looser).**
   - This reverts the late-band half of [`66c6dac`](66c6dac.md). The list
     gives each band of 17 steps a trim `t`. The step's controlled subtract
     (`dialog_gcd_controlled_sub_selected`) then loads and ripples only
     `active_width − t` bits.
   - Bands 12–15 (steps 204–258) go back from 2 trimmed bits to 1. That adds
     one gated-load CCX and one ripple position per step and pass, a few
     hundred Toffoli in total.
3. **`DIALOG_TAIL_NONCE`: 675 → 50035843.** The 48 `X;X` identity pairs at
   the end of `build_builder()` only reseed the 9,024 test inputs.
   `DIALOG_REROLL` stays at 506906.

## Why it is still correct, and what it risks

- **Comparator.** A 44-bit comparator mis-decides a branch when `u` and `v`
  agree on those 44 bits but differ below. The GCD then may not converge in
  259 steps, which gives a classical failure or phase garbage. Five bits
  fewer make that about 32 times more likely per call than at 49.
- **Band trim.** Going back to a 1-bit trim removes failure modes. The
  subtract covers one more top bit on the late steps.
- **Nonce.** The author used a classical pre-filter. It replays the K2
  forward GCD bit-exactly, including the truncated comparator, rejects nonces
  with a mis-branching input, and fully evaluates the survivors.
- Nonce 50035843 draws a clean set: 9,024 of 9,024 shots, with 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from a narrower comparator, which is comparator/width
truncation. The band-trim change goes the other way and only buys back
island density.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout c3cbcce -- src/point_add`.
   - Do not start from the git parent `8c28287`. That is zuiris's tree, with
     width margin 9, slope 1005, apply clean compare 18,
     `KAL_FOLD_CARRY_TRUNC_W=23` and `DIALOG_REROLL=4269`.
   - Diffing against the parent (82 lines) would wrongly show this commit
     moving all of those to newjordan's values.
   - Against `c3cbcce`, `git diff --ignore-cr-at-eol c3cbcce bbf7b3a -- src/point_add`
     is 6 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol bbf7b3a -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*`, `DIALOG_*` or `SUB4_*` environment variables set, because they
   override the defaults. Expect:
   - 1320 qubits
   - 1,550,539 average Toffoli (rounded)
   - score 2,046,711,480
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `50035843` (with
`DIALOG_REROLL=506906`) and an identical op stream. Any other change needs a
new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6c47a46..c83c20f 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31601,7 +31601,7 @@ fn configure_ecdsafail_submission_route() {
     // 52 -> 51: reclaimed on the 1320q base (the structural five-chunk-apply cut
     // reverted the GCD branch comparator to 52). The comparator never mis-decides
     // a branch at 51 on the verifier support; pure -T, peak-neutral.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "49");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "44");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
@@ -31765,7 +31765,7 @@ fn configure_ecdsafail_submission_route() {
     // WIDTH_SLOPE=1010 above under one shared island on the 1320q base.
     set_default_env(
         "DIALOG_GCD_BODY_CARRY_BAND_TRIMS",
-        "0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2",
+        "0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1",
     );
     // 1320q apply teardown: low-q final chunk plus a hosted boundary split at
     // the second custom-five cut. The retained carry at bit 100 hosts the
@@ -31826,7 +31826,7 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled again for the added WIDTH_SLOPE=1010 + band-late-trim=2 notches:
     // nonce=22000964 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1320q x 1,556,187 T = 2,054,166,840.
-    set_default_env("DIALOG_TAIL_NONCE", "675");
+    set_default_env("DIALOG_TAIL_NONCE", "50035843");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

