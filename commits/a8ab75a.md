# a8ab75a — Lower the replay and square ladder budgets by one (1274 → 1273 qubits), paid for with a 21-bit flag compare

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-08-22 |
| Submission | `903ced6` |
| Commit | `a8ab75ac10c23eb7cd68997f481e3412204953d1` |
| Result | 1273 qubits × 942,381 Toffoli = **1,199,651,013** |
| Base | `8d3517a` (git parent, the author's previous submission): 1274 qubits × 941,683 Toffoli = 1,199,704,142 |
| Change vs base | qubits −1, Toffoli +698, score −53,129 (leaderboard Δ −53,129) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

On this tree, two phases reach the qubit peak: the ping-pong replay and the
product-register square. Both size their chunked carry ladders against a
budget: `SUB4_PP_PEAK` for the replay (and the interleaved walk) and
`SQUARE_LADDER` for the square. This commit lowers both by one wire and
re-picks the interleave checkpoints, so the peak drops from 1274 to 1273.
Narrower ladders need more chunk boundaries, and each boundary costs a
measured erase plus a phase-repair compare.

To pay for that, the commit narrows the replay overflow-flag compare from 24
to 21 bits, which saves about 2,000 Toffoli. It also spends some Toffoli to
buy back λ: one multiply round comes back, and the endpoint fold window goes
from 20 back to 28. Net: one qubit for +698 Toffoli. One qubit is worth about
740 Toffoli here, so the trade wins by a small margin, 53,129 points.

## What changed and why it saves a qubit

All in `src/point_add/pingpong_div.rs` unless noted.

1. **Peak budgets (the qubit).**
   - `plan()`: `SUB4_PP_PEAK` 1274 → 1273, `SUB4_PP_R1` 286 → 283,
     `SUB4_PP_R2` 603 → 589.
     - The peak is the budget behind `allowance(plan, tape_len, walk_width) = peak − tape_len − 2·N − 2·walk_width`,
       which sizes every replay cell's chunk ladder.
     - It also sets the width of the exact split in the interleaved walk adds
       (`walk_low_chunk`).
     - `r1` and `r2` choose which rounds are batch-replayed and which are
       interleaved. They are re-picked for the new cap.
   - `SQUARE_LADDER` 244 → 243 in
     `src/point_add/trailmix_ludicrous/square/product_register.rs`. This is
     the live-ladder budget of the square's wide (≥ 200-bit) chunked adds.
     The square co-binds the peak, so it has to come down in the same commit.
     See [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
   - Cost: more and narrower chunks. Each extra chunk boundary in the replay
     is a measured carry erase with a 23-bit conditioned compare, about 11.5
     executed Toffoli (the author's earlier profile in
     `memory/09-pingpong-interleaved.md`).
2. **`replay_flag_compare()`: 24 → 21** (`SUB4_PP_REPLAY_FLAG_COMPARE`). This
   is the Toffoli payment.
   - Each fused replay cell measures its overflow flag out with
     `hmr(overflow, phase)` and repairs the phase with
     `cmp_lt_phase_conditioned(&target[N−k..], &source[N−k..], phase)`, which
     runs only when `phase` = 1.
   - Three fewer bits on about 1,390 cells (divide rounds 2..699, multiply
     rounds 2..693) is roughly 1,390 × 3 × 0.5 ≈ 2,100 executed Toffoli. See
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
3. **λ buy-backs, which cost Toffoli.**
   - `rounds_for(Multiply)`: `rounds() − 7` → `rounds() − 6`
     (`SUB4_PP_ROUNDS_MUL`, `rounds()` = 700). The multiply walk goes from
     693 to 694 rounds, which costs one round of walk, walk-back and replay
     cell, a few hundred Toffoli, and lowers the convergence-tail failure
     rate.
   - `endpoint_fold_window()`: 20 → 28 (`SUB4_PP_ENDPOINT_FOLD_WINDOW`). This
     undoes [`d1bb787`](d1bb787.md)'s cut on this line. It adds 8 carry
     positions to each of the 8 endpoint folds (`conditional_mod_negate`,
     `mod_halve_pm`, `mod_double_pm`), about +80 Toffoli. The author's notes
     (`memory/09-pingpong-interleaved.md`) call this window "λ-free down to
     ~25", so 20 was spending λ. See [modular-fold](../concepts/modular-fold.md).
4. **Tail nonce** (`SUB4_PINGPONG_TAIL_NONCE` default in `build()`,
   `src/point_add/mod.rs`): 25125857 → 26010236.

These four pieces are not measured separately. Taking the flag cut at about
−2,100 and the two buy-backs at about +450, the narrower ladders cost about
+2,300 Toffoli; this split is an estimate.

## Why it is still correct, and what it risks

- **Budget changes are layout changes.** The adds stay exact in value. Extra
  replay boundaries add approximate 23-bit phase repairs, so λ rises a
  little; the walk split and the square's leading-chunk repairs are exact.
- **Flag compare 21 bits.** This is wrong on a 21-bit tie, about 2^−21 per
  cell, eight times the old rate. It shows up as a **phase** failure.
- **The buy-backs lower λ.** One more multiply round shrinks the
  convergence tail, which is a **classical** channel. The wider endpoint fold
  removes rare carry escapes, also classical.
- The shipped nonce `26010236` draws a clean set: 0 classical, 0 phase and
  0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The score gain is the peak qubit, bought by lowering the ladder budgets of
both peak owners at once (a co-binder cut). That is the budget-retune form of
ancilla-lifetime / venting. The flag-compare narrowing is a secondary
comparator truncation that pays for it.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 8d3517a -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 8d3517a a8ab75a -- src/point_add` is
   16 lines in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol a8ab75a -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1273 qubits
   - 942,381 average Toffoli (rounded)
   - score 1,199,651,013
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `26010236` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 5d50b11..bc47f47 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2539,7 +2539,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(25125857);
+            .unwrap_or(26010236);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index 5fb376a..b982caa 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -20,7 +20,7 @@ fn rounds_for(direction: PingPongDirection) -> usize {
             // tape puts both replay peaks at the same width.  Convergence
             // exposure of one round on one traversal is ~+0.05 lambda.
             static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
-            tuned_window("SUB4_PP_ROUNDS_MUL", &SLOT, rounds() - 7)
+            tuned_window("SUB4_PP_ROUNDS_MUL", &SLOT, rounds() - 6)
         }
     }
 }
@@ -80,12 +80,12 @@ fn replay_fold_window() -> usize {
 /// which the tail nonce absorbs.
 fn endpoint_fold_window() -> usize {
     static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
-    tuned_window("SUB4_PP_ENDPOINT_FOLD_WINDOW", &SLOT, 20)
+    tuned_window("SUB4_PP_ENDPOINT_FOLD_WINDOW", &SLOT, 28)
 }
 
 fn replay_flag_compare() -> usize {
     static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
-    tuned_window("SUB4_PP_REPLAY_FLAG_COMPARE", &SLOT, 24)
+    tuned_window("SUB4_PP_REPLAY_FLAG_COMPARE", &SLOT, 21)
 }
 
 /// Translate the source model's `lsbs = 56` literally: its pseudo-Mersenne
@@ -1151,9 +1151,9 @@ fn plan(rounds: usize) -> Option<Plan> {
     // measured-erasure exposure (lambda) goes down as well.
     // `SUB4_PP_R1=509 SUB4_PP_R2=610` restores the previous op stream byte for
     // byte: at r1=509 no walk round is ever over budget, so nothing splits.
-    let r1 = env("SUB4_PP_R1", 286).min(rounds);
-    let r2 = env("SUB4_PP_R2", 603).min(rounds.saturating_sub(1));
-    let peak = env("SUB4_PP_PEAK", 1274);
+    let r1 = env("SUB4_PP_R1", 283).min(rounds);
+    let r2 = env("SUB4_PP_R2", 589).min(rounds.saturating_sub(1));
+    let peak = env("SUB4_PP_PEAK", 1273);
     Some(Plan { r1, r2, peak })
 }
 
diff --git a/src/point_add/trailmix_ludicrous/square/product_register.rs b/src/point_add/trailmix_ludicrous/square/product_register.rs
index eae6485..97e960e 100644
--- a/src/point_add/trailmix_ludicrous/square/product_register.rs
+++ b/src/point_add/trailmix_ludicrous/square/product_register.rs
@@ -25,7 +25,7 @@ const F_NAF: [(usize, bool); 5] = [
 /// 257-carry ladder of `tri_corr` was the square's peak owner (1287 qubits).
 const SQUARE_CHUNK_MIN: usize = 200;
 /// Live carry-ladder budget for those wide adds.
-const SQUARE_LADDER: usize = 244;
+const SQUARE_LADDER: usize = 243;
 fn add_full(circ: &mut B, addend: &[QubitId], acc: &[QubitId]) {
     assert_eq!(addend.len(), acc.len());
     let chunk_min = std::env::var("SUB4_SQUARE_CHUNK_MIN")
```

