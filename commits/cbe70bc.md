# cbe70bc — Steepen the dialog-GCD width-envelope slope from 0.708 to 0.710 bits per step

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-03 |
| Submission | `738af19` |
| Commit | `cbe70bca3a59a6e8d6eb0672afe5a4f3b92a9748` |
| Result | 1355 qubits × 1,776,467 Toffoli = **2,407,112,785** |
| Base | `353ac6d` (git parent and frontier at the time, the author's previous submission): 1355 qubits × 1,778,555 Toffoli = 2,409,942,025 |
| Change vs base | qubits ±0, Toffoli −2,088, score −2,829,240 (leaderboard Δ −2,829,240) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This pushes the author's own [`353ac6d`](353ac6d.md) further. Each
dialog-GCD step works only on the low `active_width(step)` bits of `u` and
`v`, a linear envelope `256 − step × slope + margin`. The slope goes from
0.708 to 0.710 bits per step. The envelope then sits up to 0.79 bits lower
by the last step, and after rounding to an even width, 78 of the 396 steps
lose 2 bits. That saves 2,088 average Toffoli at the unchanged 1355-qubit
peak. The first reroll count was re-searched for the new op stream.

(The submission note describes the change as 707.5 → 710 against `da42ce2`,
−2,600 Toffoli. The commit itself was built on `353ac6d`, which already had
708.)

## What changed and why it saves Toffoli

Both changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`:

1. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 708 → 710.**
   - `dialog_gcd_width_slope()` reads this variable divided by 1000 (the
     built-in default is 0.7075). It is used in
     `dialog_gcd_tobitvector_active_width(step)`:
     `ideal = 256 − step × slope + margin` (margin 26 here), rounded **up**
     to an even number and clamped to [1, 256].
   - A steeper slope lowers `ideal` by `0.002 × step`. Where that crosses an
     even boundary, the step drops 2 bits: 78 steps (the first is step 48),
     156 bit-steps in total.
   - Each bit-step costs about 3 Toffoli per pass (controlled swap, gated
     load and subtract carry), in four passes (forward and reverse, for each
     of the two GCD calls): 156 × 12 = 1,872. On the late steps where the
     width is below the comparator width, the comparator shrinks with it, by
     54 bits in total: 54 × 4 = 216. 1,872 + 216 = 2,088, exactly the
     measured saving.
   - The peak is not affected, because early steps clamp at 256 bits.
2. **Reroll: `DIALOG_REROLL` 101019 → 265503.** `DIALOG_POST_SUB_REROLL`
   stays at 503292. These are counts of identity `X;X` pairs that re-seed the
   9,024 Fiat–Shamir test inputs without changing the circuit. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

The envelope is an empirical bound, not a proof. The submission note cites a
binary-GCD degree bound from the literature as the reason a steeper slope
should be safe, but the circuit's own safety still rests on the test draw.
An input whose `u` or `v` is still wider than `active_width(step)` at one of
the 78 tightened steps loses its top bits. Its transcript then goes wrong,
which shows up as classical failures (and as phase or ancilla garbage if the
reverse pass no longer mirrors the forward one). Four times as many steps are
tightened as in `353ac6d`, so λ rises more.

The shipped pair (265503, 503292) is clean: 0 classical, 0 phase and 0
ancilla failures over all 9,024 shots, per the author. See
[comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).

## Classification rationale

The only circuit change narrows the registers on some GCD steps, which is
comparator/width truncation. The reroll change is the usual companion.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 353ac6d -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 353ac6d cbe70bc -- src/point_add` is
   4 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol cbe70bc -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` keeps any
   value already in the environment. Expect:
   - 1355 qubits
   - 1,776,467 average Toffoli (rounded)
   - score 2,407,112,785
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=265503`,
`DIALOG_POST_SUB_REROLL=503292` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 523994b..b6cf785 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31235,10 +31235,10 @@ fn configure_ecdsafail_submission_route() {
     // 1,779,067 -> 1,778,555 (-512), peak-neutral at 1355q. The tighter
     // truncation re-rolls the Fiat-Shamir island; a 1-D reroll sweep (post_sub
     // fixed at the inherited 503292) lands a clean island at DIALOG_REROLL=101019.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "708");
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "710");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "101019");
+    set_default_env("DIALOG_REROLL", "265503");
     set_default_env("DIALOG_POST_SUB_REROLL", "503292");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

