# afcc72e — Narrow the GCD width and compare tables by one bit on 54 tail steps and lower both qubit caps to 1153 (1154 → 1153 qubits)

| | |
| --- | --- |
| Contestant | odinfree (co-author tag: welttowelt) |
| Date | 2026-08-18 |
| Submission | `cb4540c` |
| Commit | `afcc72ef9dce8cec98f2310fd3ca27d0dd021f2e` |
| Result | 1153 qubits × 1,284,345 Toffoli = **1,480,849,785** |
| Base | `f735fd7` (the author's previous submission): 1154 qubits × 1,283,487 Toffoli = 1,481,143,998 |
| Change vs base | qubits −1, Toffoli +858, score −294,213 |
| Leaderboard Δ | −241,129, measured against the frontier at the time, `ebdbaac` (1154 × 1,283,441 = 1,481,090,914), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the re-mined strip-key table is copied from the commit; the patch covers the rest |

## Summary

In the trailmix route the qubit peak is a short spike during the apply-pass
folds, where the nearly full GCD tape, both 256-bit payload registers, the
narrow `u`/`v` walk registers and a few carries are all live. Most scratch in
the build is sized against a cap, `TLM_TARGET_Q`. A memory note in the tree
(`memory/05-qubit-reduction.md`) found two things. Narrowing the walk
registers alone does not lower the peak, because the vent pool grows to fill
the freed wires. Lowering the cap alone costs about 2.6k Toffoli of adder work per qubit,
plus strip keys that go stale.
Doing both together improves both factors.

This commit does both. It narrows the per-step `u`/`v` width table
`SCHED_J2`, and the comparator window table `GAP_J2` with it, by one bit on
54 of the last 60 GCD steps. It lowers `TLM_TARGET_Q` and
`TLM_SQUARE_PEAK_CAP` from 1154 to 1153. The peak drops to 1153 qubits.
Bundled in are an exact measured-uncompute carry in the square (−127 T), both
exact affine bridges, a re-measured cascade allow-list and a freshly mined
strip table. Net Toffoli rises by 858, but the score falls, because one qubit
is worth about 1,113 Toffoli here (1,283,487 / 1153).

## What changed and why it saves qubits

### 1. Narrower tail widths (`src/point_add/trailmix_ludicrous/schedule.rs`)

- `SCHED_J2[i]` is the live width of `u` and `v` at GCD step `i`.
  `GAP_J2[i]` is the comparator window for the `v < u` decision at that
  step. Both have 261 entries (`ITERS = 261`).
- Both tables drop by exactly 1 at steps **201–237** and **244–260**, 54
  entries each. Steps 238–243 are left alone. Example: the last four
  `SCHED_J2` entries go 9, 9, 9, 9 → 8, 8, 8, 8, and the last four `GAP_J2`
  entries go 10, 10, 10, 10 → 9, 9, 9, 9.
- The two tables move together on purpose. The memory note reports that the
  error depends on the difference `SCHED_J2[i] − cmp_window(i)`, and that
  moving one table without the other took the divstep failure channel from
  8.36 to 4,646 mismatches.
- Narrower registers make every walk add, compare and cswap at those steps
  cheaper, and they free wires during the tail, where the peak spike is. See
  [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) and
  [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).

### 2. Lower caps (`src/point_add/mod.rs`, `configure_q1153_second512_submission_defaults`)

- `TLM_TARGET_Q`: "1154" → "1153". `target_qubit_headroom()` in
  `trailmix_ludicrous/mod.rs` returns `TLM_TARGET_Q − active_qubits`, and
  the vented adders and folds size their extra carry ancillas to that
  headroom.
- `TLM_SQUARE_PEAK_CAP`: "1154" → "1153". `square_peak_hard_cap()` in
  `arith.rs` reads it, and the square plans its scratch against it.
- This function runs first in `build()`, so its `set_default_env` values
  win. The later `set_default_env("TLM_TARGET_Q", "1155")` has no effect.
- The caps are what turn the freed tail wires into a lower peak. Without them
  the vent pool absorbs the freed wires. Every budgeted region now has one
  qubit less to work with, which costs Toffoli. See
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md) and
  [venting-and-wire-loans](../concepts/venting-and-wire-loans.md).

### 3. Exact vented square-sum carry (`trailmix_ludicrous/arith.rs`, `square.rs`)

- New `arith::cuccaro_carry_vented(circ, x, y, cout)`. It reserves one
  Cuccaro call index, so tables keyed on Cuccaro call counts stay aligned,
  and then calls `clean_add_threaded_opt`.
- That adder computes each carry into its own fresh ancilla with one CCX.
  The carries are erased with `hmr` plus a classically conditioned CZ
  instead of the Cuccaro UMA recompute. See
  [measurement-uncompute](../concepts/measurement-uncompute.md).
- `square.rs::build_sum_hi_lo` now uses it for the 128-bit
  `lambda_hi + lambda_lo` sum, unless `TLM_SQUARE_SUM_VENTED=0`. The comment
  gives −128 emitted CCX, or −127 after a fanout rewrite gives one back.
- It holds 128 extra ancillas during that add, which is not where the peak
  spike is.

### 4. Both exact affine bridges, before the strip (`mod.rs`)

- New `apply_exact_affine_bridges(ops)` contains bridge 1 (7→3) from
  [`9aceb7d`](9aceb7d.md) and bridge 2 (14→13, control-delta) from
  [`9b2ce61`](9b2ce61.md). Each asserts a unique match. Together they are
  −2 T per shot. `TLM_EXACT_AFFINE_BRIDGES=0` turns them off.
- They now run *before* `apply_deep_strip_identity`. The comment explains
  why: the census (strip off) and the shipped build (strip on) then see the
  same pre-strip stream, so no identity key goes stale.

### 5. Re-measured cascade roots (`trailmix_ludicrous/constprop.rs`)

`DEFAULT_CASCADE_TRIPLES` is replaced with 11 new triples for the new
geometry: `(8,527,528)`, `(271,272,889)`, `(271,272,1133)`,
`(272,273,1145)`, `(273,274,1087)`, `(273,274,1133)`, `(274,275,888)`,
`(274,275,915)`, `(274,275,1145)`, `(530,531,1148)`, `(530,531,1152)`. The
per-root fire table in the doc comment is deleted. The mechanism is
[`f735fd7`](f735fd7.md)'s.

### 6. Re-mined strip table (`src/point_add/deep_strip_keys.rs`, copied)

The narrower walk and the new cap change the op stream, so the old keys'
tuple occupancies no longer match and most would be discarded as stale. The
table is replaced by a fresh census of this stream: 10,951 `DEAD_KEYS` and
3,168 `DOWNGRADE_KEYS`, 14,119 in all, against 12,202 + 4,045 = 16,247
before. The header is just "Identity-keyed deep-strip table" and records no
census size or risk budget. See [dead-gate-strip](../concepts/dead-gate-strip.md).

### 7. Tail nonce

`SUB4_TAIL_NONCE` default 1337610097 → 865024934. The comment records the
result: avg 1,284,344.872 × 1153.

**Net.** The narrower tail saves Toffoli and frees the tail wires. The lower
caps cost Toffoli in every budgeted adder. The square vent, the bridges, the
cascade and the strip claw some back. The total is +858 T for −1 qubit, a
score change of −294,213. The commit does not record the pieces separately.

## Why it is still correct, and what it risks

- **The narrower widths and windows are probabilistic.** On an input whose
  `u`/`v` values are still wider than the scheduled width at some tail step,
  a freed wire is not |0⟩. On an input where the narrower comparator
  mis-orders `u` and `v`, the walk takes the wrong branch. Either gives a
  wrong result or garbage, so it shows as a classical or ancilla failure.
  This raises λ. The skipped steps 238–243 are the band where narrowing
  costs most.
- **The cap change is exact.** It changes which layout each adder picks, not
  what it computes.
- **The square vent and both bridges are exact.**
- **The cascade roots and strip keys are empirical.** Each is priced as a
  small λ.
- The shipped nonce `865024934` draws a clean test set: 9,024 of 9,024
  shots, with 0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The qubit drop, which is what pays, is made possible by narrowing the
`SCHED_J2`/`GAP_J2` envelope where the peak binds, so the commit is filed as
comparator/width truncation. The runner-up is ancilla-lifetime / venting,
because the caps are moved at the same time. That move only pays together
with the narrowing. The square-sum vent (measurement uncompute) and the
strip and cascade re-mining are secondary.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f735fd7 -- src/point_add`.
   - `git diff --ignore-cr-at-eol f735fd7 afcc72e -- src/point_add` is
     16,046 changed lines in 6 files, 15,863 of them the strip table.
   - The git parent `ebdbaac` gives a slightly larger diff, 16,070 lines.
     Against it, the patch would also have to remove jackylee0424's
     `apply_exact_affine_bridge` helper and 12th cascade root, which this
     commit replaces with its own versions.
2. **Copy the generated strip table from the commit:**
   `git checkout afcc72e -- src/point_add/deep_strip_keys.rs`. It is
   census-mined data; part 6 above describes it.
3. **Apply the patch below** from the repo root with
   `git apply --ignore-whitespace`. The flag lets the patch apply whether the
   files use LF or CRLF line endings. It covers `mod.rs`, `arith.rs`,
   `constprop.rs`, `schedule.rs` and `square.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol afcc72e -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   or `TLM_*` overrides set. Expect:
   - 1153 qubits
   - 1,284,345 average Toffoli (1,284,344.872 before rounding)
   - score 1,480,849,785
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `865024934` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6b5bd19..c648cda 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1178,7 +1178,7 @@ const Q1153_SECOND512_SUBMISSION_NONCE: &str = "193806910775884";
 
 fn configure_q1153_second512_submission_defaults() {
     set_default_env("DIALOG_TAIL_NONCE", Q1153_SECOND512_SUBMISSION_NONCE);
-    set_default_env("TLM_TARGET_Q", "1154");
+    set_default_env("TLM_TARGET_Q", "1153");
     set_default_env("TLM_FOLD_CHUNK_ZERO_CIN", "1");
     set_default_env("TLM_FFG_MAX_G", "47");
     set_default_env("TLM_APPLY_ADD_SKIP_LASTK", "1");
@@ -1194,7 +1194,7 @@ fn configure_q1153_second512_submission_defaults() {
     set_default_env("TLM_COORD_ADD3X_TRUNC", "1");
     set_default_env("TLM_SQUARE_VENT_SHIFTED", "1");
     set_default_env("TLM_SQUARE_SHIFTED128_LOW_TAGS", "a,b,c");
-    set_default_env("TLM_SQUARE_PEAK_CAP", "1154");
+    set_default_env("TLM_SQUARE_PEAK_CAP", "1153");
     set_default_env("TLM_CUCCARO_SKIP_STRUCTURAL_DEAD_CALLS", "1");
 }
 
@@ -1784,6 +1784,97 @@ fn apply_deep_strip_identity(ops: Vec<Op>) -> Vec<Op> {
     out
 }
 
+
+/// Exact affine bridges (see call site). Bridge 1: the seven-gate source and three-gate
+/// replacement both apply q897 ^= q734 ^ q735 ^ (q511 & q898) and restore every other wire
+/// (exhaustive 32-state check in note 6bb669e). Bridge 2: with a=513,b=565,d=512,t=566 and
+/// the unchanged enclosing condition C, the intervening Clifford block has net action
+/// b ^= C*d while d is restored, so the equal endpoint CCX pair reduces to CCX(a,d -> t)
+/// after the retained block. Both windows must occur exactly once (outside the tail).
+fn apply_exact_affine_bridges(mut ops: Vec<Op>) -> Vec<Op> {
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
+    let affine_source = [
+        ccx(511, 898, 735),
+        cx(735, 897),
+        cx(735, 734),
+        cx(735, 897),
+        cx(734, 897),
+        cx(735, 734),
+        ccx(511, 898, 735),
+    ];
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
+    let affine_delta_source = [
+        ccx(513, 565, 566),
+        cx(0, 565),
+        cx(0, 569),
+        cx(0, 571),
+        cx(0, 572),
+        cx(0, 573),
+        cx(0, 574),
+        cx(0, 597),
+        cx(0, 768),
+        cx(0, 512),
+        cx(512, 565),
+        cx(0, 768),
+        cx(0, 512),
+        ccx(513, 565, 566),
+    ];
+    let delta_matches: Vec<usize> = ops
+        .windows(affine_delta_source.len())
+        .enumerate()
+        .filter_map(|(index, window)| (window == affine_delta_source.as_slice()).then_some(index))
+        .collect();
+    assert_eq!(delta_matches.len(), 1, "exact affine control-delta bridge occurrence drift");
+    let delta_index = delta_matches[0];
+    assert!(delta_index + affine_delta_source.len() <= ops.len() - 96);
+    ops.splice(
+        delta_index..delta_index + affine_delta_source.len(),
+        [
+            cx(0, 565),
+            cx(0, 569),
+            cx(0, 571),
+            cx(0, 572),
+            cx(0, 573),
+            cx(0, 574),
+            cx(0, 597),
+            cx(0, 768),
+            cx(0, 512),
+            cx(512, 565),
+            cx(0, 768),
+            cx(0, 512),
+            ccx(513, 512, 566),
+        ],
+    );
+    eprintln!("[affine-bridges] bridge1 at {} (7->3), bridge2 at {} (14->13)", affine_index, delta_index);
+    ops
+}
+
 /// Rewrite the 96-op identity tail to encode the ground nonce. Only q_target
 /// changes (X;X pairs stay identities), so circuit function is untouched; the
 /// Fiat-Shamir seed is what moves.
@@ -2371,6 +2462,16 @@ pub fn build() -> Vec<Op> {
     // census-time tuple occupancy, a self-check strictly stronger than gating on
     // baked_artifacts_valid(): it catches ANY ordinal-moving edit and discards only
     // the affected keys, loudly, instead of disabling the table.
+    // Two exact affine bridges (swadhin, 9b2ce61; recovered from 9aceb7d), applied
+    // BEFORE the deep strip so the census (strip-off) and ship (strip-on) streams share
+    // the same pre-strip geometry -> identity-keyed table stays at 0 stale keys.
+    // Each requires exactly one window witness and fails closed on drift.
+    // Default ON; TLM_EXACT_AFFINE_BRIDGES=0 disables (A/B only).
+    let ops = if std::env::var("TLM_EXACT_AFFINE_BRIDGES").ok().as_deref() == Some("0") {
+        ops
+    } else {
+        apply_exact_affine_bridges(ops)
+    };
     let strip_enabled = std::env::var("SUB4_APPLY_STRIP").ok().as_deref() != Some("0");
     let mut ops = if !strip_enabled {
         ops
@@ -2397,8 +2498,8 @@ pub fn build() -> Vec<Op> {
             }
         }
     }
-    // Tail nonce for this geometry (9024/9024 PASS, avg 1283787.015 x 1154 qubits,
-    // score 1,481,490,198). Dispositioned by trusted CPU oracle 0/0/0 over 9,024 shots.
+    // Tail nonce for this geometry (9024/9024 PASS, avg 1284344.872 x 1153 qubits,
+    // score 1,480,849,785). Dispositioned by trusted CPU oracle 0/0/0 over 9,024 shots.
     // SUB4_TAIL_NONCE overrides it for controlled re-grinding.
     //
     // This literal is a Fiat-Shamir *search parameter*, not a secret or a credential. Test
@@ -2410,7 +2511,7 @@ pub fn build() -> Vec<Op> {
     let nonce: u64 = std::env::var("SUB4_TAIL_NONCE")
         .ok()
         .and_then(|s| s.parse().ok())
-        .unwrap_or(1337610097);
+        .unwrap_or(865024934);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
diff --git a/src/point_add/trailmix_ludicrous/arith.rs b/src/point_add/trailmix_ludicrous/arith.rs
index cca0ce7..b0ce887 100644
--- a/src/point_add/trailmix_ludicrous/arith.rs
+++ b/src/point_add/trailmix_ludicrous/arith.rs
@@ -469,6 +469,16 @@ fn cbit(c: &[u8], i: usize) -> bool {
     byte < c.len() && (c[byte] >> (i % 8)) & 1 == 1
 }
 
+/// Vented Cuccaro carry (moscowchill note 6bb669e, ported per shabbydev note 1f2731d):
+/// forward carries threaded through fresh clean ancillas, each measurement-uncomputed
+/// with HMR + classically conditioned CZ (the standard exact identity: sum bits,
+/// carry-out, phase and cleared ancillas unchanged). Reserves one Cuccaro call index
+/// so downstream dead-carry tables stay aligned.
+pub fn cuccaro_carry_vented(circ: &mut B, x: &[QubitId], y: &[QubitId], cout: Option<&QubitId>) {
+    let _reserved_call_index = next_cuccaro_call_index();
+    clean_add_threaded_opt(circ, None, x, y, None, cout);
+}
+
 pub fn cuccaro_carry(
     circ: &mut B,
     ctrl: Option<&QubitId>,
diff --git a/src/point_add/trailmix_ludicrous/constprop.rs b/src/point_add/trailmix_ludicrous/constprop.rs
index 7d96b81..7686b50 100644
--- a/src/point_add/trailmix_ludicrous/constprop.rs
+++ b/src/point_add/trailmix_ludicrous/constprop.rs
@@ -593,47 +593,25 @@ fn control_net_restored(
 
 /// Cascade-root residual triples, each measured over 10,485,760 real shots.
 ///
+/// Cascade-root residual triples, validated by large-sample measurement.
+///
 /// A cascade root is a blocked self-inverse CCX pair whose single intervening
 /// write is one unconditional CCX; cancelling it leaves `t ^= s AND c AND d`.
 /// The pair is therefore removable only to the extent that triple never fires,
 /// so each entry below is an explicit error-rate trade, not a value-exact
-/// rewrite. Measured fire counts per 10,485,760 shots (expected mismatches per
-/// 9,024-shot run in brackets):
-///
-///   9:270:271      4  [0.0034]      143:273:274    7  [0.0060]
-///   274:275:1147   7  [0.0060]      143:271:272   13  [0.0112]
-///   530:531:1132  22  [0.0189]      274:275:1088  27  [0.0232]
-///   530:531:1150  46  [0.0396]      274:275:889   97  [0.0835]
-///   273:274:915  103  [0.0886]      530:531:1149 111  [0.0955]
-///   271:272:886  134  [0.1153]
-///
-/// Total added lambda 0.4912 (grind cost x1.63). Three further roots were
-/// measured and deliberately EXCLUDED as lambda-inefficient: 526:527:1150
-/// (428 fires, 0.3683 — 31% of the available lambda for 8% of the gain),
-/// 10:526:527 (241, 0.2074) and 529:530:1152 (151, 0.1299). The gap is clean:
-/// every retained root returns >=272 removed ops per unit lambda, every
-/// excluded one <=216.
-///
-/// A 1M-shot pass is NOT enough to rank these: it reported 274:275:1147 as
-/// zero-fire and mis-ordered several neighbours. Re-measure at >=10M before
-/// trusting any change to this table.
-///
-/// Removing these 11 roots unblocks 144 further pairs that the EXACT predicate
-/// then accepts on its own (inverse_pairs 1 -> 155, constprop iters 3 -> 16),
-/// so the risk surface is these 11 triples only. Net effect measured paired on
-/// identical inputs: exactly -308.000 average executed Toffoli.
+/// rewrite. Mechanism credit: Echo-Merlini, public note cd0a483.
 const DEFAULT_CASCADE_TRIPLES: &[(u64, u64, u64)] = &[
-    (9, 270, 271),
-    (143, 271, 272),
-    (143, 273, 274),
-    (271, 272, 886),
-    (273, 274, 915),
-    (274, 275, 889),
-    (274, 275, 1088),
-    (274, 275, 1147),
-    (530, 531, 1132),
-    (530, 531, 1149),
-    (530, 531, 1150),
+    (8, 527, 528),
+    (271, 272, 889),
+    (271, 272, 1133),
+    (272, 273, 1145),
+    (273, 274, 1087),
+    (273, 274, 1133),
+    (274, 275, 888),
+    (274, 275, 915),
+    (274, 275, 1145),
+    (530, 531, 1148),
+    (530, 531, 1152),
 ];
 
 fn find_inverse_pairs(
diff --git a/src/point_add/trailmix_ludicrous/schedule.rs b/src/point_add/trailmix_ludicrous/schedule.rs
index c6c57d0..dc998cf 100644
--- a/src/point_add/trailmix_ludicrous/schedule.rs
+++ b/src/point_add/trailmix_ludicrous/schedule.rs
@@ -18,9 +18,9 @@ pub fn baked_artifacts_valid() -> bool {
 
 pub const PAD: usize = 20;
 
-pub static SCHED_J2: &[u16] = &[256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 255, 254, 253, 252, 251, 250, 249, 248, 247, 246, 245, 244, 243, 242, 241, 240, 239, 238, 237, 236, 235, 234, 233, 232, 231, 230, 229, 228, 227, 226, 225, 224, 223, 222, 221, 220, 219, 218, 217, 216, 215, 214, 213, 212, 211, 210, 209, 208, 207, 206, 205, 204, 203, 202, 201, 200, 199, 198, 197, 196, 195, 194, 193, 192, 191, 190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180, 179, 178, 177, 176, 175, 174, 173, 173, 172, 170, 169, 168, 167, 166, 164, 162, 162, 161, 160, 158, 158, 157, 155, 155, 154, 153, 152, 151, 150, 149, 147, 146, 145, 144, 143, 143, 142, 141, 139, 139, 138, 137, 136, 135, 134, 133, 132, 131, 129, 128, 127, 126, 125, 124, 124, 123, 122, 120, 120, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 24, 23, 22, 21, 20, 19, 19, 18, 18, 17, 16, 15, 15, 14, 14, 14, 12, 12, 10, 9, 9, 9, 9];
+pub static SCHED_J2: &[u16] = &[256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 255, 254, 253, 252, 251, 250, 249, 248, 247, 246, 245, 244, 243, 242, 241, 240, 239, 238, 237, 236, 235, 234, 233, 232, 231, 230, 229, 228, 227, 226, 225, 224, 223, 222, 221, 220, 219, 218, 217, 216, 215, 214, 213, 212, 211, 210, 209, 208, 207, 206, 205, 204, 203, 202, 201, 200, 199, 198, 197, 196, 195, 194, 193, 192, 191, 190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180, 179, 178, 177, 176, 175, 174, 173, 173, 172, 170, 169, 168, 167, 166, 164, 162, 162, 161, 160, 158, 158, 157, 155, 155, 154, 153, 152, 151, 150, 149, 147, 146, 145, 144, 143, 143, 142, 141, 139, 139, 138, 137, 136, 135, 134, 133, 132, 131, 129, 128, 127, 126, 125, 124, 124, 123, 122, 120, 120, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 67, 66, 65, 64, 62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 24, 23, 22, 21, 20, 19, 18, 17, 17, 16, 15, 14, 14, 13, 13, 13, 11, 11, 9, 8, 8, 8, 8];
 
-pub static GAP_J2: &[u16] = &[23, 25, 25, 26, 27, 29, 29, 30, 32, 32, 34, 34, 34, 34, 34, 34, 35, 35, 34, 35, 35, 35, 34, 36, 36, 35, 35, 36, 35, 35, 37, 35, 36, 36, 36, 36, 37, 36, 37, 37, 37, 36, 37, 37, 37, 37, 38, 37, 38, 37, 38, 38, 38, 38, 38, 38, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 40, 40, 40, 40, 40, 40, 41, 41, 42, 41, 40, 41, 41, 42, 42, 43, 41, 41, 42, 42, 42, 42, 42, 42, 43, 42, 44, 43, 42, 42, 44, 43, 43, 42, 42, 43, 42, 43, 42, 43, 43, 42, 44, 43, 44, 44, 44, 44, 44, 43, 43, 44, 43, 44, 45, 44, 44, 44, 44, 44, 44, 44, 45, 45, 45, 45, 44, 45, 45, 44, 44, 45, 44, 46, 45, 46, 45, 46, 45, 45, 46, 45, 46, 46, 45, 46, 46, 46, 46, 46, 47, 47, 46, 48, 47, 47, 47, 47, 47, 48, 47, 47, 48, 48, 48, 49, 48, 48, 49, 48, 48, 49, 49, 49, 49, 49, 49, 49, 50, 51, 50, 50, 50, 50, 50, 50, 51, 50, 50, 50, 52, 51, 51, 51, 50, 52, 51, 52, 52, 52, 52, 52, 52, 51, 50, 49, 48, 47, 46, 45, 44, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 20, 19, 19, 18, 17, 16, 16, 15, 15, 15, 13, 13, 11, 10, 10, 10, 10];
+pub static GAP_J2: &[u16] = &[23, 25, 25, 26, 27, 29, 29, 30, 32, 32, 34, 34, 34, 34, 34, 34, 35, 35, 34, 35, 35, 35, 34, 36, 36, 35, 35, 36, 35, 35, 37, 35, 36, 36, 36, 36, 37, 36, 37, 37, 37, 36, 37, 37, 37, 37, 38, 37, 38, 37, 38, 38, 38, 38, 38, 38, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 40, 40, 40, 40, 40, 40, 41, 41, 42, 41, 40, 41, 41, 42, 42, 43, 41, 41, 42, 42, 42, 42, 42, 42, 43, 42, 44, 43, 42, 42, 44, 43, 43, 42, 42, 43, 42, 43, 42, 43, 43, 42, 44, 43, 44, 44, 44, 44, 44, 43, 43, 44, 43, 44, 45, 44, 44, 44, 44, 44, 44, 44, 45, 45, 45, 45, 44, 45, 45, 44, 44, 45, 44, 46, 45, 46, 45, 46, 45, 45, 46, 45, 46, 46, 45, 46, 46, 46, 46, 46, 47, 47, 46, 48, 47, 47, 47, 47, 47, 48, 47, 47, 48, 48, 48, 49, 48, 48, 49, 48, 48, 49, 49, 49, 49, 49, 49, 49, 50, 51, 50, 50, 50, 50, 50, 50, 51, 50, 50, 50, 52, 51, 51, 50, 49, 51, 50, 51, 51, 51, 51, 51, 51, 50, 49, 48, 47, 46, 45, 44, 43, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 25, 25, 24, 23, 22, 21, 20, 19, 18, 18, 17, 16, 15, 15, 14, 14, 14, 12, 12, 10, 9, 9, 9, 9];
 
 pub const GCD_SUB_K: [usize; 1032] = [139,137,134,131,130,127,124,123,120,117,116,115,114,115,114,113,114,113,112,113,112,111,112,111,110,111,110,109,110,109,108,109,108,107,108,107,106,107,106,105,106,105,104,105,104,103,104,103,102,103,102,101,102,101,100,101,100,99,100,99,98,99,98,97,98,97,96,97,96,95,96,95,94,95,94,93,94,93,92,93,92,91,92,91,90,91,90,89,90,89,88,89,88,87,86,85,86,87,86,85,86,83,84,83,82,81,84,81,80,83,80,79,80,79,78,79,78,79,80,79,78,79,76,75,76,77,74,75,74,73,74,73,72,73,72,73,74,73,72,73,72,69,70,69,70,69,70,69,70,69,68,69,68,67,68,67,66,67,66,65,66,65,64,65,64,63,64,63,62,63,62,61,62,61,60,61,60,59,60,59,58,59,58,57,58,57,56,57,56,55,56,55,54,55,54,53,54,53,52,53,52,51,52,51,50,51,50,49,50,49,48,49,48,47,48,47,46,47,46,45,46,45,44,45,44,43,44,43,42,43,42,41,42,41,40,41,40,39,40,39,38,39,38,37,36,35,32,33,32,31,30,29,26,25,26,23,26,25,281,282,279,282,281,282,285,286,287,288,289,288,291,292,293,294,295,294,295,296,295,296,297,296,297,298,297,298,299,298,299,300,299,300,301,300,301,302,301,302,303,302,303,304,303,304,305,304,305,306,305,306,307,306,307,308,307,308,309,308,309,310,309,310,311,310,311,312,311,312,313,312,313,314,313,314,315,314,315,316,315,316,317,316,317,318,317,318,319,318,319,320,319,320,321,320,321,322,321,322,323,322,323,324,323,324,325,324,325,326,325,326,325,326,325,326,325,328,329,328,329,330,329,328,329,328,329,330,329,330,331,330,333,332,331,332,335,334,335,336,335,334,335,334,335,336,335,336,339,336,337,340,337,338,339,340,339,342,341,342,343,342,341,342,343,344,345,344,345,346,345,346,347,346,347,348,347,348,349,348,349,350,349,350,351,350,351,352,351,352,353,352,353,354,353,354,355,354,355,356,355,356,357,356,357,358,357,358,359,358,359,360,359,360,361,360,361,362,361,362,363,362,363,364,363,364,365,364,365,366,365,366,367,366,367,368,367,368,369,368,369,370,369,370,371,370,371,372,373,376,379,380,383,386,387,390,393,395,395,393,390,387,386,383,380,379,376,373,372,371,370,371,370,369,370,369,368,369,368,367,368,367,366,367,366,365,366,365,364,365,364,363,364,363,362,363,362,361,362,361,360,361,360,359,360,359,358,359,358,357,358,357,356,357,356,355,356,355,354,355,354,353,354,353,352,353,352,351,352,351,350,351,350,349,350,349,348,349,348,347,348,347,346,347,346,345,346,345,344,345,344,343,342,341,342,343,342,341,342,339,340,339,338,337,340,337,336,339,336,335,336,335,334,335,334,335,336,335,334,335,332,331,332,333,330,331,330,329,330,329,328,329,328,329,330,329,328,329,328,325,326,325,326,325,326,325,326,325,324,325,324,323,324,323,322,323,322,321,322,321,320,321,320,319,320,319,318,319,318,317,318,317,316,317,316,315,316,315,314,315,314,313,314,313,312,313,312,311,312,311,310,311,310,309,310,309,308,309,308,307,308,307,306,307,306,305,306,305,304,305,304,303,304,303,302,303,302,301,302,301,300,301,300,299,300,299,298,299,298,297,298,297,296,297,296,295,296,295,294,295,294,293,292,291,288,289,288,287,286,285,282,281,282,279,282,281,25,26,23,26,25,26,29,30,31,32,33,32,35,36,37,38,39,38,39,40,39,40,41,40,41,42,41,42,43,42,43,44,43,44,45,44,45,46,45,46,47,46,47,48,47,48,49,48,49,50,49,50,51,50,51,52,51,52,53,52,53,54,53,54,55,54,55,56,55,56,57,56,57,58,57,58,59,58,59,60,59,60,61,60,61,62,61,62,63,62,63,64,63,64,65,64,65,66,65,66,67,66,67,68,67,68,69,68,69,70,69,70,69,70,69,70,69,72,73,72,73,74,73,72,73,72,73,74,73,74,75,74,77,76,75,76,79,78,79,80,79,78,79,78,79,80,79,80,83,80,81,84,81,82,83,84,83,86,85,86,87,86,85,86,87,88,89,88,89,90,89,90,91,90,91,92,91,92,93,92,93,94,93,94,95,94,95,96,95,96,97,96,97,98,97,98,99,98,99,100,99,100,101,100,101,102,101,102,103,102,103,104,103,104,105,104,105,106,105,106,107,106,107,108,107,108,109,108,109,110,109,110,111,110,111,112,111,112,113,112,113,114,113,114,115,114,115,116,117,120,123,124,127,130,131,134,137,139];
 
diff --git a/src/point_add/trailmix_ludicrous/square.rs b/src/point_add/trailmix_ludicrous/square.rs
index 8e22da1..17b1b8d 100644
--- a/src/point_add/trailmix_ludicrous/square.rs
+++ b/src/point_add/trailmix_ludicrous/square.rs
@@ -459,7 +459,13 @@ fn build_sum_hi_lo(circ: &mut B, lambda: &[QubitId]) -> Vec<QubitId> {
     for i in 0..128 {
         circ.cx(lambda[i], sum[i]);
     }
-    cuccaro_carry(circ, None, &lambda[128..N], &sum[..128], None, Some(&sum[128]));
+    // Vented square-sum carry (exact; -128 emitted CCX here, -127 net after the fanout
+    // give-back). Default ON; TLM_SQUARE_SUM_VENTED=0 restores the recomputing Cuccaro.
+    if std::env::var("TLM_SQUARE_SUM_VENTED").ok().as_deref() == Some("0") {
+        cuccaro_carry(circ, None, &lambda[128..N], &sum[..128], None, Some(&sum[128]));
+    } else {
+        arith::cuccaro_carry_vented(circ, &lambda[128..N], &sum[..128], Some(&sum[128]));
+    }
     sum
 }
 
```

