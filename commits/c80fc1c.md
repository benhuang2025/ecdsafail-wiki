# c80fc1c — Narrow the dialog-GCD branch comparator from 51 to 50 bits

| | |
| --- | --- |
| Contestant | newjordan |
| Date | 2026-06-06 |
| Submission | `516a277` |
| Commit | `c80fc1cf3cfe9598fa0a82a7011fda20212feb1a` |
| Result | 1313 qubits × 1,515,772 Toffoli = **1,990,208,636** |
| Base | `974689f` (the author's previous submission, git parent and frontier at the time): 1313 qubits × 1,516,628 Toffoli = 1,991,332,564 |
| Change vs base | qubits ±0, Toffoli −856, score −1,123,928 (leaderboard Δ −1,123,928) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the next step of the same ladder as [`9906ec0`](9906ec0.md). The
dialog-GCD branch comparator, which picks each walk step's subtract
direction from the top bits of `u` and `v`, is capped at 50 bits instead of
51. The cap binds on the same 214 wide steps of each of the four walks, so
the saving is again 4 × 214 = 856 average Toffoli, at the same 1313 qubits.
The tail nonce was re-hunted.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_COMPARE_BITS`: 51 → 50.**
   - With `DIALOG_GCD_PA9024_COMPARE_SCHEDULE=0`,
     `dialog_gcd_compare_bits_for_step(step, active_width)` returns
     `min(COMPARE_BITS, active_width)`. That is the width of the truncated
     comparator `dialog_gcd_cmp_gt_truncated_into_width` (and its controlled
     form), which compares the top bits of `u` and `v`.
   - `active_width(step) = 256 − 1.014·step + 10`, rounded up to an even
     number. It is at least 52 on steps 0–213 and exactly 50 on step 214.
     So the cap moves from 51 to 50 on steps 0–213. On step 214 the width
     was already 50, so nothing changes there.
   - 214 steps × 4 walks (forward and reverse walk of the two divisions)
     × 1 Toffoli = 856, which is exactly the measured saving.
2. **`DIALOG_TAIL_NONCE`: 44575002764 → 44825000439.**

## Why it is still correct, and what it risks

The comparator decides the wrong branch when `u` and `v` agree on all 50
compared top bits but differ below. The walk then follows the wrong branch
in the transcript, which gives a classical mismatch. One bit less roughly
doubles that per-step risk, which is still tiny on the wide steps. The new
nonce `44825000439` passed the author's remote prefilter and the trusted
evaluation: 9,024 of 9,024 shots, with 0 classical, 0 phase and 0 ancilla
failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

One comparator is narrowed by one bit, which is comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 974689f -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 974689f c80fc1c -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol c80fc1c -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*` or `DIALOG_*` environment variables set. Expect:
   - 1313 qubits
   - 1,515,772 average Toffoli (rounded)
   - score 1,990,208,636
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=44825000439` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 90ff7fb..507ad69 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -32735,7 +32735,7 @@ fn configure_ecdsafail_submission_route() {
     // Both-phase apply fold-fusion: spend comparator bits back to cb=52 (the
     // exact-screen zone) so the on-GPU island finder lands a clean Fiat-Shamir
     // nonce; the fold-fusion's -25k Toffoli keeps the score well under 2B.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "51");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "50");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "23");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_K2", "1");
@@ -32971,7 +32971,7 @@ fn configure_ecdsafail_submission_route() {
     // 1000001157 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1313q x 1,535,885 T = 2,016,617,005 (official ecdsafail run).
     set_default_env("DIALOG_GCD_SELECTED_BODY_NOCIN", "1");
-    set_default_env("DIALOG_TAIL_NONCE", "44575002764");
+    set_default_env("DIALOG_TAIL_NONCE", "44825000439");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

