# bfd3fa6 — Erase the apply chunk-boundary carries by measurement and run their exact replay only when the outcome is 1

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-08 |
| Submission | `4b7d727` |
| Commit | `bfd3fa65a9197fa2e9139c80eb632b76ae63f25c` |
| Result | 1300 qubits × 1,404,058 Toffoli = **1,825,275,400** |
| Base | `73f4f48` (gnuchev, git parent and frontier at the time): 1300 qubits × 1,454,884 Toffoli = 1,891,349,200 |
| Change vs base | qubits ±0, Toffoli −50,826, score −66,073,800 (leaderboard Δ −66,073,800) |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [adders-and-carries](../concepts/adders-and-carries.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Each of the 258 apply steps of each dialog-GCD division does one controlled
256-bit modular add (or subtract). The add is split into chunks at bits 50,
100, 150 and 189, and each chunk leaves its carry-out on a "boundary" wire.
Those four carry wires must be returned to 0 afterwards. The base did this
with an exact comparator sweep over the low 189 bits, which recomputes each
prefix carry and XORs it into its wire, at about 193 Toffoli per call.

This commit instead measures each boundary carry in the X basis and resets
it, which costs no Toffoli. The measurement leaves a phase error only when
its outcome is 1. In that case a classically conditioned block recomputes
that carry, applies a CZ to fix the phase, and erases the recompute again.
The conditioned Toffoli run on about half the shots, so the average cost
falls from about 193 to about 95 per call. Over 2 × 258 = 516 calls that is
the measured −50,826 Toffoli. Qubits are unchanged.

## What changed and why it saves Toffoli

1. **New pin `DIALOG_GCD_APPLY_BOUNDARY_CONDITIONAL_REPLAY=1`** in
   `configure_ecdsafail_submission_route()` (`src/point_add/mod.rs`), read by
   the new `dialog_gcd_apply_boundary_conditional_replay_enabled()` in
   `rounds/dialog/config.rs`.
2. **The boundary clear** in `dialog_gcd_add_ctrl_chunked_low_to_ext` and
   `dialog_gcd_sub_ctrl_chunked_low_to_ext` (`rounds/dialog/mod.rs`).
   - On this route the apply add uses `DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS=5`
     with cuts `50, 100, 150, 189`, so there are four boundary targets
     `(cout_i, p_i)`.
   - Base path: `ccx_cmp_lt_into_fast_prefix_targets_split` with
     `DIALOG_GCD_APPLY_BOUNDARY_SPLIT=100`. It runs one ripple comparator of
     `acc < source` over the low 189 bits, at one CCX per bit, plus one
     `ccx(ctrl, ·, cout_i)` per target, then a measured inverse with no
     Toffoli. This is about 189 + 4 = 193 Toffoli on every shot.
   - New path: the new function `dialog_gcd_conditional_boundary_replay`
     takes priority over the split path. It walks the targets from the
     highest to the lowest. For each one:
     ```
     phase = alloc_bit(); hmr(cout_i, phase)          // X-basis measure + reset, 0 Toffoli
     if phase:                                        // classical condition
         compare acc[p_{i-1}..p_i] < src[p_{i-1}..p_i] with carry-in cout_{i-1}
         cz(ctrl, carry_out)                          // apply (-1)^(ctrl · cout_i)
         uncompute the compare (measured, 0 Toffoli)
     ```
     The carry-in of each segment is the next-lower boundary wire, which is
     still alive because the walk goes top down. For the lowest segment it
     is the add's own `c_in`. So each segment compare reproduces the full
     prefix carry at `p_i` while scanning only `p_i − p_{i−1}` bits.
   - The segment compares cover 50 + 50 + 50 + 39 = 189 bits, at one CCX per
     bit, and each runs only when its outcome bit is 1, which is about half
     the shots. The per-target `ccx` into the wires is gone, because the
     measurement replaces it. Average: about 189 / 2 ≈ 95 Toffoli per call,
     a saving of about 98.5. Times 516 calls gives the measured −50,826.
   - The subtract twin calls the same function with the operands swapped
     (`source` before `acc_ext`), because a borrow out is `source > acc`
     on the prefix.
3. **New helper `cmp_lt_phase_conditioned_with_cin`** in `arith/compare.rs`.
   It wraps the existing `cmp_lt_fast_prefix_window_forward` /
   `_inverse` pair between `push_condition(phase)` and `pop_condition()`,
   with a fresh carry array of the segment's length and a `cz(ctrl, u[n−1])`
   in the middle.
4. **New builder methods** on `B` in `mod.rs`: `cz` (a CZ, or a Z when both
   operands coincide), `push_condition` and `pop_condition` (emit the
   `PushCondition` / `PopCondition` ops that make the enclosed gates
   classically conditional).
5. **`DIALOG_TAIL_NONCE`: 169924627 → 9400002898194.**

This is the [measurement-uncompute](../concepts/measurement-uncompute.md)
pattern: measure the garbage, then repair the phase only on the shots that
need it. The score counts *executed* Toffoli, so a conditioned repair costs
half on average. See [scoring-and-validation](../concepts/scoring-and-validation.md).
The emitted Toffoli count barely changes. The author's note gives 1,452,820
emitted, and argues that on real hardware the emitted count is the physical
cost.

## Why it is still correct, and what it risks

The change is exact. Measuring `cout_i` in the X basis and resetting it
leaves the phase `(−1)^(phase · cout_i)` on the remaining state. The
conditioned block recomputes `cout_i = ctrl ∧ carry_{p_i}(acc, source)`
exactly, from the live registers and the still-unmeasured lower boundary
wire, and the CZ cancels that phase. The recompute's own carries are
uncomputed by measurement with `cz_if` fixes, as in the base. No input can
break this, so Lambda does not change. The nonce was re-hunted only because
the op stream changed.

A wrong recompute would leave a phase error, which the evaluator reports as
phase garbage. The shipped nonce `9400002898194` draws a test set with
0 classical, 0 phase and 0 ancilla failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The Toffoli are saved by replacing an exact recompute-and-XOR erase with a
measurement erase plus a conditioned phase repair. That is measurement
uncompute.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 73f4f48 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 73f4f48 bfd3fa6 -- src/point_add` is
   117 lines in 4 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol bfd3fa6 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set. Expect:
   - 1300 qubits
   - 1,404,058 average Toffoli (rounded)
   - score 1,825,275,400
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9400002898194` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/compare.rs b/src/point_add/arith/compare.rs
index cdce1f0..f2accb2 100644
--- a/src/point_add/arith/compare.rs
+++ b/src/point_add/arith/compare.rs
@@ -297,6 +297,36 @@ pub(crate) fn cmp_lt_fast_prefix_window_inverse(
     b.cx(u[0], v[0]);
 }
 
+/// Apply the HMR phase correction for one comparator carry. The exact
+/// nonlinear replay is classically conditioned on the HMR result, so its CCX
+/// gates execute on half the shots on average.
+pub(crate) fn cmp_lt_phase_conditioned_with_cin(
+    b: &mut B,
+    u: &[QubitId],
+    v: &[QubitId],
+    c_in: QubitId,
+    ctrl: QubitId,
+    phase: BitId,
+) {
+    let n = u.len();
+    assert_eq!(v.len(), n);
+    assert!(n > 0);
+
+    b.push_condition(phase);
+    for &q in u {
+        b.x(q);
+    }
+    let carries = b.alloc_qubits(n);
+    cmp_lt_fast_prefix_window_forward(b, u, v, c_in, &carries, ctrl, &[]);
+    b.cz(ctrl, u[n - 1]);
+    cmp_lt_fast_prefix_window_inverse(b, u, v, c_in, &carries);
+    b.free_vec(&carries);
+    for &q in u {
+        b.x(q);
+    }
+    b.pop_condition();
+}
+
 pub(crate) fn ccx_cmp_lt_into_fast_prefix_targets_split(
     b: &mut B,
     u: &[QubitId],
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 15c9964..a027984 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -437,6 +437,31 @@ impl B {
         op.q_target = tgt;
         self.push_op(op);
     }
+    fn cz(&mut self, a: QubitId, b: QubitId) {
+        if a == b {
+            let mut op = Op::empty();
+            op.kind = OperationType::Z;
+            op.q_target = a;
+            self.push_op(op);
+            return;
+        }
+        let mut op = Op::empty();
+        op.kind = OperationType::CZ;
+        op.q_control1 = a;
+        op.q_target = b;
+        self.push_op(op);
+    }
+    fn push_condition(&mut self, cond: BitId) {
+        let mut op = Op::empty();
+        op.kind = OperationType::PushCondition;
+        op.c_condition = cond;
+        self.push_op(op);
+    }
+    fn pop_condition(&mut self) {
+        let mut op = Op::empty();
+        op.kind = OperationType::PopCondition;
+        self.push_op(op);
+    }
     fn swap(&mut self, a: QubitId, b: QubitId) {
         if a == b {
             return;
@@ -1072,6 +1097,7 @@ fn configure_ecdsafail_submission_route() {
     // shots: 1309 x 1,503,355 = 1,967,891,695, beats the 1,968,064,139 frontier
     // by 172,444).
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
+    set_default_env("DIALOG_GCD_APPLY_BOUNDARY_CONDITIONAL_REPLAY", "1");  // BAKED: condrep ON for env-less grader build
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_K2", "1");
     // Both-phase apply fold-fusion (fused double_y + halve_y Solinas folds,
@@ -1370,7 +1396,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "169924627");
+    set_default_env("DIALOG_TAIL_NONCE", "9400002898194");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
diff --git a/src/point_add/rounds/dialog/config.rs b/src/point_add/rounds/dialog/config.rs
index ea42204..1e38ede 100644
--- a/src/point_add/rounds/dialog/config.rs
+++ b/src/point_add/rounds/dialog/config.rs
@@ -194,6 +194,13 @@ pub(crate) fn dialog_gcd_apply_boundary_split() -> Option<usize> {
         .filter(|&split| split > 0)
 }
 
+pub(crate) fn dialog_gcd_apply_boundary_conditional_replay_enabled() -> bool {
+    std::env::var("DIALOG_GCD_APPLY_BOUNDARY_CONDITIONAL_REPLAY")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
 pub(crate) fn dialog_gcd_apply_replay_swap_host_enabled() -> bool {
     // Prototype, deliberately NOT enabled by configure_ecdsafail_submission_route.
     //
diff --git a/src/point_add/rounds/dialog/mod.rs b/src/point_add/rounds/dialog/mod.rs
index 18869fd..bb37699 100644
--- a/src/point_add/rounds/dialog/mod.rs
+++ b/src/point_add/rounds/dialog/mod.rs
@@ -1070,6 +1070,36 @@ pub(crate) fn dialog_gcd_chunk_hi(blocks: usize, block: usize, ext_n: usize) ->
     ((block + 1) * ext_n) / blocks
 }
 
+fn dialog_gcd_conditional_boundary_replay(
+    b: &mut B,
+    u: &[QubitId],
+    v: &[QubitId],
+    ctrl: QubitId,
+    c_in: QubitId,
+    targets: &[(QubitId, usize)],
+) {
+    assert!(!targets.is_empty());
+    assert!(targets.windows(2).all(|w| w[0].1 < w[1].1));
+    for index in (0..targets.len()).rev() {
+        let (target, p) = targets[index];
+        let (start, carry_in) = if index == 0 {
+            (0, c_in)
+        } else {
+            (targets[index - 1].1, targets[index - 1].0)
+        };
+        let phase = b.alloc_bit();
+        b.hmr(target, phase);
+        cmp_lt_phase_conditioned_with_cin(
+            b,
+            &u[start..p],
+            &v[start..p],
+            carry_in,
+            ctrl,
+            phase,
+        );
+    }
+}
+
 pub(crate) fn dialog_gcd_add_ctrl_chunked_low_to_ext(
     b: &mut B,
     source: &[QubitId],
@@ -1170,7 +1200,16 @@ pub(crate) fn dialog_gcd_add_ctrl_chunked_low_to_ext(
                 .iter()
                 .map(|&(cout, p, _)| (cout, p))
                 .collect::<Vec<_>>();
-            if let Some(split) = dialog_gcd_apply_boundary_split() {
+            if dialog_gcd_apply_boundary_conditional_replay_enabled() {
+                dialog_gcd_conditional_boundary_replay(
+                    b,
+                    &acc_ext[..p],
+                    &source[..p],
+                    ctrl,
+                    c_in,
+                    &targets,
+                );
+            } else if let Some(split) = dialog_gcd_apply_boundary_split() {
                 ccx_cmp_lt_into_fast_prefix_targets_split(
                     b,
                     &acc_ext[..p],
@@ -1297,7 +1336,16 @@ pub(crate) fn dialog_gcd_sub_ctrl_chunked_low_to_ext(
                 .iter()
                 .map(|&(bout, p, _)| (bout, p))
                 .collect::<Vec<_>>();
-            if let Some(split) = dialog_gcd_apply_boundary_split() {
+            if dialog_gcd_apply_boundary_conditional_replay_enabled() {
+                dialog_gcd_conditional_boundary_replay(
+                    b,
+                    &source[..p],
+                    &acc_ext[..p],
+                    ctrl,
+                    c_in,
+                    &targets,
+                );
+            } else if let Some(split) = dialog_gcd_apply_boundary_split() {
                 ccx_cmp_lt_into_fast_prefix_targets_split(
                     b,
                     &source[..p],
```

