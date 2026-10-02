# b523ecf — Start the steep part of the linear width schedule at round 30 instead of 40 (walk about 3 bits narrower from round 300 on)

| | |
| --- | --- |
| Contestant | mochimodev |
| Date | 2026-08-23 |
| Submission | `f827b9c` |
| Commit | `b523ecff127171013575bbcc3823e01996a79a34` |
| Result | 1278 qubits × 914,790 Toffoli = **1,169,101,620** |
| Base | `70d64f5` (odinfree; the git parent is `bdf4845`): 1278 qubits × 924,651 Toffoli = 1,181,703,978 |
| Change vs base | qubits ±0, Toffoli −9,861, score −12,602,358 |
| Leaderboard Δ | −1,478,646, measured against the frontier at the time, `bdf4845` (1278 × 915,947 = 1,170,580,266), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [pingpong-division](../concepts/pingpong-division.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: three uncompiled backup files are copied from the commit; the patch covers the rest |

## Summary

This tree still uses the original piecewise-linear width schedule for the
ping-pong walk registers, not the fitted tables of [`b5796ce`](b5796ce.md) and
[`bdf4845`](bdf4845.md). The schedule shrinks the registers slowly
(0.17 bit per round) up to `BREAK_1`, then faster (0.34 bit per round) up to
`BREAK_2 = 304`, then faster still (0.40).

This commit changes one constant, `BREAK_1`, from 40 to 30, so the faster
slope starts ten rounds earlier. The registers end up 3 bits narrower from
round 304 until they reach the 8-bit floor, and 1 to 3 bits narrower in
between. Over both traversals that is 3,621 fewer bit-rounds. Every walk and
walk-back add in those rounds gets cheaper, which saves 9,861 average Toffoli
at the same 1278 qubits. Some slow-shrinking inputs now overflow, so λ goes
up and a new nonce was hunted.

The rest of the diff is default-off hooks and three uncompiled backup files.

## What changed and why it saves Toffoli

1. **`BREAK_1` 40 → 30** in `value_width(round)`, `src/point_add/pingpong_div.rs`.
   - The schedule (with `start = 256 + MARGIN = 260`, `SLOPE_1 = 17`,
     `SLOPE_2 = 34`, `SLOPE_3 = 40`, `BREAK_2 = 304`, clamped to `[8, 259]`):
     ```
     round < BREAK_1:          start − 17·round/100
     BREAK_1 ≤ round < 304:    at_first − 34·(round − BREAK_1)/100,   at_first = start − 17·BREAK_1/100
     round ≥ 304:              at_second − 40·(round − 304)/100
     ```
   - Moving `BREAK_1` down makes the steep slope start earlier, so the
     schedule gets **tighter**. `at_first` goes from 254 (at round 40) to 255
     (at round 30). At round 304 the width is 162 instead of 165, and that
     3-bit gap holds until both reach the floor of 8 bits near the end.
   - Sampled widths, old → new: round 40: 254 → 252; round 304: 165 → 162;
     round 500: 87 → 84; round 699: 8 → 8.
   - `width_round_index` is the identity here (rescale off). The divide runs
     `SUB4_PP_ROUNDS = 700` rounds and the multiply `rounds() − 4 = 696`, as
     in the base. Summed over the rounds run, bit-rounds go from 199,717 to
     196,096 (−3,621).
   - The walk's signed add and its walk-back mirror are each about one
     Toffoli per bit of width. Narrower registers also leave more room for
     the interleaved replay ladders under the peak budget. See
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md),
     section "Width schedules".
2. **Default-off hooks** (no effect on the shipped stream):
   - `PP_TAIL_SHARE=K`: alias every tape sign above round `K` to one wire,
     based on the comment's observation that the sign is constant after
     convergence. Default 0 means off, and the matching early return in
     `walk_back_round` is inactive.
   - `W5_WALK_SPLIT_COMPARE`: truncate the split walk adder's boundary
     compare. The default `usize::MAX` keeps the full `low`-bit compare.
   - `W5_LADDER_FLOOR`: a minimum replay ladder budget. Unset means
     unchanged.
   - `PP_LIVESET` and `PP_IDMAP`: diagnostic dumps of the live set at the
     peak, and of the register id map.
3. **Tail nonce** in `src/point_add/mod.rs`: 5101174221 → 81327465284.
4. **Three new uncompiled backup files.** None is in the module tree.
   - `mod.rs.pre_live` (5,561 lines): an exact copy of the base's `mod.rs`.
   - `pingpong_div.rs.rrm` (2,326 lines) and `pingpong_div.rs.pre_ts` (2,337
     lines): working snapshots of the base's `pingpong_div.rs`, differing
     from it by 6 and 27 lines.
   - They stay in later trees until REgonLevy's [`edeed3f`](edeed3f.md)
     deletes them.

## Why it is still correct, and what it risks

- **Probabilistic.** Trimming a walk register's top wire is valid only if the
  value has already shrunk enough that the top bit is a copy of the sign.
  With the schedule 3 bits tighter over most of the walk, more slow inputs
  violate that. The trimmed bit then holds data, and the walk-back leaves
  garbage. That is a classical failure, usually with phase and ancilla
  garbage too.
- The cost is λ, not correctness on the validated draw. The shipped nonce
  `81327465284` draws a clean set: 0 classical, 0 phase and 0 ancilla
  failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- The hooks are inactive at their defaults. `PP_TAIL_SHARE` in particular
  would be wrong for any input that converges after round `K`.

## Classification rationale

The only active circuit change narrows the walk registers' per-round widths.
That is width truncation priced in λ.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 70d64f5 -- src/point_add`.
   - Do not start from the git parent `bdf4845`. That is odinfree's
     fitted-table tree, and this commit was not built on it.
   - Against the parent, the diff is 10,534 lines. It removes bdf4845's
     `GREEDY_M1000_WIDTH_SCHEDULE` and b5796ce's `WIDTH_SCHEDULE` table, and
     restores the linear schedule. It also moves the divide depth 698 → 700,
     the multiply depth to `rounds() − 4`, and several compare and fold
     windows. Those all just reflect the older 70d64f5 tree.
   - Against `70d64f5`, `git diff --ignore-cr-at-eol 70d64f5 b523ecf -- src/point_add`
     is 10,276 lines in 5 files, of which 10,224 are the three new backup
     files.
2. **Copy the three backup files from the commit:**
   `git checkout b523ecf -- src/point_add/mod.rs.pre_live src/point_add/pingpong_div.rs.pre_ts src/point_add/pingpong_div.rs.rrm`.
   They are uncompiled snapshots, too large to inline.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It covers `mod.rs` and `pingpong_div.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol b523ecf -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`,
   `PP_*` or `W5_*` environment variables set. Expect:
   - 1278 qubits
   - 914,790 average Toffoli (rounded)
   - score 1,169,101,620
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `81327465284` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 2e4998a..8269989 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -451,6 +451,15 @@ impl B {
         if self.active_qubits > self.peak_qubits {
             self.peak_qubits = self.active_qubits;
             self.peak_ops_idx = self.current_ops_len();
+            if std::env::var_os("PP_LIVESET").is_some() {
+                use std::io::Write;
+                let mut freed: Vec<u32> = self.free_qubits.clone();
+                freed.sort_unstable();
+                if let Ok(mut f) = std::fs::File::create("liveset.txt") {
+                    writeln!(f, "peak_active={} next_qubit={} ops_idx={} phase={}", self.active_qubits, self.next_qubit, self.current_ops_len(), self.phase).ok();
+                    writeln!(f, "free_ids={:?}", freed).ok();
+                }
+            }
             self.peak_phase = self.phase;
             if std::env::var("TRACE_EACH_PEAK").is_ok() {
                 eprintln!(
@@ -2539,7 +2548,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(5101174221);
+            .unwrap_or(81327465284);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index 404fe92..fcf4d78 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -259,6 +259,12 @@ pub(crate) fn pingpong_mod_mul_div_in_place(
                 shrink_to(b, &mut u, &mut v, value_width(plan.r1));
             }
             coefficient = b.alloc_qubits(N);
+            if std::env::var_os("PP_IDMAP").is_some() {
+                eprintln!("PP_IDMAP u=[{}..{}] len={} v=[{}..{}] len={} coeff=[{}..{}] num=[{}..{}] tape_len={} tape0={} tapeN={}",
+                    u[0].0, u[u.len()-1].0, u.len(), v[0].0, v[v.len()-1].0, v.len(),
+                    coefficient[0].0, coefficient[N-1].0, numerator[0].0, numerator[N-1].0,
+                    tape.len(), tape[0].0, tape[tape.len()-1].0);
+            }
             set_walk_peak(plan.peak);
             set_chunks(pick_chunks(&plan, plan.r1.min(rounds), u.len()));
             for r in 0..plan.r1.min(rounds) {
@@ -411,7 +417,7 @@ fn restore_wire_layout(
 }
 
 fn value_width(round: usize) -> usize {
-    const BREAK_1: usize = 40;
+    const BREAK_1: usize = 30;
     const BREAK_2: usize = 304;
     const SLOPE_1: usize = 17;
     const SLOPE_2: usize = 34;
@@ -762,7 +768,8 @@ fn signed_add_wrapping_sigma_split(
     // carry itself.
     let phase = b.alloc_bit();
     b.hmr(boundary, phase);
-    cmp_lt_phase_conditioned(b, &target[..low], &source[..low], phase);
+    let w5w = std::env::var("W5_WALK_SPLIT_COMPARE").ok().and_then(|v| v.parse::<usize>().ok()).unwrap_or(usize::MAX).min(low);
+    cmp_lt_phase_conditioned(b, &target[low - w5w..low], &source[low - w5w..low], phase);
     b.free(boundary);
 
     for &q in target {
@@ -1009,7 +1016,8 @@ fn chunks_for_allowance(allowance: usize, extra: usize) -> Option<usize> {
 
 /// Live-ladder budget left for the chunked adder at an interleaved round.
 fn ladder_for_allowance(allowance: usize, extra: usize) -> usize {
-    allowance.saturating_sub(extra)
+    let a = allowance.saturating_sub(extra);
+    match std::env::var("W5_LADDER_FLOOR").ok().and_then(|v| v.parse::<usize>().ok()) { Some(f) => a.max(f), None => a }
 }
 
 fn shrink_to(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, width: usize) {
@@ -1082,6 +1090,10 @@ fn walk_back_round(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, round:
         None => signed_add_wrapping(b, sign, source, target, false),
     }
     b.x(sign);
+    if tail_share_active() && round > tail_share_k() {
+        // aliased tail wire: owned by round tail_share_k(), do not touch it here
+        return;
+    }
     b.cx(target[1], sign);
     b.cx(source[1], sign);
     b.free(sign);
@@ -1164,6 +1176,17 @@ fn allowance(plan: &Plan, tape_len: usize, walk_width: usize) -> usize {
     plan.peak.saturating_sub(tape_len + 2 * N + 2 * walk_width)
 }
 
+/// Tail-share: post-convergence the sign is provably CONSTANT (measured 19,986/19,986),
+/// so every round at or above K can alias ONE wire instead of owning its own.
+/// Frees (rounds-1-K) tape qubits. Breaks only for inputs converging after K.
+fn tail_share_k() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    *SLOT.get_or_init(|| {
+        std::env::var("PP_TAIL_SHARE").ok().and_then(|v| v.parse::<usize>().ok()).unwrap_or(0)
+    })
+}
+fn tail_share_active() -> bool { tail_share_k() > 0 }
+
 fn value_walk(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, rounds: usize) -> Vec<QubitId> {
     let mut tape = Vec::with_capacity(rounds);
     for round in 0..rounds {
@@ -1186,9 +1209,15 @@ fn value_walk(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, rounds: usi
         } else {
             (&v[..width], &u[..width])
         };
-        let sign = b.alloc_qubit();
-        b.cx(target[1], sign);
-        b.cx(source[1], sign);
+        let k = tail_share_k();
+        let sign = if tail_share_active() && round > k && !tape.is_empty() {
+            tape[k]
+        } else {
+            let s = b.alloc_qubit();
+            b.cx(target[1], s);
+            b.cx(source[1], s);
+            s
+        };
         signed_add_wrapping(b, sign, source, target, true);
         tape.push(sign);
 
```

