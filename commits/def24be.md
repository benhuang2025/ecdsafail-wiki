# def24be — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | odinfree (co-author tag: welttowelt) · 2026-08-22 · submission `4269cf6` |
| Commit | `def24beb10d6afb381f5a4477914505d8b3eebac` |
| Result | 1278 qubits × 919,788 Toffoli = **1,175,489,064** (Δ −6,390) |
| Base | `36f6ca0`, the same circuit: 1278 × 919,793 = 1,175,495,454 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`SUB4_PINGPONG_TAIL_NONCE` default in `build()`) from
48000070891 to 68001243769. The new nonce draws a different clean set of 9,024
test shots, whose average executed Toffoli is 5 lower. The diff touches only
the nonce literal. The next commit, [`a9af194`](a9af194.md), re-rolls the same
circuit again for another −3 Toffoli. For why a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout 36f6ca0 -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1278 qubits,
919,788 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f2ff163..3b9c12b 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2539,7 +2539,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(48000070891);
+            .unwrap_or(68001243769);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
```

