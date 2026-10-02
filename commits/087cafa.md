# 087cafa — Lower the replay and square ladder budgets together by three (1278 → 1275 qubits)

| | |
| --- | --- |
| Contestant | odinfree (co-author tag: welttowelt) |
| Date | 2026-08-22 |
| Submission | `f7b7ca6` |
| Commit | `087cafaef46a4e339644a6191ff2df2e7031cb80` |
| Result | 1275 qubits × 918,972 Toffoli = **1,171,689,300** |
| Base | `940e34a` (git parent, the author's previous submission): 1278 qubits × 917,481 Toffoli = 1,172,540,718 |
| Change vs base | qubits −3, Toffoli +1,491, score −851,418 (leaderboard Δ −851,418) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

At 1278 qubits two phases reach the peak: the ping-pong replay (with its
interleaved walk) and the product-register square. Each sizes its chunked
carry ladders against a budget: `SUB4_PP_PEAK` for the replay and
`SQUARE_LADDER` for the square. Lowering only one of them leaves Q where it
is. This commit lowers both by three wires in the same circuit, and moves the
first interleave checkpoint `r1` from 356 to 342 to suit the tighter cap. Q
drops from 1278 to 1275.

Narrower ladders need more chunks, and each extra chunk boundary costs a
measured erase plus a phase-repair compare. That costs 1,491 average
Toffoli. Break-even for three qubits at this size is about 3 × 917,481 / 1275
≈ 2,159 Toffoli, so the trade wins by 851,418 points.

## What changed and why it saves qubits

1. **`plan()`: `SUB4_PP_PEAK` 1278 → 1275 and `SUB4_PP_R1` 356 → 342** in
   `src/point_add/pingpong_div.rs` (`SUB4_PP_R2` stays 625).
   - `SUB4_PP_PEAK` is the budget behind
     `allowance = peak − tape_len − 2·N − 2·walk_width`, which every replay
     cell's chunked adder must fit (`pick_chunks` / `chunk_layout`).
   - It also sets the split point of the interleaved walk adds
     (`walk_low_chunk`), whose boundary repair is exact.
   - Three fewer wires force some replay rounds to use more or narrower
     chunks, and some walk rounds to split.
   - `r1` is the round below which the replay runs as one batch, right after
     walk round `r1`. Moving it earlier makes the tape live during that batch
     14 wires shorter but the walk registers a little wider, and it moves 14
     rounds into the interleaved band. The author re-picked it for the lower
     cap; the note does not record the per-checkpoint trade.
   - The new comment says: "The replay and square are co-binders: this cut
     only lowers global width when the square carry ladder is reduced in the
     same circuit."
2. **`SQUARE_LADDER`: 248 → 245** in
   `src/point_add/trailmix_ludicrous/square/product_register.rs`. This is the
   live carry-ladder budget of the square's wide (≥ 200-bit) chunked adds
   (`add_chunked_measured_budgeted`). See
   [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md) for
   co-binders and [adders-and-carries](../concepts/adders-and-carries.md) for
   the chunked adder.
3. **Tail nonce** (`SUB4_PINGPONG_TAIL_NONCE` default in `build()`,
   `src/point_add/mod.rs`): 176078461220 → 251000962439.

## Why it is still correct, and what it risks

Changing a ladder budget changes layout, not function. Every add stays exact
in value. The walk splits and the exact leading chunks repair their
boundaries exactly. But every extra *wide* replay or square boundary is
repaired by a compare of only the top `REPLAY_CHUNK_COMPARE` = 20 bits,
which is wrong on a tie (about 2^−20 per boundary) and shows up as a
**phase** failure. So λ rises a little. The shipped nonce `251000962439`
draws a clean set: 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

This is a pure peak-qubit move: it shrinks the live carry-ladder budgets of
both co-binding phases and pays Toffoli for it. That is the budget-retune
form of ancilla-lifetime / venting.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 940e34a -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 940e34a 087cafa -- src/point_add` is
   12 lines in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 087cafa -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1275 qubits
   - 918,972 average Toffoli (rounded)
   - score 1,171,689,300
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `251000962439` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ff5483d..b13ec46 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2539,7 +2539,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(176078461220);
+            .unwrap_or(251000962439);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index c0f346f..17298ab 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -1185,9 +1185,11 @@ fn plan(rounds: usize) -> Option<Plan> {
     // measured-erasure exposure (lambda) goes down as well.
     // `SUB4_PP_R1=509 SUB4_PP_R2=610` restores the previous op stream byte for
     // byte: at r1=509 no walk round is ever over budget, so nothing splits.
-    let r1 = env("SUB4_PP_R1", 356).min(rounds);
+    // The replay and square are co-binders: this cut only lowers global width
+    // when the square carry ladder is reduced in the same circuit.
+    let r1 = env("SUB4_PP_R1", 342).min(rounds);
     let r2 = env("SUB4_PP_R2", 625).min(rounds.saturating_sub(1));
-    let peak = env("SUB4_PP_PEAK", 1278);
+    let peak = env("SUB4_PP_PEAK", 1275);
     Some(Plan { r1, r2, peak })
 }
 
diff --git a/src/point_add/trailmix_ludicrous/square/product_register.rs b/src/point_add/trailmix_ludicrous/square/product_register.rs
index a030ae8..b291b44 100644
--- a/src/point_add/trailmix_ludicrous/square/product_register.rs
+++ b/src/point_add/trailmix_ludicrous/square/product_register.rs
@@ -24,8 +24,8 @@ const F_NAF: [(usize, bool); 5] = [
 /// measured boundary erasure instead of one full-width carry ladder: the
 /// 257-carry ladder of `tri_corr` was the square's peak owner (1287 qubits).
 const SQUARE_CHUNK_MIN: usize = 200;
-/// Live carry-ladder budget for those wide adds.
-const SQUARE_LADDER: usize = 248;
+/// Live carry-ladder budget for those wide adds; co-balanced with replay peak.
+const SQUARE_LADDER: usize = 245;
 fn add_full(circ: &mut B, addend: &[QubitId], acc: &[QubitId]) {
     assert_eq!(addend.len(), acc.len());
     let chunk_min = std::env::var("SUB4_SQUARE_CHUNK_MIN")
```

