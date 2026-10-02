# dd103cd — Cut the dialog-GCD step count from 399 to 396, one fewer log block (1698 → 1693 qubits)

| | |
| --- | --- |
| Contestant | M3kko |
| Date | 2026-06-02 |
| Submission | `3b5d02e` |
| Commit | `dd103cd091d8dd57dd87f3d5570a9a076767bfbc` |
| Result | 1693 qubits × 1,697,177 Toffoli = **2,873,320,661** |
| Base | `27530d2` (pldallairedemers): 1698 qubits × 1,703,258 Toffoli = 2,892,132,084 |
| Change vs base | qubits −5, Toffoli −6,081, score −18,811,423 |
| Leaderboard Δ | −9,151,501, measured against the frontier at the time, `ad02935` (1698 × 1,697,569), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog GCD runs a fixed number of steps, `DIALOG_GCD_ACTIVE_ITERATIONS`.
The count must be large enough that every input's GCD has finished by the last
step. This commit lowers it from 399 to 396.

- **Toffoli.** Each dropped step saves about 2,000 Toffoli, almost all of it in
  the full-width apply loops.
- **Qubits.** The log is packed three steps per 5-qubit block, so 396 steps
  need one block fewer: 132 blocks instead of 133. That is 5 fewer qubits at
  the peak.
- **Cost.** Inputs whose GCD needs more than 396 steps now give wrong
  results.

The commit's own comment calls this a "[redteam PoC — sandbox only]". It says
the circuit "is then wrong on ~3e-4 of inputs, but its own Fiat-Shamir seed
samples around the failures". The reroll stays at 0, and that seed happens to
draw a test set with no failing input. The change was promoted, and later
commits built on it ([`0261289`](0261289.md)).

## What changed and why it saves Toffoli and qubits

`configure_ecdsafail_submission_route()` in `src/point_add/mod.rs` changes
`set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "399")` to `"396"` and adds
the red-team comment. Nothing else changes.

That one number drives every loop of the route; see [`4b9cfbb`](4b9cfbb.md):

- **Loops.** The tobitvector walk, its reverse, the apply and the reverse
  apply all run `for step in 0..dialog_gcd_active_iterations()`, in both GCD
  pairs.
  - The three dropped steps are 396–398. Their walk width is only 4 bits, so
    the walk part of each costs only a few dozen Toffoli.
  - The apply part is full width. In pair 2, one apply step costs about 950
    CCX:
    - `mod_double_inplace_fast`: 69
    - materialized add load: 256
    - raw 257-bit sum: 256
    - overflow fold: 72
    - 20-bit clean compare: 40
    - cswap: 256
  - The pair-1 reverse-apply step costs about the same, plus a second clean
    compare.
  - Together that is about 2,000 Toffoli per dropped step.
- **Log size.** `dialog_gcd_compressed_sidecar_blocks()` is
  `ceil(iterations / 3)`. It drops from 133 to 132, so the compressed log
  shrinks from 665 to 660 qubits. That saves 5 qubits at the peak. It also
  removes 8 compressor calls, at 9 CCX each.

The total is −6,081 Toffoli, about 2,000 for each of the three steps.

## Why it is still correct, and what it risks

This is not value-exact. A binary GCD of (p, v) needs a variable number of
steps. The route assumes that after `ACTIVE_ITERATIONS` steps u = 1 and
v = 0. The terminal-reuse code relies on that: it frees u after `x(u[0])`
and later re-seeds it.

An input that has not converged by step 396 leaves the walk unfinished:

- the replayed product is wrong, which is a classical failure;
- the "terminal" registers are not in their assumed state, which is ancilla
  garbage.

Other notes in the tree give the scale of the risk:

- The memory note added in [`ad02935`](ad02935.md) calls 399 the
  "convergence floor (397 -> 1 input fails to converge)".
- The commit comment estimates a failure rate of about 3·10^−4 of inputs,
  which is about 2.7 expected failing shots per 9,024-shot draw.
- [`9805d0c`](9805d0c.md)'s note reports that 396 iterations on another line
  failed for rerolls 0–12 and 21.

The shipped reroll 0 happens to draw a clean set: 0 classical, 0 phase and
0 ancilla failures. This is the clearest early case of buying score with
Lambda. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this as comparator/width truncation. The diff truncates no
comparator and no register width. It shortens the GCD's fixed loop bound,
which is an iteration-count truncation. The nearest existing type is the
"truncation" family it was put in. A label like "iteration/loop-bound
truncation" would describe it more precisely. The qubit saving is a side
effect of the shorter log, not a separate lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 27530d2 -- src/point_add`.
   - Do not start from the git parent `ad02935`. This commit was built on
     `27530d2`.
   - Against the parent, the diff is 224 lines. It would also revert
     Gajesh2007's fold truncation, compressor dedup and measured underflow
     clear from [`ad02935`](ad02935.md).
   - Against `27530d2`, `git diff --ignore-cr-at-eol 27530d2 dd103cd -- src/point_add`
     is 7 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol dd103cd -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or other route environment variables set. Expect:
   - 1693 qubits
   - 1,697,177 average Toffoli (rounded)
   - score 2,873,320,661
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL` = 0 and an identical op stream.
Any other change needs a new reroll search, and at 396 steps clean seeds are
rare.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6e65961..585f9a9 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -28408,7 +28408,12 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_COMPARE_BITS", "62");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "399");
+    // [redteam PoC — sandbox only] truncate inversion 399 -> 396: drops ~3 worst-case
+    // iterations, lowering Toffoli AND peak qubits (1698 -> 1693). The circuit is then
+    // wrong on ~3e-4 of inputs, but its own Fiat-Shamir seed samples around the failures,
+    // so it passes the gate at a better score. Demonstrates the verifier promotes an
+    // incorrect circuit. Revert to "399" to restore the pristine current-best.
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "396");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
```

