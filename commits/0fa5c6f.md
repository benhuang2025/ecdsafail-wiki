# 0fa5c6f — Lower the square row cap from 166 to 165 bits (1193 → 1192 qubits)

| | |
| --- | --- |
| Contestant | jieyilong (model: GPT-5 Codex) |
| Date | 2026-06-13 |
| Submission | `a7ec174` |
| Commit | `0fa5c6f5f79c1cb14f046534c9ba12ab1d81e9fa` |
| Result | 1192 qubits × 1,412,425 Toffoli = **1,683,610,600** |
| Base | `bb579bb` (git parent, BitWonka): 1193 qubits × 1,412,391 Toffoli = 1,684,982,463 |
| Change vs base | qubits −1, Toffoli +34, score −1,371,863 (leaderboard Δ −1,371,863) |
| Family | Dead-Code and Redundancy Elimination → iteration/threshold tuning |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit changes one constant and the tail nonce. `SQUARE_ROW_MAX_SEG` is
the widest row of the `λ²` schoolbook square that is still added into the
product register in one piece. Wider rows are built in two windows, so that
only half the row's bits are materialised at once. Going from 166 to 165
moves the 166-bit row into the windowed path. The square's largest transient
row register shrinks by one bit, and the peak drops from 1193 to 1192 qubits.

The new window boundary adds one measured carry cleanup to each of the
forward and inverse squares. The measured cost is +34 Toffoli.

## What changed and why it saves qubits

- `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`:
  - `SQUARE_ROW_MAX_SEG`: 166 → 165.
  - Both `DIALOG_TAIL_NONCE` lines: 8400013080067 → 2107498317. Only the first
    line takes effect. The second gets a comment.
- **Mechanism** (`arith/multiply.rs`):
  - `schoolbook_square_symmetric_lowq_selfhosted` and its inverse handle
    row `i` (width `257 − i`) as follows. A row with `width ≤ MAX_SEG` is
    built monolithically, as a `width`-bit row register added into `tmp_ext`.
    Otherwise the row goes to `square_row_windowed_apply` with
    `ceil(width / MAX_SEG) = 2` windows.
  - Row `i = 91` (width 166) is the one that moves.
  - After this commit the largest monolithic row is 165 bits, and the largest
    window is ⌈257/2⌉ = 129 bits. The square's high-water is set by the
    largest monolithic row.
  - This only lowers the global peak because, after
    [`bb579bb`](bb579bb.md), the square was the phase holding it. See
    [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
- **Cost.**
  - Each new boundary needs a measured carry cleanup: 21 rebuilt row bits and
    a 21-bit compare that runs on about half the shots (see
    [`d636d62`](d636d62.md)). That is about 31.5 Toffoli for each of the two
    squares.
  - The measured net is +34, less than that estimate. The windowed add and
    the monolithic hosted add of the same row do not cost exactly the same,
    and the new Fiat–Shamir stream shifts the average measured outcomes. I
    did not isolate the two.

## Why it is still correct, and what it risks

- The windowed row adds the same value as the monolithic one, so the change
  is value-exact.
- The new risk is the added truncated cleanup. A tie in the top 21 bits of
  the partial sum and the row window gives a wrong phase repair, which shows
  as a phase failure.
- The shipped nonce `2107498317` draws a clean set: 9,024 shots, 0 classical,
  0 phase and 0 ancilla failures. The author found it with a GPU GCD-clean
  hunt and then ran full validation. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census calls this iteration/threshold tuning. What the diff actually does
is lower a peak dial on the square's row windowing: one more row is built in
windows to save a qubit. That fits **Windowing → windowed carry/shift
blocks** better, or Register and Scratch Allocation if it is read as a
peak-budget change. The header keeps the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout bb579bb -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol bb579bb 0fa5c6f -- src/point_add` is
   8 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 0fa5c6f -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with none of the
   route's variables (`DIALOG_*`, `SQUARE_*`, `KAL_*`, `KARA_*`, `ROUND84_*`,
   `R84_*`) set, because `set_default_env` only fills unset variables. Expect:
   - 1192 qubits
   - 1,412,425 average Toffoli (rounded; 1,412,424.779 in the submission note)
   - score 1,683,610,600
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `2107498317` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index cf03467..e0bebd2 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1015,7 +1015,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR", "1");
     set_default_env("ROUND84_KEEP_QUOTIENT_PRODUCT", "1");
     set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "18");
-    set_default_env("DIALOG_TAIL_NONCE", "8400013080067");
+    set_default_env("DIALOG_TAIL_NONCE", "2107498317");
     set_default_env("DIALOG_GCD_SKIP_ZERO_EDGE_CSHIFT", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_HOST_REVERSE_RAW_BLOCK", "1");
@@ -1364,7 +1364,7 @@ fn configure_ecdsafail_submission_route() {
     // carry-recovery comparators. Value-exact: the same product lands in tmp_ext
     // (verified: ancilla-garbage 0; SQUARE_ROW_MAX_SEG=0 restores the bit-exact
     // 1284 base). Net: peak 1284 -> 1226, score 1.821e9 -> 1.771e9.
-    set_default_env("SQUARE_ROW_MAX_SEG", "166");
+    set_default_env("SQUARE_ROW_MAX_SEG", "165");
     set_default_env("DIALOG_GCD_K5_CLEAN_BLOCK", "1");
     set_default_env("DIALOG_GCD_K5_FREE_CLEAN_BLOCK_DURING_SHIFT", "1");
     set_default_env("DIALOG_GCD_FOLD_PARK_LOW_CARRIES", "1");
@@ -1467,7 +1467,9 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "8400013080067");
+    // q1192 lower-qubit island from the ad4cf86/K5 clean-block base.
+    // Validated full 0/0/0 at SQUARE_ROW_MAX_SEG=165.
+    set_default_env("DIALOG_TAIL_NONCE", "2107498317");
     set_default_env("ROUND84_FOLD_FAST_ADD", "0");  // round84 Solinas-fold small adders coherent->measured-fast (-1,434 exec-T, peak-neutral 1285)
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_FOLD_MAJ1", "1");
```

