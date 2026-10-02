# 2aedb45 — Narrow the GCD register widths and compare windows by 1 bit on divsteps 101–260, and lower the qubit caps 1152 → 1151 (1153 → 1152 qubits)

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-07-26 |
| Submission | `5745db8` |
| Commit | `2aedb4528a7fc43e6d430c869b6c9ab9406ecce0` |
| Result | 1152 qubits × 1,304,633 Toffoli = **1,502,937,216** |
| Base | `a254a8a` (git parent, the author's previous submission): 1153 qubits × 1,309,147 Toffoli = 1,509,446,491 |
| Change vs base | qubits −1, Toffoli −4,514, score −6,509,275 (leaderboard Δ −6,509,275) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the regenerated key table and six new research-note `.md` files are copied from the commit; the patch covers the rest |

## Summary

`SCHED_J2[i]` is the live width of the GCD registers `u` and `v` at divstep
`i`. The values shrink as the walk goes on, so the width can shrink too, and the
wires above it are freed. This commit makes the last 160 widths (divsteps
101–260) one bit narrower. It lowers each comparator window `GAP_J2[i]` by one
bit at the same steps, so the bottom of the compared window stays where it was.
Every walk add, compare and cswap at those steps gets one bit cheaper.

The freed wire only lowers the peak if the qubit caps go down with it. The
trailmix vent pool sizes itself to `cap − active qubits`, so on its own it just
absorbs the freed wire. The commit therefore lowers `TLM_TARGET_Q` and
`TLM_SQUARE_PEAK_CAP` from 1152 to 1151, and the peak goes from 1153 to 1152.
The new schedule shifts every gate key, so the dead-gate strip was re-mined
over 1e9 inputs. Both factors of the score drop: −1 qubit and −4,514 Toffoli.

## What changed and why it saves Toffoli and a qubit

1. **Width schedule, `src/point_add/trailmix_ludicrous/schedule.rs`.**
   - Every entry of `SCHED_J2` and of `GAP_J2` with index 101–260 goes down by
     exactly 1. That is 160 entries each; the sums go 35,486 → 35,326 and
     10,664 → 10,504. Entries 0–100 are unchanged. For example the last four
     widths go from 11, 11, 11, 11 to 10, 10, 10, 10.
   - In `forward_gcd_jump` / `reverse_gcd_jump`, `current_n = SCHED_J2[i]`. Wires
     of `u` and `v` above `current_n` are freed (`zero_and_free`), and the shift
     ladders, the `v < u` compare, the u/v cswap and the controlled add all run
     on `[..current_n]`. One bit narrower means one fewer cswap Toffoli and a
     shorter adder at each such step, in all four walks.
   - The compare covers the top `cmp_window(i)` bits, positions
     `current_n − window .. current_n − 1`. Lowering both by one keeps the lowest
     compared position the same. It drops only the top position, which the
     narrower width already assumes is 0. The note: the divstep error depends
     only on `SCHED_J2[i] − cmp_window(i)`. Moving one table without the other
     took the channel "from ~8 to ~4,600 mismatches". See
     [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) and
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
   - Why 160 entries. The note sweeps how many tail entries to narrow (n = 12
     nonces per point). Mean classical / phase failures per draw: 0 entries
     (head) 6.08 / 5.33; 96 → 8.33 / 6.92; 160 → 9.67 / 8.08; 224 → 13.67 / 10.00;
     all 258 → 1,386.83 / 140.58, which breaks the circuit. The early widths are
     a tight bound on the values, and all the slack is in the tail. 160 is the
     knee.
2. **Caps, `src/point_add/mod.rs` and `trailmix_ludicrous/mod.rs`.**
   `TLM_TARGET_Q` 1152 → 1151 in both `configure_q1153_second512_submission_defaults`
   and `install_q1153_submission_defaults`, and `TLM_SQUARE_PEAK_CAP` 1152 → 1151.
   - The vented adders size their extra carry wires as
     `headroom = TLM_TARGET_Q − active_qubits`. A narrower register alone does
     not lower the peak: narrowing 4, 12, 24 or 48 entries left it at 1153.
   - Lowering the cap alone loses as well. In the note's final-stream counts,
     cap 1151 without the narrowing gives +5,788 Toffoli for −1 qubit, against a
     break-even of about 1,135 Toffoli per qubit.
   - Only the two together win. See
     [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md) and
     [venting-and-wire-loans](../concepts/venting-and-wire-loans.md).
3. **Re-mined strip, `src/point_add/deep_strip_keys.rs`.**
   - The new schedule changes gate operands and shifts ordinals. With the old
     table, the build discarded 6,241 keys as stale, and the keys that did apply
     gave 8,720/9,024 classical mismatches. Those keys had passed the occupancy
     check but named live gates.
   - The new census: 1,000,005,632 input pairs (8 shards × 1.25e8), on the
     pre-strip stream of 1,375,689 CCX+CCZ at 1152 qubits. It gives 9,118
     `DEAD_KEYS` and 2,050 `DOWNGRADE_KEYS`, 11,168 in all (was 9,268 + 2,050).
   - The note's convergence table shows why depth matters: a 4e6-input census
     would have listed 14,886 dead keys, 63% too many. See
     [dead-gate-strip](../concepts/dead-gate-strip.md).
4. **Research notes.** New `src/point_add/memory/` (`README.md` and
   `01-architecture.md` to `05-qubit-reduction.md`). They describe the
   architecture, the λ analysis, proven floors, traps and qubit-reduction
   measurements. They are not compiled.
5. **Tail nonce:** `SUB4_TAIL_NONCE` default 5150000095 → 2000000032904.

## Why it is still correct, and what it risks

- **Width narrowing: probabilistic.** On an input whose `u` or `v` is still too
  large at some divstep in 101–260, the top wire that `zero_and_free` resets is
  not 0. The value is lost, which gives a classical failure, and the reset
  leaves a random phase. The note's sweep prices this at about +3.6 classical
  and +2.8 phase failures per draw at 160 entries. That is what raises λ, the
  expected number of failing shots.
- **Cap change: exact.** It only changes the adders' layout.
- **Strip: empirical**, as in [`a254a8a`](a254a8a.md).
- The note's grind numbers: mean 11.29 batches to the first failure, so
  P(clean seed) ≈ 2.1e-6, about 4.75e5 candidates per hit. The shipped nonce
  `2000000032904` draws a clean set: 0 classical, 0 phase and 0 ancilla
  failures, and the build log shows "0 stale keys skipped". See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Both savings come from truncating per-step widths: the register width
`SCHED_J2` and the compare window `GAP_J2`. The cap change only turns the freed
width into a lower peak, and the strip is a re-mine for the new geometry. That
is comparator/width truncation. The runner-up would be ancilla-lifetime /
venting, for the cap.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a254a8a -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol a254a8a 2aedb45 -- src/point_add` is 13,425 lines
   in 10 files, almost all of it the regenerated key table.
2. **Copy the generated table and the notes from the commit:**
   `git checkout 2aedb45 -- src/point_add/deep_strip_keys.rs src/point_add/memory`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It covers `mod.rs`, `trailmix_ludicrous/mod.rs` and `schedule.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol 2aedb45 -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `TLM_*` or
   `SUB4_*` overrides set. Expect:
   - 1152 qubits
   - 1,304,633 average Toffoli (1,304,633.369 before rounding)
   - score 1,502,937,216
   - 0 classical, 0 phase and 0 ancilla failures
6. **Nonce caveat.** The score only reproduces with the nonce `2000000032904` and
   an identical op stream. Any other change needs a new nonce hunt and,
   because the strip keys are tied to this stream, a check that no key is stale.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index c4033db..7d4e0ae 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1178,7 +1178,7 @@ const Q1153_SECOND512_SUBMISSION_NONCE: &str = "193806910775884";
 
 fn configure_q1153_second512_submission_defaults() {
     set_default_env("DIALOG_TAIL_NONCE", Q1153_SECOND512_SUBMISSION_NONCE);
-    set_default_env("TLM_TARGET_Q", "1152");
+    set_default_env("TLM_TARGET_Q", "1151");
     set_default_env("TLM_FOLD_CHUNK_ZERO_CIN", "1");
     set_default_env("TLM_FFG_MAX_G", "47");
     set_default_env("TLM_APPLY_ADD_SKIP_LASTK", "1");
@@ -1193,7 +1193,7 @@ fn configure_q1153_second512_submission_defaults() {
     set_default_env("TLM_SQUARE_VENT_MARGIN", "0");
     set_default_env("TLM_COORD_ADD3X_TRUNC", "1");
     set_default_env("TLM_SQUARE_VENT_SHIFTED", "1");
-    set_default_env("TLM_SQUARE_PEAK_CAP", "1152");
+    set_default_env("TLM_SQUARE_PEAK_CAP", "1151");
     set_default_env("TLM_CUCCARO_SKIP_STRUCTURAL_DEAD_CALLS", "1");
 }
 
@@ -2377,7 +2377,7 @@ pub fn build() -> Vec<Op> {
     };
     // The tail nonce ground for this composed stream (verified PASS 0/0/0, score 1,517,633,280).
     // SUB4_TAIL_NONCE overrides for re-grinding/seam-export.
-    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(5150000095);
+    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(2000000032904);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index 4388ab9..d6133e1 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -429,7 +429,7 @@ fn route_swaps(src: &[QubitId], dst: &[QubitId]) -> Vec<(QubitId, QubitId)> {
 
 fn install_q1153_submission_defaults() {
     for (name, value) in [
-        ("TLM_TARGET_Q", "1152"),
+        ("TLM_TARGET_Q", "1151"),
         ("TLM_FOLD_CHUNK_ZERO_CIN", "1"),
         ("TLM_FFG_MAX_G", "47"),
         ("TLM_APPLY_ADD_SKIP_LASTK", "1"),
diff --git a/src/point_add/trailmix_ludicrous/schedule.rs b/src/point_add/trailmix_ludicrous/schedule.rs
index 794baf2..d51ad70 100644
--- a/src/point_add/trailmix_ludicrous/schedule.rs
+++ b/src/point_add/trailmix_ludicrous/schedule.rs
@@ -18,37 +18,9 @@ pub fn baked_artifacts_valid() -> bool {
 
 pub const PAD: usize = 20;
 
-pub static SCHED_J2: &[u16] = &[
-    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 255, 254, 253, 252, 251, 250, 249, 248,
-    247, 246, 245, 244, 243, 242, 241, 240, 239, 238, 237, 236, 235, 234, 233, 232, 231, 230, 229,
-    228, 227, 226, 225, 224, 223, 222, 221, 220, 219, 218, 217, 216, 215, 214, 213, 212, 211, 210,
-    209, 208, 207, 206, 205, 204, 203, 202, 201, 200, 199, 198, 197, 196, 195, 194, 193, 192, 191,
-    190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180, 179, 178, 177, 176, 175, 174, 173, 173,
-    172, 170, 169, 168, 167, 166, 166, 164, 164, 163, 162, 160, 160, 159, 157, 157, 156, 155, 154,
-    153, 152, 151, 149, 148, 147, 146, 145, 145, 144, 143, 141, 141, 140, 139, 138, 137, 136, 135,
-    134, 133, 131, 130, 129, 128, 127, 126, 126, 125, 124, 122, 122, 120, 119, 118, 117, 116, 115,
-    114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95,
-    94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71,
-    70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47,
-    46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 26, 25, 24, 23, 22, 21,
-    21, 20, 20, 19, 18, 17, 17, 16, 16, 16, 14, 14, 12, 11,
-    11, 11, 11,
-];
+pub static SCHED_J2: &[u16] = &[256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 255, 254, 253, 252, 251, 250, 249, 248, 247, 246, 245, 244, 243, 242, 241, 240, 239, 238, 237, 236, 235, 234, 233, 232, 231, 230, 229, 228, 227, 226, 225, 224, 223, 222, 221, 220, 219, 218, 217, 216, 215, 214, 213, 212, 211, 210, 209, 208, 207, 206, 205, 204, 203, 202, 201, 200, 199, 198, 197, 196, 195, 194, 193, 192, 191, 190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180, 179, 178, 177, 176, 175, 174, 173, 173, 172, 170, 169, 168, 167, 166, 165, 163, 163, 162, 161, 159, 159, 158, 156, 156, 155, 154, 153, 152, 151, 150, 148, 147, 146, 145, 144, 144, 143, 142, 140, 140, 139, 138, 137, 136, 135, 134, 133, 132, 130, 129, 128, 127, 126, 125, 125, 124, 123, 121, 121, 119, 118, 117, 116, 115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71, 70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 25, 24, 23, 22, 21, 20, 20, 19, 19, 18, 17, 16, 16, 15, 15, 15, 13, 13, 11, 10, 10, 10, 10];
 
-pub static GAP_J2: &[u16] = &[
-    23, 25, 25, 26, 27, 29, 29, 30, 32, 32, 34, 34, 34, 34, 34, 34, 35, 35, 34, 35, 35, 35, 34, 36,
-    36, 35, 35, 36, 35, 35, 37, 35, 36, 36, 36, 36, 37, 36, 37, 37, 37, 36, 37, 37, 37, 37, 38, 37,
-    38, 37, 38, 38, 38, 38, 38, 38, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 40, 40, 40, 40,
-    40, 40, 41, 41, 42, 41, 40, 41, 41, 42, 42, 43, 41, 41, 42, 42, 42, 42, 42, 42, 43, 42, 44, 43,
-    42, 42, 44, 43, 43, 44, 44, 45, 44, 45, 44, 45, 45, 44, 46, 45, 46, 46, 46, 46, 46, 45, 45, 46,
-    45, 46, 47, 46, 46, 46, 46, 46, 46, 46, 47, 47, 47, 47, 46, 47, 47, 46, 46, 47, 46, 48, 47, 48,
-    47, 48, 47, 47, 48, 47, 48, 48, 47, 48, 48, 48, 48, 48, 49, 49, 48, 50, 49, 49, 49, 49, 49, 50,
-    49, 49, 50, 50, 50, 51, 50, 50, 51, 50, 50, 51, 51, 51, 51, 51, 51, 51, 52, 53, 52, 52, 52, 52,
-    52, 52, 53, 52, 52, 52, 54, 53, 53, 53, 52, 54, 53, 54, 54, 54, 54, 54, 54, 53, 52, 51, 50, 49,
-    48, 47, 46, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26,
-    25, 24, 23, 22, 22, 21, 21, 20, 19, 18, 18, 17, 17, 17, 15, 15, 13, 12,
-    12, 12, 12,
-];
+pub static GAP_J2: &[u16] = &[23, 25, 25, 26, 27, 29, 29, 30, 32, 32, 34, 34, 34, 34, 34, 34, 35, 35, 34, 35, 35, 35, 34, 36, 36, 35, 35, 36, 35, 35, 37, 35, 36, 36, 36, 36, 37, 36, 37, 37, 37, 36, 37, 37, 37, 37, 38, 37, 38, 37, 38, 38, 38, 38, 38, 38, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 39, 40, 40, 40, 40, 40, 40, 41, 41, 42, 41, 40, 41, 41, 42, 42, 43, 41, 41, 42, 42, 42, 42, 42, 42, 43, 42, 44, 43, 42, 42, 44, 43, 43, 43, 43, 44, 43, 44, 43, 44, 44, 43, 45, 44, 45, 45, 45, 45, 45, 44, 44, 45, 44, 45, 46, 45, 45, 45, 45, 45, 45, 45, 46, 46, 46, 46, 45, 46, 46, 45, 45, 46, 45, 47, 46, 47, 46, 47, 46, 46, 47, 46, 47, 47, 46, 47, 47, 47, 47, 47, 48, 48, 47, 49, 48, 48, 48, 48, 48, 49, 48, 48, 49, 49, 49, 50, 49, 49, 50, 49, 49, 50, 50, 50, 50, 50, 50, 50, 51, 52, 51, 51, 51, 51, 51, 51, 52, 51, 51, 51, 53, 52, 52, 52, 51, 53, 52, 53, 53, 53, 53, 53, 53, 52, 51, 50, 49, 48, 47, 46, 45, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 21, 20, 20, 19, 18, 17, 17, 16, 16, 16, 14, 14, 12, 11, 11, 11, 11];
 
 pub const GCD_SUB_K: [usize; 1032] = [139,137,134,131,130,127,124,123,120,117,116,115,114,115,114,113,114,113,112,113,112,111,112,111,110,111,110,109,110,109,108,109,108,107,108,107,106,107,106,105,106,105,104,105,104,103,104,103,102,103,102,101,102,101,100,101,100,99,100,99,98,99,98,97,98,97,96,97,96,95,96,95,94,95,94,93,94,93,92,93,92,91,92,91,90,91,90,89,90,89,88,89,88,87,86,85,86,87,86,85,86,83,84,83,82,81,84,81,80,83,80,79,80,79,78,79,78,79,80,79,78,79,76,75,76,77,74,75,74,73,74,73,72,73,72,73,74,73,72,73,72,69,70,69,70,69,70,69,70,69,68,69,68,67,68,67,66,67,66,65,66,65,64,65,64,63,64,63,62,63,62,61,62,61,60,61,60,59,60,59,58,59,58,57,58,57,56,57,56,55,56,55,54,55,54,53,54,53,52,53,52,51,52,51,50,51,50,49,50,49,48,49,48,47,48,47,46,47,46,45,46,45,44,45,44,43,44,43,42,43,42,41,42,41,40,41,40,39,40,39,38,39,38,37,36,35,32,33,32,31,30,29,26,25,26,23,26,25,281,282,279,282,281,282,285,286,287,288,289,288,291,292,293,294,295,294,295,296,295,296,297,296,297,298,297,298,299,298,299,300,299,300,301,300,301,302,301,302,303,302,303,304,303,304,305,304,305,306,305,306,307,306,307,308,307,308,309,308,309,310,309,310,311,310,311,312,311,312,313,312,313,314,313,314,315,314,315,316,315,316,317,316,317,318,317,318,319,318,319,320,319,320,321,320,321,322,321,322,323,322,323,324,323,324,325,324,325,326,325,326,325,326,325,326,325,328,329,328,329,330,329,328,329,328,329,330,329,330,331,330,333,332,331,332,335,334,335,336,335,334,335,334,335,336,335,336,339,336,337,340,337,338,339,340,339,342,341,342,343,342,341,342,343,344,345,344,345,346,345,346,347,346,347,348,347,348,349,348,349,350,349,350,351,350,351,352,351,352,353,352,353,354,353,354,355,354,355,356,355,356,357,356,357,358,357,358,359,358,359,360,359,360,361,360,361,362,361,362,363,362,363,364,363,364,365,364,365,366,365,366,367,366,367,368,367,368,369,368,369,370,369,370,371,370,371,372,373,376,379,380,383,386,387,390,393,395,395,393,390,387,386,383,380,379,376,373,372,371,370,371,370,369,370,369,368,369,368,367,368,367,366,367,366,365,366,365,364,365,364,363,364,363,362,363,362,361,362,361,360,361,360,359,360,359,358,359,358,357,358,357,356,357,356,355,356,355,354,355,354,353,354,353,352,353,352,351,352,351,350,351,350,349,350,349,348,349,348,347,348,347,346,347,346,345,346,345,344,345,344,343,342,341,342,343,342,341,342,339,340,339,338,337,340,337,336,339,336,335,336,335,334,335,334,335,336,335,334,335,332,331,332,333,330,331,330,329,330,329,328,329,328,329,330,329,328,329,328,325,326,325,326,325,326,325,326,325,324,325,324,323,324,323,322,323,322,321,322,321,320,321,320,319,320,319,318,319,318,317,318,317,316,317,316,315,316,315,314,315,314,313,314,313,312,313,312,311,312,311,310,311,310,309,310,309,308,309,308,307,308,307,306,307,306,305,306,305,304,305,304,303,304,303,302,303,302,301,302,301,300,301,300,299,300,299,298,299,298,297,298,297,296,297,296,295,296,295,294,295,294,293,292,291,288,289,288,287,286,285,282,281,282,279,282,281,25,26,23,26,25,26,29,30,31,32,33,32,35,36,37,38,39,38,39,40,39,40,41,40,41,42,41,42,43,42,43,44,43,44,45,44,45,46,45,46,47,46,47,48,47,48,49,48,49,50,49,50,51,50,51,52,51,52,53,52,53,54,53,54,55,54,55,56,55,56,57,56,57,58,57,58,59,58,59,60,59,60,61,60,61,62,61,62,63,62,63,64,63,64,65,64,65,66,65,66,67,66,67,68,67,68,69,68,69,70,69,70,69,70,69,70,69,72,73,72,73,74,73,72,73,72,73,74,73,74,75,74,77,76,75,76,79,78,79,80,79,78,79,78,79,80,79,80,83,80,81,84,81,82,83,84,83,86,85,86,87,86,85,86,87,88,89,88,89,90,89,90,91,90,91,92,91,92,93,92,93,94,93,94,95,94,95,96,95,96,97,96,97,98,97,98,99,98,99,100,99,100,101,100,101,102,101,102,103,102,103,104,103,104,105,104,105,106,105,106,107,106,107,108,107,108,109,108,109,110,109,110,111,110,111,112,111,112,113,112,113,114,113,114,115,114,115,116,117,120,123,124,127,130,131,134,137,139];
 
```

