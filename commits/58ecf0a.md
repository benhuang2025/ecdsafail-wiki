# 58ecf0a — Steepen the dialog-GCD width envelope one more notch (slope 1.011 → 1.012)

| | |
| --- | --- |
| Contestant | 10d9e |
| Date | 2026-06-05 |
| Submission | `819d74a` |
| Commit | `58ecf0aa9666fbcf5bf57808f7b467df8b7eb3d3` |
| Result | 1320 qubits × 1,534,277 Toffoli = **2,025,245,640** |
| Base | `351a0d0` (the author's previous submission, git parent): 1320 qubits × 1,534,757 Toffoli = 2,025,879,240 |
| Change vs base | qubits ±0, Toffoli −480, score −633,600 (leaderboard Δ −633,600) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the same lever as [`ec0fa98`](ec0fa98.md), one more notch. The
per-step GCD width envelope now shrinks by 1.012 bits per step instead of
1.011. Over the 259 steps, the summed active width drops by 28 bits and the
summed comparator width by 8 bits. Over the four transcript passes, at about
4 Toffoli per width bit and 1 per comparator bit, that is 4 × (4 × 28 + 8) =
480 average Toffoli, the measured saving. Qubits stay at 1320. The tail nonce
was re-hunted.

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 1011 → 1012.**
   - `dialog_gcd_tobitvector_active_width(step)` =
     `ceil_even(256 − step × slope + 10)`, clamped to [1, 256]. Every step's
     conditional swap, gated load, controlled subtract and K2 second-shift
     cascade runs on `u[..aw]`, `v[..aw]`. That is about 4 Toffoli per bit per
     pass (see [`ec0fa98`](ec0fa98.md)).
   - The branch comparator is `min(46, aw)` bits, so it shrinks on the late
     steps too.
   - Σ aw goes 35,306 → 35,278 (−28). Σ comparator width goes 11,114 → 11,106
     (−8). Over four passes (forward and reverse, two GCD factors) that is
     4 × (4 × 28 + 8) = 480.
   - Because of the rounding up to an even width, only some steps lose 2 bits.
     The early steps clamp at 256, so the peak does not move.
2. **`DIALOG_TAIL_NONCE`: 20397 → 10429.** This reseeds the 9,024 test
   inputs. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

The comment calls it "value-exact". It is exact only for inputs whose GCD
converges inside the tighter envelope. A slower input keeps a set bit above
`aw`, which the swap and subtract ignore. The transcript then goes wrong, and
the run shows a classical failure plus phase or ancilla garbage. λ rises a
little. The shipped nonce 10429 draws a clean set, with 0 classical, 0 phase
and 0 ancilla failures over all 9,024 shots per the commit comment.

## Classification rationale

The only circuit change narrows the per-step register widths: comparator/width
truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 351a0d0 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 351a0d0 58ecf0a -- src/point_add` is 9 lines in
   1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 58ecf0a -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set, because `set_default_env`
   keeps any value already in the environment. Expect:
   - 1320 qubits
   - 1,534,277 average Toffoli (rounded)
   - score 2,025,245,640
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=10429` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 88194ff..9a3e098 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31866,7 +31866,9 @@ fn configure_ecdsafail_submission_route() {
     // bit-exact validate (island_search_prefilter), confirmed via official run.
     // 1009 -> 1011: one further notch, stacked under one shared island with the
     // KAL_FOLD 24->22 and APPLY_CLEAN_COMPARE_BITS 20->19 re-tightenings above.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1011");
+    // 1011 -> 1012: one more width-envelope notch, stacked on COMPARE_BITS=46
+    // under the nonce-10429 island below. Value-exact, peak-neutral at 1320q.
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1012");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
     set_default_env("DIALOG_REROLL", "4269");
@@ -31896,7 +31898,10 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled again for the stacked COMPARE_BITS 47->46 re-tightening: nonce
     // 20397 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1320q x 1,534,757 T = 2,025,879,240.
-    set_default_env("DIALOG_TAIL_NONCE", "20397");
+    // Re-rolled again for the stacked WIDTH_SLOPE 1011->1012 notch: nonce 10429
+    // lands a clean island, validated 0/0/0 over all 9024 shots at
+    // 1320q x 1,534,277 T = 2,025,245,640.
+    set_default_env("DIALOG_TAIL_NONCE", "10429");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

