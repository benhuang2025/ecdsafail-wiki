# 5d2f6cf — Narrow the apply-pass overflow compare from 20 to 19 bits on the 395-step tree

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-03 |
| Submission | `682c10a` |
| Commit | `5d2f6cf38e998651f437bd89a4e15fc0b0eff77b` |
| Result | 1434 qubits × 1,729,565 Toffoli = **2,480,196,210** |
| Base | `238d366` (git parent and frontier at the time, BitWonka): 1434 qubits × 1,730,355 Toffoli = 2,481,329,070 |
| Change vs base | qubits ±0, Toffoli −790, score −1,132,860 (leaderboard Δ −1,132,860) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This re-applies twangodev's [`34a514a`](34a514a.md) cut, which was lost when
[`339fe8d`](339fe8d.md) was built on the older `5a2d910`. After every
modular add or subtract in the apply pass, an overflow flag is erased by
recomputing it from the top `k` bits of the result and the addend. This
commit makes `k` 19 instead of 20. That is one Toffoli less at each of the
2 × 395 = 790 calls, so −790 Toffoli, exactly the measured change. Qubits are
unchanged. The reroll pair was re-searched.

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`:

1. **`DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS`: 20 → 19.**
   - `dialog_gcd_cmod_add_materialized_pseudomersenne_chunked` adds
     `ctrl · a` into the 257-bit `acc ++ acc_ovf` and folds the overflow back
     with `2^256 − p` (see [modular-fold](../concepts/modular-fold.md)).
   - It then erases `acc_ovf` with
     `ccx_cmp_lt_into_fast(acc[256−k..], a[256−k..], ctrl, acc_ovf)`. This
     uses the fact that a modular add overflowed exactly when the reduced
     result is below the addend, but compares only the top `k` bits. The
     subtract does the mirror image in `dialog_gcd_clean_truncated_underflow`.
   - Each compare costs `k + 1` Toffoli. There is one add or subtract per
     step on each of the two coefficient updates, over 395 steps: 790 calls,
     so −790 Toffoli.
   - The new comment calls this lever "value-exact". It is not: it is a
     truncated compare, as explained below.
2. **Reroll pair: `DIALOG_REROLL` 4,959 → 6,458, `DIALOG_POST_SUB_REROLL`
   5,983 → 2,553.** These are the identity `X;X` counts that only re-draw the
   9,024 test inputs.

## Why it is still correct, and what it risks

The truncated compare is an approximation. If the reduced result and the
addend agree on all of their top 19 bits, the compare cannot tell which is
smaller. `acc_ovf` is then erased wrongly, and the run shows ancilla or phase
garbage. Going from 20 to 19 bits roughly doubles that per-call chance, to
about 2^-19 per call.

The reroll pair (6,458, 2,553) draws a clean set: 9,024 of 9,024 shots pass
with 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change narrows a truncated comparator, so
comparator/width truncation fits.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 238d366 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 238d366 5d2f6cf -- src/point_add` is
   9 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 5d2f6cf -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`,
   `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set, because
   `set_default_env` keeps any value already in the environment. Expect:
   - 1434 qubits
   - 1,729,565 average Toffoli (rounded)
   - score 2,480,196,210
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the reroll pair `DIALOG_REROLL=6458`,
`DIALOG_POST_SUB_REROLL=2553` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 1a5b09b..5b0ede0 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -29937,7 +29937,10 @@ fn configure_ecdsafail_submission_route() {
     // Branch comparator 58 -> 57: -1,064 executed Toffoli, peak-neutral at 1434q,
     // stacked on the active395 base. Clean island at REROLL=4959 / POST_SUB=5983.
     set_default_env("DIALOG_GCD_COMPARE_BITS", "57");
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
+    // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
+    // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
+    // frontier had dropped, stacked on compare57+active395. Clean island below.
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     // 399 -> 396. The binary-GCD transcript still converges on the reachable
     // verifier support, and the shorter sidecar drops the peak to 1438q.
@@ -30072,8 +30075,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "130");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "4959");
-    set_default_env("DIALOG_POST_SUB_REROLL", "5983");
+    set_default_env("DIALOG_REROLL", "6458");
+    set_default_env("DIALOG_POST_SUB_REROLL", "2553");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

