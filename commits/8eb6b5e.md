# 8eb6b5e — Cut the Kaliski iteration counts to pair1 = 397 and pair2 = 396

| | |
| --- | --- |
| Contestant | jtrose24 |
| Date | 2026-06-02 |
| Submission | `5b64367` |
| Commit | `8eb6b5e55f8a0631d2fd0031a2f931d8c8972302` |
| Result | 2309 qubits × 2,409,129 Toffoli = **5,562,678,861** |
| Base | `85ee8e7` (git parent, mpjunior92): 2309 qubits × 2,414,390 Toffoli = 5,574,826,510 |
| Change vs base | qubits ±0, Toffoli −5,261, score −12,147,649 (leaderboard Δ −12,147,649) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The point addition runs two Kaliski inversions, called pair1 and pair2, each
with a fixed number of iterations. This commit lowers the default counts from
399 to 397 (pair1) and from 397 to 396 (pair2). Each removed iteration drops
one forward and one backward iteration body, plus one modular halving or
doubling that undoes the inversion's `2^iters` scale factor. Together that
saves 5,261 average Toffoli at the same 2309 qubits.

Fewer iterations means slow-converging inputs no longer finish their GCD.
Neither cut is clean on its own (pair1 = 397 alone gives 1 classical mismatch,
pair2 = 396 alone gives 5), but the combined op stream draws a clean test set.

## What changed and why it saves Toffoli

**Background: the iteration count.** `with_kal_inv_raw_borrow_v_w_pair`
(`src/point_add/kaliski_inv.rs`) runs `iters` Kaliski iterations forward, calls
the body with the raw inverse in `r`, and then runs the same iterations
backward. Each iteration is a binary-GCD step on `(u, v_w)` with Bézout
coefficients `(r, s)`, and writes one history qubit `m_hist[i]`. Once
`v_w` reaches 0 the remaining iterations only double `r`, so the raw result is
`dx^-1 · 2^iters` (up to sign) for every input that finishes within `iters`
steps. The caller removes the scale:

- pair1 (`build_standard_point_add`, phase `pair1_borrow_dx_halve`):
  `pair1_iters` calls of `mod_halve_inplace_fast` on `lam`;
- pair2 (phase `pair2_double`): `pair2_iters` calls of
  `mod_double_inplace_fast` on `lam`.

See [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) and
[`e739b53`](e739b53.md) for the iteration body.

**The change** (`src/point_add/point_add.rs`, `build_standard_point_add`, both
inside the default-on `stack_2565` branch):

- `pair1_default`: 399 → 397 (`KAL_PAIR1_ITERS`).
- `pair2_default`: 397 → 396 (`KAL_PAIR2_ITERS`).

**Why it saves Toffoli.** Three iterations are removed, each from a forward
and a backward pass, so six iteration bodies disappear. They are the last
ones, which are narrow because the W-TRUNC envelope has shrunk the clipped
loops by then. Three scale-fix steps also go (two halvings, one doubling). The
total is 5,261 Toffoli. The history register `m_hist` is three qubits shorter
in total, but the 2309-qubit peak is set elsewhere and does not move.

## Why it is still correct, and what it risks

- **Probabilistic.** The Kaliski walk needs between about `n` and `2n`
  iterations, depending on the input. An input that needs more than 397
  (pair1) or 396 (pair2) iterations is not finished when the walk stops. Its
  raw inverse is wrong, so `λ` is wrong (a classical mismatch), or the
  backward pass leaves state behind (phase or ancilla failure).
- **Island.** There is no tail nonce in this era. The test set is a hash of
  the op stream. The author swept the iteration counts together with the
  truncation knobs and found that neither cut is clean alone but the pair
  is: 0 classical, 0 phase and 0 ancilla failures over 9,024 shots. The note
  also reports that small changes to the carry-tail `W`, `K0` or the shift22
  window on top of this pair all fail again. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only change is two loop counts that set how far an approximate algorithm
runs, which is iteration/threshold tuning. Runner-up: comparator/width
truncation, since cutting iterations truncates the algorithm in the same
probabilistic way.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 85ee8e7 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 85ee8e7 8eb6b5e -- src/point_add` is
   13 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 8eb6b5e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`,
   `SHIFT22_*` or `LOWQ_*` environment variables set. Expect:
   - 2309 qubits
   - 2,409,129 average Toffoli (rounded)
   - score 5,562,678,861
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with an identical op stream. There is no nonce in
this era, so any other change draws a different test set.

### Patch

```diff
diff --git a/src/point_add/point_add.rs b/src/point_add/point_add.rs
index 405cc55..c845d19 100644
--- a/src/point_add/point_add.rs
+++ b/src/point_add/point_add.rs
@@ -86,7 +86,12 @@ pub(crate) fn build_standard_point_add(
     // at peak) AND avg Toffoli 3653471->3638875, and it is robust on the pair2
     // axis (clean for pair2 in {403,404,405,406}; 403 is the established floor).
     // C1 = 399; stack_2565 default was 401 but sweep found 399 is also clean and saves Toffoli.
-    let pair1_default = if stack_2565_enabled() { 399 } else { 399 };
+    // Lottery re-roll: at the cswap-on/W-TRUNC base, the (pair1=397, pair2=396)
+    // PAIR lands a 9024-clean Fiat-Shamir island (neither drop is clean alone:
+    // p1=397 → 1 mismatch, p2=396 → 5; the combined op-stream re-rolls onto a
+    // lenient input set). Validated 0/0/0, avg-exec 2,409,129 Toffoli × 2309 =
+    // 5,562,678,861 (−0.22% vs the 399/397 baseline 5,574,826,510).
+    let pair1_default = if stack_2565_enabled() { 397 } else { 399 };
     let pair1_iters = std::env::var("KAL_PAIR1_ITERS")
         .ok()
         .and_then(|s| s.parse::<usize>().ok())
@@ -103,8 +108,10 @@ pub(crate) fn build_standard_point_add(
     } else if stack_2565_enabled() {
         // With the uv-cswap merge default-on at safe_iters=254, the follow-up
         // island sweep found pair2=397 clean and lower-Toffoli than pair2=398;
-        // 396/399 fail on this circuit shape.
-        397
+        // 396/399 fail on this circuit shape ALONE — but paired with pair1=397
+        // the (397,396) combination re-rolls onto a fresh 9024-clean island
+        // (see pair1_default note above). 396 is the new default in that pairing.
+        396
     } else {
         398
     };
```

