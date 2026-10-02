# da55bbb — Narrow the apply-phase Solinas fold carry window from 21 to 20 bits

| | |
| --- | --- |
| Contestant | SamrendraS |
| Date | 2026-06-08 |
| Submission | `451a80f` |
| Commit | `da55bbbd6e5a8d6ea998bd83427c18c9f8d8cc41` |
| Result | 1300 qubits × 1,403,524 Toffoli = **1,824,581,200** |
| Base | `bfd3fa6` (BitWonka, git parent and frontier at the time): 1300 qubits × 1,404,058 Toffoli = 1,825,275,400 |
| Change vs base | qubits ±0, Toffoli −534, score −694,200 (leaderboard Δ −694,200) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Each dialog-GCD apply step does a controlled modular add or subtract. When
the raw 256-bit result overflows, it is corrected by adding the constant
`c = 2^256 − p = 2^32 + 977` into the low bits (the Solinas fold). That
constant add has a carry chain, and the route truncates it a fixed number of
bits above the constant's top set bit, bit 32. This commit cuts that window
from 21 to 20 bits, which removes one carry CCX from every fold: 516 emitted
Toffoli over the 2 × 258 apply calls. The average executed Toffoli fell by
534. The extra 18 is draw-to-draw variation of the shot-dependent
(conditioned) Toffoli under the new nonce. Qubits are unchanged.

## What changed and why it saves Toffoli

All changes are in `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`.

1. **`KAL_FOLD_CARRY_TRUNC_W`: 21 → 20.**
   - Read by `fold_carry_trunc_window()` in `arith/const_arith.rs`. When it
     is set, the overflow fold of
     `dialog_gcd_cmod_add_materialized_pseudomersenne_chunked` calls
     `cadd_nbit_const_direct_trunc_fast(acc[..73], c, acc_ovf, w)`. The
     subtract twin calls `csub_nbit_const_direct_trunc_fast`. Here
     `DIALOG_GCD_SPECIAL_ADD_LSBS = 73`.
   - That adder computes the carries of `acc + acc_ovf·c` only up to
     position `last = min(n − 2, hi + w)`, where `hi = 32` is the highest set
     bit of `c`. Carries above `last` are treated as 0. The carries are then
     erased by measurement with `cz_if` fixes, at no Toffoli cost.
   - Above bit 32 the constant has no set bits, so each carry position costs
     one CCX, `carry_{i+1} = acc_i ∧ carry_i`. Lowering `w` by one removes
     one position: the carry out of bit 53 (into bit 54,
     `carries[53]`) is no longer computed. That is one CCX per fold,
     and 2 × 258 = 516 per run. See
     [modular-fold](../concepts/modular-fold.md).
2. **`DIALOG_TAIL_NONCE`: 9400002898194 → 9831976.** The old nonce failed
   on the tighter fold. The author found the new one with a GPU island
   filter and confirmed it with the trusted evaluator.

## Why it is still correct, and what it risks

The truncation is probabilistic. A carry that enters bit 33 keeps
propagating only through a run of 1 bits in `acc`. Dropping the carry out
of bit 53 gives a wrong sum only when acc bits 33..53 are all 1 and a carry
arrives, which is roughly a 2^-21 event per fold, about twice as likely as at 21
bits. The route comment calls the dropped carries "0 on the reachable
support" and says residual failures are dodged by the nonce. A wrong fold
corrupts the apply register, which shows up as a classical mismatch, and
usually as ancilla garbage when the overflow clean then misfires.

The shipped nonce `9831976` draws a test set with 0 classical, 0 phase and
0 ancilla failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

A one-bit narrowing of a truncated carry window is comparator/width
truncation. Strength Reduction → solinas / NAF fold was the runner-up,
because the window belongs to the Solinas fold, but the fold's structure
does not change.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout bfd3fa6 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol bfd3fa6 da55bbb -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol da55bbb -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set. Expect:
   - 1300 qubits
   - 1,403,524 average Toffoli (1,403,523.712 before rounding)
   - score 1,824,581,200
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9831976` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a027984..c207663 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1050,7 +1050,7 @@ fn configure_ecdsafail_submission_route() {
     // been left loose). Value-exact on the reachable support (the dropped fold
     // carry bits are 0 there); residual failures are pure Fiat-Shamir, dodged by
     // the shared re-rolled tail nonce below.
-    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "21");
+    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "20");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
     set_default_env("DIALOG_GCD_ROUND763_COMPRESS_LEVER", "1");
     set_default_env("DIALOG_GCD_MEASURED_UNDERFLOW_GATE", "1");
@@ -1396,7 +1396,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "9400002898194");
+    set_default_env("DIALOG_TAIL_NONCE", "9831976");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
```

