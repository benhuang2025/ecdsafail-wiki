# 4eb93cb — Cut the divide walk from 698 to 696 rounds, switch off the sparse width repair, and lower both peak budgets by one (1274 → 1273 qubits)

| | |
| --- | --- |
| Contestant | gnuchev |
| Date | 2026-08-23 |
| Submission | `b58384f` |
| Commit | `4eb93cb33bbf6a93229fe166b8d511c5e52ee253` |
| Result | 1273 qubits × 914,243 Toffoli = **1,163,831,339** |
| Base | `2c79d2f` (git parent and frontier at the time, odinfree): 1274 qubits × 916,526 Toffoli = 1,167,654,124. This is **not** the `b523ecf` listed in `data/bases.tsv`; see Reproduce. |
| Change vs base | qubits −1, Toffoli −2,283, score −3,822,785 (leaderboard Δ −3,822,785) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: three dead backup files are copied from the commit; the patch covers the rest |

## Summary

The commit changes four constants on odinfree's tree `2c79d2f`, plus the tail
nonce. Two of them save Toffoli. The divide traversal of the ping-pong walk
runs 696 rounds instead of 698, and the sparse "+1 bit" width repair that
`2c79d2f` had just added is switched off. Both make the walk and replay
cheaper, and both raise Lambda, the expected number of failing test shots.
The other two lower the ping-pong peak budget and the square's carry-ladder
budget by one each, so the circuit fits in 1273 qubits instead of 1274.

Net: one qubit and 2,283 average Toffoli fewer. The rest of the 10,234-line
diff against the parent is three backup files that `2c79d2f` had deleted and
this tree still carries. They are not compiled.

## What changed and why it saves Toffoli and a qubit

All circuit changes are in `src/point_add/pingpong_div.rs` and
`src/point_add/trailmix_ludicrous/square/product_register.rs`.

1. **Divide depth `SUB4_PP_ROUNDS`: 698 → 696** in `rounds()`.
   - `rounds()` is the depth of the **divide** traversal only. The multiply
     traversal has its own pin, `SUB4_PP_ROUNDS_MUL`, which is already 696 in
     the base and does not change. (The old note said both traversals lose
     rounds. That is wrong.)
   - Each cut round removes one walk add, one walk-back add and one replay
     cell from the divide traversal, and one tape qubit from the divide
     replay.
   - `rounds()` also feeds `width_round_index(round) = round·703/(rounds()−1)`,
     which maps a round onto the 700-entry `WIDTH_SCHEDULE`. With 696 instead
     of 698, every round reads a slightly later table entry, which is equal or
     narrower. This applies to **both** traversals, because `value_width()`
     does not know the direction. Narrower walk registers make every walk add
     and walk-back add a little cheaper.
   - Risk: a slow-converging input needs more rounds than the depth allows,
     and a value can outgrow its narrower register. Both raise Lambda. The
     in-code estimate is about +0.05 Lambda per round per traversal. See
     [pingpong-division](../concepts/pingpong-division.md).
2. **Sparse width repair off**: `width_repair()` returns 0 for every index.
   - The base's `WIDTH_REPAIR` is a sorted list of 100 sampled schedule
     indices. At each one, `value_width()` adds one bit to the table width.
     `2c79d2f`'s comment prices the set at "−0.95 lambda for +519 diagnostic
     Toffoli".
   - This commit keeps the table but writes `if false && r <= u16::MAX ...`,
     so the 100 rounds go back to the plain compressed width. That takes back
     about the 519 Toffoli and gives back the 0.95 Lambda. It is a width
     truncation. See
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
3. **Ping-pong peak budget `SUB4_PP_PEAK`: 1274 → 1273** in `plan()`.
   - `peak` is not a measured peak. It is the budget that the interleaved
     replay's chunked adds are sized against:
     `allowance = peak − (tape + 2N + 2·walk_width)` is the room left for the
     carry ladder. One less means each budgeted add gets one fewer ladder
     wire.
   - This can force an extra chunk, and so an extra measured boundary repair,
     in some rounds. That costs a few Toffoli, but the two cut divide rounds
     also shorten the divide tape, which gives the replay some room back.
4. **Square ladder `SQUARE_LADDER`: 244 → 243** in `product_register.rs`.
   - This is the live carry-ladder budget for the square's wide chunked adds
     (`add_chunked_measured_budgeted`).
   - The square and the replay are co-binders of the peak. Lowering only one
     of them would leave Q at 1274, so both drop together. See
     [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
5. **Tail nonce** (`SUB4_PINGPONG_TAIL_NONCE` default in `build()`,
   `src/point_add/mod.rs`): 100000045835813 → 65700024945645.

Items 1 and 2 provide the Toffoli saving. Items 3 and 4 provide the qubit. The
commit has no notes of its own that split the 2,283 Toffoli between them.

## Why it is still correct, and what it risks

- Nothing here is a new construction. All four knobs move existing
  approximations in the direction of fewer gates:
  - **Depth.** An input whose walk has not reached (±1, ±1) after 696 rounds
    gives a wrong quotient and dirty registers. That shows up as a classical
    and ancilla failure.
  - **Width.** A value whose top bit is not a sign copy when the register is
    trimmed leaves garbage, also a classical or ancilla failure.
  - **Peak budgets.** These are exact. They only change chunk layouts. More
    chunks mean more truncated boundary repairs, and a wrong repair is a
    phase failure.
- All three effects raise Lambda. The shipped nonce draws a test set with no
  failing input: 9,024 of 9,024 shots, with 0 classical, 0 phase and 0 ancilla
  failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- The three backup files (`mod.rs.pre_live`, `pingpong_div.rs.pre_ts`,
  `pingpong_div.rs.rrm`) are not Rust modules, so they do not affect the
  build.

## Classification rationale

The main Toffoli lever is cutting the iteration count of the divide walk, and
the repair switch-off is a threshold on the same walk. That makes it
iteration/threshold tuning. The runner-up was comparator/width truncation,
because the repair switch-off and the knock-on narrowing from
`width_round_index` both narrow widths. The two budget changes are peak
bookkeeping that go with the round cut.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 2c79d2f -- src/point_add`.
   - The base is the git parent `2c79d2f`, not the `b523ecf` in
     `data/bases.tsv`. `b523ecf` is mochimodev's tree. Against it the diff is
     only 560 lines, because both trees carry the same backup files. But those
     560 lines are mostly odinfree's `2c79d2f` work: the 700-entry
     `WIDTH_SCHEDULE` with rescaling on by default, the `WIDTH_REPAIR` table,
     depth 700 → 698, `ROUNDS_MUL` → 696, the fold and flag windows, a
     181-line `const_arith.rs` addition and memory note 11. A note built on
     `b523ecf` would credit all of that to gnuchev.
   - Against `2c79d2f`, `git diff --ignore-cr-at-eol 2c79d2f 4eb93cb -- src/point_add`
     is 10,234 lines in 6 files. 10,224 of them are the three backup files
     coming back. The real change is 10 lines in 3 files.
2. **Copy the three backup files from the commit:**
   `git checkout 4eb93cb -- src/point_add/mod.rs.pre_live src/point_add/pingpong_div.rs.pre_ts src/point_add/pingpong_div.rs.rrm`.
   They are old copies of `mod.rs` (5,561 lines) and `pingpong_div.rs`
   (2,337 and 2,326 lines) from earlier ping-pong trees. `2c79d2f` had
   deleted them. They are not compiled.
3. **Apply the patch below** from the repo root with
   `git apply --ignore-whitespace`. The flag lets the patch apply whether the
   files use LF or CRLF line endings. It covers the three edited source files.
4. **Check the tree.** `git diff --ignore-cr-at-eol 4eb93cb -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1273 qubits
   - 914,243 average Toffoli (rounded)
   - score 1,163,831,339
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `65700024945645` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ff81088..8e89661 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2545,7 +2545,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(100000045835813);
+            .unwrap_or(65700024945645);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index 6f9b4b2..7dc3830 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -31,7 +31,7 @@ fn rounds() -> usize {
     // this draw (validated 9,024/9,024 with the baked tail nonce), the tape gives
     // back four sign qubits against two wider terminal wires (peak 1320 -> 1318),
     // and each cut round saves its replay and walk adds on both traversals.
-    tuned_window("SUB4_PP_ROUNDS", &SLOT, 698)
+    tuned_window("SUB4_PP_ROUNDS", &SLOT, 696)
 }
 
 /// The width schedule is compressed so it still reaches its floor on the
@@ -489,7 +489,7 @@ fn width_repair(r: usize) -> i32 {
     if std::env::var("SUB4_PP_WIDTH_RESCALE").is_ok_and(|v| v == "0") {
         return 0;
     }
-    if r <= u16::MAX as usize && WIDTH_REPAIR.binary_search(&(r as u16)).is_ok() {
+    if false && r <= u16::MAX as usize && WIDTH_REPAIR.binary_search(&(r as u16)).is_ok() {
         1
     } else {
         0
@@ -1260,7 +1260,7 @@ fn plan(rounds: usize) -> Option<Plan> {
     // layouts by a few rounds in both directions.
     let r1 = env("SUB4_PP_R1", 340).min(rounds);
     let r2 = env("SUB4_PP_R2", 628).min(rounds.saturating_sub(1));
-    let peak = env("SUB4_PP_PEAK", 1274);
+    let peak = env("SUB4_PP_PEAK", 1273);
     Some(Plan { r1, r2, peak })
 }
 
diff --git a/src/point_add/trailmix_ludicrous/square/product_register.rs b/src/point_add/trailmix_ludicrous/square/product_register.rs
index 1212325..d354089 100644
--- a/src/point_add/trailmix_ludicrous/square/product_register.rs
+++ b/src/point_add/trailmix_ludicrous/square/product_register.rs
@@ -25,7 +25,7 @@ const F_NAF: [(usize, bool); 5] = [
 /// 257-carry ladder of `tri_corr` was the square's peak owner (1287 qubits).
 const SQUARE_CHUNK_MIN: usize = 200;
 /// Live carry-ladder budget for those wide adds; co-balanced with replay peak.
-const SQUARE_LADDER: usize = 244;
+const SQUARE_LADDER: usize = 243;
 fn add_full(circ: &mut B, addend: &[QubitId], acc: &[QubitId]) {
     assert_eq!(addend.len(), acc.len());
     let chunk_min = std::env::var("SUB4_SQUARE_CHUNK_MIN")
```

