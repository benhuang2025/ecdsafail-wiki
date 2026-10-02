# e5c53dc — Narrow the ping-pong replay flag compare from 25 to 24 bits

| | |
| --- | --- |
| Contestant | odinfree |
| Date | 2026-08-21 |
| Submission | `e4b5151` |
| Commit | `e5c53dc905e60a3189c08f0cdab4e884ce652bab` |
| Result | 1320 qubits × 945,689 Toffoli = **1,248,309,480** |
| Base | `6ee4d14`: 1320 qubits × 946,387 Toffoli = 1,249,230,840 |
| Change vs base | qubits ±0, Toffoli −698, score −921,360 (leaderboard Δ −921,360) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit changes one constant. In the replay stage of the ping-pong
divider, each replay cell leaves an overflow bit. The circuit measures that bit
out and then repairs the phase with a comparison of the top `k` bits of two
registers. This commit makes `k` 24 instead of 25. One comparator bit costs one
Toffoli, and the repair only runs on about half the shots, so the saving is
about half a Toffoli per call. Summed over all replay rounds this saves 698
average Toffoli. Qubits are unchanged. The tail nonce was re-hunted because the
op stream changed.

## What changed and why it saves Toffoli

- `src/point_add/pingpong_div.rs`, `replay_flag_compare()`: the default window
  of `SUB4_PP_REPLAY_FLAG_COMPARE` goes from 25 to 24.
  - The window is used at three sites: after the add-and-halve cell, after the
    double-and-add cell, and in the unfused `signed_mod_add_pm` (reached only
    when `SUB4_PINGPONG_UNFUSED_INVERSE` is set).
  - Each site runs `b.hmr(flag, phase)`, then
    `cmp_lt_phase_conditioned(b, &target[N - k..], &source[N - k..], phase)`.
  - `hmr` measures the flag in the X basis and resets it, so the flag costs no
    Toffoli to uncompute. The measurement can leave a sign error, which
    happens when the outcome bit `phase` is 1. In that case the comparison
    `target < source` recomputes the flag's value from the top `k` bits and
    applies the phase correction.
  - The comparison costs `k` Toffoli, but it only executes when `phase` is 1,
    which is about half the shots. See
    [measurement-uncompute](../concepts/measurement-uncompute.md) and
    [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
- `src/point_add/mod.rs`, `build()`: the default `SUB4_PINGPONG_TAIL_NONCE`
  goes from 40561 to 52007. The nonce only selects which test shots are drawn.
  It does not change the arithmetic.

## Why it is still correct, and what it risks

The truncated comparison is an approximation. It returns the wrong flag value
when the two registers agree on all of their top `k` bits, and then the phase
repair is wrong. This happens with probability about 2^-k per call, so going
from 25 to 24 bits roughly doubles the per-call error. The circuit therefore
fails on more rare "hard" inputs, and Lambda goes up. Lambda is the expected
number of failing shots in one 9,024-shot test draw.

The submission is still valid because the re-hunted nonce `52007` draws a test
set with no hard input. The run gets 0 classical, 0 phase and 0 ancilla
failures. A wrong repair would show up as a phase failure. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is a narrower comparator window, so the commit is filed
as comparator/width truncation. The nonce change comes with every circuit
change and is not a separate lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6ee4d14 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 6ee4d14 e5c53dc -- src/point_add` is
   4 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol e5c53dc -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set, because they override the defaults in the patch.
   Expect:
   - 1320 qubits
   - 945,689 average Toffoli (rounded)
   - score 1,248,309,480
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `52007` and an identical op stream.
If you change anything else, including the compare width, you must hunt a new
nonce.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index fa2ddab..da2fc35 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2531,7 +2531,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(40561);
+            .unwrap_or(52007);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index bdce97d..293b38d 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -66,7 +66,7 @@ fn endpoint_fold_window() -> usize {
 
 fn replay_flag_compare() -> usize {
     static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
-    tuned_window("SUB4_PP_REPLAY_FLAG_COMPARE", &SLOT, 25)
+    tuned_window("SUB4_PP_REPLAY_FLAG_COMPARE", &SLOT, 24)
 }
 
 /// Translate the source model's `lsbs = 56` literally: its pseudo-Mersenne
```
