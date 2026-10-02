# fdb103e — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | jackylee0424 · 2026-06-19 · submission `2c0283c` |
| Commit | `fdb103e18702e64fb32dd86135a6e60763f8a95c` |
| Result | 1165 qubits × 1,413,439 Toffoli = **1,646,656,435** (Δ −46,600) |
| Base | `f265bb1`, the same circuit: 1165 × 1,413,479 = 1,646,703,035 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`DIALOG_TAIL_NONCE` default in `build()`) from 287 to
2686. The new nonce draws a different clean set of 9,024 test shots, whose
average executed Toffoli is 40 lower. The diff touches only that literal and
the comment above it, and the emitted op count is unchanged (10,662,471). For
why a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout f265bb1 -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1165 qubits,
1,413,439 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a7f7fbc..dd4fbe2 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1983,11 +1983,11 @@ pub fn build() -> Vec<Op> {
     //     Toffoli cut while keeping peak qubits at 1166.
     //   - TLM_GCD_ADAPTIVE_LAYOUT_MARGIN=0: GCD-adaptive layout at margin 0.
     // The tail nonce reseeds the 9024 Fiat-Shamir draws so all land in the
-    // schedule-supported set: nonce 287 validates 0/0/0 over all 9024
-    // shots at 1165q x 1,413,479.340 => 1,413,479 x 1165 = 1,646,703,035.
+    // schedule-supported set: nonce 2686 validates 0/0/0 over all 9024
+    // shots at 1165q x 1,413,439.226 => 1,413,439 x 1165 = 1,646,656,435.
     set_default_env("LUD_EXTRA_FOLD_VENTS", "2");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "16");
-    set_default_env("DIALOG_TAIL_NONCE", "287");
+    set_default_env("DIALOG_TAIL_NONCE", "2686");
     set_default_env("TLM_COUT_LAYOUT_SEARCH", "1");
     set_default_env("TLM_COUT_LAYOUT_MARGIN", "0");
     set_default_env("TLM_COUT_LAYOUT_FORCE_M1_KS", "129");
```

