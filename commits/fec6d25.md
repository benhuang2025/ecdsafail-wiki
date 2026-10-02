# fec6d25 — Run the GCD for 258 steps instead of 259, dropping one 8-qubit transcript block (1390 → 1382 qubits), plus slope 1.004 → 1.005

| | |
| --- | --- |
| Contestant | 10d9e |
| Date | 2026-06-05 |
| Submission | `11d1423` |
| Commit | `fec6d254b5ceb9d9fd7e7e8f5cccc99182a030f7` |
| Result | 1382 qubits × 1,514,221 Toffoli = **2,092,653,422** |
| Base | `fa5347c` (git parent and frontier at the time, factory-sagar): 1390 qubits × 1,518,179 Toffoli = 2,110,268,810 |
| Change vs base | qubits −8, Toffoli −3,958, score −17,615,388 (leaderboard Δ −17,615,388) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The binary GCD runs a fixed number of steps, `DIALOG_GCD_ACTIVE_ITERATIONS`.
This commit lowers that from 259 to 258. Its branch bits are stored three steps
at a time in 8-qubit blocks, so 259 steps needed 87 blocks, the last holding a
single step. 258 steps fit exactly in 86 blocks. The transcript is live during
the apply pass, which was the peak, so the peak falls by one block, from 1390 to
1382 qubits. This was the first qubit reduction on this line.

The dropped step also removes one apply step per GCD call. Apply steps work on
full 256-bit registers, so that saves about 2,850 Toffoli. The same commit
steepens the width envelope slope from 1.004 to 1.005, which saves about 940
more. In total, Toffoli falls by 3,958.

## What changed and why it saves qubits and Toffoli

**Background.** The circuit is the dialog-GCD route (`emit_dialog_gcd_raw_pa`
in `src/point_add/mod.rs`). Two calls each run a reversible binary GCD on
(u, v) = (p, factor): the quotient dy/dx and the product with c = ox − Rx. Each
call has a forward pass of `ACTIVE_ITERATIONS` steps that records branch bits,
an apply pass that replays them on (x, y) once per step, and a reverse pass that
erases them. [98416e4](98416e4.md) lists one GCD step.

**The transcript blocks.** With `DIALOG_GCD_K2=1`, each step records three
bits: `b0`, `b0_and_b1` and `s2`. Groups of `DIALOG_GCD_HIGH_TAIL_ALIAS_GROUP_SIZE = 3`
steps (9 raw bits) are packed into `dialog_gcd_block_bits() = 5 + 3 = 8` qubits.
The log size is

```
dialog_gcd_compressed_sidecar_blocks() = ceil(ACTIVE_ITERATIONS / 3)
dialog_gcd_compressed_sidecar_bits()   = blocks × 8
```

That is 87 × 8 = 696 qubits at 259 steps and 86 × 8 = 688 at 258.

**The changes in `configure_ecdsafail_submission_route()`:**

1. **`DIALOG_GCD_ACTIVE_ITERATIONS`: 259 → 258.**
   - **Qubits −8.** The last block, which held only step 258, disappears. At
     this point the peak sits in the apply pass's chunked raw add and subtract
     (teddyjfpender's phase trace in [`06b07ee`](06b07ee.md) shows them at
     1382 on this tree), and the whole log is live there. So the 8 qubits come
     straight off the peak.
   - **Toffoli.** The removed GCD step itself is almost free, about 160 Toffoli,
     because at step 258 the active window is only 8 bits wide.
   - The removed apply steps cost much more, because they act on full 256-bit
     registers. Each one has a plain doubling, a controlled K=2 doubling with a
     256-wide cswap cascade, a controlled modular add with its fold, and a
     256-wide cswap.
   - One apply step goes from each of the two GCD calls, which is about 2,850
     Toffoli.
2. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 1004 → 1005.** This is the lever of
   [`98416e4`](98416e4.md). With margin 10, the 2-bit narrowing lands on 25 odd
   steps between 201 and 249.
   - Some of these steps have a window above the 52-bit comparator cap, which
     gives about 16 Toffoli per bit-step over the four passes.
   - The rest are below the cap, which gives about 20.
   - The total is about −944 Toffoli.
3. **`DIALOG_TAIL_NONCE`: 254 → 3577.**

The GCD-body cost model (4·width + min(52, width) Toffoli per step per pass)
gives −1,104 for items 1 and 2 together. The remaining −2,854 is the two apply
steps.

The comments added next to both knobs still say "peak-neutral at 1390q". The
author's submission note reports the 1382 peak, which they first saw in the
official `ecdsafail run`. Their own searcher runs in a low-qubit mode and does
not report the peak.

## Why it is still correct, and what it risks

A fixed step count is a convergence bet. An input whose GCD needs all 259 steps
to finish is no longer fully reduced after 258. The apply pass then replays an
incomplete transcript, and the output is wrong. That is a classical failure, and
it makes the input hard.

The author measured break counts at the inherited nonce on the base: 4 + 3
(classical + phase) for 258 steps alone, 4 + 3 for slope 1005 alone, and 3 + 3
with both together. The two levers' hard-input sets overlap, so the pair costs
less λ than either alone. The author notes this did not happen again on the next
tree. Nonce `3577` was found after about 3,600 tries and draws a clean set: 0
classical, 0 phase and 0 ancilla failures over all 9,024 shots.

## Classification rationale

The main lever is the GCD's step count, which is iteration/threshold tuning.
The slope notch riding along is comparator/width truncation, but it is the
smaller part of both the Toffoli and the score change. Most of the score gain
comes from the 8 qubits, which is a side effect of the iteration count through
the block-packed transcript.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout fa5347c -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol fa5347c fec6d25 -- src/point_add` is 17 changed
   lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol fec6d25 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set.
   `set_default_env` only fills variables that are unset. Expect:
   - 1382 qubits
   - 1,514,221 average Toffoli (rounded)
   - score 2,092,653,422
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `3577` and an identical op stream. Any
other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index fd6135b..a6b1b9b 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31321,7 +31321,12 @@ fn configure_ecdsafail_submission_route() {
     // 396 -> 395 -> 394 on the current 1355q route. The binary-GCD transcript
     // still converges on the verifier support for the Fiat-Shamir island below,
     // while dropping two full GCD body/reverse steps.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "259");
+    // 259 -> 258: drops one more GCD body/reverse iteration from the active
+    // band (-~3446 avg executed Toffoli, peak-neutral at 1390q). The transcript
+    // still converges on the verifier support for the Fiat-Shamir island below;
+    // stacked with WIDTH_SLOPE 1004->1005 (the two break sets partially cancel,
+    // so the combined island is gentler than either lever alone).
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "258");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -31479,7 +31484,10 @@ fn configure_ecdsafail_submission_route() {
     // 1,779,067 -> 1,778,555 (-512), peak-neutral at 1355q. The tighter
     // truncation re-rolls the Fiat-Shamir island; a 1-D reroll sweep (post_sub
     // fixed at the inherited 503292) lands a clean island at DIALOG_REROLL=101019.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1004");
+    // 1004 -> 1005: tightens every late-step GCD-body width by an extra
+    // fraction of a bit (~-512 avg executed Toffoli, peak-neutral at 1390q),
+    // stacked with ACTIVE_ITERATIONS 259->258 above under one shared island.
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1005");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
     set_default_env("DIALOG_REROLL", "4269");
@@ -31498,7 +31506,10 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the combined KAL_DOUBLE/FOLD_CARRY_TRUNC_W=23 op stream:
     // nonce=254 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1390q x 1,518,179 T = 2,110,268,810.
-    set_default_env("DIALOG_TAIL_NONCE", "254");
+    // Re-rolled for the WIDTH_SLOPE=1005 + ACTIVE_ITERATIONS=258 op stream
+    // (above): nonce=3577 lands a clean island, validated 0/0/0 over all 9024
+    // shots at 1390q x 1,514,221 T = 2,104,767,190.
+    set_default_env("DIALOG_TAIL_NONCE", "3577");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

