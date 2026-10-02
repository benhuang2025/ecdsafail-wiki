# a5e8bdf — Narrow the dialog-GCD branch comparator from 47 to 46 bits on the 1285-qubit route

| | |
| --- | --- |
| Contestant | runeape-sats |
| Date | 2026-06-06 |
| Submission | `287c73c` |
| Commit | `a5e8bdfd7e7c034ed67bc470ca2e26259a76236a` |
| Result | 1285 qubits × 1,538,787 Toffoli = **1,977,341,295** |
| Base | `571e67c` (the author's previous submission): 1285 qubits × 1,539,655 Toffoli = 1,978,456,675 |
| Change vs base | qubits ±0, Toffoli −868, score −1,115,380 |
| Leaderboard Δ | −288,051, measured against the frontier at the time, `ebbe44e` (zuiris, 1309 × 1,510,794 = 1,977,629,346), which is **not** this commit's base |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The author takes their own 1285-qubit route [`571e67c`](571e67c.md) and
narrows the dialog-GCD branch comparator by one bit, from 47 to 46. The width
envelope is at least 48 bits on 217 of the 258 walk steps, so the cap binds on
those 217 steps. Over the four walks that saves 4 × 217 = 868 Toffoli, which
matches the measured saving exactly. Qubits are unchanged. The tail nonce was
re-hunted with the author's CUDA K=2 screen.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_COMPARE_BITS`: 47 → 46.**
   - With `DIALOG_GCD_PA9024_COMPARE_SCHEDULE=0`, each walk step compares
     `min(cap, active_width)` top bits of `u` and `v`
     (`dialog_gcd_compare_bits_for_step`). The step uses that comparison to
     choose its branch.
   - On this tree `active_width(step) = 256 − 1.014·step + 10`, rounded up to
     an even number, over 258 steps. The width is at least 48 on steps 0–216,
     so on those 217 steps the comparator gets one bit narrower.
   - That is 217 × 4 walks (the forward and reverse walk of both divisions)
     = 868 Toffoli, exactly the measured saving.
2. **`DIALOG_TAIL_NONCE`: 393525 → 1027238.** The comment above the pin is
   updated to match.

## Why it is still correct, and what it risks

The comparator chooses the wrong branch when `u` and `v` agree on all 46
compared top bits. The walk then records and replays the wrong decision,
which gives a classical mismatch. One bit less roughly doubles that per-step
risk. The new nonce `1027238` draws a clean test set: 9,024 of 9,024 shots,
with 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label is Register and Scratch Allocation → ancilla-lifetime /
venting, which is the label of the base `571e67c`. This commit's diff,
though, only narrows the GCD branch comparator by one bit and changes the
nonce. No allocation changes, and the qubits stay at 1285. The diff
points to Dead-Code and Redundancy Elimination → comparator/width
truncation instead, the same label as zuiris's identical-type cut
[`ebbe44e`](ebbe44e.md) on the other line.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 571e67c -- src/point_add`.
   - Do not start from the git parent `ebbe44e`. That is zuiris's 1309-qubit
     tree, and it has also deleted 210 stray `._*` files.
   - Diffing against the parent would wrongly show this commit:
     - undoing zuiris's top-of-route overrides;
     - putting back odinfree's chunk cut 190 and the old knobs;
     - re-adding the 28-stage self-hosting and the vented square;
     - restoring those 210 files.
   - Against `571e67c`, `git diff --ignore-cr-at-eol 571e67c a5e8bdf -- src/point_add`
     is 10 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol a5e8bdf -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*`, `DIALOG_*` or `ROUND84_*` environment variables set. Expect:
   - 1285 qubits
   - 1,538,787 average Toffoli (rounded)
   - score 1,977,341,295
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=1027238` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a623cdb..550426f 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -32870,7 +32870,7 @@ fn configure_ecdsafail_submission_route() {
     // Both-phase apply fold-fusion: spend comparator bits back to cb=52 (the
     // exact-screen zone) so the on-GPU island finder lands a clean Fiat-Shamir
     // nonce; the fold-fusion's -25k Toffoli keeps the score well under 2B.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "47");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "46");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_K2", "1");
@@ -33114,15 +33114,15 @@ fn configure_ecdsafail_submission_route() {
     // round84 schoolbook x-tail uses dirty/vented Solinas reductions at the
     // final post-shift subtract and the shift-by-22 constant corrections. This
     // moves the GCD tobitvector and round84 binders down to the raw-PA 1285q
-    // floor. Comparator stack retuned to compare47/apply19; GPU K=2 scan found
-    // nonce 393525 and trusted eval validates 0/0/0 over 9024:
-    // 1285q x 1,539,655 T = 1,978,456,675.
+    // floor. Comparator stack retuned to compare46/apply19; GPU K=2 scan found
+    // nonce 1027238 and trusted eval validates 0/0/0 over 9024:
+    // 1285q x 1,538,787 T = 1,977,341,295.
     set_default_env("DIALOG_GCD_SELECTED_BODY_NOCIN", "1");
     set_default_env("DIALOG_GCD_SELECTED_BODY_GATE_SUFFIX_CARRIES", "28");
     set_default_env("ROUND84_XTAIL_SCHOOLBOOK_FINAL_SUB", "vent");
     set_default_env("ROUND84_XTAIL_SCHOOLBOOK_SHIFT_DIRTY", "1");
     set_default_env("ROUND84_XTAIL_SCHOOLBOOK_SHIFT_CONST_VENT", "1");
-    set_default_env("DIALOG_TAIL_NONCE", "393525");
+    set_default_env("DIALOG_TAIL_NONCE", "1027238");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

