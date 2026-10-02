# acf2bdb — Re-apply the measured 20-bit apply-phase clean compares on the fused-branch tree

| | |
| --- | --- |
| Contestant | saucegodbased |
| Date | 2026-06-02 |
| Submission | `8ee9ad8` |
| Commit | `acf2bdbd08d8836b5f8e5b4c6a251b7ecd907118` |
| Result | 1698 qubits × 1,838,050 Toffoli = **3,121,008,900** |
| Base | `9b6b9d6` (git parent and frontier at the time, Epistetechnician): 1698 qubits × 1,861,990 Toffoli = 3,161,659,020 |
| Change vs base | qubits ±0, Toffoli −23,940, score −40,650,120 (leaderboard Δ −40,650,120) |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the same edit as the author's earlier [`4b9cfbb`](4b9cfbb.md), applied
again. The fused-branch commit [`9b6b9d6`](9b6b9d6.md) was built on the tree
before `4b9cfbb`, so its line did not have that edit. In the apply loop, the
three 20-bit comparisons that clear the modular add/subtract overflow bit
change from `cmp_lt_into` to `cmp_lt_into_fast`. The first costs 2 Toffoli per
bit and erases its carries with a reverse sweep. The second costs 1 Toffoli per
bit and erases its carries by measurement. There are 1,197 calls, each saving
20 Toffoli, for 23,940 in total. Qubits stay at 1698. The reroll goes from 5 to
4 for the new op stream.

## What changed and why it saves Toffoli

All edits are in `src/point_add/mod.rs`. They match the `4b9cfbb` patch line
for line. Only the reroll value differs.

- `dialog_gcd_cmod_add_materialized_pseudomersenne`, in the
  `overflow_clean` phase:
  `cmp_lt_into(acc[236..], f[236..], acc_ovf)` → `cmp_lt_into_fast(...)`.
  The window is `N − DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` = 256 − 20.
- `dialog_gcd_cmod_sub_materialized_pseudomersenne` and
  `dialog_gcd_cmod_sub_materialized_pseudomersenne_borrowed_subtrahend`, in
  the `underflow_clean` phase. Both compare calls around
  `ccx(ctrl, underflow_pred, acc_ovf)` become `cmp_lt_into_fast`. The first
  call computes `underflow_pred` and the second clears it.
- `configure_ecdsafail_submission_route()`: `DIALOG_REROLL` goes from 5 to 4.
  This is the number of identity `X;X` pairs emitted on `tx[0]` at the start
  of the circuit, used only to reseed the test set.

**The cost difference.**
- `cmp_lt_into` uses a MAJ chain with no carry wires: n CCX forward, then
  n CCX in the inverse sweep, so 2n.
- `cmp_lt_into_fast` writes n carries into fresh wires with n CCX. It then
  erases them with `hmr` + `cz_if`, which costs no Toffoli. See
  [measurement-uncompute](../concepts/measurement-uncompute.md).
- With n = 20, the calls are 399 adds in pair 2's forward apply and 399 × 2
  compares in pair 1's reverse-apply subtracts. That gives 1,197 × 20 = 23,940,
  exactly the measured drop.
- The 21 transient wires live after the raw sum's carry wires are freed, so
  the peak does not move.

## Why it is still correct, and what it risks

The commit changes only how the comparator's carries are erased, and the
measured erase is exact. The compare window is still 20 bits. It can still be
wrong, with probability about 2^−20 per call, when both operands agree on all
20 top bits. A failure like that would leave `acc_ovf` or `underflow_pred`
dirty and show up as ancilla or phase garbage. Reroll 4 draws a clean set for
the new op stream: 0 classical, 0 phase and 0 ancilla failures over 9,024
shots.

## Classification rationale

The commit only changes how carries are erased, from a coherent reverse sweep
to measurement. That is measurement uncompute. It is the second of three
landings of this edit. The third is [`985ae0f`](985ae0f.md), on Gajesh2007's
line.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 9b6b9d6 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 9b6b9d6 acf2bdb -- src/point_add` is
   15 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol acf2bdb -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or other route environment variables set. Expect:
   - 1698 qubits
   - 1,838,050 average Toffoli (rounded)
   - score 3,121,008,900
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL` = 4 and an identical op stream.
Any other change needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 968fef8..9877186 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -23163,7 +23163,8 @@ fn dialog_gcd_cmod_add_materialized_pseudomersenne(
     b.set_phase("dialog_gcd_materialized_special_overflow_clean");
     if dialog_gcd_raw_apply_truncated_clean_enabled() {
         let compare_start = N - dialog_gcd_apply_clean_compare_bits();
-        cmp_lt_into(b, &acc[compare_start..], &f[compare_start..], acc_ovf);
+        // Measured comparator (peak-safe: add carries already freed).
+        cmp_lt_into_fast(b, &acc[compare_start..], &f[compare_start..], acc_ovf);
     } else {
         cmp_lt_into(b, acc, &f, acc_ovf);
     }
@@ -23228,14 +23229,14 @@ fn dialog_gcd_cmod_sub_materialized_pseudomersenne(
         for &q in &a[compare_start..] {
             b.x(q);
         }
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
             underflow_pred,
         );
         b.ccx(ctrl, underflow_pred, acc_ovf);
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
@@ -23390,14 +23391,14 @@ fn dialog_gcd_cmod_sub_materialized_pseudomersenne_borrowed_subtrahend(
         for &q in &a[compare_start..] {
             b.x(q);
         }
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
             underflow_pred,
         );
         b.ccx(ctrl, underflow_pred, acc_ovf);
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
@@ -28027,7 +28028,9 @@ fn configure_ecdsafail_submission_route() {
     // co-tune the Fiat-Shamir reroll (1 -> 5) to land a clean 9024-shot island.
     // Pure Toffoli reduction (1981734 -> 1952382), peak-neutral at 1698.
     // (Validated 0/0/0 over 9024 via eval_circuit.)
-    set_default_env("DIALOG_REROLL", "5");
+    // Apply-phase clean compares also use the measured comparator
+    // (cmp_lt_into_fast); op stream changes, reroll=4 lands a clean island.
+    set_default_env("DIALOG_REROLL", "4");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

