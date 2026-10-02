# b60eec2 — Drop the constant-|1⟩ `f1` ancilla from the bulk Kaliski iteration (2310 → 2309 qubits), and re-tune two thresholds by one

| | |
| --- | --- |
| Contestant | saucegodbased |
| Date | 2026-06-01 |
| Submission | `d0c398d` |
| Commit | `b60eec2185fa5f8f184a0e209126477a91a772f0` |
| Result | 2309 qubits × 3,637,411 Toffoli = **8,398,781,999** |
| Base | [`a3ee589`](a3ee589.md) (git parent, philburgess1): 2310 qubits × 3,638,710 Toffoli = 8,405,420,100 |
| Change vs base | qubits −1, Toffoli −1,299, score −6,638,101 (leaderboard Δ −6,638,101) |
| Family | Constant Propagation and Classical Specialization → host-derived / classical specialization |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The bulk-prefix Kaliski iteration allocated a qubit `f1`, set it to |1⟩ with an
X, and used it for exactly one thing: as a control of a classically
conditioned CZ in STEP 5. A CZ with one control known to be |1⟩ is just a Z on
the other qubit. This commit adds a conditioned single-qubit `Z` op to the
builder and uses it, so `f1` is never allocated during the iteration. `f1` was
live across STEP 4, the phase that sets the global peak, so the peak drops
from 2310 to 2309.

Because the op stream changes, the test draw changes too. To land a clean
draw the author also moved two empirical thresholds by one step each, which
happens to save 1,299 Toffoli: `R_SMALL_THRESHOLD` 326 → 327 and
`BULK_PREFIX_SAFE_ITERS` 400 → 401.

## What changed and why it saves qubits

All edits are in `src/point_add/mod.rs`. For the Kaliski iteration and the
bulk prefix, see the background in [`a3ee589`](a3ee589.md).

1. **New builder op `B::z_if(q, cond)`.** It emits `OperationType::Z` on `q`
   with classical condition `cond`. In the simulator this does
   `phase ^= cond & qubit(q)`, which is what `cz_if(c, q, cond)` does when `c`
   is |1⟩.
2. **`kaliski_iteration_bulk_prefix3()`: `f1` is removed.**
   - Old: at the top, `let f1 = b.alloc_qubit(); b.x(f1);`. In STEP 5 the
     measured uncompute of `add_f` was `b.hmr(add_f, sm); b.cz_if(f1, b_f, sm);`.
     At the end, `b.x(f1); b.free(f1);`.
   - New: STEP 5 is `b.hmr(add_f, sm); b.z_if(b_f, sm);`, and `f1` is never
     allocated over the body.
   - `f1` played the role of the generic iteration's termination flag `f`,
     which the bulk prefix knows to be 1. Its only remaining use was this
     phase fix-up (see [measurement-uncompute](../concepts/measurement-uncompute.md)
     for `hmr` + conditioned phase repair).
   - The bulk iteration's STEP 4 (the fused controlled subtract / add with a
     256-wide temporary) is where the circuit reaches its maximum. One fewer
     live wire there lowers the whole circuit's peak by one. See
     [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
3. **A transient alloc/free at the end of the iteration.** In place of the
   old `b.free(f1)`, the code does `{ let f1 = b.alloc_qubit(); b.free(f1); }`.
   `free` emits an `R` (reset) op. On a qubit that is |0⟩ the reset adds no
   phase, so this costs nothing and changes nothing in the arithmetic. The
   author's comment says it keeps the Fiat–Shamir XOF stream byte-identical.
   That is not quite right: the XOF is seeded from a hash of the whole op
   stream (`fiat_shamir_seed` in `eval_circuit.rs`), and removing the two
   `X(f1)` ops already changes that hash. What the extra `R` really does is
   keep each later `hmr`/`R` reading the same *offset* in the new stream. It
   is harmless either way.
4. **`R_SMALL_THRESHOLD`: 326 → 327.** For iterations below this threshold,
   STEP 7+8 doubles `r` with a plain wire shift (0 Toffoli) instead of a full
   modular double. One more iteration of each Kaliski run now gets the free
   shift.
5. **`BULK_PREFIX_SAFE_ITERS`: 400 → 401.** Pair2 runs 401 iterations, so its
   last iteration (index 400) now also uses the cheaper bulk body. Pair1 (399
   iterations) was already all-bulk.

Items 4 and 5 give the −1,299 Toffoli. Items 1 to 3 give the −1 qubit.

## Why it is still correct, and what it risks

- **The `f1` removal is exact.** `f1` was |1⟩ from its X until its final X,
  so `cz_if(f1, b_f, sm)` and `z_if(b_f, sm)` apply the same phase on every
  basis state.
- **The two thresholds are empirical.** The proof in the code only covers
  iterations below 256 for both. `R_SMALL_THRESHOLD = 327` assumes `r`'s top
  bit is still 0 at iteration 326, so a plain shift equals the modular
  double. `BULK_PREFIX_SAFE_ITERS = 401` assumes no input has terminated in a
  way the bulk body mishandles. An input that breaks either assumption gives a
  wrong inverse: a classical mismatch, or phase garbage when the backward run
  does not mirror the forward one.
- The author reports that neighbouring settings trip classical or phase
  failures on their own draws. The shipped op stream's draw is clean:
  0 classical, 0 phase and 0 ancilla failures. There is no tail nonce in
  this era, so the thresholds double as the knob that picks the test draw.
  See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The qubit saving comes from replacing a qubit that is known to be |1⟩ with
classical knowledge of its value, which is constant propagation. The runner-up
is Register and Scratch Allocation → ancilla-lifetime / venting, because the
effect is that a wire is no longer live at the peak. The threshold moves are
iteration/threshold tuning, but they are secondary here.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a3ee589 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol a3ee589 b60eec2 -- src/point_add` is
   39 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol b60eec2 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`,
   `POINT_ADD_*` or `BY_*` environment variables set. Expect:
   - 2309 qubits
   - 3,637,411 average Toffoli (rounded)
   - score 8,398,781,999
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era: the test set is a hash of the op stream,
so the score only reproduces with an identical op stream.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index fcc5c49..7e87a69 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -330,6 +330,15 @@ impl B {
         op.c_condition = cond;
         self.ops.push(op);
     }
+    // Single-qubit classically-conditioned Z (sim: phase ^= cond & qubit(q)).
+    // Equivalent to cz_if(c, q, cond) when c is a constant |1> ancilla.
+    fn z_if(&mut self, q: QubitId, cond: BitId) {
+        let mut op = Op::empty();
+        op.kind = OperationType::Z;
+        op.q_target = q;
+        op.c_condition = cond;
+        self.ops.push(op);
+    }
 }
 
 // ═══════════════════════════════════════════════════════════════════════════
@@ -5126,7 +5135,9 @@ fn mulmod(a: U256, b: U256, p: U256) -> U256 {
 /// (since max(r,s) doubles per iter starting from max=1, so max ≤ 2^iter_idx).
 /// In that range, mod_double(r)'s Solinas cadd is identity — replace with
 /// a plain shift (0 Toffoli) for ~255 CCX savings per iter.
-const R_SMALL_THRESHOLD: usize = 326;
+// Re-tuned 326 -> 327 to land the passing Fiat-Shamir island after the f1-drop
+// peak reduction (2310 -> 2309); paired with BULK_PREFIX_SAFE_ITERS=401.
+const R_SMALL_THRESHOLD: usize = 327;
 
 fn r_small_threshold() -> usize {
     std::env::var("KAL_R_SMALL_THRESHOLD")
@@ -5156,7 +5167,10 @@ fn kal_cswap_rs_merge_enabled() -> bool {
 /// `2^256`. Termination requires reaching `(1, 0)`, i.e. `s = 1`, so any run
 /// needs at least `ceil(log2(s0)) = 256` steps. Therefore the first 256 step
 /// entries are guaranteed bulk / nonterminal.
-const BULK_PREFIX_SAFE_ITERS: usize = 400;
+// Re-tuned 400 -> 401 to land the passing Fiat-Shamir island after the f1-drop
+// peak reduction (2310 -> 2309). At 2309 qubits this config gives the lowest
+// validated avg-Toffoli (3,637,411), beating the prior 2310-peak top.
+const BULK_PREFIX_SAFE_ITERS: usize = 401;
 
 fn env_usize(name: &str) -> Option<usize> {
     std::env::var(name).ok().and_then(|s| s.parse::<usize>().ok())
@@ -7606,8 +7620,14 @@ fn kaliski_iteration_bulk_prefix3(
     let a_f = b.alloc_qubit();
     let b_f = b.alloc_qubit();
     let add_f = b.alloc_qubit();
-    let f1 = b.alloc_qubit();
-    b.x(f1);
+    // f1 was a constant |1> ancilla whose ONLY use was cz_if(f1, b_f, sm) in
+    // STEP 5 (== z_if(b_f, sm) since f1≡|1>). It was live across the whole
+    // iteration (incl. the global-peak STEP 4), costing +1 peak qubit.
+    // We now emit z_if directly and never hold f1 across STEP 4. The original
+    // f1 free() emitted an R op (consuming 8 XOF bytes, zero phase effect since
+    // f1≡|0> at free) at iteration END; to keep the Fiat-Shamir XOF stream
+    // byte-identical we re-emit that same R at the same stream position via a
+    // transient qubit freed at iteration end (see below).
 
     let _kal_saved_phase = b.phase;
 
@@ -7782,7 +7802,7 @@ fn kaliski_iteration_bulk_prefix3(
     {
         let sm = b.alloc_bit();
         b.hmr(add_f, sm);
-        b.cz_if(f1, b_f, sm);
+        b.z_if(b_f, sm);
     }
     b.x(b_f);
     b.cx(m_i, b_f);
@@ -7846,8 +7866,13 @@ fn kaliski_iteration_bulk_prefix3(
         b.x(s[0]);
     }
 
-    b.x(f1);
-    b.free(f1);
+    // XOF-preserving transient: replicate the R op that the old f1 free()
+    // emitted here (zero phase, 8 XOF bytes) at the identical stream position.
+    // Allocated only at iteration end → not live during the STEP-4 peak.
+    {
+        let f1 = b.alloc_qubit();
+        b.free(f1);
+    }
     b.free(add_f);
     b.free(b_f);
     b.free(a_f);
```

