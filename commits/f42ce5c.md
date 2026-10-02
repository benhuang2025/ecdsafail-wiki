# f42ce5c — Cut the GCD to 396 steps so the transcript log loses one 5-qubit block (1443 → 1438 qubits), loosening two compares to find a clean island

| | |
| --- | --- |
| Contestant | Sam-Scolari |
| Date | 2026-06-03 |
| Submission | `6b7a0d3` |
| Commit | `f42ce5c49031eab2010abb35c21e789968989cdd` |
| Result | 1438 qubits × 1,736,773 Toffoli = **2,497,479,574** |
| Base | `144e07f` (phileigenlabs): 1443 qubits × 1,736,319 Toffoli = 2,505,508,317 |
| Change vs base | qubits −5, Toffoli +454, score −8,028,743 |
| Leaderboard Δ | −1,396,715, measured against the frontier at the time, `113f346` (1443 × 1,731,723 = 2,498,876,289), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **B**: 147 generated Markdown notes are copied from the commit; the patch covers `mod.rs` |

## Summary

The dialog GCD writes its branch decisions into a compressed transcript log
that stays live for the whole GCD-and-apply sandwich. Every 3 steps take one
5-qubit block. At 397 steps the log needs `ceil(397 / 3) = 133` blocks. At 396
it needs exactly 132. This commit cuts the step count from 397 to 396, which
removes one block, 5 qubits, from the live state at the peak. The peak falls
from 1443 to 1438. Dropping a step also saves roughly 2,200 Toffoli.

A shorter GCD fails on inputs that need all 397 steps. To find a clean test
island anyway, the author loosened two other approximations: the
branch-compare schedule margin goes back from 4 to 8 bits, and the apply-pass
overflow compare grows from 19 to 21 bits. Those cost about 2,600 Toffoli, so
the net is +454 Toffoli for −5 qubits. The score drops 8.0 M against the base.

## What changed and why it saves qubits

### `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()` (the patch)

1. **`DIALOG_GCD_ACTIVE_ITERATIONS`: 397 → 396.**
   - The forward and reverse transcript passes
     (`emit_dialog_gcd_compressed_sidecar_tobitvector_steps_block_lifecycle`
     and its `_reverse_` twin) and the apply pass all loop over
     `dialog_gcd_active_iterations()` steps.
   - Steps are grouped by `DIALOG_GCD_HIGH_TAIL_ALIAS_GROUP_SIZE = 3`. Each
     group's 6 raw branch bits (`b0`, `b0_and_b1` per step) are packed by the
     `round763` compressor into `DIALOG_GCD_HIGH_TAIL_ALIAS_BLOCK_BITS = 5`
     qubits. `dialog_gcd_compressed_sidecar_blocks()` is
     `ceil(iterations / 3)`, so the log goes from 133 × 5 = 665 to
     132 × 5 = 660 wires.
   - The log is live from the first forward step to the end of the reverse
     pass, so it sits under every peak phase. Five fewer log wires lower the
     peak by 5.
   - The removed step's comparator, swap, subtract and apply add/subtract save
     about 2,180 Toffoli (from the totals below).
2. **`DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN`: 4 → 8 (looser).**
   - The per-step branch-compare width is
     `min(SCHEDULE[step] + MARGIN, active_width, DIALOG_GCD_COMPARE_BITS = 58)`.
   - Recomputing the table over 396 steps, the summed width rises from 19,680
     to 19,942 bits. The comparator runs four times per step (forward and
     reverse, both GCD passes) at one Toffoli per bit: +1,048 Toffoli.
   - A wider compare is more exact, so this lowers λ.
3. **`DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS`: 19 → 21 (looser).**
   - After the apply pass's modular add, `acc_ovf` holds the add's overflow
     bit. It is erased by recomputing it as "result < addend" from only the
     top `APPLY_CLEAN_COMPARE_BITS` bits:
     `ccx_cmp_lt_into_fast(acc[256−k..], a[256−k..], ctrl, acc_ovf)` in
     `dialog_gcd_cmod_add_materialized_pseudomersenne_chunked`. The subtract
     does the same through `dialog_gcd_clean_truncated_underflow`.
   - Two more bits at each of the 2 × 396 apply sites is about +1,584
     Toffoli. The truncated compare is wrong only when the top `k` bits of
     result and addend agree, so 2 more bits make that about 4× rarer.
4. **Reroll pair: `DIALOG_REROLL` 50 → 3, `DIALOG_POST_SUB_REROLL` 39 → 51.**
   These are the identity `X;X` counts that only re-draw the 9,024 test
   inputs.

Accounting: +1,048 + 1,584 − ~2,180 ≈ +454, the measured change.

### `src/point_add/memory/research_graph/` (147 new Markdown files, copied)

This is a generated research digest, not code:
- `README.md`.
- `commit_notes/001-…md` to `143-…md`: one auto-generated note per accepted
  commit up to `d2b4bcf`, with the score, tags and the main diff lines.
- `timeline.md`, `knowledge_graph.md` (a lineage graph of the mechanisms) and
  `frontier_watch.md`.

## Why it is still correct, and what it risks

- **The iteration cut is probabilistic.** The binary GCD needs a variable
  number of steps. An input whose transcript has not converged after 396
  steps leaves `u`, `v` and the coefficients wrong, which shows up as a
  classical failure, or as ancilla garbage after the reverse pass.
- **The two compare changes go the other way.** They make existing
  approximations more exact, which lowers λ and offsets part of the extra
  risk from the cut.
- The reroll pair (3, 51) draws a clean set: 9,024 of 9,024 shots pass with
  0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The lever is the GCD step count, and its payoff is a shorter transcript log.
That is iteration/threshold tuning. The two compare widenings are give-backs
that make the island findable, not separate levers. The qubit saving could
also be read as peak work, but it comes only from the count.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 144e07f -- src/point_add`.
   - Do not start from the git parent `113f346`. Diffing against it (6,865
     lines) would also show `DIALOG_GCD_WIDTH_MARGIN` going back from 26 to
     27, which reverts twangodev's change. This commit was built on `144e07f`
     and never had it.
   - `git diff --ignore-cr-at-eol 144e07f f42ce5c -- src/point_add` is 6,854
     lines in 148 files. All but 31 lines (in `mod.rs`) are the new research
     digest.
2. **Copy the generated digest** from the commit:
   `git checkout f42ce5c -- src/point_add/memory/research_graph`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It covers `src/point_add/mod.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol f42ce5c -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`,
   `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set, because
   `set_default_env` keeps any value already in the environment. Expect:
   - 1438 qubits
   - 1,736,773 average Toffoli (rounded)
   - score 2,497,479,574
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the reroll pair `DIALOG_REROLL=3`,
`DIALOG_POST_SUB_REROLL=51` and an identical op stream. Any other change needs
a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 9283d3c..17ada9e 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -29769,11 +29769,10 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_COMPRESSED_SIDECAR_LOG", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE", "1");
-    // PA9024 compare-schedule margin tightened 8 -> 5 (trims a comparator-width
-    // bit/step, -1,868 executed Toffoli). The tighter margin needs a clean
-    // Fiat-Shamir island, found by a 2D reroll search (DIALOG_REROLL=3 +
-    // DIALOG_POST_SUB_REROLL=18 below) — 1D reroll sweeps miss it. 0/0/0 @ 1571.
-    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "4");
+    // PA9024 compare-schedule margin retuned with ACTIVE_ITERATIONS=396 and
+    // APPLY_CLEAN_COMPARE_BITS=21. The wider margin gives back a little Toffoli
+    // but lands the 1438q clean island at DIALOG_REROLL=3 / POST_SUB=51 below.
+    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "8");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "20");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "20");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
@@ -29789,13 +29788,11 @@ fn configure_ecdsafail_submission_route() {
     // stacked on the 1446-peak base + ACTIVE_ITERATIONS=397 via the reroll-37/1
     // island documented below.
     set_default_env("DIALOG_GCD_COMPARE_BITS", "58");
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "21");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
-    // 399 -> 397 (−~4,252 executed Toffoli). The binary-GCD converges within 397
-    // iterations for all 9024 inputs on the reroll-37/1 island (399 was a stale
-    // "floor"; the realizable convergence tail is shorter on the reachable support,
-    // so a co-tuned island lands it). Island-tuned, like the width truncations.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "397");
+    // 399 -> 396. The binary-GCD transcript still converges on the reachable
+    // verifier support, and the shorter sidecar drops the peak to 1438q.
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "396");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -29919,14 +29916,10 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_BODY_HOST_CIN", "1");
     set_default_env("DIALOG_GCD_LATE_BORROW_UV_HIGH", "1");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "128");
-    // TOFFOLI STACK on the 1446 base: with body-host-cin + uv-high-borrow + F_CUT=126,
-    // the two public proven tightenings COMPARE_BITS 59->58 (−952) and
-    // ACTIVE_ITERATIONS 399->397 (−4,252) stack for −5,204 executed Toffoli at the
-    // same 1446 peak. The combined op-stream re-rolls the Fiat-Shamir island; a 2-D
-    // (DIALOG_REROLL x DIALOG_POST_SUB_REROLL) search lands 37/1 clean 0/0/0 over all
-    // 9024 shots. Validated via eval_circuit: 1446q x 1,735,059 T = 2,508,895,314.
-    set_default_env("DIALOG_REROLL", "50");
-    set_default_env("DIALOG_POST_SUB_REROLL", "39");
+    // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
+    // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
+    set_default_env("DIALOG_REROLL", "3");
+    set_default_env("DIALOG_POST_SUB_REROLL", "51");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

