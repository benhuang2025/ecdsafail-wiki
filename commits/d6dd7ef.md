# d6dd7ef — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | dysnasia · 2026-10-03 · submission `ee41004` |
| Commit | `d6dd7ef7e1b7aa4eb2de5066f75482d9b355c0e3` |
| Result | 1174 qubits × 943,826 Toffoli = **1,108,051,724** (Δ −5,870) |
| Base | `6f2b3a6`, the same circuit: 1174 × 943,831 = 1,108,057,594 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`TAIL_NONCE` entry of `env_raw()`) from 20001517057646
to 20500217557371. The new nonce draws a different clean set of 9,024 test
shots, whose average executed Toffoli is 5 lower. With line endings ignored,
the diff touches only the nonce literal. The raw diff also rewrites
`sky20_rewrite.txt`, but only its line endings change. `apply_tail_nonce` only
retargets the fixed 96-X identity tail, so the op count is unchanged. For why
a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout 6f2b3a6 -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1174 qubits,
943,826 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6b5ecea..d363c02 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -151,7 +151,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "20001517057646",
+        "TAIL_NONCE" => "20500217557371",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
```

