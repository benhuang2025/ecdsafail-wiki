# 8cdc0e6 — Shorten the endpoint fold carry chain by one (ENDPOINT_FOLD_WINDOW 55 → 54), one fewer carry ancilla at the peak (1321 → 1320)

| | |
| --- | --- |
| Contestant | Akashneelesh |
| Date | 2026-08-21 |
| Submission | `7bb8713` |
| Commit | `8cdc0e6ab8fd101c107be24ae2c4b0a870ebdb1a` |
| Result | 1320 qubits × 951,299 Toffoli = **1,255,714,680** |
| Base | `897dda2` (teddyjfpender's ping-pong introduction): 1321 qubits × 952,707 Toffoli = 1,258,525,947 |
| Change vs base | qubits −1, Toffoli −1,408, score −2,811,267 |
| Leaderboard Δ | −985,645, measured against the frontier at the time, `cae8c82` (1321 × 951,325 = 1,256,700,325), which is **not** this commit's base but is its git parent |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [modular-fold](../concepts/modular-fold.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

At the end of the ping-pong replay, the two coefficient registers are
canonicalised by `conditional_mod_negate`. It subtracts the small constant
`f − 1` (with `p = 2^256 − f`, `f = 2^32 + 977`) under a control, and the
carry chain of that subtraction is cut off a fixed number of positions above
the constant's top bit. All the chain's carry ancillas are live at once, and
this moment is where the qubit peak sits.

This commit cuts the chain one position earlier: `ENDPOINT_FOLD_WINDOW` goes
from 55 to 54. That is one fewer carry ancilla at the peak, so the circuit
needs 1320 qubits instead of 1321. It also saves one Toffoli per call. The
commit keeps the git parent `cae8c82`'s narrower chunk compare (26 → 25),
which supplies most of the Toffoli saving against `897dda2`. Along the way the
five window constants become environment-tunable functions.

## What changed and why it saves qubits

All circuit changes are in `src/point_add/pingpong_div.rs`.

1. **Window constants become tunable functions.** The five `const`s
   `REPLAY_CHUNK`, `REPLAY_CHUNK_COMPARE`, `REPLAY_FOLD_WINDOW`,
   `ENDPOINT_FOLD_WINDOW` and `REPLAY_FLAG_COMPARE` are replaced by
   `replay_chunk()`, `replay_chunk_compare()`, `replay_fold_window()`,
   `endpoint_fold_window()` and `replay_flag_compare()`. Each reads an env
   var `SUB4_PP_<NAME>` once, through `tuned_window(name, slot, default)` and
   a `OnceLock`, and falls back to a default. Every use site is switched to
   the function. The defaults are 96, 25, 56, **54** and 28.
2. **`ENDPOINT_FOLD_WINDOW` 55 → 54** (default of `endpoint_fold_window()`).
   - It is the `window` argument of the constant add/subtract helpers
     `csub_nbit_const_direct_trunc_fast` / `cadd_…` in
     `arith/const_arith.rs`. They are called from `conditional_mod_negate`
     (twice per traversal, after the replay), `mod_halve_pm` and
     `mod_double_pm` (replay rounds 0–1), and the unfused `signed_mod_add_pm`.
   - The helper allocates carries for positions `0..=last`, where
     `last = min(n − 2, highest_set_bit(c) + window)`. For `c = f − 1`,
     `highest_set_bit = 32`, so `last` goes from 87 to 86 and the helper holds
     87 carries instead of 88.
   - The carries are computed with a CCX each and erased with `hmr` plus
     `cz_if` repairs (see [measurement-uncompute](../concepts/measurement-uncompute.md)),
     so one fewer position is one fewer live ancilla and one fewer CCX per
     call.
   - The doc comment on `endpoint_fold_window()` states that this is "exactly
     one fewer carry ancilla at the binding allocation, which is what takes
     peak width 1321 → 1320". The binding allocation is the
     `conditional_mod_negate` after the replay, when the 704-wire tape and
     both coefficient registers are still live. See
     [pingpong-division](../concepts/pingpong-division.md) ("Walk-back and
     endpoint") and [modular-fold](../concepts/modular-fold.md).
3. **`REPLAY_CHUNK_COMPARE` 26 → 25**, inherited from the git parent
   `cae8c82` (default of `replay_chunk_compare()`).
   - In `add_chunked_measured`, a 256-bit add is split into three chunks of
     at most 96 bits (86, 85, 85), so each add has two chunk-boundary carries. Each one is measured out with
     `hmr(carry, phase)`. Then `cmp_lt_phase_conditioned` compares the top
     `k` bits of the chunk's sum and addend, and applies the phase repair
     only if `phase` is 1.
   - One bit less is one Toffoli less per boundary, executed on about half
     the shots.
   - With two traversals of 704 replay rounds and two boundaries per add,
     that is about 1,400 Toffoli. `cae8c82` measured −1,382. See
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
4. **Tail nonce** (`src/point_add/mod.rs`): the default
   `SUB4_PINGPONG_TAIL_NONCE` goes from 82 (the base) to 6273. The git
   parent used 1063.

Against the frontier `cae8c82` the change is −1 qubit and −26 T. That is the
endpoint chain's one CCX per call, plus island noise.

## Why it is still correct, and what it risks

- **The endpoint truncation is approximate, but nearly free.** A dropped
  position matters only when the borrow out of position 86 would really
  propagate, which needs the operand bits 33–86 to all hold one particular
  value. For a random coefficient that is about 2^−54 per call. In practice
  this adds no measurable λ. The concept page calls the endpoint window
  "λ-free down to ~25". A failure would be a wrong output value, so a
  classical mismatch.
- **The chunk compare is probabilistic.** It gives the wrong phase repair
  when the top 25 bits of sum and addend tie. That is about 2^−25 per
  boundary, which shows up as phase garbage on rare inputs.
- The refactor is behaviour-preserving apart from the two defaults.
- The shipped nonce `6273` draws a clean test set: 0 classical, 0 phase and
  0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The qubit saving comes from truncating a fold carry chain by one position,
which is fold/carry truncation. Here it lowers the peak as well as Toffoli.
The inherited chunk-compare change is comparator/width truncation, but it is
`cae8c82`'s lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 897dda2 -- src/point_add`.
   - `git diff --ignore-cr-at-eol 897dda2 8cdc0e6 -- src/point_add` is 84
     changed lines in 2 files.
   - Diffing against the git parent `cae8c82` gives the same size, 84 lines.
     That diff contains only the endpoint change and the refactor, because
     `cae8c82` already has the chunk compare at 25. Either base works. The
     census uses `897dda2`, so this patch also carries `cae8c82`'s
     26 → 25.
2. **Apply the patch below** from the repo root with
   `git apply --ignore-whitespace`. The flag lets the patch apply whether the
   files use LF or CRLF line endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 8cdc0e6 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set, because the new `SUB4_PP_*` variables override
   the defaults. Expect:
   - 1320 qubits
   - 951,299 average Toffoli (rounded)
   - score 1,255,714,680
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `6273` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ff2fede..67faccc 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2531,7 +2531,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(82);
+            .unwrap_or(6273);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index 673cdd3..52b3c1f 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -5,18 +5,54 @@ use super::*;
 /// walk restores the denominator and clears the log.
 const ROUNDS: usize = 704;
 const VALUE_WIDTH: usize = N + 3;
-const REPLAY_CHUNK: usize = 96;
-const REPLAY_CHUNK_COMPARE: usize = 26;
-const REPLAY_FOLD_WINDOW: usize = 56;
-const ENDPOINT_FOLD_WINDOW: usize = 55;
-const REPLAY_FLAG_COMPARE: usize = 28;
+/// Truncation windows for the measured-erasure repairs.  Each one trades
+/// emitted Toffoli against the intrinsic mismatch rate, so they are swept as a
+/// group; the defaults are the shipped values.
+fn tuned_window(name: &str, slot: &'static std::sync::OnceLock<usize>, default: usize) -> usize {
+    *slot.get_or_init(|| {
+        std::env::var(name)
+            .ok()
+            .and_then(|v| v.parse::<usize>().ok())
+            .unwrap_or(default)
+    })
+}
+
+fn replay_chunk() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    tuned_window("SUB4_PP_REPLAY_CHUNK", &SLOT, 96)
+}
+
+fn replay_chunk_compare() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    tuned_window("SUB4_PP_REPLAY_CHUNK_COMPARE", &SLOT, 25)
+}
+
+fn replay_fold_window() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    tuned_window("SUB4_PP_REPLAY_FOLD_WINDOW", &SLOT, 56)
+}
+
+/// 54, not 55: the fold carry chain is `min(n-2, highest_set_bit(c) + window)`
+/// long, so one position off the window is exactly one fewer carry ancilla at
+/// the binding allocation, which is what takes peak width 1321 -> 1320.  The
+/// dropped position only matters when a carry would have propagated that far,
+/// which the tail nonce absorbs.
+fn endpoint_fold_window() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    tuned_window("SUB4_PP_ENDPOINT_FOLD_WINDOW", &SLOT, 54)
+}
+
+fn replay_flag_compare() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    tuned_window("SUB4_PP_REPLAY_FLAG_COMPARE", &SLOT, 28)
+}
 
 /// Translate the source model's `lsbs = 56` literally: its pseudo-Mersenne
 /// corrections operate on `acc[..lsbs]`, whereas the target helper's `window`
 /// argument means that many positions *after* the constant's top bit.
 fn replay_fold_target(target: &[QubitId]) -> &[QubitId] {
     if std::env::var_os("SUB4_PINGPONG_LOW56_FOLD").is_some() {
-        &target[..REPLAY_FOLD_WINDOW]
+        &target[..replay_fold_window()]
     } else {
         target
     }
@@ -361,7 +397,7 @@ fn fused_lift_round0_reverse_sparse(b: &mut B, v: &[QubitId], a0: QubitId) {
     for &q in &v[..N] {
         b.cx(not_a1, q);
     }
-    cadd_per_position_controls_trunc(b, &v[..N], &controls, REPLAY_FOLD_WINDOW - 2);
+    cadd_per_position_controls_trunc(b, &v[..N], &controls, replay_fold_window() - 2);
     for &q in &v[..N] {
         b.cx(not_a1, q);
     }
@@ -573,7 +609,7 @@ fn conditional_mod_negate(b: &mut B, control: QubitId, value: &[QubitId]) {
         replay_fold_target(value),
         f.wrapping_sub(U256::from(1)),
         control,
-        ENDPOINT_FOLD_WINDOW,
+        endpoint_fold_window(),
     );
 }
 
@@ -695,7 +731,7 @@ fn add_chunked_measured(
     acc: &[QubitId],
     carry_out: Option<QubitId>,
 ) {
-    let bounds = chunk_bounds(addend.len(), REPLAY_CHUNK);
+    let bounds = chunk_bounds(addend.len(), replay_chunk());
     let mut live_boundaries = Vec::<(QubitId, usize, usize)>::new();
     let mut carry_in = None;
     for (index, &(lo, hi)) in bounds.iter().enumerate() {
@@ -715,7 +751,7 @@ fn add_chunked_measured(
     for index in (0..live_boundaries.len()).rev() {
         let (carry, lo, hi) = live_boundaries[index];
         let width = hi - lo;
-        let compare = REPLAY_CHUNK_COMPARE.min(width);
+        let compare = replay_chunk_compare().min(width);
         let phase = b.alloc_bit();
         b.hmr(carry, phase);
         cmp_lt_phase_conditioned(b, &acc[hi - compare..hi], &addend[hi - compare..hi], phase);
@@ -883,10 +919,10 @@ fn signed_mod_add_pm_halve_fused(b: &mut B, sign: QubitId, source: &[QubitId], t
     b.cx(sign, plus_f);
     b.cx(parity, plus_f);
 
-    let negative_f = twos_complement_bits(f, REPLAY_FOLD_WINDOW);
+    let negative_f = twos_complement_bits(f, replay_fold_window());
     fused_fold_maskfree(
         b,
-        &target[..REPLAY_FOLD_WINDOW],
+        &target[..replay_fold_window()],
         f,
         &negative_f,
         plus_f,
@@ -916,8 +952,8 @@ fn signed_mod_add_pm_halve_fused(b: &mut B, sign: QubitId, source: &[QubitId], t
     b.hmr(overflow, phase);
     cmp_lt_phase_conditioned(
         b,
-        &target[N - REPLAY_FLAG_COMPARE..],
-        &source[N - REPLAY_FLAG_COMPARE..],
+        &target[N - replay_flag_compare()..],
+        &source[N - replay_flag_compare()..],
         phase,
     );
     b.free(overflow);
@@ -982,10 +1018,10 @@ fn signed_mod_double_add_pm_fused(
     b.cx(doubled_out, odd_correction);
     b.cx(add_out, odd_correction);
     let first_carry = and_clean(b, target[0], odd_correction);
-    let negative_f = twos_complement_bits(f, REPLAY_FOLD_WINDOW);
+    let negative_f = twos_complement_bits(f, replay_fold_window());
     fused_fold_maskfree(
         b,
-        &target[..REPLAY_FOLD_WINDOW],
+        &target[..replay_fold_window()],
         f,
         &negative_f,
         plus_f,
@@ -1026,8 +1062,8 @@ fn signed_mod_double_add_pm_fused(
     b.hmr(add_out, phase);
     cmp_lt_phase_conditioned(
         b,
-        &target[N - REPLAY_FLAG_COMPARE..],
-        &source[N - REPLAY_FLAG_COMPARE..],
+        &target[N - replay_flag_compare()..],
+        &source[N - replay_flag_compare()..],
         phase,
     );
     b.free(add_out);
@@ -1050,14 +1086,14 @@ fn signed_mod_add_pm(b: &mut B, sign: QubitId, source: &[QubitId], target: &[Qub
         replay_fold_target(target),
         f,
         overflow,
-        ENDPOINT_FOLD_WINDOW,
+        endpoint_fold_window(),
     );
     let phase = b.alloc_bit();
     b.hmr(overflow, phase);
     cmp_lt_phase_conditioned(
         b,
-        &target[N - REPLAY_FLAG_COMPARE..],
-        &source[N - REPLAY_FLAG_COMPARE..],
+        &target[N - replay_flag_compare()..],
+        &source[N - replay_flag_compare()..],
         phase,
     );
     b.free(overflow);
@@ -1077,7 +1113,7 @@ fn mod_halve_pm(b: &mut B, target: &[QubitId]) {
         replay_fold_target(target),
         f,
         parity,
-        ENDPOINT_FOLD_WINDOW,
+        endpoint_fold_window(),
     );
     for i in 0..N - 1 {
         b.swap(target[i], target[i + 1]);
@@ -1101,7 +1137,7 @@ fn mod_double_pm(b: &mut B, target: &[QubitId]) {
         replay_fold_target(target),
         f,
         overflow,
-        ENDPOINT_FOLD_WINDOW,
+        endpoint_fold_window(),
     );
     b.cx(target[0], overflow);
     b.free(overflow);
```

