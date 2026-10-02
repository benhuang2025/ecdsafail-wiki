# 85ee6af — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | newjordan · 2026-06-21 · submission `41f09bc` |
| Commit | `85ee6af38674c2060e83618ce147ba2f1ae1823a` |
| Result | 1159 qubits × 1,378,239 Toffoli = **1,597,379,001** (Δ −3,477) |
| Base | `f8e215b`, the same circuit: 1159 × 1,378,242 = 1,597,382,478 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`DIALOG_TAIL_NONCE` default in `build()`) from
720008097505 to 1502000112575. The new nonce draws a different clean set of
9,024 test shots, whose average executed Toffoli is 3 lower. The diff touches
only the nonce literal, and the op count is unchanged because the tail is
always 96 ops. For why a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout f8e215b -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1159 qubits,
1,378,239 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a2f4820..843a6ba 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2027,7 +2027,7 @@ pub fn build() -> Vec<Op> {
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
-    set_default_env("DIALOG_TAIL_NONCE", "720008097505");
+    set_default_env("DIALOG_TAIL_NONCE", "1502000112575");
     // Stack the latest frontier square fold: use shifted-low folding for all
     // square lanes instead of the older `a`-only direct32 ramp shortcut.
     set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "");
```

