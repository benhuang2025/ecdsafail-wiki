# 79e7afa — Raise the replay ladder budget to 1268 (realised peak stays 1266) and move the multiply batch split to round 326

| | |
| --- | --- |
| Contestant | odinfree (co-author tag: welttowelt) |
| Date | 2026-08-26 |
| Submission | `7cb6659` |
| Commit | `79e7afa98d21f77b1edb4f32a57a81ad398604ca` |
| Result | 1266 qubits × 906,124 Toffoli = **1,147,152,984** |
| Base | `cc409de` (git parent, the author's previous submission): 1266 qubits × 906,709 Toffoli = 1,147,893,594 |
| Change vs base | qubits ±0, Toffoli −585, score −740,610 (leaderboard Δ −740,610) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [pingpong-division](../concepts/pingpong-division.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two scheduling pins in `mod.rs` change. No code changes.

1. `SUB4_PP_PEAK`, the qubit budget that sizes the replay's chunked-add carry
   ladders, goes from 1267 to 1268. The circuit's real peak is 1266. It is set
   by the tape length (696 + 570), not by the budget, so one more unit of
   budget does not raise Q. It does let some replay rounds afford a wider
   carry ladder. Wider ladders mean fewer chunks, and each removed chunk
   boundary is one fewer truncated-compare phase repair.
2. `SUB4_PP_R1_MUL`, the multiply traversal's batch checkpoint, goes from 315
   to 326. Eleven more multiply replay rounds run in the final batch instead
   of interleaved one by one with the walk-back. Their chunk layouts change,
   and the author found 326 to be a local minimum of a jagged cost curve.

Together they save 585 average Toffoli at the same 1266 qubits.

## What changed and why it saves Toffoli

Both changes are `set_default_env` pins in the "Q1267 fallback composition"
block of `build()`, `src/point_add/mod.rs`. They feed `plan()` in
`src/point_add/pingpong_div.rs`, which is unchanged.

1. **`SUB4_PP_PEAK` 1267 → 1268** (`plan.peak`).
   - At each replay round, `allowance(plan, tape_len, walk_width) = peak − (tape_len + 2·256 + 2·walk_width)`
     is the number of qubits left for the replay cell's carry ladder.
     `ladder_for_allowance` turns that into a ladder budget. `chunk_layout`
     then chooses the chunk split of the 256-bit chunked add that fits the
     budget with the fewest *approximate* boundaries.
   - An approximate boundary is a measured carry whose phase is repaired by a
     truncated compare of `REPLAY_CHUNK_COMPARE` (22) bits. Each one costs
     about 22 Toffoli on the half of shots where the measurement outcome is 1.
     See [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
   - One more allowance qubit lets the rounds that sat just under a layout
     threshold drop a boundary. The comment measured −952 CCX for this alone.
   - Why Q does not rise: the comment says that at `ROUNDS = 696` the realised
     peak floor is `max(ROUNDS, ROUNDS_MUL) + 570 = 1266`. The ladders come in
     discrete sizes, and at 1268 none of them crosses that floor. 1269 would
     cross it, and so would 1268 together with `WALK_PEAK = 1268`.
     `SUB4_PP_WALK_PEAK` stays at 1267.
   - The comment also notes that this move had been tried and dropped when
     the divide depth was 694 ([`64f9aaa`](64f9aaa.md)). There it raised Q to
     1268. With 696 rounds restored ([`1f99759`](1f99759.md)), it is free.
     See [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md):
     the cap is a target, and the realised Q can be lower.
2. **`SUB4_PP_R1_MUL` 315 → 326** (`plan.r1` for the multiply traversal; the
   divide keeps `SUB4_PP_R1 = 335`).
   - In the multiply traversal, rounds `r1..=r2` are replayed one at a time,
     each just before its own walk-back round, with a budget computed from
     that round's tape length and walk width.
   - Rounds below `r1` are replayed together in one final batch, after the
     walk-back has reached round `r1`. That batch uses a single budget,
     computed at tape length `r1` with the odd low bits of `u` and `v` loaned
     out.
   - Moving `r1` to 326 puts rounds 315–325 into the batch and changes the
     batch's own budget. The comment's sweep is jagged: 324 → −189, 325 →
     +113, 326 → −231, 327 → +74 CCX. This is layout quantization, not a
     smooth trade, and 326 is a local minimum. See
     [pingpong-division](../concepts/pingpong-division.md) for the
     interleave plan.
3. **Tail nonce:** `SUB4_PINGPONG_TAIL_NONCE` default 12023044890526 →
   41032007408473.

The two comment figures (−952 and −231 CCX) were measured one at a time. The
shipped pair gives −585 on its own draw.

## Why it is still correct, and what it risks

- **No arithmetic changes.** Both knobs only change how the replay's 256-bit
  adds are chunked, and which rounds share a ladder budget. Chunk interiors
  are exact.
- **The boundary repairs are probabilistic,** as before. Fewer approximate
  boundaries means fewer truncated compares, so this move should lower the
  phase-channel λ a little, if anything. The comment calls the R1_MUL move
  "lambda-free".
- **The qubit claim holds by measurement.** The result is still 1266 qubits.
  If a ladder had crossed the floor, Q would have risen rather than any
  failure channel firing.
- The shipped nonce draws a clean set: 0 classical, 0 phase and 0 ancilla
  failures.

## Classification rationale

Previously filed as Dead-Code → iteration/threshold tuning. Neither knob is an
iteration count or a convergence threshold.
- The larger saving comes from raising a qubit budget so the adders can pick
  cheaper ladders. [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md)
  uses this commit as its example of exactly that, and its convention files
  budget retunes under Register and Scratch Allocation → ancilla-lifetime /
  venting (as with [`f5ff95b`](f5ff95b.md) and [`d9ef3e9`](d9ef3e9.md)).
- The `R1_MUL` move is a change to the replay schedule that serves the same
  ladder budgeting.

The runner-up is Strength Reduction → fast-adder reroute: the same adds pick
cheaper existing layouts.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout cc409de -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol cc409de 79e7afa -- src/point_add` is
   17 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 79e7afa -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1266 qubits
   - 906,124 average Toffoli (rounded)
   - score 1,147,152,984
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `41032007408473` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 1af218e..c6a4ec4 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2477,9 +2477,20 @@ pub fn build() -> Vec<Op> {
     // Q1268 while retaining a projected score improvement above 0.1%.
     set_default_env("SUB4_PP_ROUNDS_MUL", "694");
     set_default_env("SUB4_PP_R1", "335");
-    set_default_env("SUB4_PP_R1_MUL", "315");
+    // R1MUL-326: multiply-side round-1 split point. The response curve is JAGGED, not
+    // monotone (324 -> -189 CCX, 325 -> +113, 326 -> -231, 327 -> +74), so this is a discrete
+    // schedule boundary and a true local minimum rather than a failure-budget purchase.
+    // -231 CCX deterministic on every seed; peak unchanged. Measured lambda-free.
+    set_default_env("SUB4_PP_R1_MUL", "326");
     set_default_env("SUB4_PP_R2", "645");
-    set_default_env("SUB4_PP_PEAK", "1267");
+    // PP-1268: raise the ping-pong peak governor by one. At the SHIPPED ROUNDS=696 the
+    // realized peak floor is max(ROUNDS, ROUNDS_MUL) + 570 = 1266, and the ladder quantizes so
+    // that PEAK=1268 does NOT move the realized peak (1269 does; so does 1268 with WALK=1268).
+    // The extra unit of allowance lets the headroom-scheduled primitives take a cheaper
+    // ladder: -952 CCX deterministic, peak unchanged at 1266. Previously retracted as a dead
+    // end when the shipped config was ROUNDS=694, where PEAK=1268 realizes peak 1268 and costs
+    // two qubits; restoring ROUNDS to 696 revived it.
+    set_default_env("SUB4_PP_PEAK", "1268");
     set_default_env("SUB4_PP_WALK_PEAK", "1267");
     set_default_env("SUB4_PP_REPLAY_CHUNK", "96");
     set_default_env("SUB4_PP_REPLAY_CHUNK_COMPARE", "22");
@@ -2591,7 +2602,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(12023044890526);
+            .unwrap_or(41032007408473);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
```

