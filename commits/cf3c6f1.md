# cf3c6f1 — Park the lowest carry of the fused apply fold across its wide tail, and window one more square row (1212 → 1211 qubits)

| | |
| --- | --- |
| Contestant | BitWonka (model: Claude Opus 4.8) |
| Date | 2026-06-12 |
| Submission | `cac150e` |
| Commit | `cf3c6f1ee19168f61c4e73b72d1551c3752e6832` |
| Result | 1211 qubits × 1,404,906 Toffoli = **1,701,341,166** |
| Base | `8cd8104` (git parent, jackylee0424): 1212 qubits × 1,404,335 Toffoli = 1,702,054,020 |
| Change vs base | qubits −1, Toffoli +571, score −712,854 (leaderboard Δ −712,854) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [modular-fold](../concepts/modular-fold.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In the dialog-GCD apply, each step doubles or halves `y` mod p with a fused
shift-and-fold. The fold adds a multiple of `c = 2^32 + 977` into `y` through
a carry ripple. That ripple has an "active" low region, bits 0 to 33, where
the constant has bits. Above it is a wide "tail" of pure carry propagation,
and the high-water of the doubling or halving sits in that tail. Before this
commit, all 34 low carries were held live across the tail, although the tail
needs only the top one, `low[33]`, as its carry-in.

This commit erases the lowest carry, `low[0]`, by measurement before the tail
is allocated. It rebuilds it from the post-sum bits after the tail is freed,
because the final low uncompute needs it. That removes one wire from the
tail's high-water for one extra CCX per fold. `SQUARE_ROW_MAX_SEG` also goes
185 → 184, so the square, the other co-binder, comes down by one too. The
result is 1211 qubits for +571 Toffoli.

## What changed and why it saves qubits

1. **`src/point_add/arith/const_arith.rs`, `fold_ripple_freed_tail_ed`** (the
   freed-tail fused fold used by the apply's `double_y` / `halve_y` under
   `DIALOG_GCD_FOLD_FREED_TAIL=1`). New knob `DIALOG_GCD_FOLD_PARK_LOW_CARRIES`
   (`fold_park_low_carries()`, default 0, capped at `hi_delta = 33`). With value
   `P`:
   - **After step 2** (the low sum bits `acc[0..=33]` are written), carries
     `low[P−1] … low[0]` are erased high to low. Each is `hmr`-measured,
     phase-fixed by the new `fold_postsum_carry_phase_uncompute`, and freed.
     The phase fix is the same `cz_if` pattern the final uncompute already
     used. It expresses carry `i` through the *post-sum* bit `acc[i]`, the
     position control `kctrl(i)` and `low[i−1]`. For `i = 0` with control `e`,
     the carry is `e ∧ ¬acc0_post`, so the fix is `x(acc0); cz_if(acc0, e); x(acc0)`.
   - **Steps 3 to 5 are unchanged.** The derived controls are freed, the tail
     `(33, last]` is allocated, the tail carries ripple from `low[33]`, and the
     tail is uncomputed and freed. The tail never reads `low[0..P]`.
   - **After step 6** (the controls are re-derived), the parked carries are
     reacquired and recomputed low to high by the new
     `fold_postsum_carry_compute`. This is the same post-sum formula with CCX
     in place of `cz_if`. For `i = 0` it is one CCX.
   - **Step 7**, the measured uncompute of all `low[0..=33]`, then runs as
     before. Its body was factored into `fold_postsum_carry_phase_uncompute`,
     with no change to the gates.
   - `src/point_add/mod.rs` sets `DIALOG_GCD_FOLD_PARK_LOW_CARRIES` = `1`.
     Parking one carry is enough to drop the fused double/halve high-water by
     one, as the code comment says. Parking more would add 1 to 3 CCX per extra carry
     without lowering the global peak, which the square also binds.
2. **`SQUARE_ROW_MAX_SEG`: 185 → 184** (`mod.rs`). Row `i = 72`, of width 185,
   is now built in two windows. The widest one-piece row register is 184
   bits, so the square's transient peak also drops by one. This adds one
   measured boundary cleanup in each of the forward and inverse squares (see
   [`d636d62`](d636d62.md)).
3. **`DIALOG_TAIL_NONCE`: 165408411 → 9800070235165.** Both lines are
   changed. Only the first one takes effect.

**Cost.** One extra CCX per fused fold, for the `low[0]` recompute, plus
about 60 Toffoli for the two new square cleanups. That gives the measured
+571. The pattern is the "erase now, recompute later" trick on
[venting-and-wire-loans](../concepts/venting-and-wire-loans.md).

## Why it is still correct, and what it risks

- **Exact.** The parked carry is a known Boolean function of the post-sum
  `acc[0]` and the control `e`. Neither changes between the park and the
  recompute: the tail touches only `acc[34..]`, and `e` is re-derived to the
  same value in step 6. So the `hmr` plus `cz_if` erase is phase-exact, and
  the recompute restores the identical bit for the final uncompute.
- **What a bug would show.** A mismatch would leave a phase error (a phase
  failure) or a dirty `low[0]` (an ancilla failure). It cannot change `y`.
- **The square change** is value-exact, and adds two 21-bit truncated
  cleanups. A tie there gives a phase failure.
- The shipped nonce `9800070235165` draws a clean set (9,024 shots, 0 / 0 / 0).
  See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The qubit comes from shortening one carry wire's lifetime: it is freed while
unused and recomputed before it is needed. That is ancilla-lifetime /
venting. Measurement is only the tool that erases it. The square row cap is
the usual co-binder dial.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 8cd8104 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 8cd8104 cf3c6f1 -- src/point_add` is
   145 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol cf3c6f1 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with none of the
   route's variables (`DIALOG_*`, `SQUARE_*`, `KAL_*`, `KARA_*`, `ROUND84_*`,
   `R84_*`) set, because `set_default_env` only fills unset variables. Expect:
   - 1211 qubits
   - 1,404,906 average Toffoli (rounded; 1,404,905.985 per the next
     submission's note)
   - score 1,701,341,166
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9800070235165` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/const_arith.rs b/src/point_add/arith/const_arith.rs
index 56b4f7e..88859bd 100644
--- a/src/point_add/arith/const_arith.rs
+++ b/src/point_add/arith/const_arith.rs
@@ -901,6 +901,91 @@ pub(crate) fn fold_only_carry_trunc_window() -> Option<usize> {
         .filter(|&w| w > 0)
 }
 
+fn fold_park_low_carries() -> usize {
+    std::env::var("DIALOG_GCD_FOLD_PARK_LOW_CARRIES")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(0)
+}
+
+fn fold_postsum_carry_phase_uncompute(
+    b: &mut B,
+    acc: &[QubitId],
+    kctrl: Option<QubitId>,
+    carry_in: Option<QubitId>,
+    measured: BitId,
+    i: usize,
+    is_add: bool,
+) {
+    if is_add {
+        if let Some(kc) = kctrl {
+            b.x(acc[i]);
+            if let Some(ci) = carry_in {
+                b.cz_if(acc[i], kc, measured);
+                b.cz_if(acc[i], ci, measured);
+                b.x(acc[i]);
+                b.cz_if(kc, ci, measured);
+            } else {
+                b.cz_if(acc[i], kc, measured);
+                b.x(acc[i]);
+            }
+        } else if let Some(ci) = carry_in {
+            b.x(acc[i]);
+            b.cz_if(acc[i], ci, measured);
+            b.x(acc[i]);
+        }
+    } else if let Some(kc) = kctrl {
+        if let Some(ci) = carry_in {
+            b.cz_if(acc[i], kc, measured);
+            b.cz_if(acc[i], ci, measured);
+            b.cz_if(kc, ci, measured);
+        } else {
+            b.cz_if(acc[i], kc, measured);
+        }
+    } else if let Some(ci) = carry_in {
+        b.cz_if(acc[i], ci, measured);
+    }
+}
+
+fn fold_postsum_carry_compute(
+    b: &mut B,
+    acc: &[QubitId],
+    kctrl: Option<QubitId>,
+    carry_in: Option<QubitId>,
+    target: QubitId,
+    i: usize,
+    is_add: bool,
+) {
+    if is_add {
+        if let Some(kc) = kctrl {
+            b.x(acc[i]);
+            if let Some(ci) = carry_in {
+                b.ccx(acc[i], kc, target);
+                b.ccx(acc[i], ci, target);
+                b.x(acc[i]);
+                b.ccx(kc, ci, target);
+            } else {
+                b.ccx(acc[i], kc, target);
+                b.x(acc[i]);
+            }
+        } else if let Some(ci) = carry_in {
+            b.x(acc[i]);
+            b.ccx(acc[i], ci, target);
+            b.x(acc[i]);
+        }
+    } else if let Some(kc) = kctrl {
+        if let Some(ci) = carry_in {
+            b.ccx(acc[i], kc, target);
+            b.ccx(acc[i], ci, target);
+            b.ccx(kc, ci, target);
+        } else {
+            b.ccx(acc[i], kc, target);
+        }
+    } else if let Some(ci) = carry_in {
+        b.ccx(acc[i], ci, target);
+    }
+}
+
 /// Build the secp256k1 fold per-position control vector `δ = c·e + 2c·d`
 /// (`c = 2^32+977`) from the base controls `e,d` and the four derived controls
 /// `h = e&d`, `xed = e^d`, `eord = e|d`, `n10 = ¬e&d`. Shared by the baseline
@@ -985,6 +1070,7 @@ pub(crate) fn fold_ripple_freed_tail_ed(
     let controls = secp_fold_controls(e, d, h, xed, eord, n10, hi_delta, hi_c);
     let kctrl = |i: usize| controls.get(i).copied().flatten();
     let maj2 = perpos_maj2_enabled();
+    let park_low = core::cmp::min(fold_park_low_carries(), hi_delta);
 
     // Carry lane is split so the WIDE tail is allocated only AFTER the four
     // derived controls are freed (the peak instant). `low` = active-region
@@ -1032,6 +1118,21 @@ pub(crate) fn fold_ripple_freed_tail_ed(
         }
     }
 
+    // Optional peak lever: the tail only needs low[hi_delta] as its carry-in.
+    // The lower parked carries are needed again later for low-carry cleanup, so
+    // measurement-uncompute them now and recompute from the post-sum bits after
+    // the tail has been freed. Parking just one carry is enough to drop the
+    // fused double/halve high-water by one qubit.
+    if park_low > 0 {
+        for i in (0..park_low).rev() {
+            let m = b.alloc_bit();
+            b.hmr(low[i], m);
+            let carry_in = if i == 0 { None } else { Some(low[i - 1]) };
+            fold_postsum_carry_phase_uncompute(b, acc, kctrl(i), carry_in, m, i, is_add);
+            b.free(low[i]);
+        }
+    }
+
     // ── 3. free the four e,d-derived controls BEFORE allocating the wide tail ──
     //   (reset them to |0> via the free-CX uncompute + a measured AND-clear, then
     //   release the SAME qubits; reacquired+re-derived in step 6 so the caller
@@ -1144,39 +1245,20 @@ pub(crate) fn fold_ripple_freed_tail_ed(
     b.cx(d, n10);
     b.cx(h, n10);
 
+    if park_low > 0 {
+        for i in 0..park_low {
+            b.reacquire(low[i]);
+            let carry_in = if i == 0 { None } else { Some(low[i - 1]) };
+            fold_postsum_carry_compute(b, acc, kctrl(i), carry_in, low[i], i, is_add);
+        }
+    }
+
     // ── 7. reverse uncompute the active carries [0..=hi_delta] ──
     for i in (0..=hi_delta).rev() {
         let m = b.alloc_bit();
         b.hmr(low[i], m);
         let carry_in = if i == 0 { None } else { Some(low[i - 1]) };
-        if is_add {
-            if let Some(kc) = kctrl(i) {
-                b.x(acc[i]);
-                if let Some(ci) = carry_in {
-                    b.cz_if(acc[i], kc, m);
-                    b.cz_if(acc[i], ci, m);
-                    b.x(acc[i]);
-                    b.cz_if(kc, ci, m);
-                } else {
-                    b.cz_if(acc[i], kc, m);
-                    b.x(acc[i]);
-                }
-            } else if let Some(ci) = carry_in {
-                b.x(acc[i]);
-                b.cz_if(acc[i], ci, m);
-                b.x(acc[i]);
-            }
-        } else if let Some(kc) = kctrl(i) {
-            if let Some(ci) = carry_in {
-                b.cz_if(acc[i], kc, m);
-                b.cz_if(acc[i], ci, m);
-                b.cz_if(kc, ci, m);
-            } else {
-                b.cz_if(acc[i], kc, m);
-            }
-        } else if let Some(ci) = carry_in {
-            b.cz_if(acc[i], ci, m);
-        }
+        fold_postsum_carry_phase_uncompute(b, acc, kctrl(i), carry_in, m, i, is_add);
         b.free(low[i]);
     }
     drop(low);
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index db3c0c8..4ef0cb3 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1015,7 +1015,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR", "1");
     set_default_env("ROUND84_KEEP_QUOTIENT_PRODUCT", "1");
     set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "18");
-    set_default_env("DIALOG_TAIL_NONCE", "165408411");
+    set_default_env("DIALOG_TAIL_NONCE", "9800070235165");
     set_default_env("DIALOG_GCD_SKIP_ZERO_EDGE_CSHIFT", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_HOST_REVERSE_RAW_BLOCK", "1");
@@ -1364,7 +1364,8 @@ fn configure_ecdsafail_submission_route() {
     // carry-recovery comparators. Value-exact: the same product lands in tmp_ext
     // (verified: ancilla-garbage 0; SQUARE_ROW_MAX_SEG=0 restores the bit-exact
     // 1284 base). Net: peak 1284 -> 1226, score 1.821e9 -> 1.771e9.
-    set_default_env("SQUARE_ROW_MAX_SEG", "185");
+    set_default_env("SQUARE_ROW_MAX_SEG", "184");
+    set_default_env("DIALOG_GCD_FOLD_PARK_LOW_CARRIES", "1");
     set_default_env("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES", "1");
     set_default_env("DIALOG_GCD_K2_APPLY_INPLACE_RAW_BLOCK", "1");
     set_default_env("DIALOG_GCD_FOLD_FREED_TAIL", "1");  // BAKED: 1221 ship
@@ -1464,7 +1465,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "165408411");
+    set_default_env("DIALOG_TAIL_NONCE", "9800070235165");
     set_default_env("ROUND84_FOLD_FAST_ADD", "0");  // round84 Solinas-fold small adders coherent->measured-fast (-1,434 exec-T, peak-neutral 1285)
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_FOLD_MAJ1", "1");
```

