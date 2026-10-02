# d3e35ae — Steepen the dialog-GCD width slope to 0.711 and cut the comparator schedule margin from 7 to 6 bits

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-03 |
| Submission | `18f807e` |
| Commit | `d3e35ae2f12fa2e9b78dd61a7a45800f217a48a1` |
| Result | 1355 qubits × 1,775,211 Toffoli = **2,405,410,905** |
| Base | `cbe70bc` (git parent and frontier at the time, the author's previous submission): 1355 qubits × 1,776,467 Toffoli = 2,407,112,785 |
| Change vs base | qubits ±0, Toffoli −1,256, score −1,701,880 (leaderboard Δ −1,701,880) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two truncation knobs of the dialog GCD get one notch tighter. The slope of
the per-step width envelope goes from 0.710 to 0.711 bits per step, which
narrows 39 steps by 2 bits. The margin added to the per-step comparator
schedule goes from 7 to 6, which narrows the branch comparator by 1 bit on
the 50 steps where the schedule, not the global cap, sets its width (the
first 51 steps, except step 48). The saving is exactly 1,256 average Toffoli at the unchanged 1355-qubit peak.
The first reroll count was re-searched for the new op stream.

## What changed and why it saves Toffoli

All changes are in `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`:

1. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 710 → 711.**
   - `dialog_gcd_tobitvector_active_width(step)` is
     `256 − step × slope + margin` (margin 26), rounded **up** to an even
     number. A slope 0.001 steeper lowers it by up to 0.4 bits at step 395,
     and 39 steps (the first is step 76) cross an even boundary and lose 2
     bits: 78 bit-steps.
   - As in [`353ac6d`](353ac6d.md) and [`cbe70bc`](cbe70bc.md), each
     bit-step costs 3 Toffoli per pass (controlled swap, gated load, subtract
     carry) in four passes, so 78 × 12 = 936. On late steps the comparator is
     limited by the width, and it loses 30 bits: 30 × 4 = 120.
2. **`DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN`: 7 → 6.**
   - `dialog_gcd_compare_bits_for_step` returns
     `min(SCHEDULE[step] + margin, COMPARE_BITS = 56, active_width)`, where
     `SCHEDULE` is the baked 399-entry `DIALOG_GCD_PA9024_COMPARE_SCHEDULE`
     table of per-step comparator needs. On most mid-run steps the global cap
     of 56 binds, and on late steps the width does. The schedule term binds
     on the first 51 steps except step 48: their schedule entries are 49 or
     less, so `SCHEDULE + 6` is still below the cap. Those 50 steps lose 1
     bit each.
   - The comparator costs one CCX per bit in each of the four passes:
     50 × 4 = 200.
3. Total: 936 + 120 + 200 = 1,256, the measured saving.
4. **Reroll: `DIALOG_REROLL` 265503 → 12027.** `DIALOG_POST_SUB_REROLL`
   stays at 503292. These are counts of identity `X;X` pairs that re-seed the
   9,024 Fiat–Shamir test inputs without changing the circuit. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

The peak is not affected: early steps clamp at 256 bits, and the comparator
is not a peak binder in this tree.

## Why it is still correct, and what it risks

Both knobs are probabilistic.

- **Slope.** An input whose `u` or `v` is still wider than
  `active_width(step)` at a tightened step loses its top bits, and its
  transcript goes wrong.
- **Schedule margin.** The schedule records how many top bits each step's
  comparison needed on a reference sample, and the margin is the headroom
  above that. With one bit less, an input whose `u` and `v` agree on more
  leading bits than expected takes the wrong branch.
- Either failure shows up as classical failures, and as phase or ancilla
  garbage if the reverse pass no longer mirrors the forward one. λ rises.
- The shipped pair (12027, 503292) is clean: 0 classical, 0 phase and 0
  ancilla failures over all 9,024 shots, per the author. See
  [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).

## Classification rationale

Both circuit changes narrow registers or comparators on some GCD steps,
which is comparator/width truncation. The reroll change is the usual
companion.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout cbe70bc -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol cbe70bc d3e35ae -- src/point_add` is
   8 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol d3e35ae -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` keeps any
   value already in the environment. Expect:
   - 1355 qubits
   - 1,775,211 average Toffoli (rounded)
   - score 2,405,410,905
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=12027`,
`DIALOG_POST_SUB_REROLL=503292` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index b6cf785..d6355a3 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31068,7 +31068,9 @@ fn configure_ecdsafail_submission_route() {
     // low/mid-width GCD steps (below the 57 cap) for -452 executed Toffoli,
     // peak-neutral at 1434q, orthogonal to compare57. The late-game lineage ran
     // margin=5; the base had reverted to 7. Clean island at REROLL=1844/POST_SUB=3532.
-    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "7");
+    // Margin 7 -> 6 stacked on the WIDTH_SLOPE=711 tightening: narrows the per-step
+    // comparator on low/mid-width GCD steps, orthogonal to the slope envelope.
+    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "6");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "20");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "20");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
@@ -31235,10 +31237,10 @@ fn configure_ecdsafail_submission_route() {
     // 1,779,067 -> 1,778,555 (-512), peak-neutral at 1355q. The tighter
     // truncation re-rolls the Fiat-Shamir island; a 1-D reroll sweep (post_sub
     // fixed at the inherited 503292) lands a clean island at DIALOG_REROLL=101019.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "710");
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "711");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "265503");
+    set_default_env("DIALOG_REROLL", "12027");
     set_default_env("DIALOG_POST_SUB_REROLL", "503292");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

