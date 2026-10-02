# 9aceb7d — Exact 7→3 affine-bridge peephole: two equal CCX around a CX block become one

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-08-12 |
| Submission | `4bad376` |
| Commit | `9aceb7dace3eb7d23192ea0f5725f4858ba88cf3` |
| Result | 1154 qubits × 1,284,131 Toffoli = **1,481,887,174** |
| Base | `474c29a` (git parent and frontier at the time, gopikannappan): 1154 qubits × 1,284,147 Toffoli = 1,481,905,638 |
| Change vs base | qubits ±0, Toffoli −16, score −18,464 (leaderboard Δ −18,464) |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The finished op stream contains, exactly once, a 7-op window in which the
same Toffoli `CCX(511, 898 → 735)` appears at both ends with five CNOTs
between them. Tracking what the window does to each wire shows that it only
changes wire 897, by `q734 ⊕ q735 ⊕ q511·q898`. The same effect needs only
two CNOTs and one Toffoli.

This commit finds that window after all other rewrite passes and replaces it
with the 3-op form. That removes one unconditional Toffoli, so every shot
executes one Toffoli fewer. The rewrite is exact. The measured change of −16
is that one Toffoli plus the luck of a new test draw.

## What changed and why it saves Toffoli

All changes are in `build()` in `src/point_add/mod.rs`, after the post-strip
fanout closure and just before the tail nonce.

- A 7-op pattern `affine_source` is built from two helper closures `cx` and
  `ccx` (no classical condition):

  ```
  ccx(511, 898 -> 735)
  cx(735 -> 897)
  cx(735 -> 734)
  cx(735 -> 897)
  cx(734 -> 897)
  cx(735 -> 734)
  ccx(511, 898 -> 735)
  ```

- `ops.windows(7)` must match it exactly once (`assert_eq!(matches.len(), 1,
  "exact affine bridge occurrence drift")`), and the match must lie before
  the 96-op nonce tail.
- The window is spliced to `cx(734 -> 897); cx(735 -> 897); ccx(511, 898 -> 897)`.
- The tail nonce `SUB4_TAIL_NONCE` goes from 906027526784 to 1978352376.

**Why the two forms are equal.** Write `a = q735`, `b = q734`, `c = q897`
and `p = q511·q898` (511 and 898 are never written in the window):

| after op | a | b | c |
|---|---|---|---|
| 1 `ccx → a` | a⊕p | b | c |
| 2 `cx a → c` | a⊕p | b | c⊕a⊕p |
| 3 `cx a → b` | a⊕p | b⊕a⊕p | c⊕a⊕p |
| 4 `cx a → c` | a⊕p | b⊕a⊕p | c |
| 5 `cx b → c` | a⊕p | b⊕a⊕p | c⊕b⊕a⊕p |
| 6 `cx a → b` | a⊕p | b | c⊕b⊕a⊕p |
| 7 `ccx → a` | a | b | c⊕a⊕b⊕p |

The net effect is `c ^= a ⊕ b ⊕ p`, with `a` and `b` restored. The
replacement applies `c ^= b`, `c ^= a`, `c ^= p`, which is the same. It has
one CCX instead of two and two CX instead of five.

The code calls this an "affine bridge": the pair of equal CCX bracketing a
Clifford block is collapsed by moving the AND onto the wire that the block
actually changes. See [dead-gate-strip](../concepts/dead-gate-strip.md),
"Affine-bridge peepholes".

## Why it is still correct, and what it risks

- **Exact.** The table above holds for every value of the five wires, so the
  circuit computes the same function on every input. No hard inputs are
  added and λ is unchanged.
- **Fail-closed.** If an upstream edit moves, duplicates or removes the
  window, the unique-match assert aborts the build instead of rewriting the
  wrong ops. The pattern names fixed qubit indices, so it is tied to this
  exact stream.
- **Score.** The rewrite saves exactly one executed Toffoli per shot. The
  other 15 of the −16 come from the new test draw. See
  [scoring-and-validation](../concepts/scoring-and-validation.md).
- The shipped nonce `1978352376` draws a clean test set: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

An exact local rewrite that cancels one CCX of an equal pair is
dead-gate/self-inverse removal. The census puts exact peepholes and
census-mined strips in the same change-type.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 474c29a -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 474c29a 9aceb7d -- src/point_add` is
   44 changed lines in `mod.rs`.
2. **Apply the patch below** from the repo root with
   `git apply --ignore-whitespace`. The flag lets the patch apply whether the
   files use LF or CRLF line endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 9aceb7d -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   or `TLM_*` overrides set. Expect:
   - 1154 qubits
   - 1,284,131 average Toffoli (rounded)
   - score 1,481,887,174
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `1978352376` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 39dcd36..a623d4a 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2397,13 +2397,55 @@ pub fn build() -> Vec<Op> {
             }
         }
     }
+    // Apply the single exact top-level affine bridge witnessed on this fixed
+    // post-strip stream.  The seven-gate source and three-gate replacement are
+    // the basis-action identity proved by AffineBridgeConjugation; requiring a
+    // unique occurrence fails closed if an upstream edit moves or duplicates it.
+    let mut affine_source = Vec::with_capacity(7);
+    let cx = |control: u64, target: u64| {
+        let mut op = Op::empty();
+        op.kind = OperationType::CX;
+        op.q_control1 = QubitId(control);
+        op.q_target = QubitId(target);
+        op
+    };
+    let ccx = |a: u64, b: u64, target: u64| {
+        let mut op = Op::empty();
+        op.kind = OperationType::CCX;
+        op.q_control2 = QubitId(a);
+        op.q_control1 = QubitId(b);
+        op.q_target = QubitId(target);
+        op
+    };
+    affine_source.extend([
+        ccx(511, 898, 735),
+        cx(735, 897),
+        cx(735, 734),
+        cx(735, 897),
+        cx(734, 897),
+        cx(735, 734),
+        ccx(511, 898, 735),
+    ]);
+    let matches: Vec<usize> = ops
+        .windows(affine_source.len())
+        .enumerate()
+        .filter_map(|(index, window)| (window == affine_source.as_slice()).then_some(index))
+        .collect();
+    assert_eq!(matches.len(), 1, "exact affine bridge occurrence drift");
+    let affine_index = matches[0];
+    assert!(affine_index + affine_source.len() <= ops.len() - 96);
+    ops.splice(
+        affine_index..affine_index + affine_source.len(),
+        [cx(734, 897), cx(735, 897), ccx(511, 898, 897)],
+    );
+
     // Tail nonce for the v5c composed geometry (9024/9024 PASS, avg 1285673.863 x 1154 qubits,
     // score 1,483,667,638). Dispositioned by trusted CPU oracle 0/0/0 over 9,024 shots.
     // SUB4_TAIL_NONCE overrides it for controlled re-grinding.
     let nonce: u64 = std::env::var("SUB4_TAIL_NONCE")
         .ok()
         .and_then(|s| s.parse().ok())
-        .unwrap_or(906027526784);
+        .unwrap_or(1978352376);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
```

