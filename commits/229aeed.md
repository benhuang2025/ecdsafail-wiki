# 229aeed — Cut the dialog GCD from 260 to 259 steps on newjordan's slope-1008 tree

| | |
| --- | --- |
| Contestant | 10d9e |
| Date | 2026-06-05 |
| Submission | `3bc5fbb` |
| Commit | `229aeed59e650fb155c034062c082b6502502cb8` |
| Result | 1320 qubits × 1,560,885 Toffoli = **2,060,368,200** |
| Base | `94e9418` (newjordan, submission `9510ccc`): 1320 qubits × 1,564,001 Toffoli = 2,064,481,320 |
| Change vs base | qubits ±0, Toffoli −3,116, score −4,113,120 |
| Leaderboard Δ | −498,960, measured against the frontier at the time, `c64c03f` (PhantasticUniverse, 1320 × 1,561,263 = 2,060,867,160), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The early-June circuit divides with the `DIALOG_GCD` route: a reversible
binary GCD runs a fixed number of steps on `(u, v)`, records its branch bits,
and an "apply" loop replays the bits on the Bézout pair `(x, y)`. The step
count is a pin, `DIALOG_GCD_ACTIVE_ITERATIONS`. The 1320-qubit
"apply teardown" lineage had raised it from 258 back to 260 to avoid phase
failures.

This commit lowers it to 259 on newjordan's tree and re-hunts the tail
nonce. Removing one step saves 3,116 average Toffoli. Qubits stay at 1320.
The cost is that a few more inputs do not finish their GCD in time, so a
clean nonce is harder to find. The author found one (754) after about 790
tries.

## What changed and why it saves Toffoli

All circuit changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_ACTIVE_ITERATIONS`: 260 → 259.**
   - `dialog_gcd_active_iterations()` returns this value, and every GCD loop
     runs that many steps: the forward transcript
     (`emit_dialog_gcd_compressed_sidecar_tobitvector_steps`), the apply on
     `(x, y)` and their reverses.
   - A forward step computes two branch bits (`b0` = parity of `v`,
     `b0_and_b1` = `b0` and `u > v` from a truncated compare), cswaps `u` and
     `v`, subtracts under `b0`, and shifts `v` right. With `DIALOG_GCD_K2=1` it
     can shift a second time and records that bit too.
   - An apply step on `(x, y)` doubles `y` mod p (twice under K2), adds `x`
     into `y` under `b0`, and cswaps `x` and `y` under `b0_and_b1`. All of that
     is on full 256-bit registers.
   - So dropping the last step saves its narrow forward and reverse
     bitvector work plus a full apply step in every apply pass. The author
     measured −3,116 average Toffoli, and the peak stays at 1320.
2. **`DIALOG_TAIL_NONCE`: 1876 → 754.** `build_builder()` ends with 48
   `X;X` pairs, each on `tx[0]` or `tx[1]` by one nonce bit. They are exact
   identities. They change only the op-stream hash, which picks the 9,024
   Fiat–Shamir test inputs. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
3. **New file `src/point_add/memory/2026-06-05-width-envelope-sweep-1382q.md`**,
   the author's session log (not read by the build). It says that on the
   older 1382-qubit tree a 259 → 258 cut also removed a scratch row and
   dropped the peak 1390 → 1382. It records break counts per lever at the
   inherited nonce and how two levers' break sets can partly cancel. It
   also gives a recipe for a classical pre-filter that checks both GCD inputs
   per test case (`dx = Px − Qx` and the second factor) against the width
   envelope, plus the usage of the author's nonce searcher
   `src/bin/island_search_jac.rs` (outside `src/point_add`).

## Why it is still correct, and what it risks

- The cut is probabilistic. A binary GCD on two 256-bit numbers needs a
  data-dependent number of steps. With K=2 almost every input finishes within
  259, but a rare input that needs step 260 leaves `v ≠ 0` and an incomplete
  transcript. Its result is wrong (classical failure), and the unfinished
  registers can leave phase garbage when they are uncomputed.
- At the inherited nonce the author counted 5 classical and 5 phase breaks
  for 259 (11 + 3 for 258, 15 + 5 for 257).
- Nonce 754 draws a clean set: 9,024 of 9,024 shots, with 0 classical,
  0 phase and 0 ancilla failures.

## Classification rationale

The published label is comparator/width truncation, but the diff changes no
width or comparator. It shortens the GCD loop by one step, which is
iteration/threshold tuning (the label that [`c64c03f`](c64c03f.md) got for the
same cut). The memory file is documentation only.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 94e9418 -- src/point_add`.
   - Do not start from the git parent `c64c03f`. That is PhantasticUniverse's
     tree, which has the same 259 cut but also `KAL_DOUBLE_CARRY_TRUNC_W=22`
     and `DIALOG_GCD_WIDTH_SLOPE_X1000=1005`. Diffing against the parent would
     wrongly show this commit widening the double window back to 23 and moving
     the slope to 1008.
   - Against `94e9418`, `git diff --ignore-cr-at-eol 94e9418 229aeed -- src/point_add`
     is 81 lines in 2 files, 69 of them the new memory file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 229aeed -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*`, `DIALOG_*` or `SUB4_*` environment variables set, because they
   override the defaults. Expect:
   - 1320 qubits
   - 1,560,885 average Toffoli (rounded)
   - score 2,060,368,200
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `754` and an identical op stream.
Any other change needs a new nonce hunt.

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
index b58850c..46a415e 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31605,7 +31605,12 @@ fn configure_ecdsafail_submission_route() {
     // 258 -> 260: re-spends two active GCD rows after the 1320q apply teardown
     // below. This removes the residual phase failures at the custom-five seed
     // while still staying below the 1320q x current-best Toffoli budget.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "260");
+    // 260 -> 259: drops one GCD body/reverse iteration from the active band
+    // (-3,116 avg executed Toffoli, peak-neutral at 1320q). The apply-teardown
+    // lineage (teddyjfpender/newjordan) had raised this back to 260; the
+    // transcript still converges on the verifier support, so the iteration is
+    // reclaimable on the 1320q structure via the tail-nonce island below.
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "259");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -31793,7 +31798,10 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the active260 custom-five hosted-boundary apply teardown:
     // nonce=108 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1320q x 1,565,417 T = 2,066,350,440.
-    set_default_env("DIALOG_TAIL_NONCE", "1876");
+    // Re-rolled for ACTIVE_ITERATIONS=259 on the newjordan slope1008 / 1320q
+    // apply-teardown base: nonce=754 lands a clean island, validated 0/0/0 over
+    // all 9024 shots at 1320q x 1,560,885 T = 2,060,368,200.
+    set_default_env("DIALOG_TAIL_NONCE", "754");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

