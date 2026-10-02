# 4cd1b2f — Nonce re-roll only (no circuit change)

| | |
| --- | --- |
| Contestant · Date | odinfree · 2026-06-25 · submission `4397484` |
| Commit | `4cd1b2f8f409949f20476d23889ea6dd0b02ae29` |
| Result | 1153 qubits × 1,368,474 Toffoli = **1,577,850,522** (Δ −3,459) |
| Base | `9b09c7e`, the same circuit: 1153 × 1,368,477 = 1,577,853,981 |
| Family | Verifier Search → nonce/island reroll |
| Concepts | [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |

## Summary

This commit makes no optimization. It only changes the tail nonce in
`src/point_add/mod.rs` (`Q1153_SECOND512_SUBMISSION_NONCE`, which sets
`DIALOG_TAIL_NONCE`) from 810197699946 to 930308424560. The new nonce draws a
different clean set of 9,024 test shots, whose average executed Toffoli is 3
lower. The diff touches only nonce literals: the same value also goes into two
fallback `DIALOG_TAIL_NONCE` defaults (one in `trailmix_ludicrous/mod.rs`)
that never take effect because the variable is already set. The emitted op
count is unchanged (10,203,570). For why a nonce moves the score, see
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Reproduce

From `git checkout 9b09c7e -- src/point_add`, apply the patch below with
`git apply --ignore-whitespace`. `./benchmark.sh` should give 1153 qubits,
1,368,474 average Toffoli and 0 / 0 / 0 failures.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a53956b..c142639 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1081,7 +1081,7 @@ fn set_default_env(name: &str, value: &str) {
 // Q1153 second-512 scan route. To submit a clean hit from the current hunt,
 // update this nonce, build with no shell env overrides, run `ecdsafail run`,
 // and submit only if it remains 0 / 0 / 0.
-const Q1153_SECOND512_SUBMISSION_NONCE: &str = "810197699946";
+const Q1153_SECOND512_SUBMISSION_NONCE: &str = "930308424560";
 
 fn configure_q1153_second512_submission_defaults() {
     set_default_env("DIALOG_TAIL_NONCE", Q1153_SECOND512_SUBMISSION_NONCE);
@@ -2149,7 +2149,7 @@ pub fn build() -> Vec<Op> {
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
-    set_default_env("DIALOG_TAIL_NONCE", "2430844");
+    set_default_env("DIALOG_TAIL_NONCE", "930308424560");
     set_default_env("TLM_FOLD_TAIL_CINC", "1");
     set_default_env("TLM_CODEC_DIAMOND_MCX", "1");
     set_default_env("SINGLE_CCX_FANOUT_DISABLE", "1");
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index 2ccd621..ca42a04 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -362,7 +362,7 @@ fn install_q1153_submission_defaults() {
         ("TLM_FOLD_CHUNK_ZERO_CIN", "1"),
         ("TLM_FFG_MAX_G", "47"),
         ("TLM_APPLY_ADD_SKIP_LASTK", "1"),
-        ("DIALOG_TAIL_NONCE", "2430844"),
+        ("DIALOG_TAIL_NONCE", "930308424560"),
     ] {
         if name == "DIALOG_TAIL_NONCE" && std::env::var_os(name).is_some() {
             continue;
```

