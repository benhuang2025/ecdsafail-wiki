# c3cbcce — Narrow the dialog-GCD branch compare from 51 to 49 bits on mpjunior92's tree

| | |
| --- | --- |
| Contestant | newjordan |
| Date | 2026-06-05 |
| Submission | `d5ca1f7` |
| Commit | `c3cbccee94853549c07d05bd8d43656832be9ac6` |
| Result | 1320 qubits × 1,554,467 Toffoli = **2,051,896,440** |
| Base | `66c6dac` (mpjunior92, submission `da99bf4`): 1320 qubits × 1,556,187 Toffoli = 2,054,166,840 |
| Change vs base | qubits ±0, Toffoli −1,720, score −2,270,400 |
| Leaderboard Δ | −728,640, measured against the frontier at the time, `5ad23b1` (zuiris, 1320 × 1,555,019 = 2,052,625,080), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog GCD decides each step's branch with a comparator that looks at
only the top bits of `u` and `v`. This commit shortens that comparator from
51 to 49 bits. Each bit costs one Toffoli per call, so the change saves
1,720 average Toffoli, about 860 per bit, at the same 1320 qubits.

A shorter comparator decides wrongly on a few more inputs. That made a clean
test set rarer, so the author re-hunted both reroll knobs on a rented CPU
fleet.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_COMPARE_BITS`: 51 → 49.**
   - Each forward GCD step computes `b0_and_b1 = b0 ∧ (u > v)` with
     `dialog_gcd_ccx_cmp_gt_truncated_into_width(_hosted)`. That compares only
     the top `min(COMPARE_BITS, active_width)` bits of the step's active window
     (`dialog_gcd_compare_bits_for_step()`, with the PA9024 schedule off).
   - The comparator makes one carry CCX per bit and erases the carries by
     measurement (`hmr` plus `cz_if`), which costs no Toffoli. So two fewer
     bits save 2 Toffoli per call.
   - The calls come from the forward and reverse transcript passes of both GCD
     uses, on every step whose window is still at least 51 bits wide.
   - The measured 860 Toffoli per bit matches the per-bit rate implied by
     [`5ad23b1`](5ad23b1.md).
2. **`DIALOG_REROLL`: 4269 → 506906.** `build_builder()` emits this many
   `X;X` pairs on `tx[0]` right after the registers are declared. They are
   exact identities. The new value adds about a million X gates, but no
   Toffoli and no qubits. They only change the op-stream bytes and so the
   9,024 test inputs.
3. **`DIALOG_TAIL_NONCE`: 22000964 → 675.** The 48 `X;X` pairs at the end of
   `build_builder()`. They play the same role.

## Why it is still correct, and what it risks

- The truncated comparator gives the wrong branch when `u` and `v` agree on
  the top 49 bits of the window but differ lower down. That GCD step then
  subtracts in the wrong direction, and the GCD may not converge in 259
  steps. That gives a classical failure, or phase garbage when the
  transcript is uncomputed.
- Going from 51 to 49 bits makes a mis-decision about 4 times more likely
  per call.
- The pair `DIALOG_REROLL=506906`, `DIALOG_TAIL_NONCE=675` draws a clean
  set: 9,024 of 9,024 shots, with 0 classical, 0 phase and 0 ancilla
  failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is a narrower comparator, so the commit is filed as
comparator/width truncation. The two reroll values come with every
probabilistic change and are not a lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 66c6dac -- src/point_add`.
   - Do not start from the git parent `5ad23b1`. That is zuiris's tree, which
     has compare 46, apply clean compare 18, `KAL_FOLD_CARRY_TRUNC_W=23`,
     slope 1005 and the 1-bit band trims.
   - Diffing against the parent (76 lines) would wrongly show this commit
     undoing zuiris's comparator cuts and moving the slope, band trims and
     fold window back to the values in mpjunior92's tree.
   - Against `66c6dac`, `git diff --ignore-cr-at-eol 66c6dac c3cbcce -- src/point_add`
     is 6 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol c3cbcce -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*`, `DIALOG_*` or `SUB4_*` environment variables set, because they
   override the defaults. Expect:
   - 1320 qubits
   - 1,554,467 average Toffoli (rounded)
   - score 2,051,896,440
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=506906`, `DIALOG_TAIL_NONCE=675`
and an identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f4784cb..6c47a46 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31601,7 +31601,7 @@ fn configure_ecdsafail_submission_route() {
     // 52 -> 51: reclaimed on the 1320q base (the structural five-chunk-apply cut
     // reverted the GCD branch comparator to 52). The comparator never mis-decides
     // a branch at 51 on the verifier support; pure -T, peak-neutral.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "51");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "49");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
@@ -31798,7 +31798,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1010");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
-    set_default_env("DIALOG_REROLL", "4269");
+    set_default_env("DIALOG_REROLL", "506906");
     set_default_env("DIALOG_POST_SUB_REROLL", "503292");
     // Fiat-Shamir island for ACTIVE_ITERATIONS=393 + WIDTH_MARGIN=25 (1350q base).
     // The fixed-length 96-op identity tail (see the DIALOG_TAIL_NONCE block in
@@ -31826,7 +31826,7 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled again for the added WIDTH_SLOPE=1010 + band-late-trim=2 notches:
     // nonce=22000964 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1320q x 1,556,187 T = 2,054,166,840.
-    set_default_env("DIALOG_TAIL_NONCE", "22000964");
+    set_default_env("DIALOG_TAIL_NONCE", "675");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

