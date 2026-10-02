# f37a0bc — Run the dialog GCD for 261 steps instead of 262

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-06-06 |
| Submission | `a127dbe` |
| Commit | `f37a0bcccec2362431d6e815e9ef28dbd8d6741a` |
| Result | 1309 qubits × 1,494,942 Toffoli = **1,956,879,078** |
| Base | `11ceae2` (odinfree, git parent and frontier at the time): 1309 qubits × 1,497,795 Toffoli = 1,960,613,655 |
| Change vs base | qubits ±0, Toffoli −2,853, score −3,734,577 (leaderboard Δ +3,724,105: the leaderboard measured it against `a6a92a4`, 1,953,154,973, which was promoted a minute later from this tree and scored better) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

[11ceae2](11ceae2.md) raised the dialog-GCD length from 258 to 262 steps to
make clean nonces easier to find. This commit takes one of those steps back:
`DIALOG_GCD_ACTIVE_ITERATIONS` goes from 262 to 261. Every forward walk,
apply pass and reverse walk is one step shorter. That saves 2,853 Toffoli,
almost all of it in the two apply passes. Qubits are unchanged. Fewer steps
means more inputs that do not finish the GCD in time, so a new tail nonce was
hunted.

## What changed and why it saves Toffoli

All changes are in `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`.

1. **`DIALOG_GCD_ACTIVE_ITERATIONS`: 262 → 261.**
   - `dialog_gcd_active_iterations()` (`rounds/dialog/config.rs`) is the loop
     bound for every walk, apply and reverse-walk emitter in
     `rounds/dialog/`. Background on the route is in [8316db1](8316db1.md).
   - The dropped step is 261. There the walk's `active_width` is only 2 bits,
     so the forward and reverse walk steps are nearly free. The cost is in the
     apply pass of each of the two divisions. Each apply step is:
     - a modular double (or halve) of `y`, fused with the K2 second shift;
     - a controlled 256-bit modular add (or subtract) of `x` into `y`, with
       its overflow clean;
     - a 256-wide controlled swap, one Toffoli per bit.
     That is about 1,400 Toffoli per division per step, and 2,853 in total.
   - The body band trim `"0,1"` keeps band size `ceil(261 / 2) = 131`, so it
     still trims steps 131 and up.
2. **`DIALOG_TAIL_NONCE`: 2432 → 5646**, the fixed 48-pair `X;X` identity
   tail that reseeds the 9,024 test inputs.
3. The comments are updated to match.

## Why it is still correct, and what it risks

The K2 binary GCD of `(p, dx)` (and of `(p, c)` for the second division)
needs an input-dependent number of steps to reach its terminal state. Once
converged, extra steps are no-ops on `(u, v)`. An input that needs more than
261 steps is not finished. It gives a wrong slope and therefore a wrong output
point (a classical failure), and the reverse walk leaves garbage (an ancilla or
phase failure). Dropping a step adds those inputs to the hard set. The
classical pre-filter from [88079e6](88079e6.md) flags them as `NonConvergence`.

All the other truncations are unchanged: the width envelope, the 49-bit
branch comparator, the body trim and the 20-bit apply-clean comparator. The
shipped nonce `5646` draws a test set with 0 classical, 0 phase and 0 ancilla
failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is a loop count, so iteration/threshold tuning fits.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 11ceae2 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 11ceae2 f37a0bc -- src/point_add` is
   14 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol f37a0bc -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` only fills
   in unset variables. Expect:
   - 1309 qubits
   - 1,494,942 average Toffoli (rounded)
   - score 1,956,879,078
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=5646` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index d9bb949..5dab580 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1080,11 +1080,11 @@ fn configure_ecdsafail_submission_route() {
     // 260 -> 259 after the 1320q apply teardown: saves one GCD body/reverse row.
     // Stacked with KAL_DOUBLE_CARRY_TRUNC_W=22, the nonce below lands the clean
     // 1320q island while improving the custom-five seed's Toffoli count.
-    // 258 -> 262 on the lowq0 final-chunk route: spend four GCD rows from the
+    // 258 -> 261 on the lowq0 final-chunk route: spend three GCD rows from the
     // recovered fast-final Toffoli budget to remove most nonconvergence pressure
     // while staying under the 1309q round84 peak. Re-hunted with the GCD filter
-    // and quantum-confirmed at tail nonce 2432.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "262");
+    // and quantum-confirmed at tail nonce 5646.
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "261");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -1324,10 +1324,10 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the APPLY_CLEAN_COMPARE_BITS 21 -> 20 re-tightening above:
     // nonce 721381 lands a clean Fiat-Shamir island, validated 0/0/0 over all
     // 9024 shots at 1309q x 1,503,355 T = 1,967,891,695.
-    // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=262 route:
-    // nonce 2432 validates 0/0/0 over all 9024 shots at
-    // 1309q x 1,497,795 T = 1,960,613,655.
-    set_default_env("DIALOG_TAIL_NONCE", "2432");
+    // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=261 route:
+    // nonce 5646 validates 0/0/0 over all 9024 shots at
+    // 1309q x 1,494,942 T = 1,956,879,078.
+    set_default_env("DIALOG_TAIL_NONCE", "5646");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

