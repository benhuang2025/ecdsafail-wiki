# 9bcc27d — Merge each Kaliski iteration's closing `(r, s)` swap into the next iteration's opening swap

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-05-31 |
| Submission | `d35d6e7` |
| Commit | `9bcc27d76b7a59ef27f964dc85ea7a452593c5f4` |
| Result | 2708 qubits × 3,546,654 Toffoli = **9,604,339,032** |
| Base | [`666b591`](666b591.md) (the author's earlier submission): 2708 qubits × 3,820,981 Toffoli = 10,347,216,548 |
| Change vs base | qubits ±0, Toffoli −274,327, score −742,877,516 |
| Leaderboard Δ | −714,197,088, measured against the frontier at the time, [`1c400f2`](1c400f2.md) (2708 × 3,810,390 = 10,318,536,120), which is **not** this commit's base |
| Family | Fusion → boundary cswap-merge |
| Concepts | [scoring-and-validation](../concepts/scoring-and-validation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Each Kaliski iteration swaps the Bézout coefficients `(r, s)` twice under its
swap decision `a_k`: once at STEP 3, to bring the pair into canonical order,
and again at STEP 9, to put it back. Between iteration `k`'s STEP 9 and
iteration `k+1`'s STEP 3, nothing touches `r` or `s`. Two controlled swaps of
the same register pair compose to one swap controlled by the XOR of the
controls: `cswap(a_k)·cswap(a_{k+1}) = cswap(a_k ⊕ a_{k+1})`.

This commit defers STEP 9's `(r, s)` swap and carries `a_k` across the
iteration boundary in a one-qubit "frame". It then does both swaps as one at
the next STEP 3. Each boundary saves one controlled swap of up to 256 bits, at
one Toffoli per bit, and pays 2 Toffoli to reset the frame. Over the four
Kaliski runs this is −274,327 Toffoli, the largest single drop of the early
era. The frame is not live during STEP 4, where each iteration peaks, so the
peak stays at 2708.

## What changed and why it saves Toffoli

All edits are in `src/point_add/mod.rs`. The switch is `kal_cswap_rs_merge_enabled()`
(env `KAL_CSWAP_RS_MERGE`, default on). Two diagnostic sub-switches,
`KAL_CSWAP_RS_MERGE_GENERIC` and `KAL_CSWAP_RS_MERGE_BULK`, are also on by
default. The merge only applies when `coeff` is `None`, which is the default
channel.

**Forward bodies** (`kaliski_iteration_bulk_prefix3` and `kaliski_iteration`)
gain the arguments `frame: &mut Option<QubitId>` and `is_last: bool`.

- *STEP 9, when not the last iteration*: the `(r, s)` cswap loop (width
  `min(k+2, n)`) and STEP 10 (`a_f ^= NOT s[0]`) are skipped. Instead:
  ```
  frame_out = alloc;  cx(a_f, frame_out)   // frame = a_k
  cx(frame_out, a_f)                        // a_f = 0, freed as usual
  ```
  The `(u, v_w)` part of STEP 9 is still done eagerly.
- *STEP 3, when a frame is incoming*:
  ```
  cx(frame_in, a_f)                         // a_f = a_{k-1} ⊕ a_k
  for j < min(k+1, n): cswap(a_f, r[j], s[j])   // one merged swap
  cx(frame_in, a_f)                         // a_f = a_k again
  // reset the frame: a_{k-1} = NOT(a_k ? r[0] : s[0])
  cx(s[0], frame_in); x(frame_in)
  ccx(a_f, r[0], frame_in); ccx(a_f, s[0], frame_in)
  free(frame_in)
  ```
  The widths agree: STEP 9 of iteration `k−1` uses `min((k−1)+2, n)`, and
  STEP 3 of iteration `k` uses `min(k+1, n)`.
- The reset uses the invariant that STEP 10 relies on: right after STEP 9,
  `a_{k−1} = NOT s[0]`. After the merged swap, the pair is in iteration `k`'s
  post-STEP-3 order, which is swapped if and only if `a_k = 1`. So the old
  `s[0]` is now `r[0]` when `a_k = 1` and `s[0]` otherwise.
- The last iteration (`is_last`) does STEP 9 and STEP 10 eagerly, so no frame
  leaves the loop. Iteration 0 has no incoming frame and swaps eagerly at
  STEP 3.

**Backward bodies** (`kaliski_iteration_bulk_prefix3_backward`,
`kaliski_iteration_backward`) run the exact reverse.
- At reverse STEP 10/9 they rebuild `a_f = a_k` from the incoming frame and
  free the frame.
- At reverse STEP 3 (for `iter_idx ≠ 0`) they allocate a new frame, rebuild
  `a_{k−1}` into it with the reset formula in reverse, undo the merged swap
  under `a_{k−1} ⊕ a_k`, and hand the frame to the next backward iteration
  (iteration `k − 1`).

**Loop drivers.** Each of the six forward and backward drivers
(`_with_coeff_caps` / `_backward_caps`, `_alias_v_w_caps`, `_prescaled_kind`)
keeps a `frame` across iterations and computes `is_last = (i + 1 == iters)`. A
`debug_assert` checks that the frame is used up. If only the bulk path merges,
`merge_boundary_break` stops the frame from crossing from bulk into generic
iterations. That cannot happen by default.

**Count.** The removed swap has width `min(k+2, 256)`, at one Toffoli per bit
(`cswap` is CX·CCX·CX). Summed over about 398 iterations, that is about 69,000
Toffoli per run. Four runs (pair 1 and pair 2, forward and backward) give
about 277,000. The frame reset costs 2 CCX per boundary, about 3,200 in all.
The backward generic body also no longer pays its `f`-gated reverse STEP 10
CCX. The net is the measured −274,327.

**Peak.** The frame qubit is allocated after STEP 6-8 and freed at the next
STEP 3, before STEP 4 allocates its 256-qubit `tmp` register. So it never
coexists with the iteration's peak, and the peak stays at 2708. See
[peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).

## Why it is still correct, and what it risks

The merge is exact wherever the base is correct.
- `cswap(p)·cswap(q) = cswap(p ⊕ q)` holds as a unitary on the same register
  pair, and STEPs 0 to 2 of iteration `k` do not touch `r` or `s`.
- The frame reset uses the same identity as the base's STEP 10,
  `a = NOT s[0]` after STEP 9. If that identity failed on some input, the base
  would already leave `a_f` dirty. Here the frame would be freed dirty
  instead. Either way the result is an ancilla failure.
- The backward pass is the gate-by-gate reverse, so the measurement-uncompute
  phases inside the iterations are unchanged.

There is no tail nonce in this era. The 9,024 test inputs are a SHAKE256 hash
of the op stream, so the draw changed. The base's probabilistic Kaliski
settings (loop length, bulk prefix, `R_SMALL_THRESHOLD = 326`) passed on the
new draw with 0 classical, 0 phase and 0 ancilla failures, per the submission
note.

## Classification rationale

Two adjacent controlled operations on the same registers are fused into one
across the iteration boundary. That is Fusion → boundary cswap-merge. Later
commits refine the same frame, for example cutting the reset to one CCX (see
[`d4959a1`](d4959a1.md)).

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 666b591 -- src/point_add`.
   - Do not start from the git parent `e54aaba`. That is an organiser commit
     ("fix harness") whose `src/point_add` equals [`1c400f2`](1c400f2.md).
   - Against the parent the diff is 455 lines. It reverts three other commits:
     the fast `2^32`-term add of [`e33b400`](e33b400.md), the Solinas-fold
     audit of [`81ff75b`](81ff75b.md), and the bulk-prefix caps of
     [`1c400f2`](1c400f2.md).
   - Against `666b591`, `git diff --ignore-cr-at-eol 666b591 9bcc27d -- src/point_add`
     is 326 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 9bcc27d -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`,
   `AFFINE_*`, `DUMMY_TOFFOLIS` or other environment overrides set. Expect:
   - 2708 qubits
   - 3,546,654 average Toffoli (rounded)
   - score 9,604,339,032
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era. The 9,024 test inputs are a hash of the
op stream, so the score, and the clean draw, only reproduce with an identical
op stream.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 606c285..ca07604 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -4009,6 +4009,31 @@ fn r_small_threshold() -> usize {
         .unwrap_or(R_SMALL_THRESHOLD)
 }
 
+/// (r,s) cswap boundary-merge: defer step9(k) and fuse it with step3(k+1) on
+/// the (r,s) Bezout channel via the pure-unitary identity
+/// `cswap(p)·cswap(q) = cswap(p⊕q)`. A persistent `frame` parity qubit carries
+/// the deferred step9 control (= a_k, the iter's swap decision) across the
+/// iteration boundary, allocated only over the boundary span (step6_7_8 →
+/// next step3) so it is never live during step4 → peak-neutral. −274k CCX.
+/// Default ON; `KAL_CSWAP_RS_MERGE=0` restores the byte-identical eager path.
+/// Only active for the default coeff=None channel.
+fn kal_cswap_rs_merge_enabled() -> bool {
+    std::env::var("KAL_CSWAP_RS_MERGE").ok().as_deref() != Some("0")
+}
+
+// DIAGNOSTIC: gate the (r,s) boundary-merge in the GENERIC (non-bulk) Kaliski
+// path independently, to bisect a phase/correctness regression between the
+// bulk-prefix iterations and the generic tail iterations.
+fn kal_cswap_rs_merge_generic_enabled() -> bool {
+    kal_cswap_rs_merge_enabled()
+        && std::env::var("KAL_CSWAP_RS_MERGE_GENERIC").ok().as_deref() != Some("0")
+}
+// DIAGNOSTIC: gate the merge in the BULK path independently.
+fn kal_cswap_rs_merge_bulk_enabled() -> bool {
+    kal_cswap_rs_merge_enabled()
+        && std::env::var("KAL_CSWAP_RS_MERGE_BULK").ok().as_deref() != Some("0")
+}
+
 /// For nonzero secp256k1 inputs, the first 256 Kaliski iterations are always
 /// nonterminal, so `f = 1` and `v_w != 0` at step entry are guaranteed.
 ///
@@ -6466,7 +6491,11 @@ fn kaliski_iteration_bulk_prefix3(
     m_i: QubitId,
     iter_idx: usize,
     coeff: Option<(&[QubitId], &[QubitId])>,
+    frame: &mut Option<QubitId>,
+    is_last: bool,
 ) {
+    // (r,s) cswap boundary-merge is only valid on the default coeff=None channel.
+    let merge_rs = coeff.is_none() && kal_cswap_rs_merge_bulk_enabled();
     let a_f = b.alloc_qubit();
     let b_f = b.alloc_qubit();
     let add_f = b.alloc_qubit();
@@ -6532,8 +6561,34 @@ fn kaliski_iteration_bulk_prefix3(
     } else {
         u.len()
     };
-    for j in 0..rs_width_step3 {
-        cswap(b, a_f, r[j], s[j]);
+    // (r,s) STEP 3 — merged with the deferred STEP 9 of the previous iteration
+    // when merge_rs and an incoming frame parity is present.
+    if let (true, Some(frame_in)) = (merge_rs, *frame) {
+        // frame_in = a_{k-1} (previous iter's deferred step9 control).
+        // Merged cswap control = a_{k-1} ⊕ a_k. Build into a_f (free CX),
+        // emit one cswap (width = min(k+1,n) = step9(k-1) width = step3(k)
+        // width), then restore a_f to a_k. After: physical = canonical-post
+        // step3(k).
+        b.cx(frame_in, a_f); // a_f = a_{k-1} ⊕ a_k
+        for j in 0..rs_width_step3 {
+            cswap(b, a_f, r[j], s[j]);
+        }
+        b.cx(frame_in, a_f); // a_f = a_k (restored)
+        // Reset frame_in (= a_{k-1}) to |0⟩ via the step10 reroute of the
+        // previous iter, evaluated on the now-canonical (r,s) with a_k (= a_f)
+        // as the select bit (distinct qubit from frame_in → no self-control):
+        //   a_{k-1} = NOT(a_k ? r[0] : s[0])
+        // frame_in ^= NOT(a_f ? r[0] : s[0]):
+        b.cx(s[0], frame_in);
+        b.x(frame_in); // frame_in ^= NOT s[0]
+        b.ccx(a_f, r[0], frame_in);
+        b.ccx(a_f, s[0], frame_in); // frame_in ^= a_f & (r[0] ^ s[0])
+        b.free(frame_in); // frame_in now |0⟩
+        *frame = None;
+    } else {
+        for j in 0..rs_width_step3 {
+            cswap(b, a_f, r[j], s[j]);
+        }
     }
     if let Some((cr, cs)) = coeff {
         b.set_phase("kal_bulk_coeff_step3_cswap");
@@ -6637,18 +6692,31 @@ fn kaliski_iteration_bulk_prefix3(
     } else {
         u.len()
     };
-    for j in 0..rs_width_step9 {
-        cswap(b, a_f, r[j], s[j]);
-    }
-    if let Some((cr, cs)) = coeff {
-        b.set_phase("kal_bulk_coeff_step9_cswap");
-        coeff_channel_cswap(b, a_f, cr, cs);
+    if merge_rs && !is_last {
+        // DEFER the (r,s) STEP 9 cswap: carry a_k as the outgoing frame parity
+        // (allocated here, consumed by the next iter's merged step3). This
+        // qubit is NOT live during STEP 4 (allocated after step6_7_8, freed at
+        // the next step3 before step4) → peak-neutral. a_f (= a_k) is then
+        // reset to |0⟩ for free using the frame copy as select.
+        let frame_out = b.alloc_qubit();
+        b.cx(a_f, frame_out); // frame_out = a_k
+        b.cx(frame_out, a_f); // a_f = a_k ^ a_k = 0
+        *frame = Some(frame_out);
+    } else {
+        // Eager (r,s) STEP 9 (edge: last iter, or merge disabled), then STEP 10.
+        for j in 0..rs_width_step9 {
+            cswap(b, a_f, r[j], s[j]);
+        }
+        if let Some((cr, cs)) = coeff {
+            b.set_phase("kal_bulk_coeff_step9_cswap");
+            coeff_channel_cswap(b, a_f, cr, cs);
+        }
+        // STEP 10: uncompute a via a ^= NOT s[0].
+        b.x(s[0]);
+        b.cx(s[0], a_f);
+        b.x(s[0]);
     }
 
-    b.x(s[0]);
-    b.cx(s[0], a_f);
-    b.x(s[0]);
-
     b.x(f1);
     b.free(f1);
     b.free(add_f);
@@ -6668,8 +6736,12 @@ fn kaliski_iteration(
     f: QubitId,
     iter_idx: usize,
     coeff: Option<(&[QubitId], &[QubitId])>,
+    frame: &mut Option<QubitId>,
+    is_last: bool,
 ) {
     let n = u.len();
+    // (r,s) cswap boundary-merge is only valid on the default coeff=None channel.
+    let merge_rs = coeff.is_none() && kal_cswap_rs_merge_enabled();
     // Iter-local flags (zero at iter start and iter end): alloc fresh here
     // so they don't live during body (which sees lower peak by -3 qubits).
     let a_f = b.alloc_qubit();
@@ -6751,8 +6823,26 @@ fn kaliski_iteration(
         cswap(b, a_f, u[j], v_w[j]);
     }
     let rs_width_step3 = if iter_idx + 1 < n { iter_idx + 1 } else { n };
-    for j in 0..rs_width_step3 {
-        cswap(b, a_f, r[j], s[j]);
+    // (r,s) STEP 3 — merged with the deferred STEP 9 of the previous iter when
+    // merge_rs and an incoming frame parity is present. (See bulk variant.)
+    if let (true, Some(frame_in)) = (merge_rs, *frame) {
+        b.cx(frame_in, a_f); // a_f = a_{k-1} ⊕ a_k
+        for j in 0..rs_width_step3 {
+            cswap(b, a_f, r[j], s[j]);
+        }
+        b.cx(frame_in, a_f); // a_f = a_k (restored)
+        // Reset frame_in (= a_{k-1}) to |0⟩ via prev iter's step10 reroute,
+        // a_k (= a_f) as select: frame_in ^= NOT(a_f ? r[0] : s[0]).
+        b.cx(s[0], frame_in);
+        b.x(frame_in);
+        b.ccx(a_f, r[0], frame_in);
+        b.ccx(a_f, s[0], frame_in);
+        b.free(frame_in);
+        *frame = None;
+    } else {
+        for j in 0..rs_width_step3 {
+            cswap(b, a_f, r[j], s[j]);
+        }
     }
     if let Some((cr, cs)) = coeff {
         b.set_phase("kal_coeff_step3_cswap");
@@ -6879,22 +6969,26 @@ fn kaliski_iteration(
         cswap(b, a_f, u[j], v_w[j]);
     }
     let rs_width_step9 = if iter_idx + 2 < n { iter_idx + 2 } else { n };
-    for j in 0..rs_width_step9 {
-        cswap(b, a_f, r[j], s[j]);
-    }
-    if let Some((cr, cs)) = coeff {
-        b.set_phase("kal_coeff_step9_cswap");
-        coeff_channel_cswap(b, a_f, cr, cs);
+    if merge_rs && !is_last {
+        // DEFER the (r,s) STEP 9: carry a_k as the outgoing frame parity.
+        let frame_out = b.alloc_qubit();
+        b.cx(a_f, frame_out); // frame_out = a_k
+        b.cx(frame_out, a_f); // a_f = 0 (reset via frame copy)
+        *frame = Some(frame_out);
+    } else {
+        for j in 0..rs_width_step9 {
+            cswap(b, a_f, r[j], s[j]);
+        }
+        if let Some((cr, cs)) = coeff {
+            b.set_phase("kal_coeff_step9_cswap");
+            coeff_channel_cswap(b, a_f, cr, cs);
+        }
+        // ─── STEP 10: uncompute a via `a ^= NOT s[0]` ───
+        b.x(s[0]);
+        b.cx(s[0], a_f);
+        b.x(s[0]);
     }
 
-    // ─── STEP 10: uncompute a via `a ^= NOT s[0]` ───
-    // After STEP 9's swap, the invariant (from qrisp) is that
-    //   a == NOT s[0]
-    // Hence `cx(NOT s[0], a)` zeros a.
-    b.x(s[0]);
-    b.cx(s[0], a_f);
-    b.x(s[0]);
-
     // Free iter-local flags (all at 0 now).
     b.free(add_f);
     b.free(b_f);
@@ -7155,8 +7249,20 @@ fn kaliski_forward_with_coeff_caps(
 
     // ─── Iterations ───
     let use_bulk_prefix3 = bulk_prefix_enabled();
+    // When the bulk path merges but the generic path does not, the frame must
+    // NOT cross the bulk→generic boundary: the last bulk iter applies its step9
+    // eagerly (treated as "last") so no frame is handed to the generic tail.
+    let merge_boundary_break = use_bulk_prefix3
+        && kal_cswap_rs_merge_bulk_enabled()
+        && !kal_cswap_rs_merge_generic_enabled()
+        && bulk_caps.forward < iters;
+    let mut frame: Option<QubitId> = None;
     for i in 0..iters {
+        let mut is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_caps.forward {
+            if merge_boundary_break && i + 1 == bulk_caps.forward {
+                is_last = true;
+            }
             kaliski_iteration_bulk_prefix3(
                 b,
                 p,
@@ -7167,6 +7273,8 @@ fn kaliski_forward_with_coeff_caps(
                 st.m_hist[i],
                 i,
                 coeff,
+                &mut frame,
+                is_last,
             );
         } else {
             kaliski_iteration(
@@ -7180,9 +7288,12 @@ fn kaliski_forward_with_coeff_caps(
                 st.f_flag,
                 i,
                 coeff,
+                &mut frame,
+                is_last,
             );
         }
     }
+    debug_assert!(frame.is_none(), "kaliski forward frame not consumed");
 
     // After the loop for nonzero v_in, classical invariants give:
     //   u = 1, v_w = 0, f = 0, a = b = add = 0
@@ -7258,27 +7369,42 @@ fn kaliski_iteration_bulk_prefix3_backward(
     s: &[QubitId],
     m_i: QubitId,
     iter_idx: usize,
+    frame: &mut Option<QubitId>,
+    is_last: bool,
 ) {
     let n = u.len();
+    // (r,s) cswap boundary-merge — bulk backward is always coeff=None.
+    let merge_rs = kal_cswap_rs_merge_bulk_enabled();
     let a_f = b.alloc_qubit();
     let b_f = b.alloc_qubit();
     let add_f = b.alloc_qubit();
 
     let _kal_saved_phase = b.phase;
 
-    // Reverse STEP 10.
-    b.set_phase("bk_bulk_step10");
-    b.x(s[0]);
-    b.cx(s[0], a_f);
-    b.x(s[0]);
-
-    // Reverse STEP 9.
-    b.set_phase("bk_bulk_step9_cswap");
+    // Reverse STEP 10 + STEP 9 (r,s).
     let rs_width_step9 = if iter_idx + 2 < n { iter_idx + 2 } else { n };
-    for j in (0..rs_width_step9).rev() {
-        cswap(b, a_f, r[j], s[j]);
+    if merge_rs && !is_last {
+        // Reverse of forward step9-defer: recreate a_f = a_k from the incoming
+        // frame parity, then zero+free the frame.
+        b.set_phase("bk_bulk_step9_cswap");
+        let frame_in = frame.expect("merged backward expects an incoming frame");
+        b.cx(frame_in, a_f); // a_f = a_k
+        b.cx(a_f, frame_in); // frame = 0
+        b.free(frame_in);
+        *frame = None;
+    } else {
+        // Eager reverse STEP 10 then STEP 9 (r,s) — edge (last iter) / merge off.
+        b.set_phase("bk_bulk_step10");
+        b.x(s[0]);
+        b.cx(s[0], a_f);
+        b.x(s[0]);
+        b.set_phase("bk_bulk_step9_cswap");
+        for j in (0..rs_width_step9).rev() {
+            cswap(b, a_f, r[j], s[j]);
+        }
     }
-    // Late-iter truncation mirrors forward step9.
+    // Reverse STEP 9 (u,v) — always eager.
+    b.set_phase("bk_bulk_step9_cswap");
     let uv_width_step9 = if iter_idx < n { n } else { 2 * n - iter_idx };
     for j in (0..uv_width_step9).rev() {
         cswap(b, a_f, u[j], v_w[j]);
@@ -7368,8 +7494,28 @@ fn kaliski_iteration_bulk_prefix3_backward(
     // Reverse STEP 3.
     b.set_phase("bk_bulk_step3_cswap");
     let rs_width_step3 = if iter_idx + 1 < n { iter_idx + 1 } else { n };
-    for j in (0..rs_width_step3).rev() {
-        cswap(b, a_f, r[j], s[j]);
+    // Reverse of the forward (r,s) STEP 3. When merged, recreate the outgoing
+    // frame parity (= a_{k-1}) and hand it to the previous (backward-later) iter.
+    // Iter 0's forward step3 is an explicit edge (no incoming frame), so its
+    // reverse is the plain eager cswap.
+    if merge_rs && iter_idx != 0 {
+        let frame_out = b.alloc_qubit();
+        // Reverse reroute (recreate frame_out = a_{k-1}), a_f = a_k as select.
+        b.ccx(a_f, s[0], frame_out);
+        b.ccx(a_f, r[0], frame_out);
+        b.x(frame_out);
+        b.cx(s[0], frame_out);
+        // Reverse the merged cswap: control a_{k-1} ⊕ a_k.
+        b.cx(frame_out, a_f); // a_f = a_{k-1} ⊕ a_k
+        for j in (0..rs_width_step3).rev() {
+            cswap(b, a_f, r[j], s[j]);
+        }
+        b.cx(frame_out, a_f); // a_f = a_k (restored)
+        *frame = Some(frame_out);
+    } else {
+        for j in (0..rs_width_step3).rev() {
+            cswap(b, a_f, r[j], s[j]);
+        }
     }
     // Late-iter truncation mirrors forward step3.
     let uv_width_step3 = if iter_idx < n { n } else { 2 * n - iter_idx };
@@ -7427,8 +7573,12 @@ fn kaliski_iteration_backward(
     m_i: QubitId,
     f: QubitId,
     iter_idx: usize,
+    frame: &mut Option<QubitId>,
+    is_last: bool,
 ) {
     let n = u.len();
+    // (r,s) cswap boundary-merge — generic backward is always coeff=None here.
+    let merge_rs = kal_cswap_rs_merge_generic_enabled();
     // Iter-local flags alloc'd fresh (zero at iter start in the backward
     // direction). They are zeroed and freed at iter end to match forward.
     let a_f = b.alloc_qubit();
@@ -7436,20 +7586,29 @@ fn kaliski_iteration_backward(
     let add_f = b.alloc_qubit();
 
     let _kal_saved_phase = b.phase;
-    b.set_phase("bk_step10");
-    // Reverse STEP 10
-    // Matches forward's gated update.
-    b.x(s[0]);
-    b.ccx(f, s[0], a_f);
-    b.x(s[0]);
-
-    // ── Reverse STEP 9 ─────────────────────────────────────────────────
+    // ── Reverse STEP 10 + STEP 9 (r,s) ─────────────────────────────────
     let rs_width_step9 = if iter_idx + 2 < n { iter_idx + 2 } else { n };
+    if merge_rs && !is_last {
+        // Reverse of forward step9-defer: recreate a_f = a_k from incoming frame.
+        b.set_phase("bk_step9_cswap");
+        let frame_in = frame.expect("merged backward expects an incoming frame");
+        b.cx(frame_in, a_f); // a_f = a_k
+        b.cx(a_f, frame_in); // frame = 0
+        b.free(frame_in);
+        *frame = None;
+    } else {
+        b.set_phase("bk_step10");
+        // Reverse STEP 10. Matches forward's gated update.
+        b.x(s[0]);
+        b.ccx(f, s[0], a_f);
+        b.x(s[0]);
+        b.set_phase("bk_step9_cswap");
+        for j in (0..rs_width_step9).rev() {
+            cswap(b, a_f, r[j], s[j]);
+        }
+    }
     let uv_width = if iter_idx < n { n } else { 2 * n - iter_idx };
     b.set_phase("bk_step9_cswap");
-    for j in (0..rs_width_step9).rev() {
-        cswap(b, a_f, r[j], s[j]);
-    }
     for j in (0..uv_width).rev() {
         cswap(b, a_f, u[j], v_w[j]);
     }
@@ -7549,8 +7708,25 @@ fn kaliski_iteration_backward(
     // Reverse STEP 3 ─────────────────────────────────────────────────
     let rs_width_step3 = if iter_idx + 1 < n { iter_idx + 1 } else { n };
     let uv_width = if iter_idx < n { n } else { 2 * n - iter_idx };
-    for j in (0..rs_width_step3).rev() {
-        cswap(b, a_f, r[j], s[j]);
+    // Reverse of forward (r,s) STEP 3: recreate the outgoing frame parity when
+    // merged. Iter 0 forward step3 was an explicit edge → plain eager reverse.
+    if merge_rs && iter_idx != 0 {
+        let frame_out = b.alloc_qubit();
+        // Reverse reroute (recreate frame_out = a_{k-1}), a_f = a_k as select.
+        b.ccx(a_f, s[0], frame_out);
+        b.ccx(a_f, r[0], frame_out);
+        b.x(frame_out);
+        b.cx(s[0], frame_out);
+        b.cx(frame_out, a_f); // a_f = a_{k-1} ⊕ a_k
+        for j in (0..rs_width_step3).rev() {
+            cswap(b, a_f, r[j], s[j]);
+        }
+        b.cx(frame_out, a_f); // a_f = a_k (restored)
+        *frame = Some(frame_out);
+    } else {
+        for j in (0..rs_width_step3).rev() {
+            cswap(b, a_f, r[j], s[j]);
+        }
     }
     for j in (0..uv_width).rev() {
         cswap(b, a_f, u[j], v_w[j]);
@@ -7659,8 +7835,17 @@ fn kaliski_backward_caps(
 
     let use_bulk_prefix3 = bulk_prefix_enabled();
     // ─── Reverse iterations (in reverse order) ───
+    let merge_boundary_break = use_bulk_prefix3
+        && kal_cswap_rs_merge_bulk_enabled()
+        && !kal_cswap_rs_merge_generic_enabled()
+        && bulk_caps.backward < iters;
+    let mut frame: Option<QubitId> = None;
     for i in (0..iters).rev() {
+        let mut is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_caps.backward {
+            if merge_boundary_break && i + 1 == bulk_caps.backward {
+                is_last = true;
+            }
             kaliski_iteration_bulk_prefix3_backward(
                 b,
                 p,
@@ -7670,6 +7855,8 @@ fn kaliski_backward_caps(
                 &st.s,
                 st.m_hist[i],
                 i,
+                &mut frame,
+                is_last,
             );
         } else {
             kaliski_iteration_backward(
@@ -7682,9 +7869,12 @@ fn kaliski_backward_caps(
                 st.m_hist[i],
                 st.f_flag,
                 i,
+                &mut frame,
+                is_last,
             );
         }
     }
+    debug_assert!(frame.is_none(), "kaliski backward frame not consumed");
 
     // ─── Reverse Init ───
     b.x(st.f_flag);
@@ -8734,7 +8924,9 @@ fn kaliski_forward_alias_v_w_caps(
     b.x(st.f_flag);
 
     let use_bulk_prefix3 = bulk_prefix_enabled();
+    let mut frame: Option<QubitId> = None;
     for i in 0..iters {
+        let is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_caps.forward {
             kaliski_iteration_bulk_prefix3(
                 b,
@@ -8746,6 +8938,8 @@ fn kaliski_forward_alias_v_w_caps(
                 st.m_hist[i],
                 i,
                 None,
+                &mut frame,
+                is_last,
             );
         } else {
             kaliski_iteration(
@@ -8759,9 +8953,12 @@ fn kaliski_forward_alias_v_w_caps(
                 st.f_flag,
                 i,
                 None,
+                &mut frame,
+                is_last,
             );
         }
     }
+    debug_assert!(frame.is_none(), "kaliski alias forward frame not consumed");
 }
 
 fn kaliski_backward_alias_v_w_caps(
@@ -8774,7 +8971,9 @@ fn kaliski_backward_alias_v_w_caps(
     debug_assert!(iters <= st.m_hist.len());
 
     let use_bulk_prefix3 = bulk_prefix_enabled();
+    let mut frame: Option<QubitId> = None;
     for i in (0..iters).rev() {
+        let is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_caps.backward {
             kaliski_iteration_bulk_prefix3_backward(
                 b,
@@ -8785,6 +8984,8 @@ fn kaliski_backward_alias_v_w_caps(
                 &st.s,
                 st.m_hist[i],
                 i,
+                &mut frame,
+                is_last,
             );
         } else {
             kaliski_iteration_backward(
@@ -8797,9 +8998,12 @@ fn kaliski_backward_alias_v_w_caps(
                 st.m_hist[i],
                 st.f_flag,
                 i,
+                &mut frame,
+                is_last,
             );
         }
     }
+    debug_assert!(frame.is_none(), "kaliski alias backward frame not consumed");
 
     b.x(st.f_flag);
     b.x(st.s[0]);
@@ -8925,7 +9129,9 @@ fn kaliski_forward_prescaled_kind(
 
     let use_bulk_prefix3 = bulk_prefix_enabled();
     let bulk_prefix_iters = bulk_prefix_safe_iters();
+    let mut frame: Option<QubitId> = None;
     for i in 0..iters {
+        let is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_prefix_iters {
             kaliski_iteration_bulk_prefix3(
                 b,
@@ -8937,6 +9143,8 @@ fn kaliski_forward_prescaled_kind(
                 st.m_hist[i],
                 i,
                 None,
+                &mut frame,
+                is_last,
             );
         } else {
             kaliski_iteration(
@@ -8950,9 +9158,12 @@ fn kaliski_forward_prescaled_kind(
                 st.f_flag,
                 i,
                 None,
+                &mut frame,
+                is_last,
             );
         }
     }
+    debug_assert!(frame.is_none(), "kaliski prescaled forward frame not consumed");
 }
 
 fn kaliski_backward_prescaled_mixed(
@@ -8991,7 +9202,9 @@ fn kaliski_backward_prescaled_kind(
 
     let use_bulk_prefix3 = bulk_prefix_enabled();
     let bulk_prefix_iters = bulk_prefix_safe_iters();
+    let mut frame: Option<QubitId> = None;
     for i in (0..iters).rev() {
+        let is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_prefix_iters {
             kaliski_iteration_bulk_prefix3_backward(
                 b,
@@ -9002,6 +9215,8 @@ fn kaliski_backward_prescaled_kind(
                 &st.s,
                 st.m_hist[i],
                 i,
+                &mut frame,
+                is_last,
             );
         } else {
             kaliski_iteration_backward(
@@ -9014,9 +9229,12 @@ fn kaliski_backward_prescaled_kind(
                 st.m_hist[i],
                 st.f_flag,
                 i,
+                &mut frame,
+                is_last,
             );
         }
     }
+    debug_assert!(frame.is_none(), "kaliski prescaled backward frame not consumed");
 
     b.x(st.f_flag);
     b.x(st.s[0]);
```

