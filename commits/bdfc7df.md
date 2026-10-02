# bdfc7df — Lower the dialog-GCD width-envelope margin from 26 to 25 bits, with a new reroll pair

| | |
| --- | --- |
| Contestant | aburan28 |
| Date | 2026-06-03 |
| Submission | `e7a1da2` |
| Commit | `bdfc7df13b0e86407cd4394f4c5c92b60548afb5` |
| Result | 1434 qubits × 1,723,493 Toffoli = **2,471,488,962** |
| Base | `2bd707e` (the author's previous submission, git grandparent): 1434 qubits × 1,728,069 Toffoli = 2,478,050,946 |
| Change vs base | qubits ±0, Toffoli −4,576, score −6,561,984 |
| Leaderboard Δ | −5,019,000, measured against the frontier at the time, `e75ea5c` (10d9e, 1434 × 1,726,993 = 2,476,507,962), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog binary GCD does not run its 395 steps at the full 256-bit width.
Each step works only on the low `active_width(step)` bits of `u` and `v`, a
linear envelope that shrinks as the GCD converges, plus a safety margin. This
commit lowers that margin from 26 to 25 bits. Because the width is rounded up
to an even number, 178 of the 395 steps lose 2 bits, and every controlled
swap and controlled subtract in those steps gets cheaper. That saves 4,576
average Toffoli at the unchanged 1434-qubit peak. The reroll pair was
re-searched to find a clean test set for the new op stream.

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`:

1. **`DIALOG_GCD_WIDTH_MARGIN`: 26 → 25.**
   - It is read by `dialog_gcd_width_margin()` and used by
     `dialog_gcd_tobitvector_active_width(step)`:
     `ideal = 256 − step × 0.7075 + margin`, rounded **up** to an even number
     and clamped to [1, 256]. 0.7075 (`DIALOG_GCD_WIDTH_SLOPE_X1000` unset) is
     the empirical per-step shrink rate of `max(bitlen(u), bitlen(v))`.
   - Every transcript step slices `u_active = u[..active_width]` and
     `v_active = v[..active_width]`. The controlled swap (one CCX per bit), the
     gated load and the controlled subtract
     (`dialog_gcd_controlled_sub_selected`) all run over that width. The branch
     comparator is capped by `DIALOG_GCD_COMPARE_BITS` and the per-step
     schedule, but also by `active_width`, so on the 38 late steps (321 to
     392) where the width binds it loses 2 bits as well: 76 compare bits.
   - Early steps clamp at 256, so the peak, which is set elsewhere, does not
     move.
   - With 395 active steps (`DIALOG_GCD_ACTIVE_ITERATIONS=395`), the summed
     per-step width goes from 56,202 to 55,846 bits: 178 steps lose 2 bits,
     the rest lose none because of the even rounding. 4,576 is exactly
     12 × 356 + 4 × 76. That fits about 3 Toffoli per removed bit (swap,
     gated load, subtract carry) plus one per removed compare bit, in each of
     the four transcript passes: forward and reverse, for each of the two GCD
     calls.
2. **Reroll pair: `DIALOG_REROLL` 694534 → 643155,
   `DIALOG_POST_SUB_REROLL` 579110 → 208158.** These are counts of identity
   `X;X` pairs emitted before and after the input subtraction. They change the
   op-stream hash, and so the 9,024 Fiat–Shamir test inputs, without changing
   what the circuit computes. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

The width truncation is probabilistic. It assumes that at step `s` both `u`
and `v` fit in `active_width(s)` bits. An input whose GCD converges more
slowly than the envelope has a nonzero bit above the cut. The swap and
subtract then ignore that bit, the transcript decisions go wrong, and the run
shows classical failures (and phase or ancilla garbage when the reverse pass
no longer mirrors the forward one). One bit less margin halves the headroom,
so λ (the expected number of failing shots per 9,024-shot draw) rises.

The shipped pair (643155, 208158) draws a clean set: the author reports 0
classical, 0 phase and 0 ancilla failures over all 9,024 shots. See
[comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)
and [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) for the dialog GCD
lineage.

## Classification rationale

The only circuit change narrows the registers each GCD step operates on,
which is comparator/width truncation. The reroll change is the usual
companion of any circuit change in this era.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 2bd707e -- src/point_add`.
   - The git parent is `e75ea5c` (10d9e). It set `DIALOG_GCD_COMPARE_BITS`
     56 → 55 with its own reroll pair and added
     `src/point_add/memory/2026-06-03-island-search-tool-and-landability-wall.md`.
     This commit was built on `2bd707e` and keeps 56, so diffing against the
     parent (134 lines) would wrongly show a revert of the comparator to 56
     and the deletion of that 122-line memo.
   - `git diff --ignore-cr-at-eol 2bd707e bdfc7df -- src/point_add` is 6
     lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol bdfc7df -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` keeps any
   value already in the environment. Expect:
   - 1434 qubits
   - 1,723,493 average Toffoli (rounded)
   - score 2,471,488,962
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=643155`,
`DIALOG_POST_SUB_REROLL=208158` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 7b2694e..249204b 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -29989,7 +29989,7 @@ fn configure_ecdsafail_submission_route() {
     // PA9024_COMPARE_SCHEDULE_MARGIN 8->7: -5,576 executed Toffoli at the 1434
     // peak. Re-rolled Fiat-Shamir island lands clean (0/0/0 over 9024) at
     // DIALOG_REROLL=0 / DIALOG_POST_SUB_REROLL=44. 1434q x 1,733,573 T = 2,485,943,682.
-    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "26");
+    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "25");
     // Measured (Gidney) uncompute for the apply-phase modular subtract's raw
     // difference, mirroring the already-measured apply ADD. ~n Toffoli instead
     // of ~2n per call; peak-neutral (same carry lane the ADD already uses).
@@ -30079,8 +30079,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "130");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "694534");
-    set_default_env("DIALOG_POST_SUB_REROLL", "579110");
+    set_default_env("DIALOG_REROLL", "643155");
+    set_default_env("DIALOG_POST_SUB_REROLL", "208158");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

