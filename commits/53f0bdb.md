# 53f0bdb — Route the Solinas ±c steps of the qq modular adders through the truncated direct constant adders, and cut the carry-tail window to 22

| | |
| --- | --- |
| Contestant | anupsv |
| Date | 2026-06-01 |
| Submission | `ba6b8fc` |
| Commit | `53f0bdb306ccfbd87652493312a1aedb0311e701` |
| Result | 2309 qubits × 2,439,354 Toffoli = **5,632,468,386** |
| Base | `ba05d3a` (Gajesh2007's submission): 2309 qubits × 2,462,914 Toffoli = 5,686,868,426 |
| Change vs base | qubits ±0, Toffoli −23,560, score −54,400,040 |
| Leaderboard Δ | −20,672,477, measured against the frontier at the time, `297f5e5` (2309 × 2,448,307 = 5,653,140,863), which is **not** this commit's base |
| Family | Strength Reduction → fast-adder reroute |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [modular-fold](../concepts/modular-fold.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The quantum-quantum modular adders reduce mod p with two constant steps:
an unconditional `+c`, then a conditional `−c`, where `c = 2^32 + 977`. Both
steps used to load `c` into a 257-bit register and run a full-width ripple
adder. This commit sends both through the register-free direct constant
adder and subtractor. Those already have the carry-tail cut, so their chains
stop a few dozen bits above bit 32. This is the same move that
[`ba05d3a`](ba05d3a.md) made for `mod_double_inplace_fast`, applied to three
more functions.

The new op stream needed a new island. The shared carry-tail window drops
from 36 to 22 bits, which saves Toffoli in every truncated call.
`R_SMALL_THRESHOLD` drops from 325 to 323, which costs a little. Net:
−23,560 average Toffoli at the same 2309 qubits.

## What changed and why it saves Toffoli

1. **`src/point_add/modular.rs`: new switch `KAL_DIRECT_CONST_QQFOLD`**, on
   unless set to `0`. It adds a `use_direct` branch to three functions:
   - `mod_add_qq_fast` and `mod_add_qq_fast_from_zero`:
     - the `+c` step becomes `cadd_nbit_const_direct_fast(acc_ext, c, one)`,
       with `one` a fresh wire set to 1;
     - the conditional `−c` becomes
       `csub_nbit_const_direct_fast(acc_ext, c, flag)`.
     - Before, they were `load_const` plus `add_nbit_qq_fast`, and a CX-loaded
       register plus `sub_nbit_qq_fast`.
   - `mod_sub_qq_fast`: the conditional `−c` becomes
     `csub_nbit_const_direct_fast(acc_ext[..n], c, flag)` instead of
     `csub_nbit_const_fast`.
2. **How the modular add works.**
   - `acc_ext = acc + a` over 257 bits.
   - Then `+c`: bit 256 (`acc_ovf`) is now set exactly when `acc + a ≥ p`.
   - `flag = NOT acc_ovf`, then `−c` under `flag`. This undoes the `+c` when no
     reduction was needed.
   - `flag` is cleaned with `cmp_lt_into_fast`.
3. **Why it saves Toffoli.** The old constant steps ran a full 257-bit ripple,
   at about one Toffoli per bit. The direct versions compute carries only up
   to `kal_carrytail_count_c = 33 + W` positions, at one CCX each, with the
   majority fold at the set bits of `c`. The note measures −6,346 Toffoli for
   this reroute alone at `W = 36`. These adders serve the affine combine and
   the two Solinas folds.
4. **`src/point_add/kaliski_state.rs`:**
   - `kal_carrytail_w()`: 36 → 22 on the default (add path on) branch. Every
     truncated direct constant add or subtract now computes 14 fewer
     positions. With the roughly 1,250 such calls measured in
     [`297f5e5`](297f5e5.md), plus the new ones, that is the larger part of
     the saving.
   - `R_SMALL_THRESHOLD`: 325 → 323. Kaliski iterations 323 and 324 now do the
     full modular double of `r` instead of the Toffoli-free rotate. This costs
     a few hundred Toffoli and is the safer direction.

## Why it is still correct, and what it risks

- **The reroute** changes which adder computes each `±c`. The values are the
  same wherever the carry chain fits in the window.
- **The `+c` step is the delicate one.** Its carry out of bit 255 is the
  reduction decision `acc_ovf`. With the cut, a carry that runs from bit 33
  through more than `W` 1-bits of `acc + a` is dropped. Then both the high
  bits and the reduction flag are wrong.
  - This step is unconditional (its control is a constant 1), so it has a
    carry out of the low 33 bits on a large share of inputs.
  - The chance of a 22-bit run of 1s after that is about 2^-22 per call.
  - The comment says this is sound because no carry from the sum can reach
    bit 256 outside the window. That is true only in this probabilistic
    sense.
- **The 22-bit window** is below the longest add-carry run (28 bits) seen in
  the 3M-trial Monte Carlo in the comments. So the add path is truly
  probabilistic on all truncated adds, not only these. A dropped carry gives
  a wrong sum and a classical mismatch.
- **`R_SMALL = 323`** is safer than 325.

There is no nonce in this era. A joint 9,024-shot screen found `R_SMALL = 323`
with `W = 22` clean. `W = 20` and `W = 23`, and `R_SMALL` 322 and 324, fail.
This draw is clean: 0 classical, 0 phase and 0 ancilla failures. The note
also checks that `KAL_DIRECT_CONST_QQFOLD=0` reproduces the base's count. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The main edit sends existing calls to a cheaper adder, which fits Strength
Reduction → fast-adder reroute. The window cut from 36 to 22 is fold/carry
truncation and gives a large share of the saving, so it is a close
runner-up. The same reroute for `mod_double_inplace_fast` in `ba05d3a` was
filed under fold/carry truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout ba05d3a -- src/point_add`.
   - Do not start from the git parent `297f5e5`. That is jtrose24's tree,
     with `R_SMALL_THRESHOLD = 319` and carry-tail `W = 23`.
   - Against the parent, the diff is 66 lines in 2 files. It would show those
     two knobs and their comments moving to 323 and 22, mixed in with this
     change.
   - Against `ba05d3a`, `git diff --ignore-cr-at-eol ba05d3a 53f0bdb -- src/point_add`
     is 43 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 53f0bdb -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,439,354 average Toffoli (rounded)
   - score 5,632,468,386
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index b197600..1aa015c 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -38,7 +38,7 @@ use super::*;
 // cswap-base a25248f margin=0 island (with K0=26/R=326 only W=26 is clean at
 // 2,574,129; dropping to K0=25 needs the R=325 re-roll → 2,570,415). R=324/326/327
 // reject at this depth. Stacks: margin=0 + K0=25 + R=325 + W=26 = 5,935,088,235.
-pub(crate) const R_SMALL_THRESHOLD: usize = 325;
+pub(crate) const R_SMALL_THRESHOLD: usize = 323;
 
 pub(crate) fn r_small_threshold() -> usize {
     std::env::var("KAL_R_SMALL_THRESHOLD")
@@ -255,7 +255,7 @@ pub(crate) fn kal_carrytail_w() -> usize {
     // the island so W=36 lands clean — W∈{32,33,34,35,37,40,44} reject with DOUBLE on).
     // DOUBLE + W=36 = 2,462,914 × 2309 = 5,686,868,426 (9024-clean, flat peak 2309).
     let default = if kal_carrytail_add_enabled() {
-        36
+        22
     } else if kal_cswap_wtrunc_enabled() {
         26
     } else {
diff --git a/src/point_add/modular.rs b/src/point_add/modular.rs
index 6445cf9..6493a7b 100644
--- a/src/point_add/modular.rs
+++ b/src/point_add/modular.rs
@@ -211,6 +211,15 @@ pub(crate) fn mod_sub_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256
         );
         b.free(q_clean2[0]);
         b.free(q_clean2[1]);
+    } else if std::env::var("KAL_DIRECT_CONST_QQFOLD").ok().as_deref() != Some("0") {
+        // CARRY-TAIL (default-ON): route the sparse Solinas conditional -c through
+        // the truncatable direct const-sub (kal_carrytail_count_c clips its borrow
+        // chain to k0+W = 33+36 = 69 bits). The constant is the SPARSE Solinas
+        // c = 2^32+977, so the constant-aware window keeps the truncation tight and
+        // the high result bits exact; validated 9024-clean (-6,346 avg-exec Toffoli
+        // combined with the +c/-c reduction sites). KAL_DIRECT_CONST_QQFOLD=0 restores
+        // the register-loaded full-width csub_nbit_const_fast.
+        csub_nbit_const_direct_fast(b, &acc_ext[..n], c, flag);
     } else {
         csub_nbit_const_fast(b, &acc_ext[..n], c, flag);
     }
@@ -628,6 +637,17 @@ pub(crate) fn mod_add_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256
     let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
     // add_nbit_const with fast Cuccaro OR venting (using `a` as dirty).
     let use_vent = std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1");
+    // KAL_DIRECT_CONST_QQFOLD (CARRY-TAIL, default-ON): route the sparse Solinas
+    // reduction const-ops (+c / conditional -c) through the register-free direct
+    // const adders, which carry-tail-truncate the carry/borrow chain via the
+    // constant-aware window (kal_carrytail_count_c: cut = k0+W = 33+36 = 69 for the
+    // SPARSE c = 2^32+977). NOTE: the `+c` step here uses the resulting bit-256 carry
+    // (acc_ovf) AS the reduction flag — truncating that chain is only sound if no
+    // carry from the qq-sum can reach bit 256 outside the window, which holds for the
+    // Solinas constant and is validated 9024-clean (the harness fails closed). This is
+    // -6,346 avg-exec Toffoli vs the loaded-const full-width path, flat peak 2309.
+    // KAL_DIRECT_CONST_QQFOLD=0 restores the loaded-const reduction.
+    let use_direct = std::env::var("KAL_DIRECT_CONST_QQFOLD").ok().as_deref() != Some("0");
     if use_vent {
         let n1 = acc_ext.len();
         // Use `a_ext` as dirty qubits (it was just used as add operand,
@@ -644,6 +664,12 @@ pub(crate) fn mod_add_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256
         );
         b.free(q_clean2[0]);
         b.free(q_clean2[1]);
+    } else if use_direct {
+        let one = b.alloc_qubit();
+        b.x(one);
+        cadd_nbit_const_direct_fast(b, &acc_ext, c, one);
+        b.x(one);
+        b.free(one);
     } else {
         let n1 = acc_ext.len();
         let ca = load_const(b, n1, c);
@@ -668,6 +694,8 @@ pub(crate) fn mod_add_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256
         );
         b.free(q_clean2[0]);
         b.free(q_clean2[1]);
+    } else if use_direct {
+        csub_nbit_const_direct_fast(b, &acc_ext, c, flag);
     } else {
         let n1 = acc_ext.len();
         let ca = b.alloc_qubits(n1);
@@ -713,6 +741,9 @@ pub(crate) fn mod_add_qq_fast_from_zero(b: &mut B, acc: &[QubitId], a: &[QubitId
 
     let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
     let use_vent = std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1");
+    // CARRY-TAIL (default-ON): same truncated direct const reduction as
+    // mod_add_qq_fast; see KAL_DIRECT_CONST_QQFOLD note there. =0 restores loaded-const.
+    let use_direct = std::env::var("KAL_DIRECT_CONST_QQFOLD").ok().as_deref() != Some("0");
     if use_vent {
         let n1 = acc_ext.len();
         let c_low = c.as_limbs()[0];
@@ -727,6 +758,12 @@ pub(crate) fn mod_add_qq_fast_from_zero(b: &mut B, acc: &[QubitId], a: &[QubitId
         );
         b.free(q_clean2[0]);
         b.free(q_clean2[1]);
+    } else if use_direct {
+        let one = b.alloc_qubit();
+        b.x(one);
+        cadd_nbit_const_direct_fast(b, &acc_ext, c, one);
+        b.x(one);
+        b.free(one);
     } else {
         let n1 = acc_ext.len();
         let ca = load_const(b, n1, c);
@@ -750,6 +787,8 @@ pub(crate) fn mod_add_qq_fast_from_zero(b: &mut B, acc: &[QubitId], a: &[QubitId
         );
         b.free(q_clean2[0]);
         b.free(q_clean2[1]);
+    } else if use_direct {
+        csub_nbit_const_direct_fast(b, &acc_ext, c, flag);
     } else {
         let n1 = acc_ext.len();
         let ca = b.alloc_qubits(n1);
```

