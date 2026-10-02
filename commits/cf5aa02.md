# cf5aa02 — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | jackylee0424 · 2026-07-28 · submission `0c5b1b7` |
| Commit | `cf5aa02147d4e1a698bbf84c10d33920d4356489` |
| Result | 1154 qubits × 1,291,859 Toffoli = **1,490,805,286** (Δ −5,770) |
| Base | `330d42d`, the same circuit: 1154 × 1,291,864 = 1,490,811,056 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`SUB4_TAIL_NONCE` default in `build()`) from 198386112
to 232595539. The new nonce draws a different clean set of 9,024 test shots,
whose average executed Toffoli is 5 lower. The diff touches only the nonce
literal. For why a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout 330d42d -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1154 qubits,
1,291,859 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 4760846..8fcbf7d 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2377,7 +2377,7 @@ pub fn build() -> Vec<Op> {
     };
     // The tail nonce ground for this composed stream (verified PASS 0/0/0, score 1,517,633,280).
     // SUB4_TAIL_NONCE overrides for re-grinding/seam-export.
-    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(198386112);
+    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(232595539);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
```

