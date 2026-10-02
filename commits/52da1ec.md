# 52da1ec — Narrow the replay overflow-flag repair compare from 22 to 20 bits

| | |
| --- | --- |
| Contestant | REgonLevy |
| Date | 2026-08-27 |
| Submission | `153f9eb` |
| Commit | `52da1ecd9c2435e560df705cb7a03ab998343840` |
| Result | 1266 qubits × 904,740 Toffoli = **1,145,400,840** |
| Base | `79e7afa` (git parent, odinfree's frontier): 1266 qubits × 906,124 Toffoli = 1,147,152,984 |
| Change vs base | qubits ±0, Toffoli −1,384, score −1,752,144 (leaderboard Δ −1,752,144) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: one backup file is copied from the commit; the patch covers the rest |

## Summary

Every ping-pong replay cell adds a source into a target mod p and leaves an
overflow flag. The circuit does not uncompute that flag with gates. It
measures the flag out with `hmr` and then repairs the leftover phase with a
compare of the top `k` bits of the two registers, run only when the
measurement outcome is 1.

This commit pins `k` (`SUB4_PP_REPLAY_FLAG_COMPARE`) at 20 instead of 22. Each
compare bit is one Toffoli on about half the shots, and there is one such
compare per replay round in each of the two traversals (about 1,390 rounds).
So two bits save about 1,390 executed Toffoli, close to the measured 1,384. Q
is unchanged. A narrower compare is wrong more often, so λ goes up and a new
nonce was hunted. The commit also adds an unused backup file, `mod.rs.bak`.

## What changed and why it saves Toffoli

1. **`SUB4_PP_REPLAY_FLAG_COMPARE` 22 → 20**, a `set_default_env` pin in
   `build()`, `src/point_add/mod.rs`. It is read by `replay_flag_compare()`
   in `src/point_add/pingpong_div.rs`, whose own fallback is also 22.
   - The window is used at three sites: the divide cell
     `signed_mod_add_pm_halve_fused`, the multiply cell
     `signed_mod_double_add_pm_fused`, and the unfused `signed_mod_add_pm`.
     Each site runs:
     ```
     b.hmr(overflow, phase);                       // X-measure the flag, reset it
     cmp_lt_phase_conditioned(b,
         &target[N - k..], &source[N - k..], phase); // under push_condition(phase)
     ```
   - After the add, the overflow flag equals `[target < source]`, the carry
     out of `target + source`. The `hmr` leaves the phase `(-1)^(phase·flag)`.
     The conditioned compare recomputes `[target < source]` from the top `k`
     bits only, applies a Z with it, and unwinds its own carries, which
     cancels that phase.
   - The compare costs about `k` Toffoli and runs only on shots where
     `phase = 1`, about half of them. So each bit removed saves about 0.5
     executed Toffoli per replay round. See
     [measurement-uncompute](../concepts/measurement-uncompute.md) and
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
2. **Tail nonce:** `SUB4_PINGPONG_TAIL_NONCE` default 41032007408473 →
   1562067597.
3. **New file `src/point_add/mod.rs.bak`** (5,624 lines). It is a copy of the
   base's `mod.rs`, byte for byte (ignoring line endings). It is not part of
   the module tree, so it is not compiled and has no effect on the circuit.
   REgonLevy's next commit, [`edeed3f`](edeed3f.md), keeps it and deletes
   three older stale snapshots.

## Why it is still correct, and what it risks

- **Probabilistic.** The truncated compare gets the flag wrong when `target`
  and `source` agree on all of their top `k` bits, which happens at about
  2^-k per call. Then the phase repair is wrong. Going from 22 to 20 bits
  roughly quadruples that per-call rate.
- A wrong repair leaves no classical error, only a phase error. It is caught
  by the phase channel, as phase garbage in that 64-shot batch.
- Because the late replay rounds have narrow walk registers, the failure rate
  is not flat across rounds (see
  [pingpong-division](../concepts/pingpong-division.md)). Later commits shape
  this window per round instead of pinning one value.
- The shipped nonce `1562067597` draws a clean set: 0 classical, 0 phase and
  0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is a narrower truncated compare, so this is
comparator/width truncation. The backup file has no circuit effect.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 79e7afa -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 79e7afa 52da1ec -- src/point_add` is
   5,628 lines in 2 files, of which 5,624 are the new backup file.
2. **Copy the backup file from the commit:**
   `git checkout 52da1ec -- src/point_add/mod.rs.bak`. It is an uncompiled
   copy of the base's `mod.rs`, too large to inline.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It covers `mod.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol 52da1ec -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1266 qubits
   - 904,740 average Toffoli (rounded)
   - score 1,145,400,840
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `1562067597` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index c6a4ec4..926538b 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2502,7 +2502,7 @@ pub fn build() -> Vec<Op> {
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
+            .unwrap_or(1562067597);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
```

