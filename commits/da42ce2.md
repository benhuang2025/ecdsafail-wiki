# da42ce2 — Cap the dialog-GCD branch comparator at 56 bits instead of 58 on the 1355-qubit tree

| | |
| --- | --- |
| Contestant | harrigan |
| Date | 2026-06-03 |
| Submission | `9fad60c` |
| Commit | `da42ce22313ed6a3e97da8ab14cca178533b0ebe` |
| Result | 1355 qubits × 1,779,067 Toffoli = **2,410,635,785** |
| Base | `13a01b8` (git parent and frontier at the time, nikhiljha): 1355 qubits × 1,781,211 Toffoli = 2,413,540,905 |
| Change vs base | qubits ±0, Toffoli −2,144, score −2,905,120 (leaderboard Δ −2,905,120) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Each dialog-GCD step decides whether to swap `u` and `v` by comparing them,
and that comparison only looks at their top few bits. The number of bits is
the smaller of a per-step schedule and a global cap. This commit lowers the
cap from 58 to 56 bits. It is the same edit as [`5b5a5d4`](5b5a5d4.md),
which was made on the 1411-qubit tree. [`13a01b8`](13a01b8.md) was built on
the same parent and kept 58, so the cut was available again. On the steps
where the cap binds, the summed comparator width drops by 536 bits. The comparison runs in four passes and
costs one Toffoli per bit, so the saving is exactly 4 × 536 = 2,144 Toffoli
at the unchanged 1355-qubit peak. The reroll was re-searched for the new op
stream.

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`:

1. **`DIALOG_GCD_COMPARE_BITS`: 58 → 56.**
   - Each step writes `b0_and_b1 = v_odd AND (u > v)`. With
     `DIALOG_GCD_FUSED_BRANCH_BITS=1` and
     `DIALOG_GCD_BRANCH_BITS_HOST_COMPARATOR=1` the comparison is
     `dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted`, which compares only the
     top `compare_bits` bits of the active `u` and `v`. Its carries are
     cleared by measurement, so it costs one CCX per bit.
   - `dialog_gcd_compare_bits_for_step(step, active_width)` returns
     `min(SCHEDULE[step] + 7, COMPARE_BITS, active_width)` (at least 1).
     `SCHEDULE` is the baked 399-entry `DIALOG_GCD_PA9024_COMPARE_SCHEDULE`
     table and 7 is `DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN`. The global
     knob is a ceiling on the schedule.
   - With this tree's 396 steps and width margin 26 (as in `5b5a5d4`;
     the `13a01b8` changes do not touch the comparator), the summed per-step
     comparator width is 19,814 bits at a cap of 58 and 19,278 at 56: 536
     bits fewer.
   - The comparison runs in the forward and the reverse transcript pass of
     both GCD calls (the `dy/dx` quotient and the x-tail product). 4 × 536 =
     2,144, exactly the measured saving.
2. **Reroll: `DIALOG_REROLL` 171 → 291150, `DIALOG_POST_SUB_REROLL` 0 →
   503292.** These are counts of identity `X;X` pairs before and after the
   input subtraction. They change the op-stream hash, and so the 9,024 Fiat–Shamir test
   inputs, without changing the circuit. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

The truncated comparison is wrong when `u` and `v` agree on all of their top
56 bits but differ lower down. The step then takes the wrong branch, and the
transcript no longer drives the apply replay correctly. That shows up as a
classical failure, or as phase or ancilla garbage if the reverse pass no
longer mirrors the forward one. Two fewer bits make this about 4× more likely
on each step where the cap binds, so λ rises.

The shipped pair (291150, 503292) is clean: 0 classical, 0 phase and 0
ancilla failures over all 9,024 shots, per the author, who found it with a
custom offline reroll searcher. See
[comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).

## Classification rationale

The only circuit change is a narrower comparator, which is comparator/width
truncation. The reroll change is the usual companion of any circuit change
in this era.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 13a01b8 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 13a01b8 da42ce2 -- src/point_add` is
   6 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol da42ce2 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` keeps any
   value already in the environment. Expect:
   - 1355 qubits
   - 1,779,067 average Toffoli (rounded)
   - score 2,410,635,785
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=291150`,
`DIALOG_POST_SUB_REROLL=503292` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 9c046f8..1346f3c 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31085,7 +31085,7 @@ fn configure_ecdsafail_submission_route() {
     // island documented below.
     // Branch comparator 58 -> 57: -1,064 executed Toffoli, peak-neutral at 1434q,
     // stacked on the active395 base. Clean island at REROLL=4959 / POST_SUB=5983.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "58");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "56");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
@@ -31227,8 +31227,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT3", "168");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "171");
-    set_default_env("DIALOG_POST_SUB_REROLL", "0");
+    set_default_env("DIALOG_REROLL", "291150");
+    set_default_env("DIALOG_POST_SUB_REROLL", "503292");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

