# ffc4e07 — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | benhuang2025 · 2026-08-21 · submission `9493ec0` |
| Commit | `ffc4e078c3fb4cf765edbc1678db6cada5e11813` |
| Result | 1279 qubits × 944,120 Toffoli = **1,207,529,480** (Δ −11,511) |
| Base | `f3b2f1f`, the same circuit: 1279 × 944,129 = 1,207,540,991 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`SUB4_PINGPONG_TAIL_NONCE` default in `build()`) from
3004060 to 320000001. The new nonce draws a different clean set of 9,024 test
shots, whose average executed Toffoli is 9 lower. The diff touches only the
nonce literal. For why a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout f3b2f1f -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1279 qubits,
944,120 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index da54fe0..22d31f3 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2539,7 +2539,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(3004060);
+            .unwrap_or(320000001);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
```

