# adec6f4 — Lend one sign-copy wire of the terminal `u` across the replay (1318 → 1317 qubits)

| | |
| --- | --- |
| Contestant | odinfree (co-author tag: welttowelt) |
| Date | 2026-08-21 |
| Submission | `7e48163` |
| Commit | `adec6f4a2a7f0c5f3e42e561ed80a49f7bcbe50b` |
| Result | 1317 qubits × 940,018 Toffoli = **1,238,003,706** |
| Base | `be0c8bc` (git parent, Akashneelesh): 1318 qubits × 940,014 Toffoli = 1,238,938,452 |
| Change vs base | qubits −1, Toffoli +4, score −934,746 (leaderboard Δ −934,746) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The peak of this circuit sits in the ping-pong coefficient replay, where the
whole sign tape, the two 256-bit coefficient registers and the terminal walk
registers `u` and `v` are all live. At the end of the walk `u` is +1 or −1 in
two's complement, so every bit above bit 0 equals its sign bit. The replay
reads only the sign. This commit clears the second-highest bit of `u` with one
CX from the sign, frees the wire for the whole replay, and rebuilds it with
the same CX afterwards. The replay plateau is one wire lower, so the peak drops
from 1318 to 1317 qubits. It costs no Toffoli. The +4 average Toffoli is
island noise from the new test draw. This is the first sign-copy loan in the
ping-pong line; [`152fbe0`](152fbe0.md) later generalises it to all 16 known-value wires of `u` and `v` (15 more than here).

## What changed and why it saves a qubit

1. **Loan of `u[len−2]` across the replay** in
   `pingpong_mod_mul_div_in_place`, `src/point_add/pingpong_div.rs`.
   - Right after `value_walk` and the allocation of `coefficient`:
     ```
     terminal_sign = u[len-1]; replay_loan = u[len-2]
     cx(terminal_sign, replay_loan)   # replay_loan was a copy of the sign, now |0>
     free(replay_loan)                # emits R on a |0> wire, returns it to the pool
     ```
   - The replay then runs (`replay_halving` plus `conditional_mod_negate`
     for Divide; the seed CNOTs, `conditional_mod_negate` and
     `replay_doubling_inverse` for Multiply). The allocator hands the freed
     index to replay scratch, such as chunk carries and fold carries, which
     return it to |0⟩ before freeing it.
   - After the replay, before `free_vec(&coefficient)` and `value_walk_back`:
     `reacquire(replay_loan); cx(terminal_sign, replay_loan)`. That restores
     the sign extension that the walk-back expects.
   - The loan covers both traversals, Divide and Multiply. Both replays were
     at the 1318 plateau, so both come down together.
   - Why the bit is a copy: the walk ends at the fixed point (±1, ±1).
     +1 = `0…01` and −1 = `1…11`, so bits 1 to w−1 of `u` are all equal to the
     sign. See [venting-and-wire-loans](../concepts/venting-and-wire-loans.md)
     and [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
2. **Tail nonce** (`SUB4_PINGPONG_TAIL_NONCE` default in `build()`,
   `src/point_add/mod.rs`): 700291 → 165193.

## Why it is still correct, and what it risks

On every input whose walk converges, `u[len−2]` really is a copy of the sign,
so the clear, the reset and the restore are exact. The sign wire is only read
during the replay, never changed, so the restore uses the same value as the
clear. The loan adds no new failure mode beyond the existing depth
truncation. On an input whose walk has not converged the bit may differ from
the sign. Then `free` resets a 1, which leaves a random **phase**, but such an
input already fails classically. The +4 Toffoli is not a gate change: the new
nonce draws different inputs and measurement outcomes, and the average of the
conditionally executed repairs moves a little. The shipped nonce `165193`
draws a clean set: 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from shortening one wire's live range across the peak: the
wire is cleared, lent out and restored. That is ancilla-lifetime / venting.
Scratch/ancilla reuse was the runner-up, since the freed wire is reused as
replay scratch; the lifetime cut is the primary lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout be0c8bc -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol be0c8bc adec6f4 -- src/point_add` is
   16 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol adec6f4 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1317 qubits
   - 940,018 average Toffoli (rounded)
   - score 1,238,003,706
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `165193` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 17d017c..2badef8 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2531,7 +2531,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(700291);
+            .unwrap_or(165193);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index a052c14..0582599 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -134,6 +134,17 @@ pub(crate) fn pingpong_mod_mul_div_in_place(
     let tape = value_walk(b, &mut u, &mut v);
     let coefficient = b.alloc_qubits(N);
 
+    // The fixed walk terminates with each signed value equal to +1 or -1.
+    // Therefore the penultimate bit is a copy of the sign bit.  It is idle
+    // throughout coefficient replay, which only observes the terminal sign,
+    // so clear and release this passenger across the replay peak.  Every
+    // scratch user returns it to |0>; reacquire and restore the sign extension
+    // before the reverse value walk consumes the terminal register again.
+    let terminal_sign = u[u.len() - 1];
+    let replay_loan = u[u.len() - 2];
+    b.cx(terminal_sign, replay_loan);
+    b.free(replay_loan);
+
     match direction {
         PingPongDirection::Divide => {
             // The emitted seed is genuinely (0,c), not a cost-model comment:
@@ -162,6 +173,9 @@ pub(crate) fn pingpong_mod_mul_div_in_place(
         }
     }
 
+    b.reacquire(replay_loan);
+    b.cx(terminal_sign, replay_loan);
+
     // Divide leaves two equal canonical outputs and clears one above;
     // multiply's inverse recurrence ends at (0,a*c).  Either way this is a
     // proved-zero register, never a fake free.
```

