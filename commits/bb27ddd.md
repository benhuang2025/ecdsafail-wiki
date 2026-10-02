# bb27ddd — Narrow the dialog-GCD walk width envelope by two bits on the 1572-qubit tree (WIDTH_MARGIN 28 → 26)

| | |
| --- | --- |
| Contestant | anupsv |
| Date | 2026-06-02 |
| Submission | `e810f4e` |
| Commit | `bb27dddd2efd4b0bd54dfb561fca00a21a98fff9` |
| Result | 1572 qubits × 1,761,589 Toffoli = **2,769,217,908** |
| Base | `68e3653` (saucegodbased, git parent and frontier at the time): 1572 qubits × 1,770,897 Toffoli = 2,783,850,084 |
| Change vs base | qubits ±0, Toffoli −9,308, score −14,632,176 (leaderboard Δ −14,632,176) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the same lever as mpjunior92's [412312f](412312f.md), applied to the
new 1572-qubit tree and pushed one bit further. The dialog-GCD walk works on
the low `active_width(step)` bits of `u` and `v`, where the width is a
straight-line envelope plus a margin. The margin goes from 28 to 26, so 359 of
the 399 steps run 2 bits narrower. Each step-bit costs 3 Toffoli per walk, and
the comparator, which is capped by the width on late steps, loses 173 bits per
walk. Over the four walks that is 4 × (3 × 718 + 173) = 9,308 Toffoli.
Qubits are unchanged. The Fiat–Shamir reroll was rescanned from 41 to 20.

## What changed and why it saves Toffoli

Background on the walk is in [8316db1](8316db1.md), and the width envelope is
explained in [412312f](412312f.md).

- `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`:
  `DIALOG_GCD_WIDTH_MARGIN` default 28 → 26.
  - `dialog_gcd_tobitvector_active_width(step)` =
    `ceil_even(256 − 0.7075·step + margin)`, clamped to 256.
  - That width sets the `cswap` loop, the gated load `ccx(b0, u_i, gated_i)`,
    and the measured subtract or add body. Each is about 1 Toffoli per bit per
    step. It also caps the branch comparator width.
  - Per walk, the summed width goes from 56,930 to 56,212 bits (−718: every
    step after the first 40 or so, which are clamped at 256, loses 2 bits).
    The summed comparator width goes from 21,252 to 21,079 (−173), with this
    tree's comparator margin of 8.
  - 3 × 718 + 173 = 2,327 per walk, × 4 walks = 9,308, the measured drop.
- `DIALOG_REROLL` default 41 → 20: the count of identity `X;X` pairs at the
  start of `build()`. It only re-seeds the test inputs.

## Why it is still correct, and what it risks

The envelope is a fitted line, not a bound. Any input whose GCD values shrink
more slowly than `256 − 0.7075·step + 26` keeps live bits above the active
width. The swap and subtract then ignore those bits and the walk goes wrong.
Two bits less margin puts more inputs over the line than 412312f's one bit did.

A failure shows as a classical mismatch, usually with ancilla garbage from the
reverse walk. The shipped reroll 20 draws a test set with 0 classical, 0 phase
and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

The submission note gives the score as 2,769,218,508. The leaderboard value,
which 1572 × 1,761,589 confirms, is 2,769,217,908.

## Classification rationale

A narrower per-step register width is comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 68e3653 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 68e3653 bb27ddd -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol bb27ddd -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set. Expect:
   - 1572 qubits
   - 1,761,589 average Toffoli (rounded)
   - score 2,769,217,908
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL = 20` and an identical op
stream. Any other change needs a new reroll scan.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 78973c2..50948af 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -28760,7 +28760,7 @@ fn configure_ecdsafail_submission_route() {
     // co-tune the Fiat-Shamir reroll to land a clean 9024-shot island. Pure
     // Toffoli reduction (2447846 -> 2396158), peak-neutral at 1698.
     // (Validated 0/0/0 over 9024 via eval_circuit.)
-    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "28");
+    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "26");
     // Measured (Gidney) uncompute for the apply-phase modular subtract's raw
     // difference, mirroring the already-measured apply ADD. ~n Toffoli instead
     // of ~2n per call; peak-neutral (same carry lane the ADD already uses).
@@ -28773,7 +28773,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_HOST_GATED", "1");
     set_default_env("DIALOG_GCD_APPLY_WINDOW_BLOCKS", "2");
     // New op stream (windowed apply) needs its own clean Fiat-Shamir island.
-    set_default_env("DIALOG_REROLL", "41");
+    set_default_env("DIALOG_REROLL", "20");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

