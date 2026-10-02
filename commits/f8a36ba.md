# f8a36ba — Truncate the carry ripple of the modular double/halve constant add to 24 bits above bit 32, and turn on the per-step GCD compare schedule

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-02 |
| Submission | `66ad478` |
| Commit | `f8a36ba24cd757be09ee655bc12ae757fdf7454f` |
| Result | 1698 qubits × 1,704,086 Toffoli = **2,893,538,028** |
| Base | `9b6b9d6` (Epistetechnician): 1698 qubits × 1,861,990 Toffoli = 3,161,659,020 |
| Change vs base | qubits ±0, Toffoli −157,904, score −268,120,992 |
| Leaderboard Δ | −227,470,872, measured against the frontier at the time, `acf2bdb` (1698 × 1,838,050), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md) (the unused Karatsuba path), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog-GCD apply loop doubles y modulo p at every forward step and halves
it at every reverse step. Each double or halve adds or subtracts the constant
`c = 2^256 − p = 2^32 + 977`, controlled on the bit that was shifted out.
Before this commit, the circuit did that with a full 256-bit adder: it loaded
`c` into a 256-qubit register and ran a 255-carry ripple. That cost 255
Toffoli per call.

This commit adds the constant directly, without a loaded register, and stops
the carry ripple 24 bits above the constant's top set bit, at carry 56. That
costs 69 Toffoli per call, a saving of 186. Over 820 calls this saves 152,520
Toffoli. A dropped carry only matters when the register has a run of 25 ones
just above bit 32, which happens with probability about 2^−25 per call.

The commit also turns on a baked per-step width table for the GCD swap
comparator, plus a margin of 8 bits. That saves another 5,384 Toffoli.
Qubits stay at 1698.

## What changed and why it saves Toffoli

All edits are in `src/point_add/mod.rs`. The route is described in
[`4b9cfbb`](4b9cfbb.md).

**1. Carry-truncated double and halve (−152,520 Toffoli).**

New helpers:

- **`highest_set_bit(c)`**. For c = 2^32 + 977 it returns 32.
- **`double_carry_trunc_window()`**. It reads `KAL_DOUBLE_CARRY_TRUNC_W`.
- **`cadd_nbit_const_direct_trunc_fast(acc, c, ctrl, window)`**. This is a
  copy of the existing register-free `cadd_nbit_const_direct_fast`, except
  that the carry wires stop at `last = min(n − 2, hi + window)`.
  - Carry `i` is `MAJ(acc_i, c_i·ctrl, carry_{i−1})`. That is 1 CCX where
    `c_i` = 0, 3 CCX where `c_i` = 1, and 1 CCX for `i` = 0.
  - Sum bits above `last + 1` get no carry, so they keep their input value.
  - The carries are erased by measurement (`hmr` + `cz_if`), using the same
    post-sum identity as the full adder.
- **`csub_nbit_const_direct_trunc_fast`**. This is the borrow twin, with the
  same window. The halve therefore stays the exact inverse of the double
  whenever the truncation does not trigger.

`mod_double_inplace_fast_with_dirty` and `mod_halve_inplace_fast_with_dirty`
now check `double_carry_trunc_window()` first. Before this commit, both fell
through to `cadd_nbit_const_fast` and `csub_nbit_const_fast`. Those load `c`
under control into a fresh 256-qubit register and run a 256-bit measured
Cuccaro add, which has 255 carries and costs 255 CCX.

`configure_ecdsafail_submission_route()` sets `KAL_DOUBLE_CARRY_TRUNC_W=24`,
so `last` = 32 + 24 = 56. The 7 set bits of `c` are bits 0, 4, 6, 7, 8, 9 and
32, so the cost is:

```
1 (i = 0) + 6 × 3 (set bits 4, 6, 7, 8, 9, 32) + 50 × 1 (other i in 1..=56) = 69 CCX
```

That saves 255 − 69 = 186 per call. There are 820 calls:

- 399 doubles in pair 2's forward apply;
- 399 halves in pair 1's reverse apply;
- 10 doubles and 10 halves in the x-tail square, `squaring_sub_from_acc_schoolbook`;
- 1 double and 1 halve in `mod_add_double_qb`.

Then 820 × 186 = 152,520. The new code also allocates 57 carry wires instead
of 256 + 255, but the peak is set elsewhere and stays at 1698.

**2. Per-step comparator schedule (−5,384 Toffoli).**

The tree already held a baked table,
`DIALOG_GCD_PA9024_COMPARE_SCHEDULE: [usize; 399]`. It gives one compare
width per walk step, from 12 bits at step 0 rising to about 60–73 bits
mid-walk. The base had the table switched off. The code does not document
where it came from. The name suggests it was measured on a 9,024-shot test
set.

This commit adds `DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN` (default 0) and
changes `dialog_gcd_compare_bits_for_step` to:

```
k(step) = max(1, min( min(COMPARE_BITS, w), min(max(table[step] + margin, floor), w) ))
w = active_width(step), floor = DIALOG_GCD_PA9024_COMPARE_SCHEDULE_FLOOR (default 1)
```

The route now sets `DIALOG_GCD_PA9024_COMPARE_SCHEDULE=1` (it was 0) and
`..._MARGIN=8`, with `DIALOG_GCD_COMPARE_BITS` still 63. Before this commit
every step used `min(63, w)`. Now 107 steps use fewer bits, mostly the first
100 steps, where step 0 drops from 63 to 20. The total over steps drops by
1,346 bits. Each bit is paid at the 4 fused comparator sites per step
([`9b6b9d6`](9b6b9d6.md)), so the saving is 4 × 1,346 = 5,384.

**3. Unused code.** The commit also adds:

- `squaring_sub_from_acc_karatsuba`, a one-level Karatsuba square that is
  symmetric in its three half-squares, about 200 lines;
- the `ROUND84_XTAIL_KARATSUBA` branch in `round84_emit_fused_square_xtail`.

Nothing sets `ROUND84_XTAIL_KARATSUBA`, so the shipped build still uses the
schoolbook square. The commit also moves an existing doc comment
("Fast `v := 2*v mod p` …") so that it now sits above `highest_set_bit`. That
is cosmetic.

The reroll stays at the base's `DIALOG_REROLL` = 5.

## Why it is still correct, and what it risks

- **Carry truncation is probabilistic.** The truncated adder gives a wrong
  result when a carry from bits 0–32 runs through 24 or more ones above bit
  32 and would have reached past bit 56. The source comment estimates
  ~2^−(window+1) per call for random `acc`. The doubled values are close to
  uniform field elements, so over 820 calls a shot fails with probability
  around 2.4·10^−5. A rough estimate is λ ≈ 0.2 per 9,024-shot draw.
- **Failures are classical.** The carries that are kept follow the exact
  recurrence and are erased exactly. Bit 0 is never affected, so the parity
  clear `cx(v[0], ovf)` stays exact. A trigger only corrupts the high bits of
  y, which shows up as a classical mismatch.
- **The schedule is probabilistic.** A narrower swap comparison misjudges
  `u > v` when u and v tie on their top `k(step)` bits. The walk then goes
  wrong, which is a classical failure.
- The shipped reroll 5 draws a clean set for the new stream: 0 classical,
  0 phase and 0 ancilla failures over 9,024 shots, per the submission note.

## Classification rationale

Most of the saving, 152,520 of 157,904, comes from cutting the carry tail of
the reduction-constant add inside the double and halve. That is fold/carry
truncation. The schedule part is a comparator-width truncation and is the
runner-up. The Karatsuba square is not active and plays no part.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 9b6b9d6 -- src/point_add`.
   - Do not start from the git parent `acf2bdb`. This commit was built on
     `9b6b9d6`.
   - Against the parent, the diff is 434 lines. It would also revert
     saucegodbased's measured apply-clean compares from [`acf2bdb`](acf2bdb.md).
     That is why this commit's Toffoli count does not include acf2bdb's −23,940.
   - Against `9b6b9d6`, `git diff --ignore-cr-at-eol 9b6b9d6 f8a36ba -- src/point_add`
     is 419 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol f8a36ba -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `ROUND84_*` or `KARA_*` environment variables set.
   Expect:
   - 1698 qubits
   - 1,704,086 average Toffoli (rounded)
   - score 2,893,538,028
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL` = 5 and an identical op stream.
Any other change needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 968fef8..90cb490 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2035,6 +2035,188 @@ fn mod_double_inplace(b: &mut B, v: &[QubitId], p: U256) {
 }
 
 /// Fast `v := 2*v mod p` using measurement-based Cuccaro.
+fn highest_set_bit(c: U256) -> usize {
+    let mut hi = 0usize;
+    for i in 0..256 {
+        if bit(c, i) {
+            hi = i;
+        }
+    }
+    hi
+}
+
+fn double_carry_trunc_window() -> Option<usize> {
+    std::env::var("KAL_DOUBLE_CARRY_TRUNC_W")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .filter(|&w| w > 0)
+}
+
+/// Carry-tail-truncated controlled add of a sparse classical constant.
+///
+/// Identical arithmetic to [`cadd_nbit_const_direct_fast`] except the forward
+/// carry ripple (and the matching measurement-uncompute) is stopped `window`
+/// bits above the constant's highest set bit `hi`. Carries `> hi + window`
+/// are assumed 0; the corresponding high sum bits keep their input value.
+/// This is exact unless a carry generated at/below `hi` propagates through an
+/// unbroken run of `window + 1` ones in `acc` above `hi` — probability
+/// ~2^-(window+1) per call for random `acc`. The carries `[0 ..= last]` follow
+/// the exact same recurrence and post-sum identity as the full adder, so they
+/// are returned cleanly to 0 (no phase / ancilla garbage); only the high sum
+/// value is approximate.
+fn cadd_nbit_const_direct_trunc_fast(
+    b: &mut B,
+    acc: &[QubitId],
+    c: U256,
+    ctrl: QubitId,
+    window: usize,
+) {
+    let n = acc.len();
+    if n == 0 {
+        return;
+    }
+    if n == 1 {
+        if bit(c, 0) {
+            b.cx(ctrl, acc[0]);
+        }
+        return;
+    }
+
+    let hi = highest_set_bit(c);
+    let last = core::cmp::min(n - 2, hi.saturating_add(window));
+    let carries = b.alloc_qubits(last + 1);
+
+    // Forward carry sweep, truncated at `last`. carry_{i+1} = maj(acc_i, k_i, carry_i).
+    for i in 0..=last {
+        let target = carries[i];
+        let carry_in = if i == 0 { None } else { Some(carries[i - 1]) };
+        if bit(c, i) {
+            if let Some(ci) = carry_in {
+                b.ccx(acc[i], ci, target);
+                b.ccx(ctrl, acc[i], target);
+                b.ccx(ctrl, ci, target);
+            } else {
+                b.ccx(acc[i], ctrl, target);
+            }
+        } else if let Some(ci) = carry_in {
+            b.ccx(acc[i], ci, target);
+        }
+    }
+
+    // Sum bits: acc_i ^= k_i ^ carry_{i-1}; carries above `last` are 0.
+    for i in 0..n {
+        if bit(c, i) {
+            b.cx(ctrl, acc[i]);
+        }
+        if i > 0 && i - 1 <= last {
+            b.cx(carries[i - 1], acc[i]);
+        }
+    }
+
+    // Measurement-uncompute carries in reverse (same identity as the full adder).
+    for i in (0..=last).rev() {
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        let carry_in = if i == 0 { None } else { Some(carries[i - 1]) };
+        if bit(c, i) {
+            b.x(acc[i]);
+            if let Some(ci) = carry_in {
+                b.cz_if(acc[i], ctrl, m);
+                b.cz_if(acc[i], ci, m);
+                b.x(acc[i]);
+                b.cz_if(ctrl, ci, m);
+            } else {
+                b.cz_if(acc[i], ctrl, m);
+                b.x(acc[i]);
+            }
+        } else if let Some(ci) = carry_in {
+            b.x(acc[i]);
+            b.cz_if(acc[i], ci, m);
+            b.x(acc[i]);
+        }
+    }
+
+    b.free_vec(&carries);
+}
+
+/// Carry-tail-truncated controlled subtract of a sparse classical constant.
+/// Borrow analogue of [`cadd_nbit_const_direct_trunc_fast`]; the inverse used
+/// by the apply-phase modular halve so that halve exactly inverts double when
+/// neither truncation triggers (the regime selected by the co-tuned reroll).
+fn csub_nbit_const_direct_trunc_fast(
+    b: &mut B,
+    acc: &[QubitId],
+    c: U256,
+    ctrl: QubitId,
+    window: usize,
+) {
+    let n = acc.len();
+    if n == 0 {
+        return;
+    }
+    if n == 1 {
+        if bit(c, 0) {
+            b.cx(ctrl, acc[0]);
+        }
+        return;
+    }
+
+    let hi = highest_set_bit(c);
+    let last = core::cmp::min(n - 2, hi.saturating_add(window));
+    let borrows = b.alloc_qubits(last + 1);
+
+    // Forward borrow sweep, truncated at `last`.
+    for i in 0..=last {
+        let target = borrows[i];
+        let borrow_in = if i == 0 { None } else { Some(borrows[i - 1]) };
+        if bit(c, i) {
+            b.x(acc[i]);
+            if let Some(bi) = borrow_in {
+                b.ccx(acc[i], bi, target);
+                b.ccx(ctrl, acc[i], target);
+                b.ccx(ctrl, bi, target);
+            } else {
+                b.ccx(acc[i], ctrl, target);
+            }
+            b.x(acc[i]);
+        } else if let Some(bi) = borrow_in {
+            b.x(acc[i]);
+            b.ccx(acc[i], bi, target);
+            b.x(acc[i]);
+        }
+    }
+
+    // Difference bits: acc_i ^= k_i ^ borrow_{i-1}; borrows above `last` are 0.
+    for i in 0..n {
+        if bit(c, i) {
+            b.cx(ctrl, acc[i]);
+        }
+        if i > 0 && i - 1 <= last {
+            b.cx(borrows[i - 1], acc[i]);
+        }
+    }
+
+    // Measurement-uncompute borrows in reverse (same identity as the full sub).
+    for i in (0..=last).rev() {
+        let m = b.alloc_bit();
+        b.hmr(borrows[i], m);
+        let borrow_in = if i == 0 { None } else { Some(borrows[i - 1]) };
+        if bit(c, i) {
+            if let Some(bi) = borrow_in {
+                b.cz_if(acc[i], ctrl, m);
+                b.cz_if(acc[i], bi, m);
+                b.cz_if(ctrl, bi, m);
+            } else {
+                b.cz_if(acc[i], ctrl, m);
+            }
+        } else if let Some(bi) = borrow_in {
+            b.cz_if(acc[i], bi, m);
+        }
+    }
+
+    b.free_vec(&borrows);
+}
+
 fn mod_double_inplace_fast(b: &mut B, v: &[QubitId], p: U256) {
     mod_double_inplace_fast_with_dirty(b, v, p, None)
 }
@@ -2058,7 +2240,10 @@ fn mod_double_inplace_fast_with_dirty(
     let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
     let use_venting = std::env::var("KAL_VENT_DOUBLE").ok().as_deref() == Some("1")
         && dirty_src.map_or(false, |d| d.len() >= n - 2);
-    if use_venting {
+    if let Some(w) = double_carry_trunc_window() {
+        // Carry-tail-truncated sparse-constant add (default OFF).
+        cadd_nbit_const_direct_trunc_fast(b, v, c, ovf, w);
+    } else if use_venting {
         let dirty = dirty_src.unwrap();
         let q_clean2: [QubitId; 2] = [b.alloc_qubit(), b.alloc_qubit()];
         venting::ciadd_dirty_2clean_classical(
@@ -2613,7 +2798,11 @@ fn mod_halve_inplace_fast_with_dirty(
     // If caller provided enough dirty qubits AND c fits in u64 (it does
     // for secp256k1: c = 2^32 + 977), use the venting variant.
     let use_venting = kal_vent_halve_enabled() && dirty_src.map_or(false, |d| d.len() >= n - 2);
-    if use_venting {
+    if let Some(w) = double_carry_trunc_window() {
+        // Carry-tail-truncated sparse-constant sub (inverse of the truncated
+        // double; default OFF; same window so double/halve stay exact inverses).
+        csub_nbit_const_direct_trunc_fast(b, v, c, ovf, w);
+    } else if use_venting {
         // c as u64 (it fits: c = 0x1000003D1).
         // For n=256, we still need to pass the full 256-bit constant via u64.
         // Since c only has 33 bits, u64 is fine.
@@ -5401,6 +5590,208 @@ fn squaring_sub_from_acc_schoolbook(b: &mut B, acc: &[QubitId], x: &[QubitId], p
     b.free_vec(&tmp_ext);
 }
 
+/// Squaring-aware 1-level Karatsuba variant of [`squaring_sub_from_acc_schoolbook`].
+///
+/// Computes `acc -= x^2 mod p` (Solinas-reduced) via a 1-level Karatsuba
+/// SQUARE. Split `x = hi‖lo` (`h = n/2` bits each) and form the three
+/// SYMMETRIC sub-squares
+///   z0 = lo^2,  z2 = hi^2,  z1 = (lo+hi)^2,
+/// then combine `z1 -= z0 + z2` (= 2·lo·hi) and add the middle term:
+///   x^2 = z0 + (z1 - z0 - z2)·2^h + z2·2^{2h}.
+/// Each sub-square is the existing symmetric square (`schoolbook_square_symmetric`,
+/// cross-products counted once via Gidney-uncomputed AND lanes), so the dominant
+/// cross-product AND budget drops ~25 % vs the symmetric 256-bit schoolbook
+/// square: 3·(n/2)(n/2-1)/2 cross ANDs instead of n(n-1)/2. Using a plain
+/// Karatsuba MUL with x=y would re-introduce the cross terms and be strictly
+/// worse — the symmetry of the SQUARE is what buys the win.
+///
+/// Peak control: the (lo+hi)^2 square is emitted FIRST, before the 2n-bit
+/// `tmp_ext` result register is allocated, and its `x_sum` operand is freed
+/// before `tmp_ext` is taken — so the z1 step (z1_reg + x_sum + row) and the
+/// z0/z2 step (tmp_ext + z1_reg + row) never coexist. The combine carries use
+/// the non-fast (ancilla-free) Cuccaro, and the Solinas lanes default to the
+/// low-peak set (non-fast add/sub, direct-const double/halve, lowq shift) so the
+/// extra z1_reg register (2(h+1) q) is absorbed without pushing the affine
+/// square phase over the global GCD-body peak binder (~1567 < 1698).
+fn squaring_sub_from_acc_karatsuba(b: &mut B, acc: &[QubitId], x: &[QubitId], p: U256) {
+    let n = acc.len();
+    debug_assert_eq!(n, 256);
+    debug_assert_eq!(x.len(), n);
+    let h = n / 2;
+    let x_lo: Vec<QubitId> = x[0..h].to_vec();
+    let x_hi: Vec<QubitId> = x[h..n].to_vec();
+
+    // z1_reg holds z1 = (lo+hi)^2, width 2*(h+1).
+    let z1_reg = b.alloc_qubits(2 * (h + 1));
+
+    // ── Forward z1 = (lo+hi)^2 FIRST (tmp_ext not yet allocated → low peak). ──
+    {
+        let x_sum = b.alloc_qubits(h + 1);
+        karatsuba_half_sum_compute(b, &x_lo, &x_hi, &x_sum);
+        schoolbook_square_symmetric(b, &x_sum, &z1_reg);
+        karatsuba_half_sum_uncompute(b, &x_lo, &x_hi, &x_sum);
+        b.free_vec(&x_sum);
+    }
+
+    // 2n-bit result accumulator for x^2 (allocated after the z1 square so its
+    // 2n qubits never coexist with the z1 operand/row registers).
+    let tmp_ext = b.alloc_qubits(2 * n);
+
+    // z0 = lo^2 → tmp_ext[0..2h], z2 = hi^2 → tmp_ext[2h..4h].
+    {
+        let slice: Vec<QubitId> = tmp_ext[0..2 * h].to_vec();
+        schoolbook_square_symmetric(b, &x_lo, &slice);
+    }
+    {
+        let slice: Vec<QubitId> = tmp_ext[2 * h..4 * h].to_vec();
+        schoolbook_square_symmetric(b, &x_hi, &slice);
+    }
+
+    // Combine: z1 -= z0; z1 -= z2; mid (tmp_ext[h..4h]) += z1. Non-fast Cuccaro
+    // (no carry ancilla) keeps the peak flat while tmp_ext + z1_reg are live.
+    {
+        let pad = b.alloc_qubits(2);
+        let mut z0_ext: Vec<QubitId> = tmp_ext[0..2 * h].to_vec();
+        z0_ext.extend_from_slice(&pad);
+        sub_nbit_qq(b, &z0_ext, &z1_reg);
+        b.free_vec(&pad);
+    }
+    {
+        let pad = b.alloc_qubits(2);
+        let mut z2_ext: Vec<QubitId> = tmp_ext[2 * h..4 * h].to_vec();
+        z2_ext.extend_from_slice(&pad);
+        sub_nbit_qq(b, &z2_ext, &z1_reg);
+        b.free_vec(&pad);
+    }
+    {
+        let pad = b.alloc_qubits(3 * h - 2 * (h + 1));
+        let mut z1_ext: Vec<QubitId> = z1_reg.to_vec();
+        z1_ext.extend_from_slice(&pad);
+        let acc_slice: Vec<QubitId> = tmp_ext[h..4 * h].to_vec();
+        add_nbit_qq(b, &z1_ext, &acc_slice);
+        b.free_vec(&pad);
+    }
+
+    // ── Solinas reduction: acc -= (lo + hi·c) mod p. ──
+    // z1_reg (2(h+1) q) is still live through this whole block, so the lanes
+    // that allocate a full-width carry ancilla (fast Cuccaro add/sub, fast
+    // shift) bind the affine-square phase peak. Each lane defaults to its
+    // low-peak (ancilla-free) variant so the phase peak stays below the global
+    // GCD-body binder; per-lane env knobs select the higher-peak fast variants
+    // for measurement (each computes the SAME value on `acc`, so any mix is
+    // value-correct):
+    //   KARA_SOL_MOD_FAST=1   → fast mod add/sub          (else non-fast)
+    //   KARA_SOL_DBL_FAST=1   → fast in-place double/halve (else direct-const)
+    //   KARA_SOL_SHIFT_FAST=1 → fast shift-by-22          (else lowq shift)
+    let mod_fast = std::env::var("KARA_SOL_MOD_FAST").ok().as_deref() == Some("1");
+    let dbl_fast = std::env::var("KARA_SOL_DBL_FAST").ok().as_deref() == Some("1");
+    let shift_fast = std::env::var("KARA_SOL_SHIFT_FAST").ok().as_deref() == Some("1");
+    let lo: Vec<QubitId> = tmp_ext[0..n].to_vec();
+    let hi: Vec<QubitId> = tmp_ext[n..2 * n].to_vec();
+    let mod_sub = |b: &mut B, acc: &[QubitId], a: &[QubitId]| {
+        if mod_fast {
+            mod_sub_qq_fast(b, acc, a, p);
+        } else {
+            mod_sub_qq(b, acc, a, p);
+        }
+    };
+    let mod_add = |b: &mut B, acc: &[QubitId], a: &[QubitId]| {
+        if mod_fast {
+            mod_add_qq_fast(b, acc, a, p);
+        } else {
+            mod_add_qq(b, acc, a, p);
+        }
+    };
+    let mod_dbl = |b: &mut B, v: &[QubitId]| {
+        if dbl_fast {
+            mod_double_inplace_fast(b, v, p);
+        } else {
+            mod_double_inplace_direct_const_fast(b, v, p);
+        }
+    };
+    let mod_hlv = |b: &mut B, v: &[QubitId]| {
+        if dbl_fast {
+            mod_halve_inplace_fast(b, v, p);
+        } else {
+            mod_halve_inplace_direct_const_fast(b, v, p);
+        }
+    };
+    mod_sub(b, acc, &lo);
+    mod_sub(b, acc, &hi);
+    for _ in 0..4 {
+        mod_dbl(b, &hi);
+    }
+    mod_sub(b, acc, &hi);
+    for _ in 0..2 {
+        mod_dbl(b, &hi);
+    }
+    mod_add(b, acc, &hi); // sign flipped
+    for _ in 0..4 {
+        mod_dbl(b, &hi);
+    }
+    mod_sub(b, acc, &hi);
+    let (spill, flag_inv, ovf) = if shift_fast {
+        mod_shift_left_by_k(b, &hi, p, 22)
+    } else {
+        mod_shift_left_by_k_lowq(b, &hi, p, 22)
+    };
+    mod_sub_qq(b, acc, &hi, p);
+    if shift_fast {
+        mod_shift_right_by_k(b, &hi, p, 22, spill, flag_inv, ovf);
+    } else {
+        mod_shift_right_by_k_lowq(b, &hi, p, 22, spill, flag_inv, ovf);
+    }
+    for _ in 0..10 {
+        mod_hlv(b, &hi);
+    }
+
+    // ── Inverse combine: mid -= z1; z1 += z2; z1 += z0. ──
+    {
+        let pad = b.alloc_qubits(3 * h - 2 * (h + 1));
+        let mut z1_ext: Vec<QubitId> = z1_reg.to_vec();
+        z1_ext.extend_from_slice(&pad);
+        let acc_slice: Vec<QubitId> = tmp_ext[h..4 * h].to_vec();
+        sub_nbit_qq(b, &z1_ext, &acc_slice);
+        b.free_vec(&pad);
+    }
+    {
+        let pad = b.alloc_qubits(2);
+        let mut z2_ext: Vec<QubitId> = tmp_ext[2 * h..4 * h].to_vec();
+        z2_ext.extend_from_slice(&pad);
+        add_nbit_qq(b, &z2_ext, &z1_reg);
+        b.free_vec(&pad);
+    }
+    {
+        let pad = b.alloc_qubits(2);
+        let mut z0_ext: Vec<QubitId> = tmp_ext[0..2 * h].to_vec();
+        z0_ext.extend_from_slice(&pad);
+        add_nbit_qq(b, &z0_ext, &z1_reg);
+        b.free_vec(&pad);
+    }
+
+    // Uncompute z2, z0 (reverse of forward compute order), then free tmp_ext.
+    {
+        let slice: Vec<QubitId> = tmp_ext[2 * h..4 * h].to_vec();
+        schoolbook_square_symmetric_inverse(b, &x_hi, &slice);
+    }
+    {
+        let slice: Vec<QubitId> = tmp_ext[0..2 * h].to_vec();
+        schoolbook_square_symmetric_inverse(b, &x_lo, &slice);
+    }
+    b.free_vec(&tmp_ext);
+
+    // Uncompute z1 last (mirrors the forward z1-first ordering, tmp_ext freed).
+    {
+        let x_sum = b.alloc_qubits(h + 1);
+        karatsuba_half_sum_compute(b, &x_lo, &x_hi, &x_sum);
+        schoolbook_square_symmetric_inverse(b, &x_sum, &z1_reg);
+        karatsuba_half_sum_uncompute(b, &x_lo, &x_hi, &x_sum);
+        b.free_vec(&x_sum);
+    }
+
+    b.free_vec(&z1_reg);
+}
+
 fn squaring_sub_from_acc_schoolbook_lowq_shift22(
     b: &mut B,
     acc: &[QubitId],
@@ -17806,7 +18197,11 @@ fn round84_emit_fused_square_xtail(
     p: U256,
 ) {
     b.set_phase("round84_fused_square_xtail_dx_sub_lam_square_lowq");
-    if std::env::var("ROUND84_XTAIL_WALK_SQUARE").ok().as_deref() == Some("1") {
+    if std::env::var("ROUND84_XTAIL_KARATSUBA").ok().as_deref() == Some("1") {
+        // Squaring-aware 1-level Karatsuba square (default OFF). Overrides the
+        // ROUND84_XTAIL_SCHOOLBOOK default set in configure_ecdsafail_submission_route.
+        squaring_sub_from_acc_karatsuba(b, tx, lam, p);
+    } else if std::env::var("ROUND84_XTAIL_WALK_SQUARE").ok().as_deref() == Some("1") {
         squaring_sub_from_acc_walk_controls_lowq(b, tx, lam, p);
     } else if std::env::var("ROUND84_XTAIL_SCHOOLBOOK").ok().as_deref() == Some("1") {
         squaring_sub_from_acc_schoolbook(b, tx, lam, p);
@@ -22508,15 +22903,23 @@ fn dialog_gcd_pa9024_compare_schedule_floor() -> usize {
         .max(1)
 }
 
+fn dialog_gcd_pa9024_compare_schedule_margin() -> usize {
+    std::env::var("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(0)
+}
+
 fn dialog_gcd_compare_bits_for_step(step: usize, active_width: usize) -> usize {
     let global = dialog_gcd_compare_bits().min(active_width);
     if dialog_gcd_pa9024_compare_schedule_enabled() {
-        let scheduled = DIALOG_GCD_PA9024_COMPARE_SCHEDULE
+        let scheduled = (DIALOG_GCD_PA9024_COMPARE_SCHEDULE
             .get(step)
             .copied()
             .unwrap_or(global)
-            .max(dialog_gcd_pa9024_compare_schedule_floor())
-            .min(active_width);
+            + dialog_gcd_pa9024_compare_schedule_margin())
+        .max(dialog_gcd_pa9024_compare_schedule_floor())
+        .min(active_width);
         return scheduled.min(global).max(1);
     }
     global.max(1)
@@ -27999,7 +28402,9 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("SKIP_ALT_SEED_CHECKS", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_SIDECAR_LOG", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
-    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE", "0");
+    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE", "1");
+    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "8");
+    set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "24");
     set_default_env("DIALOG_GCD_COMPARE_BITS", "63");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
```

