# ba3efc1 — Skip bit 0 of the vented GCD-step subtract and reverse add, and undo the previous commit's two tightenings

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-18 |
| Submission | `48fb635` |
| Commit | `ba3efc105de099089de195497b85c08bbd3e83f9` |
| Result | 1168 qubits × 1,431,621 Toffoli = **1,672,133,328** |
| Base | `1caf521` (git parent, mpjunior92): 1168 qubits × 1,432,332 Toffoli = 1,672,963,776 |
| Change vs base | qubits ±0, Toffoli −711, score −830,448 (leaderboard Δ −830,448) |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In each dialog-GCD step, the work register `v` gets `v −= b0·u`, where `b0` is
a copy of `v`'s low bit and `u` is always odd. Bit 0 of that subtraction is
therefore known: it is `v[0] ⊕ b0` with no borrow. The old code still ran it
through the vented Cuccaro adder. The new code does bit 0 with one CNOT and
runs the adder from bit 1. The same holds for the mirror add that undoes the
step.

The commit also puts `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS = 19` and
`DIALOG_GCD_WIDTH_SLOPE_X1000 = 1015` at the top of the route. Because the
first setting wins, this undoes both of the parent's tightenings
([`1caf521`](1caf521.md)). The net result is 711 fewer average Toffoli than the
parent at the same 1168 qubits. Against the grandparent [`35ceb01`](35ceb01.md),
which has the same two settings, it is 2,055 fewer.

## What changed and why it saves Toffoli

### Bit-0 skip in the vented body (`src/point_add/rounds/dialog/mod.rs`)

- `emit_dialog_gcd_raw_tobitvector_steps()` runs each GCD step:
  1. Copy `v[0]` into the log bit `b0`.
  2. Compute `b0∧b1` with a truncated compare.
  3. Cswap `u` and `v` under `b0∧b1`. With `DIALOG_GCD_ODD_U_LOWBIT_FASTPATH`
     the swap already skips bit 0, because both values are odd when it fires.
  4. Call `dialog_gcd_controlled_sub_selected(u_active, v_active, b0, …)`, so
     `v −= b0·u`.
- With `DIALOG_GCD_RAW_TOBITVECTOR_MATERIALIZED_SUB = 0` and
  `DIALOG_GCD_CTRL_BODY_VENTED = 1`, the live branch is
  `cuccaro_sub_ctrl_vented(subtrahend, acc, ctrl, vents)` over the whole
  active width. The materialized branch already had an "odd low bit" fast path
  (`body_start = 1`), but that branch is not used in this route.
- New `dialog_gcd_vented_body_odd_lowbit_enabled()` reads
  `DIALOG_GCD_VENTED_BODY_ODD_LOWBIT`. When it is on, the odd-u fast path is
  on and the body is at least 3 bits wide, the vented branch now does
  `b.cx(ctrl, acc[0])` and then
  `cuccaro_sub_ctrl_vented(&subtrahend[1..bw], &acc[1..bw], ctrl, &vents[..bw − 2])`.
  `dialog_gcd_controlled_add_selected` does the same for the reverse add.
- Why it is exact: `u` is odd (`subtrahend[0] = 1`), and at the subtract
  `acc[0] = v[0] = b0 = ctrl`. So bit 0 of `acc − ctrl·u` is `acc[0] ⊕ ctrl`,
  and the borrow out of bit 0 is `ctrl ∧ ¬acc[0] = 0`. At the reverse-add site
  `acc[0] = 0` and `addend[0] = 1`, so again the bit is a CNOT and there is no
  carry.
- The adder becomes one bit shorter. That saves the Toffoli of one controlled
  ripple cell and one vent, in every GCD step of every GCD pass, forward and
  reverse. See [adders-and-carries](../concepts/adders-and-carries.md) and
  [venting-and-wire-loans](../concepts/venting-and-wire-loans.md).
- Also added but off: `dialog_gcd_vented_body_band_trim_enabled()`
  (`DIALOG_GCD_VENTED_BODY_BAND_TRIM`), and the width helper
  `dialog_gcd_vented_body_width()` with `DIALOG_GCD_VENTED_BODY_UNIFORM_TRIM`
  and `_TRIM_CAP`, for trimming the top of the vented body. The knob is not
  set, so `bw = n`.

### Route settings (`src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`)

- New first lines:
  - `DIALOG_GCD_VENTED_BODY_ODD_LOWBIT = "1"`;
  - `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS = "19"`;
  - `DIALOG_GCD_WIDTH_SLOPE_X1000 = "1015"`.

  The parent's `"18"` and `"1017"` lines are still in the file further down,
  but `set_default_env` keeps the first value. So the apply clean compare is
  back to 19 bits and the GCD width envelope is back to slope 1.015, which
  restores the 35 steps that 1caf521 had narrowed by 2 bits.
- `DIALOG_TAIL_NONCE`: `"2150000021998006"` → `"200005858317"`, in all three
  places.
- The submission note mentions only the bit-0 lever. It does not say that
  1caf521's two cuts were reverted. A likely reason: the lever was ported from
  a 35ceb01-era tree and its settings were pinned at the top.

## Why it is still correct, and what it risks

- **Exact.** The bit-0 skip is exact on every input, not just likely ones. It
  depends only on the invariants that `u` stays odd and that `b0` is a copy of
  `v[0]`, and both hold by construction. It adds no new failure mode.
- **Safer.** Undoing 1caf521's two tightenings removes that commit's extra
  risk:
  - fewer tied top-bit compares in the apply phase, each of which would be a
    phase error;
  - fewer GCD register overflows on slow-shrinking inputs, each of which would
    be a classical error.

  Lambda is back to the 35ceb01 level.
- **Nonce.** Nonce `200005858317` draws a clean set: 0 classical, 0 phase and
  0 ancilla failures over 9,024 shots. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The lever removes gates whose effect is known in advance: one bit position of
a ripple adder whose result is a fixed CNOT and whose carry is always 0. That
is dead-gate removal. The two reverted settings are a choice about how much
Lambda to spend, not a separate lever. Note that the leaderboard Δ against the
parent understates the lever, because the parent's cuts were given back.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 1caf521 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 1caf521 ba3efc1 -- src/point_add` is
   84 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol ba3efc1 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `SQUARE_*`, `MOD_*` or `KAL_*` environment variables set. Expect:
   - 1168 qubits
   - 1,431,621 average Toffoli (rounded)
   - score 1,672,133,328
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `200005858317` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 83cb752..f35c44d 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1005,6 +1005,9 @@ fn set_default_env(name: &str, value: &str) {
 }
 
 fn configure_ecdsafail_submission_route() {
+    set_default_env("DIALOG_GCD_VENTED_BODY_ODD_LOWBIT", "1");
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1015");
     set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("DIALOG_GCD_FOLD_FREE_FIRST_HIGH_CARRY", "1");
     // q1168 host-E route. These defaults are first so the historical fallback
@@ -1103,7 +1106,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_TOBITVECTOR_CSWAP_BODY_TRIM", "0");
     set_default_env("DIALOG_GCD_WIDTH_MARGIN", "10");
     set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1017");
-    set_default_env("DIALOG_TAIL_NONCE", "2150000021998006");
+    set_default_env("DIALOG_TAIL_NONCE", "200005858317");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "19");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("SQUARE_ROW_MAX_SEG", "141");
@@ -1128,7 +1131,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR", "1");
     set_default_env("ROUND84_KEEP_QUOTIENT_PRODUCT", "1");
     set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "17");
-    set_default_env("DIALOG_TAIL_NONCE", "2150000021998006");
+    set_default_env("DIALOG_TAIL_NONCE", "200005858317");
     set_default_env("DIALOG_GCD_SKIP_ZERO_EDGE_CSHIFT", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_HOST_REVERSE_RAW_BLOCK", "1");
@@ -1579,7 +1582,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "2150000021998006");
+    set_default_env("DIALOG_TAIL_NONCE", "200005858317");
     set_default_env("ROUND84_FOLD_FAST_ADD", "0");  // round84 Solinas-fold small adders coherent->measured-fast (-1,434 exec-T, peak-neutral 1285)
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_FOLD_MAJ1", "1");
diff --git a/src/point_add/rounds/dialog/mod.rs b/src/point_add/rounds/dialog/mod.rs
index f82e20b..b3898c5 100644
--- a/src/point_add/rounds/dialog/mod.rs
+++ b/src/point_add/rounds/dialog/mod.rs
@@ -412,6 +412,55 @@ pub(crate) fn dialog_gcd_body_carry_trunc_width(active_width: usize, step: usize
     active_width.saturating_sub(w).max(2)
 }
 
+/// Band-trim the LIVE (vented) divstep body sub/add to body_carry_trunc_width,
+/// mirroring the materialized-path trim (which is baked+validated) onto the
+/// cuccaro_*_ctrl_vented else-branch that currently runs full active_width. The
+/// trimmed-off top cells are |0> on reachable GCD support (WIDTH_MARGIN premise)
+/// and the post-cswap body never borrows past the active operand, so the result
+/// is value-exact on that support. Default OFF = byte-identical.
+pub(crate) fn dialog_gcd_vented_body_band_trim_enabled() -> bool {
+    std::env::var("DIALOG_GCD_VENTED_BODY_BAND_TRIM").ok().as_deref() == Some("1")
+}
+
+/// Effective vented-body sub/add width at this step. OFF => full active_width n.
+/// With the knob ON it mirrors body_carry_trunc_width (the baked schedule);
+/// DIALOG_GCD_VENTED_BODY_UNIFORM_TRIM=N overrides with a flat (n-N) trim so the
+/// score/lambda_cl Pareto can be swept (N=1 conservative .. larger = more lossy).
+pub(crate) fn dialog_gcd_vented_body_width(n: usize, step: usize) -> usize {
+    if !dialog_gcd_vented_body_band_trim_enabled() {
+        return n;
+    }
+    if let Some(u) = std::env::var("DIALOG_GCD_VENTED_BODY_UNIFORM_TRIM")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .filter(|&u| u > 0)
+    {
+        return n.saturating_sub(u).max(2);
+    }
+    let mut w = dialog_gcd_body_carry_trunc_width(n, step).min(n).max(2);
+    // Optional per-step trim CAP: cap the schedule's trim at K bits (w >= n-K).
+    // With overshoot<=8 < WIDTH_MARGIN=10, cap=2 keeps the trimmed cells |0> on
+    // ALL reachable inputs (bitlen <= active_width-2) => value-exact-always =>
+    // density-neutral, trading a little cut for a guaranteed-clean island.
+    if let Some(cap) = std::env::var("DIALOG_GCD_VENTED_BODY_TRIM_CAP")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+    {
+        w = w.max(n.saturating_sub(cap)).min(n);
+    }
+    w
+}
+
+/// Skip bit 0 of the LIVE vented divstep body (mirrors the materialized
+/// body_start=1 fastpath, which is wired only to the dead MATERIALIZED_SUB
+/// branch). Kaliski invariant: u kept odd (subtrahend[0]=1) and acc[0]=ctrl at
+/// the sub site / acc[0]=0 at the reverse-add site, so the bit-0 result is a
+/// known cx(ctrl,acc[0]) with NO carry into bit 1 — value-exact, density-neutral,
+/// orthogonal to the band-trim (band trims the top, this the bottom). Default OFF.
+pub(crate) fn dialog_gcd_vented_body_odd_lowbit_enabled() -> bool {
+    std::env::var("DIALOG_GCD_VENTED_BODY_ODD_LOWBIT").ok().as_deref() == Some("1")
+}
+
 pub(crate) fn dialog_gcd_binder_notch_steps() -> Vec<usize> {
     std::env::var("DIALOG_GCD_BINDER_NOTCH_STEPS")
         .ok()
@@ -786,7 +835,18 @@ pub(crate) fn dialog_gcd_controlled_sub_selected(
             if let Some(vents) =
                 borrowed_carries.filter(|c| n >= 2 && c.len() >= n - 1)
             {
-                cuccaro_sub_ctrl_vented(b, subtrahend, acc, ctrl, &vents[..n - 1]);
+                let bw = dialog_gcd_vented_body_width(n, step);
+                if dialog_gcd_vented_body_odd_lowbit_enabled()
+                    && dialog_gcd_odd_u_lowbit_fastpath_enabled()
+                    && bw >= 3
+                {
+                    // Bit-0 result = cx(ctrl, acc[0]); no borrow into bit 1 (acc[0]=ctrl,
+                    // subtrahend[0]=1). Run the vented body over [1..bw].
+                    b.cx(ctrl, acc[0]);
+                    cuccaro_sub_ctrl_vented(b, &subtrahend[1..bw], &acc[1..bw], ctrl, &vents[..bw - 2]);
+                } else {
+                    cuccaro_sub_ctrl_vented(b, &subtrahend[..bw], &acc[..bw], ctrl, &vents[..bw - 1]);
+                }
                 return;
             }
         }
@@ -988,7 +1048,18 @@ pub(crate) fn dialog_gcd_controlled_add_selected(
             if let Some(vents) =
                 borrowed_carries.filter(|c| n >= 2 && c.len() >= n - 1)
             {
-                cuccaro_add_ctrl_vented(b, addend, acc, ctrl, &vents[..n - 1]);
+                let bw = dialog_gcd_vented_body_width(n, step);
+                if dialog_gcd_vented_body_odd_lowbit_enabled()
+                    && dialog_gcd_odd_u_lowbit_fastpath_enabled()
+                    && bw >= 3
+                {
+                    // Reverse-add mirror: acc[0]=0, addend[0]=1 => bit-0 result =
+                    // cx(ctrl, acc[0]), no carry into bit 1. Body over [1..bw].
+                    b.cx(ctrl, acc[0]);
+                    cuccaro_add_ctrl_vented(b, &addend[1..bw], &acc[1..bw], ctrl, &vents[..bw - 2]);
+                } else {
+                    cuccaro_add_ctrl_vented(b, &addend[..bw], &acc[..bw], ctrl, &vents[..bw - 1]);
+                }
                 return;
             }
         }
```

