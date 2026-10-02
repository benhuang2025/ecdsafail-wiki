# 2dcf00d — Add 1-bit GCD body notches at steps 11 and 12 (peak-neutral Toffoli trim)

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-06-08 |
| Submission | `582ad52` |
| Commit | `2dcf00d6e82c36cb6a4d1989fc65889ce511f3f4` |
| Result | 1297 qubits × 1,403,733 Toffoli = **1,820,641,701** |
| Base | `a4db9a5` (SamrendraS, git parent and frontier at the time): 1297 qubits × 1,403,755 Toffoli = 1,820,670,235 |
| Change vs base | qubits ±0, Toffoli −22, score −28,534 (leaderboard Δ −28,534) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

[8983da8](8983da8.md) introduced a per-step map of extra high-bit trims for
the dialog-GCD walk body, `DIALOG_GCD_BINDER_NOTCH_MAP`, and set it to
`13:1`. This commit fills the gap and sets it to `11:1,12:1,13:1`. The
bodies at steps 11 and 12 become one bit narrower. The peak is now set by
the walk's shift and reverse-add phases, so it stays at 1297. Each trimmed
bit saves about 2 Toffoli per body: −16 emitted over 2 steps and 4 walks,
−22 measured. The tail nonce was refreshed.

## What changed and why it saves Toffoli

All changes are in `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`.

1. **`DIALOG_GCD_BINDER_NOTCH_MAP`: `13:1` → `11:1,12:1,13:1`.**
   - `dialog_gcd_binder_notch_map_extra(step)` adds the listed extra to the
     body trim `w` in `dialog_gcd_body_carry_trunc_width`. `active_width` is
     256 at step 11 and 254 at step 12, and their band trim is 3.
   - Step 11 (which also has the default trio notch +2) goes from 251 to 250
     bits. Step 12 goes from 251 to 250 bits.
   - Each body bit is one gated-load CCX (`ctrl ∧ src`) and one carry CCX.
     Over the 4 walks (forward and reverse walk of both divisions) that is
     2 × 2 × 4 = −16 emitted Toffoli. The measured −22 includes draw
     variance in the conditioned Toffoli.
   - The composite scratch at those steps also shrinks, but they were not
     peak binders, so the qubit count does not move.
2. **`DIALOG_TAIL_NONCE`: 44846255 → 3967248.**

## Why it is still correct, and what it risks

The trims are probabilistic. If an input still has a set high bit of `u` or
`v`, or a carry into the cut, at step 11 or 12, the body computes the wrong
difference, the walk goes off its path, and the run shows a classical
mismatch and ancilla garbage. The shipped nonce `3967248` draws a test set
with 0 classical, 0 phase and 0 ancilla failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change narrows the body width at two steps, which saves
Toffoli and not qubits. That is comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a4db9a5 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol a4db9a5 2dcf00d -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 2dcf00d -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set. Expect:
   - 1297 qubits
   - 1,403,733 average Toffoli (rounded)
   - score 1,820,641,701
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `3967248` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index c417821..0b3441d 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1276,7 +1276,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_TOBITVECTOR_CSWAP_BODY_TRIM", "0");
     set_default_env("DIALOG_GCD_BINDER_NOTCH_STEPS", "8,9,10");
     set_default_env("DIALOG_GCD_BINDER_NOTCH_EXTRA", "3");
-    set_default_env("DIALOG_GCD_BINDER_NOTCH_MAP", "13:1");
+    set_default_env("DIALOG_GCD_BINDER_NOTCH_MAP", "11:1,12:1,13:1");
     set_default_env(
         "DIALOG_GCD_SPECIAL_OVERFLOW_CLEAN_STEP_BITS",
         "113:21,131:21,142:22,187:23,205:22,210:21",
@@ -1399,7 +1399,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "44846255");
+    set_default_env("DIALOG_TAIL_NONCE", "3967248");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
```

