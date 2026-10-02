# 03d9ecd — Cut the tree-wide fold guard from 25 to 21 bits and buy λ back with wider replay folds

| | |
| --- | --- |
| Contestant | moscowchill |
| Date | 2026-09-27 |
| Submission | `11b05b8` |
| Commit | `03d9ecd2df6727d5f76939edc4cc9ed33216f344` |
| Result | 1250 qubits × 889,047 Toffoli = **1,111,308,750** |
| Base | `ea73b1a` (git parent, jackylee0424's frontier): 1250 qubits × 889,081 Toffoli = 1,111,351,250 |
| Change vs base | qubits ±0, Toffoli −34, score −42,500 (leaderboard Δ −42,500) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [pingpong-division](../concepts/pingpong-division.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit is a sell/buy package of three pins plus the nonce, all in
`src/point_add/mod.rs`.

- **Sell:** `FOLD_GUARD` goes from 25 to 21. This is the headroom above the
  constant in every truncated fold outside the replay cells: the coordinate
  shell, the square, and the divider's round-0/round-1 and endpoint folds.
  Each such fold gets 4 positions shorter, which saves Toffoli. Each fold's
  dropped-carry rate rises from about 2^-25 to about 2^-21, which spends λ.
- **Buys:** two replay-fold pins widen windows that `FOLD_GUARD` does not
  control. `PP_FOLD_WIDEN` goes from 0 to 64, so the first 64 replay rounds get
  one more fold bit. `PP_FOLD_PROFILE`'s 32-band goes from −1 to 0, so rounds
  whose walk width is 32–37 get one more bit. These cost Toffoli and give λ
  back.

The sell saves more than the buys cost. The net is 34 fewer average Toffoli at
the same 1250 qubits.

## What changed and why it saves Toffoli

Background for all three pins: [modular-fold](../concepts/modular-fold.md).

**1. `FOLD_GUARD`: "25" → "21"** (alphabetical list in `env_raw`).

`fold_guard()` is read in these places:
- **`modular::f_slice() = 33 + fold_guard()`, so 58 → 54.**
  - This is the slice used by `mod_addsub` and `mod_rsub_vented_loaded`, the
    coordinate-shell and square modular add/subs.
  - It is also used by the walk's round-0 lift and its reverse
    (`round0_correction`, `round0_correction_fused`, `round0_reverse`), by
    replay rounds 0 and 1 (`mod_halve_pm`, `mod_double_pm`, the seeds, and the
    `j_fuse` fusions, which are `f_slice + 1` wide), and by the endpoint's
    `conditional_mod_negate` and `endpoint_sparse_sub`.
- **`square.rs`:** the headroom of `window_add` (`top = shift + len + fold_guard()`)
  and of the WCIN windows. Each NAF window of the square gets 4 positions
  shorter.
- **`j_fuse::wcin_w()`:** the WCIN unit increment defaults to
  `fold_guard() + 1`, so 26 → 22 bits.
- **`pingpong::round1_window(m) = 31 + fold_guard()`:** the walk's round-1
  constant add and its receivers, so 56 → 52 bits.

Each of these is a truncated carry chain that costs about one Toffoli per
position. So every call site saves about 4 Toffoli. The replay cell folds of
rounds 2 and up are **not** affected. Their window is
`PP_REPLAY_FOLD_WINDOW` (54) plus the per-round offsets below.

**2. `PP_FOLD_WIDEN`: "0" → "64"** (pkgFdP block).
- `fold_offset(round)` adds `+1` when `round < fold_widen()`. That holds in
  both directions, because `Plan::fold_window` uses it for divide and multiply
  alike.
- Rounds 0 and 1 do not use `fold_window`, so in effect replay rounds 2–63
  each get a 1-bit wider fold.
- The comment above `fold_widen` explains why this is a level, not a shape.
  The flat region's escape rate sits between two integer window widths, so a
  block of leading rounds carries the extra bit, and which block it is does
  not matter.

**3. `PP_FOLD_PROFILE`: "38:0,32:-1,19:-3,0:-4" → "38:0,32:0,19:-3,0:-4"**
(r6a_dpark block).
- `band_at` picks the first band whose threshold is at or below the round's
  walk width.
- Rounds with walk width 32–37 now get offset 0 instead of −1. In this width
  schedule that is rounds 616–630, which is 15 rounds per traversal.

**4. `TAIL_NONCE`: 280927324351371 → 141341059326522.**

## Why it is still correct, and what it risks

- **Everything here is probabilistic.** A truncated fold drops the carry that
  would leave its slice, and the register then ends up `2^W` too small, which
  is a wrong field element.
  - With `FOLD_GUARD = 21`, each non-replay fold misses with probability about
    2^-21 per call, where it was about 2^-25. That is 16 times more often, at
    every such site.
  - The source's balance rule says that one guard serves all of these sites,
    because "the balance rule makes them all want the same per-call error
    whatever their call counts are".
- **The buys lower the replay folds' miss rate.** Each extra window bit about
  halves the escape rate at that round, over 62 + 15 rounds in each traversal.
  The package bets that the λ these buys return covers the λ the sell spends,
  at a lower Toffoli total.
- **Channels.** A missed fold gives a classical failure, because the output
  value is wrong.
- The shipped nonce `141341059326522` draws a clean test set: 9,024 of 9,024
  shots pass, with 0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The Toffoli saving comes from shortening truncated fold carry chains
(`FOLD_GUARD`), which is fold/carry truncation. The two widenings are
protective buys inside the same package, of the same kind but in the other
direction. They are not a separate lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout ea73b1a -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol ea73b1a 03d9ecd -- src/point_add` is
   8 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 03d9ecd -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`.
   - All settings are fixed arms of `env_raw` in `mod.rs`, and the process
     environment is never read. Leave `PP_*`, `SQ_*`, `HEO_*` and `SUB4_*`
     unset anyway.
   - Expect 1250 qubits and 889,047 average Toffoli (rounded).
   - Expect a score of 1,111,308,750.
   - Expect 0 classical, 0 phase and 0 ancilla failures.

The score only reproduces with `TAIL_NONCE` `141341059326522` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 7d974c6..d198e05 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -54,7 +54,7 @@ fn env_raw(name: &str) -> Option<String> {
         "I12_B_GUARD" => "4",
         "CMP_SEED_ALL" => "1",
         "ERASE_COMPARE" => "24",
-        "FOLD_GUARD" => "25",
+        "FOLD_GUARD" => "21",
         "PP_CF_DEFER_WALK_PHASE" => "1",
         "PP_CF_END_CHUNK" => "8",
         "PP_CHUNK_SHAPE" => "64:0,38:1,25:-2,0:-4",
@@ -127,7 +127,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "280927324351371",
+        "TAIL_NONCE" => "141341059326522",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
@@ -144,7 +144,7 @@ fn env_raw(name: &str) -> Option<String> {
         // The first matching arm wins, so a key must never appear twice. Then mirror
         // it in the grinder's Config::p426fdp (GRIND_WIDEN / GRIND_FOLD_GUARD defaults).
         "PP_RETAIN_LATE_WIDEN" => "1",
-        "PP_FOLD_WIDEN" => "0",
+        "PP_FOLD_WIDEN" => "64",
         "PP_DROP_EXACT_LEAD" => "1",
         "PP_DROP_EXACT_LEAD_DIR" => "mul",
         "PP_F_PEAKCMP" => "24",
@@ -199,7 +199,7 @@ fn env_raw(name: &str) -> Option<String> {
         // Classical results bit-identical to r6a_dpark; paired dfailb -0.039 +- 0.069 over 512 nonces.
         "I35_PROFILE" => "621:1:1,622:1:1,623:1:1,641:0:1,646:0:1,658:1:1,659:1:1,660:1:1,661:1:1,662:1:1,663:1:1,664:1:1,665:1:1,666:1:1,667:1:1,668:1:1,669:1:1,670:1:1,671:1:1,672:1:1,673:1:1,674:1:1,675:1:1,676:1:1,677:1:1,678:1:1,679:1:1,680:1:1,681:1:1,682:1:1,683:1:1,684:1:1,685:1:1,686:1:1,687:1:1,688:1:1,689:1:1,690:1:1,691:1:1,692:1:1,693:1:1,694:1:1,695:1:1,696:1:1,697:1:1",
         "PP_HEAD_MUL" => "413",
-        "PP_FOLD_PROFILE" => "38:0,32:-1,19:-3,0:-4",
+        "PP_FOLD_PROFILE" => "38:0,32:0,19:-3,0:-4",
         // New exact constructions (agent J: square B-branch fusions; agent U: doubling-replay park).
         "PP_J_SFUSE_B" => "1",
         "PP_J_WCIN" => "1",
```

