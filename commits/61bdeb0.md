# 61bdeb0 — Narrow the shift22 final-reduction carry window from 37 to 35 (cut 70 → 68), with re-roll 47 → 19

| | |
| --- | --- |
| Contestant | antojoseph |
| Date | 2026-06-02 |
| Submission | `ea8ad85` |
| Commit | `61bdeb0117608ddc73063c21d64ca5420a0eee0b` |
| Result | 2024 qubits × 2,559,439 Toffoli = **5,180,304,536** |
| Base | `9899c06` (git parent, the author's previous submission): 2024 qubits × 2,559,463 Toffoli = 5,180,353,112 |
| Change vs base | qubits ±0, Toffoli −24, score −48,576 (leaderboard Δ −48,576) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The shift22 helper (`v · 2^22 mod p`) ends with a final reduction: `+c`, read
the top bit, then a conditional `−c`, with `c = 2^32 + 977`. Since
[`1b913c5`](1b913c5.md) those two steps, and their two inverses, use the direct
constant adder with a carry chain of `33 + SHIFT22_CARRYTAIL_W` positions.
This commit lowers `W` from 37 to 35, so the cut goes from 70 to 68 and each
step saves 2 Toffoli. Four steps per forward/inverse pair and three executed
pairs give exactly the observed −24. `KAL_REROLL` goes from 47 to 19 to land a
clean draw. Qubits are unchanged.

## What changed and why it saves Toffoli

1. **`shift22_carrytail_cut()`: `SHIFT22_CARRYTAIL_W` 37 → 35**
   (`src/point_add/solinas.rs`).
   - The cut is used by `cadd_nbit_const_direct_fast_cut` and
     `csub_nbit_const_direct_fast_cut` in step 3 (`+c`) and step 4
     (conditional `−c`) of `mod_shift_left_by_k`, and in the two reverse steps
     of `mod_shift_right_by_k`. Each carry position costs one Toffoli.
   - The saving is 2 positions × 4 steps × 3 pairs = 24. The spill-fold window
     of [`3f534f2`](3f534f2.md) is not in this tree (this line descends from
     `6e71096`).
   - The doc comment is updated. The author's note calls this "STEP-2", but
     the code changed is the STEP-3/STEP-4 window.
2. **`KAL_REROLL`: 47 → 19** (`src/point_add/mod.rs`): identity `X;X` pairs
   that only re-draw the test inputs. The author reports `rr` = 19, 92 and 123
   all clean, with the same average Toffoli.

## Why it is still correct, and what it risks

- **Exact in practice.** The chain still reaches 35 bits above `c`'s top bit.
  A carry is dropped only if bits 33…68 of the value are all ones, about
  2^-36 per call. The flag of step 3 is also wrong on values in
  `[p, 2^256)`, which have probability about 2^-223. A wrong result shows up
  as a classical mismatch.
- **Island.** `W = 34` had no clean re-roll in 0–127. The shipped stream is
  clean: 0 classical, 0 phase and 0 ancilla failures over 9,024 shots. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

A carry chain in the modular reduction is cut two bits shorter, which is
fold/carry truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 9899c06 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 9899c06 61bdeb0 -- src/point_add` is
   20 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 61bdeb0 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`,
   `AFFINE_*`, `SHIFT22_*` or `LOWQ_*` environment variables set. Expect:
   - 2024 qubits
   - 2,559,439 average Toffoli (rounded)
   - score 5,180,304,536
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `KAL_REROLL = 19` and an identical op stream.
Any other change needs a new re-roll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 645d118..ce1e22a 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -262,15 +262,16 @@ pub fn build() -> Vec<Op> {
     // into a searchable axis: hold a tighter-than-floor truncation and sweep
     // `rr` until the resulting input set validates 0/0/0. Default 0 = no-op.
     {
-        // Baked default rr=47 is CO-TUNED to the validated C* op stream (dialog
+        // Baked default rr=19 is CO-TUNED to the validated C* op stream (dialog
         // fold + affine recompute mfw243 + early-recover, slack=3, margin=0,
-        // R_SMALL=326): it lands a clean 9024 Fiat-Shamir island for that stream
-        // (avg-exec 2,559,463 T × 2024 peak = 5,180,353,112, validated 0/0/0).
-        // Re-search this value whenever any scored op changes the op stream.
+        // R_SMALL=326, shift22-carrytail-W=35): it lands a clean 9024 Fiat-Shamir
+        // island for that stream (avg-exec 2,559,439 T × 2024 peak = 5,180,304,536,
+        // validated 0/0/0). Re-search this value whenever any scored op changes
+        // the op stream.
         let rr: usize = std::env::var("KAL_REROLL")
             .ok()
             .and_then(|v| v.parse::<usize>().ok())
-            .unwrap_or(47);
+            .unwrap_or(19);
         for _ in 0..rr {
             b.x(tx[0]);
             b.x(tx[0]);
diff --git a/src/point_add/solinas.rs b/src/point_add/solinas.rs
index d7a9a39..73d0fd5 100644
--- a/src/point_add/solinas.rs
+++ b/src/point_add/solinas.rs
@@ -30,14 +30,15 @@ pub(crate) fn shift22_carrytail() -> bool {
 /// W=40 → 0/0/0, avg-exec 2,429,724. Note this is NOT a pure truncation-soundness
 /// floor — even W=223 (full chain, zero truncation) MISSES the Fiat-Shamir island
 /// (1 mismatch), because routing STEP-3/4 through the direct const adders re-rolls
-/// the test inputs; W=37 is the value that lands a 9024-clean island AND truncates.
-/// Single value, used identically forward and reverse (phase-parity).
-/// W∈{20,22,25,30,35,36,38,39,41,42,45,50,55,60,90,223} all MISS the island.
+/// the test inputs; W=35 is the value that lands a 9024-clean island AND truncates
+/// on the C* stack (dialog-fold + affine-recompute + early-recover, slack=3,
+/// R_SMALL=326). Single value, used identically forward and reverse (phase-parity).
+/// W=34 rejects the Fiat-Shamir island lottery (no clean reroll in 0-127).
 pub(crate) fn shift22_carrytail_cut() -> usize {
     let w = std::env::var("SHIFT22_CARRYTAIL_W")
         .ok()
         .and_then(|s| s.parse::<usize>().ok())
-        .unwrap_or(37);
+        .unwrap_or(35);
     33usize.saturating_add(w)
 }
 
```

