# dda7bfd — Narrow the GCD branch comparator from 74 to 72 bits

| | |
| --- | --- |
| Contestant | robertkodra |
| Date | 2026-06-05 |
| Submission | `1664274` |
| Commit | `dda7bfd21e71e498b64b8c3e206f5ffb863cfafa` |
| Result | 1390 qubits × 1,531,871 Toffoli = **2,129,300,690** |
| Base | `5174a69` (PhantasticUniverse): 1390 qubits × 1,533,415 Toffoli = 2,131,446,850 |
| Change vs base | qubits ±0, Toffoli −1,544, score −2,146,160 |
| Leaderboard Δ | −811,760, measured against the frontier at the time, `98416e4` (1390 × 1,532,455 = 2,130,112,450), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Each step of the binary GCD decides whether to swap its two registers by
comparing them. The comparison only looks at the top `DIALOG_GCD_COMPARE_BITS`
bits of the current window. This commit lowers that cap from 74 to 72. On the
first 193 GCD steps (0 to 192), where the window is wider than 72 bits, every comparison
gets 2 bits shorter. One comparator bit is one Toffoli, and the comparator runs
in four passes, so the saving is 386 bit-steps × 4 = 1,544 Toffoli. That is
exactly the measured drop. Qubits are unchanged. The tail nonce was re-hunted.

The author started from the frontier `98416e4` and also put its width slope back
from 1005 to 1004. The resulting tree is `5174a69` plus the comparator change.

## What changed and why it saves Toffoli

**Background.** The circuit is the dialog-GCD route (`emit_dialog_gcd_raw_pa`
in `src/point_add/mod.rs`). Two calls each run a reversible binary GCD on
(u, v) = (p, factor): the quotient dy/dx and the product with c = ox − Rx. Each
call has a forward pass that records branch bits, an apply pass that replays
them, and a reverse pass that erases them. Each GCD step compares, swaps,
subtracts and halves, using only the low `active_width(step)` bits.
[98416e4](98416e4.md) lists one step and the width formula.

**The comparator.** The forward step computes
`b0_and_b1 = v[0] AND (u > v)` with
`dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted`. It runs
`ccx_cmp_lt_into_fast_borrowed_carries` on `v[aw−k..aw]` and `u[aw−k..aw]`, where
`aw` is the active width and `k = dialog_gcd_compare_bits_for_step(step, aw)`.

- `DIALOG_GCD_PA9024_COMPARE_SCHEDULE` is `0` in this tree, so `k` is just
  `min(DIALOG_GCD_COMPARE_BITS, aw)`.
- The comparator spends one Toffoli per bit on its carry chain, plus one CCX
  into the target. It erases its carries with `hmr` and `cz_if`, which costs no
  Toffoli.
- The reverse pass recomputes the same comparator to erase `b0_and_b1`.
- So each comparator bit costs 1 Toffoli per step in each of four passes: forward
  and reverse, in each of the two GCD calls.

**The change.** In `configure_ecdsafail_submission_route()`:

- `DIALOG_GCD_COMPARE_BITS`: 74 → 72.
  - The window is wider than 72 bits at steps 0 to 192 (width = 2·⌈(265 − 1.004·step)/2⌉,
    capped at 256). Summing the drop in `min(cap, width)` over the 259 steps
    gives 386 bit-steps, and 386 × 4 = 1,544.
  - Later steps already have a window of 72 bits or less, so they are not
    affected.
- `DIALOG_TAIL_NONCE`: 7046 → 73633164035081. This is the fixed-length 48-bit
  identity tail that only reselects the test set. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

The truncated comparator returns "not greater" when u and v agree on all `k`
compared bits but u is larger lower down. Then the swap is skipped, `v − u` goes
negative and wraps, and the GCD is wrong from that step on. That shows up as a
classical failure, with ancilla garbage after it.

Early in the walk both values are close to 256 bits, so 72 compared bits are all
significant. The chance of a tie is about 2^-72 per step, which is negligible.
Later, the window's top bits lie above the values, and the useful compared width
shrinks. A later contestant, alexander-sei in [`fc27501`](fc27501.md), ran a
classical filter over 300k inputs and found no mis-decision at caps down to 52.
So this lever is close to free in λ, and the nonce hunt is driven by the other
truncations.

The shipped nonce `73633164035081` draws a clean set: 0 classical, 0 phase and
0 ancilla failures over all 9,024 shots.

## Classification rationale

The only circuit change shortens a comparator, which is comparator/width
truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 5174a69 -- src/point_add`.
   - The git parent is `98416e4`, robertkodra's own previous tree with width
     slope 1005. Against it, the diff also sets `DIALOG_GCD_WIDTH_SLOPE_X1000`
     back from 1005 to 1004, which reverts that commit.
   - Against `5174a69`, `git diff --ignore-cr-at-eol 5174a69 dda7bfd -- src/point_add`
     is 4 changed lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol dda7bfd -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set.
   `set_default_env` only fills variables that are unset. Expect:
   - 1390 qubits
   - 1,531,871 average Toffoli (rounded)
   - score 2,129,300,690
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `73633164035081` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 124dbbf..56700dd 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31292,7 +31292,7 @@ fn configure_ecdsafail_submission_route() {
     // island documented below.
     // Branch comparator 58 -> 57: -1,064 executed Toffoli, peak-neutral at 1434q,
     // stacked on the active395 base. Clean island at REROLL=4959 / POST_SUB=5983.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "74");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "72");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
@@ -31463,7 +31463,7 @@ fn configure_ecdsafail_submission_route() {
     // clean island: validated 0/0/0 over all 9024 shots at 1350q x 1,763,987 T.
     // Fiat-Shamir island for the K=2 apply rebalance above: 0/0/0 over all
     // 9024 shots at 1390q x 1,630,487 T.
-    set_default_env("DIALOG_TAIL_NONCE", "7046");
+    set_default_env("DIALOG_TAIL_NONCE", "73633164035081");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

