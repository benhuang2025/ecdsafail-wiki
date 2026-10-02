# 21fbfc7 — Move the last apply-adder chunk boundary from bit 200 to 190, shortening the boundary-clear comparator

| | |
| --- | --- |
| Contestant | robertkodra |
| Date | 2026-06-05 |
| Submission | `d77c0b2` |
| Commit | `21fbfc717c44ddb7a9efa2c582e5943f6c8bd6f8` |
| Result | 1320 qubits × 1,540,355 Toffoli = **2,033,268,600** |
| Base | `e4497a6` (the author's previous submission, git parent): 1320 qubits × 1,542,945 Toffoli = 2,036,687,400 |
| Change vs base | qubits ±0, Toffoli −2,590, score −3,418,800 (leaderboard Δ −3,418,800) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog-GCD apply adds or subtracts `x` into `y` once per GCD step. To keep
the qubit peak low, that 257-bit add is split into five chunks, and the carry
bits left at the chunk boundaries are cleared at the end by one shared
comparator over the low `cut4` bits. This commit moves the last boundary
`cut4` from 200 down to 190. The shared comparator becomes 10 bits shorter. The
final chunk becomes 10 bits wider, and its own internal half-way comparator
grows by 5 bits. The net is −5 Toffoli per apply call. There are 518 calls
(259 adds and 259 subtracts), so the run saves 2,590 Toffoli. The change is
exact, and the 1320-qubit peak is set elsewhere and does not move. The tail
nonce was re-hunted for the new op stream.

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_APPLY_CHUNKED_F_CUT4`: 200 → 190.**
   - The apply runs `dialog_gcd_cmod_add_materialized_pseudomersenne_chunked`
     (forward apply, `y += b0·x`) and
     `dialog_gcd_cmod_sub_materialized_pseudomersenne_chunked` (reverse apply,
     `y −= b0·x`) once per GCD step, 259 steps each.
   - With `DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS=5` and `..._CUSTOM5=1`,
     `dialog_gcd_chunk_hi` cuts the 257-bit extended accumulator at
     `CUT, CUT2, CUT3, CUT4` = 50, 100, 150, 200 (now 190).
   - `dialog_gcd_add_ctrl_chunked_low_to_ext` adds chunk by chunk. For each
     chunk it loads `ctrl·x[lo..hi]` into a temporary register with CCX gates,
     ripples a Cuccaro adder that ends in a boundary carry bit `cout`, and
     clears the temporary by measurement. The next chunk takes `cout` as its
     carry-in. The four `cout` bits stay dirty.
   - After the last chunk, all boundary carries are cleared in one sweep by
     `ccx_cmp_lt_into_fast_prefix_targets_split`. It recomputes
     `acc[..p] < x[..p]`, which is the carry out of position `p`, as a single
     ripple over the low `p = CUT4` bits, and XORs each prefix result into the
     matching `cout`. The ripple costs one Toffoli per bit, and its carries are
     erased by measurement (`hmr` + `cz_if`). See
     [measurement-uncompute](../concepts/measurement-uncompute.md).
     `DIALOG_GCD_APPLY_BOUNDARY_SPLIT=100` splits that ripple at bit 100, but
     the length is still `p`.
   - So moving `CUT4` from 200 to 190 makes the boundary-clear ripple 10 bits
     shorter: −10 Toffoli per call.
   - The final chunk, `[CUT4, 257)`, grows from 57 to 67 bits. With
     `DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS=2` it runs
     `cuccaro_add_fast_windowed_low_to_ext`, which splits it in half and clears
     its own half-way carry with `cmp_lt_into_fast_with_cin` over the lower
     half: ⌊57/2⌋ = 28 bits before, ⌊67/2⌋ = 33 bits now. That is +5 Toffoli per
     call.
   - The total ripple and load length over all chunks is unchanged.
   - Net −5 per call × 518 calls = −2,590, the measured saving.
   - The wider final chunk holds 10 more loaded bits at once, but the apply
     teardown is not the binding phase, so the peak stays 1320 (see
     [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md)).
2. **`DIALOG_TAIL_NONCE`: 148111066097918 → 275637277737190.** This reseeds
   the 9,024 Fiat–Shamir test inputs and does not change the arithmetic. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

The change is exact. Any cut positions give the same sum, because the prefix
comparator recomputes each boundary carry over the full low prefix rather than
a truncated window. The code comment says the same: "The chunked sub/add is
EXACT regardless of F_CUT". No new hard inputs appear. The nonce was re-hunted
only because any op-stream change re-rolls the test set, and the inherited
residual failures (from the GCD width and comparator truncations) may land in
it. A broken boundary clear would show as ancilla garbage on the `cout` wires.
The submission note reports 0 classical, 0 phase and 0 ancilla failures over
all 9,024 shots.

## Classification rationale

The census files this as fold/carry truncation. The diff does not truncate
anything. It moves an exact chunk boundary so that the shared boundary-clear
comparator is shorter, at a smaller cost inside the final chunk. A better label
would be an exact adder chunk rebalancing (Arithmetic restructuring, or
comparator/width with the note that the width cut is exact). The published
label is kept in the header.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout e4497a6 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol e4497a6 21fbfc7 -- src/point_add` is 4 lines in
   1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 21fbfc7 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set, because `set_default_env`
   keeps any value already in the environment. Expect:
   - 1320 qubits
   - 1,540,355 average Toffoli (rounded)
   - score 2,033,268,600
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=275637277737190` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ed4112b..6c6d2f9 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31833,7 +31833,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "50");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "100");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT3", "150");
-    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT4", "200");
+    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT4", "190");
     // WIDTH_SLOPE tightening: the per-step GCD width envelope shrink rate
     // (ideal = N - step*SLOPE + MARGIN) was left at the default 0.7075 by the
     // whole frontier lineage; only the constant MARGIN was ever tuned. The
@@ -31866,7 +31866,7 @@ fn configure_ecdsafail_submission_route() {
     // 1390q x 1,518,179 T = 2,110,268,810.
     // Final-window W2 island: validated 0/0/0 over all 9024 shots at
     // 1320q x 1,545,787 T = 2,040,438,840.
-    set_default_env("DIALOG_TAIL_NONCE", "148111066097918");
+    set_default_env("DIALOG_TAIL_NONCE", "275637277737190");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

