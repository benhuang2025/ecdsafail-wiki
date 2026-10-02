# f50ae3b — Narrow the dialog-GCD apply-phase overflow/underflow clean compare from 20 to 19 bits

| | |
| --- | --- |
| Contestant | gnuchev |
| Date | 2026-06-14 |
| Submission | `dc6724b` |
| Commit | `f50ae3b867d27b41ac4d6408a76649ecfe5e6f34` |
| Result | 1170 qubits × 1,434,496 Toffoli = **1,678,360,320** |
| Base | `6878ef8` (git parent, the author's previous submission): 1170 qubits × 1,434,726 Toffoli = 1,678,629,420 |
| Change vs base | qubits ±0, Toffoli −230, score −269,100 (leaderboard Δ −269,100) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The circuit is the 1170-qubit dialog-GCD route. Its inversion records the GCD
steps and then "applies" them to a coefficient register with one controlled
modular add or subtract per step. Each such add leaves an overflow (or
underflow) flag that is cleaned with a comparator that only looks at the top
bits of the two registers. This commit makes the default width of that
comparator 19 bits instead of 20. That saves 230 average Toffoli at the same
1170 qubits. The tail nonce was re-hunted.

The submission note describes this as stacking two tightenings. The other one,
the square-row cleanup at 18 bits, was already in the base
[`6878ef8`](6878ef8.md); this commit only adds the apply-side bit.

## What changed and why it saves Toffoli

- `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`:
  `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` default `"20"` → `"19"`. This first
  block of `set_default_env` calls wins over the later fallback block (which
  also says `"19"`), because `set_default_env` only sets unset variables.
- How the knob is used:
  - `dialog_gcd_apply_clean_compare_bits()` (`rounds/dialog/config.rs`) returns
    it, falling back to `DIALOG_GCD_COMPARE_BITS` if it is unset.
  - `dialog_gcd_special_clean_compare_bits_from_env(step, env)`
    (`rounds/dialog/mod.rs`) uses it as the default for every apply step that
    has no per-step override. The overrides are
    `DIALOG_GCD_SPECIAL_OVERFLOW_CLEAN_STEP_BITS` (6 steps at 21 to 23 bits)
    and `DIALOG_GCD_SPECIAL_UNDERFLOW_CLEAN_STEP_BITS` (4 steps at 21 to 22).
  - The apply phase does a controlled pseudo-Mersenne modular add of `a` into
    `acc`: a raw add into `acc` extended by one overflow bit `acc_ovf`, then a
    fold that adds `c = 2^256 − p` to the low limbs when `acc_ovf` is set. The
    flag must then be cleared. It equals "the reduced `acc` is less than `a`",
    and the circuit tests that only on the top `k` bits:
    `compare_start = N − k`, comparing `acc[compare_start..]` with
    `a[compare_start..]`. The subtract path
    (`dialog_gcd_clean_truncated_underflow_with_borrowed`) does the mirror
    test with `a`'s top bits complemented.
  - With `DIALOG_GCD_SPECIAL_CLEAN_CONDITIONAL_REPLAY=1` (set in the fallback
    block), the flag is measured out with `hmr` and the comparison runs in
    `dialog_gcd_cmp_lt_phase_conditioned_hosted` only when the measurement bit
    is 1, as a phase repair. See
    [measurement-uncompute](../concepts/measurement-uncompute.md).
- One bit less removes about one Toffoli from every apply step that uses the
  default, forward and reverse. The submission note counts 506 emitted
  Toffoli. Because the repair runs on about half the shots, the measured
  average saving is 230. See
  [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
- `DIALOG_TAIL_NONCE` default: `"38047539020"` → `"26008558798"`.

## Why it is still correct, and what it risks

The modular add and its fold are unchanged and exact. Only the flag cleanup is
approximate. The truncated compare gives the right flag unless the top 19 bits
of `acc` and `a` are equal, which happens with probability about 2^-19 per
step for random values; the previous 20 bits had half that rate. When it is
wrong, the phase repair after the `hmr` is wrong, so the failure shows up in
the phase channel (the submission note calls the class
`ApplyCleanupMismatch`).

The new nonce `26008558798` draws a test set that avoids those inputs and the
square-cleanup inputs of the base: 0 classical, 0 phase and 0 ancilla failures
over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is a comparator one bit narrower, which is
comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6878ef8 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 6878ef8 f50ae3b -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol f50ae3b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `SQUARE_*` or `KAL_*` environment variables set. Expect:
   - 1170 qubits
   - 1,434,496 average Toffoli (1,434,495.783 before rounding)
   - score 1,678,360,320
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `26008558798` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index d06e385..e92efae 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1014,7 +1014,7 @@ fn configure_ecdsafail_submission_route() {
         "DIALOG_GCD_APPLY_CHUNKED_F_CUTS",
         "17,34,50,66,81,96,110,124,137,150,163,175,187,198,209,219,229,238,247",
     );
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
     set_default_env("DIALOG_GCD_APPLY_IMPLICIT_HIGH_ZERO", "1");
     set_default_env("DIALOG_GCD_BINDER_NOTCH_EXTRA", "3");
     set_default_env("DIALOG_GCD_BINDER_NOTCH_MAP", "11:1,12:1,13:1");
@@ -1084,7 +1084,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_TOBITVECTOR_CSWAP_BODY_TRIM", "0");
     set_default_env("DIALOG_GCD_WIDTH_MARGIN", "10");
     set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1015");
-    set_default_env("DIALOG_TAIL_NONCE", "38047539020");
+    set_default_env("DIALOG_TAIL_NONCE", "26008558798");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "19");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("SQUARE_ROW_MAX_SEG", "143");
```

