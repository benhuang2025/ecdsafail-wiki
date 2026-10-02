# c3c3f8d — Run the dialog GCD for 395 steps instead of 396 on the 1355-qubit tree

| | |
| --- | --- |
| Contestant | PhantasticUniverse |
| Date | 2026-06-04 |
| Submission | `b29ff7f` |
| Commit | `c3c3f8df6664f2560858a5db891450026fd58716` |
| Result | 1355 qubits × 1,773,011 Toffoli = **2,402,429,905** |
| Base | `d3e35ae` (git parent and frontier at the time, mpjunior92): 1355 qubits × 1,775,211 Toffoli = 2,405,410,905 |
| Change vs base | qubits ±0, Toffoli −2,200, score −2,981,000 (leaderboard Δ −2,981,000) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog GCD runs a fixed number of binary-GCD steps. This commit cuts
that number from 396 to 395. It is the same edit as [`311d6c3`](311d6c3.md)
and [`a392fd4`](a392fd4.md), made again because the 1355-qubit line
([`13a01b8`](13a01b8.md) and its successors) had been built on a 396-step
tree. The dropped
step is almost free in the GCD itself, because by step 395 the width
envelope is only 2 bits. The saving comes from the apply replay, which
re-applies every step's decision to full 256-bit registers: one fewer step
there saves about 1,000 Toffoli in each of the two GCD calls. In total that
is 2,200 average Toffoli at the unchanged 1355-qubit peak. The reroll pair
was re-searched for the new op stream.

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`:

1. **`DIALOG_GCD_ACTIVE_ITERATIONS`: 396 → 395.**
   - `dialog_gcd_active_iterations()` reads it. It sets the number of steps
     of every pass of the dialog GCD: the forward and reverse transcript
     passes, and the apply replay between them, for both GCD calls (the
     `dy/dx` quotient and the x-tail product).
   - **GCD passes.** The last step, index 395, ran at
     `active_width = 2` (`256 − 395 × 0.711 + 26 = 1.2`, rounded up to an
     even number; this tree has slope 0.711 and margin 26), so dropping it
     saves only a few Toffoli per pass.
   - **Apply replay.** `emit_dialog_gcd_compressed_sidecar_apply_bitvector_block_lifecycle`
     (and its reverse-exact twin for the quotient) replays each step on the
     256-bit Bézout pair: a modular double of `y` (`mod_double_inplace_fast`),
     a `b0`-controlled modular add of `x` into `y`
     (`dialog_gcd_cmod_add_materialized_pseudomersenne`), and a
     `b0_and_b1`-controlled swap of `x` and `y` (256 CCX). These are full
     width at every step, so one step costs roughly 1,000 Toffoli. Two apply
     passes account for most of the 2,200.
   - **Qubits.** The transcript is stored in 5-qubit blocks of 3 steps, and
     `dialog_gcd_compressed_sidecar_blocks()` is
     `ceil(iterations / 3) = 132` for both 395 and 396. The transcript keeps
     its size, so the peak does not move. The last block just holds 2 steps,
     and the u-high runway (`13a01b8`) parks the same blocks as in the base.
2. **Reroll: `DIALOG_REROLL` 12027 → 4269.** `DIALOG_POST_SUB_REROLL`
   stays at 503292. The author found the value with a hunter that first
   applies a classical width and convergence prefilter, then simulates the
   survivors on all 9,024 shots. These are counts of identity
   `X;X` pairs that re-seed the 9,024 Fiat–Shamir test inputs without
   changing what the circuit computes. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

A fixed step count is probabilistic. The binary GCD of `(p, dx)` needs a
number of steps that depends on the input. An input that has not reached
`v = 0` after 395 steps leaves the transcript incomplete. The apply replay
then computes the wrong quotient, which shows up as a classical failure, and
the reverse pass no longer restores `u` and `v`, which shows up as ancilla
garbage. One step fewer raises λ, the expected number of failing shots per
9,024-shot draw.

The shipped pair (4269, 503292) is clean: 0 classical, 0 phase and 0
ancilla failures over all 9,024 shots, per the author. See
[trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) for the dialog GCD
lineage and
[comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)
for the other step budgets of this era.

## Classification rationale

The only circuit change is a shorter fixed iteration count, which is
iteration/threshold tuning. It removes a step that is almost always idle, so
the Dead-Code family fits. The reroll change is the usual companion.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout d3e35ae -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol d3e35ae c3c3f8d -- src/point_add` is
   13 lines in 1 file, most of them comments.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol c3c3f8d -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` keeps any
   value already in the environment. Expect:
   - 1355 qubits
   - 1,773,011 average Toffoli (rounded)
   - score 2,402,429,905
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=4269`,
`DIALOG_POST_SUB_REROLL=503292` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index d6355a3..3da9ed2 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31093,9 +31093,10 @@ fn configure_ecdsafail_submission_route() {
     // frontier had dropped, stacked on compare57+active395. Clean island below.
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
-    // 399 -> 396. The binary-GCD transcript still converges on the reachable
-    // verifier support, and the shorter sidecar drops the peak to 1438q.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "396");
+    // 396 -> 395 on the current 1355q route. The binary-GCD transcript still
+    // converges on the verifier support for the rerolled Fiat-Shamir island
+    // below, while dropping one full GCD body/reverse step.
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "395");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -31238,9 +31239,9 @@ fn configure_ecdsafail_submission_route() {
     // truncation re-rolls the Fiat-Shamir island; a 1-D reroll sweep (post_sub
     // fixed at the inherited 503292) lands a clean island at DIALOG_REROLL=101019.
     set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "711");
-    // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
-    // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "12027");
+    // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
+    // 9024 shots at 1355q x 1,773,011 T.
+    set_default_env("DIALOG_REROLL", "4269");
     set_default_env("DIALOG_POST_SUB_REROLL", "503292");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

