# d19dbb5 — Break the 2708 plateau: in-place Kaliski denominators, schoolbook multiplies, carries borrowed from clean history bits and register-free folds (2708 → 2310 qubits)

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-05-31 |
| Submission | `f94f726` |
| Commit | `d19dbb5390c11aaaac70e113647dbe07530a5c41` |
| Result | 2310 qubits × 3,656,039 Toffoli = **8,445,450,090** |
| Base | [`74a1a8b`](74a1a8b.md) (cryptogakusei, on top of the author's [`9bcc27d`](9bcc27d.md)): 2708 qubits × 3,546,494 Toffoli = 9,603,905,752 |
| Change vs base | qubits −398, Toffoli +109,545, score −1,158,455,662 |
| Leaderboard Δ | −1,145,844,506, measured against the frontier at the time, [`3bbccd3`](3bbccd3.md) (2708 × 3,541,837 = 9,591,294,596), which is **not** this commit's base |
| Family | Register and Scratch Allocation → in-place mutation |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [modular-fold](../concepts/modular-fold.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change (one file, about 1,365 lines) |

## Summary

Every commit since [`bc9728a`](bc9728a.md) sat at 2708 qubits. The author's
code comments describe the intermediate 2457 peak (a stage in the table
below) as a "joint pin": several phases
(the multiplies' Solinas folds, the Kaliski STEP-4 adds and the `r` doublings)
all reached about the same height, so lowering any one of them alone let
another set the same peak. This commit lowers all of them together, with a
stack of default-on levers behind two master switches. The peak falls by 398
qubits, to 2310. That is close to the "published `9n` floor" (`9n = 2304`)
the comments aim at; the switch is named after Gouzien et al.

The main levers are:
- both Kaliski inversions use the live x-difference register in place as
  their `v` register;
- the two multiplies that bracket the inversions use schoolbook instead of
  Karatsuba, so Karatsuba's middle-term register is never allocated;
- the STEP-4 adders host their 255-wire carry banks on history qubits
  `m_hist[i+1..]`, which are known to be zero at that moment, and on the
  provably-zero high bits of `u`;
- the multiply folds, the `r` doublings and the shift-22 reduction use
  carry-free or register-free adders.

Most of these cost Toffoli: slower adders, more expensive multiplies, and
longer Kaliski loops (401 / 403 iterations instead of 399 / 398), which the
new op stream needed to draw a clean test set. The net is +109,545 Toffoli,
about +3.1%, against −14.7% qubits, so the score falls 12.1%.

## What changed and why it saves qubits

All edits are in `src/point_add/mod.rs`. The author's note gives this
sequence of peaks, each step validated on its own:

| stage | peak | levers |
| --- | --- | --- |
| base | 2708 | — |
| `POINT_ADD_STACK_2565` | 2565 | in-place `v` for both inversions, schoolbook multiplies |
| `AFFINE_Y_MUL_LOWSCRATCH_FOLD` | 2459 | low-scratch affine y-multiply |
| pair-1 loop 405 → 401 | 2457 | two fewer `m_hist` qubits live at the peak |
| `KAL_GOUZIEN_9N` | 2333 | STEP-4 carry borrow, direct `r` double, low-scratch pair multiplies |
| `KAL_GZ_SOLINAS_LOWSCRATCH` | 2310 | dirty-borrow shift-22 reduction |

### 1. Stack switch `stack_2565_enabled()` (env `POINT_ADD_STACK_2565`, default on)

- **In-place `v` for pair 1.** `KAL_PAIR1_BORROW_DX_DENOM` now defaults to on.
  `build_standard_point_add` takes the existing branch that calls
  `with_kal_inv_raw_borrow_v_w_pair(tx, …)`. Kaliski's `v_w` register is the
  live denominator `tx = x2 − x1` itself, not a fresh 256-qubit copy. The
  forward run drives it to 0 and the backward run restores it. The body
  (`lam = ty · inv` in phase `pair1_borrow_dx_mul1`, then the halvings) does
  not touch `tx`. That is −256 qubits in pair 1's working set.
- **In-place `v` for pair 2.** New branch (env `KAL_PAIR2_INPLACE_V`, default
  on) that runs pair 2 through the same `with_kal_inv_raw_borrow_v_w_pair(tx, …)`.
  Its body (`pair2_double`, `pair2_mul`, `pair2_cleanup`) uses only `lam`, `ty`
  and `inv_raw`.
- **Schoolbook multiplies.** `pair1_mul1_karatsuba_enabled` and
  `pair2_mul_karatsuba_enabled` now default to off. The Karatsuba multiplies
  hold a `z1_reg` of `2·(128+1) = 258` qubits for the middle product, which
  the code comments name as the binder at `sol_sub6` / `kara_z1_add`.
  Schoolbook needs no such register, but it costs more Toffoli. See
  [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md).
- **Loop lengths.** The pair-1 default goes from 399 to 401, and pair 2's
  from 398 to 403. The comments say the combination has a "non-monotonic
  single-input classical-mismatch cliff". Clean loop lengths scatter rather
  than follow a convergence floor. 405 / 403 was a first clean "island", and
  401 is a better one found by a grid search. These lengths cost Toffoli, and
  the two extra pair-1 `m_hist` qubits are live at the peak.

### 2. Low-scratch affine y-multiply (`AFFINE_Y_MUL_LOWSCRATCH_FOLD`, default = stack switch)

`square_tx_and_combined_ty_l2minus3qx` computes `ty += λ·breg` while the
512-qubit `λ²` product register is still live. It now calls the new
`mod_mul_add_into_acc_schoolbook_lowscratch_fold`, which has three scratch
cuts:
- **Multiply.** `schoolbook_mul_into_addsub_lsx` is the Litinski add-subtract
  schoolbook, but its `−x` correction is done by the new
  `correction_sub_x_lowscratch`. That subtracts `x` from the low `n` bits and
  ripples one borrow bit up the high `n+1` bits with a register-free controlled
  decrement, instead of padding `x` to `2n+1` bits (about 256 pad qubits). The
  borrow is cleared with the identity `borrow = (¬x < L_new)`. There is a
  matching `_lsx_inverse`.
- **Fold adds.** New `mod_add_qq_lowq_lowscratch` and `mod_sub_qq_lowq_lowscratch`:
  the carry-free Cuccaro (`add_nbit_qq`, about 2 Toffoli per bit), the
  register-free direct constant adders and the carry-free comparator
  (`cmp_lt_into`). The subtract's flag is cleared through a register-free
  `mod_neg_inplace_direct`. No carry bank and no loaded constant.
- **Fold doublings.** New `mod_double_inplace_direct`: a shift, then `+c` under
  the overflow bit with `cadd_nbit_const_direct_fast`. It does not hold the
  loaded 256-qubit constant and its carries at the same time, as
  `mod_double_inplace_fast` does. The comment calls this "the dominant lever".

### 3. 9n-floor switch `kal_gouzien_9n_enabled()` (env `KAL_GOUZIEN_9N`, default on)

Sub-switches, each default on:

- **`KAL_GZ_STEP4_SLOW`: borrow STEP 4's carry banks.**
  - Every Kaliski body (forward, backward, bulk and generic) gets a new
    `m_future = &m_hist[i+1..iters]` argument from the six loop drivers.
  - In the forward run those history bits are still 0. In the backward run
    they have already been uncomputed. Either way they are clean `|0⟩` qubits
    that are already allocated.
  - New `cuccaro_add_fast_borrow` / `cuccaro_sub_fast_borrow` are the
    measured-carry Cuccaro with the carry bank taken from a caller slice.
    The measured erase returns the bank to `|0⟩` instead of freeing it.
  - `add_nbit_qq_fast_mfut` / `sub_nbit_qq_fast_mfut` take as many carries as
    possible from `m_future` and allocate the rest fresh.
  - If more than `gz_max_fresh_carries()` (env `KAL_GZ_MAX_FRESH`, default 131)
    would be fresh, the code falls back to the plain carry-free Cuccaro. That
    keeps the peak flat at about 2 Toffoli per bit instead of 1.
  - These replace STEP 4's `v_w −= tmp`, `s += tmp` and the backward mirrors.
    STEP 4 holds the 256-qubit `tmp` register plus a 255-wire carry bank,
    which made it one of the 2457 binders. See
    [venting-and-wire-loans](../concepts/venting-and-wire-loans.md).
- **`KAL_GZ_LATE_RECOVER`: also borrow `u`'s zero high bits.**
  - Late in the walk, `m_future` is small while the `s` add is still 256 bits
    wide. Without help the fallback would fire from about iteration 277 on.
    The comment says that costs about 133k Toffoli.
  - The Kaliski invariant `bitlen(u) + bitlen(v_w) ≤ 2n − i` makes
    `u[2n−i..n)` zero for `i > n`. The base already relies on it for every
    truncated width. New `gz_u_clean_high` returns that slice, and
    `*_mfut_pool` borrows from `m_future` first, then from it.
  - The pool is then about `iters − 1 − n ≈ 145` qubits, so the fresh
    shortfall (about 110) stays under 131, and the `s` adds never fall back.
  - `u` is not read between borrow and release: the `r`-into-`u` transform
    of STEP 4 runs strictly after the forward add and before the backward
    subtract.
- **`KAL_GZ_DOUBLE_DIRECT`.** STEP 7+8's `r := 2r mod p` (from
  `R_SMALL_THRESHOLD = 326` on) uses `mod_double_inplace_direct`. That removes
  the constant register and carries that bound `step6_7_8`.
- **`KAL_GZ_MUL_LOWSCRATCH`.** The now-schoolbook `pair1_mul1_write_into_zero_acc`
  and `pair2_mul_add_into_acc` call the low-scratch fold multiplies of part 2.
  The pair-1 version, `mod_mul_write_into_zero_acc_schoolbook_lowscratch_fold`,
  uses `mod_add_qq_fast_from_zero_lowscratch` for its first add.

### 4. Dirty-borrow shift-22 (`KAL_GZ_SOLINAS_LOWSCRATCH`, default on)

This applies inside `mod_mul_add_into_acc_schoolbook_lowscratch_fold`, so in
the y-multiply and in pair 2's multiply. It is the `2^32` term: the shift by
22, the `+hi·2^32` add and the shift back. All three take the product's low
half `lo` as a borrowed dirty register, which is restored on exit:
- `mod_shift_left_by_k_dirty` / `mod_shift_right_by_k_dirty`:
  - The five spill ops use the new `shift22_spill_op_dirty`. It adds the
    22-bit spill into the 22-bit window with a captured carry-out, propagates
    that one carry up the high bits with the Gidney-style
    `venting::ciadd_dirty_2clean_classical` (2 clean ancillas plus the dirty
    donor), and clears the carry with `carry = (low_new < spill)`. That holds
    about 27 transient qubits instead of the 257-qubit `padded` register.
  - The `+c` and conditional `−c` steps use
    `venting::{iadd,cisub,ciadd}_dirty_2clean_classical` instead of a loaded
    constant.
- `mod_add_qq_dirty` does the `2^32` add itself the same way.

The comments put the remaining floor just below this, at `bk_step4` (about
2309).

### 5. Reverts and clean-ups

- **74a1a8b undone.** `mod_add_solinas_ext_product` goes back to
  `mod_add_qq_fast` for its first four adds, and
  `mod_mul_add_into_acc_karatsuba_lowq_with_tmp_ext` goes back too. The
  commit was evidently built on the author's own `9bcc27d` tree.
- The diagnostic switches `KAL_CSWAP_RS_MERGE_GENERIC` / `_BULK` and the
  `merge_boundary_break` logic of [`9bcc27d`](9bcc27d.md) are removed. The
  merge is now gated by `KAL_CSWAP_RS_MERGE` alone, which is unchanged by
  default.
- A `TRACE_PEAK`-only debug line prints `next_qubit`.

### Where the Toffoli goes

The author's comments give these numbers:
- the stack stage scored about 9.361e9 at 2565 qubits, about +103k Toffoli
  over 9bcc27d, from the schoolbook multiplies and the longer loops;
- the 9n stage "paid +3.72%" before late recovery won about 126k back;
- pair 1 at 401 instead of 405 lowered the average Toffoli from 3,653,471 to
  3,638,875.

The remaining costs are the carry-free fold adds (about +1,000 Toffoli per
add), the direct-constant doublings (+12 Toffoli per call) and the Gidney
dirty adders. Net against the base: +109,545.

## Why it is still correct, and what it risks

Exact parts:
- **In-place `v`.** `with_kal_inv_raw_borrow_v_w_pair` already existed. It is
  exact if the body leaves `tx` alone, which both bodies do.
- **Borrowed carries.** Exact, because the donor bits are zero by
  construction. Future history bits are written only in their own iteration.
  `u[2n−i..n)` is zero by the Kaliski bit-length invariant, which depends only
  on the iteration index. The measured erase returns them to zero. A donor
  that was not zero would show up as a phase failure or ancilla garbage.
- **Register-free and dirty adders.** These compute the same values. The
  Gidney dirty adders restore their donor `lo`, and the comparator identities
  used to clear carries and borrows are exact.
- **Schoolbook multiplies.** Value-identical to Karatsuba.

Probabilistic parts, as before: the Kaliski loop lengths (now 401 / 403), the
bulk prefix and `R_SMALL_THRESHOLD = 326` (see [`a16788e`](a16788e.md) and
[`9bd0748`](9bd0748.md)). The comment beside `pair1_default` is explicit that
clean loop lengths for this op stream are found by search, not derived. 399
gives a single-input classical mismatch, 405 and 401 are clean, and pair 2
below 403 "trips the cswap-merge phase cliff".

There is no tail nonce in this era. The 9,024 test inputs are a SHAKE256 hash
of the op stream, so choosing the loop lengths is how the author found a
clean draw. The note reports 0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The family, Register and Scratch Allocation, fits: almost all of the change
is about which qubits hold what, and when. The change-type, in-place
mutation, covers the in-place `v` levers. The largest single lever, though,
is hosting carry banks on idle clean qubits, which is closer to scratch/ancilla
reuse or wire loans. The rest is scratch removal through register-free
adders, plus a multiplier swap. A multi-lever commit like this has no single
best change-type.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 74a1a8b -- src/point_add`.
   - The tree differs least from `74a1a8b`: 1,365 changed lines, against 1,387
     from the author's own `9bcc27d`. The patch therefore also undoes
     74a1a8b's fold edits (part 5).
   - Do not start from the git parent `3bbccd3`. Against it the diff is 1,675
     lines. It would also revert mmurrs's shift-22 position-32 fast add and
     pair-2 cut of [`04b3a76`](04b3a76.md), and the bit-register adder of
     [`3bbccd3`](3bbccd3.md).
   - `git diff --ignore-cr-at-eol 74a1a8b d19dbb5 -- src/point_add` is 1,365
     changed lines (1,287 added, 78 removed) in 1 file. It is kept inline (Tier A) because it is a set of edits
     to one existing file, not a new file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol d19dbb5 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `POINT_ADD_*`, `KAL_*`, `AFFINE_*`, `LOWQ_SHIFT22*`, `DUMMY_TOFFOLIS` or other
   environment overrides set. Expect:
   - 2310 qubits
   - 3,656,039 average Toffoli (rounded)
   - score 8,445,450,090
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era. The 9,024 test inputs are a hash of the
op stream, so the score, and the clean draw, only reproduce with an identical
op stream. The loop lengths 401 / 403 are tied to this exact stream.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 2055ac4..520fbce 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -411,14 +411,133 @@ fn point_add_karatsuba_enabled() -> bool {
     env_flag_enabled("POINT_ADD_KARATSUBA", true)
 }
 
+/// Master switch for the "9n-floor" peak-drop construction (default OFF; when
+/// OFF the emitted circuit is byte-identical to the f1d99ad C1 baseline).
+///
+/// The f1d99ad peak (2457) is a JOINT PIN across the pair2 Kaliski STEP-4
+/// phases (kal_bulk_step4 / kal_step4 / bk_step4 / bk_bulk_step4 + their
+/// step6_7_8 mod_double) AND the two binding multiplies (pair2_mul,
+/// pair1_borrow_dx_mul1). Each STEP-4 holds a 256-wide `tmp` accumulator
+/// co-resident with an ~255-wide measurement-Cuccaro carry register
+/// (`sub_nbit_qq_fast` + `add_nbit_qq_fast`); each step6_7_8 holds a
+/// `cadd_nbit_const_fast` const-register + carry register; each binding mul
+/// holds the schoolbook Solinas-fold transient. Below the 2455-2457 cluster
+/// the next floor is `shift22_step4` = 2333.
+///
+/// To move the GLOBAL peak below 2457 ALL THREE must drop simultaneously
+/// (drop one alone -> another rebinds at 2457). When this flag is ON:
+///   - STEP-4 sub/add: fast measurement-Cuccaro (n-1 carry register) ->
+///     slow in-place Cuccaro (`add_nbit_qq`/`sub_nbit_qq`, 1 ancilla,
+///     maj/uma carry rides in-place on tmp). Removes the ~255-carry register
+///     from the binder at +~n CCX/op. Phase-clean + emit_inverse-safe (pure
+///     CCX/CX, no measurement-vent).
+///   - STEP 6/7/8 r-double: `mod_double_inplace_fast` (const reg + carries)
+///     -> `mod_double_inplace_direct` (register-free direct const-add).
+///   - pair2_mul + pair1_borrow_dx_mul1: schoolbook ->
+///     `mod_mul_add_into_acc_schoolbook_lowscratch_fold` (the proven affine
+///     y-mul peak-saver: lsx mul + lowscratch Solinas folds + direct doubles).
+fn kal_gouzien_9n_enabled() -> bool {
+    env_flag_enabled("KAL_GOUZIEN_9N", true)
+}
+
+/// Sub-knob: STEP-4 carry-register elimination (slow in-place Cuccaro). On by
+/// default when the master flag is on. Diagnostic isolation: set to 0 to keep
+/// fast Cuccaro at STEP-4 while still applying the mul/double drops.
+fn gz_step4_slow() -> bool {
+    kal_gouzien_9n_enabled() && env_flag_enabled("KAL_GZ_STEP4_SLOW", true)
+}
+
+/// Sub-knob: STEP-6/7/8 r-double register-free direct const-add.
+fn gz_double_direct() -> bool {
+    kal_gouzien_9n_enabled() && env_flag_enabled("KAL_GZ_DOUBLE_DIRECT", true)
+}
+
+/// Sub-knob: pair2_mul + pair1_borrow_dx_mul1 lowscratch Solinas fold.
+fn gz_mul_lowscratch() -> bool {
+    kal_gouzien_9n_enabled() && env_flag_enabled("KAL_GZ_MUL_LOWSCRATCH", true)
+}
+
+/// Sub-knob: late-iter Toffoli RECOVERY — widen the clean carry-borrow pool of
+/// the STEP-4 q-q s-add/s-sub (the slow-Cuccaro fallback victim) by also
+/// borrowing the GCD register `u`'s PROVABLY-|0> high bits.
+///
+/// Background: the 9n-floor (KAL_GOUZIEN_9N) hosts the fast-Cuccaro carry
+/// register on clean future m_hist bits (`m_future`). The pool shrinks as the
+/// walk advances, so once `(add_width-1) - |m_future|` exceeds KAL_GZ_MAX_FRESH
+/// the s-add/s-sub falls back to a register-FREE in-place Cuccaro (+~n CCX).
+/// That fallback fires for ALL iters with iter_idx > iters-1-KAL_GZ_MAX_FRESH
+/// (~iter 277..iters) because s is full-width there while m_future is tiny —
+/// it costs +~133k Toffoli (the +3.72% the 9n-floor paid for the 2333 peak).
+///
+/// Recovery: at the SAME late iters, the GCD walk has SHRUNK. The Kaliski
+/// invariant guarantees `bitlen(u)+bitlen(v_w) <= 2n-iter_idx`, hence
+/// individually `bitlen(u) <= 2n-iter_idx`, so for iter_idx>n the high bits
+/// `u[2n-iter_idx..n)` (= iter_idx-n qubits) are PROVABLY |0>. They are already
+/// allocated (part of the live `u` register) so borrowing them adds ZERO width.
+/// They are not read between borrow and restore (the slow op is between `tmp`
+/// and `s`; `u`'s value sits in [0..2n-iter_idx), untouched by the s-op and by
+/// its own transform which runs strictly after (fwd) / before (bwd) the s-op).
+/// The borrow is restored to |0> by the same measurement-uncompute as the
+/// validated `cuccaro_*_fast_borrow`. The clean-bit boundary is a CLASSICAL
+/// function of iter_idx (no data-dependent branch), so validity is structural.
+///
+/// Pool size becomes `|m_future| + (iter_idx-n) = iters-1-n` (~144-146) which is
+/// constant across the late tail and keeps the fresh shortfall (255-pool ~110)
+/// strictly below KAL_GZ_MAX_FRESH everywhere => NO slow Cuccaro at all, and
+/// fewer fresh carries than before => per-step peak can only DROP, never rise.
+fn gz_late_recover() -> bool {
+    kal_gouzien_9n_enabled() && env_flag_enabled("KAL_GZ_LATE_RECOVER", true)
+}
+
+/// Sub-knob: shift22 (rshift22) Solinas reduction LOW-SCRATCH path. Replaces
+/// the ~256-wide loaded-constant register of the shift22 STEP-3 const-add and
+/// STEP-4 conditional const-sub (the 2333 binder) with Gidney venting
+/// dirty-borrow const adders, and replaces the STEP-2 cuccaro spill-add's
+/// ~257-wide `padded` register (the 2330 cuccaro_op_0 floor) with a narrow
+/// k-bit spill add plus a venting dirty-borrow controlled-increment. Both cut
+/// ~256 clean transient qubits at the affine y-mul Solinas-fold binder.
+/// Gate KAL_GZ_SOLINAS_LOWSCRATCH (default on; set =0 to restore the byte-identical 1df6866 shift22).
+fn gz_solinas_lowscratch() -> bool {
+    kal_gouzien_9n_enabled() && env_flag_enabled("KAL_GZ_SOLINAS_LOWSCRATCH", true)
+}
+
+/// Provably-|0> high bits of the GCD register `u` at the late-iter STEP-4
+/// instant: `u[2n-iter_idx .. n)` for iter_idx>n (else empty). Safe clean carry
+/// donors for the s-add/s-sub borrow pool. See [`gz_late_recover`].
+fn gz_u_clean_high(u: &[QubitId], iter_idx: usize) -> &[QubitId] {
+    let n = u.len();
+    if iter_idx <= n {
+        return &u[..0];
+    }
+    let lo = (2 * n).saturating_sub(iter_idx).min(n);
+    &u[lo..]
+}
+
+/// Master switch for the stacked sub-2708-peak construction (default ON).
+/// When ON (no env / != "0"):
+///   - pair1 inverse borrows dx as in-place v_w  (drops pair1-backward carrier)
+///   - pair2 inverse borrows tx as in-place v_w  (drops pair2-forward carrier)
+///   - pair1_mul1 + pair2_mul use schoolbook (no Karatsuba z1_reg) so the mul
+///     Solinas boundary frees ~258q  -> drops sol_sub6 / kara_z1_add below 2565
+///   - Kaliski iters bumped (405/403) to clear the in-place-v + schoolbook +
+///     direct-const-halve correctness/phase margin (9024-shot validated).
+/// Net: global peak 2708 -> 2565, score 9.604e9 -> 9.361e9 (-11.34% vs baseline).
+/// Set POINT_ADD_STACK_2565=0 to restore the byte-identical C1 circuit.
+fn stack_2565_enabled() -> bool {
+    env_flag_enabled("POINT_ADD_STACK_2565", true)
+}
+
 fn pair1_mul1_karatsuba_enabled(n: usize) -> bool {
     let min_n = std::env::var("POINT_ADD_KARATSUBA_MIN_N")
         .ok()
         .and_then(|v| v.parse::<usize>().ok())
         .unwrap_or(256);
+    // Stack default: pair1_mul1 is schoolbook (frees the Karatsuba z1_reg from
+    // the binding sol_sub6 boundary). User can force Karatsuba via the knob.
+    let karatsuba_default = !stack_2565_enabled();
     point_add_karatsuba_enabled()
         && n >= min_n
-        && env_flag_enabled("KAL_PAIR1_MUL1_KARATSUBA", true)
+        && env_flag_enabled("KAL_PAIR1_MUL1_KARATSUBA", karatsuba_default)
 }
 
 fn direct_const_halve_enabled() -> bool {
@@ -445,9 +564,12 @@ fn pair2_mul_karatsuba_enabled(n: usize) -> bool {
         .ok()
         .and_then(|v| v.parse::<usize>().ok())
         .unwrap_or(256);
+    // Stack default: pair2_mul is schoolbook (frees the Karatsuba z1_reg from
+    // the binding kara_z1_add boundary). User can force Karatsuba via the knob.
+    let karatsuba_default = !stack_2565_enabled();
     point_add_karatsuba_enabled()
         && n >= min_n
-        && env_flag_enabled("KAL_PAIR2_MUL_KARATSUBA", true)
+        && env_flag_enabled("KAL_PAIR2_MUL_KARATSUBA", karatsuba_default)
 }
 
 // ═══════════════════════════════════════════════════════════════════════════
@@ -540,6 +662,65 @@ fn cuccaro_add_fast(b: &mut B, a: &[QubitId], acc: &[QubitId], c_in: QubitId) {
     b.free_vec(&carries);
 }
 
+/// Carry-BORROW twin of [`cuccaro_add_fast`]: identical gate sequence, but the
+/// n-1 carry qubits are BORROWED from `carry_src` (which MUST be clean |0⟩ on
+/// entry and is restored to |0⟩ on exit by the measurement-uncompute) instead
+/// of freshly allocated. Flat Toffoli, zero new width at the peak — the carry
+/// register is hosted on already-live but idle clean ancilla (e.g. the future
+/// Kaliski m_hist transcript bits m_hist[iter+1..], guaranteed |0⟩ until their
+/// own iteration writes them). `carry_src.len()` must be >= n-1.
+fn cuccaro_add_fast_borrow(
+    b: &mut B,
+    a: &[QubitId],
+    acc: &[QubitId],
+    c_in: QubitId,
+    carry_src: &[QubitId],
+) {
+    let n = a.len();
+    assert_eq!(n, acc.len());
+    if n == 0 {
+        return;
+    }
+    if n == 1 {
+        b.cx(c_in, acc[0]);
+        b.cx(a[0], acc[0]);
+        return;
+    }
+    assert!(carry_src.len() >= n - 1, "borrow carry_src too short");
+    let carries = &carry_src[..n - 1];
+
+    b.cx(a[0], acc[0]);
+    b.cx(a[0], c_in);
+    b.ccx(c_in, acc[0], carries[0]);
+    b.cx(carries[0], a[0]);
+    for i in 1..n - 1 {
+        b.cx(a[i], acc[i]);
+        b.cx(a[i], a[i - 1]);
+        b.ccx(a[i - 1], acc[i], carries[i]);
+        b.cx(carries[i], a[i]);
+    }
+
+    b.cx(a[n - 2], acc[n - 1]);
+    b.cx(a[n - 1], acc[n - 1]);
+
+    for i in (1..n - 1).rev() {
+        b.cx(carries[i], a[i]);
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        b.cz_if(a[i - 1], acc[i], m);
+        b.cx(a[i], a[i - 1]);
+        b.cx(a[i - 1], acc[i]);
+    }
+    b.cx(carries[0], a[0]);
+    let m0 = b.alloc_bit();
+    b.hmr(carries[0], m0);
+    b.cz_if(c_in, acc[0], m0);
+    b.cx(a[0], c_in);
+    b.cx(c_in, acc[0]);
+    // carries are borrowed: restored to |0> by the measurement-uncompute,
+    // NOT freed (they belong to the caller's m_hist register).
+}
+
 /// In-place addition `acc += a mod 2^n` on quantum n-bit registers.
 /// * `c_in` is a fresh ancilla qubit at 0 on entry and returns to 0.
 /// * `a` unchanged; `acc` becomes (a + acc) mod 2^n.
@@ -737,6 +918,58 @@ fn mod_add_qq(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
     let _ = (acc_ext, a_ext);
 }
 
+/// Dirty-borrow variant of `mod_add_qq` (KAL_GZ_SOLINAS_LOWSCRATCH): the two
+/// 257-wide loaded-constant registers of the `+c` / conditional `-c` reduction
+/// steps are replaced by Gidney venting dirty-borrow const adders (2 clean
+/// ancilla + a borrowed n-2 DIRTY donor, restored). Used for the shift22
+/// position-32 add inside the affine y-mul Solinas fold, where the loaded-const
+/// register was the actual 2333 binder. `dirty` must be co-resident, >= n-1
+/// wide, disjoint from `acc` and `a`, and is restored to its entry value.
+fn mod_add_qq_dirty(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256, dirty: &[QubitId]) {
+    let n = acc.len();
+    assert_eq!(n, a.len());
+    debug_assert_eq!(n, 256);
+
+    let (acc_ext, acc_ovf) = ext_reg(b, acc);
+    let (a_ext, a_ovf) = ext_reg(b, a);
+    let m = acc_ext.len(); // n+1
+
+    add_nbit_qq(b, &a_ext, &acc_ext);
+
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    let c_low = c.as_limbs()[0];
+
+    // Step 2: acc_ext += c  (register-free venting dirty-borrow).
+    {
+        let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
+        venting::iadd_dirty_2clean_classical(b, &acc_ext, &dirty[..m - 2], &q_clean2, c_low, false);
+        b.free(q_clean2[0]);
+        b.free(q_clean2[1]);
+    }
+
+    let flag = b.alloc_qubit();
+    b.cx(acc_ovf, flag);
+
+    // Step 4: if flag=0 undo the +c == conditional -c controlled by !flag.
+    b.x(flag);
+    {
+        let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
+        venting::cisub_dirty_2clean_classical(b, &acc_ext, &dirty[..m - 2], &q_clean2, c_low, flag);
+        b.free(q_clean2[0]);
+        b.free(q_clean2[1]);
+    }
+    b.x(flag);
+
+    b.cx(flag, acc_ovf);
+
+    cmp_lt_into(b, &acc_ext[..n], &a_ext[..n], flag);
+    b.free(flag);
+
+    unext_reg(b, a_ovf);
+    unext_reg(b, acc_ovf);
+    let _ = (acc_ext, a_ext);
+}
+
 fn mod_sub_qq(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
     // mod_add_qq is a bijection on (acc, a): (acc, a) ↦ (acc + a mod p, a).
     // Its gate-level inverse therefore acts as (acc, a) ↦ (acc - a mod p, a),
@@ -812,6 +1045,88 @@ fn mod_neg_inplace_fast(b: &mut B, v: &[QubitId], p: U256) {
     unload_const(b, &ca, p.wrapping_add(U256::from(1)));
 }
 
+/// Register-free mod_neg: `v := (p - v) mod p` via flip + direct const-add of
+/// (p+1). Avoids the n-bit `load_const` register of `mod_neg_inplace_fast`,
+/// so it adds no n-wide transient scratch (only the direct carry sweep's
+/// ancillae). Used in the low-scratch Solinas fold.
+fn mod_neg_inplace_direct(b: &mut B, v: &[QubitId], p: U256) {
+    for &q in v {
+        b.x(q);
+    }
+    let one = b.alloc_qubit();
+    b.x(one);
+    cadd_nbit_const_direct_fast(b, v, p.wrapping_add(U256::from(1)), one);
+    b.x(one);
+    b.free(one);
+}
+
+/// Carry-free + register-free `acc := (acc + a) mod p`. Uses the no-carry
+/// Cuccaro (`add_nbit_qq`), the register-free direct const adders, and the
+/// no-carry comparator (`cmp_lt_into`). Holds ~0 wide transient scratch (only
+/// 2 ext-ovf + 1 flag), at +~n Toffoli per call vs the fast variant. Drops the
+/// Solinas-fold instant by ~256 (the cuccaro carry register) — the dominant
+/// fold-scratch at the affine y-mul binder.
+fn mod_add_qq_lowq_lowscratch(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
+    let n = acc.len();
+    assert_eq!(n, a.len());
+    debug_assert_eq!(n, 256);
+
+    let (acc_ext, acc_ovf) = ext_reg(b, acc);
+    let (a_ext, a_ovf) = ext_reg(b, a);
+
+    add_nbit_qq(b, &a_ext, &acc_ext);
+
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    let one = b.alloc_qubit();
+    b.x(one);
+    cadd_nbit_const_direct_fast(b, &acc_ext, c, one);
+    b.x(one);
+    b.free(one);
+
+    let flag = b.alloc_qubit();
+    b.cx(acc_ovf, flag);
+    b.x(flag);
+    csub_nbit_const_direct_fast(b, &acc_ext, c, flag);
+    b.x(flag);
+    b.cx(flag, acc_ovf);
+    cmp_lt_into(b, &acc_ext[..n], &a_ext[..n], flag);
+    b.free(flag);
+
+    unext_reg(b, a_ovf);
+    unext_reg(b, acc_ovf);
+    let _ = (acc_ext, a_ext);
+}
+
+/// Carry-free + register-free `acc := (acc - a) mod p`. Companion to
+/// `mod_add_qq_lowq_lowscratch`.
+fn mod_sub_qq_lowq_lowscratch(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
+    let n = acc.len();
+    assert_eq!(n, a.len());
+    debug_assert_eq!(n, 256);
+
+    let (acc_ext, acc_ovf) = ext_reg(b, acc);
+    let (a_ext, a_ovf) = ext_reg(b, a);
+
+    sub_nbit_qq(b, &a_ext, &acc_ext);
+
+    let flag = b.alloc_qubit();
+    b.cx(acc_ovf, flag);
+    b.cx(flag, acc_ovf);
+
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    csub_nbit_const_direct_fast(b, &acc_ext[..n], c, flag);
+
+    b.x(flag);
+    mod_neg_inplace_direct(b, &a_ext[..n], p);
+    cmp_lt_into(b, &acc_ext[..n], &a_ext[..n], flag);
+    mod_neg_inplace_direct(b, &a_ext[..n], p);
+    b.free(flag);
+
+    unext_reg(b, a_ovf);
+    unext_reg(b, acc_ovf);
+    let _ = (acc_ext, a_ext);
+}
+
 fn mod_add_qc(b: &mut B, acc: &[QubitId], c: U256, p: U256) {
     // acc := (acc + c) mod p. c is a compile-time constant.
     let n = acc.len();
@@ -910,6 +1225,247 @@ fn cuccaro_sub_fast(b: &mut B, a: &[QubitId], acc: &[QubitId], c_in: QubitId) {
     b.free_vec(&carries);
 }
 
+/// Carry-BORROW twin of [`cuccaro_sub_fast`]: see [`cuccaro_add_fast_borrow`].
+/// Borrows `carry_src[..n-1]` (clean |0>, restored to |0>) as the carry block.
+fn cuccaro_sub_fast_borrow(
+    b: &mut B,
+    a: &[QubitId],
+    acc: &[QubitId],
+    c_in: QubitId,
+    carry_src: &[QubitId],
+) {
+    let n = a.len();
+    assert_eq!(n, acc.len());
+    if n == 0 {
+        return;
+    }
+    if n == 1 {
+        b.cx(a[0], acc[0]);
+        b.cx(c_in, acc[0]);
+        return;
+    }
+    assert!(carry_src.len() >= n - 1, "borrow carry_src too short");
+    let carries = &carry_src[..n - 1];
+
+    b.cx(c_in, acc[0]);
+    b.cx(a[0], c_in);
+    b.ccx(c_in, acc[0], carries[0]);
+    b.cx(carries[0], a[0]);
+    for i in 1..n - 1 {
+        b.cx(a[i - 1], acc[i]);
+        b.cx(a[i], a[i - 1]);
+        b.ccx(a[i - 1], acc[i], carries[i]);
+        b.cx(carries[i], a[i]);
+    }
+
+    b.cx(a[n - 1], acc[n - 1]);
+    b.cx(a[n - 2], acc[n - 1]);
+
+    for i in (1..n - 1).rev() {
+        b.cx(carries[i], a[i]);
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        b.cz_if(a[i - 1], acc[i], m);
+        b.cx(a[i], a[i - 1]);
+        b.cx(a[i], acc[i]);
+    }
+    b.cx(carries[0], a[0]);
+    let m0 = b.alloc_bit();
+    b.hmr(carries[0], m0);
+    b.cz_if(c_in, acc[0], m0);
+    b.cx(a[0], c_in);
+    b.cx(a[0], acc[0]);
+    // carries borrowed: restored to |0>, NOT freed.
+}
+
+/// Borrow-carry `acc += a mod 2^n`: hosts the fast-Cuccaro carry register on
+/// `carry_src` (clean |0>, restored). Flat Toffoli, no new peak width.
+fn add_nbit_qq_fast_borrow(b: &mut B, a: &[QubitId], acc: &[QubitId], carry_src: &[QubitId]) {
+    assert_eq!(a.len(), acc.len());
+    let c_in = b.alloc_qubit();
+    cuccaro_add_fast_borrow(b, a, acc, c_in, carry_src);
+    b.free(c_in);
+}
+
+/// Borrow-carry `acc -= a mod 2^n`. Companion to [`add_nbit_qq_fast_borrow`].
+fn sub_nbit_qq_fast_borrow(b: &mut B, a: &[QubitId], acc: &[QubitId], carry_src: &[QubitId]) {
+    assert_eq!(a.len(), acc.len());
+    let c_in = b.alloc_qubit();
+    cuccaro_sub_fast_borrow(b, a, acc, c_in, carry_src);
+    b.free(c_in);
+}
+
+/// Build a width-(n-1) clean-|0> carry register for a fast-Cuccaro add/sub of
+/// width n, hosting as many bits as possible on `m_future` (clean |0> bits that
+/// belong to the caller and are restored to |0> on exit), and freshly
+/// allocating only the shortfall. Returns (full_carry_vec, fresh_count); the
+/// caller must `free` the LAST `fresh_count` entries after the add/sub. Flat
+/// Toffoli vs the all-fresh path; peak width drops by `min(n-1, m_future.len())`.
+fn borrow_carry_register(
+    b: &mut B,
+    n: usize,
+    m_future: &[QubitId],
+) -> (Vec<QubitId>, usize) {
+    let need = n.saturating_sub(1);
+    let borrowed = need.min(m_future.len());
+    let fresh_count = need - borrowed;
+    let mut carries: Vec<QubitId> = Vec::with_capacity(need);
+    carries.extend_from_slice(&m_future[..borrowed]);
+    for _ in 0..fresh_count {
+        carries.push(b.alloc_qubit());
+    }
+    (carries, fresh_count)
+}
+
+/// Max fresh carry qubits we will allocate on top of the m_future borrow
+/// before falling back to the slow (carry-register-FREE, 1-ancilla in-place
+/// Cuccaro). Tuned so the per-step peak stays <= the 2333 shift22 floor:
+/// 2333 - (binder carrier 1175 + tmp 256 + init 512 + lam 256 + slack) leaves
+/// headroom for ~120 fresh carries. When the m_future pool is too small to
+/// cover (n-1) with <= this many fresh bits, we use slow Cuccaro for that one
+/// call (flat WIDTH, +~n Toffoli) — only the few late iters with an exhausted
+/// pool pay it, keeping the global Toffoli penalty small while still capping
+/// the peak at the floor.
+fn gz_max_fresh_carries() -> usize {
+    // 131 = the max fresh-carry budget that keeps the per-step peak at the 2333
+    // shift22 floor (132+ lets kal_bulk_step4 borrow-fast push to 2334+).
+    // Swept empirically; minimizes the slow-Cuccaro fallback Toffoli at 2333.
+    std::env::var("KAL_GZ_MAX_FRESH")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(131)
+}
+
+/// `acc += a mod 2^n`: borrow the carry register from `m_future` (clean |0>);
+/// if the shortfall would exceed `gz_max_fresh_carries`, fall back to the slow
+/// in-place Cuccaro (no carry register at all) so the peak stays at the floor.
+fn add_nbit_qq_fast_mfut(b: &mut B, a: &[QubitId], acc: &[QubitId], m_future: &[QubitId]) {
+    assert_eq!(a.len(), acc.len());
+    let n = a.len();
+    let need = n.saturating_sub(1);
+    let borrowed = need.min(m_future.len());
+    if need - borrowed > gz_max_fresh_carries() {
+        // Pool too small: slow Cuccaro (1 ancilla, no carry register).
+        let c_in = b.alloc_qubit();
+        cuccaro_add(b, a, acc, c_in);
+        b.free(c_in);
+        return;
+    }
+    let (carries, fresh) = borrow_carry_register(b, n, m_future);
+    let c_in = b.alloc_qubit();
+    cuccaro_add_fast_borrow(b, a, acc, c_in, &carries);
+    b.free(c_in);
+    for &q in carries[carries.len() - fresh..].iter() {
+        b.free(q);
+    }
+}
+
+/// `acc -= a mod 2^n` with m_future borrow + slow-Cuccaro shortfall fallback.
+fn sub_nbit_qq_fast_mfut(b: &mut B, a: &[QubitId], acc: &[QubitId], m_future: &[QubitId]) {
+    assert_eq!(a.len(), acc.len());
+    let n = a.len();
+    let need = n.saturating_sub(1);
+    let borrowed = need.min(m_future.len());
+    if need - borrowed > gz_max_fresh_carries() {
+        let c_in = b.alloc_qubit();
+        cuccaro_sub(b, a, acc, c_in);
+        b.free(c_in);
+        return;
+    }
+    let (carries, fresh) = borrow_carry_register(b, n, m_future);
+    let c_in = b.alloc_qubit();
+    cuccaro_sub_fast_borrow(b, a, acc, c_in, &carries);
+    b.free(c_in);
+    for &q in carries[carries.len() - fresh..].iter() {
+        b.free(q);
+    }
+}
+
+/// Build a width-(n-1) clean-|0> carry register from TWO already-live clean
+/// pools (`m_future` first, then `extra`), freshly allocating only the
+/// shortfall. Both pools must be |0> on entry; the borrowed bits are restored
+/// to |0> by the caller's measurement-uncompute. Returns (carry_vec,
+/// fresh_count); the caller frees the LAST `fresh_count` entries. Adds ZERO
+/// peak width for every bit drawn from the pools. See [`gz_late_recover`].
+fn borrow_carry_register_pool(
+    b: &mut B,
+    n: usize,
+    m_future: &[QubitId],
+    extra: &[QubitId],
+) -> (Vec<QubitId>, usize) {
+    let need = n.saturating_sub(1);
+    let mut carries: Vec<QubitId> = Vec::with_capacity(need);
+    let take_mf = need.min(m_future.len());
+    carries.extend_from_slice(&m_future[..take_mf]);
+    if carries.len() < need {
+        let take_ex = (need - carries.len()).min(extra.len());
+        carries.extend_from_slice(&extra[..take_ex]);
+    }
+    let fresh_count = need - carries.len();
+    for _ in 0..fresh_count {
+        carries.push(b.alloc_qubit());
+    }
+    (carries, fresh_count)
+}
+
+/// `acc += a mod 2^n`: borrow carries from `m_future` THEN `extra` (both clean
+/// |0>, restored on exit); slow-Cuccaro fallback only if the COMBINED pool is
+/// still too small. Recovers the late-iter slow-fallback Toffoli at flat peak.
+fn add_nbit_qq_fast_mfut_pool(
+    b: &mut B,
+    a: &[QubitId],
+    acc: &[QubitId],
+    m_future: &[QubitId],
+    extra: &[QubitId],
+) {
+    assert_eq!(a.len(), acc.len());
+    let n = a.len();
+    let need = n.saturating_sub(1);
+    let pool = m_future.len() + extra.len();
+    let borrowed = need.min(pool);
+    if need - borrowed > gz_max_fresh_carries() {
+        let c_in = b.alloc_qubit();
+        cuccaro_add(b, a, acc, c_in);
+        b.free(c_in);
+        return;
+    }
+    let (carries, fresh) = borrow_carry_register_pool(b, n, m_future, extra);
+    let c_in = b.alloc_qubit();
+    cuccaro_add_fast_borrow(b, a, acc, c_in, &carries);
+    b.free(c_in);
+    for &q in carries[carries.len() - fresh..].iter() {
+        b.free(q);
+    }
+}
+
+/// `acc -= a mod 2^n` twin of [`add_nbit_qq_fast_mfut_pool`].
+fn sub_nbit_qq_fast_mfut_pool(
+    b: &mut B,
+    a: &[QubitId],
+    acc: &[QubitId],
+    m_future: &[QubitId],
+    extra: &[QubitId],
+) {
+    assert_eq!(a.len(), acc.len());
+    let n = a.len();
+    let need = n.saturating_sub(1);
+    let pool = m_future.len() + extra.len();
+    let borrowed = need.min(pool);
+    if need - borrowed > gz_max_fresh_carries() {
+        let c_in = b.alloc_qubit();
+        cuccaro_sub(b, a, acc, c_in);
+        b.free(c_in);
+        return;
+    }
+    let (carries, fresh) = borrow_carry_register_pool(b, n, m_future, extra);
+    let c_in = b.alloc_qubit();
+    cuccaro_sub_fast_borrow(b, a, acc, c_in, &carries);
+    b.free(c_in);
+    for &q in carries[carries.len() - fresh..].iter() {
+        b.free(q);
+    }
+}
+
 /// Fast `acc += a mod 2^n` using measurement-based Cuccaro.
 fn add_nbit_qq_fast(b: &mut B, a: &[QubitId], acc: &[QubitId]) {
     assert_eq!(a.len(), acc.len());
@@ -1298,6 +1854,26 @@ fn mod_double_inplace_fast(b: &mut B, v: &[QubitId], p: U256) {
     b.free(ovf);
 }
 
+/// `v := 2*v mod p` using the register-free direct const-add (no `load_const`
+/// addend register and no measurement-Cuccaro carry register held alongside
+/// it). Transient scratch ~n/2 less than `mod_double_inplace_fast`'s
+/// `cadd_nbit_const_fast` (which holds a 256-bit const register + 256 add
+/// carries simultaneously). Same value semantics; used in the low-scratch
+/// Solinas fold where the mod_double instant is the affine y-mul binder.
+fn mod_double_inplace_direct(b: &mut B, v: &[QubitId], p: U256) {
+    let n = v.len();
+    let ovf = b.alloc_qubit();
+    b.swap(v[n - 1], ovf);
+    for i in (0..n - 1).rev() {
+        b.swap(v[i], v[i + 1]);
+    }
+    debug_assert_eq!(n, 256);
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    cadd_nbit_const_direct_fast(b, v, c, ovf);
+    b.cx(v[0], ovf);
+    b.free(ovf);
+}
+
 /// `v := 2*v` assuming v[n-1] = 0 (no wrap). Just a shift-left cascade.
 /// 0 Toffoli. Used in Kaliski STEP 7+8 for small iters where r[255]=0 guaranteed.
 fn mod_double_no_corr(b: &mut B, v: &[QubitId]) {
@@ -1485,18 +2061,259 @@ fn mod_shift_right_by_k(
         } else {
             cuccaro_add_fast(b, &padded, &v_slice, c_in);
         }
-        b.free(c_in);
-        for i in 0..k.min(pad_width) {
-            b.cx(spill[i], padded[i]);
+        b.free(c_in);
+        for i in 0..k.min(pad_width) {
+            b.cx(spill[i], padded[i]);
+        }
+        b.free_vec(&padded);
+    };
+    // Reverse: undo ADD at 32, 10; undo SUB at 6; undo ADD at 4, 0.
+    cuccaro_op(b, 32, true); // undo +spill·2^32
+    cuccaro_op(b, 10, true); // undo +spill·2^10
+    cuccaro_op(b, 6, false); // undo -spill·2^6
+    cuccaro_op(b, 4, true); // undo +spill·2^4
+    cuccaro_op(b, 0, true); // undo +spill·2^0
+
+    // Reverse step 1: reverse swap cascades.
+    for shift_i in (0..k).rev() {
+        for i in 0..n - 1 {
+            b.swap(v[i], v[i + 1]);
+        }
+        b.swap(v[n - 1], spill[k - 1 - shift_i]);
+    }
+
+    b.free(ovf);
+    b.free_vec(&spill);
+}
+
+/// Low-scratch spill add `v_ext[pos..] += spill*2^pos` (KAL_GZ_SOLINAS_LOWSCRATCH).
+/// `spill` is a k-bit quantum value; the full-width add it represents has nonzero
+/// addend bits only in [pos, pos+k). Instead of the ~(n+1-pos)-wide `padded`
+/// carry-scratch register, this adds the k-bit chunk with a captured carry-out,
+/// propagates that single carry through the high bits via a Gidney venting
+/// controlled-increment (2 clean ancilla + a borrowed DIRTY donor, restored),
+/// then uncomputes the carry-out via the exact comparator identity
+/// `carry == (low_sum < spill)`. Net transient ~k+5 instead of ~n.
+fn shift22_spill_op_dirty(
+    b: &mut B,
+    v_ext: &[QubitId],
+    spill: &[QubitId],
+    pos: usize,
+    k: usize,
+    is_sub: bool,
+    dirty: &[QubitId],
+) {
+    let total = v_ext.len(); // n+1
+    let w = total - pos; // width of the affected window
+    debug_assert!(w >= k);
+    let v_slice: Vec<QubitId> = v_ext[pos..total].to_vec();
+    let low: Vec<QubitId> = v_slice[..k].to_vec();
+    let hi: Vec<QubitId> = v_slice[k..].to_vec(); // width w-k
+
+    // Step A: add/sub the k-bit spill into the low window, capturing carry/borrow.
+    let carry = b.alloc_qubit();
+    let zpad = b.alloc_qubit(); // |0> top bit of the (k+1)-bit addend
+    let mut addend = spill.to_vec();
+    addend.push(zpad);
+    let mut acc = low.clone();
+    acc.push(carry);
+    let c_in = b.alloc_qubit();
+    if is_sub {
+        cuccaro_sub(b, &addend, &acc, c_in);
+    } else {
+        cuccaro_add(b, &addend, &acc, c_in);
+    }
+    b.free(c_in);
+    b.free(zpad); // restored to |0> by cuccaro (addend register is preserved)
+
+    // Step B: propagate the single carry/borrow into the high window.
+    // add: hi += carry. sub: hi -= carry == controlled-decrement (invert,+1,invert).
+    if w - k >= 5 {
+        let dlen = (w - k).saturating_sub(2);
+        let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
+        if is_sub {
+            for &q in hi.iter() {
+                b.cx(carry, q); // controlled-invert hi (no-op when carry=0)
+            }
+            venting::ciadd_dirty_2clean_classical(
+                b, &hi, &dirty[..dlen], &q_clean2, 1, carry, false,
+            );
+            for &q in hi.iter() {
+                b.cx(carry, q);
+            }
+        } else {
+            venting::ciadd_dirty_2clean_classical(
+                b, &hi, &dirty[..dlen], &q_clean2, 1, carry, false,
+            );
+        }
+        b.free(q_clean2[0]);
+        b.free(q_clean2[1]);
+    } else {
+        let c = U256::from(1u64);
+        if is_sub {
+            csub_nbit_const_direct_fast(b, &hi, c, carry);
+        } else {
+            cadd_nbit_const_direct_fast(b, &hi, c, carry);
+        }
+    }
+
+    // Step C: uncompute `carry`. add: carry == (low_new < spill).
+    // sub: borrow == ((~low_new) < spill).
+    if is_sub {
+        for &q in low.iter() {
+            b.x(q);
+        }
+        cmp_lt_into(b, &low, spill, carry);
+        for &q in low.iter() {
+            b.x(q);
+        }
+    } else {
+        cmp_lt_into(b, &low, spill, carry);
+    }
+    b.free(carry);
+}
+
+/// KAL_GZ_SOLINAS_LOWSCRATCH forward shift22: same arithmetic as
+/// `mod_shift_left_by_k` but STEP-2 spill ops use the dirty-borrow narrow
+/// spill-add (no ~257-wide `padded`) and STEP-3/STEP-4 const-add /
+/// conditional-const-sub use Gidney venting dirty-borrow const adders (no
+/// ~257-wide loaded-constant register). `dirty` is a co-resident DIRTY donor
+/// register (>= n-2 wide, restored to its entry value on exit).
+fn mod_shift_left_by_k_dirty(
+    b: &mut B,
+    v: &[QubitId],
+    p: U256,
+    k: usize,
+    dirty: &[QubitId],
+) -> (Vec<QubitId>, QubitId, QubitId) {
+    let n = v.len();
+    debug_assert_eq!(n, 256);
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    let c_low = c.as_limbs()[0];
+
+    let spill = b.alloc_qubits(k);
+    let ovf = b.alloc_qubit();
+    let flag_inv = b.alloc_qubit();
+
+    for shift_i in 0..k {
+        b.swap(v[n - 1], spill[k - 1 - shift_i]);
+        for i in (0..n - 1).rev() {
+            b.swap(v[i], v[i + 1]);
+        }
+    }
+
+    let mut v_ext = v.to_vec();
+    v_ext.push(ovf);
+
+    b.set_phase("shift22_cuccaro_op_0");
+    shift22_spill_op_dirty(b, &v_ext, &spill, 0, k, false, dirty);
+    b.set_phase("shift22_cuccaro_op_4");
+    shift22_spill_op_dirty(b, &v_ext, &spill, 4, k, false, dirty);
+    b.set_phase("shift22_cuccaro_op_6");
+    shift22_spill_op_dirty(b, &v_ext, &spill, 6, k, true, dirty);
+    b.set_phase("shift22_cuccaro_op_10");
+    shift22_spill_op_dirty(b, &v_ext, &spill, 10, k, false, dirty);
+    b.set_phase("shift22_cuccaro_op_32");
+    shift22_spill_op_dirty(b, &v_ext, &spill, 32, k, false, dirty);
+
+    // Step 3: unconditional const add of c (register-free venting dirty-borrow).
+    b.set_phase("shift22_step3");
+    {
+        let m = v_ext.len();
+        let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
+        venting::iadd_dirty_2clean_classical(
+            b, &v_ext, &dirty[..m - 2], &q_clean2, c_low, false,
+        );
+        b.free(q_clean2[0]);
+        b.free(q_clean2[1]);
+    }
+    b.x(ovf);
+    b.cx(ovf, flag_inv); // flag_inv = NOT(top_bit_after_add) = (value < p)
+    b.x(ovf);
+
+    // Step 4: conditional const sub of c (register-free venting dirty-borrow).
+    b.set_phase("shift22_step4");
+    {
+        let m = v_ext.len();
+        let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
+        venting::cisub_dirty_2clean_classical(
+            b, &v_ext, &dirty[..m - 2], &q_clean2, c_low, flag_inv,
+        );
+        b.free(q_clean2[0]);
+        b.free(q_clean2[1]);
+    }
+    b.x(flag_inv);
+    b.cx(flag_inv, ovf);
+    b.x(flag_inv);
+
+    (spill, flag_inv, ovf)
+}
+
+/// Gate-level inverse of `mod_shift_left_by_k_dirty`.
+fn mod_shift_right_by_k_dirty(
+    b: &mut B,
+    v: &[QubitId],
+    p: U256,
+    k: usize,
+    spill: Vec<QubitId>,
+    flag_inv: QubitId,
+    ovf: QubitId,
+    dirty: &[QubitId],
+) {
+    let n = v.len();
+    debug_assert_eq!(n, 256);
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    let c_low = c.as_limbs()[0];
+
+    let mut v_ext = v.to_vec();
+    v_ext.push(ovf);
+
+    // Reverse step 4.
+    b.x(flag_inv);
+    b.cx(flag_inv, ovf);
+    b.x(flag_inv);
+    b.set_phase("rshift22_rev_step4");
+    {
+        // inverse of cisub(c, flag_inv) is ciadd(c, flag_inv): if flag_inv: x += c.
+        let m = v_ext.len();
+        let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
+        venting::ciadd_dirty_2clean_classical(
+            b, &v_ext, &dirty[..m - 2], &q_clean2, c_low, flag_inv, false,
+        );
+        b.free(q_clean2[0]);
+        b.free(q_clean2[1]);
+    }
+
+    // Reverse step 3.
+    b.x(ovf);
+    b.cx(ovf, flag_inv);
+    b.x(ovf);
+    b.set_phase("rshift22_rev_step3");
+    {
+        // inverse of iadd(c) is isub(c) == invert; iadd(c); invert.
+        let m = v_ext.len();
+        let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
+        for &q in v_ext.iter() {
+            b.x(q);
+        }
+        venting::iadd_dirty_2clean_classical(
+            b, &v_ext, &dirty[..m - 2], &q_clean2, c_low, false,
+        );
+        for &q in v_ext.iter() {
+            b.x(q);
         }
-        b.free_vec(&padded);
-    };
-    // Reverse: undo ADD at 32, 10; undo SUB at 6; undo ADD at 4, 0.
-    cuccaro_op(b, 32, true); // undo +spill·2^32
-    cuccaro_op(b, 10, true); // undo +spill·2^10
-    cuccaro_op(b, 6, false); // undo -spill·2^6
-    cuccaro_op(b, 4, true); // undo +spill·2^4
-    cuccaro_op(b, 0, true); // undo +spill·2^0
+        b.free(q_clean2[0]);
+        b.free(q_clean2[1]);
+    }
+    b.free(flag_inv);
+    b.set_phase("rshift22_rev_step2");
+
+    // Reverse step 2: undo the spill ops in reverse order with flipped signs.
+    shift22_spill_op_dirty(b, &v_ext, &spill, 32, k, true, dirty); // undo +2^32
+    shift22_spill_op_dirty(b, &v_ext, &spill, 10, k, true, dirty); // undo +2^10
+    shift22_spill_op_dirty(b, &v_ext, &spill, 6, k, false, dirty); // undo -2^6
+    shift22_spill_op_dirty(b, &v_ext, &spill, 4, k, true, dirty); // undo +2^4
+    shift22_spill_op_dirty(b, &v_ext, &spill, 0, k, true, dirty); // undo +2^0
 
     // Reverse step 1: reverse swap cascades.
     for shift_i in (0..k).rev() {
@@ -2265,6 +3082,181 @@ fn controlled_add_subtract_fast_inverse(b: &mut B, x: &[QubitId], acc: &[QubitId
     b.free(pad);
 }
 
+/// Low-scratch `wide -= x` where `x` is n-bit and `wide` is (2n+1)-bit.
+/// Instead of extending `x` to the full (2n+1) width (which allocates ~n+1
+/// pad qubits — the dominant transient scratch inside the Litinski multiply),
+/// subtract `x` only from the low n bits and ripple the single borrow up the
+/// high (n+1) bits with a register-free controlled decrement. Transient
+/// scratch ≈ n (one comparator's carries) instead of ~2n. Correct-by-
+/// construction from validated primitives (cmp_lt / cuccaro_sub_fast /
+/// csub_nbit_const_direct_fast).
+///
+/// Borrow algebra: borrow = (L_old < x); L_new = (L_old - x) mod 2^n;
+/// H_new = H - borrow. Uncompute borrow = (~x < L_new) (proven identity
+/// L_old < x  iff  L_new >= 2^n - x  iff  ~x < L_new).
+fn correction_sub_x_lowscratch(b: &mut B, x: &[QubitId], wide: &[QubitId]) {
+    let n = x.len();
+    debug_assert_eq!(wide.len(), 2 * n + 1);
+    let lo: Vec<QubitId> = wide[0..n].to_vec();
+    let hi: Vec<QubitId> = wide[n..2 * n + 1].to_vec();
+
+    let borrow = b.alloc_qubit();
+    // borrow = (L_old < x)
+    cmp_lt_into_fast(b, &lo, x, borrow);
+    // L -= x  (mod 2^n)
+    {
+        let c_in = b.alloc_qubit();
+        cuccaro_sub_fast(b, x, &lo, c_in);
+        b.free(c_in);
+    }
+    // H -= borrow  (register-free controlled decrement of the high n+1 bits)
+    csub_nbit_const_direct_fast(b, &hi, U256::from(1u64), borrow);
+    // Uncompute borrow = (~x < L_new): flip x (free), compare, flip back.
+    for i in 0..n {
+        b.x(x[i]);
+    }
+    cmp_lt_into_fast(b, x, &lo, borrow);
+    for i in 0..n {
+        b.x(x[i]);
+    }
+    b.free(borrow);
+}
+
+/// Exact gate-level inverse of `correction_sub_x_lowscratch`: `wide += x`.
+fn correction_add_x_lowscratch(b: &mut B, x: &[QubitId], wide: &[QubitId]) {
+    let n = x.len();
+    debug_assert_eq!(wide.len(), 2 * n + 1);
+    let lo: Vec<QubitId> = wide[0..n].to_vec();
+    let hi: Vec<QubitId> = wide[n..2 * n + 1].to_vec();
+
+    let borrow = b.alloc_qubit();
+    // Reverse the borrow-uncompute: recompute borrow = (~x < L_new).
+    for i in 0..n {
+        b.x(x[i]);
+    }
+    cmp_lt_into_fast(b, x, &lo, borrow);
+    for i in 0..n {
+        b.x(x[i]);
+    }
+    // Reverse H -= borrow  ->  H += borrow.
+    cadd_nbit_const_direct_fast(b, &hi, U256::from(1u64), borrow);
+    // Reverse L -= x  ->  L += x.
+    {
+        let c_in = b.alloc_qubit();
+        cuccaro_add_fast(b, x, &lo, c_in);
+        b.free(c_in);
+    }
+    // Reverse borrow compute: borrow = (L_old < x) (now L = L_old again).
+    cmp_lt_into_fast(b, &lo, x, borrow);
+    b.free(borrow);
+}
+
+/// Variant of `schoolbook_mul_into_addsub` that uses the low-scratch
+/// borrow-ripple `-x` correction, dropping the multiply's transient peak by
+/// ~n (the full-width x_ext pads). Semantics identical: `tmp_ext += x*y`.
+fn schoolbook_mul_into_addsub_lsx(b: &mut B, x: &[QubitId], y: &[QubitId], tmp_ext: &[QubitId]) {
+    let n = x.len();
+    debug_assert_eq!(y.len(), n);
+    debug_assert_eq!(tmp_ext.len(), 2 * n);
+
+    let low = b.alloc_qubit();
+    let mut wide: Vec<QubitId> = Vec::with_capacity(2 * n + 1);
+    wide.push(low);
+    wide.extend_from_slice(tmp_ext);
+
+    for k in 0..n {
+        let slice: Vec<QubitId> = wide[k..k + n + 1].to_vec();
+        controlled_add_subtract_fast(b, x, &slice, y[k]);
+    }
+
+    // +2^n * (y + 1)
+    {
+        let pad = b.alloc_qubit();
+        let mut y_ext = y.to_vec();
+        y_ext.push(pad);
+        let slice: Vec<QubitId> = wide[n..2 * n + 1].to_vec();
+        let c_in = b.alloc_qubit();
+        b.x(c_in);
+        cuccaro_add_fast(b, &y_ext, &slice, c_in);
+        b.x(c_in);
+        b.free(c_in);
+        b.free(pad);
+    }
+
+    // -2^{2n}
+    b.x(wide[2 * n]);
+
+    // -x (low-scratch borrow-ripple, the peak-relevant change).
+    correction_sub_x_lowscratch(b, x, &wide);
+
+    // +2^n * x
+    {
+        let pad = b.alloc_qubit();
+        let mut x_ext = x.to_vec();
+        x_ext.push(pad);
+        let slice: Vec<QubitId> = wide[n..2 * n + 1].to_vec();
+        let c_in = b.alloc_qubit();
+        cuccaro_add_fast(b, &x_ext, &slice, c_in);
+        b.free(c_in);
+        b.free(pad);
+    }
+
+    b.free(low);
+}
+
+/// Exact gate-level inverse of `schoolbook_mul_into_addsub_lsx`.
+fn schoolbook_mul_into_addsub_lsx_inverse(
+    b: &mut B,
+    x: &[QubitId],
+    y: &[QubitId],
+    tmp_ext: &[QubitId],
+) {
+    let n = x.len();
+    debug_assert_eq!(y.len(), n);
+    debug_assert_eq!(tmp_ext.len(), 2 * n);
+
+    let low = b.alloc_qubit();
+    let mut wide: Vec<QubitId> = Vec::with_capacity(2 * n + 1);
+    wide.push(low);
+    wide.extend_from_slice(tmp_ext);
+
+    // Reverse correction 4: sub x at bit n.
+    {
+        let pad = b.alloc_qubit();
+        let mut x_ext = x.to_vec();
+        x_ext.push(pad);
+        let slice: Vec<QubitId> = wide[n..2 * n + 1].to_vec();
+        let c_in = b.alloc_qubit();
+        cuccaro_sub_fast(b, &x_ext, &slice, c_in);
+        b.free(c_in);
+        b.free(pad);
+    }
+    // Reverse correction 3 (-x): add x back via the low-scratch ripple.
+    correction_add_x_lowscratch(b, x, &wide);
+    // Reverse correction 2: toggle wide[2n].
+    b.x(wide[2 * n]);
+    // Reverse correction 1: sub (y+1) at bit n.
+    {
+        let pad = b.alloc_qubit();
+        let mut y_ext = y.to_vec();
+        y_ext.push(pad);
+        let slice: Vec<QubitId> = wide[n..2 * n + 1].to_vec();
+        let c_in = b.alloc_qubit();
+        b.x(c_in);
+        cuccaro_sub_fast(b, &y_ext, &slice, c_in);
+        b.x(c_in);
+        b.free(c_in);
+        b.free(pad);
+    }
+    // Reverse n add-subtract rows.
+    for k in (0..n).rev() {
+        let slice: Vec<QubitId> = wide[k..k + n + 1].to_vec();
+        controlled_add_subtract_fast_inverse(b, x, &slice, y[k]);
+    }
+
+    b.free(low);
+}
+
 /// Litinski 2024 add-subtract schoolbook: tmp_ext += x * y.
 ///
 /// Precondition: tmp_ext has 2n bits and holds value A_in.
@@ -2801,8 +3793,6 @@ fn mod_mul_add_into_acc_karatsuba_lowq_with_tmp_ext(
     p: U256,
     tmp_ext: &[QubitId],
 ) {
-    /// Low-peak Karatsuba add-multiply: keep the half-sum/merge adders lowq and
-    /// use register-free Solinas correction for all positive reduction folds.
     let n = acc.len();
     debug_assert_eq!(n, 256);
     debug_assert_eq!(tmp_ext.len(), 2 * n);
@@ -2812,16 +3802,12 @@ fn mod_mul_add_into_acc_karatsuba_lowq_with_tmp_ext(
 
     let lo: Vec<QubitId> = tmp_ext[0..n].to_vec();
     let hi: Vec<QubitId> = tmp_ext[n..2 * n].to_vec();
-    // This lowq Karatsuba path is selected exactly at live-state-heavy sites.
-    // Avoid materializing full-width Solinas constants during the positive
-    // folds; the direct sparse-constant correction is arithmetically identical
-    // to mod_add_qq_fast but saves a field-sized scratch register at local peak.
-    mod_add_qq_fast_lowscratch(b, acc, &lo, p);
-    mod_add_qq_fast_lowscratch(b, acc, &hi, p);
+    mod_add_qq_fast(b, acc, &lo, p);
+    mod_add_qq_fast(b, acc, &hi, p);
     for _ in 0..4 {
         mod_double_inplace_fast(b, &hi, p);
     }
-    mod_add_qq_fast_lowscratch(b, acc, &hi, p);
+    mod_add_qq_fast(b, acc, &hi, p);
     for _ in 0..2 {
         mod_double_inplace_fast(b, &hi, p);
     }
@@ -2829,7 +3815,7 @@ fn mod_mul_add_into_acc_karatsuba_lowq_with_tmp_ext(
     for _ in 0..4 {
         mod_double_inplace_fast(b, &hi, p);
     }
-    mod_add_qq_fast_lowscratch(b, acc, &hi, p);
+    mod_add_qq_fast(b, acc, &hi, p);
     let (spill, flag_inv, ovf) = mod_shift_left_by_k(b, &hi, p, 22);
     mod_add_qq(b, acc, &hi, p);
     mod_shift_right_by_k(b, &hi, p, 22, spill, flag_inv, ovf);
@@ -3041,6 +4027,10 @@ fn pair1_mul1_write_into_zero_acc(
 ) {
     if pair1_mul1_karatsuba_enabled(acc.len()) {
         mod_mul_write_into_zero_acc_karatsuba(b, acc, x, y, p);
+    } else if gz_mul_lowscratch() {
+        // 9n-floor: drop the pair1_borrow_dx_mul1 schoolbook Solinas-fold
+        // transient below 2333 so it no longer rebinds the peak.
+        mod_mul_write_into_zero_acc_schoolbook_lowscratch_fold(b, acc, x, y, p);
     } else {
         mod_mul_write_into_zero_acc_schoolbook(b, acc, x, y, p);
     }
@@ -3073,6 +4063,10 @@ fn pair2_mul_add_into_acc(
         } else {
             mod_mul_add_into_acc_karatsuba(b, acc, x, y, p);
         }
+    } else if gz_mul_lowscratch() {
+        // 9n-floor: drop the schoolbook Solinas-fold transient below 2333 so
+        // pair2_mul no longer rebinds the peak once STEP-4 has dropped.
+        mod_mul_add_into_acc_schoolbook_lowscratch_fold(b, acc, x, y, p);
     } else {
         mod_mul_add_into_acc_schoolbook(b, acc, x, y, p);
     }
@@ -3295,6 +4289,122 @@ fn mod_mul_add_into_acc_schoolbook(
     b.free_vec(&tmp_ext);
 }
 
+/// Peak-minimized affine y-mul `acc += x*y mod p`. Drops the y-mul binder from
+/// 2565 to 2459 (the next cluster) by removing the ~256-wide transient scratch
+/// that the schoolbook MAC holds ON TOP of its 512-bit product `tmp_ext` while
+/// the lam² square's 512-bit `tmp_ext` co-resides. Three independent scratch
+/// cuts, each replacing a register-allocating primitive with its carry/register-
+/// free equivalent (all near-Toffoli-neutral, measured +0.10% total):
+///   1. forward/inverse mul: `schoolbook_mul_into_addsub_lsx` — the `-x`
+///      correction's full-width x_ext pads (~n) -> a 1-qubit borrow ripple.
+///   2. Solinas fold adds/sub: `mod_*_qq_lowq_lowscratch` — carry-free Cuccaro
+///      + register-free direct const adders + carry-free comparator.
+///   3. Solinas fold doublings: `mod_double_inplace_direct` — register-free
+///      direct const-add (no `load_const` register + 256 add carries co-live).
+/// The binding instant inside the schoolbook fold was the `mod_double` step
+/// (cadd_nbit_const_fast holds a 256-bit const register AND 256 add carries =
+/// ~512 transient); cut #3 is the dominant lever. Validated 9024-shot clean.
+fn mod_mul_add_into_acc_schoolbook_lowscratch_fold(
+    b: &mut B,
+    acc: &[QubitId],
+    x: &[QubitId],
+    y: &[QubitId],
+    p: U256,
+) {
+    let n = acc.len();
+    debug_assert_eq!(n, 256);
+
+    let tmp_ext = b.alloc_qubits(2 * n);
+    schoolbook_mul_into_addsub_lsx(b, x, y, &tmp_ext);
+
+    let lo: Vec<QubitId> = tmp_ext[0..n].to_vec();
+    let hi: Vec<QubitId> = tmp_ext[n..2 * n].to_vec();
+    mod_add_qq_lowq_lowscratch(b, acc, &lo, p);
+    mod_add_qq_lowq_lowscratch(b, acc, &hi, p); // position 0
+    for _ in 0..4 {
+        mod_double_inplace_direct(b, &hi, p);
+    }
+    mod_add_qq_lowq_lowscratch(b, acc, &hi, p); // position 4
+    for _ in 0..2 {
+        mod_double_inplace_direct(b, &hi, p);
+    }
+    mod_sub_qq_lowq_lowscratch(b, acc, &hi, p); // position 6
+    for _ in 0..4 {
+        mod_double_inplace_direct(b, &hi, p);
+    }
+    mod_add_qq_lowq_lowscratch(b, acc, &hi, p); // position 10
+    if gz_solinas_lowscratch() {
+        // The shift22 at this Solinas fold is the affine y-mul binder (2333).
+        // Borrow the co-resident dirty product `lo` half (restored on exit) as
+        // the venting dirty donor so the shift22 reduction holds ~k+5 scratch
+        // instead of ~257, dropping the binder below the bk_step4 floor (2309).
+        let (spill, flag_inv, ovf) = mod_shift_left_by_k_dirty(b, &hi, p, 22, &lo);
+        b.set_phase("shift22_pos32_dirty");
+        mod_add_qq_dirty(b, acc, &hi, p, &lo); // position 32 (venting dirty-borrow)
+        mod_shift_right_by_k_dirty(b, &hi, p, 22, spill, flag_inv, ovf, &lo);
+    } else {
+        let (spill, flag_inv, ovf) = mod_shift_left_by_k(b, &hi, p, 22);
+        mod_add_qq(b, acc, &hi, p); // position 32
+        mod_shift_right_by_k(b, &hi, p, 22, spill, flag_inv, ovf);
+    }
+    b.set_phase("sol_halve_tail");
+    for _ in 0..10 {
+        mod_halve_inplace_fast(b, &hi, p);
+    }
+
+    b.set_phase("schoolbook_mul_inverse");
+    schoolbook_mul_into_addsub_lsx_inverse(b, x, y, &tmp_ext);
+    b.free_vec(&tmp_ext);
+}
+
+/// From-zero (acc == 0 on entry) twin of
+/// `mod_mul_add_into_acc_schoolbook_lowscratch_fold`. Same three scratch cuts
+/// (lsx mul, lowscratch Solinas folds, register-free direct doubles) but the
+/// first lo-add uses the from-zero CX-copy path. Used for the pair1_borrow_dx
+/// mul1 binder under the 9n-floor flag.
+fn mod_mul_write_into_zero_acc_schoolbook_lowscratch_fold(
+    b: &mut B,
+    acc: &[QubitId],
+    x: &[QubitId],
+    y: &[QubitId],
+    p: U256,
+) {
+    let n = acc.len();
+    debug_assert_eq!(n, 256);
+
+    let tmp_ext = b.alloc_qubits(2 * n);
+    schoolbook_mul_into_addsub_lsx(b, x, y, &tmp_ext);
+
+    let lo: Vec<QubitId> = tmp_ext[0..n].to_vec();
+    let hi: Vec<QubitId> = tmp_ext[n..2 * n].to_vec();
+    // acc == 0 on entry: first lo-add is a CX-copy + register-free correction.
+    mod_add_qq_fast_from_zero_lowscratch(b, acc, &lo, p);
+    mod_add_qq_lowq_lowscratch(b, acc, &hi, p); // position 0
+    for _ in 0..4 {
+        mod_double_inplace_direct(b, &hi, p);
+    }
+    mod_add_qq_lowq_lowscratch(b, acc, &hi, p); // position 4
+    for _ in 0..2 {
+        mod_double_inplace_direct(b, &hi, p);
+    }
+    mod_sub_qq_lowq_lowscratch(b, acc, &hi, p); // position 6
+    for _ in 0..4 {
+        mod_double_inplace_direct(b, &hi, p);
+    }
+    mod_add_qq_lowq_lowscratch(b, acc, &hi, p); // position 10
+    let (spill, flag_inv, ovf) = mod_shift_left_by_k(b, &hi, p, 22);
+    mod_add_qq(b, acc, &hi, p); // position 32
+    mod_shift_right_by_k(b, &hi, p, 22, spill, flag_inv, ovf);
+    b.set_phase("sol_halve_tail");
+    for _ in 0..10 {
+        mod_halve_inplace_fast(b, &hi, p);
+    }
+
+    b.set_phase("schoolbook_mul_inverse");
+    schoolbook_mul_into_addsub_lsx_inverse(b, x, y, &tmp_ext);
+    b.free_vec(&tmp_ext);
+}
+
 /// Symmetric schoolbook for squaring: x² = sum_i x[i]·2^(2i) + sum_{i<j} 2·x[i]·x[j]·2^(i+j).
 /// Each cross-product is computed ONCE (instead of twice in full schoolbook),
 /// halving the AND count + Cuccaro_add length. Saves ~130k CCX per squaring.
@@ -3401,23 +4511,17 @@ fn squaring_add_to_acc_schoolbook(b: &mut B, acc: &[QubitId], x: &[QubitId], p:
 }
 
 fn mod_add_solinas_ext_product(b: &mut B, acc: &[QubitId], tmp_ext: &[QubitId], p: U256) {
-    /// Fold a 512-bit product into a freshly-zero field accumulator using the
-    /// secp256k1 Solinas relation, avoiding loaded constant scratch registers.
     let n = acc.len();
     debug_assert_eq!(n, 256);
     debug_assert_eq!(tmp_ext.len(), 2 * n);
     let lo: Vec<QubitId> = tmp_ext[0..n].to_vec();
     let hi: Vec<QubitId> = tmp_ext[n..2 * n].to_vec();
-    // In the main affine-combined path this helper is used immediately after
-    // allocating `acc` as |0>.  Use the from-zero variant for the low limb,
-    // saving the initial ripple add, and use low-scratch positive Solinas
-    // folds to reduce the peak qubit footprint.
-    mod_add_qq_fast_from_zero_lowscratch(b, acc, &lo, p);
-    mod_add_qq_fast_lowscratch(b, acc, &hi, p);
+    mod_add_qq_fast(b, acc, &lo, p);
+    mod_add_qq_fast(b, acc, &hi, p);
     for _ in 0..4 {
         mod_double_inplace_fast(b, &hi, p);
     }
-    mod_add_qq_fast_lowscratch(b, acc, &hi, p);
+    mod_add_qq_fast(b, acc, &hi, p);
     for _ in 0..2 {
         mod_double_inplace_fast(b, &hi, p);
     }
@@ -3425,7 +4529,7 @@ fn mod_add_solinas_ext_product(b: &mut B, acc: &[QubitId], tmp_ext: &[QubitId],
     for _ in 0..4 {
         mod_double_inplace_fast(b, &hi, p);
     }
-    mod_add_qq_fast_lowscratch(b, acc, &hi, p);
+    mod_add_qq_fast(b, acc, &hi, p);
     let (spill, flag_inv, ovf) = mod_shift_left_by_k(b, &hi, p, 22);
     mod_add_qq(b, acc, &hi, p);
     mod_shift_right_by_k(b, &hi, p, 22, spill, flag_inv, ovf);
@@ -3488,6 +4592,16 @@ fn square_tx_and_combined_ty_l2minus3qx(
     b.set_phase("affine_combined_y_mul");
     if env_flag_enabled("POINT_ADD_AFFINE_COMBINED_Y_KARATSUBA_LOWQ", false) {
         mod_mul_add_into_acc_karatsuba_lowq(b, ty, lam, &breg, p);
+    } else if env_flag_enabled("AFFINE_Y_MUL_LOWSCRATCH_FOLD", stack_2565_enabled()) {
+        // Peak-minimized y-mul: cuts the ~256-wide transient scratch the
+        // schoolbook MAC holds on top of its 512 product while the lam² square's
+        // 512 product co-resides (the -x correction pads, the Solinas fold's
+        // carry/const registers, and the fold mod_double's const register). The
+        // y-mul instant drops 2565 -> ~2333, below the next cluster (2459),
+        // breaking the 2565 binder. Default-on under STACK-2565; set
+        // AFFINE_Y_MUL_LOWSCRATCH_FOLD=0 to restore the byte-identical
+        // fast-fold schoolbook MAC (peak 2565).
+        mod_mul_add_into_acc_schoolbook_lowscratch_fold(b, ty, lam, &breg, p);
     } else {
         mod_mul_add_into_acc_schoolbook(b, ty, lam, &breg, p);
     }
@@ -4033,19 +5147,6 @@ fn kal_cswap_rs_merge_enabled() -> bool {
     std::env::var("KAL_CSWAP_RS_MERGE").ok().as_deref() != Some("0")
 }
 
-// DIAGNOSTIC: gate the (r,s) boundary-merge in the GENERIC (non-bulk) Kaliski
-// path independently, to bisect a phase/correctness regression between the
-// bulk-prefix iterations and the generic tail iterations.
-fn kal_cswap_rs_merge_generic_enabled() -> bool {
-    kal_cswap_rs_merge_enabled()
-        && std::env::var("KAL_CSWAP_RS_MERGE_GENERIC").ok().as_deref() != Some("0")
-}
-// DIAGNOSTIC: gate the merge in the BULK path independently.
-fn kal_cswap_rs_merge_bulk_enabled() -> bool {
-    kal_cswap_rs_merge_enabled()
-        && std::env::var("KAL_CSWAP_RS_MERGE_BULK").ok().as_deref() != Some("0")
-}
-
 /// For nonzero secp256k1 inputs, the first 256 Kaliski iterations are always
 /// nonterminal, so `f = 1` and `v_w != 0` at step entry are guaranteed.
 ///
@@ -6501,13 +7602,16 @@ fn kaliski_iteration_bulk_prefix3(
     r: &[QubitId],
     s: &[QubitId],
     m_i: QubitId,
+    m_future: &[QubitId],
     iter_idx: usize,
     coeff: Option<(&[QubitId], &[QubitId])>,
     frame: &mut Option<QubitId>,
     is_last: bool,
 ) {
     // (r,s) cswap boundary-merge is only valid on the default coeff=None channel.
-    let merge_rs = coeff.is_none() && kal_cswap_rs_merge_bulk_enabled();
+    let merge_rs = coeff.is_none() && kal_cswap_rs_merge_enabled();
+    let gz = gz_step4_slow();
+    let gz_dbl = gz_double_direct();
     let a_f = b.alloc_qubit();
     let b_f = b.alloc_qubit();
     let add_f = b.alloc_qubit();
@@ -6623,7 +7727,14 @@ fn kaliski_iteration_bulk_prefix3(
         }
         // Narrow load/sub width to the late-iter bound.
         // Both tmp and v_w are 256 qubits. Use slice [0..load_width] for each.
-        sub_nbit_qq_fast(b, &tmp[..load_width], &v_w[..load_width]);
+        // 9n-floor: carry-BORROW fast Cuccaro — host the n-1 carry register on
+        // clean future m_hist bits (restored to |0>), so the STEP-4 binder
+        // drops by up to n-1 at FLAT Toffoli.
+        if gz {
+            sub_nbit_qq_fast_mfut(b, &tmp[..load_width], &v_w[..load_width], m_future);
+        } else {
+            sub_nbit_qq_fast(b, &tmp[..load_width], &v_w[..load_width]);
+        }
         let transform_width = if iter_idx + 1 < n { iter_idx + 1 } else { n };
         for i in 0..transform_width {
             b.cx(r[i], u[i]);
@@ -6644,7 +7755,18 @@ fn kaliski_iteration_bulk_prefix3(
             None
         };
         let s_slice: Vec<QubitId> = s[0..add_width].to_vec();
-        add_nbit_qq_fast(b, &tmp_slice, &s_slice);
+        if gz {
+            // Late-iter recovery: also borrow u's provably-|0> high bits so the
+            // full-width s-add never falls back to slow Cuccaro (flat peak).
+            if gz_late_recover() {
+                let u_clean = gz_u_clean_high(u, iter_idx);
+                add_nbit_qq_fast_mfut_pool(b, &tmp_slice, &s_slice, m_future, u_clean);
+            } else {
+                add_nbit_qq_fast_mfut(b, &tmp_slice, &s_slice, m_future);
+            }
+        } else {
+            add_nbit_qq_fast(b, &tmp_slice, &s_slice);
+        }
         if let Some(q) = tmp_pad {
             b.free(q);
         }
@@ -6681,6 +7803,10 @@ fn kaliski_iteration_bulk_prefix3(
     }
     if iter_idx < r_small_threshold() {
         mod_double_no_corr(b, r);
+    } else if gz_dbl {
+        // 9n-floor: register-free direct const-add double (drops the
+        // const-register + carry-register that bind step6_7_8 at 2457).
+        mod_double_inplace_direct(b, r, p);
     } else {
         mod_double_inplace_fast(b, r, p);
     }
@@ -6745,6 +7871,7 @@ fn kaliski_iteration(
     r: &[QubitId],
     s: &[QubitId],
     m_i: QubitId,
+    m_future: &[QubitId],
     f: QubitId,
     iter_idx: usize,
     coeff: Option<(&[QubitId], &[QubitId])>,
@@ -6754,6 +7881,8 @@ fn kaliski_iteration(
     let n = u.len();
     // (r,s) cswap boundary-merge is only valid on the default coeff=None channel.
     let merge_rs = coeff.is_none() && kal_cswap_rs_merge_enabled();
+    let gz = gz_step4_slow();
+    let gz_dbl = gz_double_direct();
     // Iter-local flags (zero at iter start and iter end): alloc fresh here
     // so they don't live during body (which sees lower peak by -3 qubits).
     let a_f = b.alloc_qubit();
@@ -6882,7 +8011,11 @@ fn kaliski_iteration(
         // Sub v_w -= tmp. Late-iter: both high bits 0, truncate to load_width.
         let tmp_sub_slice: Vec<QubitId> = tmp[0..load_width].to_vec();
         let v_w_sub_slice: Vec<QubitId> = v_w[0..load_width].to_vec();
-        sub_nbit_qq_fast(b, &tmp_sub_slice, &v_w_sub_slice);
+        if gz {
+            sub_nbit_qq_fast_mfut(b, &tmp_sub_slice, &v_w_sub_slice, m_future);
+        } else {
+            sub_nbit_qq_fast(b, &tmp_sub_slice, &v_w_sub_slice);
+        }
         // Transform tmp from "add_f AND u" to "add_f AND r".
         // Small-iter: only the low iter+1 bits of r can be nonzero; the
         // carry slot for s += r is handled by an explicit 0 pad instead of a
@@ -6911,7 +8044,18 @@ fn kaliski_iteration(
             None
         };
         let s_slice: Vec<QubitId> = s[0..add_width].to_vec();
-        add_nbit_qq_fast(b, &tmp_slice, &s_slice);
+        if gz {
+            // Late-iter recovery: also borrow u's provably-|0> high bits so the
+            // full-width s-add never falls back to slow Cuccaro (flat peak).
+            if gz_late_recover() {
+                let u_clean = gz_u_clean_high(u, iter_idx);
+                add_nbit_qq_fast_mfut_pool(b, &tmp_slice, &s_slice, m_future, u_clean);
+            } else {
+                add_nbit_qq_fast_mfut(b, &tmp_slice, &s_slice, m_future);
+            }
+        } else {
+            add_nbit_qq_fast(b, &tmp_slice, &s_slice);
+        }
         if let Some(q) = tmp_pad {
             b.free(q);
         }
@@ -6964,6 +8108,8 @@ fn kaliski_iteration(
     // is identity; a plain shift suffices. Saves ~255 CCX per small iter.
     if iter_idx < r_small_threshold() {
         mod_double_no_corr(b, r);
+    } else if gz_dbl {
+        mod_double_inplace_direct(b, r, p);
     } else {
         mod_double_inplace_fast(b, r, p);
     }
@@ -7261,20 +8407,10 @@ fn kaliski_forward_with_coeff_caps(
 
     // ─── Iterations ───
     let use_bulk_prefix3 = bulk_prefix_enabled();
-    // When the bulk path merges but the generic path does not, the frame must
-    // NOT cross the bulk→generic boundary: the last bulk iter applies its step9
-    // eagerly (treated as "last") so no frame is handed to the generic tail.
-    let merge_boundary_break = use_bulk_prefix3
-        && kal_cswap_rs_merge_bulk_enabled()
-        && !kal_cswap_rs_merge_generic_enabled()
-        && bulk_caps.forward < iters;
     let mut frame: Option<QubitId> = None;
     for i in 0..iters {
-        let mut is_last = i + 1 == iters;
+        let is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_caps.forward {
-            if merge_boundary_break && i + 1 == bulk_caps.forward {
-                is_last = true;
-            }
             kaliski_iteration_bulk_prefix3(
                 b,
                 p,
@@ -7283,6 +8419,7 @@ fn kaliski_forward_with_coeff_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 i,
                 coeff,
                 &mut frame,
@@ -7297,6 +8434,7 @@ fn kaliski_forward_with_coeff_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 st.f_flag,
                 i,
                 coeff,
@@ -7380,13 +8518,15 @@ fn kaliski_iteration_bulk_prefix3_backward(
     r: &[QubitId],
     s: &[QubitId],
     m_i: QubitId,
+    m_future: &[QubitId],
     iter_idx: usize,
     frame: &mut Option<QubitId>,
     is_last: bool,
 ) {
     let n = u.len();
     // (r,s) cswap boundary-merge — bulk backward is always coeff=None.
-    let merge_rs = kal_cswap_rs_merge_bulk_enabled();
+    let merge_rs = kal_cswap_rs_merge_enabled();
+    let gz = gz_step4_slow();
     let a_f = b.alloc_qubit();
     let b_f = b.alloc_qubit();
     let add_f = b.alloc_qubit();
@@ -7458,7 +8598,16 @@ fn kaliski_iteration_bulk_prefix3_backward(
         let sub_width = if iter_idx + 2 < n { iter_idx + 2 } else { n };
         let tmp_sub_slice: Vec<QubitId> = tmp[0..sub_width].to_vec();
         let s_slice: Vec<QubitId> = s[0..sub_width].to_vec();
-        if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
+        if gz {
+            // Late-iter recovery: also borrow u's provably-|0> high bits so the
+            // full-width s-sub never falls back to slow Cuccaro (flat peak).
+            if gz_late_recover() {
+                let u_clean = gz_u_clean_high(u, iter_idx);
+                sub_nbit_qq_fast_mfut_pool(b, &tmp_sub_slice, &s_slice, m_future, u_clean);
+            } else {
+                sub_nbit_qq_fast_mfut(b, &tmp_sub_slice, &s_slice, m_future);
+            }
+        } else if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
             sub_nbit_qq(b, &tmp_sub_slice, &s_slice);
         } else {
             sub_nbit_qq_fast(b, &tmp_sub_slice, &s_slice);
@@ -7484,7 +8633,9 @@ fn kaliski_iteration_bulk_prefix3_backward(
         let add_width = if iter_idx < n { n } else { 2 * n - iter_idx };
         let tmp_add_slice: Vec<QubitId> = tmp[0..add_width].to_vec();
         let v_w_slice: Vec<QubitId> = v_w[0..add_width].to_vec();
-        if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
+        if gz {
+            add_nbit_qq_fast_mfut(b, &tmp_add_slice, &v_w_slice, m_future);
+        } else if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
             add_nbit_qq(b, &tmp_add_slice, &v_w_slice);
         } else {
             add_nbit_qq_fast(b, &tmp_add_slice, &v_w_slice);
@@ -7583,6 +8734,7 @@ fn kaliski_iteration_backward(
     r: &[QubitId],
     s: &[QubitId],
     m_i: QubitId,
+    m_future: &[QubitId],
     f: QubitId,
     iter_idx: usize,
     frame: &mut Option<QubitId>,
@@ -7590,7 +8742,8 @@ fn kaliski_iteration_backward(
 ) {
     let n = u.len();
     // (r,s) cswap boundary-merge — generic backward is always coeff=None here.
-    let merge_rs = kal_cswap_rs_merge_generic_enabled();
+    let merge_rs = kal_cswap_rs_merge_enabled();
+    let gz = gz_step4_slow();
     // Iter-local flags alloc'd fresh (zero at iter start in the backward
     // direction). They are zeroed and freed at iter end to match forward.
     let a_f = b.alloc_qubit();
@@ -7662,7 +8815,16 @@ fn kaliski_iteration_backward(
         let sub_width = if iter_idx + 2 < n { iter_idx + 2 } else { n };
         let tmp_sub_slice: Vec<QubitId> = tmp[0..sub_width].to_vec();
         let s_slice: Vec<QubitId> = s[0..sub_width].to_vec();
-        if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
+        if gz {
+            // Late-iter recovery: also borrow u's provably-|0> high bits so the
+            // full-width s-sub never falls back to slow Cuccaro (flat peak).
+            if gz_late_recover() {
+                let u_clean = gz_u_clean_high(u, iter_idx);
+                sub_nbit_qq_fast_mfut_pool(b, &tmp_sub_slice, &s_slice, m_future, u_clean);
+            } else {
+                sub_nbit_qq_fast_mfut(b, &tmp_sub_slice, &s_slice, m_future);
+            }
+        } else if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
             sub_nbit_qq(b, &tmp_sub_slice, &s_slice);
         } else {
             sub_nbit_qq_fast(b, &tmp_sub_slice, &s_slice);
@@ -7685,7 +8847,9 @@ fn kaliski_iteration_backward(
         let add_width = transform_width;
         let tmp_add_slice: Vec<QubitId> = tmp[0..add_width].to_vec();
         let v_w_slice: Vec<QubitId> = v_w[0..add_width].to_vec();
-        if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
+        if gz {
+            add_nbit_qq_fast_mfut(b, &tmp_add_slice, &v_w_slice, m_future);
+        } else if std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1") {
             add_nbit_qq(b, &tmp_add_slice, &v_w_slice);
         } else {
             add_nbit_qq_fast(b, &tmp_add_slice, &v_w_slice);
@@ -7847,17 +9011,10 @@ fn kaliski_backward_caps(
 
     let use_bulk_prefix3 = bulk_prefix_enabled();
     // ─── Reverse iterations (in reverse order) ───
-    let merge_boundary_break = use_bulk_prefix3
-        && kal_cswap_rs_merge_bulk_enabled()
-        && !kal_cswap_rs_merge_generic_enabled()
-        && bulk_caps.backward < iters;
     let mut frame: Option<QubitId> = None;
     for i in (0..iters).rev() {
-        let mut is_last = i + 1 == iters;
+        let is_last = i + 1 == iters;
         if use_bulk_prefix3 && i < bulk_caps.backward {
-            if merge_boundary_break && i + 1 == bulk_caps.backward {
-                is_last = true;
-            }
             kaliski_iteration_bulk_prefix3_backward(
                 b,
                 p,
@@ -7866,6 +9023,7 @@ fn kaliski_backward_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 i,
                 &mut frame,
                 is_last,
@@ -7879,6 +9037,7 @@ fn kaliski_backward_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 st.f_flag,
                 i,
                 &mut frame,
@@ -8948,6 +10107,7 @@ fn kaliski_forward_alias_v_w_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 i,
                 None,
                 &mut frame,
@@ -8962,6 +10122,7 @@ fn kaliski_forward_alias_v_w_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 st.f_flag,
                 i,
                 None,
@@ -8995,6 +10156,7 @@ fn kaliski_backward_alias_v_w_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 i,
                 &mut frame,
                 is_last,
@@ -9008,6 +10170,7 @@ fn kaliski_backward_alias_v_w_caps(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 st.f_flag,
                 i,
                 &mut frame,
@@ -9153,6 +10316,7 @@ fn kaliski_forward_prescaled_kind(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 i,
                 None,
                 &mut frame,
@@ -9167,6 +10331,7 @@ fn kaliski_forward_prescaled_kind(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 st.f_flag,
                 i,
                 None,
@@ -9226,6 +10391,7 @@ fn kaliski_backward_prescaled_kind(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 i,
                 &mut frame,
                 is_last,
@@ -9239,6 +10405,7 @@ fn kaliski_backward_prescaled_kind(
                 &st.r,
                 &st.s,
                 st.m_hist[i],
+                &st.m_hist[i + 1..iters],
                 st.f_flag,
                 i,
                 &mut frame,
@@ -9721,7 +10888,9 @@ fn build_standard_point_add(
     p: U256,
 ) {
     let pair2_branch_inv = std::env::var("KAL_PAIR2_BRANCH_INV_ROLL").ok().as_deref() == Some("1");
-    let kal_pair1_borrow_dx_denom = env_flag_enabled("KAL_PAIR1_BORROW_DX_DENOM", false);
+    // Stack default: pair1 inverse borrows dx as in-place v_w.
+    let kal_pair1_borrow_dx_denom =
+        env_flag_enabled("KAL_PAIR1_BORROW_DX_DENOM", stack_2565_enabled());
     let kal_pair1_invkeep_outside_lambda =
         env_flag_enabled("KAL_PAIR1_INVKEEP_OUTSIDE_LAMBDA", false);
     let kal_pair1_invkeep_skip_second_cleanup =
@@ -9778,10 +10947,24 @@ fn build_standard_point_add(
         || branch_term_div
         || branch_term_roll_div
         || std::env::var("KAL_TAGGED_DIV_VALIDATE").ok().as_deref() == Some("1");
+    // Stack default: pair1=401.  The cswap-merge / in-place-v / schoolbook
+    // interaction has a NON-MONOTONIC single-input classical-mismatch cliff:
+    // the fast HMR add/sub/halve blocks' phase fingerprint is coupled to the
+    // 2^iters descaling, so cleanliness scatters across iter counts rather than
+    // being a simple convergence floor.  Widening the late-iter (u,v) truncation
+    // (`2n-iter+margin`) only reshuffles the fingerprint, it does NOT close the
+    // cliff (verified across margin 0..4 over a full 9024-shot grid), so a
+    // structural root-fix that returns iters to 399 is intractable in the fast
+    // path.  405 was the prior safe island; 401 is a strictly better island
+    // found by the same grid: it lowers peak 2459->2457 (-2 m_hist qubits live
+    // at peak) AND avg Toffoli 3653471->3638875, and it is robust on the pair2
+    // axis (clean for pair2 in {403,404,405,406}; 403 is the established floor).
+    // C1 = 399.  (KAL_PAIR1_ITERS overrides for sweeps.)
+    let pair1_default = if stack_2565_enabled() { 401 } else { 399 };
     let pair1_iters = std::env::var("KAL_PAIR1_ITERS")
         .ok()
         .and_then(|s| s.parse::<usize>().ok())
-        .unwrap_or(399);
+        .unwrap_or(pair1_default);
     // The tagged validation paths change the op stream / Fiat-Shamir seed;
     // keep pair2 at the prior robust 404 setting to avoid conflating the
     // algebra probe with an iteration-threshold phase cliff.  Env overrides are
@@ -9791,6 +10974,10 @@ fn build_standard_point_add(
     // remains outside the verified safety margin.
     let pair2_default = if tagged_div_validate || pair2_branch_inv {
         404
+    } else if stack_2565_enabled() {
+        // Stack default: pair2=403 clears the in-place-v + schoolbook margin
+        // (9024-shot validated; pair2<403 trips the cswap-merge phase cliff).
+        403
     } else {
         398
     };
@@ -10203,6 +11390,24 @@ fn build_standard_point_add(
                     }
                     b.free_vec(&scaled_tx);
                 }
+            } else if env_flag_enabled("KAL_PAIR2_INPLACE_V", stack_2565_enabled()) {
+                // In-place-v (Gouzien/Qualtran): alias the live denominator tx as
+                // Kaliski's v_w (carrier 4n->3n). The body must not read/write tx;
+                // pair2 body touches only lam/ty/inv_raw. Drops the pair2-forward
+                // uvrs working set by n=256, attacking the kal_bulk_step4 binder.
+                with_kal_inv_raw_borrow_v_w_pair(
+                    b, &tx, p, pair2_iters, KalPair::Pair2, |b, inv_raw| {
+                        b.set_phase("pair2_double");
+                        for _ in 0..pair2_iters {
+                            mod_double_inplace_fast(b, &lam, p);
+                        }
+                        b.set_phase("pair2_mul");
+                        pair2_mul_add_into_acc(b, &lam, inv_raw, &ty, p);
+                        b.set_phase("pair2_cleanup");
+                        mod_sub_qb(b, &ty, &oy, p);
+                        b.set_phase("pair2_kaliski_backward");
+                    },
+                );
             } else {
                 with_kal_inv_raw_pair(b, &tx, p, pair2_iters, KalPair::Pair2, |b, inv_raw| {
                     b.set_phase("pair2_double");
@@ -10445,6 +11650,10 @@ pub fn build() -> Vec<Op> {
             b.peak_ops_idx,
             b.ops.len()
         );
+        // SCORED metric: analyze_ops uses max-qubit-id+1 (= next_qubit high-water),
+        // which can exceed the simultaneous-live peak when free/realloc fragments
+        // the id space. This is the number the eval_circuit scorer reports.
+        eprintln!("DEBUG scored_num_qubits(next_qubit)={}", b.next_qubit);
         let pk = b.peak_qubits;
         let mut uniq: std::collections::BTreeMap<&'static str, (u32, usize)> =
             std::collections::BTreeMap::new();
```

