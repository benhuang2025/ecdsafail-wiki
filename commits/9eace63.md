# 9eace63 — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | dysnasia · 2026-10-04 · submission `7555085` |
| Commit | `9eace6349ebad0fde94d64974855f8abdad2ee0c` |
| Result | 1173 qubits × 944,578 Toffoli = **1,107,989,994** (Δ −11,730) |
| Base | `83d0f70` (git parent, the author's q73c), the same circuit: 1173 × 944,588 = 1,108,001,724 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`"TAIL_NONCE"` in `env_raw()`) from 24700083572177 to
24700228103001. The new nonce draws a different clean set of 9,024 test shots,
whose average executed Toffoli is 10 lower (944,577.533 by the submission
note). The diff touches only the nonce literal. `apply_tail_nonce()` writes
the nonce into the `q_target` of the 96 trailing X ops, so the op count is
unchanged by construction, and the q73c recipe and its 105 rewrite rows
(`q73c_rewrite.txt`) are untouched. For why a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout 83d0f70 -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1173 qubits,
944,578 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index bab52e5..30d8f38 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -151,7 +151,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "24700083572177",
+        "TAIL_NONCE" => "24700228103001",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
```

