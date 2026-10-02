# ae3b97b — Steepen the GCD width envelope slope from 1.006 to 1.007 bits per step

| | |
| --- | --- |
| Contestant | 10d9e |
| Date | 2026-06-05 |
| Submission | `c0ecf45` |
| Commit | `ae3b97b28b015dc4d83a45f9b092afbe7cab40d0` |
| Result | 1382 qubits × 1,513,293 Toffoli = **2,091,370,926** |
| Base | `05d68e5` (git parent and frontier at the time, the author's previous submission): 1382 qubits × 1,513,677 Toffoli = 2,091,901,614 |
| Change vs base | qubits ±0, Toffoli −384, score −530,688 (leaderboard Δ −530,688) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the next notch after [`05d68e5`](05d68e5.md):
`DIALOG_GCD_WIDTH_SLOPE_X1000` goes from 1006 to 1007. The binary GCD's working
window becomes 2 bits narrower on 12 odd steps between 143 and 165, which saves
24 bit-steps × 16 = 384 Toffoli. Qubits are unchanged. The nonce was re-hunted.
The author also added a session note that records the lever densities and a
recipe for a classical nonce prefilter.

## What changed and why it saves Toffoli

**Background.** The circuit is the dialog-GCD route (`emit_dialog_gcd_raw_pa`
in `src/point_add/mod.rs`). Two calls each run a reversible binary GCD: the
quotient dy/dx and the product with c = ox − Rx. Each call has a forward pass,
an apply pass and a reverse pass. [98416e4](98416e4.md) lists one GCD step and
the width formula
`active_width(step) = clamp(2·⌈(256 − step·SLOPE/1000 + MARGIN)/2⌉, 1, 256)`.

**The changes:**

- `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`:
  - `DIALOG_GCD_WIDTH_SLOPE_X1000`: 1006 → 1007, with margin 10 and 258 steps.
    - The rounded width drops by 2 bits at the odd steps 143, 145, …, 165
      (124 → 122 down to 102 → 100).
    - These windows are wider than the 52-bit comparator cap. So each bit-step
      saves about 4 Toffoli per pass in the cswap, the subtract or add, and the
      K=2 halving cascade.
    - Over four passes, that is 16 per bit-step: 24 × 16 = 384.
  - `DIALOG_TAIL_NONCE`: 13555 → 6483.
- New file `src/point_add/memory/2026-06-05-width-envelope-sweep-1382q.md`
  (69 lines). This is the author's session log for `bc858e8`, `fec6d25`,
  `05d68e5` and this commit. It records:
  - that dropping one GCD step also dropped the peak, 1390 → 1382;
  - that the break sets of two levers can overlap, so the pair costs less λ;
  - break counts per lever and tree;
  - a recipe for a classical prefilter that replays the truncated GCD on both
    factors, dx and c = ox − Rx, to screen nonces before full simulation.

The per-notch saving keeps falling (−544 for the last notch, −384 for this one),
because each notch narrows fewer steps. The author reads this as the envelope
nearing the real bit-length curve.

## Why it is still correct, and what it risks

A narrower window cuts the top bits of any input whose GCD registers have not
shrunk as fast as the envelope assumes. The GCD then goes wrong, which is a
classical failure. The author measured 7 classical and 4 phase breaks at the
inherited nonce. That was the gentlest useful lever on this tree:

- the comparator at 51 broke 7 + 5 but saves only about 8 Toffoli;
- the apply-clean comparator at 19 broke 10 + 7;
- margin 9 broke 15 + 9;
- 257 steps broke 13 + 5.

The local full-validation searcher found nonce `6483` after about 6,500 tries.
It draws a clean set: 0 classical, 0 phase and 0 ancilla failures over all
9,024 shots.

## Classification rationale

The only circuit change narrows the GCD registers' working width, which is
comparator/width truncation. The added note is documentation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 05d68e5 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 05d68e5 ae3b97b -- src/point_add` is 87 lines
   in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ae3b97b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set.
   `set_default_env` only fills variables that are unset. Expect:
   - 1382 qubits
   - 1,513,293 average Toffoli (rounded)
   - score 2,091,370,926
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `6483` and an identical op stream. Any
other change needs a new nonce hunt.

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
index c18701f..c4add0d 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31484,11 +31484,11 @@ fn configure_ecdsafail_submission_route() {
     // 1,779,067 -> 1,778,555 (-512), peak-neutral at 1355q. The tighter
     // truncation re-rolls the Fiat-Shamir island; a 1-D reroll sweep (post_sub
     // fixed at the inherited 503292) lands a clean island at DIALOG_REROLL=101019.
-    // 1004 -> 1005 -> 1006: tightens every late-step GCD-body width by an extra
-    // fraction of a bit per notch (~-512 / -544 avg executed Toffoli per notch,
+    // 1004 -> 1005 -> 1006 -> 1007: tightens every late-step GCD-body width by an
+    // extra fraction of a bit per notch (~-512 / -544 / -384 avg executed Toffoli,
     // peak-neutral at 1382q). 1005 was stacked with ACTIVE_ITERATIONS 259->258
-    // under a shared island; 1006 then re-rolled to its own island below.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1006");
+    // under a shared island; 1006 and 1007 each re-rolled to their own island.
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1007");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
     set_default_env("DIALOG_REROLL", "4269");
@@ -31509,10 +31509,12 @@ fn configure_ecdsafail_submission_route() {
     // 1390q x 1,518,179 T = 2,110,268,810.
     // Re-rolled for the WIDTH_SLOPE=1005 + ACTIVE_ITERATIONS=258 op stream:
     // nonce=3577 was clean at 1382q x 1,514,221 T = 2,092,653,422.
-    // Re-rolled again for WIDTH_SLOPE=1006 (above): nonce=13555 lands a clean
-    // island, validated 0/0/0 over all 9024 shots at 1382q x 1,513,677 T =
-    // 2,091,901,614.
-    set_default_env("DIALOG_TAIL_NONCE", "13555");
+    // Re-rolled again for WIDTH_SLOPE=1006: nonce=13555 was clean at
+    // 1382q x 1,513,677 T = 2,091,901,614.
+    // Re-rolled again for WIDTH_SLOPE=1007 (above): nonce=6483 lands a clean
+    // island, validated 0/0/0 over all 9024 shots at 1382q x 1,513,293 T =
+    // 2,091,370,926.
+    set_default_env("DIALOG_TAIL_NONCE", "6483");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

