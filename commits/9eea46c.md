# 9eea46c — Remove one CCZ with a zero control at a fixed op index, plus a re-hunted nonce

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-07-18 |
| Submission | `ac60e6d` |
| Commit | `9eea46c9697c6de87b73ef80ba6e1b454f28e47f` |
| Result | 1152 qubits × 1,318,717 Toffoli = **1,519,161,984** |
| Base | `a505e6d` (git parent, mochimodev): 1152 qubits × 1,318,724 Toffoli = 1,519,170,048 |
| Change vs base | qubits ±0, Toffoli −7, score −8,064 (leaderboard Δ −8,064) |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [modular-fold](../concepts/modular-fold.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The only change to the shipped circuit is the deletion of a single `CCZ` at
op index 6,291,733 of the final stream, after the M-60 drop of
[`a505e6d`](a505e6d.md). The submission note says this gate acts on qubits
`(0, 305, 12)` and that its control on qubit 0 is statically zero at that
point. A CCZ with a control that is always 0 is the identity, and the scorer
charges it as a Toffoli anyway. Deleting it saves at most one Toffoli per
shot. The re-hunted nonce (9001904503906) accounts for the rest of the 7-Toffoli
drop in the average.

The rest of the diff adds switches that are off by default: a fold-trace
"shadow census", narrower fold and doubling windows, and a six-CCZ variant
of the drop. It also refactors `fused_fold`, which emits the same gates as
before.

## What changed and why it saves Toffoli

- **The active change** (`src/point_add/mod.rs`, end of `build()`).
  - `build()` now forces `TLM_DROP_ZERO_CCZ1=1` with `std::env::set_var`.
  - After `apply_m60_dead_t10`, that switch takes `final_ops[6291733]` and
    asserts two things: `op.kind == CCZ`, and `op.q_control2 == QubitId(0)`.
    It then removes the op.
  - The assert checks the qubit *identity*, not its value. The claim that
    qubit 0 holds |0⟩ at that point comes from the author's analysis and
    is not re-checked by the build. Qubit 0 was first allocated as `reg0[0]`
    (P.x bit 0). The claim is that at this point of the stream that wire
    holds |0⟩.
  - With a zero control, `CCZ` applies no phase on any input, so removing it
    changes nothing but the Toffoli tally (see
    [dead-gate-strip](../concepts/dead-gate-strip.md)).
- **Nonce.** The forced `DIALOG_TAIL_NONCE` goes from `9000624727621` to
  `9001904503906`.
  - The emitted stream is 9,781,973 ops, one fewer than the base.
  - The average executed Toffoli falls by 7: about 1 from the deleted gate
    and the rest from the new 9,024-shot draw. See
    [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- **Off by default, no effect on the shipped stream:**
  - `TLM_DROP_ZERO_CCZ6` removes six CCZ at fixed indices
    6,291,733 … 6,292,061, called "proof-backed zero-operand CCZ gates".
    Each index is asserted to be a CCZ.
  - `TLM_FOLD_TRIM_52` (with `TLM_FOLD_TRIM_52_EXCLUDE`) and `TLM_I0_DOUBLE_52`
    narrow the fused-fold window, or the step-0 `controlled_mod_double` `+f`
    window, from `LSBS` to `LSBS − 1`.
  - `TLM_DOUBLE_SHADOW`, together with `TLM_DOUBLE_SHADOW_MARKERS`, is a
    census tool.
    - It turns on `TRACE_OP_SITES` and tags every fused-fold call with
      context `0xd000_0000 | call_index`. `set_op_trace_context` keeps that
      outer tag while nested scopes run.
    - It records each fold's `[start_op, end_op)` range and remaps the ranges
      through the fan-out rewrites and the M-60 drops
      (`shift_fold_shadow_markers_for_rewrite`, `…_for_drops`).
    - It writes them to a TSV, which is presumably meant for finding
      double-width fold carries that never fire.
- **`fused_fold` refactor** (`trailmix_ludicrous/fused.rs`).
  - The function now takes the full `y` and a `complement` flag. It slices
    `ylow = y[..width]` and `dirty = y[width..2·width−1]` itself, with
    `width = LSBS` unless `TLM_FOLD_TRIM_52` is set.
  - With `complement = true` it applies the `X` sandwich around the fold
    that `fused_double_cdouble_reverse` used to apply outside the call.
  - Counters and trace contexts emit no ops, so the op sequence is
    unchanged.

## Why it is still correct, and what it risks

- If qubit 0 really is |0⟩ at op 6,291,733 on every input, the deletion is
  exact. The author describes it as statically zero, and the six-gate variant
  as "proof-backed".
- If that is wrong for some input, the missing CCZ leaves a phase error on
  that input, which shows up as a phase failure.
- The deletion is positional. The two asserts (kind, and control qubit 0)
  catch most misalignments if anything upstream shifts the stream.
- The forced nonce `9001904503906` draws a clean set: 9,024 of 9,024 shots,
  0 classical, 0 phase and 0 ancilla failures, average 1,318,717.281 Toffoli
  (submission note).

## Classification rationale

One never-acting Toffoli-class gate is deleted, so the label is
dead-gate/self-inverse removal. Since the score moves by only 7 Toffoli, most
of it from the nonce, the commit sits close to a nonce/island reroll. The
gate deletion makes it a circuit change, however small.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a505e6d -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol a505e6d 9eea46c -- src/point_add` is 292
   changed lines in 4 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 9eea46c -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`,
   `TLM_*`, `M60_*` or `SINGLE_CCX_*` overrides set. `DIALOG_TAIL_NONCE` and
   `TLM_DROP_ZERO_CCZ1` are force-set by `build()` in any case. Expect:
   - 1152 qubits
   - 1,318,717 average Toffoli (1,318,717.281 before rounding)
   - score 1,519,161,984
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9001904503906` and an identical op
stream. Any upstream change also moves the fixed index 6,291,733.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6a12553..7f115eb 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -61,6 +61,13 @@ pub(crate) fn set_op_trace_context(context: u32) -> u32 {
     }
     OP_TRACE_CONTEXT.with(|slot| {
         let old = slot.get();
+        // During the double-width shadow census, retain the outer fold-call
+        // identity across more granular nested provenance scopes.
+        if std::env::var("TLM_DOUBLE_SHADOW").ok().as_deref() == Some("1")
+            && old & 0xf000_0000 == 0xd000_0000
+        {
+            return old;
+        }
         slot.set(context);
         old
     })
@@ -1691,11 +1698,18 @@ fn apply_m60_dead_t10(ops: Vec<Op>) -> Vec<Op> {
 }
 
 pub fn build() -> Vec<Op> {
+    let double_shadow = std::env::var("TLM_DOUBLE_SHADOW").ok().as_deref() == Some("1");
+    if double_shadow {
+        // Site provenance is a sidecar only; it does not alter the emitted Op stream.
+        std::env::set_var("TRACE_OP_SITES", "1");
+    }
     // M-60 (C2b): bake the dead_t10 winning Fiat-Shamir nonce so the challenge harness
     // reproduces the validated winner. Forced (not set_default) to win over the C1 default.
     // The nonce only appends identity X-pairs at the tail; the dead-CCX skip-set applied
     // post-fanout (apply_m60_dead_t10) is nonce-invariant.
-    std::env::set_var("DIALOG_TAIL_NONCE", "9000624727621");
+    std::env::set_var("DIALOG_TAIL_NONCE", "9001904503906");
+    // Bake the independently validated single-CCZ route overlay into submitted source.
+    std::env::set_var("TLM_DROP_ZERO_CCZ1", "1");
     configure_q1153_second512_submission_defaults();
 
     if std::env::var("TLM_SQ_SELFTEST").ok().as_deref() == Some("1") {
@@ -1955,8 +1969,14 @@ pub fn build() -> Vec<Op> {
     set_default_env("TLM_FUSED_CLEAN_FOLD_SKIP_TOP31", "1");
     set_default_env("TLM_GIDNEY_SKIP_SMALL_RESIDUAL_DEAD", "1");
     let mut ops = trailmix_ludicrous::build_trailmix_ludicrous_ops();
+    let mut shadow_markers = double_shadow.then(|| {
+        let sites = take_last_op_sites();
+        assert_eq!(sites.len(), ops.len(), "shadow site trace after constprop");
+        trailmix_ludicrous::collect_fold_shadow_markers(&sites)
+    });
 
     if let Ok(k) = std::env::var("TLM_SEED_PERTURB").unwrap_or_default().parse::<usize>() {
+        assert!(!double_shadow || k == 0, "shadow census requires TLM_SEED_PERTURB=0");
         for _ in 0..k {
             ops.push(crate::circuit::Op {
                 kind: crate::circuit::OperationType::DebugPrint,
@@ -1974,13 +1994,24 @@ pub fn build() -> Vec<Op> {
         .as_deref()
         == Some("1")
     {
+        if let Some(markers) = shadow_markers.take() {
+            trailmix_ludicrous::write_fold_shadow_markers(&markers);
+        }
         return ops;
     }
     let input_ops = ops.len();
     let mut fanout_passes = 0usize;
     loop {
         match single_ccx_fanout::rewrite_first_target_fanout(ops.clone(), 96) {
-            Ok((rewritten, _witness)) => {
+            Ok((rewritten, witness)) => {
+                if let Some(markers) = shadow_markers.as_mut() {
+                    trailmix_ludicrous::shift_fold_shadow_markers_for_rewrite(
+                        markers,
+                        witness.first_index,
+                        witness.blocker_index,
+                        witness.second_index,
+                    );
+                }
                 fanout_passes += 1;
                 ops = rewritten;
             }
@@ -2003,7 +2034,43 @@ pub fn build() -> Vec<Op> {
         ops.len(),
         fanout_passes,
     );
-    apply_m60_dead_t10(ops)
+    let m60_disabled = std::env::var("M60_DISABLE").ok().as_deref() == Some("1");
+    let mut final_ops = apply_m60_dead_t10(ops);
+    if let Some(mut markers) = shadow_markers {
+        if !m60_disabled {
+            let mut drops = m60_dead_t10::M60_DEAD_T10.to_vec();
+            drops.sort_unstable();
+            trailmix_ludicrous::shift_fold_shadow_markers_for_drops(&mut markers, &drops);
+        }
+        trailmix_ludicrous::write_fold_shadow_markers(&markers);
+    }
+    if std::env::var("TLM_DROP_ZERO_CCZ6").ok().as_deref() == Some("1") {
+        const DROP: [usize; 6] = [6291733, 6291783, 6291840, 6291906, 6291983, 6292061];
+        for &index in &DROP {
+            assert_eq!(
+                final_ops.get(index).map(|op| op.kind),
+                Some(OperationType::CCZ),
+                "zero-CCZ overlay index {index} shifted"
+            );
+        }
+        final_ops = final_ops
+            .into_iter()
+            .enumerate()
+            .filter_map(|(index, op)| (!DROP.contains(&index)).then_some(op))
+            .collect();
+        eprintln!("TLM_DROP_ZERO_CCZ6: removed 6 proof-backed zero-operand CCZ gates");
+    }
+    if std::env::var("TLM_DROP_ZERO_CCZ1").ok().as_deref() == Some("1") {
+        const DROP_INDEX: usize = 6291733;
+        let op = final_ops
+            .get(DROP_INDEX)
+            .expect("single zero-CCZ overlay index out of range");
+        assert_eq!(op.kind, OperationType::CCZ, "single zero-CCZ overlay index shifted");
+        assert_eq!(op.q_control2.0, 0, "single zero-CCZ overlay lost its zero control");
+        final_ops.remove(DROP_INDEX);
+        eprintln!("TLM_DROP_ZERO_CCZ1: removed post-M60 CCZ index {DROP_INDEX}");
+    }
+    final_ops
 }
 
 pub fn square_window_selftest() -> Result<(), String> {
diff --git a/src/point_add/trailmix_ludicrous/fused.rs b/src/point_add/trailmix_ludicrous/fused.rs
index c4a118f..1109571 100644
--- a/src/point_add/trailmix_ludicrous/fused.rs
+++ b/src/point_add/trailmix_ludicrous/fused.rs
@@ -2,7 +2,25 @@
 use super::arith::{F_SECP256K1, LSBS};
 use super::{B, BExt};
 use crate::circuit::{BitId, QubitId};
-use std::cell::Cell;
+use std::cell::{Cell, RefCell};
+
+const SHADOW_CONTEXT_BASE: u32 = 0xd000_0000;
+
+#[derive(Clone, Copy, Debug)]
+struct FoldShadowCall {
+    call_index: usize,
+    kind: &'static str,
+    high_qubit: QubitId,
+    e: QubitId,
+    d: QubitId,
+}
+
+#[derive(Clone, Debug)]
+pub(crate) struct FoldShadowMarker {
+    call: FoldShadowCall,
+    start_op: usize,
+    end_op: usize,
+}
 
 thread_local! {
     static FOLD_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
@@ -13,6 +31,7 @@ thread_local! {
     static FOLD_BOUNDARY_ZERO_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
     static FUSED_CDOUBLE_FWD_SHIFT_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
     static FUSED_CDOUBLE_REV_SHIFT_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
+    static FOLD_SHADOW_CALLS: RefCell<Vec<FoldShadowCall>> = const { RefCell::new(Vec::new()) };
 }
 
 pub(super) fn reset_fold_call_index() {
@@ -24,6 +43,102 @@ pub(super) fn reset_fold_call_index() {
     FOLD_BOUNDARY_ZERO_CALL_INDEX.with(|index| index.set(0));
     FUSED_CDOUBLE_FWD_SHIFT_CALL_INDEX.with(|index| index.set(0));
     FUSED_CDOUBLE_REV_SHIFT_CALL_INDEX.with(|index| index.set(0));
+    FOLD_SHADOW_CALLS.with(|calls| calls.borrow_mut().clear());
+}
+
+fn shadow_enabled() -> bool {
+    std::env::var("TLM_DOUBLE_SHADOW").ok().as_deref() == Some("1")
+}
+
+fn enter_shadow_call(call_index: usize, kind: &'static str, high: QubitId, e: QubitId, d: QubitId) -> u32 {
+    if !shadow_enabled() {
+        return 0;
+    }
+    FOLD_SHADOW_CALLS.with(|calls| {
+        calls.borrow_mut().push(FoldShadowCall {
+            call_index,
+            kind,
+            high_qubit: high,
+            e,
+            d,
+        });
+    });
+    crate::point_add::set_op_trace_context(SHADOW_CONTEXT_BASE | call_index as u32)
+}
+
+pub(super) fn collect_fold_shadow_markers(
+    sites: &[crate::point_add::OpSite],
+) -> Vec<FoldShadowMarker> {
+    let calls = FOLD_SHADOW_CALLS.with(|calls| calls.borrow().clone());
+    calls
+        .into_iter()
+        .map(|call| {
+        let context = SHADOW_CONTEXT_BASE | call.call_index as u32;
+        let mut positions = sites
+            .iter()
+            .enumerate()
+            .filter_map(|(index, site)| (site.2 == context).then_some(index));
+        let start = positions.next().unwrap_or_else(|| {
+            panic!("shadow fold call {} has no surviving operations", call.call_index)
+        });
+        let end = positions.last().unwrap_or(start) + 1;
+            FoldShadowMarker { call, start_op: start, end_op: end }
+        })
+        .collect()
+}
+
+pub(super) fn shift_fold_shadow_markers_for_rewrite(
+    markers: &mut [FoldShadowMarker],
+    first_removed: usize,
+    insertion_after: usize,
+    second_removed: usize,
+) {
+    let map = |boundary: usize| {
+        boundary
+            - usize::from(first_removed < boundary)
+            - usize::from(second_removed < boundary)
+            + usize::from(insertion_after < boundary)
+    };
+    for marker in markers {
+        marker.start_op = map(marker.start_op);
+        marker.end_op = map(marker.end_op);
+    }
+}
+
+pub(super) fn shift_fold_shadow_markers_for_drops(
+    markers: &mut [FoldShadowMarker],
+    drops: &[usize],
+) {
+    for marker in markers {
+        marker.start_op -= drops.partition_point(|&index| index < marker.start_op);
+        marker.end_op -= drops.partition_point(|&index| index < marker.end_op);
+    }
+}
+
+pub(super) fn write_fold_shadow_markers(markers: &[FoldShadowMarker]) {
+    if !shadow_enabled() {
+        return;
+    }
+    let mut out = String::from("call_index\tkind\tstart_op\tend_op\thigh_qubit\te_qubit\td_qubit\n");
+    for marker in markers {
+        let call = marker.call;
+        out.push_str(&format!(
+            "{}\t{}\t{}\t{}\t{}\t{}\t{}\n",
+            call.call_index,
+            call.kind,
+            marker.start_op,
+            marker.end_op,
+            call.high_qubit.0,
+            call.e.0,
+            call.d.0,
+        ));
+    }
+    let path = std::env::var("TLM_DOUBLE_SHADOW_MARKERS")
+        .unwrap_or_else(|_| "double_shadow_markers.tsv".to_owned());
+    std::fs::write(&path, out).unwrap_or_else(|error| {
+        panic!("failed to write shadow markers {path}: {error}")
+    });
+    eprintln!("TLM_DOUBLE_SHADOW: wrote {} fold markers to {}", markers.len(), path);
 }
 
 fn next_fold_call_index() -> usize {
@@ -38,6 +153,22 @@ fn active_fold_call_index() -> usize {
     ACTIVE_FOLD_CALL_INDEX.with(|index| index.get())
 }
 
+fn fold_window_width(call_index: usize) -> usize {
+    if std::env::var("TLM_FOLD_TRIM_52").ok().as_deref() != Some("1") {
+        return LSBS;
+    }
+    let excluded = std::env::var("TLM_FOLD_TRIM_52_EXCLUDE").unwrap_or_default();
+    if excluded
+        .split(',')
+        .filter_map(|value| value.trim().parse::<usize>().ok())
+        .any(|value| value == call_index)
+    {
+        LSBS
+    } else {
+        LSBS - 1
+    }
+}
+
 fn enter_fold_call_index(index: usize) -> usize {
     ACTIVE_FOLD_CALL_INDEX.with(|slot| {
         let prior = slot.get();
@@ -1743,13 +1874,22 @@ fn build_fold_at(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId], dirty: &
     }
 }
 
-fn fused_fold(circ: &mut B, e: &QubitId, d: &QubitId, ylow: &[QubitId], dirty: &[QubitId]) {
+fn fused_fold(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId], complement: bool) {
     let call_index = next_fold_call_index();
+    let width = fold_window_width(call_index);
+    let ylow = &y[..width];
+    let dirty = &y[width..2 * width - 1];
+    let shadow_context = enter_shadow_call(call_index, "controlled", ylow[width - 1], *e, *d);
     let prior_fold_call_index = enter_fold_call_index(call_index);
     let timeline_start = circ.active_timeline.len();
     let entry_active = circ.active_qubits;
     let code = super::next_fold();
     let mut selected_nv = None;
+    if complement {
+        for q in ylow {
+            circ.x(*q);
+        }
+    }
     if code < 0 {
         let chunk = std::env::var("TLM_FOLD_CHUNK_FORCE")
             .ok()
@@ -1770,6 +1910,11 @@ fn fused_fold(circ: &mut B, e: &QubitId, d: &QubitId, ylow: &[QubitId], dirty: &
         selected_nv = Some(nv);
         build_fold_at(circ, e, d, ylow, dirty, nv);
     }
+    if complement {
+        for q in ylow {
+            circ.x(*q);
+        }
+    }
     restore_fold_call_index(prior_fold_call_index);
     if std::env::var_os("TRACE_TLM_FOLD").is_some() {
         let local_peak = circ.active_timeline[timeline_start..]
@@ -1788,10 +1933,14 @@ fn fused_fold(circ: &mut B, e: &QubitId, d: &QubitId, ylow: &[QubitId], dirty: &
             circ.current_ops_len(),
         );
     }
+    if shadow_enabled() {
+        crate::point_add::restore_op_trace_context(shadow_context);
+    }
 }
 
 fn fused_fold_e_only(circ: &mut B, e: &QubitId, y: &[QubitId]) {
     let call_index = next_fold_call_index();
+    let shadow_context = enter_shadow_call(call_index, "e_only", y[LSBS - 1], *e, *e);
     let prior_fold_call_index = enter_fold_call_index(call_index);
     let timeline_start = circ.active_timeline.len();
     let entry_active = circ.active_qubits;
@@ -1830,6 +1979,9 @@ fn fused_fold_e_only(circ: &mut B, e: &QubitId, y: &[QubitId]) {
             circ.current_ops_len(),
         );
     }
+    if shadow_enabled() {
+        crate::point_add::restore_op_trace_context(shadow_context);
+    }
 }
 
 fn trace_fold_alloc(circ: &B, name: &str, stage: &str, i: usize) {
@@ -1873,8 +2025,7 @@ pub fn fused_double_cdouble(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
         crate::point_add::restore_op_trace_context(old_context);
     }
 
-    let borrow: Vec<QubitId> = y[LSBS..2 * LSBS - 1].to_vec();
-    fused_fold(circ, &w[n], &w[n + 1], &y[..LSBS], &borrow);
+    fused_fold(circ, &w[n], &w[n + 1], y, false);
 
     circ.cx(y[0], w[n]);
     clear_and(circ, &w[n + 1], s2, &y[1]);
@@ -1915,14 +2066,7 @@ pub fn fused_double_cdouble_reverse(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
     circ.ccx(*s2, y[1], w[n + 1]);
     circ.cx(y[0], w[n]);
 
-    let borrow: Vec<QubitId> = y[LSBS..2 * LSBS - 1].to_vec();
-    for q in &y[..LSBS] {
-        circ.x(*q);
-    }
-    fused_fold(circ, &w[n], &w[n + 1], &y[..LSBS], &borrow);
-    for q in &y[..LSBS] {
-        circ.x(*q);
-    }
+    fused_fold(circ, &w[n], &w[n + 1], y, true);
 
     for i in 1..w.len() {
         let bit = i - 1;
diff --git a/src/point_add/trailmix_ludicrous/gcd.rs b/src/point_add/trailmix_ludicrous/gcd.rs
index 0c29716..c7909ae 100644
--- a/src/point_add/trailmix_ludicrous/gcd.rs
+++ b/src/point_add/trailmix_ludicrous/gcd.rs
@@ -682,7 +682,12 @@ fn controlled_mod_double(circ: &mut B, ctrl: &QubitId, a: &[QubitId]) {
         circ.cswap(*ctrl, *w[i], *w[i + 1]);
     }
 
-    arith::add_f_window_pub(circ, &ovf, a, arith::LSBS, &f_bytes, None);
+    let width = if std::env::var("TLM_I0_DOUBLE_52").ok().as_deref() == Some("1") {
+        arith::LSBS - 1
+    } else {
+        arith::LSBS
+    };
+    arith::add_f_window_pub(circ, &ovf, a, width, &f_bytes, None);
 
     clear_and(circ, &ovf, ctrl, &a[0]);
     circ.zero_and_free(ovf);
@@ -696,11 +701,16 @@ fn controlled_mod_double_reverse(circ: &mut B, ctrl: &QubitId, a: &[QubitId]) {
 
     circ.ccx(*ctrl, a[0], ovf);
 
-    for q in &a[..arith::LSBS] {
+    let width = if std::env::var("TLM_I0_DOUBLE_52").ok().as_deref() == Some("1") {
+        arith::LSBS - 1
+    } else {
+        arith::LSBS
+    };
+    for q in &a[..width] {
         circ.x(*q);
     }
-    arith::add_f_window_pub(circ, &ovf, a, arith::LSBS, &f_bytes, None);
-    for q in &a[..arith::LSBS] {
+    arith::add_f_window_pub(circ, &ovf, a, width, &f_bytes, None);
+    for q in &a[..width] {
         circ.x(*q);
     }
 
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index 08fda4b..02da164 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -5,6 +5,39 @@ mod comparator;
 mod constprop;
 pub mod ec_add;
 mod fused;
+
+pub(super) use fused::FoldShadowMarker;
+
+pub(super) fn collect_fold_shadow_markers(
+    sites: &[crate::point_add::OpSite],
+) -> Vec<FoldShadowMarker> {
+    fused::collect_fold_shadow_markers(sites)
+}
+
+pub(super) fn shift_fold_shadow_markers_for_rewrite(
+    markers: &mut [FoldShadowMarker],
+    first_removed: usize,
+    insertion_after: usize,
+    second_removed: usize,
+) {
+    fused::shift_fold_shadow_markers_for_rewrite(
+        markers,
+        first_removed,
+        insertion_after,
+        second_removed,
+    );
+}
+
+pub(super) fn shift_fold_shadow_markers_for_drops(
+    markers: &mut [FoldShadowMarker],
+    drops: &[usize],
+) {
+    fused::shift_fold_shadow_markers_for_drops(markers, drops);
+}
+
+pub(super) fn write_fold_shadow_markers(markers: &[FoldShadowMarker]) {
+    fused::write_fold_shadow_markers(markers);
+}
 mod gcd;
 mod gidney;
 mod mcx;
```

