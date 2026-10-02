# ecbf87b — Cap the GCD branch comparator at 59 bits instead of 61, with a new reroll pair

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-02 |
| Submission | `061e105` |
| Commit | `ecbf87b5593ccdb6dd6ffa27a503a630bf6aae13` |
| Result | 1567 qubits × 1,683,915 Toffoli = **2,638,694,805** |
| Base | `006e38b` (git parent and frontier at the time, solimander): 1567 qubits × 1,685,515 Toffoli = 2,641,202,005 |
| Change vs base | qubits ±0, Toffoli −1,600, score −2,507,200 (leaderboard Δ −2,507,200) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In this era the slope λ is computed with a reversible binary GCD (the
"dialog GCD"). Each GCD step has to decide whether `u > v`, and the circuit
decides it from only the top few bits of the two registers. This commit lowers
the global cap on that comparison from 61 to 59 bits. One comparator bit costs
one Toffoli, and the comparison runs four times per step (forward and reverse
transcript pass, in both GCD pairs), so the 400 bits removed across the steps
save exactly 1,600 Toffoli. Qubits are unchanged. Because the op stream
changed, the author re-rolled the Fiat–Shamir test set with a new pair of
identity X;X counts.

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`, which sets the route's knobs with `set_default_env`:

1. **`DIALOG_GCD_COMPARE_BITS`: 61 → 59.**
   - In each step of the transcript pass (`emit_dialog_gcd_compressed_sidecar_tobitvector_steps_block_lifecycle`
     and its `_reverse_` twin), the circuit writes two log bits:
     `b0 = v[0]` (v is odd) and `b0_and_b1 = b0 AND (u > v)`. The second one
     decides the conditional swap of `u` and `v` before `v −= u; v >>= 1`.
   - `u > v` is computed by `dialog_gcd_ccx_cmp_gt_truncated_into_width`, which
     runs `ccx_cmp_lt_into_fast` on only the top `compare_bits` bits of the
     active registers. That comparator spends one CCX per bit on the carry
     chain and clears the carries by measurement (`hmr` + `cz_if`), so its
     cost is one Toffoli per bit.
   - `compare_bits` comes from `dialog_gcd_compare_bits_for_step(step, active_width)`.
     With `DIALOG_GCD_PA9024_COMPARE_SCHEDULE=1` it is
     `min(SCHEDULE[step] + MARGIN, DIALOG_GCD_COMPARE_BITS, active_width)`, where
     `SCHEDULE` is a baked 399-entry table of per-step widths and `MARGIN` is 5.
     So `DIALOG_GCD_COMPARE_BITS` is a global ceiling on the schedule.
   - Lowering the ceiling to 59 only touches steps whose scheduled width
     exceeds 59. With the base's other settings (399 active steps,
     `DIALOG_GCD_WIDTH_MARGIN=27`) that is 212 of the 399 steps (steps 54 to
     318), and the per-step widths summed over all steps drop from 20,410 to
     20,010 bits, 400 fewer.
   - The comparison runs once in the forward transcript pass and once in its
     reverse, for each of the two GCD pairs (quotient and product). That is
     4 × 400 = 1,600 Toffoli, which matches the measured −1,600.
2. **Reroll pair: `DIALOG_REROLL` 6 → 0, `DIALOG_POST_SUB_REROLL` 28 → 10.**
   - `build_builder()` emits `DIALOG_REROLL` pairs of `X(tx[0]); X(tx[0])`
     before the first subtraction and `DIALOG_POST_SUB_REROLL` pairs of
     `X(tx[1]); X(tx[1])` right after `Px −= Qx; Py −= Qy`. Each pair is an
     identity, so the circuit is unchanged. The bytes of the op stream change,
     and with them the 9,024 test inputs drawn from its hash.
   - This era has no tail nonce yet. These two counts play its role: a
     two-dimensional search space for a clean test set. The author's note says
     1-D sweeps of either count alone found no clean island for this stream.

## Why it is still correct, and what it risks

The truncated comparison is approximate. It can return the wrong `u > v`
answer when `u` and `v` agree on all of their top 59 bits (within the active
width) but differ below. Then the step swaps when it should not, or the other
way round, and `v −= u` can go negative. The transcript is then not the one
the apply pass expects, and the quotient or product comes out wrong, which the
evaluator reports as a classical failure (or as phase or ancilla garbage when
the uncompute pass no longer mirrors the forward one).

Lowering the cap from 61 to 59 raises that chance by about 4× per affected
step, so λ (the expected number of failing shots in one 9,024-shot draw)
grows. The submission still validates because the reroll pair (0, 10) draws a
test set with no hard input: 9,024 of 9,024 shots pass with 0 classical,
0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md); in this era
the "nonce" is the pair of X;X counts rather than a tail.

## Classification rationale

The only circuit change is a narrower comparator, so comparator/width
truncation fits. The reroll change comes with every circuit change in this era
and is not a separate lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 006e38b -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 006e38b ecbf87b -- src/point_add` is 9 lines
   changed in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ecbf87b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`,
   `KAL_*` or `ROUND84_*` environment variables set, because `set_default_env`
   keeps any value already in the environment. Expect:
   - 1567 qubits
   - 1,683,915 average Toffoli (rounded)
   - score 2,638,694,805
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the reroll pair `DIALOG_REROLL=0`,
`DIALOG_POST_SUB_REROLL=10` and an identical op stream. Any other change needs
a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index b8697ce..d223b2e 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -29258,7 +29258,10 @@ fn configure_ecdsafail_submission_route() {
     // Branch comparator width tightened 63 -> 61 (−1,160 executed Toffoli),
     // STACKED on the PA9024 margin-5 cut. Two within-budget truncations coexist
     // via the 2-D reroll island (DIALOG_REROLL=1, DIALOG_POST_SUB_REROLL=0).
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "61");
+    // Branch comparator width tightened 61 -> 59 (−1,600 executed Toffoli),
+    // stacked on the chunked-apply + round763 + acc=19 base via the 2-D reroll
+    // island (DIALOG_REROLL=0, DIALOG_POST_SUB_REROLL=10). Validated 0/0/0 @ 1567.
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "59");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "399");
@@ -29301,8 +29304,8 @@ fn configure_ecdsafail_submission_route() {
     // Round763 reachable-support compressor + apply-clean compare bits 19 on
     // the chunked apply route needs a fresh Fiat-Shamir island: 6/28 validates
     // 0/0/0 over 9024 at 1567q and 1,685,515 avg executed Toffoli.
-    set_default_env("DIALOG_REROLL", "6");
-    set_default_env("DIALOG_POST_SUB_REROLL", "28");
+    set_default_env("DIALOG_REROLL", "0");
+    set_default_env("DIALOG_POST_SUB_REROLL", "10");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

