# 76fdaf2 — Cut the dialog GCD from 259 to 258 steps on the fold-fusion tree

| | |
| --- | --- |
| Contestant | newjordan |
| Date | 2026-06-06 |
| Submission | `356496a` |
| Commit | `76fdaf2bae21147c77971e12b0c743ab3b29fccf` |
| Result | 1313 qubits × 1,512,823 Toffoli = **1,986,336,599** |
| Base | `c80fc1c` (the author's previous submission, git parent and frontier at the time): 1313 qubits × 1,515,772 Toffoli = 1,990,208,636 |
| Change vs base | qubits ±0, Toffoli −2,949, score −3,872,037 (leaderboard Δ −3,872,037) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog GCD runs a fixed number of binary-GCD steps. With K=2, each step
can strip two trailing zeros. This commit lowers the step count from 259 to
258. The last step disappears from every forward walk, reverse walk and apply
pass. The walk part of that step is cheap, because the width envelope is near
its floor there. The apply part is a full 256-bit step on the Bézout register
`y`. The saving is 2,949 average Toffoli at the same 1313 qubits. The cost is
that inputs needing all 259 steps no longer finish. The tail nonce was
re-hunted to avoid them.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_ACTIVE_ITERATIONS`: 259 → 258.**
   - `dialog_gcd_active_iterations()` is the loop bound of every forward
     transcript walk (`..._tobitvector_steps`), its reverse, and the forward
     and reverse apply loops on `(x, y)`.
   - In the walk, the last step is narrow: `active_width(258) = 6` bits under
     the envelope `256 − 1.014·step + 10`. Its branch compare, cswap,
     controlled subtract and shift are only a few Toffoli.
   - In each apply pass the step is full width. Forward, it is one fused K=2
     double (about 341 Toffoli, see [`8a47cf5`](8a47cf5.md)), a controlled
     256-bit modular add with its fold and its 23-bit clean compare, and a
     256-wire cswap. The reverse apply has the mirror-image halve and
     subtract.
   - The measured total is −2,949. The pre-fusion cut of the same kind,
     [`229aeed`](229aeed.md) (260 → 259), measured −3,116. The difference of
     about 170 is roughly what fusion removed from one step's double and
     halve (about 99), plus the narrower comparators and windows since then.
   - The transcript is pair-compressed (`DIALOG_GCD_K2_PAIR_COMPRESS=1`), so
     its size depends on the step count. Peak qubits did not move: 1313 both
     before and after.
2. **`DIALOG_TAIL_NONCE`: 44825000439 → 45100002269.**

## Why it is still correct, and what it risks

The walk must bring `(u, v)` to its terminal state within the fixed step
count. An input whose K=2 binary GCD needs 259 steps no longer converges.
The transcript is then incomplete, `y` is not the quotient, and the reverse
walk leaves the registers dirty. That shows up as a classical mismatch, and
often also as phase or ancilla garbage. Such inputs are rare, but at a
fixed nonce they are what the test draw must avoid. The new nonce
`45100002269` passed the author's remote watcher and the trusted evaluation:
9,024 of 9,024 shots, with 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only lever is the GCD step count, which is iteration/threshold tuning.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout c80fc1c -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol c80fc1c 76fdaf2 -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 76fdaf2 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*` or `DIALOG_*` environment variables set. Expect:
   - 1313 qubits
   - 1,512,823 average Toffoli (rounded)
   - score 1,986,336,599
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=45100002269` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 507ad69..bcdbfbc 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -32753,7 +32753,7 @@ fn configure_ecdsafail_submission_route() {
     // 260 -> 259 after the 1320q apply teardown: saves one GCD body/reverse row.
     // Stacked with KAL_DOUBLE_CARRY_TRUNC_W=22, the nonce below lands the clean
     // 1320q island while improving the custom-five seed's Toffoli count.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "259");
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "258");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -32971,7 +32971,7 @@ fn configure_ecdsafail_submission_route() {
     // 1000001157 lands a clean island, validated 0/0/0 over all 9024 shots at
     // 1313q x 1,535,885 T = 2,016,617,005 (official ecdsafail run).
     set_default_env("DIALOG_GCD_SELECTED_BODY_NOCIN", "1");
-    set_default_env("DIALOG_TAIL_NONCE", "44825000439");
+    set_default_env("DIALOG_TAIL_NONCE", "45100002269");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

