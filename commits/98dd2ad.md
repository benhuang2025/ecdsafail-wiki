# 98dd2ad — Extend conditional-replay erasure to the reverse-walk branch bit, the apply overflow/underflow cleans and the full-width modular-add flags

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-08 |
| Submission | `52c6b6b` |
| Commit | `98dd2ad505a0eb03e315294d6bf4185afec0ab1c` |
| Result | 1297 qubits × 1,386,820 Toffoli = **1,798,705,540** |
| Base | `2dcf00d` (jackylee0424, git parent and frontier at the time): 1297 qubits × 1,403,733 Toffoli = 1,820,641,701 |
| Change vs base | qubits ±0, Toffoli −16,913, score −21,936,161 (leaderboard Δ −21,936,161) |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

[bfd3fa6](bfd3fa6.md) introduced "conditional replay" for the apply-phase
chunk-boundary carries. A one-bit flag that the base erased by recomputing
it (a comparator plus a CCX into the flag, on every shot) is instead
measured in the X basis and reset, at no Toffoli cost. Only when the
measurement outcome is 1 does a classically conditioned block recompute the
flag's value and cancel the phase with a CZ. The score counts *executed*
Toffoli, so the recompute costs about half on average, and the CCX into the
flag disappears.

This commit applies the same trick at three more kinds of flag erasure:
- the branch bit erased in each reverse dialog-GCD walk step;
- the overflow and underflow cleans of the apply-phase modular add and
  subtract;
- the internal flag of the full-width `mod_add_qq_fast` /
  `mod_sub_qq_fast` adders.

Together they save 16,913 average Toffoli at the same 1297 qubits. Every
replacement is exact.

## What changed and why it saves Toffoli

Three new pins in `configure_ecdsafail_submission_route()`
(`src/point_add/mod.rs`), each read by a new switch:

1. **`DIALOG_GCD_REVERSE_BRANCH_CONDITIONAL_REPLAY=1`**
   (`dialog_gcd_reverse_branch_conditional_replay_enabled()` in
   `rounds/dialog/config.rs`).
   - In the `..._tobitvector_reverse_branch_bits` phase of
     `emit_dialog_gcd_compressed_sidecar_tobitvector_steps_reverse_block_lifecycle`
     (`rounds/dialog/compressed.rs`), the branch bit `b0_and_b1 = b0 ∧ (u > v)`
     on the top `k` bits was erased by re-running the fused truncated
     comparator `dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted`. That
     costs `k` carry CCX plus one CCX into the bit.
   - It is now `hmr(b0_and_b1, phase)` followed by the new
     `dialog_gcd_cmp_gt_truncated_phase_conditioned_hosted` in
     `rounds/dialog/mod.rs`. That function compares the same top-`k`
     windows (`v[start..] < u[start..]`) under `push_condition(phase)`,
     applies `cz(b0, carry_out)`, and uncomputes by measurement. It keeps
     the same carry hosting as the original: a borrowed slice, a partial
     borrow plus owned remainder, or self-allocation. That is why the new
     `cmp_lt_phase_conditioned_borrowed_carries` exists in
     `arith/compare.rs`.
   - Cost per step goes from `k + 1` to about `k / 2`. On this route
     `k = min(SCHEDULE[step], 48, active_width)`, which sums to 9,930 over
     the 258 steps. Two reverse walks give about
     2 × (9,930 / 2 + 258) ≈ 10,450 Toffoli.
2. **`DIALOG_GCD_SPECIAL_CLEAN_CONDITIONAL_REPLAY=1`**
   (`dialog_gcd_special_clean_conditional_replay_enabled()`).
   - **Overflow clean** in `dialog_gcd_cmod_add_materialized_pseudomersenne_chunked`:
     the old `ccx_cmp_lt_into_fast(acc[top k], a[top k], ctrl, acc_ovf)`
     becomes `hmr(acc_ovf, phase)` followed by
     `cmp_lt_phase_conditioned_with_cin(acc[top k], a[top k], c_in, ctrl, phase)`.
   - **Underflow clean** in `dialog_gcd_clean_truncated_underflow`: the old
     `cx(ctrl, acc_ovf)` + `ccx_cmp_lt_into_fast(...)` meant
     `acc_ovf = ctrl ⊕ (ctrl ∧ cmp)`. The new code measures `acc_ovf`, adds
     `z_if(ctrl, phase)` for the `ctrl` term, and runs the conditioned
     compare for the `ctrl ∧ cmp` term.
   - `k` is 20 (21–23 at the ten override steps), so each call goes from
     about 21 to about 10 Toffoli. Over 2 × 258 calls that is about
     −5,690.
3. **`MOD_FAST_FLAG_CONDITIONAL_REPLAY=1`**, read inline in `arith/modular.rs`
   by `mod_add_qq_fast`, `mod_add_qq_fast_from_zero` and `mod_sub_qq_fast`.
   - These full-width modular adders end with
     `cmp_lt_into_fast(acc_ext[..n], a_ext[..n], flag)` to clear their
     reduction flag, at about 256 CCX.
   - That becomes `hmr(flag, phase)` plus the new
     `cmp_lt_phase_conditioned(acc, a, phase)`. This is an uncontrolled
     conditioned compare, whose phase fix is a `Z` on the carry-out
     (`b.cz(u[n−1], u[n−1])` emits a `Z`).
   - Each call saves about 128 Toffoli on average. These adders are used
     outside the GCD (the point-add's linear steps and some multiply
     helpers). The remaining roughly 780 Toffoli of the measured total
     matches about six such calls. I did not count the calls in a build.
4. **`DIALOG_TAIL_NONCE`: 3967248 → 9100005549463.**

The three estimates add up to about −16,900, against −16,913 measured. The
emitted Toffoli count barely moves, because the recompute gates are all
still emitted, only conditioned. See
[measurement-uncompute](../concepts/measurement-uncompute.md) and
[scoring-and-validation](../concepts/scoring-and-validation.md).

## Why it is still correct, and what it risks

Every replacement is exact. Each erased flag holds exactly the value that
the conditioned block recomputes, from registers that are in the same state
as when the flag was written:
- the reverse walk has restored `u` and `v` to the branch point;
- the apply's `acc` and `a` are unchanged since the clean target was set;
- the modular adder's flag is exactly `acc < a` at that point, which is
  why the old code could clear it with that compare.

The X-basis measurement leaves the phase `(−1)^(phase · flag)`, and the
conditioned CZ or Z removes it. The truncated comparisons are the same
truncations as before, so no new hard inputs appear, and Lambda does not
change. A slip would show up as phase garbage.

The shipped nonce `9100005549463` draws a test set with 0 classical,
0 phase and 0 ancilla failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

All three levers replace a recompute-to-erase with a measurement plus a
conditioned phase repair. That is measurement uncompute.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 2dcf00d -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 2dcf00d 98dd2ad -- src/point_add` is
   202 lines in 6 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 98dd2ad -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or `MOD_*` environment variables set. Expect:
   - 1297 qubits
   - 1,386,820 average Toffoli (rounded)
   - score 1,798,705,540
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9100005549463` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/compare.rs b/src/point_add/arith/compare.rs
index f2accb2..2f3443f 100644
--- a/src/point_add/arith/compare.rs
+++ b/src/point_add/arith/compare.rs
@@ -327,6 +327,60 @@ pub(crate) fn cmp_lt_phase_conditioned_with_cin(
     b.pop_condition();
 }
 
+pub(crate) fn cmp_lt_phase_conditioned_borrowed_carries(
+    b: &mut B,
+    u: &[QubitId],
+    v: &[QubitId],
+    c_in: QubitId,
+    carries: &[QubitId],
+    ctrl: QubitId,
+    phase: BitId,
+) {
+    let n = u.len();
+    assert_eq!(v.len(), n);
+    assert!(n > 0);
+    assert!(carries.len() >= n);
+
+    b.push_condition(phase);
+    for &q in u {
+        b.x(q);
+    }
+    cmp_lt_fast_prefix_window_forward(b, u, v, c_in, carries, ctrl, &[]);
+    b.cz(ctrl, u[n - 1]);
+    cmp_lt_fast_prefix_window_inverse(b, u, v, c_in, carries);
+    for &q in u {
+        b.x(q);
+    }
+    b.pop_condition();
+}
+
+pub(crate) fn cmp_lt_phase_conditioned(
+    b: &mut B,
+    u: &[QubitId],
+    v: &[QubitId],
+    phase: BitId,
+) {
+    let n = u.len();
+    assert_eq!(v.len(), n);
+    assert!(n > 0);
+
+    let c_in = b.alloc_qubit();
+    b.push_condition(phase);
+    for &q in u {
+        b.x(q);
+    }
+    let carries = b.alloc_qubits(n);
+    cmp_lt_fast_prefix_window_forward(b, u, v, c_in, &carries, c_in, &[]);
+    b.cz(u[n - 1], u[n - 1]);
+    cmp_lt_fast_prefix_window_inverse(b, u, v, c_in, &carries);
+    b.free_vec(&carries);
+    for &q in u {
+        b.x(q);
+    }
+    b.pop_condition();
+    b.free(c_in);
+}
+
 pub(crate) fn ccx_cmp_lt_into_fast_prefix_targets_split(
     b: &mut B,
     u: &[QubitId],
diff --git a/src/point_add/arith/modular.rs b/src/point_add/arith/modular.rs
index 161ad3c..c0ca900 100644
--- a/src/point_add/arith/modular.rs
+++ b/src/point_add/arith/modular.rs
@@ -169,7 +169,13 @@ pub(crate) fn mod_sub_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256
     // Negate a in place, compare, un-negate.
     b.x(flag);
     mod_neg_inplace_fast(b, &a_ext[..n], p);
-    cmp_lt_into_fast(b, &acc_ext[..n], &a_ext[..n], flag);
+    if std::env::var("MOD_FAST_FLAG_CONDITIONAL_REPLAY").ok().as_deref() == Some("1") {
+        let phase = b.alloc_bit();
+        b.hmr(flag, phase);
+        cmp_lt_phase_conditioned(b, &acc_ext[..n], &a_ext[..n], phase);
+    } else {
+        cmp_lt_into_fast(b, &acc_ext[..n], &a_ext[..n], flag);
+    }
     mod_neg_inplace_fast(b, &a_ext[..n], p);
     b.free(flag);
 
@@ -947,7 +953,13 @@ pub(crate) fn mod_add_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256
     }
     b.x(flag);
     b.cx(flag, acc_ovf);
-    cmp_lt_into_fast(b, &acc_ext[..n], &a_ext[..n], flag);
+    if std::env::var("MOD_FAST_FLAG_CONDITIONAL_REPLAY").ok().as_deref() == Some("1") {
+        let phase = b.alloc_bit();
+        b.hmr(flag, phase);
+        cmp_lt_phase_conditioned(b, &acc_ext[..n], &a_ext[..n], phase);
+    } else {
+        cmp_lt_into_fast(b, &acc_ext[..n], &a_ext[..n], flag);
+    }
     b.free(flag);
 
     unext_reg(b, a_ovf);
@@ -1029,7 +1041,13 @@ pub(crate) fn mod_add_qq_fast_from_zero(b: &mut B, acc: &[QubitId], a: &[QubitId
     }
     b.x(flag);
     b.cx(flag, acc_ovf);
-    cmp_lt_into_fast(b, &acc_ext[..n], &a_ext[..n], flag);
+    if std::env::var("MOD_FAST_FLAG_CONDITIONAL_REPLAY").ok().as_deref() == Some("1") {
+        let phase = b.alloc_bit();
+        b.hmr(flag, phase);
+        cmp_lt_phase_conditioned(b, &acc_ext[..n], &a_ext[..n], phase);
+    } else {
+        cmp_lt_into_fast(b, &acc_ext[..n], &a_ext[..n], flag);
+    }
     b.free(flag);
 
     unext_reg(b, a_ovf);
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 0b3441d..086c8d5 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1098,6 +1098,10 @@ fn configure_ecdsafail_submission_route() {
     // by 172,444).
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_APPLY_BOUNDARY_CONDITIONAL_REPLAY", "1");  // BAKED: condrep ON for env-less grader build
+    // Bake the exact conditional-replay stack for env-less GPU hunts and grader builds.
+    set_default_env("DIALOG_GCD_REVERSE_BRANCH_CONDITIONAL_REPLAY", "1");
+    set_default_env("DIALOG_GCD_SPECIAL_CLEAN_CONDITIONAL_REPLAY", "1");
+    set_default_env("MOD_FAST_FLAG_CONDITIONAL_REPLAY", "1");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_K2", "1");
     // Both-phase apply fold-fusion (fused double_y + halve_y Solinas folds,
@@ -1399,7 +1403,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "3967248");
+    set_default_env("DIALOG_TAIL_NONCE", "9100005549463");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
diff --git a/src/point_add/rounds/dialog/compressed.rs b/src/point_add/rounds/dialog/compressed.rs
index 1c7e6fc..0029d67 100644
--- a/src/point_add/rounds/dialog/compressed.rs
+++ b/src/point_add/rounds/dialog/compressed.rs
@@ -1050,7 +1050,19 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_tobitvector_steps_reverse_block
             }
 
             b.set_phase("dialog_gcd_compressed_block_tobitvector_reverse_branch_bits");
-            if dialog_gcd_fused_branch_bits_enabled() {
+            if dialog_gcd_reverse_branch_conditional_replay_enabled() {
+                let phase = b.alloc_bit();
+                b.hmr(b0_and_b1, phase);
+                dialog_gcd_cmp_gt_truncated_phase_conditioned_hosted(
+                    b,
+                    u_active,
+                    v_active,
+                    b0,
+                    phase,
+                    compare_bits,
+                    borrowed_carries,
+                );
+            } else if dialog_gcd_fused_branch_bits_enabled() {
                 // Fused path: no separate `cmp` ancilla (derives b0_and_b1 from the
                 // comparator carry). Allocating it would add a dead live-qubit at the
                 // reverse_branch_bits peak instant, so allocate only on the non-fused
diff --git a/src/point_add/rounds/dialog/config.rs b/src/point_add/rounds/dialog/config.rs
index 1e38ede..b6c9c98 100644
--- a/src/point_add/rounds/dialog/config.rs
+++ b/src/point_add/rounds/dialog/config.rs
@@ -201,6 +201,20 @@ pub(crate) fn dialog_gcd_apply_boundary_conditional_replay_enabled() -> bool {
         == Some("1")
 }
 
+pub(crate) fn dialog_gcd_reverse_branch_conditional_replay_enabled() -> bool {
+    std::env::var("DIALOG_GCD_REVERSE_BRANCH_CONDITIONAL_REPLAY")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
+pub(crate) fn dialog_gcd_special_clean_conditional_replay_enabled() -> bool {
+    std::env::var("DIALOG_GCD_SPECIAL_CLEAN_CONDITIONAL_REPLAY")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
 pub(crate) fn dialog_gcd_apply_replay_swap_host_enabled() -> bool {
     // Prototype, deliberately NOT enabled by configure_ecdsafail_submission_route.
     //
diff --git a/src/point_add/rounds/dialog/mod.rs b/src/point_add/rounds/dialog/mod.rs
index 579f97e..a47268d 100644
--- a/src/point_add/rounds/dialog/mod.rs
+++ b/src/point_add/rounds/dialog/mod.rs
@@ -122,6 +122,59 @@ pub(crate) fn dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted(
     }
 }
 
+pub(crate) fn dialog_gcd_cmp_gt_truncated_phase_conditioned_hosted(
+    b: &mut B,
+    u: &[QubitId],
+    v: &[QubitId],
+    ctrl: QubitId,
+    phase: BitId,
+    compare_bits: usize,
+    borrowed: Option<&[QubitId]>,
+) {
+    assert_eq!(u.len(), v.len());
+    assert!(!u.is_empty());
+    let compare_bits = compare_bits.min(u.len()).max(1);
+    let start = u.len() - compare_bits;
+    let cmp_u = &v[start..];
+    let cmp_v = &u[start..];
+    let n = cmp_u.len();
+    let need = n + 1;
+    let avail = borrowed.map(|s| s.len()).unwrap_or(0);
+    if dialog_gcd_partial_host_comparator_enabled() && avail > 0 && avail < need {
+        let slice = borrowed.expect("avail>0");
+        let owned = b.alloc_qubits(need - avail);
+        let mut clean: Vec<QubitId> = Vec::with_capacity(need);
+        clean.extend_from_slice(slice);
+        clean.extend_from_slice(&owned);
+        let (c_in, carries) = clean.split_first().expect("need >= 1");
+        cmp_lt_phase_conditioned_borrowed_carries(
+            b,
+            cmp_u,
+            cmp_v,
+            *c_in,
+            &carries[..n],
+            ctrl,
+            phase,
+        );
+        b.free_vec(&owned);
+    } else if let Some(slice) = borrowed.filter(|s| s.len() >= need) {
+        let (c_in, carries) = slice.split_first().expect("slice len >= n+1 > 0");
+        cmp_lt_phase_conditioned_borrowed_carries(
+            b,
+            cmp_u,
+            cmp_v,
+            *c_in,
+            &carries[..n],
+            ctrl,
+            phase,
+        );
+    } else {
+        let c_in = b.alloc_qubit();
+        cmp_lt_phase_conditioned_with_cin(b, cmp_u, cmp_v, c_in, ctrl, phase);
+        b.free(c_in);
+    }
+}
+
 pub(crate) fn dialog_gcd_partial_host_comparator_enabled() -> bool {
     std::env::var("DIALOG_GCD_PARTIAL_HOST_COMPARATOR")
         .ok()
@@ -977,8 +1030,24 @@ pub(crate) fn dialog_gcd_clean_truncated_underflow(
     for &q in &a[compare_start..] {
         b.x(q);
     }
-    b.cx(ctrl, acc_ovf);
-    ccx_cmp_lt_into_fast(b, &acc[compare_start..], &a[compare_start..], ctrl, acc_ovf);
+    if dialog_gcd_special_clean_conditional_replay_enabled() {
+        let phase = b.alloc_bit();
+        b.hmr(acc_ovf, phase);
+        b.z_if(ctrl, phase);
+        let c_in = b.alloc_qubit();
+        cmp_lt_phase_conditioned_with_cin(
+            b,
+            &acc[compare_start..],
+            &a[compare_start..],
+            c_in,
+            ctrl,
+            phase,
+        );
+        b.free(c_in);
+    } else {
+        b.cx(ctrl, acc_ovf);
+        ccx_cmp_lt_into_fast(b, &acc[compare_start..], &a[compare_start..], ctrl, acc_ovf);
+    }
     for &q in &a[compare_start..] {
         b.x(q);
     }
@@ -1450,7 +1519,22 @@ pub(crate) fn dialog_gcd_cmod_add_materialized_pseudomersenne_chunked(
 
     b.set_phase("dialog_gcd_materialized_special_overflow_clean");
     let compare_start = N - dialog_gcd_special_overflow_clean_compare_bits(step);
-    ccx_cmp_lt_into_fast(b, &acc[compare_start..], &a[compare_start..], ctrl, acc_ovf);
+    if dialog_gcd_special_clean_conditional_replay_enabled() {
+        let phase = b.alloc_bit();
+        b.hmr(acc_ovf, phase);
+        let c_in = b.alloc_qubit();
+        cmp_lt_phase_conditioned_with_cin(
+            b,
+            &acc[compare_start..],
+            &a[compare_start..],
+            c_in,
+            ctrl,
+            phase,
+        );
+        b.free(c_in);
+    } else {
+        ccx_cmp_lt_into_fast(b, &acc[compare_start..], &a[compare_start..], ctrl, acc_ovf);
+    }
     unext_reg(b, acc_ovf);
 }
 
```

