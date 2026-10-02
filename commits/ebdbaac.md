# ebdbaac — Admit a 12th cascade root (529,530,1152) and re-apply the 7→3 affine bridge

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-08-17 |
| Submission | `6af22f9` |
| Commit | `ebdbaac41f79d8f757a61028d0e81dc4baa07e1f` |
| Result | 1154 qubits × 1,283,441 Toffoli = **1,481,090,914** |
| Base | `f735fd7` (odinfree's cascade lever): 1154 qubits × 1,283,487 Toffoli = 1,481,143,998 |
| Change vs base | qubits ±0, Toffoli −46, score −53,084 |
| Leaderboard Δ | −50,776, measured against the frontier at the time, `9b2ce61` (1154 × 1,283,485 = 1,481,141,690), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

`f735fd7` cancels blocked pairs of identical Toffolis when the three-way AND
left behind (the "residual triple") almost never fires. It accepted 11 such
triples and left out three more as too expensive in λ. This commit accepts
one of the three, `(529, 530, 1152)`, which fired 151 times in 10.5 million
shots (about +0.13 λ). Cancelling that root also lets the exact canceller
remove the pairs it was blocking.

The commit also re-applies the exact 7→3 affine bridge from `9aceb7d`, worth
one Toffoli. Together the two save 46 average Toffoli at 1154 qubits.

## What changed and why it saves Toffoli

1. **`src/point_add/trailmix_ludicrous/constprop.rs`**: `(529, 530, 1152)` is
   appended to `DEFAULT_CASCADE_TRIPLES`, which now has 12 entries.
   - `find_inverse_pairs` cancels a pair `CCX(a,b→t) … CCX(a,b→t)` whose only
     intervening control write is one unconditional `CCX(c,d→a)` when the
     sorted triple `(b, c, d)` is on that list. The pair's net effect is
     `t ^= b·c·d`, so removing it is wrong only when that AND is 1.
   - `f735fd7`'s comment lists this triple as excluded: 151 fires per
     10,485,760 shots, 0.1299 expected failures per 9,024-shot run, below its
     cut-off of about 272 removed ops per unit of λ.
   - Removing this root also unblocks more pairs that the exact predicate then
     cancels on later `constprop::run` iterations. The commit's total
     saving, −46 T, therefore includes those follow-on pairs. See
     [`f735fd7`](f735fd7.md) and the "Cascade" entry in
     [dead-gate-strip](../concepts/dead-gate-strip.md).
2. **`src/point_add/mod.rs`**: new helpers `affine_bridge_cx`,
   `affine_bridge_ccx` and `apply_exact_affine_bridge(ops)`. The function
   finds the unique 7-op window
   `ccx(511,898→735) cx(735→897) cx(735→734) cx(735→897) cx(734→897) cx(735→734) ccx(511,898→735)`
   and replaces it with `cx(734→897) cx(735→897) ccx(511,898→897)`, the
   exact identity from [`9aceb7d`](9aceb7d.md). It is called just before
   the tail nonce is applied. −1 T per shot.
3. **Tail nonce**: default `SUB4_TAIL_NONCE` 1337610097 → 947619100.

## Why it is still correct, and what it risks

- **The new root is probabilistic.** On inputs where `q529·q530·q1152 = 1`
  at the blocking write, `t` misses a flip, which gives a wrong value or a
  phase error. Its measured cost is about 0.13 extra failing shots per draw,
  on top of the 0.49 the first 11 roots already cost. The pairs it unblocks
  are exact.
- **The bridge is exact** and fail-closed: it asserts a single match.
- The shipped nonce `947619100` draws a clean test set: 0 classical, 0 phase
  and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- Because the branch was cut from `f735fd7`, it does not have `9b2ce61`'s
  second bridge (−1 T) or its 14-op tail. `afcc72e` later brings both bridges
  back.

## Classification rationale

Both parts remove redundant CCX pairs, one by a λ-priced cascade root and one
by an exact peephole. That is dead-gate/self-inverse removal.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f735fd7 -- src/point_add`.
   - `git diff --ignore-cr-at-eol f735fd7 ebdbaac -- src/point_add` is 50
     changed lines in 2 files.
   - Do not start from the git parent `9b2ce61`. Against it the diff is 167
     lines. It would delete swadhin's second (control-delta) bridge and his
     base-1024 nonce tail, which this commit never had.
2. **Apply the patch below** from the repo root with
   `git apply --ignore-whitespace`. The flag lets the patch apply whether the
   files use LF or CRLF line endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ebdbaac -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   or `TLM_*` overrides set (in particular no `TLM_CASCADE_*`). Expect:
   - 1154 qubits
   - 1,283,441 average Toffoli (rounded)
   - score 1,481,090,914
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `947619100` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6b5bd19..6193c5b 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1784,6 +1784,52 @@ fn apply_deep_strip_identity(ops: Vec<Op>) -> Vec<Op> {
     out
 }
 
+fn affine_bridge_cx(control: u64, target: u64) -> Op {
+    let mut op = Op::empty();
+    op.kind = OperationType::CX;
+    op.q_control1 = QubitId(control);
+    op.q_target = QubitId(target);
+    op
+}
+
+fn affine_bridge_ccx(control2: u64, control1: u64, target: u64) -> Op {
+    let mut op = Op::empty();
+    op.kind = OperationType::CCX;
+    op.q_control2 = QubitId(control2);
+    op.q_control1 = QubitId(control1);
+    op.q_target = QubitId(target);
+    op
+}
+
+/// Exact affine-bridge identity, guarded by the complete seven-op occurrence.
+fn apply_exact_affine_bridge(mut ops: Vec<Op>) -> Vec<Op> {
+    let source = [
+        affine_bridge_ccx(511, 898, 735),
+        affine_bridge_cx(735, 897),
+        affine_bridge_cx(735, 734),
+        affine_bridge_cx(735, 897),
+        affine_bridge_cx(734, 897),
+        affine_bridge_cx(735, 734),
+        affine_bridge_ccx(511, 898, 735),
+    ];
+    let matches: Vec<usize> = ops
+        .windows(source.len())
+        .enumerate()
+        .filter_map(|(index, window)| (window == source).then_some(index))
+        .collect();
+    assert_eq!(matches.len(), 1, "exact affine-bridge occurrence drift");
+    let index = matches[0];
+    ops.splice(
+        index..index + source.len(),
+        [
+            affine_bridge_cx(734, 897),
+            affine_bridge_cx(735, 897),
+            affine_bridge_ccx(511, 898, 897),
+        ],
+    );
+    ops
+}
+
 /// Rewrite the 96-op identity tail to encode the ground nonce. Only q_target
 /// changes (X;X pairs stay identities), so circuit function is untouched; the
 /// Fiat-Shamir seed is what moves.
@@ -2407,10 +2453,11 @@ pub fn build() -> Vec<Op> {
     // against its own exact stream. Baking the value in is how a solution ships on this
     // benchmark. Static analysers that pattern-match on "nonce" flag it as a hard-coded
     // cryptographic value; that reading does not apply here.
+    let ops = apply_exact_affine_bridge(ops);
     let nonce: u64 = std::env::var("SUB4_TAIL_NONCE")
         .ok()
         .and_then(|s| s.parse().ok())
-        .unwrap_or(1337610097);
+        .unwrap_or(947619100);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
diff --git a/src/point_add/trailmix_ludicrous/constprop.rs b/src/point_add/trailmix_ludicrous/constprop.rs
index 7d96b81..33f2c4b 100644
--- a/src/point_add/trailmix_ludicrous/constprop.rs
+++ b/src/point_add/trailmix_ludicrous/constprop.rs
@@ -634,6 +634,7 @@ const DEFAULT_CASCADE_TRIPLES: &[(u64, u64, u64)] = &[
     (530, 531, 1132),
     (530, 531, 1149),
     (530, 531, 1150),
+    (529, 530, 1152),
 ];
 
 fn find_inverse_pairs(
```

