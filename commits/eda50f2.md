# eda50f2 — Lower the GCD compare-schedule margin from 8 to 7 bits

| | |
| --- | --- |
| Contestant | Epistetechnician |
| Date | 2026-06-02 |
| Submission | `37f1ef4` |
| Commit | `eda50f2060eb5bdc3a8e06509d1f3d48564bae1b` |
| Result | 1698 qubits × 1,668,241 Toffoli = **2,832,673,218** |
| Base | `b694e22` (git parent and frontier at the time, Gajesh2007): 1698 qubits × 1,668,753 Toffoli = 2,833,542,594 |
| Change vs base | qubits ±0, Toffoli −512, score −869,376 (leaderboard Δ −869,376) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The width of the GCD swap comparator at each step comes from a baked
per-step table plus a safety margin. [`f8a36ba`](f8a36ba.md) set that margin
to 8. This commit lowers it to 7.

The margin only binds on steps where `table + margin` is below both the
63-bit global cap and the register width. That is 128 steps, almost all in
the first 140 steps of the walk. On each of them the comparator gets one bit
narrower, which saves 1 Toffoli at each of the 4 fused comparator sites. That
is 128 × 4 = 512 Toffoli. Qubits stay at 1698. The reroll goes from 12 to 4.

## What changed and why it saves Toffoli

`configure_ecdsafail_submission_route()` in `src/point_add/mod.rs` changes
two pins:

- **`DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN`: 8 → 7.**
- **`DIALOG_REROLL`: 12 → 4.** The comment above it is updated.

`dialog_gcd_compare_bits_for_step` returns

```
k(step) = max(1, min( min(63, w), min(max(table[step] + margin, 1), w) ))
```

where `w = active_width(step)` and `table` is
`DIALOG_GCD_PA9024_COMPARE_SCHEDULE`. With margin 8, `table + 8` is the
smallest term on 128 steps: steps 0–9, most of steps 10–110, and a few up to
step 191. Lowering the margin by 1 lowers `k` by 1 on exactly those steps.

The fused swap comparator ([`9b6b9d6`](9b6b9d6.md)) costs `k + 1` CCX. It
runs 4 times per step, in the forward and reverse walk of each GCD pair. So
the saving is 128 × 4 = 512, exactly the measured drop.

The commit also adds a memory note,
`src/point_add/memory/2026-06-02-a16-schedule-margin7-reroll4.md`. It lists
probes that failed on this line at the rerolls tried:

- the odd-u fastpath of [`9805d0c`](9805d0c.md): rerolls 0–5; rerolls 6–18
  with the fold window at 21; and its load-only and cswap-only halves at
  reroll 12;
- `DIALOG_GCD_ACTIVE_ITERATIONS=398`;
- either carry window at 19;
- `DIALOG_GCD_WIDTH_MARGIN=27`.

## Why it is still correct, and what it risks

Narrowing the comparator is a heuristic. When u and v tie on their top `k`
bits, it misjudges `u > v`. The walk then branches wrong, which is a classical
failure. The early steps, where the table is narrowest (12–30 bits), carry
most of the added risk. Reroll 4 draws a clean set: 0 classical, 0 phase and
0 ancilla failures over 9,024 shots.

## Classification rationale

The only circuit change is a narrower per-step comparator window, so this is
comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout b694e22 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol b694e22 eda50f2 -- src/point_add` is
   42 lines in 2 files, most of them in the new memory note.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol eda50f2 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or other route environment variables set. Expect:
   - 1698 qubits
   - 1,668,241 average Toffoli (rounded)
   - score 2,832,673,218
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL` = 4 and an identical op stream.
Any other change needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/memory/2026-06-02-a16-schedule-margin7-reroll4.md b/src/point_add/memory/2026-06-02-a16-schedule-margin7-reroll4.md
new file mode 100644
index 0000000..85c923b
--- /dev/null
+++ b/src/point_add/memory/2026-06-02-a16-schedule-margin7-reroll4.md
@@ -0,0 +1,35 @@
+# 2026-06-02 a16 schedule margin 7 reroll4
+
+Base: promoted `a16cb87` at `1,668,753 T`, `1,698 Q`, score
+`2,833,542,594`.
+
+Change:
+
+- Tightened `DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN` from `8` to `7`.
+- Co-tuned `DIALOG_REROLL` from `12` to `4`.
+- Kept the a16 carry-tail defaults:
+  - `KAL_DOUBLE_CARRY_TRUNC_W=20`
+  - `KAL_FOLD_CARRY_TRUNC_W=20`
+  - `DIALOG_GCD_ACTIVE_ITERATIONS=399`
+- Did not keep the odd-lowbit fastpath probe; it did not compose cleanly with
+  the a16 carry-tail island.
+
+Local proof:
+
+- `./benchmark.sh --note dialog-gcd-a16-sched-margin7-reroll4-default`
+- `9024/9024` shots OK.
+- Classical mismatches: `0`.
+- Phase-garbage batches: `0`.
+- Ancilla-garbage batches: `0`.
+- Metrics: `1,668,241 T`, `1,698 Q`.
+- Score: `2,832,673,218`.
+
+Rejected nearby probes:
+
+- Odd-lowbit fastpath on a16 with rerolls `0..5` failed.
+- Odd-lowbit with `KAL_FOLD_CARRY_TRUNC_W=21` and rerolls `6..18` failed.
+- Odd load-only and cswap-only subprobes failed at reroll `12`.
+- `DIALOG_GCD_ACTIVE_ITERATIONS=398` failed at reroll `12`.
+- `KAL_DOUBLE_CARRY_TRUNC_W=19` and `KAL_FOLD_CARRY_TRUNC_W=19` each failed
+  at reroll `12`.
+- `DIALOG_GCD_WIDTH_MARGIN=27` failed at rerolls `12` and `5`.
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ef5f271..aeec005 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -28497,7 +28497,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_COMPRESSED_SIDECAR_LOG", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE", "1");
-    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "8");
+    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "7");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "20");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "20");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
@@ -28529,7 +28529,10 @@ fn configure_ecdsafail_submission_route() {
     // the materialized add/sub clean predicates with the measured comparator.
     // Pure Toffoli reduction (1697569 -> 1673629), peak-neutral at 1698.
     // (Validated 0/0/0 over 9024 via eval_circuit.)
-    set_default_env("DIALOG_REROLL", "12");
+    // Compare schedule margin 7 composes with the a16 carry-tail route when
+    // co-tuned to reroll 4. Pure Toffoli reduction (1668753 -> 1668241),
+    // peak-neutral at 1698. (Validated 0/0/0 over 9024 via eval_circuit.)
+    set_default_env("DIALOG_REROLL", "4");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

