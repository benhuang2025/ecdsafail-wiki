# edeed3f — Narrow the endpoint fold window from 26 to 18, and delete stale backup sources

| | |
| --- | --- |
| Contestant | REgonLevy |
| Date | 2026-08-28 |
| Submission | `b0de3ea` |
| Commit | `edeed3f54e8712b481e58e36a7d0f77ae2708277` |
| Result | 1266 qubits × 903,463 Toffoli = **1,143,784,158** |
| Base | `79e7afa` (odinfree, the smallest diff; the git parent is `db7623e`): 1266 qubits × 906,124 Toffoli = 1,147,152,984 |
| Change vs base | qubits ±0, Toffoli −2,661, score −3,368,826 |
| Leaderboard Δ | −49,374, measured against the frontier at the time, the git parent `db7623e` (1266 × 903,502 = 1,143,833,532), which is **not** the base used here |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [pingpong-division](../concepts/pingpong-division.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change (it is long only because it deletes two backup files) |

## Summary

The ping-pong divider's endpoint steps (the terminal sign fixes, the modular
halve and double, and the round-1 `h` borrow) add the small constant `f`
through short carry chains. Each chain stops a fixed number of bits past
`f`'s top bit and drops any carry that would go further. This commit pins
that window, `SUB4_PP_ENDPOINT_FOLD_WINDOW`, at 18 instead of 26. Each chain
loses 8 positions.

Against the frontier, its git parent `db7623e`, this is the only circuit
change, worth 39 average Toffoli at the same 1266 qubits. The rest of the
commit deletes three stale, uncompiled backup files. Against `79e7afa`, the
base with the smallest diff, the patch also carries the two compare
narrowings of [`52da1ec`](52da1ec.md) and [`db7623e`](db7623e.md) at the same
values, which is why the change vs base is −2,661 Toffoli.

## What changed and why it saves Toffoli

1. **`SUB4_PP_ENDPOINT_FOLD_WINDOW` 26 → 18**, a `set_default_env` pin in
   `build()`, `src/point_add/mod.rs`. This is the new lever.
   - `endpoint_fold_window()` in `pingpong_div.rs` (unchanged) feeds the
     window argument of `cadd_nbit_const_direct_trunc_fast` and its
     subtraction twin. The doc comment there says the chain is
     `min(n − 2, highest_set_bit(c) + window)` positions long.
   - The window is used by `conditional_mod_negate` (the terminal sign fix of
     each coefficient register), `signed_mod_add_pm`, `mod_halve_pm`,
     `mod_double_pm`, the signed-frame converters (off in this build), and
     `round1_window`, which sizes the round-1 `h` borrow as `32 + window`.
   - Each live call loses 8 chain positions. A position costs about one
     Toffoli, since the chain's AND wires are measurement-uncomputed. These
     calls run a few times per traversal, not per round, so the total is
     small: −39 against the parent. See
     [modular-fold](../concepts/modular-fold.md), section "Endpoint folds".
2. **Carried over, not new.** `SUB4_PP_REPLAY_FLAG_COMPARE` 22 → 20 and
   `SUB4_PP_REPLAY_CHUNK_COMPARE` 22 → 21. These are the values of the git
   parent: they came in with [`52da1ec`](52da1ec.md) and
   [`db7623e`](db7623e.md). They appear in the patch only because the base
   is `79e7afa`. They supply the other −2,622 Toffoli of the change vs base.
3. **Tail nonce:** `SUB4_PINGPONG_TAIL_NONCE` default → 6003138460055 (the
   parent's was 75787140768792).
4. **Housekeeping, no circuit effect.** None of these files are part of the
   module tree.
   - Deletes `src/point_add/pingpong_div.rs.pre_ts` (2,337 lines) and
     `pingpong_div.rs.rrm` (2,326 lines): old snapshots of the divider that
     came in with mochimodev's [`b523ecf`](b523ecf.md).
   - Deletes `mod.rs.pre_live`, an old snapshot of `mod.rs`.
   - Keeps `mod.rs.bak`, the copy of `79e7afa`'s `mod.rs` that `52da1ec`
     added. Against `79e7afa`, git shows these last two together as a rename
     `mod.rs.pre_live → mod.rs.bak` with 65 changed lines.

## Why it is still correct, and what it risks

- **Probabilistic.** A dropped carry gives a register that is off by a power
  of two, which is a wrong field element and a classical failure. Over
  random data, a carry runs more than `window` bits past `f`'s top with
  probability about 2^-window. So each call now fails at about 2^-18 instead
  of 2^-26. With only a handful of calls per shot, this adds little λ.
- The two carried-over compare narrowings are phase-channel truncations; see
  their own notes.
- The shipped nonce draws a clean set: 0 classical, 0 phase and 0 ancilla
  failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- odinfree adopted the same 18-bit window a few hours later in
  [`716e359`](716e359.md).

## Classification rationale

The only new circuit change narrows a constant-fold carry window. That is
fold/carry truncation. The file deletions have no circuit effect.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 79e7afa -- src/point_add`.
   - `79e7afa` gives the smallest diff:
     `git diff --ignore-cr-at-eol 79e7afa edeed3f -- src/point_add` is 4,736
     lines in 4 files, almost all of it the two deleted divider snapshots.
   - The git parent `db7623e` has the same circuit apart from the window.
     Diffing against it is 10,228 lines, because the parent still holds all
     three snapshot files, including the 5,561-line `mod.rs.pre_live`. The
     circuit part of that diff is only the window and the nonce.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base. Most of it deletes
   `pingpong_div.rs.pre_ts` and `pingpong_div.rs.rrm`.
3. **Check the tree.** `git diff --ignore-cr-at-eol edeed3f -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1266 qubits
   - 903,463 average Toffoli (rounded)
   - score 1,143,784,158
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `6003138460055` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

Delete these files first:

```sh
rm src/point_add/pingpong_div.rs.pre_ts \
   src/point_add/pingpong_div.rs.rrm
```

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index c6a4ec4..b8c60f6 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2493,16 +2493,16 @@ pub fn build() -> Vec<Op> {
     set_default_env("SUB4_PP_PEAK", "1268");
     set_default_env("SUB4_PP_WALK_PEAK", "1267");
     set_default_env("SUB4_PP_REPLAY_CHUNK", "96");
-    set_default_env("SUB4_PP_REPLAY_CHUNK_COMPARE", "22");
+    set_default_env("SUB4_PP_REPLAY_CHUNK_COMPARE", "21");
     set_default_env("SUB4_PP_REPLAY_FOLD_WINDOW", "54");
     set_default_env("SUB4_PP_REPLAY_FOLD_WINDOW_MUL", "53");
-    set_default_env("SUB4_PP_ENDPOINT_FOLD_WINDOW", "26");
+    set_default_env("SUB4_PP_ENDPOINT_FOLD_WINDOW", "18");
     // MERGE: the level-2 Karatsuba square (ours) needs 6 more live wires in
     // the replay cell than the canonical-residue frame does, and those 6 wires
     // are exactly what pins the peak at 1273. Canonical residues cost ~628 T
     // and buy the peak down to 1267 -- 105 T/wire against a ~716 break-even.
     set_default_env("SUB4_PP_SIGNED_FRAME", "0");
-    set_default_env("SUB4_PP_REPLAY_FLAG_COMPARE", "22");
+    set_default_env("SUB4_PP_REPLAY_FLAG_COMPARE", "20");
     set_default_env("SUB4_SQUARE_CHUNK_MIN", "18446744073709551615");
     set_default_env("SUB4_SQUARE_LADDER", "243");
 
@@ -2602,7 +2602,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(41032007408473);
+            .unwrap_or(6003138460055);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/mod.rs.pre_live b/src/point_add/mod.rs.bak
similarity index 97%
rename from src/point_add/mod.rs.pre_live
rename to src/point_add/mod.rs.bak
index 2e4998a..c6a4ec4 100644
--- a/src/point_add/mod.rs.pre_live
+++ b/src/point_add/mod.rs.bak
@@ -501,6 +501,12 @@ impl B {
     }
     fn free(&mut self, q: QubitId) {
         self.r(q);
+        self.release_clean(q);
+    }
+    /// Return a qubit that the caller has unitarily restored to |0> without
+    /// emitting a reset. This preserves the measurement stream when a clean
+    /// temporary is parked and reused inside one reversible cell.
+    fn release_clean(&mut self, q: QubitId) {
         self.free_qubits
             .push(q.0.try_into().expect("qubit id fits in u32"));
         if self.active_qubits > 0 {
@@ -2237,6 +2243,12 @@ fn ccz_self_inverse_cancel_conservative(ops: Vec<Op>) -> Vec<Op> {
 }
 
 pub fn build() -> Vec<Op> {
+    // Diagnostic: dump the width schedule (base + rescaled) and exit without
+    // emitting.  Byte-neutral to the shipped stream (gated, default-off).
+    if std::env::var_os("SUB4_DUMP_WSCHED").is_some() {
+        pingpong_div::dump_width_schedule();
+        return Vec::new();
+    }
     // Reproduce the exact source parent used by the q1150 route.  These are
     // intentionally forced instead of defaults so the benchmark environment
     // cannot select a different geometry.
@@ -2445,6 +2457,55 @@ pub fn build() -> Vec<Op> {
     set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "");
     set_default_env("TLM_SQUARE_F_SHIFTED_LOW", "1");
 
+    // Freeze the Q1267 fallback composition while keeping each knob
+    // externally overridable for focused reliability experiments. The
+    // pingpong tail nonce intentionally remains at the frontier fallback.
+    // SW-1: TLM_FFG_MAX_G is clamped to 47 by
+    // configure_q1153_second512_submission_defaults(), which belongs to the
+    // RETIRED Q1153 route. It still governs all 14 live add_f_window folds on
+    // this path, where the clamp is not needed: 55 is the width limit and any
+    // value >= 55 is bit-identical. Lifting it converts all 14 to the clean
+    // ladder. Measured -45.566 executed Toffoli, paired over 8 frozen seeds;
+    // lambda_c delta 0 by bit-identical frozen failure sets 8/8; peak unchanged.
+    // Set here, in the promoted route's own block, rather than by editing the
+    // retired installer.
+    std::env::set_var("TLM_FFG_MAX_G", "55");
+    set_default_env("SUB4_PINGPONG_LOW56_FOLD", "1");
+    set_default_env("SUB4_PP_ROUNDS", "696");
+    // Keep one additional multiply traversal round as a bounded reliability
+    // purchase. The extra tape wire raises this composition from Q1267 to
+    // Q1268 while retaining a projected score improvement above 0.1%.
+    set_default_env("SUB4_PP_ROUNDS_MUL", "694");
+    set_default_env("SUB4_PP_R1", "335");
+    // R1MUL-326: multiply-side round-1 split point. The response curve is JAGGED, not
+    // monotone (324 -> -189 CCX, 325 -> +113, 326 -> -231, 327 -> +74), so this is a discrete
+    // schedule boundary and a true local minimum rather than a failure-budget purchase.
+    // -231 CCX deterministic on every seed; peak unchanged. Measured lambda-free.
+    set_default_env("SUB4_PP_R1_MUL", "326");
+    set_default_env("SUB4_PP_R2", "645");
+    // PP-1268: raise the ping-pong peak governor by one. At the SHIPPED ROUNDS=696 the
+    // realized peak floor is max(ROUNDS, ROUNDS_MUL) + 570 = 1266, and the ladder quantizes so
+    // that PEAK=1268 does NOT move the realized peak (1269 does; so does 1268 with WALK=1268).
+    // The extra unit of allowance lets the headroom-scheduled primitives take a cheaper
+    // ladder: -952 CCX deterministic, peak unchanged at 1266. Previously retracted as a dead
+    // end when the shipped config was ROUNDS=694, where PEAK=1268 realizes peak 1268 and costs
+    // two qubits; restoring ROUNDS to 696 revived it.
+    set_default_env("SUB4_PP_PEAK", "1268");
+    set_default_env("SUB4_PP_WALK_PEAK", "1267");
+    set_default_env("SUB4_PP_REPLAY_CHUNK", "96");
+    set_default_env("SUB4_PP_REPLAY_CHUNK_COMPARE", "22");
+    set_default_env("SUB4_PP_REPLAY_FOLD_WINDOW", "54");
+    set_default_env("SUB4_PP_REPLAY_FOLD_WINDOW_MUL", "53");
+    set_default_env("SUB4_PP_ENDPOINT_FOLD_WINDOW", "26");
+    // MERGE: the level-2 Karatsuba square (ours) needs 6 more live wires in
+    // the replay cell than the canonical-residue frame does, and those 6 wires
+    // are exactly what pins the peak at 1273. Canonical residues cost ~628 T
+    // and buy the peak down to 1267 -- 105 T/wire against a ~716 break-even.
+    set_default_env("SUB4_PP_SIGNED_FRAME", "0");
+    set_default_env("SUB4_PP_REPLAY_FLAG_COMPARE", "22");
+    set_default_env("SUB4_SQUARE_CHUNK_MIN", "18446744073709551615");
+    set_default_env("SUB4_SQUARE_LADDER", "243");
+
     set_default_env("TLM_GRAD_FINAL_NO_COUT", "1");
     set_default_env("TLM_APPLY_FWD_FIRST_CSWAP_SKIP", "1");
     set_default_env("CONSTPROP_MAX_ITERS", "16");
@@ -2536,10 +2597,12 @@ pub fn build() -> Vec<Op> {
             return Vec::new();
         }
         let mut ops = pingpong_div::build_pingpong_point_add();
+        // Exact-clean nonce for the Q1267/M697 stream, verified by the optimized
+        // and reference evaluators over all 9,024 shots.
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(5101174221);
+            .unwrap_or(41032007408473);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
```

