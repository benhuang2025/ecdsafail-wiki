# 3bbccd3 — Add the classical point coordinate with classically-controlled carries instead of loading it into qubits

| | |
| --- | --- |
| Contestant | mmurrs |
| Date | 2026-05-31 |
| Submission | `0c38fea` |
| Commit | `3bbccd3cb0813249eb0ad4ba8dab1a42fd718802` |
| Result | 2708 qubits × 3,541,837 Toffoli = **9,591,294,596** |
| Base | [`04b3a76`](04b3a76.md) (git parent, the author's previous submission): 2708 qubits × 3,541,843 Toffoli = 9,591,310,844 |
| Change vs base | qubits ±0, Toffoli −6, score −16,248 (leaderboard Δ −16,248) |
| Family | Constant Propagation and Classical Specialization → host-derived / classical specialization |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [modular-fold](../concepts/modular-fold.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The fixed input point `(x1, y1)` reaches the circuit as classical bit
registers (`ox`, `oy`), whose values are known per shot but are not qubits.
To add `x1` to a quantum register, `mod_add_qb` used to copy the 256 bits
into fresh qubits with classically-conditioned X gates, run the quantum-quantum
fast modular add, and erase the copy.

This commit adds `mod_add_qb_direct`, which never loads the bits. Its adder and
comparator use each classical bit as a classical condition on the gates that
need it. Toffoli is almost the same. The saving is only 6, because the
carry at bit 0 no longer needs a Toffoli. The 256-qubit copy disappears, but
that phase does not set the peak, so qubits are unchanged.

## What changed and why it saves Toffoli

All edits are in `src/point_add/mod.rs`.

**New builder primitives** on `B`: `z_if(q, cond)` and `cx_if(ctrl, tgt, cond)`,
which are gates conditioned on a classical bit, and
`push_condition` / `pop_condition`, wrapped as `with_bit_condition(b, cond, f)`.
These put every gate emitted inside `f` under an extra classical condition.

**New `add_nbit_qb_fast(bits, acc)`**: `acc += bits mod 2^n`, where `bits`
is a classical register.
- Forward carry sweep: `carry_{i+1} = majority(acc_i, k_i, carry_i) = acc_i·carry_i ⊕ k_i·(acc_i ⊕ carry_i)`.
  It is emitted as `ccx(acc_i, carry_i)` (none at `i = 0`, where there is no
  carry-in), plus `cx_if(acc_i → target, k_i)` and `cx_if(carry_i → target, k_i)`.
  So there is one Toffoli per position from 1 on, and the classical bit costs
  only conditioned CX gates.
- Sum: `x_if(acc_i, k_i)` and `cx(carry_i, acc_i)`.
- Carry erase: `hmr`, then the phase `(−1)^{majority(¬s_i, k_i, carry_i)}`
  applied as a `cz_if(¬acc_i, carry_i)` plus, under `with_bit_condition(k_i)`,
  two `z_if`s. See [measurement-uncompute](../concepts/measurement-uncompute.md).

**New `cmp_lt_bits_into_fast(u, bits, flag)`**: `flag ^= (u < bits)`, using
the carry-out of `¬u + bits` with the same classical-conditioned carry
sweep and measured erase. A helper, `phase_majority_qbitq`, emits the
phase fix.

**New `mod_add_qb_direct(acc, bits)`**, the same five steps as
`mod_add_qq_fast`:
1. `add_nbit_qb_fast(bits, acc_ext)`;
2. `+c` with `add_nbit_const_fast`;
3. `−c` under `NOT acc_ovf` with `csub_nbit_const_fast`;
4. fix up the overflow bit;
5. clear the flag with `cmp_lt_bits_into_fast(acc, bits)`.

**Routing.** `mod_add_qb` calls `mod_add_qb_direct` when
`offset_bits_add_enabled()` is on (`POINT_ADD_BITREG_OFFSETS`, default on, or
`POINT_ADD_BITREG_OFFSET_ADD`). `mod_sub_qb`, `mod_add_double_qb` and
`mod_sub_double_qb` still load the bits. The note says the subtract and
double variants "were not phase/correctness clean".

**Count.** The fast quantum-quantum Cuccaro adder pays one CCX at position 0,
`ccx(c_in, acc[0])`, and the bit-register adder pays none there. The
comparator gains the same way. `mod_add_qb` runs three times per point
addition: `breg += x1` and `tx += x1` in `square_tx_and_combined_ty_l2minus3qx`,
and the final `tx += x1` in `build_standard_point_add`. Two Toffoli per call
gives the measured −6.

**Unrelated, with no effect on the default circuit:**
- `sol_sub6_lowq_enabled()` (`POINT_ADD_SOL_SUB6_LOWQ`, default off) can switch
  the `sol_sub6` step of the pair-1 Karatsuba fold to the slow subtract.
- `KAL_VENT_HALVE` is now read through `env_flag_enabled`. It is still off by
  default.
- A `#[cfg(test)]` module exhaustively checks `add_nbit_qb_fast` and
  `cmp_lt_bits_into_fast` at 4 bits for value, phase and ancilla cleanliness.

## Why it is still correct, and what it risks

The change is exact on every input. Conditioning a gate on a classical bit
`k` is the same as applying it to a qubit holding `k`. So the new adder and
comparator compute the same carries and results as the loaded-register
versions, and the phase fixes are the same majority identity with `k` as a
classical factor. The tests check this exhaustively on 4-bit registers, and
the full benchmark checks it on the real ones. A wrong fix would show up as a
phase failure.

There is no tail nonce in this era. The 9,024 test inputs are a SHAKE256 hash
of the op stream, so the draw changed. The base's probabilistic settings,
including pair 2 at 397 iterations (see [`04b3a76`](04b3a76.md)), passed on
the new draw with 0 classical, 0 phase and 0 ancilla failures, per the note.

## Classification rationale

A value that is classical at run time is used as a classical control instead
of being loaded into qubits. That is classical specialization. It saves a
little Toffoli, and a 256-qubit register in a phase that is not the peak.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 04b3a76 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 04b3a76 3bbccd3 -- src/point_add` is
   290 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 3bbccd3 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `POINT_ADD_*`, `KAL_*`, `LOWQ_SHIFT22*`, `DUMMY_TOFFOLIS` or other
   environment overrides set. Expect:
   - 2708 qubits
   - 3,541,837 average Toffoli (3,541,837.000 before rounding, per the note)
   - score 9,591,294,596
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era. The 9,024 test inputs are a hash of the
op stream, so the score, and the clean draw, only reproduce with an identical
op stream.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index d6e9bf8..94d9a49 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -313,6 +313,21 @@ impl B {
         op.c_condition = cond;
         self.ops.push(op);
     }
+    fn z_if(&mut self, q: QubitId, cond: BitId) {
+        let mut op = Op::empty();
+        op.kind = OperationType::Z;
+        op.q_target = q;
+        op.c_condition = cond;
+        self.ops.push(op);
+    }
+    fn cx_if(&mut self, ctrl: QubitId, tgt: QubitId, cond: BitId) {
+        let mut op = Op::empty();
+        op.kind = OperationType::CX;
+        op.q_control1 = ctrl;
+        op.q_target = tgt;
+        op.c_condition = cond;
+        self.ops.push(op);
+    }
     // ── Measurement / phase / classical bit ops ──
     fn hmr(&mut self, q: QubitId, c: BitId) {
         let mut op = Op::empty();
@@ -321,6 +336,17 @@ impl B {
         op.c_target = c;
         self.ops.push(op);
     }
+    fn push_condition(&mut self, cond: BitId) {
+        let mut op = Op::empty();
+        op.kind = OperationType::PushCondition;
+        op.c_condition = cond;
+        self.ops.push(op);
+    }
+    fn pop_condition(&mut self) {
+        let mut op = Op::empty();
+        op.kind = OperationType::PopCondition;
+        self.ops.push(op);
+    }
     // ── Classically-conditioned variants for all remaining gates ──
     fn cz_if(&mut self, a: QubitId, b: QubitId, cond: BitId) {
         let mut op = Op::empty();
@@ -332,6 +358,12 @@ impl B {
     }
 }
 
+fn with_bit_condition<F: FnOnce(&mut B)>(b: &mut B, cond: BitId, f: F) {
+    b.push_condition(cond);
+    f(b);
+    b.pop_condition();
+}
+
 // ═══════════════════════════════════════════════════════════════════════════
 //  emit_inverse: run a closure, pop the ops it emitted, and re-emit them
 //  reversed.
@@ -450,6 +482,10 @@ fn pair2_mul_karatsuba_enabled(n: usize) -> bool {
         && env_flag_enabled("KAL_PAIR2_MUL_KARATSUBA", true)
 }
 
+fn sol_sub6_lowq_enabled() -> bool {
+    env_flag_enabled("POINT_ADD_SOL_SUB6_LOWQ", false)
+}
+
 // ═══════════════════════════════════════════════════════════════════════════
 //  Cuccaro ripple-carry adder
 // ═══════════════════════════════════════════════════════════════════════════
@@ -671,6 +707,151 @@ fn unload_bits(b: &mut B, qs: &[QubitId], bits: &[BitId]) {
     b.free_vec(qs);
 }
 
+fn offset_bits_enabled() -> bool {
+    env_flag_enabled("POINT_ADD_BITREG_OFFSETS", true)
+}
+
+fn offset_bits_add_enabled() -> bool {
+    offset_bits_enabled() || env_flag_enabled("POINT_ADD_BITREG_OFFSET_ADD", false)
+}
+
+fn bit_src(bits: &[BitId], i: usize) -> Option<BitId> {
+    bits.get(i).copied()
+}
+
+fn phase_majority_qbitq(
+    b: &mut B,
+    a: QubitId,
+    k: Option<BitId>,
+    carry: Option<QubitId>,
+    m: BitId,
+) {
+    if let Some(c) = carry {
+        b.cz_if(a, c, m);
+    }
+    if let Some(k) = k {
+        with_bit_condition(b, k, |b| {
+            b.z_if(a, m);
+            if let Some(c) = carry {
+                b.z_if(c, m);
+            }
+        });
+    }
+}
+
+/// `acc += bits mod 2^n`, where `bits` is a runtime classical bit register.
+/// Carry qubits are measured out with the same Gidney-style phase correction
+/// as the qubit/qubit fast adder, but the offset payload is never loaded into
+/// qubits.
+fn add_nbit_qb_fast(b: &mut B, bits: &[BitId], acc: &[QubitId]) {
+    let n = acc.len();
+    assert!(bits.len() <= n);
+    if n == 0 {
+        return;
+    }
+    if n == 1 {
+        if let Some(k) = bit_src(bits, 0) {
+            b.x_if(acc[0], k);
+        }
+        return;
+    }
+
+    let carries = b.alloc_qubits(n - 1);
+
+    // Forward carry sweep: carry_{i+1} = majority(acc_i, bit_i, carry_i).
+    for i in 0..n - 1 {
+        let target = carries[i];
+        let carry_in = if i == 0 { None } else { Some(carries[i - 1]) };
+        if let Some(c) = carry_in {
+            b.ccx(acc[i], c, target);
+        }
+        if let Some(k) = bit_src(bits, i) {
+            b.cx_if(acc[i], target, k);
+            if let Some(c) = carry_in {
+                b.cx_if(c, target, k);
+            }
+        }
+    }
+
+    // Sum bits.
+    for i in 0..n {
+        if let Some(k) = bit_src(bits, i) {
+            b.x_if(acc[i], k);
+        }
+        if i > 0 {
+            b.cx(carries[i - 1], acc[i]);
+        }
+    }
+
+    // Measurement-uncompute carries. For addition, after the sum write:
+    // carry_{i+1} = majority(!acc_i_final, bit_i, carry_i).
+    for i in (0..n - 1).rev() {
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        let carry_in = if i == 0 { None } else { Some(carries[i - 1]) };
+        if let Some(c) = carry_in {
+            b.x(acc[i]);
+            b.cz_if(acc[i], c, m);
+            b.x(acc[i]);
+        }
+        if let Some(k) = bit_src(bits, i) {
+            with_bit_condition(b, k, |b| {
+                b.x(acc[i]);
+                b.z_if(acc[i], m);
+                b.x(acc[i]);
+                if let Some(c) = carry_in {
+                    b.z_if(c, m);
+                }
+            });
+        }
+    }
+
+    b.free_vec(&carries);
+}
+
+/// flag ^= (u < bits), preserving `u` and without materializing `bits`.
+fn cmp_lt_bits_into_fast(b: &mut B, u: &[QubitId], bits: &[BitId], flag: QubitId) {
+    let n = u.len();
+    assert!(bits.len() <= n);
+    if n == 0 {
+        return;
+    }
+
+    let carries = b.alloc_qubits(n);
+    for i in 0..n {
+        b.x(u[i]);
+    }
+
+    // Carry-out of (~u + bits) is 1 iff u < bits.
+    for i in 0..n {
+        let target = carries[i];
+        let carry_in = if i == 0 { None } else { Some(carries[i - 1]) };
+        if let Some(c) = carry_in {
+            b.ccx(u[i], c, target);
+        }
+        if let Some(k) = bit_src(bits, i) {
+            b.cx_if(u[i], target, k);
+            if let Some(c) = carry_in {
+                b.cx_if(c, target, k);
+            }
+        }
+    }
+
+    b.cx(carries[n - 1], flag);
+
+    for i in (0..n).rev() {
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        let carry_in = if i == 0 { None } else { Some(carries[i - 1]) };
+        phase_majority_qbitq(b, u[i], bit_src(bits, i), carry_in, m);
+    }
+
+    for i in 0..n {
+        b.x(u[i]);
+    }
+    b.free_vec(&carries);
+}
+
 // ═══════════════════════════════════════════════════════════════════════════
 //  Extended registers and modular reduction
 // ═══════════════════════════════════════════════════════════════════════════
@@ -822,6 +1003,10 @@ fn mod_add_qc(b: &mut B, acc: &[QubitId], c: U256, p: U256) {
 
 fn mod_add_qb(b: &mut B, acc: &[QubitId], bits: &[BitId], p: U256) {
     // acc := (acc + bits) mod p. `bits` is a classical bit register.
+    if offset_bits_add_enabled() {
+        mod_add_qb_direct(b, acc, bits, p);
+        return;
+    }
     let a = load_bits(b, bits);
     mod_add_qq_fast(b, acc, &a, p);
     unload_bits(b, &a, bits);
@@ -853,6 +1038,30 @@ fn mod_sub_qb(b: &mut B, acc: &[QubitId], bits: &[BitId], p: U256) {
     unload_bits(b, &a, bits);
 }
 
+fn mod_add_qb_direct(b: &mut B, acc: &[QubitId], bits: &[BitId], p: U256) {
+    let n = acc.len();
+    assert_eq!(bits.len(), n);
+    debug_assert_eq!(n, 256);
+
+    let (acc_ext, acc_ovf) = ext_reg(b, acc);
+
+    add_nbit_qb_fast(b, bits, &acc_ext);
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    add_nbit_const_fast(b, &acc_ext, c);
+
+    let flag = b.alloc_qubit();
+    b.cx(acc_ovf, flag);
+    b.x(flag);
+    csub_nbit_const_fast(b, &acc_ext, c, flag);
+    b.x(flag);
+    b.cx(flag, acc_ovf);
+    cmp_lt_bits_into_fast(b, &acc_ext[..n], bits, flag);
+    b.free(flag);
+
+    unext_reg(b, acc_ovf);
+    let _ = acc_ext;
+}
+
 // ═══════════════════════════════════════════════════════════════════════════
 //  Non-modular n-bit primitives
 // ═══════════════════════════════════════════════════════════════════════════
@@ -1676,7 +1885,7 @@ fn mod_halve_inplace_fast_with_dirty(
     b.cx(v[0], ovf);
     // If caller provided enough dirty qubits AND c fits in u64 (it does
     // for secp256k1: c = 2^32 + 977), use the venting variant.
-    let use_venting = std::env::var("KAL_VENT_HALVE").ok().as_deref() == Some("1")
+    let use_venting = env_flag_enabled("KAL_VENT_HALVE", false)
         && dirty_src.map_or(false, |d| d.len() >= n - 2);
     if use_venting {
         // c as u64 (it fits: c = 0x1000003D1).
@@ -3010,7 +3219,11 @@ fn mod_mul_write_into_zero_acc_karatsuba_with_tmp_ext(
         mod_double_inplace_fast(b, &hi, p);
     }
     b.set_phase("sol_sub6");
-    mod_sub_qq_fast(b, acc, &hi, p);
+    if sol_sub6_lowq_enabled() {
+        mod_sub_qq(b, acc, &hi, p);
+    } else {
+        mod_sub_qq_fast(b, acc, &hi, p);
+    }
     for _ in 0..4 {
         mod_double_inplace_fast(b, &hi, p);
     }
@@ -10632,3 +10845,76 @@ pub fn build() -> Vec<Op> {
 
     b.ops.clone()
 }
+
+#[cfg(test)]
+mod bitreg_offset_tests {
+    use super::*;
+    use crate::sim::Simulator;
+    use sha3::digest::{ExtendableOutput, Update};
+
+    fn xof(tag: &[u8]) -> sha3::Shake256Reader {
+        let mut h = Shake256::default();
+        h.update(tag);
+        h.finalize_xof()
+    }
+
+    fn run_cases<F, G>(n: usize, build: F, expected: G)
+    where
+        F: Fn(&mut B, &[BitId], &[QubitId], QubitId),
+        G: Fn(u64, u64) -> (u64, bool),
+    {
+        let mut b = B::new();
+        let acc = b.alloc_qubits(n);
+        let bits = b.alloc_bits(n);
+        let flag = b.alloc_qubit();
+        build(&mut b, &bits, &acc, flag);
+
+        let mut x = xof(b"bitreg-offset-test");
+        let mut sim = Simulator::new(b.next_qubit as usize, b.next_bit as usize, &mut x);
+        for a in 0..(1u64 << n) {
+            for k in 0..(1u64 << n) {
+                sim.clear_for_shot();
+                for i in 0..n {
+                    if (a >> i) & 1 != 0 {
+                        *sim.qubit_mut(acc[i]) = 1;
+                    }
+                    if (k >> i) & 1 != 0 {
+                        *sim.bit_mut(bits[i]) = 1;
+                    }
+                }
+                sim.apply_iter(b.ops.iter());
+                let (want_acc, want_flag) = expected(a, k);
+                let mut got = 0u64;
+                for i in 0..n {
+                    got |= (sim.qubit(acc[i]) & 1) << i;
+                }
+                assert_eq!((got, sim.qubit(flag) != 0), (want_acc, want_flag), "a={a} k={k}");
+                assert_eq!(sim.phase & 1, 0, "phase a={a} k={k}");
+                for q in 0..b.next_qubit {
+                    let is_live = acc.iter().any(|v| v.0 == q) || flag.0 == q;
+                    if !is_live {
+                        assert_eq!(sim.qubit(QubitId(q)) & 1, 0, "garbage q{q} a={a} k={k}");
+                    }
+                }
+            }
+        }
+    }
+
+    #[test]
+    fn add_nbit_qb_fast_is_phase_clean() {
+        run_cases(
+            4,
+            |b, bits, acc, _flag| add_nbit_qb_fast(b, bits, acc),
+            |a, k| ((a + k) & 15, false),
+        );
+    }
+
+    #[test]
+    fn cmp_lt_bits_into_fast_is_phase_clean() {
+        run_cases(
+            4,
+            |b, bits, acc, flag| cmp_lt_bits_into_fast(b, acc, bits, flag),
+            |a, k| (a, a < k),
+        );
+    }
+}
```

