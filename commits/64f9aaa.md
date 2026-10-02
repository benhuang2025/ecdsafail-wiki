# 64f9aaa — Cut the divide walk from 696 to 694 rounds (which also narrows the width schedule in both traversals)

| | |
| --- | --- |
| Contestant | odinfree (co-author tag: welttowelt) |
| Date | 2026-08-25 |
| Submission | `18d4a0e` |
| Commit | `64f9aaa510b338041bc15d54b32c97fc2f1f5442` |
| Result | 1266 qubits × 909,063 Toffoli = **1,150,873,758** |
| Base | `522d002` (the author's circuit; the git parent `037b888` is the same circuit with another nonce): 1266 qubits × 911,402 Toffoli = 1,153,834,932 |
| Change vs base | qubits ±0, Toffoli −2,339, score −2,961,174 |
| Leaderboard Δ | −2,948,514, measured against the frontier at the time, `037b888` (1266 × 911,392 = 1,153,822,272), the nonce reroll of the base |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The ping-pong divider runs its value walk for a fixed number of rounds. This
commit pins the divide depth `SUB4_PP_ROUNDS` at 694 instead of 696. The
multiply depth was already pinned separately at 694, so only the divide
traversal loses rounds. Two fewer rounds means two fewer walk adds, walk-back
adds and coefficient replay cells.

The depth knob has a second effect. The width schedule is stretched to fit the
divide depth, so with a shorter depth every round of both traversals reads
its register width from a slightly later, narrower point of the table. That
narrows the walk by about 550 bit-rounds in total. Together these save 2,339
average Toffoli at the same 1266 qubits. The cost is λ: inputs that need the
two dropped rounds, or the extra width, now fail. A new tail nonce was hunted.

## What changed and why it saves Toffoli

1. **Divide depth: `SUB4_PP_ROUNDS` 696 → 694**, a `set_default_env` pin in
   the "Q1267 fallback composition" block of `build()`, `src/point_add/mod.rs`.
   - `rounds_for(Divide)` returns `rounds()`, which reads this variable.
     `rounds_for(Multiply)` reads `SUB4_PP_ROUNDS_MUL`, which the same block
     already pins at 694. So after this commit both traversals run 694 rounds.
     The comment above the `ROUNDS_MUL` pin ("one additional multiply
     traversal round") is stale and was left as is.
   - Each divide round costs a walk add, the matching walk-back add, and one
     fused replay cell (`signed_mod_add_pm_halve_fused`, a 256-bit modular
     add-and-halve). Dropping rounds 694 and 695 removes those. In the base
     those two rounds already ran at the floor width of 8 bits, so most of
     this part of the saving is the two replay cells.
   - It also removes two tape wires, but the peak is set by the
     `SUB4_PP_PEAK = 1267` budget, so Q stays at 1266.
2. **Side effect on the width schedule** (`width_round_index` in
   `src/point_add/pingpong_div.rs`, unchanged code).
   - `value_width(round)` looks up the 700-entry `WIDTH_SCHEDULE` at index
     `round × (ROUNDS_DEFAULT − 1) / (rounds() − 1)` = `round × 703 / (rounds() − 1)`,
     plus a +1 at the 100 `WIDTH_REPAIR` indices. The schedule is thus
     compressed to end at its floor on the last divide round.
   - The function uses `rounds()` for both directions. With `rounds()` = 694,
     the multiplier is 703/693 instead of 703/695, so each round maps to a
     slightly later, narrower table entry. This applies to the multiply walk
     too, even though its own depth did not change.
   - Summing `value_width` over the rounds actually run: divide 97,634 → 97,353
     bit-rounds, multiply 97,618 → 97,353. That is 546 fewer bit-rounds in
     total. Every walk and walk-back add in those rounds gets narrower. See
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
3. **Tail nonce:** `SUB4_PINGPONG_TAIL_NONCE` default 900613964630 (the
   parent's) → 1200595782693.

## Why it is still correct, and what it risks

Both effects are probabilistic, not exact.
- **Depth.** The walk is only correct if it reaches its terminal state (±1, ±1)
  within the fixed depth. An input that converges in round 694 or 695 was fine
  before and now yields a wrong quotient and dirty walk wires. See
  [pingpong-division](../concepts/pingpong-division.md).
- **Width.** A narrower register in some round is wrong for inputs whose walk
  value has not shrunk that far yet. The trimmed top bit is then not a sign
  copy, and the walk-back leaves garbage.
- Either failure shows up mostly in the classical channel, and usually as
  phase or ancilla garbage too.
- λ goes up, so a clean nonce is harder to find for this tree and for anyone
  building on it. The shipped nonce draws a clean set: 0 classical, 0 phase
  and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- The next frontier commit, [`1f99759`](1f99759.md), is built on `522d002`
  rather than on this commit, so it keeps 696 divide rounds. The cut did not
  carry forward.

## Classification rationale

The change is a shorter fixed iteration count for the walk, which is
iteration/threshold tuning. The width narrowing is a side effect of the same
knob, not a separate edit, so the commit is not filed as width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 522d002 -- src/point_add`.
   - The git parent `037b888` has the same circuit as `522d002` with a
     different nonce. Diffing against either is 4 lines in 1 file, and only
     the old nonce literal differs. The note uses `522d002`, the last tree with
     a circuit change.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 64f9aaa -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1266 qubits
   - 909,063 average Toffoli (rounded)
   - score 1,150,873,758
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `1200595782693` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 8b497c1..d2c6b84 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2461,7 +2461,7 @@ pub fn build() -> Vec<Op> {
     // externally overridable for focused reliability experiments. The
     // pingpong tail nonce intentionally remains at the frontier fallback.
     set_default_env("SUB4_PINGPONG_LOW56_FOLD", "1");
-    set_default_env("SUB4_PP_ROUNDS", "696");
+    set_default_env("SUB4_PP_ROUNDS", "694");
     // Keep one additional multiply traversal round as a bounded reliability
     // purchase. The extra tape wire raises this composition from Q1267 to
     // Q1268 while retaining a projected score improvement above 0.1%.
@@ -2581,7 +2581,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(82505456522172);
+            .unwrap_or(1200595782693);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
```

