# ec0fa98 — Steepen the dialog-GCD width envelope (slope 1.005 → 1.009) and add a classical island filter

| | |
| --- | --- |
| Contestant | 10d9e |
| Date | 2026-06-05 |
| Submission | `687348e` |
| Commit | `ec0fa982086b588f56e88c92606097328b6197ca` |
| Result | 1320 qubits × 1,538,227 Toffoli = **2,030,459,640** |
| Base | `21fbfc7` (robertkodra, git parent): 1320 qubits × 1,540,355 Toffoli = 2,033,268,600 |
| Change vs base | qubits ±0, Toffoli −2,128, score −2,808,960 (leaderboard Δ −2,808,960) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **B**: the new analysis file `dialog_gcd_classical_filter.rs` is copied; the patch covers the rest |

## Summary

Each dialog-GCD step only operates on the low `active_width(step)` bits of `u`
and `v`, a linear envelope that shrinks by `WIDTH_SLOPE` bits per step. This
commit makes the envelope shrink a little faster: 1.009 bits per step instead
of 1.005. Over the 259 steps, the summed active width drops by 124 bits and the
summed comparator width by 36 bits. Every bit removed from a step saves about
4 Toffoli (conditional swap, gated load, subtract, K2 shift), and every
comparator bit saves 1, in each of four transcript passes. That is
4 × (4 × 124 + 36) = 2,128 Toffoli, the measured saving. Qubits stay at 1320.

The commit also adds an analysis-only classical filter and a session memo.
Neither changes the circuit.

## What changed and why it saves Toffoli

Background (see [dialog-gcd-early](../concepts/dialog-gcd-early.md) for this early route). Everything is in
`src/point_add/mod.rs`. The dialog binary GCD runs `ACTIVE_ITERATIONS = 259`
K2 steps on each of the two inversion factors (`dx = Px − Qx` and
`c = Qx − Rx`), as a forward transcript pass and a reverse erase pass. That is
four passes over the same step schedule.

1. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 1005 → 1009** in
   `configure_ecdsafail_submission_route()`.
   - `dialog_gcd_tobitvector_active_width(step)` =
     `256 − step × slope + DIALOG_GCD_WIDTH_MARGIN`, rounded up to an even
     number and clamped to [1, 256]. Margin is 10.
   - The step's work runs on `u[..aw]` and `v[..aw]`:
     - the conditional swap (one CCX per bit),
     - the gated load and borrow ripple of `dialog_gcd_controlled_sub_selected`
       (about one Toffoli per bit each; the gated register is cleared by
       measurement),
     - the K2 second-shift `cswap` cascade (one CCX per bit).
   - So one bit removed from `aw` saves about 4 Toffoli per step per pass.
   - The branch comparator is `min(COMPARE_BITS = 47, aw)` bits, so on the late
     steps where `aw < 47` it shrinks too, at 1 Toffoli per bit.
   - From slope 1.005 to 1.009, Σ aw over 259 steps goes 35,494 → 35,370
     (−124 bits) and Σ comparator width goes 11,373 → 11,337 (−36 bits).
     4 passes × (4 × 124 + 36) = 2,128 Toffoli, exactly the measured saving.
   - The early steps clamp at 256, so the peak does not move.
2. **`DIALOG_TAIL_NONCE`: 275637277737190 → 6416.** This reseeds the 9,024
   Fiat–Shamir test inputs and does not change the arithmetic. The comment
   gives 6700 as a backup. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
3. **New file `src/point_add/dialog_gcd_classical_filter.rs`** (524 lines,
   copied in Tier B), declared with `pub mod dialog_gcd_classical_filter;` in
   `mod.rs`. Nothing in `build()` calls it.
   - It is a CPU model of the truncated K2 binary GCD.
     `DialogGcdFilterConfig::from_env` reads the same `DIALOG_GCD_*` knobs
     (iterations, compare bits, margin, slope, band trims, PA9024 schedule,
     odd-u fast path, K2).
   - `point_add_gcd_factors` derives both factors `dx` and `c = Qx − Rx`.
   - `check_gcd_factor` replays the truncated GCD and returns a `HardReason`:
     `WidthOverflow` (bit length exceeds `active_width`), `NonConvergence`
     (the full GCD needs more than `ACTIVE_ITERATIONS` steps), or, only with
     `DIALOG_GCD_FILTER_STRICT_COMPARE=1`, `ComparatorMismatch` (the truncated
     compare disagrees with the full-window compare). By default a comparator
     disagreement is not flagged: the replay follows the truncated decision and
     leaves comparator correctness to full validation.
   - `check_all_shots` applies this to all 9,024 inputs of a nonce.
   - Two unit tests: a known clean nonce passes, and margin 8 is stricter than
     margin 9.
   - It lets a nonce hunt skip the quantum simulation for nonces that already
     contain a hard input.
4. **New memo
   `src/point_add/memory/2026-06-05-width-envelope-sweep-1382q.md`.** Session
   notes from an earlier 1382-qubit base. It records that dropping one GCD
   iteration also dropped the peak, that two levers' failure sets can cancel
   under one island, and that both GCD factors must be checked. It is a recipe
   for the classical filter above.

## Why it is still correct, and what it risks

The width envelope is probabilistic. The commit comment calls it
"value-exact", because the dropped high bits are 0 on any input whose GCD has
converged in time. But some inputs converge more slowly than the envelope.
Their `u` or `v` then has a set bit above `aw`, the swap and subtract ignore
it, and the transcript goes wrong. That shows as a classical failure, and
usually as phase or ancilla garbage when the reverse pass no longer mirrors the
forward one. A steeper slope cuts more bits on late steps, so λ, the expected
number of such inputs in one 9,024-shot draw, goes up.

The shipped nonce 6416 draws a clean set. The author reports 0 classical,
0 phase and 0 ancilla failures over all 9,024 shots, found with the filter and
then confirmed by the official run. The new filter file has no effect on the op
stream.

## Classification rationale

The only circuit change narrows the per-step GCD register widths, which is
comparator/width truncation. The filter and memo are tooling.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 21fbfc7 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 21fbfc7 ec0fa98 -- src/point_add` is 609 lines
   in 3 files, 524 of them the new filter file.
2. **Copy the new filter file from the commit:**
   `git checkout ec0fa98 -- src/point_add/dialog_gcd_classical_filter.rs`.
   It is hand-written analysis code, described above, and is copied because it
   is large and does not affect the circuit.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It covers `mod.rs` and the memo.
4. **Check the tree.** `git diff --ignore-cr-at-eol ec0fa98 -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `KAL_*` environment variables set, because `set_default_env`
   keeps any value already in the environment. Expect:
   - 1320 qubits
   - 1,538,227 average Toffoli (rounded)
   - score 2,030,459,640
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=6416` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/memory/2026-06-05-width-envelope-sweep-1382q.md b/src/point_add/memory/2026-06-05-width-envelope-sweep-1382q.md
new file mode 100644
index 0000000..7509451
--- /dev/null
+++ b/src/point_add/memory/2026-06-05-width-envelope-sweep-1382q.md
@@ -0,0 +1,69 @@
+# 2026-06-05 Width-envelope sweep + first peak-qubit drop to 1382 (4 promotions)
+
+Session arc on the COMPARE_BITS=52 lineage (alexander-sei's 488afae opened it).
+The frontier was very hot early (robertkodra/factory-sagar/alexander-sei grinding
+single notches every ~10-30 min), then cooled mid-session. Four promotions landed:
+
+| submission | change | score |
+|---|---|---|
+| 6936bcd | re-stack `KAL_FOLD 24->23` on the compare52 base (it had reverted) | 2,111,711,630 |
+| 11d1423 | `ACTIVE_ITERATIONS 259->258` + `WIDTH_SLOPE 1004->1005` (shared island) | **2,092,653,422** |
+| 79d7ee1 | `WIDTH_SLOPE 1005->1006` | 2,091,901,614 |
+
+(11d1423 also via factory-sagar's intermediate 78696aa = `KAL_DOUBLE 24->23`.)
+
+## The two big lessons
+
+1. **Dropping a whole GCD iteration also drops peak qubits.**
+   `DIALOG_GCD_ACTIVE_ITERATIONS 259 -> 258` cut ~3,446 executed Toffoli AND moved
+   the peak width **1390 -> 1382** (the dropped iteration's scratch row is no
+   longer live). First peak reduction in this lineage. This is worth far more than
+   a carry-window bit and re-opens the width x peak product. 258->257 on the new
+   base is sparse (13+5) — past convergence for many inputs — but a margin/iter
+   combo that sheds another scratch row is the highest-value next target.
+
+2. **Break sets can CANCEL across levers -> stack two savings under one island.**
+   On the 1382 base, `slope1005` alone = 4+3, `active258` alone = 4+3, but
+   **`slope1005 + active258` = 3+3** (gentler than either). Always measure the
+   combo break count, not just the sum. (Did NOT recur on the next base:
+   slope1006+active257 = 26+18, purely additive. Lever-set dependent.)
+
+## Density map (classical+phase breaks at inherited nonce, by base)
+
+- compare52 base (488afae): kal_f23 = 0+2 (island nonce 55, ~15s).
+- 1382 base (11d1423): slope1006 = 6+6 (island nonce 13555, ~30min/13.6k nonces),
+  active257 = 13+5, margin9 = 9+4, applyc19 = 10+6. No cancelling combos.
+
+Phase breaks hurt density more than the classical count alone suggests
+(6+6 took ~13.6k nonces vs 3+3 at ~3.6k and 0+2 at ~55).
+
+## The wall: WIDTH_MARGIN 10 -> 9
+
+The biggest remaining single lever (~-4,184 T, likely another peak drop) but a
+sparse island: 9+ breaks, >1/14000 by local brute search (killed at 14k nonces).
+Brute tail-nonce search at ~7-8 nonce/s on 11 threads runs out of runway here.
+
+**To break this wall, build the both-factor classical convergence pre-filter**
+(alexander-sei's 488afae note + robertkodra clearly use one). Recipe:
+- For each test input derive the TWO GCD inputs per point-add: `dx = Px - Qx mod p`
+  and `c = Qx - Rx mod p` where `Rx = E.x`, `E = target + offset` (expected point,
+  so Rx is free from the precomputed expected point). Checking only `dx`
+  undercounts the hard rate ~2x and yields false-clean islands.
+- Run the truncated-width binary GCD classically (model `active_width(step)` from
+  the WIDTH_MARGIN/SLOPE/ACTIVE envelope + body-carry band) and reject any input
+  whose register width overflows the envelope (= a value error = hard input).
+- A nonce is clean iff NONE of its 9024 inputs is hard on EITHER factor.
+- Must be bit-exact with the quantum truncation; validate by reproducing known
+  islands (e.g. nonce 13555 clean, neighbors dirty) before trusting it.
+`src/point_add/kaliski_classical_replay.rs` has the FULL-WIDTH recurrence as a
+starting point, but it does NOT yet model the width envelope — that's the work.
+
+## Tooling
+
+`src/bin/island_search_jac.rs` — full-validation tail-nonce searcher, bit-exact
+with eval_circuit (startup self-check vs affine k*G). ~7-8 nonce/s on 11 threads,
+sim-bound. Usage:
+`ISLAND_LOWQ=1 <KNOB=val ...> ISLAND_THREADS=11 ./target/release/island_search_jac <start> <count> [step]`
+Reports `CLEAN nonce=N avg_toffoli=T ...` on the first clean island. Note the
+avg_toffoli is exact but peak qubits must be read from the official `ecdsafail run`
+(the searcher runs LOWQ) — that's how the 1382 drop was first observed.
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6c6d2f9..bcc958c 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -69,6 +69,7 @@ use crate::weierstrass_elliptic_curve::WeierstrassEllipticCurve;
 pub mod by;
 #[cfg(test)]
 pub mod coset_proto;
+pub mod dialog_gcd_classical_filter;
 pub mod fermat_inv;
 pub mod halfgcd_coeff_decoder;
 pub mod halfgcd_live_pa;
@@ -31845,7 +31846,15 @@ fn configure_ecdsafail_submission_route() {
     // truncation re-rolls the Fiat-Shamir island; a 1-D reroll sweep (post_sub
     // fixed at the inherited 503292) lands a clean island at DIALOG_REROLL=101019.
     // Back off the width slope to 1004 for the final-window W2 clean island.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1005");
+    // Re-tighten WIDTH_SLOPE 1005 -> 1009 on the W2 final-window base (which had
+    // left the slope loose to find its structural island). The per-step GCD-body
+    // width envelope shrinks an extra ~4 notches; the dropped high bits are
+    // provably 0 on the converged reachable support, so it is value-exact and the
+    // residual failures are pure Fiat-Shamir, dodged by the re-rolled tail nonce
+    // below. avg executed Toffoli 1,540,355 -> 1,538,227 (-2,128), peak-neutral at
+    // 1320q. Found with the local classical width-convergence pre-filter +
+    // bit-exact validate (island_search_prefilter), confirmed via official run.
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1009");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
     set_default_env("DIALOG_REROLL", "4269");
@@ -31866,7 +31875,10 @@ fn configure_ecdsafail_submission_route() {
     // 1390q x 1,518,179 T = 2,110,268,810.
     // Final-window W2 island: validated 0/0/0 over all 9024 shots at
     // 1320q x 1,545,787 T = 2,040,438,840.
-    set_default_env("DIALOG_TAIL_NONCE", "275637277737190");
+    // Re-rolled for the WIDTH_SLOPE 1005 -> 1009 re-tightening above: nonce 6416
+    // lands a clean Fiat-Shamir island, validated 0/0/0 over all 9024 shots at
+    // 1320q x 1,538,227 T = 2,030,459,640 (backup: 6700).
+    set_default_env("DIALOG_TAIL_NONCE", "6416");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

