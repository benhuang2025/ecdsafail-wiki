# cef001a — Extend the Kaliski (u, v) cswap boundary-merge from 329 to 331 iterations, with a new reroll count

| | |
| --- | --- |
| Contestant | owizdom |
| Date | 2026-06-02 |
| Submission | `d1d29eb` |
| Commit | `cef001abe40a07cb197a83a961a4967a39d630b1` |
| Result | 2006 qubits × 2,552,687 Toffoli = **5,120,690,122** |
| Base | `908521d` (git parent, anupsv): 2006 qubits × 2,553,083 Toffoli = 5,121,484,498 |
| Change vs base | qubits ±0, Toffoli −396, score −794,376 (leaderboard Δ −794,376) |
| Family | Fusion → boundary cswap-merge |
| Concepts | [scoring-and-validation](../concepts/scoring-and-validation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the last frontier commit on the old Kaliski-inversion circuit, just
before [`cddd5df`](cddd5df.md) replaced it with the dialog-GCD route. Each
Kaliski iteration swaps the `u` and `v` registers twice under the same
control: once to sort them (step 3) and once to put them back (step 9). An
earlier commit had fused each step-9 swap into the next iteration's step-3
swap, so one controlled swap does both jobs. The fusion is only valid while
`u ≠ v`, so it was limited to the first 329 iterations. This commit extends it
to 331, which deletes two more controlled swaps of about 50 bits in each of
the four Kaliski walks. That saves 396 average Toffoli at the same 2006 qubits.

The commit also changes the reroll count `KAL_REROLL` from 5 to 47. This
appends more identity `X;X` pairs to the stream, so the 9,024 test inputs are
drawn again. 47 is a count whose draw happens to be clean for the new stream.

## What changed and why it saves Toffoli

- **`src/point_add/kaliski_state.rs`, `kal_cswap_uv_merge_safe_iters()`: 329 → 331.**
  - Background: the inverse is a reversible Kaliski "almost inverse" walk on
    `(u, v_w)`, starting from `(p, dx)`. In each iteration `k`, step 3 swaps
    `(u, v_w)` under the control `a_k` (the branch decision), and step 9 swaps
    them back under the same `a_k`. Each swap is a controlled swap of every
    bit, which costs one Toffoli per bit (`cswap` = CX, CCX, CX).
  - With the merge on (`kal_cswap_uv_merge_enabled()`, default on), step 9 of
    iteration `k` is not emitted. Instead `a_k` is carried into iteration
    `k+1` on a `frame` qubit, and that iteration's step 3 swaps under
    `a_k ⊕ a_{k+1}`. This uses the identity `cswap(p)·cswap(q) = cswap(p⊕q)`.
    The merged swap uses iteration `k`'s wider width envelope.
  - The catch: during iteration `k+1`, the registers are still physically
    swapped by `a_k`. Step 1 corrects its flags with extra gates under
    `frame_in`. Step 2 computes `u > v_w` on the swapped registers and then
    corrects it with `l_gt ^= frame_in`. That correction is right only if
    `u ≠ v_w`: when they are equal, swapping does not change the comparison,
    so the XOR flips a correct answer.
  - With gcd = 1, equality can only happen as `(u, v_w) = (1, 1)` near the end
    of the walk. So the merge is applied only for `iter_idx < safe_iters`
    (`uv_merge_in`, `uv_merge_out` in `kaliski_walk.rs`). Past that point the
    eager step-9 swap is used.
  - Raising the limit to 331 merges iterations 329 and 330 too. That deletes
    the step-9 swaps of iterations 328 and 329, of width
    `min(2·256 − k, kal_wtrunc_width(k))` = 52 and 51 bits (`K0 = 21`), in
    each of the four walks (forward and backward for `pair1` and `pair2`).
    Less the extra step-1 CCX and the one-bit-wider merged step-3 swap of
    each newly merged iteration, that is 4 × (103 − 4) = 396, the measured
    net saving in average Toffoli.
- **`src/point_add/mod.rs`, `build()`: the default `KAL_REROLL` goes from 5 to
  47.**
  - `KAL_REROLL` appends `rr` pairs of `X(tx[0]); X(tx[0])` after the point
    addition. The pairs are an identity with no Toffoli and no new qubits,
    but they change the op-stream hash that selects the 9,024 test inputs.
  - In this era there was no tail nonce yet, and this count plays that role.
    The comment in the base said 330 "has no clean reroll island" at the old
    count. The author found that 331 does give a clean draw at `rr = 47`.

## Why it is still correct, and what it risks

- The merge itself is an exact identity of controlled swaps. The only
  approximation is the `gt ^= frame` shortcut in step 2, which is wrong on an
  input that reaches `u = v_w` in iterations 329 or 330. On such an input the
  walk takes the wrong branch and the result is wrong. That would show as a
  classical mismatch, and probably also as phase or ancilla garbage.
- Moving the limit later makes those inputs more likely, which is why the
  base author stopped at 329. The reroll count 47 gives a draw with no such
  input: 9,024 of 9,024 shots pass, with 0 classical, 0 phase and 0 ancilla
  failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), where the
  later tail nonce does this same job.

## Classification rationale

The saving comes from extending a fusion of two controlled swaps across an
iteration boundary to two more iterations. That is Fusion → boundary
cswap-merge. You could also see it as a truncation-style "safe prefix" knob,
but the gates removed are swaps that the fusion makes redundant, not bits of
a narrower operation. The reroll count is the nonce-equivalent that comes
with every circuit change in this era.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 908521d -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 908521d cef001a -- src/point_add` is 4 lines
   in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol cef001a -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   environment variables set, because they override the defaults in the
   patch. Expect:
   - 2006 qubits
   - 2,552,687 average Toffoli (rounded)
   - score 5,120,690,122
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `KAL_REROLL = 47` and an identical op stream.
Any other change draws a new test set and needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index 8d44c65..0709911 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -552,7 +552,7 @@ pub(crate) fn kal_cswap_uv_merge_safe_iters() -> usize {
     // cswaps fwd+bwd, -22,600 avg-exec Toffoli) co-tuned with reroll=5 below.
     // 330 has no clean reroll island (u==v_w equality at iter 329 breaks the
     // cheap gt^=frame correction). Keep tunable for future sweeps.
-    env_usize("KAL_CSWAP_UV_MERGE_SAFE_ITERS").unwrap_or(329)
+    env_usize("KAL_CSWAP_UV_MERGE_SAFE_ITERS").unwrap_or(331) // CO-TUNE: 331 + reroll=47 (full-9024 island)
 }
 
 /// For nonzero secp256k1 inputs, the first 256 Kaliski iterations are always
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index fb127fd..36791d9 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -275,7 +275,7 @@ pub fn build() -> Vec<Op> {
         let rr: usize = std::env::var("KAL_REROLL")
             .ok()
             .and_then(|v| v.parse::<usize>().ok())
-            .unwrap_or(5);
+            .unwrap_or(47); // CO-TUNE: rr=47 lands the cswap=331 full-9024 island
         for _ in 0..rr {
             b.x(tx[0]);
             b.x(tx[0]);
```

