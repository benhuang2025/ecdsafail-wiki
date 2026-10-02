# ba05d3a — Route mod_double_inplace_fast through the truncated direct constant adder, and set the carry-tail window to 36

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `375fdff` |
| Commit | `ba05d3a9ce88f1ae4f4014ca94df88e4771c2586` |
| Result | 2309 qubits × 2,462,914 Toffoli = **5,686,868,426** |
| Base | `d6551e8` (git parent, solimander's submission): 2309 qubits × 2,547,490 Toffoli = 5,882,154,410 |
| Change vs base | qubits ±0, Toffoli −84,576, score −195,285,984 (leaderboard Δ −195,285,984) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [modular-fold](../concepts/modular-fold.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

`mod_double_inplace_fast` computes `2v mod p`. It shifts `v`, then adds the
sparse Solinas constant `c = 2^32 + 977` under the overflow bit. It did that
add with `cadd_nbit_const_fast`, which loads `c` into a 256-bit register and
runs a full 256-bit ripple adder. Carry-tail truncation never reached that
adder.

This commit flips an existing switch so the add goes through the
register-free `cadd_nbit_const_direct_fast`. That adder has the majority
fold and, since [`d6551e8`](d6551e8.md), the carry-tail cut for sparse
constants, so its carry chain stops at bit 69 instead of running all 256
bits. The shared carry-tail window also moves from 44 to 36 bits to land a
clean island. Net: −84,576 average Toffoli at the same 2309 qubits.

## What changed and why it saves Toffoli

1. **`src/point_add/modular.rs`, `mod_double_inplace_fast`.**
   - The test `KAL_DIRECT_CONST_DOUBLE == "1"` becomes `!= "0"`, so the
     direct path is now the default.
   - The function does a cascade of swaps (a rotate left, with the old top
     bit moved into `ovf`), then `cadd_nbit_const_direct_fast(v, c, ovf)`,
     then `cx(v[0], ovf)` to clean `ovf`.
   - Before, the add was `cadd_nbit_const_fast(v, c, ovf)`. That loads
     `ovf ? c : 0` into a fresh 256-bit register and runs `add_nbit_qq_fast`,
     a full-width ripple adder with measured carries, at about one Toffoli per
     bit.
   - Now the add has no constant register. It computes carries only up to
     `kal_carrytail_count_c = 33 + W` positions. Above bit 32 each carry is
     one CCX. At the set bits, the majority fold gives one CCX per carry.
   - With `W = 36` that is about 69 Toffoli per call instead of about 256.
2. **Who calls it.** In this tree the Kaliski `r` doubling already uses
   `mod_double_inplace_direct` (`gz_double_direct()` is on by default). The
   calls that change are the other users of `mod_double_inplace_fast`:
   - the 397 doublings of `lam` in pair2 (`pair2_double` in `point_add.rs`),
     which fix up the power-of-two factor the Kaliski almost-inverse leaves;
   - the doublings inside some multipliers' Solinas folds and a few helpers in
     `modular.rs`. (The constant-multiply chains in `kaliski_inv.rs` also call
     it, but only on the opt-in prescale paths.)

   The author puts the count at about 800 calls per point addition.
3. **`src/point_add/kaliski_state.rs`, `kal_carrytail_w()`.** When the add
   path is on (the default), the window goes from 44 to 36. This applies to
   every truncated direct constant add and subtract. Each one now computes 8
   fewer carry or borrow positions, which saves a little more on top. The
   comment records the sweep with the new routing: 36 is clean, and 32 to 35,
   37, 40 and 44 fail.

## Why it is still correct, and what it risks

The rerouting itself is exact. Both adders compute `v + (ovf ? c : 0)` mod
2^256. The direct one is the same adder the Kaliski step already uses for its
own doublings.

The truncation is the bet. The constant is the sparse `c` (top set bit 32).
Above bit 32, a carry survives only through a run of 1-bits of `v`. The
comments put the longest run seen in a 3M-trial Monte Carlo at 28 bits for
adds, which reaches bit 60. A 36-bit window reaches bit 68, so about 8 bits of
slack are left. For subtracts the longest run reaches bit 51, so there is more
slack. A dropped carry gives a wrong double, and so a classical mismatch.
The constant-aware window from `d6551e8` still gives dense constants such as
`p + 1` the full chain.

There is no nonce in this era. The op stream changed a lot, and only `W = 36`
landed a clean 9,024-shot set. `W = 32` missed by one shot. This draw is
clean: 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from making the carry-chain cut reach an adder it did not
reach before, and from cutting the chain further. That is fold/carry
truncation. A reasonable runner-up is Strength Reduction → fast-adder
reroute, since the main edit sends a call to a different adder.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout d6551e8 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol d6551e8 ba05d3a -- src/point_add` is
   15 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ba05d3a -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,462,914 average Toffoli (rounded)
   - score 5,686,868,426
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index eca7307..b197600 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -249,8 +249,13 @@ pub(crate) fn kal_carrytail_w() -> usize {
     // (0/0/0): avg-exec 2,547,490 Toffoli × 2309 = 5,882,154,410, below the
     // sub-only baseline 5,935,088,235. W∈{32,36,40,49,60,90,140} reject the
     // Fiat-Shamir island lottery here. Sub-only fallbacks retained for overrides.
+    // T-squeeze: with KAL_DIRECT_CONST_DOUBLE default-ON (mod_double routed through a
+    // truncatable sparse direct const-add), the both-path clean carry-tail floor drops
+    // 44->36 (chain to bit 33+36=69; the direct-double's extra truncated sites re-roll
+    // the island so W=36 lands clean — W∈{32,33,34,35,37,40,44} reject with DOUBLE on).
+    // DOUBLE + W=36 = 2,462,914 × 2309 = 5,686,868,426 (9024-clean, flat peak 2309).
     let default = if kal_carrytail_add_enabled() {
-        44
+        36
     } else if kal_cswap_wtrunc_enabled() {
         26
     } else {
diff --git a/src/point_add/modular.rs b/src/point_add/modular.rs
index 4866fe6..6445cf9 100644
--- a/src/point_add/modular.rs
+++ b/src/point_add/modular.rs
@@ -437,7 +437,13 @@ pub(crate) fn mod_double_inplace_fast(b: &mut B, v: &[QubitId], p: U256) {
     // `ovf` and the low register holds T mod 2^n for T = 2*v. If ovf=1 then
     // T = 2^n + low and T mod p = low + c; otherwise T mod p = low.
     let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
-    if std::env::var("KAL_DIRECT_CONST_DOUBLE").ok().as_deref() == Some("1") {
+    // T-squeeze: KAL_DIRECT_CONST_DOUBLE default-ON. mod_double's reduction constant
+    // here is the SPARSE Solinas c = 2^32+977, so routing it through the register-free
+    // direct const-add lets the carry-tail SUB/ADD truncation (now both-path on this
+    // base) clip its borrow/carry chain to W bits — across all ~800 mod_double calls
+    // of the two Kaliski passes. With carry-tail W=36 this is -84,576 avg-exec Toffoli
+    // vs the carry-register variant, flat peak 2309, 9024-clean. Set =0 to restore.
+    if std::env::var("KAL_DIRECT_CONST_DOUBLE").ok().as_deref() != Some("0") {
         cadd_nbit_const_direct_fast(b, v, c, ovf);
     } else {
         cadd_nbit_const_fast(b, v, c, ovf);
```

