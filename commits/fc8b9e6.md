# fc8b9e6 — Lower the Kaliski W-TRUNC safety margin from 4 to 3 bits

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `ceb0ce9` |
| Commit | `fc8b9e6325f3f2a28f0f6ce1b16db99bfcbee1d8` |
| Result | 2309 qubits × 2,865,661 Toffoli = **6,616,811,249** |
| Base | `1e18b4d` (git parent, the author's previous submission): 2309 qubits × 2,870,041 Toffoli = 6,626,924,669 |
| Change vs base | qubits ±0, Toffoli −4,380, score −10,113,420 (leaderboard Δ −10,113,420) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit changes one constant. The circuit of this era inverts with a
reversible Kaliski binary almost-inverse. Its per-iteration width loops are
cut to an empirical bit-length envelope plus a safety margin (W-TRUNC). The
margin goes from 4 bits to 3. Every truncated loop in every Kaliski
iteration past the full-width prefix then runs one bit narrower. That saves
4,380 average Toffoli at the same 2309 qubits.

The margin was tuned against the test island. The previous commit
(`1e18b4d`, carry-tail truncation) changed the op stream and so drew a new
9,024-shot test set. On that op stream the author found that margin 3 is
clean, while margins 2 and 1 fail.

## What changed and why it saves Toffoli

- `src/point_add/kaliski_state.rs`, `kal_wtrunc_margin()`: the default of
  `KAL_WTRUNC_MARGIN` goes from 4 to 3. The comment is rewritten with the
  sweep result.
- **What W-TRUNC is.** The inverse is a qrisp-style Kaliski almost-inverse on
  registers `u, v_w` (the GCD pair) and `r, s` (the Bézout pair), with
  `n = 256`. Two inversions run per point addition, "pair1" with 399
  iterations and "pair2" with 397, and each runs forward and backward.
  - The provable bound on the live width of `u` and `v_w` is `n` while
    `iter < n`, then `2n − iter`.
  - `kal_wtrunc_width(iter, n)` returns the empirical envelope
    `w_env(it) = n` for `it < K0 = 27`, and `n − ⌊(it − 27)·2/3⌋` afterwards,
    plus the margin, capped at `n`. The envelope came from 80k random
    inputs, with 1 to 7 bits of slack above the sample maximum.
  - Every site takes `min(provable, kal_wtrunc_width(iter, n))`, so W-TRUNC
    only ever narrows a loop.
- **Where the width is used** (`src/point_add/kaliski_walk.rs`, forward and
  backward of both the bulk-prefix and the generic iteration):
  - the STEP-0 OR chain that tests `v_w == 0`;
  - the STEP-2 comparator `u > v_w` (`with_gt`);
  - the STEP-4 load `tmp = add_f AND u` (one CCX per bit), the
    `sub_nbit_qq_fast` subtract into `v_w`.
- **Why it saves Toffoli.** Past iteration 27 plus a few, the envelope plus
  margin is below the provable bound. Each loop then loses one bit position
  per iteration, which is about one Toffoli per loop. Spread over roughly
  1,600 Kaliski iterations (forward and backward of both pairs), this gives
  the measured 4,380.

## Why it is still correct, and what it risks

The truncation is probabilistic. A loop of width `w` assumes the top bits of
`u` and `v_w` above `w` are zero. If an input converges more slowly than the
envelope plus margin allows, a nonzero bit is ignored. The comparison or the
subtraction is then wrong, and the inverse is wrong. This shows up as a
classical mismatch, and the broken uncompute can also leave phase garbage.
Each bit of margin removed roughly halves the slack above the measured
envelope.

There is no tail nonce in this era. The test set is a Fiat–Shamir hash of the
op stream itself, so each margin value draws a different set. The author's
full 9,024-shot screen on this op stream gave:
- margin 3: clean, 0 classical, 0 phase and 0 ancilla failures;
- margin 2: 2 mismatches and 1 phase failure;
- margin 1: 2 mismatches.

So 3 is the floor on this island. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) and
[comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).

## Classification rationale

The only change narrows the width of comparators, OR chains and adders in
the GCD walk, which is comparator/width truncation. The runner-up would be
iteration/threshold tuning, since the margin is a tuned threshold, but what
it controls is a bit width.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 1e18b4d -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 1e18b4d fc8b9e6 -- src/point_add` is
   15 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol fc8b9e6 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,865,661 average Toffoli (rounded)
   - score 6,616,811,249
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index fdf209a..312a4ac 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -75,12 +75,15 @@ pub(crate) fn kal_wtrunc_k0() -> usize {
 }
 
 pub(crate) fn kal_wtrunc_margin() -> usize {
-    // Banked: margin=4 pairs with the CARRY-TAIL SUB W=96 truncation to land a
-    // 9024-clean island (the carrytail op-count change re-rolls the Fiat-Shamir
-    // inputs, and margin=4 gives the GCD W-TRUNC enough slack to absorb the new
-    // stragglers). Validated clean; score 6,626,924,669. (Without carrytail the
-    // banked margin was 0.) KAL_WTRUNC_MARGIN env override remains available.
-    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(4)
+    // Banked: margin=3 — re-tightened from 4 on the CARRY-TAIL SUB W=96 island.
+    // The carry-tail op-count change re-rolled the Fiat-Shamir inputs; a full
+    // 9024-shot screen on this island maps the validity cliff at margin: 3=clean
+    // (0/0/0), 2=FAIL (2 mismatch / 1 phase), 1=FAIL (2 mismatch). So margin=3 is
+    // the validating floor for the combined (carry-tail + GCD W-TRUNC) circuit —
+    // -4,380 avg-exec Toffoli vs margin=4, peak-neutral 2309. Validated clean;
+    // score 6,616,811,249. (Carry-tail base had margin=4; pre-carry-tail it was
+    // 0.) KAL_WTRUNC_MARGIN env override remains available.
+    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(3)
 }
 
 /// Empirical-bound truncation width for a CCX-bearing Kaliski width loop at
```

