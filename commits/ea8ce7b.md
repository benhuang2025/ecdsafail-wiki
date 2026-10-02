# ea8ce7b — Re-port zuiris's step-11 body notch and sibling-s2 borrow onto odinfree's apply-cut tree (1307 → 1306 qubits)

| | |
| --- | --- |
| Contestant | jieyilong |
| Date | 2026-06-07 |
| Submission | `ff46db2` |
| Commit | `ea8ce7be09c3784da55dd74278c55598bccba47e` |
| Result | 1306 qubits × 1,467,424 Toffoli = **1,916,455,744** |
| Base | `94535d1` (odinfree, git parent and frontier at the time): 1307 qubits × 1,467,440 Toffoli = 1,917,944,080 |
| Change vs base | qubits −1, Toffoli −16, score −1,488,336 (leaderboard Δ −1,488,336) |
| Family | Register and Scratch Allocation → scratch/ancilla reuse |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

`3409fbd` (zuiris) took the peak from 1307 to 1306 with two small edits to the
dialog-GCD forward walk. `94535d1` (odinfree) was built on the tree before
`3409fbd`, so it went back to 1307 qubits while saving Toffoli in the apply
phase. This commit composes the two. It copies just the two live mechanisms of
`3409fbd` onto `94535d1`, without that commit's large inert additions:

- **Step-11 body-width notch.** The add/sub body of walk step 11 drops its top
  2 bits.
- **Sibling-s2 borrow.** At even steps, the scratch pool borrows the sibling
  step's still-clean shift2 cell.

Together they stop steps 10 and 11 from binding the peak, so the peak drops to
1306. The narrower body saves 16 Toffoli. The tail nonce was re-hunted.

## What changed and why it saves qubits

The mechanism is explained in full in [3409fbd](3409fbd.md). In short: steps
10 and 11 of the compressed-block forward walk both have active width 256, so
both ask for `want = 2·body_len − 1 = 509` scratch lanes and tie at the peak.
Both must drop for the peak to fall (see
[peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md)).

1. **`src/point_add/rounds/dialog/mod.rs`, `dialog_gcd_body_carry_trunc_width`.**
   When the notch is on and `step == dialog_gcd_trio_width_notch_step()`
   (default 11), the trim `w` grows by `dialog_gcd_trio_width_notch_extra()`
   (default 2). Step 11's body width goes from 256 to 254, and its `want` from
   509 to 505. Three helper functions are added with the same defaults as in
   `3409fbd`.
   - **One difference from `3409fbd`:** here
     `dialog_gcd_trio_width_notch_enabled()` is *default on*. It returns true
     unless `DIALOG_GCD_TRIO_WIDTH_NOTCH=0`. There is no `set_default_env` pin in
     `mod.rs`.
2. **`src/point_add/rounds/dialog/compressed.rs`, `dialog_gcd_build_composite_scratch`.**
   Inside the `DIALOG_GCD_BORROW_CURRENT_S2` branch: when the notch is on and
   `slot == 0`, also push the sibling's `s2` cell `raw_block[2·group_size + 1]`
   into the borrowed lanes. The guards are the same: the pool is not full, the
   cell is not a duplicate, and it is not in the active `u` or `v`. That cell is
   `|0⟩` throughout this step's body in both the forward and the reverse walk,
   so step 10 allocates one fewer owned lane. It costs no gate.
3. **`src/point_add/mod.rs`**: `DIALOG_TAIL_NONCE` 25012277 → 100879.

None of the other `3409fbd` additions are ported: the clean direct constant
adders, the K2 state-updating reverse pop, the self-tests, `TRACE_COMPOSITE`
and the `R84_DIRECT_MIDSUB_*` branches. None of them ran there either.

**Toffoli.** 2 body bits × 2 Toffoli (gated load and carry) × 4 walks = 16,
which matches the measured −16, exactly as in `3409fbd`.

## Why it is still correct, and what it risks

The sibling-s2 borrow is exact. The wire is provably `|0⟩` while borrowed and is
returned clean.

The notch is a width truncation. Step 11's body is exact as long as bits 254
and 255 of `u` and `v`, and the carry into them, are zero at that step. With the
10-bit width margin this holds in practice, the same argument as the existing
`DIALOG_GCD_BODY_CARRY_BAND_TRIMS`. A violation would give a wrong GCD state,
seen as a classical mismatch and as ancilla garbage after the reverse walk.

The inherited nonce failed on the new op stream. The author screened a 5M-nonce
window with a CUDA GCD filter and confirmed `100879` with the trusted
evaluator: 0 classical, 0 phase and 0 ancilla failures over all 9,024 shots.
See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

As in `3409fbd`, the qubit comes from borrowing a known-clean cell and from
shrinking one step's scratch demand, so scratch/ancilla reuse fits. The work
here is a port that composes two accepted branches. That is not a separate
change-type, so the label follows the mechanism.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 94535d1 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 94535d1 ea8ce7b -- src/point_add` is
   37 lines in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ea8ce7b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set. In particular,
   `DIALOG_GCD_TRIO_WIDTH_NOTCH=0` would switch the new lever off. Expect:
   - 1306 qubits
   - 1,467,424 average Toffoli (rounded)
   - score 1,916,455,744
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=100879` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 24d32c1..eb4954d 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1350,7 +1350,7 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=262 route:
     // nonce 2432 validates 0/0/0 over all 9024 shots at
     // 1309q x 1,497,795 T = 1,960,613,655.
-    set_default_env("DIALOG_TAIL_NONCE", "25012277");
+    set_default_env("DIALOG_TAIL_NONCE", "100879");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
diff --git a/src/point_add/rounds/dialog/compressed.rs b/src/point_add/rounds/dialog/compressed.rs
index d768456..78874e3 100644
--- a/src/point_add/rounds/dialog/compressed.rs
+++ b/src/point_add/rounds/dialog/compressed.rs
@@ -436,6 +436,16 @@ pub(crate) fn dialog_gcd_build_composite_scratch(
         {
             lanes.push(s2);
         }
+        if dialog_gcd_trio_width_notch_enabled() && slot == 0 && group_size >= 2 {
+            let sibling_s2 = raw_block[2 * group_size + 1];
+            if lanes.len() < want
+                && !lanes.contains(&sibling_s2)
+                && !u[..active_width].contains(&sibling_s2)
+                && !v[..active_width].contains(&sibling_s2)
+            {
+                lanes.push(sibling_s2);
+            }
+        }
     }
     let owned = b.alloc_qubits(want - lanes.len());
     lanes.extend_from_slice(&owned);
diff --git a/src/point_add/rounds/dialog/mod.rs b/src/point_add/rounds/dialog/mod.rs
index d878daf..72d8809 100644
--- a/src/point_add/rounds/dialog/mod.rs
+++ b/src/point_add/rounds/dialog/mod.rs
@@ -209,15 +209,38 @@ pub(crate) fn dialog_gcd_body_carry_band_trim(step: usize) -> Option<usize> {
 }
 
 pub(crate) fn dialog_gcd_body_carry_trunc_width(active_width: usize, step: usize) -> usize {
-    let w = dialog_gcd_body_carry_band_trim(step).unwrap_or_else(|| {
+    let mut w = dialog_gcd_body_carry_band_trim(step).unwrap_or_else(|| {
         std::env::var("DIALOG_GCD_BODY_CARRY_TRUNC_W")
             .ok()
             .and_then(|s| s.parse::<usize>().ok())
             .unwrap_or(0)
     });
+    if dialog_gcd_trio_width_notch_enabled() && step == dialog_gcd_trio_width_notch_step() {
+        w = w.saturating_add(dialog_gcd_trio_width_notch_extra());
+    }
     active_width.saturating_sub(w).max(2)
 }
 
+pub(crate) fn dialog_gcd_trio_width_notch_enabled() -> bool {
+    // Default-on successor from aaf9616: the current route inherited its body
+    // geometry, and this one-step notch is needed to reclaim the 1306q tier.
+    std::env::var("DIALOG_GCD_TRIO_WIDTH_NOTCH").ok().as_deref() != Some("0")
+}
+
+pub(crate) fn dialog_gcd_trio_width_notch_step() -> usize {
+    std::env::var("DIALOG_GCD_TRIO_WIDTH_NOTCH_STEP")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(11)
+}
+
+pub(crate) fn dialog_gcd_trio_width_notch_extra() -> usize {
+    std::env::var("DIALOG_GCD_TRIO_WIDTH_NOTCH_EXTRA")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(2)
+}
+
 
 pub(crate) fn dialog_gcd_host_gated_enabled() -> bool {
     // Port of our KAL_GZ_EARLY_RECOVER carry-pool relocation: host the
```

