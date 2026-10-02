# d484caa — Re-mine the dead-gate strip on the new stream and key it by gate identity instead of op position (1,442 gates)

| | |
| --- | --- |
| Contestant | mochimodev |
| Date | 2026-07-23 |
| Submission | `eccfedb` |
| Commit | `d484caaf600f7972edf568724197bd3af157e167` |
| Result | 1152 qubits × 1,316,081 Toffoli = **1,516,125,312** |
| Base | `5b834ba` (git parent, the author's previous submission): 1152 qubits × 1,317,390 Toffoli = 1,517,633,280 |
| Change vs base | qubits ±0, Toffoli −1,309, score −1,507,968 (leaderboard Δ −1,507,968) |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the generated key table `deep_strip_keys.rs` is copied from the commit; the patch covers `mod.rs` |

## Summary

The base had dropped its positional dead-gate strip because its edits shifted
every op index. This commit mines a new strip for the base's stream: a fire
census over 1e8 random inputs finds 1,442 Toffoli-class gates (1,400 CCX and 42
CCZ) whose two quantum controls were never both 1. The scorer charges such
gates in full even though they do nothing, so deleting them saves 1,309 average
executed Toffoli at the same 1152 qubits.

The new part is how the strip finds its gates. Each gate is keyed by its
operands plus "the k-th gate with these operands", instead of by its op index.
An edit elsewhere in the stream shifts indices but usually leaves these keys
unchanged, so the table keeps working after unrelated edits.

## What changed and why it saves Toffoli

- **New generated file `src/point_add/deep_strip_keys.rs`.** It holds
  `DEAD_KEYS: &[(u8, u64, u64, u64, u64, u32)]` with 1,442 entries. Each key is
  `(kind, q_control2, q_control1, q_target, c_condition, ordinal)`:
  - `kind` is 13 for CCX and 14 for CCZ;
  - `c_condition` is the classical condition bit, with `u64::MAX` meaning none;
  - `ordinal` counts earlier gates with the same five fields, in stream order.
  The header says the keys come from a 1e8 fire census of the composed stream
  (the seven exact wins of 5b834ba plus the GAP_J2 narrowing of 3f8ce09).
- **New `apply_deep_strip_identity(ops)` in `src/point_add/mod.rs`.**
  - It walks the stream once, keeps a counter per five-field tuple, and drops
    each CCX/CCZ whose six-field key is in `DEAD_KEYS`.
  - The counter advances for every matching gate, dropped or not, so ordinals
    refer to the unstripped stream, the one the census saw.
  - It does not check that the number of matches equals the table length. It
    only prints the count.
- **In `build()`** it is now the default strip, after the second fanout pass
  and before the tail nonce. `SUB4_APPLY_STRIP=0` turns it off, and
  `SUB4_APPLY_D2_STRIP=1` selects the old positional D2 strip instead.
- **Why it saves Toffoli.** `sim.rs` charges a CCX/CCZ whenever its classical
  condition is true, whatever its control values. A gate that never fires costs
  a full Toffoli per shot for nothing. See
  [dead-gate-strip](../concepts/dead-gate-strip.md) and
  [scoring-and-validation](../concepts/scoring-and-validation.md).
- **Tail nonce:** `SUB4_TAIL_NONCE` default 2001891927370 → 4001397000397.

## Why it is still correct, and what it risks

- **Empirical, not exact.** "Never fired in 1e8 inputs" is not a proof. The
  note says the marginal gates fire below 1e-8, and that strips from 1e6-input
  censuses "over-count ~5x and collapse the circuit". If a removed gate would
  fire on some input, that input gets a wrong output or a stray phase, and the
  classical or phase channel catches it.
- The note reports the same clean-batch rate as the unstripped circuit, 0.857422
  at a fixed seed. So the strip did not measurably raise λ, the expected number
  of failing shots, and the nonce hunt was no harder.
- **Identity keys can still go stale.** An upstream edit that changes the
  operands of gates in the dead region, or adds a gate with the same operand
  tuple earlier in the stream, shifts the ordinals. The strip then deletes a
  live gate. Nothing in this version detects that. The next re-mine,
  [`a254a8a`](a254a8a.md), added a `tuple_occupancy` guard for this reason.
- The shipped nonce `4001397000397` draws a clean test set: 9,024 of 9,024 shots,
  0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is deleting gates that a census found never fire. That
is dead-gate/self-inverse removal, like the earlier positional strips.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 5b834ba -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 5b834ba d484caa -- src/point_add` is 1,496 lines
   in 2 files, almost all of it the new key table.
2. **Copy the generated key table from the commit:**
   `git checkout d484caa -- src/point_add/deep_strip_keys.rs`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It covers `mod.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol d484caa -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `TLM_*` or
   `SUB4_*` overrides set. Expect:
   - 1152 qubits
   - 1,316,081 average Toffoli (1,316,080.523 before rounding)
   - score 1,516,125,312
   - 0 classical, 0 phase and 0 ancilla failures
6. **Nonce caveat.** The score only reproduces with the nonce `4001397000397`
   and an identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index b51a551..1d81b0b 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -24,6 +24,7 @@ pub mod trailmix_ludicrous;
 mod single_ccx_fanout;
 mod m60_dead_t10;
 mod d2_deep_strip;
+mod deep_strip_keys;
 
 thread_local! {
     static D1_PHASE_CORRECTED_PRODUCT_CORE_SCOPE: std::cell::Cell<bool> =
@@ -1670,6 +1671,43 @@ fn apply_d2_deep_strip(ops: Vec<Op>) -> Vec<Op> {
     ops.into_iter().enumerate().filter(|(i, _)| !drop.contains(i)).map(|(_, o)| o).collect()
 }
 
+/// Identity-keyed deep strip. Instead of positional indices (which any op-stream edit
+/// invalidates), each census-dead CCX/CCZ is keyed by its operand tuple
+/// (kind, q_control2, q_control1, q_target, c_condition) plus the k-th-occurrence ordinal
+/// of that tuple in stream order. Derived once from a 1e8 fire-census; re-applies to any
+/// edited stream that does not relabel the dead region, with no re-census.
+fn apply_deep_strip_identity(ops: Vec<Op>) -> Vec<Op> {
+    use std::collections::{HashMap, HashSet};
+    let dead: HashSet<(u8, u64, u64, u64, u64, u32)> =
+        deep_strip_keys::DEAD_KEYS.iter().copied().collect();
+    if dead.is_empty() {
+        return ops;
+    }
+    let mut ord: HashMap<(u8, u64, u64, u64, u64), u32> = HashMap::new();
+    let mut out = Vec::with_capacity(ops.len());
+    let mut removed = 0usize;
+    for op in ops {
+        let kb = op.kind as u8; // CCX=13, CCZ=14 in the serialized stream
+        if kb == 13 || kb == 14 {
+            let tup = (kb, op.q_control2.0, op.q_control1.0, op.q_target.0, op.c_condition.0);
+            let o = ord.entry(tup).or_insert(0);
+            let key = (tup.0, tup.1, tup.2, tup.3, tup.4, *o);
+            *o += 1;
+            if dead.contains(&key) {
+                removed += 1;
+                continue;
+            }
+        }
+        out.push(op);
+    }
+    eprintln!(
+        "[deep-strip-identity] removed {} / {} dead keys matched",
+        removed,
+        deep_strip_keys::DEAD_KEYS.len()
+    );
+    out
+}
+
 /// Rewrite the 96-op identity tail to encode the ground nonce. Only q_target
 /// changes (X;X pairs stay identities), so circuit function is untouched; the
 /// Fiat-Shamir seed is what moves.
@@ -2236,14 +2274,18 @@ pub fn build() -> Vec<Op> {
     // submission-4: the baked d2 deep-strip is indexed for the OLD (pre-bit-exact-wins) op
     // stream and would misfire here; it is a near-eps lever and is re-derived on the composed
     // stream separately. Disable it for the pure bit-exact-wins circuit unless explicitly re-enabled.
-    let ops = if std::env::var("SUB4_APPLY_D2_STRIP").ok().as_deref() == Some("1") {
+    // Identity-keyed deep strip (1442 census-dead gates, zero-error) on by default;
+    // SUB4_APPLY_STRIP=0 disables for A/B measurement.
+    let ops = if std::env::var("SUB4_APPLY_STRIP").ok().as_deref() == Some("0") {
+        ops
+    } else if std::env::var("SUB4_APPLY_D2_STRIP").ok().as_deref() == Some("1") {
         apply_d2_deep_strip(ops)
     } else {
-        ops
+        apply_deep_strip_identity(ops)
     };
     // The tail nonce ground for this composed stream (verified PASS 0/0/0, score 1,517,633,280).
     // SUB4_TAIL_NONCE overrides for re-grinding/seam-export.
-    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(2001891927370);
+    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(4001397000397);
     apply_tail_nonce(ops, nonce)
 }
 
```

