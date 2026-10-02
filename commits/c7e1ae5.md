# c7e1ae5 — Fold the constant-add carry majority from 3 Toffoli to 1 on the swap-truncation tree

| | |
| --- | --- |
| Contestant | saucegodbased |
| Date | 2026-06-01 |
| Submission | `65d2cd7` |
| Commit | `c7e1ae53f442ad31359d5ca182f08eb82837d2d3` |
| Result | 2309 qubits × 2,610,715 Toffoli = **6,028,140,935** |
| Base | `404d630` (Gajesh2007's swap-truncation submission): 2309 qubits × 2,615,899 Toffoli = 6,040,110,791 |
| Change vs base | qubits ±0, Toffoli −5,184, score −11,969,856 |
| Leaderboard Δ | −7,157,900, measured against the frontier at the time, `a25248f` (2309 × 2,613,815 = 6,035,298,835), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [modular-fold](../concepts/modular-fold.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

One exact gate identity. The controlled constant adder
`cadd_nbit_const_direct_fast` computes each carry as a three-input majority.
At every bit where the constant has a 1, that majority used three Toffoli.
This commit writes it with one Toffoli and some CX gates, using
`MAJ(a, b, d) = d ⊕ ((a ⊕ d) ∧ (b ⊕ d))`. The carry values are the same, so
nothing downstream changes. The saving is 5,184 average Toffoli at the same
2309 qubits.

It is the same rewrite as the first half of [`d4959a1`](d4959a1.md). That
commit was on the older `a97b4e9` line. This one ports it to
[`404d630`](404d630.md), the tree that already had the (u, v_w) swap
truncation.

## What changed and why it saves Toffoli

- `src/point_add/kaliski_state.rs`: new `majfold_add_enabled()` switch
  (`KAL_MAJFOLD_ADD`, on by default). It mirrors the existing
  `majfold_sub_enabled()` for the subtractor.
- `src/point_add/cuccaro.rs`, `cadd_nbit_const_direct_fast`, forward carry
  sweep:
  - The adder adds `ctrl ? c : 0` with `c = 2^32 + 977`, without loading `c`
    into a register. At bit `i`, `carry_{i+1} = MAJ(acc_i, k_i, carry_i)`,
    where `k_i = ctrl` if `c` has a 1 at bit `i`, and 0 otherwise.
  - Old code at a set bit with a carry-in: `ccx(acc,ci,t); ccx(ctrl,acc,t);
    ccx(ctrl,ci,t)`, three Toffoli.
  - New code: `cx(ci,acc); cx(ci,ctrl); ccx(acc,ctrl,t); cx(ci,t); cx(ci,ctrl);
    cx(ci,acc)`, one Toffoli. The two CX before the CCX turn `acc` and `ctrl`
    into `acc ⊕ ci` and `ctrl ⊕ ci`. The CCX writes their AND, and `cx(ci,t)`
    adds the pivot back. The last two CX restore `acc` and `ctrl`.
  - `977 = 0b1111010001`, so `c` has 1s at bits 0, 4, 6, 7, 8, 9 and 32. Bit 0
    has no carry-in, so it already used one Toffoli. The other 6 set bits save
    2 Toffoli each, 12 per call. In general each call saves 2 Toffoli per set
    bit of its constant below the carry cut, other than bit 0.
- **Callers** (`src/point_add/modular.rs` and `mul_schoolbook.rs`):
  - the `+c` correction of `mod_double_inplace_direct`, used for the Kaliski
    STEP 7–8 doublings of `r` past `R_SMALL_THRESHOLD`, among others;
  - the `+c` step of the low-scratch modular adders
    (`mod_add_qq_lowq_lowscratch` and its relatives) and the Solinas folds;
  - `mod_neg_inplace_direct`, which adds the dense constant `p + 1` and so
    saves far more per call;
  - two `+1` uses, which save nothing.

  The total over one point addition is 5,184. See
  [modular-fold](../concepts/modular-fold.md).
- **Only the forward sweep changes.** The reverse sweep erases each carry with
  `hmr` and repairs the phase with classically conditioned `CZ`s, which cost no
  Toffoli. It sees the same carry values, so it needs no change. See
  [measurement-uncompute](../concepts/measurement-uncompute.md).

## Why it is still correct, and what it risks

The rewrite is a Boolean identity. It writes the same value into the same
carry wire, and the two pivot CX pairs restore `acc` and `ctrl`. So the state
after the sweep is the same as before on every input, and so are the measured
uncompute and its phase repair. No approximation knob moved.

The op stream still changes, so the 9,024-shot test set is drawn again (there
is no nonce in this era). The tree keeps the base's approximate knobs (W-TRUNC,
swap truncation, carry-tail, iteration counts), so a new draw could hit a hard
input. This draw is clean: 0 classical, 0 phase and 0 ancilla failures.

The submission note also records a dead end. Truncating the ADD path's carry
chain the way the SUB path is truncated gives about 141 phase-failure batches
at every width. The ADD reverse sweep uses the complemented identity
`MAJ(NOT acc_i_final, k_i, carry_i)`, and a cut chain turns its error into a
relative phase.

## Classification rationale

The published label is Dead-Code and Redundancy Elimination →
comparator/width truncation. The diff narrows nothing. It replaces a
three-Toffoli majority with an exact one-Toffoli form, which is Strength
Reduction, the label used for the same rewrite in [`d4959a1`](d4959a1.md)
("fast-adder reroute"). A closer change-type would be "majority / AND-XOR
gate fold". The header keeps the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 404d630 -- src/point_add`.
   - Do not start from the git parent `a25248f`. That is Gajesh2007's second
     version of the swap truncation, built on `d4959a1`.
   - Against the parent, the diff is 178 lines in 3 files. It would show
     `a25248f`'s `kal_cswap_wtrunc_enabled` widths being swapped back for
     `404d630`'s `kal_uv_cswap_width`, the carry-tail window going from 59 to
     49, and the one-Toffoli frame reset going back to two Toffoli. None of
     that is part of this change.
   - Against `404d630`, `git diff --ignore-cr-at-eol 404d630 c7e1ae5 -- src/point_add`
     is 31 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol c7e1ae5 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,610,715 average Toffoli (rounded)
   - score 6,028,140,935
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/cuccaro.rs b/src/point_add/cuccaro.rs
index 15f9679..d763461 100644
--- a/src/point_add/cuccaro.rs
+++ b/src/point_add/cuccaro.rs
@@ -794,14 +794,27 @@ pub(crate) fn cadd_nbit_const_direct_fast(b: &mut B, acc: &[QubitId], c: U256, c
     let carries = b.alloc_qubits(cut);
 
     // Forward carry sweep. carry_{i+1} = majority(acc_i, k_i, carry_i).
+    let majfold = majfold_add_enabled();
     for i in 0..cut {
         let target = carries[i];
         let carry_in = if i == 0 { None } else { Some(carries[i - 1]) };
         if bit(c, i) {
             if let Some(ci) = carry_in {
-                b.ccx(acc[i], ci, target);
-                b.ccx(ctrl, acc[i], target);
-                b.ccx(ctrl, ci, target);
+                // MAJ(acc[i], ctrl, ci) -> fold to 1 CCX + free CX (ci pivot):
+                // maj(a,b,d)=d^(a^d)&(b^d). Value identical -> backward Hmr
+                // measurement-uncompute (cz_if) unchanged.
+                if majfold {
+                    b.cx(ci, acc[i]);
+                    b.cx(ci, ctrl);
+                    b.ccx(acc[i], ctrl, target);
+                    b.cx(ci, target);
+                    b.cx(ci, ctrl);
+                    b.cx(ci, acc[i]);
+                } else {
+                    b.ccx(acc[i], ci, target);
+                    b.ccx(ctrl, acc[i], target);
+                    b.ccx(ctrl, ci, target);
+                }
             } else {
                 b.ccx(acc[i], ctrl, target);
             }
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index f85704e..e7dd77c 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -219,6 +219,18 @@ pub(crate) fn majfold_sub_enabled() -> bool {
     std::env::var("KAL_MAJFOLD_SUB").ok().as_deref() != Some("0")
 }
 
+/// MAJ-FOLD (ADD path): mirror of [`majfold_sub_enabled`] for the direct
+/// const-ADD forward AND inverse carry majorities in
+/// `cadd_nbit_const_direct_fast`. Forward carry is maj(acc_i, ctrl, carry_i);
+/// inverse carry is maj(!acc_i_final, ctrl, carry_i). Both fold to 1 CCX + free
+/// CX using the carry-in `ci` as the pivot (maj(a,b,d)=d^(a^d)&(b^d)). The
+/// computed carry value is identical to the 3-CCX form, so the sum XOR and the
+/// backward Hmr cz_if measurement-uncompute are byte-unchanged.
+/// KAL_MAJFOLD_ADD=0 disables. Default-ON (validated 9024-clean).
+pub(crate) fn majfold_add_enabled() -> bool {
+    std::env::var("KAL_MAJFOLD_ADD").ok().as_deref() != Some("0")
+}
+
 pub(crate) fn kal_carrytail_w() -> usize {
     // Banked clean island: SUB W=36 (paired with WTRUNC K0=26, margin=3, MAJ-fold
     // SUB on). The carry-tail SUB borrow chain runs to bit 33+36=69, far above the
```

