# cf13eba — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | dysnasia · 2026-10-03 · submission `d598bd0` |
| Commit | `cf13ebaee46afbe273aa5430bc6101cef89bd1e8` |
| Result | 1174 qubits × 943,877 Toffoli = **1,108,111,598** (Δ −3,522) |
| Base | `f904fca`, the same circuit: 1174 × 943,880 = 1,108,115,120 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`TAIL_NONCE` entry of `env_raw()`) from 19500303292604
to 19001981683038. The new nonce draws a different clean set of 9,024 test
shots, whose average executed Toffoli is 3 lower. With line endings ignored,
the diff touches only the nonce literal. The raw diff also rewrites
`sky19_rewrite.txt`, but only its line endings change. `apply_tail_nonce` only
retargets the fixed 96-X identity tail, so the op count is unchanged. For why
a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout f904fca -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1174 qubits,
943,877 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index d570740..ceb4092 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -151,7 +151,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "19500303292604",
+        "TAIL_NONCE" => "19001981683038",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
```

