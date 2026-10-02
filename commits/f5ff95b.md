# f5ff95b — Raise the scratch-qubit caps 1150 → 1158: spend 7 qubits to buy 9,147 Toffoli

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-07-26 |
| Submission | `a536a48` |
| Commit | `f5ff95b26059e0d01b143e67bf93cad2649a3668` |
| Result | 1158 qubits × 1,292,651 Toffoli = **1,496,889,858** |
| Base | `3222da6` (git parent, the author's previous submission): 1151 qubits × 1,301,798 Toffoli = 1,498,369,498 |
| Change vs base | qubits +7, Toffoli −9,147, score −1,479,640 (leaderboard Δ −1,479,640) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the regenerated key table `deep_strip_keys.rs` is copied from the commit; the patch covers the rest |

## Summary

The trailmix builders size their extra scratch wires against a qubit cap:
vents that let an adder measure a carry away instead of uncomputing it with a
Toffoli, chunk counts, fold windows. Earlier commits had pushed the cap down
to 1150 to win qubits. This commit goes the other way and raises
`TLM_TARGET_Q` and `TLM_SQUARE_PEAK_CAP` to 1158. The builders then pick wider,
cheaper layouts. Peak qubits rise by 7 to 1158, and average Toffoli falls by
9,147.

The trade pays because one qubit is worth only about T/Q ≈ 1,130 Toffoli of
score here. 9,147 Toffoli is more than the 7,869 that 7 qubits would have to
buy back. The author's sweep finds the score's minimum near caps 1156–1158.
The circuit's arithmetic is unchanged. The strip was re-mined, because even a
cap-only change shifts its keys.

## What changed and why it saves Toffoli

- **`src/point_add/mod.rs`, `configure_q1153_second512_submission_defaults()`:**
  `TLM_TARGET_Q` 1150 → 1158 and `TLM_SQUARE_PEAK_CAP` 1150 → 1158.
  **`trailmix_ludicrous/mod.rs`, `install_q1153_submission_defaults()`:**
  `TLM_TARGET_Q` 1150 → 1158.
- **What the caps do.** `target_qubit_headroom(circ)` returns
  `TLM_TARGET_Q − active_qubits`. Its callers use that headroom to decide how
  many extra wires they may take at that moment:
  - the vent count of the vented hybrid adders and the chunk count `k` in
    `gidney.rs`;
  - the comparator layout in `comparator.rs`;
  - the fold vents in `fused.rs`;
  - the fold window `g` in `arith.rs`.
  `TLM_SQUARE_PEAK_CAP` plays the same role in the square. More vents mean
  more carries measured out with `hmr` (no Toffoli) instead of uncomputed with
  a CCX, and fewer chunk-boundary carry erases. See
  [venting-and-wire-loans](../concepts/venting-and-wire-loans.md) and
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
- **The author's sweep** of executed Toffoli (taken from `results.tsv`, which
  `eval_circuit` fills even on failing runs):

  | cap = peak | executed Toffoli | product |
  |---|---|---|
  | 1156 | 1,304,605 | 1,508,122,941 |
  | 1158 | 1,302,946 | 1,508,811,466 |
  | 1160 | 1,302,225 | 1,510,581,251 |
  | 1164 | 1,301,370 | 1,514,794,163 |
  | 1170 | 1,301,245 | 1,522,457,095 |

  These are pre-strip numbers; the shipped, stripped build is 1,292,651. The
  note warns against ranking caps by *emitted* CCX. The extra gates a low cap
  forces are mostly classically conditioned, so they execute far below the
  average. The emitted count overstated the cost of qubits by 4.6×.
- **Re-mined strip, `src/point_add/deep_strip_keys.rs`:** a census of 780,016,640
  input pairs gives 8,953 `DEAD_KEYS` and 2,035 `DOWNGRADE_KEYS` (10,988 keys, was
  11,086). The note found that even a cap change makes keys stale: moving the
  cap 1151 → 1148 on the old table discarded 3,144 keys and gave 8,646 classical
  mismatches. See [dead-gate-strip](../concepts/dead-gate-strip.md).
- **Tail nonce:** `SUB4_TAIL_NONCE` default 66014000021257 → 95447000630348.

## Why it is still correct, and what it risks

- **The cap change is exact.** It changes which layout each adder uses, not
  what it computes. The note measured the cap axis as λ-neutral: n = 24 per
  arm, cap 1151 gives 8.67 / 7.38 classical / phase failures per draw, cap 1148
  gives 8.79 / 7.50.
- **The strip is empirical**, as in [`a254a8a`](a254a8a.md).
- The note's λ_total estimates: head 23.8, this build 22.9. Before the seed
  grind, a random seed showed 8 classical / 6 phase / 0 ancilla failures. The
  shipped nonce `95447000630348` draws a clean set: 0 classical, 0 phase and 0
  ancilla failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

No gate logic changes, only the scratch budget that the allocation-sensitive
builders may use. That is filed as ancilla-lifetime / venting, like the other
cap retunes (d9ef3e9, 31f9c58), even though it trades in the opposite
direction to most of them.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 3222da6 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 3222da6 f5ff95b -- src/point_add` is 6,534 lines
   in 3 files, almost all of it the regenerated key table.
2. **Copy the generated table from the commit:**
   `git checkout f5ff95b -- src/point_add/deep_strip_keys.rs`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
4. **Check the tree.** `git diff --ignore-cr-at-eol f5ff95b -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `TLM_*` or
   `SUB4_*` overrides set. Expect:
   - 1158 qubits
   - 1,292,651 average Toffoli (rounded)
   - score 1,496,889,858
   - 0 classical, 0 phase and 0 ancilla failures
6. **Nonce caveat.** The score only reproduces with the nonce `95447000630348` and
   an identical op stream. Any other change needs a new nonce hunt and a strip
   re-mine.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6f38aa8..5eeb060 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1178,7 +1178,7 @@ const Q1153_SECOND512_SUBMISSION_NONCE: &str = "193806910775884";
 
 fn configure_q1153_second512_submission_defaults() {
     set_default_env("DIALOG_TAIL_NONCE", Q1153_SECOND512_SUBMISSION_NONCE);
-    set_default_env("TLM_TARGET_Q", "1150");
+    set_default_env("TLM_TARGET_Q", "1158");
     set_default_env("TLM_FOLD_CHUNK_ZERO_CIN", "1");
     set_default_env("TLM_FFG_MAX_G", "47");
     set_default_env("TLM_APPLY_ADD_SKIP_LASTK", "1");
@@ -1193,7 +1193,7 @@ fn configure_q1153_second512_submission_defaults() {
     set_default_env("TLM_SQUARE_VENT_MARGIN", "0");
     set_default_env("TLM_COORD_ADD3X_TRUNC", "1");
     set_default_env("TLM_SQUARE_VENT_SHIFTED", "1");
-    set_default_env("TLM_SQUARE_PEAK_CAP", "1150");
+    set_default_env("TLM_SQUARE_PEAK_CAP", "1158");
     set_default_env("TLM_CUCCARO_SKIP_STRUCTURAL_DEAD_CALLS", "1");
 }
 
@@ -2377,7 +2377,7 @@ pub fn build() -> Vec<Op> {
     };
     // The tail nonce ground for this composed stream (verified PASS 0/0/0, score 1,517,633,280).
     // SUB4_TAIL_NONCE overrides for re-grinding/seam-export.
-    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(66014000021257);
+    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(95447000630348);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index 7c95ddd..2c8b33d 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -429,7 +429,7 @@ fn route_swaps(src: &[QubitId], dst: &[QubitId]) -> Vec<(QubitId, QubitId)> {
 
 fn install_q1153_submission_defaults() {
     for (name, value) in [
-        ("TLM_TARGET_Q", "1150"),
+        ("TLM_TARGET_Q", "1158"),
         ("TLM_FOLD_CHUNK_ZERO_CIN", "1"),
         ("TLM_FFG_MAX_G", "47"),
         ("TLM_APPLY_ADD_SKIP_LASTK", "1"),
```

