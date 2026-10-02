# a4db9a5 — Deepen the GCD body binder notch at steps 8–10 from 2 to 3 bits (1298 → 1297 qubits)

| | |
| --- | --- |
| Contestant | SamrendraS |
| Date | 2026-06-08 |
| Submission | `e96bb06` |
| Commit | `a4db9a5c5c292cd029e42fc2ab560279ad4dd55e` |
| Result | 1297 qubits × 1,403,755 Toffoli = **1,820,670,235** |
| Base | `8983da8` (the author's previous submission, git parent and frontier at the time): 1298 qubits × 1,403,781 Toffoli = 1,822,107,738 |
| Change vs base | qubits −1, Toffoli −26, score −1,437,503 (leaderboard Δ −1,437,503) |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is not a nonce-only change. Besides the new nonce, it raises
`DIALOG_GCD_BINDER_NOTCH_EXTRA` from 2 to 3. The dialog-GCD walk body at
steps 8, 9 and 10 therefore drops 3 high bits instead of 2.

The binder notches started at [a5a590a](a5a590a.md), and
[8983da8](8983da8.md) lowered the other binders to 1298. Each bit of
notch shrinks the body's composite scratch at that step, and the peak falls
from 1298 to 1297. The narrower bodies also save about 2 Toffoli per body:
−24 emitted, −26 measured. According to the author, the peak is now set by
the walk's shift and reverse-add phases at 1297, so a deeper notch would not
help.

## What changed and why it saves qubits

All changes are in `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`.

1. **`DIALOG_GCD_BINDER_NOTCH_EXTRA`: 2 → 3**. It applies to every step in
   `DIALOG_GCD_BINDER_NOTCH_STEPS = 8,9,10`.
   - `dialog_gcd_body_carry_trunc_width(active_width, step)` returns
     `active_width − w`. `active_width` is 256 at these steps, and the band
     trims are 0 for steps 0–9 and 3 for steps 10–19. With the new value the
     bodies are:
     - step 8: 254 → 253 bits;
     - step 9: 254 → 253 bits;
     - step 10: 251 → 250 bits.
   - The composite scratch is `2·body_len − 1` wires. According to the code
     comment, a body trimmed by one more bit asks for one fewer owned
     scratch wire, so these binder steps drop by 1 to 1297. See
     [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
   - Toffoli: one fewer gated-load CCX and one fewer carry CCX per body,
     over 3 steps × 4 walks: −24 emitted. The measured −26 includes draw
     variance in the conditioned Toffoli.
2. **`DIALOG_TAIL_NONCE`: 47863838 → 44846255.**

`DIALOG_GCD_BINDER_NOTCH_MAP=13:1`, `F_CUT4=190` and the scratch-borrow
levers of [8983da8](8983da8.md) are unchanged.

## Why it is still correct, and what it risks

A deeper notch is a riskier truncation. The body now ignores 3 high bits of
`u` and `v` at steps 8–10. If an input still has a set bit, or a carry, in
those positions, the body gives a wrong result. The classical filter's
`BodyTrimMismatch` check (added in [8983da8](8983da8.md)) screens nonces for
exactly this. A failure shows as a classical mismatch and ancilla garbage.

The shipped nonce `44846255` draws a test set with 0 classical, 0 phase and
0 ancilla failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label, nonce/island reroll, does not fit. The diff changes a
circuit knob, the notch depth, which lowers the peak by one qubit and
changes the emitted op stream. Like the other binder-notch commits
([a5a590a](a5a590a.md), [73f4f48](73f4f48.md), [f3820d0](f3820d0.md)), it
belongs under Dead-Code and Redundancy Elimination → comparator/width
truncation. Register and Scratch Allocation → scratch/ancilla reuse is the
runner-up.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 8983da8 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 8983da8 a4db9a5 -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol a4db9a5 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set. Expect:
   - 1297 qubits
   - 1,403,755 average Toffoli (1,403,754.599 before rounding)
   - score 1,820,670,235
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `44846255` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 766797b..c417821 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1275,7 +1275,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_BODY_CARRY_BAND_TRIMS", "0,3,3,3,3,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,3,3");
     set_default_env("DIALOG_GCD_TOBITVECTOR_CSWAP_BODY_TRIM", "0");
     set_default_env("DIALOG_GCD_BINDER_NOTCH_STEPS", "8,9,10");
-    set_default_env("DIALOG_GCD_BINDER_NOTCH_EXTRA", "2");
+    set_default_env("DIALOG_GCD_BINDER_NOTCH_EXTRA", "3");
     set_default_env("DIALOG_GCD_BINDER_NOTCH_MAP", "13:1");
     set_default_env(
         "DIALOG_GCD_SPECIAL_OVERFLOW_CLEAN_STEP_BITS",
@@ -1399,7 +1399,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "47863838");
+    set_default_env("DIALOG_TAIL_NONCE", "44846255");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
```

