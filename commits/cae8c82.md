# cae8c82 — Narrow the ping-pong replay chunk-boundary compare from 26 to 25 bits

| | |
| --- | --- |
| Contestant | RealAdii |
| Date | 2026-08-21 |
| Submission | `d626411` |
| Commit | `cae8c827135a5c7769ce4dabf13d20158b65a921` |
| Result | 1321 qubits × 951,325 Toffoli = **1,256,700,325** |
| Base | `897dda2` (git parent, teddyjfpender): 1321 qubits × 952,707 Toffoli = 1,258,525,947 |
| Change vs base | qubits ±0, Toffoli −1,382, score −1,825,622 (leaderboard Δ −1,825,622) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the first tuning commit on teddyjfpender's ping-pong divider
([`897dda2`](897dda2.md)), and it changes one constant. Each replay round adds
two 256-bit registers in three chunks. The two carries between chunks are
measured out, and the phase each measurement leaves is repaired by comparing
only the top `REPLAY_CHUNK_COMPARE` bits of the chunk. This commit makes that
compare 25 bits instead of 26. One compare bit is one Toffoli on the roughly
half of shots where the repair runs. With two boundaries in each of about
1,400 replay cells, that saves 1,382 average Toffoli. Qubits are unchanged.

## What changed and why it saves Toffoli

1. **`REPLAY_CHUNK_COMPARE`: 26 → 25** (a `const` in
   `src/point_add/pingpong_div.rs`).
   - `add_chunked_measured` splits each replay add into
     `chunk_bounds(256, REPLAY_CHUNK = 96)`, which is three chunks (86, 85 and
     85 bits) joined by two carry wires.
   - After the add, each boundary carry is erased with `b.hmr(carry, phase)`
     and then
     `cmp_lt_phase_conditioned(b, &acc[hi−k..hi], &addend[hi−k..hi], phase)`
     with `k = REPLAY_CHUNK_COMPARE`. The carry out of a chunk is exactly
     `[sum < addend]` over that chunk, so applying that comparison as a phase
     cancels the measurement's kickback.
   - The compare runs only when `phase` = 1 (`push_condition`). It costs `k`
     CCX forward and an `hmr`/`cz_if` inverse with no Toffoli. So one bit less
     is one Toffoli less on about half the shots, per boundary.
   - The fused replay cell runs in rounds 2..703 of both the Divide and the
     Multiply traversal, about 1,404 cells. 1,404 × 2 boundaries × 0.5 ≈ 1,404
     Toffoli, against the measured −1,382. See
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)
     and [measurement-uncompute](../concepts/measurement-uncompute.md).
2. **Tail nonce** (`SUB4_PINGPONG_TAIL_NONCE` default in `build()`,
   `src/point_add/mod.rs`): 82 → 1063.

## Why it is still correct, and what it risks

The add itself is exact. Only the phase repair is approximate: the truncated
compare is wrong when the top 25 bits of sum and addend tie, about 2^−25 per
boundary, and then the shot ends with a wrong **phase**. Going from 26 to 25
bits doubles this per-call rate, which raises λ a little. The shipped nonce
`1063` draws a clean set: 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change narrows a truncated comparator, which is
comparator/width truncation. The nonce change is the re-roll every circuit
change needs.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 897dda2 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 897dda2 cae8c82 -- src/point_add` is
   4 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol cae8c82 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   or `TLM_*` environment variables set. Expect:
   - 1321 qubits
   - 951,325 average Toffoli (rounded)
   - score 1,256,700,325
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `1063` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ff2fede..3d07bf7 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2531,7 +2531,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(82);
+            .unwrap_or(1063);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index 673cdd3..9e9325f 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -6,7 +6,7 @@ use super::*;
 const ROUNDS: usize = 704;
 const VALUE_WIDTH: usize = N + 3;
 const REPLAY_CHUNK: usize = 96;
-const REPLAY_CHUNK_COMPARE: usize = 26;
+const REPLAY_CHUNK_COMPARE: usize = 25;
 const REPLAY_FOLD_WINDOW: usize = 56;
 const ENDPOINT_FOLD_WINDOW: usize = 55;
 const REPLAY_FLAG_COMPARE: usize = 28;
```

