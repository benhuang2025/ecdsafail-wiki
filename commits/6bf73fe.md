# 6bf73fe — Reduce the x-tail square mod p by folding its high half into its low half in place, instead of five modular add/subs on a doubled-and-halved high half

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-07 |
| Submission | `835298d` |
| Commit | `6bf73fe440b693d5f56ca3c42eb31d7d65d9da54` |
| Result | 1307 qubits × 1,470,765 Toffoli = **1,922,289,855** |
| Base | `8925623` (the author's previous submission, git parent and frontier at the time): 1307 qubits × 1,484,125 Toffoli = 1,939,751,375 |
| Change vs base | qubits ±0, Toffoli −13,360, score −17,461,520 |
| Leaderboard Δ | 0. The same tree was first submitted as `333950b` at 02:14 ("promotion failed", Δ −17,461,520), so by the time `835298d` was promoted the recorded frontier score already equalled it |
| Family | Strength Reduction → solinas / NAF fold |
| Concepts | [modular-fold](../concepts/modular-fold.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [adders-and-carries](../concepts/adders-and-carries.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The x-coordinate tail subtracts `λ²` from a 256-bit register `acc`. It squares
`λ` into a 512-bit integer `S = lo + hi·2^256` and then must reduce `S` mod
`p`. Since `p = 2^256 − c` with `c = 2^32 + 977`, `S ≡ lo + hi·c`. The old code
did this with modular arithmetic on `hi` itself: it subtracted `lo`, then
built `hi·c` term by term with 10 modular doublings, a 22-bit modular shift and
5 modular add/subs into `acc`, and then undid the doublings with 10 modular
halvings.

The new code does the reduction with plain integer adds, in place in the
square's own registers. It adds `hi·c` into `lo` as five shifted adds/subs,
keeps the part that overflows `2^256` in a small 34-bit "quotient" register,
multiplies that quotient by `c` once and adds it into `lo` as well. `lo` then
holds a 256-bit number congruent to `S`, and a single modular subtract
`acc −= lo` does the job. Everything is unfolded in reverse before the square
is uncomputed. This removes most of the modular doublings, halvings and
subtracts, for a net −13,360 Toffoli. The extra scratch (34 + 66 wires plus a
few wrap bits) lives only in the x-tail, which is not the qubit binder, so the
peak stays at 1307. One small carry chain is truncated, which adds a
~2^-22-per-call failure mode; the nonce was re-hunted.

## What changed and why it saves Toffoli

### `src/point_add/arith/multiply.rs`

**`squaring_sub_from_acc_schoolbook_lowq_shift22(b, acc, x, p)`** is the x-tail
square on this route (`rounds/dialog/mod.rs` calls it because
`ROUND84_XTAIL_KARATSUBA=0`). It computes the 512-bit square into `tmp_ext`
with the self-hosted schoolbook square, reduces, and then runs the square in
reverse. Only the reduction between the two squares changes.

Old reduction (still the `else` branch):
```
acc -= lo  (mod p)
acc -= hi                         ; ·1
4 × mod_double(hi);  acc -= hi    ; ·16
2 × mod_double(hi);  acc += hi    ; ·64 (subtracted with a minus sign)
4 × mod_double(hi);  acc -= hi    ; ·1024
mod_shift_left_by_k_lowq(hi, 22); acc -= hi  ; ·2^32
mod_shift_right_by_k_lowq(hi, 22); 10 × mod_halve(hi)   ; restore hi
```
That is `acc −= lo + hi·(1 + 16 − 64 + 1024 + 2^32) = lo + hi·c`, using six
256-bit modular add/subs, ten modular doublings, ten modular halvings and a
22-bit modular shift and unshift. Every one of those modular steps contains a
256-bit add plus a compare-and-correct against `p`.

New reduction, used when `ROUND84_INPLACE_SOLINAS_FOLD=1`:

1. **`round84_fold_hi_into_lo_aggregate(b, lo, hi, dirty)`**. It allocates a
   34-bit `quotient` register and writes `c` in signed form
   `c = 2^0 − 2^4 − 2^5 + 2^10 + 2^32` (terms `(0,+), (4,−), (5,−), (10,+), (32,+)`).
   For each term `(shift, add)`:
   - `lo[shift..] ± hi[..256−shift]` with plain Cuccaro `add_nbit_qq` /
     `sub_nbit_qq` (no modulus). The target is extended by one fresh `wrap`
     bit, which catches the carry (or borrow) out of bit 255.
   - `round84_update_fold_quotient` then records what fell off the top: it adds
     (or subtracts) the dropped top `shift` bits of `hi` (the "spill",
     `hi[256−shift..]`) into `quotient`, and adds (or subtracts) `wrap` with a
     controlled ±1 (`cadd/csub_nbit_const_direct_fast`).
   - Invariant after all five steps: `lo_new + quotient·2^256 = lo + hi·c`
     exactly. The `wrap` bits are kept in `Round84FoldStep` for the unfold.
2. **Apply `quotient·c` once.** Since `lo + hi·c < 2^256·(c + 1)`, the
   quotient is at most `c < 2^33`, so its low 33 bits suffice.
   - `round84_compute_quotient_c_product` builds `product = quotient·c` in a
     66-bit register: a CX copy for the `2^0` term plus `add_nbit_qq` of the
     quotient at shifts 4, 6, 7, 8, 9 and 32. These are the set bits of
     `c = 2^32 + 0b1111010001`.
   - `round84_add_narrow_correction` adds `product` into `lo[..66]` with the
     carry out caught in a new `correction_wrap` bit. It then propagates that
     carry into `lo[66..]` with `cadd_nbit_const_direct_trunc_fast(…, 1, wrap,
     W)`, a controlled +1 whose carry chain stops `W = ROUND84_INPLACE_QUOTIENT_CARRY_TRUNC_W = 21`
     bits up.
   - The product is uncomputed at once by `round84_uncompute_quotient_c_product`.
   - `lo` now holds `lo + hi·c − quotient·2^256 + quotient·c ≡ S (mod p)`.
3. **`mod_sub_qq_vent(b, acc, lo, p)`**: one 256-bit modular subtract, the
   existing low-peak "venting" variant.
4. **`round84_unfold_hi_from_lo_aggregate`** runs steps 2 and 1 backwards
   (recompute the product, subtract the correction, uncompute the product, then
   undo the five shifted adds and quotient updates in reverse order). That
   restores `lo` and `hi` to the square and frees `quotient` and the wraps.

The new path replaces 26 modular operations on 256-bit registers by ten
plain 256-bit adds (five forward and five back, at 2 Toffoli per bit
for in-place Cuccaro) and a few narrow 34- to 66-bit adds. The measured net
saving is 13,360 Toffoli.

Other edits in the file: three knob readers
(`round84_inplace_solinas_fold_enabled`,
`round84_inplace_quotient_carry_trunc_window` default 21, and
`round84_inplace_vent_carry_enabled`), the structs `Round84FoldStep` and
`Round84AggregateFold`, four `b.set_phase(...)` labels, and removal of the now
unused `c` constant. `ROUND84_INPLACE_VENT_CARRY` would replace the truncated
+1 with a venting add that borrows `acc` as dirty scratch. It is not set, so
the truncated path runs.

### `src/point_add/mod.rs`

In `configure_ecdsafail_submission_route()`:
- `ROUND84_INPLACE_SOLINAS_FOLD` = `1` (new)
- `ROUND84_INPLACE_QUOTIENT_CARRY_TRUNC_W` = `21` (new; same as the code default)
- `DIALOG_TAIL_NONCE`: 1401613145 → 4009893105

### `src/point_add/arith/modular.rs`

Only a trailing blank line is removed.

**Qubits.** The fold adds `quotient` (34), `product` (66), six wrap bits and
the truncated carry chain (22) while the 512-bit square is live. The x-tail is
not the phase that sets the 1307 peak, so the peak is unchanged (see
[peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md)).

## Why it is still correct, and what it risks

The five shifted adds, the quotient bookkeeping and the `quotient·c` product
are exact integer arithmetic. `2^256 ≡ c (mod p)` is exact, so the folded `lo`
is congruent to `S`. See [modular-fold](../concepts/modular-fold.md) for the
identity. The unfold is the exact gate-by-gate reverse, so `lo`, `hi`,
`quotient` and the wraps are restored on every input where the forward path
was exact.

Two places are approximate:
- **The truncated +1.** `cadd_nbit_const_direct_trunc_fast` with window 21
  drops the carry if it would run through 22 consecutive ones in
  `lo[66..]`. Its doc comment gives the rate as about `2^-(window+1)` per call
  for random data, here ~2^-22. Its carry wires still return to 0, so a
  failure is a wrong value of `lo`, hence a wrong `x3`: a classical mismatch.
- **A non-canonical folded `lo`.** The folded value lies in `[0, 2^256)` but
  can exceed `p`, which the modular subtract does not expect. That band has
  width `c ≈ 2^33`, so it is hit with probability around 2^-223. The comment in
  `mod.rs` mentions it together with the carry truncation.

Both are dodged by the Fiat–Shamir island. Nonce `4009893105` validated with
0 classical, 0 phase and 0 ancilla failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The commit replaces a chain of modular doublings and modular add/subs with a
cheaper pseudo-Mersenne (Solinas) fold over a signed form of `c`. That is
strength reduction of the fold, so solinas / NAF fold fits. The 21-bit carry
truncation is a supporting detail, not the lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 8925623 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 8925623 6bf73fe -- src/point_add` is
   330 lines in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 6bf73fe -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `ROUND84_*` or other route environment variables set, because
   `set_default_env` only fills in unset variables. Expect:
   - 1307 qubits
   - 1,470,765 average Toffoli (rounded)
   - score 1,922,289,855
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=4009893105` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/modular.rs b/src/point_add/arith/modular.rs
index 7e1ec8d..dc2b2fa 100644
--- a/src/point_add/arith/modular.rs
+++ b/src/point_add/arith/modular.rs
@@ -1099,4 +1099,3 @@ pub(crate) fn cmod_sub_qq_lowq(b: &mut B, acc: &[QubitId], a: &[QubitId], ctrl:
     }
     b.free_vec(&f);
 }
-
diff --git a/src/point_add/arith/multiply.rs b/src/point_add/arith/multiply.rs
index 2bf765e..2d7054b 100644
--- a/src/point_add/arith/multiply.rs
+++ b/src/point_add/arith/multiply.rs
@@ -740,6 +740,269 @@ pub(crate) fn xtail_sq_selfhost_enabled() -> bool {
     std::env::var("XTAIL_SQ_SELFHOST").ok().as_deref() != Some("0")
 }
 
+fn round84_inplace_solinas_fold_enabled() -> bool {
+    std::env::var("ROUND84_INPLACE_SOLINAS_FOLD")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
+fn round84_inplace_quotient_carry_trunc_window() -> usize {
+    std::env::var("ROUND84_INPLACE_QUOTIENT_CARRY_TRUNC_W")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(21)
+        .max(1)
+}
+
+fn round84_inplace_vent_carry_enabled() -> bool {
+    std::env::var("ROUND84_INPLACE_VENT_CARRY")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
+struct Round84FoldStep {
+    shift: usize,
+    add: bool,
+    wrap: QubitId,
+}
+
+struct Round84AggregateFold {
+    steps: Vec<Round84FoldStep>,
+    quotient: Vec<QubitId>,
+    correction_wrap: QubitId,
+}
+
+fn round84_update_fold_quotient(
+    b: &mut B,
+    quotient: &[QubitId],
+    hi: &[QubitId],
+    step: &Round84FoldStep,
+    inverse: bool,
+) {
+    let add = step.add != inverse;
+    let update_wrap = |b: &mut B| {
+        if add {
+            cadd_nbit_const_direct_fast(b, quotient, U256::from(1), step.wrap);
+        } else {
+            csub_nbit_const_direct_fast(b, quotient, U256::from(1), step.wrap);
+        }
+    };
+    let update_spill = |b: &mut B| {
+        if step.shift == 0 {
+            return;
+        }
+        let pad = b.alloc_qubits(quotient.len() - step.shift);
+        let mut spill = hi[hi.len() - step.shift..].to_vec();
+        spill.extend_from_slice(&pad);
+        if add {
+            add_nbit_qq(b, &spill, quotient);
+        } else {
+            sub_nbit_qq(b, &spill, quotient);
+        }
+        b.free_vec(&pad);
+    };
+
+    if inverse {
+        update_wrap(b);
+        update_spill(b);
+    } else {
+        update_spill(b);
+        update_wrap(b);
+    }
+}
+
+fn round84_compute_quotient_c_product(b: &mut B, quotient: &[QubitId]) -> Vec<QubitId> {
+    // quotient <= c, so its low 33 bits suffice and quotient*c fits in 66 bits.
+    let q = &quotient[..33];
+    let product = b.alloc_qubits(66);
+    for i in 0..q.len() {
+        b.cx(q[i], product[i]);
+    }
+    for shift in [4usize, 6, 7, 8, 9, 32] {
+        let target = &product[shift..];
+        let pad = b.alloc_qubits(target.len() - q.len());
+        let mut source = q.to_vec();
+        source.extend_from_slice(&pad);
+        add_nbit_qq(b, &source, target);
+        b.free_vec(&pad);
+    }
+    product
+}
+
+fn round84_uncompute_quotient_c_product(b: &mut B, quotient: &[QubitId], product: &[QubitId]) {
+    let q = &quotient[..33];
+    for shift in [4usize, 6, 7, 8, 9, 32].into_iter().rev() {
+        let target = &product[shift..];
+        let pad = b.alloc_qubits(target.len() - q.len());
+        let mut source = q.to_vec();
+        source.extend_from_slice(&pad);
+        sub_nbit_qq(b, &source, target);
+        b.free_vec(&pad);
+    }
+    for i in 0..q.len() {
+        b.cx(q[i], product[i]);
+    }
+    b.free_vec(product);
+}
+
+fn round84_add_narrow_correction(
+    b: &mut B,
+    lo: &[QubitId],
+    product: &[QubitId],
+    dirty: &[QubitId],
+) -> QubitId {
+    let wrap = b.alloc_qubit();
+    let source_top = b.alloc_qubit();
+    let mut target_ext = lo[..product.len()].to_vec();
+    target_ext.push(wrap);
+    let mut source_ext = product.to_vec();
+    source_ext.push(source_top);
+    add_nbit_qq(b, &source_ext, &target_ext);
+    b.free(source_top);
+    let high = &lo[product.len()..];
+    if round84_inplace_vent_carry_enabled() {
+        let clean2 = [b.alloc_qubit(), b.alloc_qubit()];
+        venting::ciadd_dirty_2clean_classical(
+            b,
+            high,
+            &dirty[..high.len() - 2],
+            &clean2,
+            1,
+            wrap,
+            false,
+        );
+        b.free(clean2[0]);
+        b.free(clean2[1]);
+    } else {
+        cadd_nbit_const_direct_trunc_fast(
+            b,
+            high,
+            U256::from(1),
+            wrap,
+            round84_inplace_quotient_carry_trunc_window(),
+        );
+    }
+    wrap
+}
+
+fn round84_sub_narrow_correction(
+    b: &mut B,
+    lo: &[QubitId],
+    product: &[QubitId],
+    wrap: QubitId,
+    dirty: &[QubitId],
+) {
+    let high = &lo[product.len()..];
+    if round84_inplace_vent_carry_enabled() {
+        let clean2 = [b.alloc_qubit(), b.alloc_qubit()];
+        venting::cisub_dirty_2clean_classical(b, high, &dirty[..high.len() - 2], &clean2, 1, wrap);
+        b.free(clean2[0]);
+        b.free(clean2[1]);
+    } else {
+        csub_nbit_const_direct_trunc_fast(
+            b,
+            high,
+            U256::from(1),
+            wrap,
+            round84_inplace_quotient_carry_trunc_window(),
+        );
+    }
+    let source_top = b.alloc_qubit();
+    let mut target_ext = lo[..product.len()].to_vec();
+    target_ext.push(wrap);
+    let mut source_ext = product.to_vec();
+    source_ext.push(source_top);
+    sub_nbit_qq(b, &source_ext, &target_ext);
+    b.free(source_top);
+    b.free(wrap);
+}
+
+/// Reversibly fold `hi*c` into `lo`, where `c = 2^256-p`.
+///
+/// Each signed shifted add/sub retains its 2^256 quotient contribution. The
+/// five contributions are accumulated into a 34-bit register, multiplied by
+/// sparse `c` once, and added to `lo`. The returned state is sufficient to
+/// restore the original square after `lo` has been consumed.
+fn round84_fold_hi_into_lo_aggregate(
+    b: &mut B,
+    lo: &[QubitId],
+    hi: &[QubitId],
+    dirty: &[QubitId],
+) -> Round84AggregateFold {
+    let n = lo.len();
+    let quotient = b.alloc_qubits(34);
+    // c = 2^32 + 977 = 2^32 + 2^10 - 2^5 - 2^4 + 1.
+    let terms = [
+        (0usize, true),
+        (4, false),
+        (5, false),
+        (10, true),
+        (32, true),
+    ];
+    let mut steps = Vec::with_capacity(terms.len());
+
+    for (shift, add) in terms {
+        let width = n - shift;
+        let wrap = b.alloc_qubit();
+        let source_top = b.alloc_qubit();
+        let mut target_ext = lo[shift..].to_vec();
+        target_ext.push(wrap);
+        let mut source_ext = hi[..width].to_vec();
+        source_ext.push(source_top);
+        if add {
+            add_nbit_qq(b, &source_ext, &target_ext);
+        } else {
+            sub_nbit_qq(b, &source_ext, &target_ext);
+        }
+        b.free(source_top);
+
+        let step = Round84FoldStep { shift, add, wrap };
+        round84_update_fold_quotient(b, &quotient, hi, &step, false);
+        steps.push(step);
+    }
+
+    let product = round84_compute_quotient_c_product(b, &quotient);
+    let correction_wrap = round84_add_narrow_correction(b, lo, &product, dirty);
+    round84_uncompute_quotient_c_product(b, &quotient, &product);
+    Round84AggregateFold {
+        steps,
+        quotient,
+        correction_wrap,
+    }
+}
+
+fn round84_unfold_hi_from_lo_aggregate(
+    b: &mut B,
+    lo: &[QubitId],
+    hi: &[QubitId],
+    dirty: &[QubitId],
+    state: Round84AggregateFold,
+) {
+    let product = round84_compute_quotient_c_product(b, &state.quotient);
+    round84_sub_narrow_correction(b, lo, &product, state.correction_wrap, dirty);
+    round84_uncompute_quotient_c_product(b, &state.quotient, &product);
+
+    for step in state.steps.into_iter().rev() {
+        round84_update_fold_quotient(b, &state.quotient, hi, &step, true);
+        let width = lo.len() - step.shift;
+        let source_top = b.alloc_qubit();
+        let mut target_ext = lo[step.shift..].to_vec();
+        target_ext.push(step.wrap);
+        let mut source_ext = hi[..width].to_vec();
+        source_ext.push(source_top);
+        if step.add {
+            sub_nbit_qq(b, &source_ext, &target_ext);
+        } else {
+            add_nbit_qq(b, &source_ext, &target_ext);
+        }
+        b.free(source_top);
+        b.free(step.wrap);
+    }
+    b.free_vec(&state.quotient);
+}
+
 /// Schoolbook squarer with Bennett uncompute. For squaring `tmp_ext = x*x`
 /// (2n bits, no mod reduction), then sub from acc with on-the-fly Solinas
 /// reduction, then uncompute tmp_ext via gate-level inverse. Saves ~170k
@@ -1127,9 +1390,9 @@ pub(crate) fn squaring_sub_from_acc_schoolbook_lowq_shift22(
     let n = acc.len();
     debug_assert_eq!(n, 256);
     debug_assert_eq!(x.len(), n);
-    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
 
     let tmp_ext = b.alloc_qubits(2 * n);
+    b.set_phase("round84_inplace_solinas_square_forward");
     if xtail_sq_selfhost_enabled() {
         schoolbook_square_symmetric_lowq_selfhosted(b, x, &tmp_ext);
     } else {
@@ -1138,32 +1401,41 @@ pub(crate) fn squaring_sub_from_acc_schoolbook_lowq_shift22(
 
     let lo: Vec<QubitId> = tmp_ext[0..n].to_vec();
     let hi: Vec<QubitId> = tmp_ext[n..2 * n].to_vec();
-    mod_sub_qq(b, acc, &lo, p);
-    let _ = c;
-    mod_sub_qq(b, acc, &hi, p);
-    for _ in 0..4 {
-        mod_double_inplace_direct_const_fast(b, &hi, p);
-    }
-    mod_sub_qq(b, acc, &hi, p);
-    for _ in 0..2 {
-        mod_double_inplace_direct_const_fast(b, &hi, p);
-    }
-    mod_add_qq(b, acc, &hi, p);
-    for _ in 0..4 {
-        mod_double_inplace_direct_const_fast(b, &hi, p);
-    }
-    mod_sub_qq(b, acc, &hi, p);
-    let (spill, flag_inv, ovf) = mod_shift_left_by_k_lowq(b, &hi, p, 22);
-    if r84_lowq_enabled() {
-        mod_sub_qq_lowq(b, acc, &hi, p);
+    if round84_inplace_solinas_fold_enabled() {
+        b.set_phase("round84_inplace_solinas_fold");
+        let state = round84_fold_hi_into_lo_aggregate(b, &lo, &hi, acc);
+        b.set_phase("round84_inplace_solinas_sub");
+        mod_sub_qq_vent(b, acc, &lo, p);
+        b.set_phase("round84_inplace_solinas_unfold");
+        round84_unfold_hi_from_lo_aggregate(b, &lo, &hi, acc, state);
     } else {
+        mod_sub_qq(b, acc, &lo, p);
         mod_sub_qq(b, acc, &hi, p);
-    }
-    mod_shift_right_by_k_lowq(b, &hi, p, 22, spill, flag_inv, ovf);
-    for _ in 0..10 {
-        mod_halve_inplace_direct_const_fast(b, &hi, p);
+        for _ in 0..4 {
+            mod_double_inplace_direct_const_fast(b, &hi, p);
+        }
+        mod_sub_qq(b, acc, &hi, p);
+        for _ in 0..2 {
+            mod_double_inplace_direct_const_fast(b, &hi, p);
+        }
+        mod_add_qq(b, acc, &hi, p);
+        for _ in 0..4 {
+            mod_double_inplace_direct_const_fast(b, &hi, p);
+        }
+        mod_sub_qq(b, acc, &hi, p);
+        let (spill, flag_inv, ovf) = mod_shift_left_by_k_lowq(b, &hi, p, 22);
+        if r84_lowq_enabled() {
+            mod_sub_qq_lowq(b, acc, &hi, p);
+        } else {
+            mod_sub_qq(b, acc, &hi, p);
+        }
+        mod_shift_right_by_k_lowq(b, &hi, p, 22, spill, flag_inv, ovf);
+        for _ in 0..10 {
+            mod_halve_inplace_direct_const_fast(b, &hi, p);
+        }
     }
 
+    b.set_phase("round84_inplace_solinas_square_inverse");
     if xtail_sq_selfhost_enabled() {
         schoolbook_square_symmetric_lowq_selfhosted_inverse(b, x, &tmp_ext);
     } else {
@@ -1199,4 +1471,3 @@ pub(crate) fn squaring_sub_from_acc_walk_controls_lowq(b: &mut B, acc: &[QubitId
     }
     b.free_vec(&ctrl_copy);
 }
-
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index e4aa775..92ae55c 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1250,6 +1250,14 @@ fn configure_ecdsafail_submission_route() {
     // compressed-block: current-step s2 composite-scratch fold (1308->1307).
     set_default_env("R84_LOWQ", "1");
     set_default_env("R84_LOWQ_CIN_BORROW", "1");
+    // Fold the square's high half into its low half in place, accumulate the
+    // resulting 33-bit quotient, apply quotient*(2^256-p) once, subtract once,
+    // then reversibly unfold before Bennett-uncomputing the square. The final
+    // modular subtract vents onto the folded operand, retaining the 1307q peak.
+    // The 21-bit high-carry propagation and rare folded-lo noncanonical band
+    // are selected away with the shared Fiat-Shamir island.
+    set_default_env("ROUND84_INPLACE_SOLINAS_FOLD", "1");
+    set_default_env("ROUND84_INPLACE_QUOTIENT_CARRY_TRUNC_W", "21");
     set_default_env("DIALOG_GCD_BORROW_CURRENT_S2", "1");
     set_default_env("DIALOG_GCD_APPLY_BOUNDARY_SPLIT", "100");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "50");
@@ -1340,7 +1348,7 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=262 route:
     // nonce 2432 validates 0/0/0 over all 9024 shots at
     // 1309q x 1,497,795 T = 1,960,613,655.
-    set_default_env("DIALOG_TAIL_NONCE", "1401613145");
+    set_default_env("DIALOG_TAIL_NONCE", "4009893105");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

