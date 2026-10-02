# d9ef3e9 — Re-sweep the scratch-qubit caps for the narrowed schedule: 1150 → 1154, spending 3 qubits for 5,166 Toffoli

| | |
| --- | --- |
| Contestant | gopikannappan |
| Date | 2026-07-26 |
| Submission | `8233cd7` |
| Commit | `d9ef3e950e0a9151daa81278770bc9bdb4a73537` |
| Result | 1154 qubits × 1,294,287 Toffoli = **1,493,607,198** |
| Base | `60d6185` (git parent, the author's previous submission): 1151 qubits × 1,299,453 Toffoli = 1,495,670,403 |
| Change vs base | qubits +3, Toffoli −5,166, score −2,063,205 (leaderboard Δ −2,063,205) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the regenerated key table `deep_strip_keys.rs` is copied from the commit; the patch covers `mod.rs` |

## Summary

This is the same knob as [`f5ff95b`](f5ff95b.md): the caps `TLM_TARGET_Q` and
`TLM_SQUARE_PEAK_CAP` set how many scratch wires (vents, chunk carries, fold
windows) the trailmix builders may use. f5ff95b found that the score is lowest
at caps 1156–1158 on the schedule of its time. [`60d6185`](60d6185.md) then
narrowed the GCD width schedule further, which moves that minimum. The author
re-swept the cap on the narrowed circuit and found the minimum at 1154. Going
from 1150 to 1154 raises the peak by 3 qubits and lowers average Toffoli by
5,166. That is more than the 3,378 Toffoli the 3 qubits would have to buy back.

The arithmetic is unchanged. The dead-gate strip was re-mined, now at 256M
inputs, because even a cap change shifts its keys.

## What changed and why it saves Toffoli

- **`src/point_add/mod.rs`, `configure_q1153_second512_submission_defaults()`:**
  `TLM_TARGET_Q` 1150 → 1154 and `TLM_SQUARE_PEAK_CAP` 1150 → 1154.
  - `trailmix_ludicrous/mod.rs::install_q1153_submission_defaults` still lists
    `TLM_TARGET_Q = 1150`. It skips any name that is already set, and
    `configure_…` runs first, so 1154 wins.
- **Mechanism.** `target_qubit_headroom()` = `TLM_TARGET_Q − active_qubits`
  decides how many vents and chunk wires the vented adders, comparators and
  folds may take. More headroom means more carries measured out instead of
  uncomputed with Toffoli. See [`f5ff95b`](f5ff95b.md),
  [venting-and-wire-loans](../concepts/venting-and-wire-loans.md) and
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
- **The sweep** (strip off; executed Toffoli from `results.tsv`):

  | cap | peak | avg executed Toffoli | product |
  |---|---|---|---|
  | 1150 (base) | 1151 | 1,310,561.883 | 1,508,456,727 |
  | 1152 | 1153 | 1,307,794.006 | 1,507,886,489 |
  | **1154** | **1154** | **1,305,015.533** | **1,505,987,925** |
  | 1156 | 1156 | 1,302,899.402 | 1,506,151,709 |
  | 1158 | 1158 | 1,301,321.545 | 1,506,930,349 |

  The note's explanation: the narrower schedule leaves fewer live wires to
  absorb, so less headroom is needed and the optimum moves left. The cap has
  to be re-swept for each schedule.
- **Re-mined strip, `src/point_add/deep_strip_keys.rs`.**
  - With the old table, 3,393 keys were discarded as stale, and the build gave
    8,689 classical mismatches and 141/141 phase garbage.
  - New census: 256,000,000 input pairs in 5 shards. It gives 9,324 dead and
    2,156 downgrade keys, 11,480 in all (was 11,921). The build logs "0 stale
    keys skipped".
  - The deeper census keeps fewer gates (the strip saves about 10,726 average
    Toffoli instead of about 11,109). In exchange its measured residual is 4
    divergences in 5,120,000 shots, about +0.007 failing shots per draw. See
    [dead-gate-strip](../concepts/dead-gate-strip.md).
- **Tail nonce:** `SUB4_TAIL_NONCE` default 20142451900 → 30008006160.

## Why it is still correct, and what it risks

- **Cap change: exact.** It is a layout choice. The note measured it as
  λ-neutral (paired n = 16, strip off): classical 14.94 at cap 1150 against
  15.25 at cap 1154, not significant.
- **Strip: empirical**, as above.
- The measured clean-seed density is 4.31e-8, 4.6× better than the base. Almost
  all of the improvement is in the phase channel; the classical channel is
  unchanged.
- The note also tested the obvious next step, narrowing 224 tail entries by 2
  instead of 160. It would save about 2,800 Toffoli but doubles classical λ to
  31.25, which is unreachable.
- The shipped nonce `30008006160` draws a clean set: 9,024 of 9,024 shots, 0
  classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

No gate logic changes, only the scratch budget that sets the qubit/Toffoli
trade. It is the same kind of cap retune as f5ff95b, so ancilla-lifetime /
venting. The strip is a re-derivation for the new stream.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 60d6185 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 60d6185 d9ef3e9 -- src/point_add` is 7,300 lines
   in 2 files, almost all of it the key table.
2. **Copy the generated table from the commit:**
   `git checkout d9ef3e9 -- src/point_add/deep_strip_keys.rs`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
4. **Check the tree.** `git diff --ignore-cr-at-eol d9ef3e9 -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `TLM_*` or
   `SUB4_*` overrides set. Expect:
   - 1154 qubits
   - 1,294,287 average Toffoli (1,294,287.225 before rounding)
   - score 1,493,607,198
   - 0 classical, 0 phase and 0 ancilla failures
6. **Nonce caveat.** The score only reproduces with the nonce `30008006160` and an
   identical op stream. Any other change needs a new nonce hunt and a strip
   re-mine.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index e0f6099..b7f6c13 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1178,7 +1178,7 @@ const Q1153_SECOND512_SUBMISSION_NONCE: &str = "193806910775884";
 
 fn configure_q1153_second512_submission_defaults() {
     set_default_env("DIALOG_TAIL_NONCE", Q1153_SECOND512_SUBMISSION_NONCE);
-    set_default_env("TLM_TARGET_Q", "1150");
+    set_default_env("TLM_TARGET_Q", "1154");
     set_default_env("TLM_FOLD_CHUNK_ZERO_CIN", "1");
     set_default_env("TLM_FFG_MAX_G", "47");
     set_default_env("TLM_APPLY_ADD_SKIP_LASTK", "1");
@@ -1193,7 +1193,7 @@ fn configure_q1153_second512_submission_defaults() {
     set_default_env("TLM_SQUARE_VENT_MARGIN", "0");
     set_default_env("TLM_COORD_ADD3X_TRUNC", "1");
     set_default_env("TLM_SQUARE_VENT_SHIFTED", "1");
-    set_default_env("TLM_SQUARE_PEAK_CAP", "1150");
+    set_default_env("TLM_SQUARE_PEAK_CAP", "1154");
     set_default_env("TLM_CUCCARO_SKIP_STRUCTURAL_DEAD_CALLS", "1");
 }
 
@@ -2377,7 +2377,7 @@ pub fn build() -> Vec<Op> {
     };
     // The tail nonce ground for this composed stream (verified PASS 0/0/0, score 1,517,633,280).
     // SUB4_TAIL_NONCE overrides for re-grinding/seam-export.
-    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(20142451900);
+    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(30008006160);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
```

