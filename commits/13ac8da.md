# 13ac8da — Lower the Kaliski W-TRUNC safety margin from 10 to 0 bits

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `03499c8` |
| Commit | `13ac8da27bc3f2d6d9d0f5508354a67327d48572` |
| Result | 2309 qubits × 2,929,804 Toffoli = **6,764,917,436** |
| Base | [`b86e789`](b86e789.md) (git parent, the author's previous submission): 2309 qubits × 2,973,304 Toffoli = 6,865,358,936 |
| Change vs base | qubits ±0, Toffoli −43,500, score −100,441,500 (leaderboard Δ −100,441,500) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

One constant. The W-TRUNC margin goes from 10 to 0. The Kaliski width loops
are then clipped exactly to the fitted envelope
`w_env(it) = 256 − ⌊(it − 27)·2/3⌋`, with no extra slack. Each clipped loop
loses 10 more bit positions, and clipping starts at iteration 29. The result is
43,500 fewer average Toffoli at 2309 qubits.

This is the most aggressive setting possible. It passes on this op stream's
test draw, but the code's own earlier comment calls margin 0 "the cliff". The
next W-TRUNC commit, [`1e18b4d`](1e18b4d.md), is built on the margin-20 tree
instead, and later commits come down to margin 0 again only gradually, from 4.

## What changed and why it saves Toffoli

- `src/point_add/kaliski_state.rs`, `kal_wtrunc_margin()`: the default of
  `KAL_WTRUNC_MARGIN` goes from 10 to 0. The comment says margin 0 is a
  narrow 9,024-shot-clean island and that the neighbouring margins are
  non-monotone.
- The clipped width is `min(n, w_env(it) + margin)` for `it ≥ 27`, clamped by
  the provable bound at each site (see [`36e8578`](36e8578.md)). With margin 0
  it equals `w_env(it)` from iteration 29 on. Examples:
  - iteration 100: 208 bits instead of 218 at margin 10;
  - iteration 254: 105 bits;
  - iteration 350: 41 bits.
- The clipped loops are:
  - the STEP 0 OR chain (generic iteration);
  - the STEP 2 `u > v_w` comparator;
  - the STEP 4 `add_f & u` load and the `v_w −= tmp` subtract;
  - the backward mirrors of these, in all four Kaliski runs.

  Each costs about one Toffoli per bit.

## Why it is still correct, and what it risks

- **This is the riskiest W-TRUNC setting.** The envelope was fitted to 80,000
  random inputs with 1 to 7 bits of slack above that sample's maximum. The
  comment in [`36e8578`](36e8578.md) reports that on 300,000 fresh inputs the
  minimum slack equalled the margin, which at margin 0 means some inputs touch
  the envelope exactly. The same comment warned "margin=0 is the cliff
  (slack=0 = corruption one input away)".
- **What a failure looks like.** An input whose `u` or `v_w` has a set bit at
  or above `w_env(it)` at any iteration loses that bit in a comparator,
  subtractor or OR chain. Its inverse is then wrong: a classical mismatch,
  usually with phase garbage from the backward run.
- **It passes only on this draw.** There is no tail nonce in this era, so the
  test set is a hash of the op stream. This op stream's draw happens to avoid
  every such input: 0 classical, 0 phase and 0 ancilla failures. Neighbouring
  margins fail non-monotonically. That pattern shows the outcome is decided by
  which inputs the hash draws, not by a safety margin. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

A truncation margin is narrowed: comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout b86e789 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol b86e789 13ac8da -- src/point_add` is
   8 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 13ac8da -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`,
   `POINT_ADD_*` or `BY_*` environment variables set. Expect:
   - 2309 qubits
   - 2,929,804 average Toffoli (rounded)
   - score 6,764,917,436
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era: the test set is a hash of the op stream,
so the score only reproduces with an identical op stream.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index 061127a..1c357f2 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -75,11 +75,11 @@ pub(crate) fn kal_wtrunc_k0() -> usize {
 }
 
 pub(crate) fn kal_wtrunc_margin() -> usize {
-    // Banked: margin=10 (optimizer-20260601-021354; T -41,700 vs margin=20; 6,865,358,936).
-    // Sweep after the UV STEP1 fanout found a narrow clean island at margin=20;
-    // the next 9024-shot-valid step down is margin=10 (margins 5/12 reject).
+    // Banked: margin=0 is a narrow 9024-shot-clean WTRUNC island on top of the
+    // f1-drop/fanout stack. Neighboring sampled margins are non-monotone, so
+    // keep this as an exact scorer-validated island, not a proof margin.
     // KAL_WTRUNC_MARGIN env override remains available.
-    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(10)
+    env_usize("KAL_WTRUNC_MARGIN").unwrap_or(0)
 }
 
 /// Empirical-bound truncation width for a CCX-bearing Kaliski width loop at
```

