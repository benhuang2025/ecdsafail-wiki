# ca7fd40 — Stack four dialog-GCD tightenings on newjordan's 1320-qubit tree: branch compare 52 → 51, apply clean compare 20 → 19, width slope 1.005 → 1.009, 260 → 259 steps

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-05 |
| Submission | `5afafb7` |
| Commit | `ca7fd406086e826da4d73139625bcf8319655264` |
| Result | 1320 qubits × 1,557,239 Toffoli = **2,055,555,480** |
| Base | `a92d098` (newjordan, submission `2be504e`): 1320 qubits × 1,563,855 Toffoli = 2,064,288,600 |
| Change vs base | qubits ±0, Toffoli −6,616, score −8,733,120 |
| Leaderboard Δ | −4,812,720, measured against the frontier at the time, `229aeed` (10d9e, 1320 × 1,560,885 = 2,060,368,200), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The 1320-qubit "apply teardown" (teddyjfpender, `06b07ee`) had reset several
dialog-GCD truncation knobs to looser values than the older 1382-qubit line
used. This commit tightens four of them at once on newjordan's tree: the GCD
branch comparator, the apply-phase clean comparator, the per-step width
envelope and the step count. Each one removes Toffoli that almost never
matters. Together they save 6,616 average Toffoli at the same 1320 qubits.

All four are probabilistic, so the commit needed a new test set with no
failing input. The author found tail nonce 11,000,665 with a parallel
early-exit nonce sweep on large cloud machines.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`. The comments added next to the
`KAL_DOUBLE_CARRY_TRUNC_W` and `KAL_FOLD_CARRY_TRUNC_W` pins say they were
tightened to 22 here, but the base already has both at 22, so their values do
not change.

Background: the `DIALOG_GCD` route runs a reversible binary GCD on `(u, v)`
for a fixed number of steps. Each step computes branch bits, cswaps `u` and
`v`, subtracts, and shifts. The step's bits are stored in a compressed
transcript and replayed by an "apply" loop on the Bézout pair `(x, y)`. All of
this runs forward and in reverse, for both GCD uses in the point add (the
quotient and the multiply pass).

1. **`DIALOG_GCD_COMPARE_BITS`: 52 → 51.**
   - The branch bit `b0_and_b1` needs `u > v`. The code computes it with
     `dialog_gcd_ccx_cmp_gt_truncated_into_width(_hosted)`, which only compares
     the top `compare_bits` bits of the step's active window, so it is
     `v[start..] < u[start..]` with `start = active_width − compare_bits`.
   - `dialog_gcd_compare_bits_for_step()` uses `min(COMPARE_BITS, active_width)`
     here, because `DIALOG_GCD_PA9024_COMPARE_SCHEDULE` is `0`.
   - The comparator (`ccx_cmp_lt_into_fast` and its borrowed-carry form) costs
     one CCX per compared bit on its forward MAJ sweep. Its carries are erased
     by `hmr` plus `cz_if`, which costs no Toffoli. So the cut saves one
     Toffoli per comparator call, on every step whose window is still wider
     than 51 bits.
2. **`DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS`: 20 → 19.**
   - Each apply step's controlled modular add
     (`dialog_gcd_cmod_add_materialized_pseudomersenne_with_clean_scratch`)
     leaves an overflow flag `acc_ovf`. It is cleared by comparing the result
     with the addend: `cmp_lt_into_fast(&acc[N − k..], &f[N − k..], acc_ovf)`.
     The subtract twin uses `dialog_gcd_clean_truncated_underflow`.
   - `k = N − compare_start` is this knob. Only the top `k` bits are
     compared, at one CCX per bit, so 19 saves one Toffoli per apply add and
     per apply subtract.
3. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 1005 → 1009.**
   - `dialog_gcd_tobitvector_active_width(step)` is
     `256 − step × slope + WIDTH_MARGIN`, rounded up to an even number and
     clamped to 256, with `WIDTH_MARGIN = 10`. It is how many low bits of `u`
     and `v` each step works on.
   - A steeper slope makes every late step's window narrower: by about
     `0.004 × step` bits, so up to 1 bit at step 259, and by 2 bits on some
     steps after rounding.
   - The cswap and the controlled subtract cost about one Toffoli per window
     bit, so each step whose rounded window drops by 2 bits gets cheaper.
4. **`DIALOG_GCD_ACTIVE_ITERATIONS`: 260 → 259.** One fewer GCD step in every
   loop. The same cut alone measured −3,116 Toffoli in
   [`229aeed`](229aeed.md). This commit's comment says −3,108 here.
5. **`DIALOG_POST_SUB_REROLL`: 631921 → 503292** and **`DIALOG_TAIL_NONCE`:
   1476 → 11000665.** Both only add identity `X;X` pairs, which reseed the
   9,024 Fiat–Shamir test inputs. The reroll value goes back to the one in the
   older 1320-qubit trees. The tail nonce is 48 `X;X` pairs at the end of
   `build_builder()`.

The individual savings were not measured separately. After the iteration
cut, about 3,500 Toffoli are left for the three width changes together.

## Why it is still correct, and what it risks

- **Branch compare.** A truncated compare gives the wrong branch when `u`
  and `v` agree on their top 51 window bits but differ below. The step then
  subtracts the wrong way, and the GCD can fail to converge. The author
  repeats an earlier claim (from the `73 → 52` commit's comment) that a
  classical filter over both GCD inputs on 300k cases never saw a mis-decision
  down to 52 bits. The new comment asserts the same at 51 but shows no data.
- **Apply clean compare.** If the sum and addend agree on their top 19 bits,
  `acc_ovf` is not cleared. That leaves ancilla or phase garbage.
- **Width slope.** If an input's real bit length is still above the narrower
  window at some step, its high bits are cut off and the result is wrong. That
  gives a classical failure.
- **Steps.** An input that needs step 260 does not finish its GCD. That gives
  a classical or phase failure.
- The author measured at least 3 classical-plus-phase failures across 80
  random nonces. Nonce 11000665 draws a clean set: 9,024 of 9,024 shots, with
  0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Three of the four levers narrow a comparator or a register window, so the
commit is filed as comparator/width truncation. The step-count cut is
iteration/threshold tuning, and it is the largest single piece (about 3,100 of
6,616). That makes iteration/threshold tuning a close runner-up.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a92d098 -- src/point_add`.
   - The author's note names `9510ccc` (`94e9418`) as the base. `a92d098`, its
     successor by the same author, is closer: it already has both carry
     windows at 22.
   - Do not start from the git parent `229aeed`. That is 10d9e's tree, which has
     the same 259 cut but keeps the double and fold windows at 23, the slope
     at 1008 and nonce 754. Diffing against the parent (113 lines) would
     wrongly show this commit tightening both windows and deleting
     10d9e's memory file.
   - Against `a92d098`, `git diff --ignore-cr-at-eol a92d098 ca7fd40 -- src/point_add`
     is 36 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ca7fd40 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*`, `DIALOG_*` or `SUB4_*` environment variables set, because they
   override the defaults. Expect:
   - 1320 qubits
   - 1,557,239 average Toffoli (rounded)
   - score 2,055,555,480
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `11000665` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 90ce594..f0407d9 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31560,12 +31560,18 @@ fn configure_ecdsafail_submission_route() {
     // DOUBLE-carry lazy-Solinas window tightened 24 -> 23 (-1,038 avg executed
     // Toffoli, peak-neutral at 1390q). Re-found tail nonce below validates the
     // combined double+fold carry-truncation stream.
+    // 23 -> 22: one further notch, reclaimed on the 1320q five-chunk-apply base
+    // (the structural cut reset the carry-trunc windows to 23). Value-exact on
+    // the reachable verifier support; residual failures are pure Fiat-Shamir,
+    // dodged by the re-found tail nonce below.
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "22");
     // FOLD-carry lazy-Solinas window tightened 24 -> 23 (-518 avg executed
     // Toffoli, peak-neutral at 1390q). Re-stacked onto alexander-sei's
     // COMPARE_BITS=52 base, which had reverted FOLD to 24. Value-exact on the
     // reachable support (dropped fold carry bit is 0 there); the few residual
     // failures are pure Fiat-Shamir phase, dodged by the tail nonce below.
+    // 23 -> 22: reclaimed on the 1320q base alongside DOUBLE=22 (orthogonal
+    // Solinas-fold windows). Value-exact on the reachable support.
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "22");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
     set_default_env("DIALOG_GCD_ROUND763_COMPRESS_LEVER", "1");
@@ -31592,11 +31598,15 @@ fn configure_ecdsafail_submission_route() {
     // 2 T/bit), peak-neutral at 1390q, with ZERO change to islandability. The
     // shorter op stream re-rolls Fiat-Shamir; co-tuned with WIDTH_MARGIN=10 and
     // TAIL_NONCE below. Validated 0/0/0 over all 9024 shots.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "52");
+    // 52 -> 51: reclaimed on the 1320q base (the structural five-chunk-apply cut
+    // reverted the GCD branch comparator to 52). The comparator never mis-decides
+    // a branch at 51 on the verifier support; pure -T, peak-neutral.
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "51");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
+    // 20 -> 19: reclaimed on the 1320q base alongside COMPARE_BITS=51.
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_K2", "1");
     // 396 -> 395 -> 394 on the current 1355q route. The binary-GCD transcript
@@ -31605,7 +31615,12 @@ fn configure_ecdsafail_submission_route() {
     // 258 -> 260: re-spends two active GCD rows after the 1320q apply teardown
     // below. This removes the residual phase failures at the custom-five seed
     // while still staying below the 1320q x current-best Toffoli budget.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "260");
+    // 260 -> 259: reclaim one GCD row. On the 1320q five-chunk base the apply
+    // peak no longer scales with the iteration count (the apply teardown caps
+    // it), so 259 is peak-neutral at 1320q and the residual convergence/phase
+    // failures are dodged by the combined-stream tail nonce below (measured
+    // floor cf+pg=3 over 80 nonces). -3,108 avg executed Toffoli.
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "259");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -31771,11 +31786,14 @@ fn configure_ecdsafail_submission_route() {
     // 1004 -> 1005: tightens every late-step GCD-body width by an extra
     // fraction of a bit (~-512 avg executed Toffoli, peak-neutral at 1390q),
     // stacked with ACTIVE_ITERATIONS 259->258 above under one shared island.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1005");
+    // 1008 -> 1009: one more notch on the per-step width-envelope shrink rate,
+    // reclaimed on the 1320q base. Peak-neutral at 1320q; the tighter late-step
+    // widths stay within the provably-|0> converged GCD region. ~-512 avg-T.
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1009");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
     set_default_env("DIALOG_REROLL", "4269");
-    set_default_env("DIALOG_POST_SUB_REROLL", "631921");
+    set_default_env("DIALOG_POST_SUB_REROLL", "503292");
     // Fiat-Shamir island for ACTIVE_ITERATIONS=393 + WIDTH_MARGIN=25 (1350q base).
     // The fixed-length 96-op identity tail (see the DIALOG_TAIL_NONCE block in
     // build_builder) reseeds the 9024 Fiat-Shamir test inputs without changing
@@ -31793,7 +31811,13 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the active260 custom-five hosted-boundary apply teardown:
     // nonce=108 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1320q x 1,565,417 T = 2,066,350,440.
-    set_default_env("DIALOG_TAIL_NONCE", "1476");
+    // Re-rolled for the reclaimed-width stack on the 1320q base (COMPARE_BITS=51,
+    // APPLY_CLEAN_COMPARE_BITS=19, KAL_DOUBLE/FOLD_CARRY_TRUNC_W=22, WIDTH_SLOPE=
+    // 1009, ACTIVE_ITERATIONS=259): nonce=11000665 lands a clean island, validated
+    // 0/0/0 over all 9024 shots at 1320q x 1,557,239 T = 2,055,555,480. Found by a
+    // parallel early-exit tail-nonce sweep on 192-core boxes, then confirmed with
+    // the official full-9024 eval_circuit.
+    set_default_env("DIALOG_TAIL_NONCE", "11000665");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

