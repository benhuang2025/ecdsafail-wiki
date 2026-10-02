# d2b4bcf — Cap the GCD branch comparator at 57 bits on the 1446-qubit tree

| | |
| --- | --- |
| Contestant | Epistetechnician |
| Date | 2026-06-02 |
| Submission | `44bc2a4` |
| Commit | `d2b4bcf0d98bc80d434703123bc0c1ae967a59e0` |
| Result | 1446 qubits × 1,736,185 Toffoli = **2,510,523,510** |
| Base | `8ab5f90` (git parent and frontier at the time, pldallairedemers): 1446 qubits × 1,737,201 Toffoli = 2,511,992,646 |
| Change vs base | qubits ±0, Toffoli −1,016, score −1,469,136 (leaderboard Δ −1,469,136) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the same one-knob cut as 10d9e's [`14b84f1`](14b84f1.md), carried
onto the new 1446-qubit tree of [`8ab5f90`](8ab5f90.md). That tree had been
built on `fd8e712` and so still had the comparator cap at 58.

Each step of the dialog GCD (the early circuit's reversible binary extended
GCD, which computes `dy / dx mod p`) decides `u > v` from only the top bits
of the two registers. Lowering the global cap on that comparison from 58 to
57 bits removes one bit on each of the 254 steps where the cap binds. The
comparison runs four times per step at one Toffoli per bit, so the saving is
4 × 254 = 1,016 Toffoli. Qubits are unchanged. The reroll pair was
re-searched from (1, 28) to (3, 118).

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`, the function that pins all route defaults with
`set_default_env`:

1. **`DIALOG_GCD_COMPARE_BITS`: 58 → 57.**
   - Background: the dialog GCD runs `DIALOG_GCD_ACTIVE_ITERATIONS = 398`
     steps on the pair `(u, v)`. Each step computes branch bits (is `v` odd,
     is `u > v`), conditionally swaps, subtracts and halves, and appends the
     branch bits to a compressed transcript log. A later "apply" pass replays
     the log on the coefficient registers. See
     [dialog-gcd-early](../concepts/dialog-gcd-early.md) for this route;
     [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) describes its
     later version.
   - `dialog_gcd_compare_bits_for_step(step, active_width)` returns
     `min(DIALOG_GCD_PA9024_COMPARE_SCHEDULE[step] + MARGIN, active_width, DIALOG_GCD_COMPARE_BITS)`,
     floored at 1. The schedule is a baked 399-entry table, the margin is
     `DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN = 5`, and `active_width` comes
     from the width envelope (`DIALOG_GCD_WIDTH_MARGIN = 27`). The global
     value is therefore a cap: it only matters on steps where
     `schedule + 5` and the active width both exceed it.
   - The comparator compares only the top `compare_bits` of `u` and `v`
     (`start = len − compare_bits`, then `cmp_lt` of `v[start..]` against
     `u[start..]`). On this tree it is the hosted
     `ccx_cmp_lt_into_fast_borrowed_carries`, one Toffoli per bit, with its
     carries borrowed from the unwritten log tail and cleared by measurement
     (`hmr` + `cz_if`). See
     [measurement-uncompute](../concepts/measurement-uncompute.md).
   - As in `14b84f1`, the 57 cap binds on 254 active steps (steps 53 to 320).
     The comparator runs in the forward and
     reverse transcript passes of both GCD pairs, so the drop is
     4 × 254 = 1,016 Toffoli, exactly the measured change. See
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
2. **Reroll pair: `DIALOG_REROLL` 1 → 3, `DIALOG_POST_SUB_REROLL` 28 → 118.**
   These are the early circuit's nonce. `build_builder()` emits
   `DIALOG_REROLL` pairs of `X;X` on `tx[0]` before the first subtraction and
   `DIALOG_POST_SUB_REROLL` pairs on `tx[1]` after `Px −= Qx, Py −= Qy`. Each
   pair is an exact identity, so it changes only the op-stream bytes and hence
   the Fiat–Shamir test draw. The comment lines above the knob were updated
   to describe the new island.

## Why it is still correct, and what it risks

The truncated comparison is approximate. When `u` and `v` agree on their top
57 bits it can return the wrong `u > v`. The step then takes the wrong branch,
and the transcript no longer follows the true GCD. That shows up as a
classical failure, or as phase or ancilla garbage when the reverse pass no
longer mirrors the forward pass. One bit fewer roughly doubles the per-step
risk on the 254 affected steps, so λ goes up.

The reroll pair (3, 118) draws a clean set: 9,024 of 9,024 shots pass with
0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is a narrower, approximate comparator, so
comparator/width truncation fits. The reroll change comes with every circuit
change and is not a separate lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 8ab5f90 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 8ab5f90 d2b4bcf -- src/point_add` is
   13 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol d2b4bcf -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`,
   `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set, because
   `set_default_env` keeps any value already in the environment. Expect:
   - 1446 qubits
   - 1,736,185 average Toffoli (rounded)
   - score 2,510,523,510
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the reroll pair `DIALOG_REROLL=3`,
`DIALOG_POST_SUB_REROLL=118` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 4cca767..3ddd6b1 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -29673,7 +29673,10 @@ fn configure_ecdsafail_submission_route() {
     // Branch comparator width tightened 61 -> 59 (−1,600 executed Toffoli),
     // stacked on the chunked-apply + round763 + acc=19 base via the 2-D reroll
     // island (DIALOG_REROLL=0, DIALOG_POST_SUB_REROLL=10). Validated 0/0/0 @ 1567.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "58");
+    // On the partial-hosted 1446q surface, compare58 was the first clean frontier.
+    // compare57 is peak-neutral and saves 1,016 executed Toffoli; a 2-D reroll
+    // search lands on 3/118 clean 0/0/0 over all 9024 shots.
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "57");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "398");
@@ -29780,10 +29783,10 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_BRANCH_BITS_HOST_COMPARATOR", "1");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "126");
     // Partial body-gated hosting plus F_CUT=126 drops the hosted-comparator
-    // route to the 1446q branch/apply co-binder. A 2-D reroll search lands
-    // 1/28 clean 0/0/0 over all 9024 shots at 1446q and 1,737,201 Toffoli.
-    set_default_env("DIALOG_REROLL", "1");
-    set_default_env("DIALOG_POST_SUB_REROLL", "28");
+    // route to the 1446q branch/apply co-binder. The compare57 route is clean
+    // on the 3/118 Fiat-Shamir island at 1446q and 1,736,185 Toffoli.
+    set_default_env("DIALOG_REROLL", "3");
+    set_default_env("DIALOG_POST_SUB_REROLL", "118");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

