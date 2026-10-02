# 6e7ca2c — Lower the dialog-GCD branch comparator's global cap from 63 to 61 bits

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-02 |
| Submission | `655038c` |
| Commit | `6e7ca2cf986d48cc021c0e79af833e55a092cfa2` |
| Result | 1571 qubits × 1,742,173 Toffoli = **2,736,953,783** |
| Base | `14fc786` (the author's previous submission, git parent and frontier): 1571 qubits × 1,743,333 Toffoli = 2,738,776,143 |
| Change vs base | qubits ±0, Toffoli −1,160, score −1,822,360 (leaderboard Δ −1,822,360) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog-GCD branch comparator's width per step is the smallest of three
numbers: the per-step schedule entry plus a margin, the live register width,
and a global cap. In the middle of the walk the schedule asks for more than 63
bits, so the cap decides. This commit lowers the cap from 63 to 61. The 156
steps that compared more than 61 bits (134 of them at the cap of 63) now
compare 1 or 2 bits fewer, 290 bits fewer per walk. Over four walks at one Toffoli per bit, that saves 1,160 Toffoli.
Qubits are unchanged.

## What changed and why it saves Toffoli

Background on the walk step and the comparator schedule is in
[8316db1](8316db1.md).

- `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`:
  `DIALOG_GCD_COMPARE_BITS` default 63 → 61, with a comment.
  - `dialog_gcd_compare_bits()` reads it.
    `dialog_gcd_compare_bits_for_step(step, w)` returns
    `min(SCHEDULE[step] + 5, w, DIALOG_GCD_COMPARE_BITS)`.
  - The schedule entries are 56–73 over most of the walk (steps ≈ 50–330), so
    with margin 5 the cap of 63 was binding on many steps.
  - With the cap at 61, 156 steps change, and the per-walk total goes from
    20,700 to 20,410 bits (−290). 4 walks × 290 = 1,160, exactly the
    measured drop.
  - The apply-phase clean comparators use their own width,
    `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS = 20`, so they are not affected.
- `DIALOG_REROLL` 3 → 1 and `DIALOG_POST_SUB_REROLL` 18 → 0. These are the two
  identity `X;X` pads, re-searched jointly for a clean draw.

## Why it is still correct, and what it risks

This is a probabilistic truncation. In the middle of the walk `u` and `v` are
still 100–200 bits wide, and the comparator decides `u > v` from only the top
61 bits of the live window. A tie on all 61 bits gives the wrong branch. The
tie probability at 61 bits is tiny per step, but the commit stacks it on the
margin-5 cut from [14fc786](14fc786.md), and the walk has 399 steps and many
inputs.

A wrong branch shows as a classical mismatch, usually with ancilla garbage
from the reverse walk. The shipped pair (1, 0) draws 0 classical, 0 phase and
0 ancilla failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

A narrower truncated comparator is comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 14fc786 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 14fc786 6e7ca2c -- src/point_add` is
   9 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 6e7ca2c -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set.
   Expect:
   - 1571 qubits
   - 1,742,173 average Toffoli (rounded)
   - score 2,736,953,783
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL = 1`,
`DIALOG_POST_SUB_REROLL = 0` and an identical op stream. Any other change
needs a new reroll scan.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index dbb2ad4..c406eae 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -29023,7 +29023,10 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "20");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
     set_default_env("DIALOG_GCD_MEASURED_UNDERFLOW_GATE", "1");
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "63");
+    // Branch comparator width tightened 63 -> 61 (−1,160 executed Toffoli),
+    // STACKED on the PA9024 margin-5 cut. Two within-budget truncations coexist
+    // via the 2-D reroll island (DIALOG_REROLL=1, DIALOG_POST_SUB_REROLL=0).
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "61");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "399");
@@ -29060,8 +29063,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_WINDOW_BLOCKS", "2");
     // New low-bit body op stream needs its own clean Fiat-Shamir island:
     // REROLL=1, POST_SUB_REROLL=12 validates 0/0/0 over 9024.
-    set_default_env("DIALOG_REROLL", "3");
-    set_default_env("DIALOG_POST_SUB_REROLL", "18");
+    set_default_env("DIALOG_REROLL", "1");
+    set_default_env("DIALOG_POST_SUB_REROLL", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

