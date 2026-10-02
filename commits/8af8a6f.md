# 8af8a6f — Narrow the carry-cleanup compare of four coordinate add/subs from 19 to 18 top bits

| | |
| --- | --- |
| Contestant | yudduy |
| Date | 2026-08-01 |
| Submission | `220845c` |
| Commit | `8af8a6fded8ed3037acbb0b45d00339a77d01dc5` |
| Result | 1154 qubits × 1,289,073 Toffoli = **1,487,590,242** |
| Base | `4579b79` (git parent and frontier at the time, the author's `90e90e6`): 1154 qubits × 1,289,081 Toffoli = 1,487,599,474 |
| Change vs base | qubits ±0, Toffoli −8, score −9,232 (leaderboard Δ −9,232) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [modular-fold](../concepts/modular-fold.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below (with its `rm` list) is the whole change |

## Summary

The affine-add shell has five modular add/subtracts of a classical coordinate:
`x − ox` and `y − oy` before the inversion, the `+3x` add, and the final `y`
subtraction and reverse subtraction. Each one ends with an overflow bit
`anc`, which is erased by measuring it out and repairing the phase with a
compare of the top `k` bits. The compare runs only on shots where the
measurement gave 1. This commit makes `k` 18 instead of 19 at four of the five
sites. The final `y` subtraction stays at 19, because narrowing it gave phase
failures.

The circuit saving is small: 60 emitted ops, about 2 executed Toffoli. The
note says that most of the −8 rounded Toffoli comes from the new nonce
drawing a cheaper test set. The commit also deletes most of the
`memory/repro` research scripts that the base had added.

## What changed and why it saves Toffoli

1. **`src/point_add/trailmix_ludicrous/arith.rs`.** Three helpers get a
   `cleanup_bits` parameter. The old entry points become wrappers that pass
   `msbs()`, which is `TLM_MSBS` or `arith::PAD = 19`:
   - `mod_add` → `mod_add_with_cleanup`. The cleanup is
     `controlled_lt_msbs_conditional(y, x, k, anc)`.
   - `mod_sub_vented` → `mod_sub_vented_with_cleanup`. The cleanup is
     `controlled_add_carry_msbs_conditional(y, x, k, anc)`.
   - `mod_rsub_vented_loaded` → `mod_rsub_vented_loaded_with_cleanup`.
2. **What the cleanup does.** `controlled_lt_msbs_conditional` runs
   `hmr(anc, bit)` and frees `anc`. Then, under `push_condition(bit)`, it runs
   a chunked compare of the top `k` bits of the result against the top `k` bits
   of the addend, and applies a Z on the "less than" flag.
   - After `y += x` (and the `+f` fold), the overflow bit equals `[y < x]`. So
     the phase flip cancels the phase that the measurement left.
   - Using only the top `k` bits is the approximation. It is wrong when the two
     agree on all `k` bits and the lower bits would decide, about 2^-k per call.
   - Each bit costs about one Toffoli of compare, executed on about half the
     shots. See [measurement-uncompute](../concepts/measurement-uncompute.md),
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)
     and [modular-fold](../concepts/modular-fold.md).
3. **`src/point_add/trailmix_ludicrous/ec_add.rs`.**
   - New `coord_cleanup_bits(setting)` reads a per-site variable, falls back to
     `TLM_COORD_MSBS`, then to `msbs()`.
   - `coord_addsub` takes the width as an argument. The five sites read
     `TLM_COORD_X_SUB_MSBS`, `TLM_COORD_Y_SUB_MSBS`, `TLM_COORD_ADD3X_MSBS` (on
     the `TLM_COORD_ADD3X_TRUNC=1` path), `TLM_COORD_Y_SUB_FINAL_MSBS` and
     `TLM_COORD_RSUB_MSBS`.
4. **`src/point_add/mod.rs`.**
   - New defaults `TLM_COORD_MSBS = 18` and `TLM_COORD_Y_SUB_FINAL_MSBS = 19`.
     The result is 18 at `x_sub`, `y_sub`, `add3x` and `rsub_final`, and 19 at
     `y_sub_final`.
   - Tail nonce `SUB4_TAIL_NONCE` 60000115034108 → 62000008397024.
5. **Strip.** `deep_strip_keys.rs` is unchanged (the risk-3.0 table). The build
   still reports 12,292 dead removals, 3,923 downgrades and 251 stale keys,
   the same counts as the base.
6. **`src/point_add/memory/`.** 58 files are deleted: most of `repro/`, its
   `__pycache__`, `06-research-status.md`, `CEILING.md`, `RIG.md`,
   `reframe_log.md` and `niche_portfolio.json`. `README.md` goes back to its
   older text. Only `repro/dgm_search.py` and `repro/test_dgm_search.py` remain.
   None of this is compiled.

## Why it is still correct, and what it risks

- **Probabilistic.** Each narrowed compare roughly doubles its own tie rate, to
  about 2^-18 per call. A wrong compare leaves the measurement's phase, which
  shows up as phase garbage.
- **The note's site-by-site test:** narrowing all five sites added a
  phase-garbage batch in a paired 9,024-shot run. The one-site builds did not
  add up linearly (they gave 2, 2, 2, 2 and 3 failing batches), so the author
  built subsets directly. The kept subset leaves `y_sub_final` at 19 and was
  clean in the paired court.
- **Hunt record:** 30M GPU-screened nonces gave 153 hits. 83 passed 512 shots,
  20 passed 2,048, 1 passed 8,192, and that one also passed 9,024.
- The shipped nonce `62000008397024` draws a clean set: 9,024 of 9,024 shots, 0
  classical, 0 phase and 0 ancilla failures, at 1,289,073.125 average Toffoli.
  See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is a narrower truncated compare: comparator/width
truncation. The author says most of the measured gain is nonce luck, so a
nonce reroll is a close runner-up, but the circuit does change.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 4579b79 -- src/point_add`.
   - `data/bases.tsv` lists `7726431`, because it counts the 58 deleted research
     files as diff lines. From `7726431` the patch would also have to rebuild
     d6eed9a's square reroute (245 lines of `square.rs`) and 4579b79's 369
     risk-3.0 keys, none of which is this commit's work.
   - The note names `4579b79` as the starting frontier. It is also the git
     parent, and its code differs from this commit only in the coordinate edit.
   - `git diff --ignore-cr-at-eol 4579b79 8af8a6f -- src/point_add` is 10,093
     lines in 62 files. Almost all of it is the 58 deletions, which the patch
     below lists as an `rm` command.
2. **Delete the 58 files and apply the patch below.** From the repo root, run the
   `rm` command at the top of the patch section, then apply the diff with
   `git apply --ignore-whitespace`. The flag lets the patch apply whether the
   files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol 8af8a6f -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `TLM_*` or
   `SUB4_*` overrides set. Expect:
   - 1154 qubits
   - 1,289,073 average Toffoli (1,289,073.125 before rounding)
   - score 1,487,590,242
   - 0 classical, 0 phase and 0 ancilla failures
5. **Nonce caveat.** The score only reproduces with the nonce `62000008397024` and
   an identical op stream. Any other change needs a new nonce hunt.

### Patch

Delete these files first:

```sh
rm src/point_add/memory/06-research-status.md \
   src/point_add/memory/CEILING.md \
   src/point_add/memory/RIG.md \
   src/point_add/memory/niche_portfolio.json \
   src/point_add/memory/reframe_log.md \
   src/point_add/memory/repro/__pycache__/artifact_io.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/exact_scorer.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/schema_harness.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/test_exact_scorer.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/test_repro_contracts.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/test_schema_harness.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/test_world_model.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/world_model.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y1_composite_synth.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y5_joint_codec_neighborhood.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y5_joint_codec_stochastic.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y5_joint_codec_synth.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y5_joint_codec_triple_fusion.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y5_joint_codec_two_rebase.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y5_normalizer_synth.cpython-313.pyc \
   src/point_add/memory/repro/__pycache__/y5_pair25_quotient.cpython-313.pyc \
   src/point_add/memory/repro/artifact_io.py \
   src/point_add/memory/repro/exact_scorer.py \
   src/point_add/memory/repro/h0_classical_independence.py \
   src/point_add/memory/repro/h0_debug_payload_census.py \
   src/point_add/memory/repro/h0_fixed_point_census.py \
   src/point_add/memory/repro/h0_fixed_point_dynamics.py \
   src/point_add/memory/repro/h0_nonce_fixed_point_census.py \
   src/point_add/memory/repro/h0_permutation_fixed_point_census.py \
   src/point_add/memory/repro/h3_affine_shell_rank.py \
   src/point_add/memory/repro/hyperplane_mitm.cpp \
   src/point_add/memory/repro/schema_harness.py \
   src/point_add/memory/repro/test_exact_scorer.py \
   src/point_add/memory/repro/test_h0_debug_payload_census.py \
   src/point_add/memory/repro/test_h0_fixed_point_census.py \
   src/point_add/memory/repro/test_h0_nonce_fixed_point_census.py \
   src/point_add/memory/repro/test_h0_permutation_fixed_point_census.py \
   src/point_add/memory/repro/test_h3_affine_shell_rank.py \
   src/point_add/memory/repro/test_repro_contracts.py \
   src/point_add/memory/repro/test_schema_harness.py \
   src/point_add/memory/repro/test_verifier_ceiling.py \
   src/point_add/memory/repro/test_world_model.py \
   src/point_add/memory/repro/test_y1_composite_synth.py \
   src/point_add/memory/repro/test_y3_global_codec.py \
   src/point_add/memory/repro/test_y5_normalizer_synth.py \
   src/point_add/memory/repro/verifier_ceiling.py \
   src/point_add/memory/repro/world_model.py \
   src/point_add/memory/repro/y1_composite_synth.py \
   src/point_add/memory/repro/y3_global_codec.py \
   src/point_add/memory/repro/y5_joint_codec_neighborhood.py \
   src/point_add/memory/repro/y5_joint_codec_stochastic.py \
   src/point_add/memory/repro/y5_joint_codec_synth.py \
   src/point_add/memory/repro/y5_joint_codec_triple_fusion.py \
   src/point_add/memory/repro/y5_joint_codec_two_rebase.py \
   src/point_add/memory/repro/y5_normalizer_synth.py \
   src/point_add/memory/repro/y5_pair25_quotient.py \
   src/point_add/memory/repro/y6_source_invariant.py \
   src/point_add/memory/repro/zero_score_lookup.py
```

```diff
diff --git a/src/point_add/memory/README.md b/src/point_add/memory/README.md
index d00e5fc..31ed509 100644
--- a/src/point_add/memory/README.md
+++ b/src/point_add/memory/README.md
@@ -1,7 +1,7 @@
 # Memory
 
-Start with `06-research-status.md` for the current frontier, proved scope, failed approaches, open problems, and exact
-re-entry commands. These notes live under `src/point_add` so they travel with submissions.
+Durable notes for this circuit, mirrored from the repo-root `notes/` folder so they travel with submissions
+(`editablePaths` is `src/point_add` only, so anything outside it is not shipped).
 
 | file | contents |
 |---|---|
@@ -10,9 +10,6 @@ re-entry commands. These notes live under `src/point_add` so they travel with su
 | `03-proven-floors.md` | where the headroom is NOT, with proofs (rank bound, multiplicative complexity, exact codec enumeration) |
 | `04-traps.md` | four ways an env knob silently no-ops, positional addressing, validation gates |
 | `05-qubit-reduction.md` | the measured qubit programme, including the exchange-rate trap |
-| `06-research-status.md` | latest research handoff: certified baseline, scoped results, counterexamples, unresolved work, re-entry conditions |
-| `repro/` | compact tested programs retained to reproduce or extend the durable claims |
-| [`repro/world_model.py`](repro/world_model.py) | executable evidence, invalidation, history-replay, and promotion-gate model |
 
 The single most important operational fact: **a persistent-set reduction only pays if you lower `TLM_TARGET_Q` by the
 same amount**, because the vent pool expands to fill whatever you free. The second most important: **only a
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 97c7b62..b5e21c5 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1192,6 +1192,8 @@ fn configure_q1153_second512_submission_defaults() {
     set_default_env("TLM_COORD_RSUB_FUSED", "1");
     set_default_env("TLM_SQUARE_VENT_MARGIN", "0");
     set_default_env("TLM_COORD_ADD3X_TRUNC", "1");
+    set_default_env("TLM_COORD_MSBS", "18");
+    set_default_env("TLM_COORD_Y_SUB_FINAL_MSBS", "19");
     set_default_env("TLM_SQUARE_VENT_SHIFTED", "1");
     set_default_env("TLM_SQUARE_SHIFTED128_LOW_TAGS", "a,b,c");
     set_default_env("TLM_SQUARE_PEAK_CAP", "1154");
@@ -2376,12 +2378,13 @@ pub fn build() -> Vec<Op> {
     } else {
         apply_deep_strip_identity(ops)
     };
-    // Tail nonce for the exact H2 risk-3.0 stream (9024/9024 PASS, score 1,487,599,474).
-    // SUB4_TAIL_NONCE overrides it for controlled re-grinding.
+    // Tail nonce for the exact H3 coordinate-width-18 stream
+    // (9,024/9,024 PASS, score 1,487,590,242).
+    // SUB4_TAIL_NONCE remains available for controlled re-grinding.
     let nonce: u64 = std::env::var("SUB4_TAIL_NONCE")
         .ok()
         .and_then(|s| s.parse().ok())
-        .unwrap_or(60000115034108);
+        .unwrap_or(62000008397024);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
diff --git a/src/point_add/trailmix_ludicrous/arith.rs b/src/point_add/trailmix_ludicrous/arith.rs
index cca0ce7..9a50d33 100644
--- a/src/point_add/trailmix_ludicrous/arith.rs
+++ b/src/point_add/trailmix_ludicrous/arith.rs
@@ -1576,6 +1576,15 @@ fn add_cout_vented_unctrl(circ: &mut B, x: &[QubitId], y: &[QubitId], cout: &Qub
 }
 
 pub fn mod_rsub_vented_loaded(circ: &mut B, t1: &[QubitId], y: &[QubitId]) {
+    mod_rsub_vented_loaded_with_cleanup(circ, t1, y, msbs());
+}
+
+pub fn mod_rsub_vented_loaded_with_cleanup(
+    circ: &mut B,
+    t1: &[QubitId],
+    y: &[QubitId],
+    cleanup_bits: usize,
+) {
     let n = y.len();
     assert_eq!(t1.len(), n, "mod_rsub_vented_loaded: t1,y must both be n=256 bits");
     assert_eq!(n, 256, "secp256k1 mod_rsub_vented_loaded expects n=256");
@@ -1594,7 +1603,7 @@ pub fn mod_rsub_vented_loaded(circ: &mut B, t1: &[QubitId], y: &[QubitId]) {
         circ.x(*q);
     }
     circ.x(anc);
-    controlled_lt_msbs_conditional(circ, None, &y[..n], &t1[..n], msbs(), anc);
+    controlled_lt_msbs_conditional(circ, None, &y[..n], &t1[..n], cleanup_bits, anc);
 }
 
 fn add_cout_vented_skip_dead(circ: &mut B, x: &[QubitId], y: &[QubitId], cout: &QubitId, call_index: usize) {
@@ -1693,6 +1702,10 @@ fn square_peak_hard_cap() -> usize {
 }
 
 pub fn mod_add(circ: &mut B, x: &[QubitId], y: &[QubitId]) {
+    mod_add_with_cleanup(circ, x, y, msbs());
+}
+
+pub fn mod_add_with_cleanup(circ: &mut B, x: &[QubitId], y: &[QubitId], cleanup_bits: usize) {
     let n = x.len();
     assert_eq!(y.len(), n, "mod_add: x,y must both be n=256 bits");
     assert_eq!(n, 256, "secp256k1 mod_add expects n=256");
@@ -1702,7 +1715,7 @@ pub fn mod_add(circ: &mut B, x: &[QubitId], y: &[QubitId]) {
 
     add_f_window(circ, &anc, y, LSBS, &f_bytes, Some(LSBS - 1));
 
-    controlled_lt_msbs_conditional(circ, None, &y[..n], &x[..n], msbs(), anc);
+    controlled_lt_msbs_conditional(circ, None, &y[..n], &x[..n], cleanup_bits, anc);
 }
 
 pub fn mod_add_exact(circ: &mut B, x: &[QubitId], y: &[QubitId]) {
@@ -1757,6 +1770,15 @@ pub fn mod_add_shifted_low(circ: &mut B, x: &[QubitId], y: &[QubitId], shift: us
 }
 
 pub fn mod_sub_vented(circ: &mut B, x: &[QubitId], y: &[QubitId]) {
+    mod_sub_vented_with_cleanup(circ, x, y, msbs());
+}
+
+pub fn mod_sub_vented_with_cleanup(
+    circ: &mut B,
+    x: &[QubitId],
+    y: &[QubitId],
+    cleanup_bits: usize,
+) {
     let n = x.len();
     assert_eq!(y.len(), n, "mod_sub_vented: x,y must both be n=256 bits");
     assert_eq!(n, 256, "secp256k1 mod_sub_vented expects n=256");
@@ -1777,7 +1799,7 @@ pub fn mod_sub_vented(circ: &mut B, x: &[QubitId], y: &[QubitId]) {
     for q in &y[..LSBS] {
         circ.x(*q);
     }
-    controlled_add_carry_msbs_conditional(circ, None, &y[..n], &x[..n], msbs(), &anc);
+    controlled_add_carry_msbs_conditional(circ, None, &y[..n], &x[..n], cleanup_bits, &anc);
     circ.zero_and_free(anc);
 }
 
diff --git a/src/point_add/trailmix_ludicrous/ec_add.rs b/src/point_add/trailmix_ludicrous/ec_add.rs
index f42f740..12b9027 100644
--- a/src/point_add/trailmix_ludicrous/ec_add.rs
+++ b/src/point_add/trailmix_ludicrous/ec_add.rs
@@ -1,7 +1,7 @@
 
 use super::arith::{
-    mod_add, mod_add_exact, mod_neg, mod_rsub_vented_loaded, mod_sub_classical_low3,
-    mod_sub_shifted_low, mod_sub_vented,
+    mod_add, mod_add_exact, mod_add_with_cleanup, mod_neg, mod_rsub_vented_loaded_with_cleanup,
+    mod_sub_classical_low3, mod_sub_shifted_low, mod_sub_vented, mod_sub_vented_with_cleanup,
 };
 use super::gcd::{mod_mul_inverse_in_place, Direction};
 use super::square::mod_square_sub_pm_secp256k1_symmetric;
@@ -11,7 +11,25 @@ use crate::circuit::{BitId, QubitId};
 
 const N: usize = 256;
 
-fn coord_addsub(circ: &mut B, dst: &[QubitId], coord: &[BitId], subtract: bool) {
+fn coord_cleanup_bits(setting: &str) -> usize {
+    std::env::var(setting)
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .or_else(|| {
+            std::env::var("TLM_COORD_MSBS")
+                .ok()
+                .and_then(|value| value.parse::<usize>().ok())
+        })
+        .unwrap_or_else(super::arith::msbs)
+}
+
+fn coord_addsub(
+    circ: &mut B,
+    dst: &[QubitId],
+    coord: &[BitId],
+    subtract: bool,
+    cleanup_bits: usize,
+) {
     debug_assert_eq!(dst.len(), N);
     debug_assert_eq!(coord.len(), N);
     let split_low3 = subtract
@@ -41,9 +59,9 @@ fn coord_addsub(circ: &mut B, dst: &[QubitId], coord: &[BitId], subtract: bool)
     }
 
     if subtract {
-        mod_sub_vented(circ, &temp, dst);
+        mod_sub_vented_with_cleanup(circ, &temp, dst, cleanup_bits);
     } else {
-        mod_add(circ, &temp, dst);
+        mod_add_with_cleanup(circ, &temp, dst, cleanup_bits);
     }
     for i in 0..N {
         circ.x_if_bit(temp[i], coord[i]);
@@ -65,7 +83,12 @@ fn coord_add3x(circ: &mut B, dst: &[QubitId], coord: &[BitId]) {
     }
 
     if std::env::var("TLM_COORD_ADD3X_TRUNC").ok().as_deref() == Some("1") {
-        mod_add(circ, &temp, dst);
+        mod_add_with_cleanup(
+            circ,
+            &temp,
+            dst,
+            coord_cleanup_bits("TLM_COORD_ADD3X_MSBS"),
+        );
     } else {
         mod_add_exact(circ, &temp, dst);
     }
@@ -238,7 +261,12 @@ fn coord_rsub(circ: &mut B, x: &[QubitId], coord: &[BitId]) {
         for i in 0..N {
             circ.x_if_bit(t[i], coord_p1[i]);
         }
-        mod_rsub_vented_loaded(circ, &t, x);
+        mod_rsub_vented_loaded_with_cleanup(
+            circ,
+            &t,
+            x,
+            coord_cleanup_bits("TLM_COORD_RSUB_MSBS"),
+        );
         for i in 0..N {
             circ.x_if_bit(t[i], coord_p1[i]);
         }
@@ -285,9 +313,21 @@ pub fn ec_add(
     assert_eq!(oy.len(), N, "oy is 256 classical bits");
 
     circ.set_phase("tlm_coord_x_sub");
-    coord_addsub(circ, x2, ox, true);
+    coord_addsub(
+        circ,
+        x2,
+        ox,
+        true,
+        coord_cleanup_bits("TLM_COORD_X_SUB_MSBS"),
+    );
     circ.set_phase("tlm_coord_y_sub");
-    coord_addsub(circ, &y2[..N], oy, true);
+    coord_addsub(
+        circ,
+        &y2[..N],
+        oy,
+        true,
+        coord_cleanup_bits("TLM_COORD_Y_SUB_MSBS"),
+    );
 
     circ.set_phase("tlm_inverse");
     let xv = std::mem::take(x2);
@@ -304,7 +344,13 @@ pub fn ec_add(
     *x2 = mod_mul_inverse_in_place(circ, xv, y2, Direction::Forward);
 
     circ.set_phase("tlm_coord_y_sub_final");
-    coord_addsub(circ, &y2[..N], oy, true);
+    coord_addsub(
+        circ,
+        &y2[..N],
+        oy,
+        true,
+        coord_cleanup_bits("TLM_COORD_Y_SUB_FINAL_MSBS"),
+    );
     circ.set_phase("tlm_coord_rsub_final");
     coord_rsub(circ, x2, ox);
 }
```

