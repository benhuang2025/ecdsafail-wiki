# c6cc74e — Narrow the K=2 dialog-GCD width envelope by one more bit (WIDTH_MARGIN 18 → 17)

| | |
| --- | --- |
| Contestant | robertkodra |
| Date | 2026-06-05 |
| Submission | `55d5052` |
| Commit | `c6cc74ee607a4445d9a02b5e06a608bf01585d01` |
| Result | 1390 qubits × 1,598,967 Toffoli = **2,222,564,130** |
| Base | `01260e8` (newjordan, git parent and frontier at the time): 1390 qubits × 1,602,999 Toffoli = 2,228,168,610 |
| Change vs base | qubits ±0, Toffoli −4,032, score −5,604,480 (leaderboard Δ −5,604,480) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the same lever as [01260e8](01260e8.md), one bit further. The
dialog-GCD walk's width envelope `256 − 0.95·step + margin` loses one more bit
of margin, going from 18 to 17. The width is rounded up to an even number, so
120 of the 259 steps get 2 bits narrower and the rest do not change. Each
step-bit costs 4 Toffoli in the K=2 walk, and the comparator loses a few
capped bits. The saving is 4,032 Toffoli, exactly what the width formula
predicts. Qubits are unchanged. A new tail nonce was hunted.

## What changed and why it saves Toffoli

- `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`:
  - default `DIALOG_GCD_WIDTH_MARGIN`: 18 → 17;
  - default `DIALOG_TAIL_NONCE`: 141744616447148 → 177449118471529.
- `dialog_gcd_tobitvector_active_width(step)` sets the width of four per-step
  loops in each walk, each about 1 Toffoli per bit:
  - the branch `cswap`;
  - the gated load;
  - the subtract or add body;
  - the K=2 conditional-shift `cswap` cascade.

  It also caps the branch comparator, at `min(74, active_width)`. See
  [01260e8](01260e8.md) for the full list.
- **The count.** Replaying the formula over the 259 steps, the summed width
  per walk goes from 39,280 to 39,040 bits (−240, i.e. 120 steps × 2). The
  summed comparator width goes from 18,118 to 18,070 (−48). Per walk that is
  4 × 240 + 48 = 1,008 Toffoli. The four walks give 4,032, the measured drop.
- The runway transcript allocation stays at 480 bits. The peak is set by the
  apply-phase chunked add, so it stays at 1390.

## Why it is still correct, and what it risks

The envelope is a statistical fit. An input whose `u` or `v` still has a live
bit above `active_width` loses it, and the GCD walk goes wrong. That shows as
a classical mismatch and ancilla garbage, because the reverse walk no longer
restores `u` and `v`. One bit less margin makes such inputs more common.

The new nonce `177449118471529` was found with a tail-nonce search over
9,024-shot candidates. It draws a test set with 0 classical, 0 phase and
0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

A narrower per-step register width is comparator/width truncation. There is
no other change.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 01260e8 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 01260e8 c6cc74e -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol c6cc74e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set, because
   `set_default_env` only fills in unset variables. Expect:
   - 1390 qubits
   - 1,598,967 average Toffoli (rounded)
   - score 2,222,564,130
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=177449118471529` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 78725fd..d541a51 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31321,7 +31321,7 @@ fn configure_ecdsafail_submission_route() {
     // PA9024_COMPARE_SCHEDULE_MARGIN 8->7: -5,576 executed Toffoli at the 1434
     // peak. Re-rolled Fiat-Shamir island lands clean (0/0/0 over 9024) at
     // DIALOG_REROLL=0 / DIALOG_POST_SUB_REROLL=44. 1434q x 1,733,573 T = 2,485,943,682.
-    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "18");
+    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "17");
     // Measured (Gidney) uncompute for the apply-phase modular subtract's raw
     // difference, mirroring the already-measured apply ADD. ~n Toffoli instead
     // of ~2n per call; peak-neutral (same carry lane the ADD already uses).
@@ -31437,7 +31437,7 @@ fn configure_ecdsafail_submission_route() {
     // clean island: validated 0/0/0 over all 9024 shots at 1350q x 1,763,987 T.
     // Fiat-Shamir island for the K=2 apply rebalance above: 0/0/0 over all
     // 9024 shots at 1390q x 1,630,487 T.
-    set_default_env("DIALOG_TAIL_NONCE", "141744616447148");
+    set_default_env("DIALOG_TAIL_NONCE", "177449118471529");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

