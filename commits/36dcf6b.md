# 36dcf6b — Drop the known-zero top bit of the apply adder's addend (1572 → 1571 qubits)

| | |
| --- | --- |
| Contestant | pldallairedemers |
| Date | 2026-06-02 |
| Submission | `005e17a` |
| Commit | `36dcf6beb305b51365841008302e6a5f5c47460c` |
| Result | 1571 qubits × 1,746,797 Toffoli = **2,744,218,087** |
| Base | `075c0c6` (ptrdsh, git parent and frontier at the time): 1572 qubits × 1,746,797 Toffoli = 2,745,964,884 |
| Change vs base | qubits −1, Toffoli ±0, score −1,746,797 (leaderboard Δ −1,746,797) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The 1572-qubit peak sits in the GCD apply pass, inside the controlled modular
add and subtract (`dialog_gcd_cmod_{add,sub}_materialized_pseudomersenne`). Each
one adds a 256-bit materialized addend `f` into a 257-bit accumulator
`acc_ext`. To make the operand widths match, the base allocated one extra wire,
`f_ovf`, that is always |0⟩, and used it as bit 256 of `f`. This commit removes
that wire. It adds two adder variants that take an `n`-bit addend and an
`(n+1)`-bit accumulator directly, and uses them for the last block of the
windowed adder from [68e3653](68e3653.md). The addition and its Toffoli count
are unchanged, and the peak drops by one qubit.

## What changed and why it saves a qubit

All in `src/point_add/mod.rs`:

- **New `cuccaro_add_fast_low_to_ext(a, acc_ext, c_in)`** computes
  `acc_ext += a + c_in (mod 2^(n+1))` with `|acc_ext| = |a| + 1`.
  - It is the measured-carry Cuccaro adder (`cuccaro_add_fast`) with `n` carry
    wires for the `n` addend bits, and one CCX per bit.
  - The top sum bit comes from a single `cx(a[n-1], acc_ext[n])`. After the MAJ
    sweep `a[n-1]` holds the carry into bit `n`, and the addend's bit `n` is 0.
  - The carries are erased by `hmr` + `cz_if`, as before.
- **New `cuccaro_sub_fast_low_to_ext`** is the matching subtractor.
- **New `cuccaro_add_fast_windowed_low_to_ext` /
  `cuccaro_sub_fast_windowed_low_to_ext`** are the windowed adders of
  68e3653, with block boundaries over the 257-bit `acc_ext`.
  - Block 0 (bits 0..128) still uses `cuccaro_add_fast` with a fresh zero and a
    `cout` extension.
  - The last block passes `a[128..256]` (128 bits) and `acc_ext[128..257]`
    (129 bits) to the `_low_to_ext` helper. That replaces a 129-bit operand
    whose top bit was the zero wire `f_ovf`.
  - The boundary carry is cleared exactly as before, with
    `cmp_lt_into_fast(acc_ext[..128], a[..128])`.
- **`dialog_gcd_cmod_add_materialized_pseudomersenne` and
  `dialog_gcd_cmod_sub_materialized_pseudomersenne`**: when
  `DIALOG_GCD_APPLY_WINDOW_BLOCKS` is set (it is, to 2), they pass `f` instead
  of `f_ext`, and no longer allocate `f_ovf`. The non-windowed branches still
  build `f_ext`, now allocating `f_ovf` locally.
- **Toffoli.** A 129-bit `cuccaro_add_fast` has 128 CCX, and the
  128-into-129 `_low_to_ext` has 128 CCX. The total is unchanged at
  1,746,797.
- **New reroll site `DIALOG_POST_SUB_REROLL`**, default 10.
  - `build_builder()` emits that many identity `X;X` pairs on `tx[1]` right
    after the two coordinate subtractions.
  - It is a second Fiat–Shamir knob next to `DIALOG_REROLL`, which stays at 9.
    It picks a clean test draw for the new op stream without changing Toffoli
    or qubits.
- The rest of the diff is rustfmt line-wrapping (`B::free`, the self-test,
  two `..._enabled()` helpers, `builder_from_ops`) with no effect on the
  output.

## Why it is still correct, and what it risks

This is exact. The removed wire was |0⟩ for its whole life and was only read
as the addend's top bit. The new helpers compute the same sum with that bit
treated as a constant 0. The boundary-carry identity and the measured carry
erasure are as in 68e3653.

No new failure mode is added. The new op stream draws a new test set for the
base's existing approximations (width envelope, comparator schedule, truncated
fold and clean windows). With `DIALOG_POST_SUB_REROLL = 10` that set is clean:
0 classical, 0 phase and 0 ancilla failures. A mistake in the new helpers
would show as a classical mismatch (wrong sum) or as phase garbage (a wrong
`cz_if` fix-up). See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The change frees a scratch wire at the peak without changing the gates that
do the work, so it is filed as register/scratch allocation. It could also be
called dead-wire elimination, because the wire held a known constant. The
census filed it as ancilla-lifetime / venting, which is reasonable: the
wire's lifetime drops to zero.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 075c0c6 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 075c0c6 36dcf6b -- src/point_add` is
   303 lines in 1 file. About 60 of them are formatting.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 36dcf6b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set.
   Expect:
   - 1571 qubits
   - 1,746,797 average Toffoli (rounded)
   - score 2,744,218,087
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL = 9`,
`DIALOG_POST_SUB_REROLL = 10` and an identical op stream. Any other change
needs a new reroll scan.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 3e99c85..69b5c14 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -412,7 +412,8 @@ impl B {
     }
     fn free(&mut self, q: QubitId) {
         self.r(q);
-        self.free_qubits.push(q.0.try_into().expect("qubit id fits in u32"));
+        self.free_qubits
+            .push(q.0.try_into().expect("qubit id fits in u32"));
         if self.active_qubits > 0 {
             self.active_qubits -= 1;
         }
@@ -1567,6 +1568,92 @@ fn cuccaro_sub_fast(b: &mut B, a: &[QubitId], acc: &[QubitId], c_in: QubitId) {
     b.free_vec(&carries);
 }
 
+/// Fast Cuccaro add into an extended accumulator where the source high bit is
+/// known zero: `acc_ext += a + c_in (mod 2^(n+1))`.
+fn cuccaro_add_fast_low_to_ext(b: &mut B, a: &[QubitId], acc_ext: &[QubitId], c_in: QubitId) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    if n == 0 {
+        b.cx(c_in, acc_ext[0]);
+        return;
+    }
+
+    let carries = b.alloc_qubits(n);
+
+    b.cx(a[0], acc_ext[0]);
+    b.cx(a[0], c_in);
+    b.ccx(c_in, acc_ext[0], carries[0]);
+    b.cx(carries[0], a[0]);
+    for i in 1..n {
+        b.cx(a[i], acc_ext[i]);
+        b.cx(a[i], a[i - 1]);
+        b.ccx(a[i - 1], acc_ext[i], carries[i]);
+        b.cx(carries[i], a[i]);
+    }
+
+    b.cx(a[n - 1], acc_ext[n]);
+
+    for i in (1..n).rev() {
+        b.cx(carries[i], a[i]);
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        b.cz_if(a[i - 1], acc_ext[i], m);
+        b.cx(a[i], a[i - 1]);
+        b.cx(a[i - 1], acc_ext[i]);
+    }
+    b.cx(carries[0], a[0]);
+    let m0 = b.alloc_bit();
+    b.hmr(carries[0], m0);
+    b.cz_if(c_in, acc_ext[0], m0);
+    b.cx(a[0], c_in);
+    b.cx(c_in, acc_ext[0]);
+
+    b.free_vec(&carries);
+}
+
+/// Fast Cuccaro subtract from an extended accumulator where the source high bit
+/// is known zero: `acc_ext -= a + c_in (mod 2^(n+1))`.
+fn cuccaro_sub_fast_low_to_ext(b: &mut B, a: &[QubitId], acc_ext: &[QubitId], c_in: QubitId) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    if n == 0 {
+        b.cx(c_in, acc_ext[0]);
+        return;
+    }
+
+    let carries = b.alloc_qubits(n);
+
+    b.cx(c_in, acc_ext[0]);
+    b.cx(a[0], c_in);
+    b.ccx(c_in, acc_ext[0], carries[0]);
+    b.cx(carries[0], a[0]);
+    for i in 1..n {
+        b.cx(a[i - 1], acc_ext[i]);
+        b.cx(a[i], a[i - 1]);
+        b.ccx(a[i - 1], acc_ext[i], carries[i]);
+        b.cx(carries[i], a[i]);
+    }
+
+    b.cx(a[n - 1], acc_ext[n]);
+
+    for i in (1..n).rev() {
+        b.cx(carries[i], a[i]);
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        b.cz_if(a[i - 1], acc_ext[i], m);
+        b.cx(a[i], a[i - 1]);
+        b.cx(a[i], acc_ext[i]);
+    }
+    b.cx(carries[0], a[0]);
+    let m0 = b.alloc_bit();
+    b.hmr(carries[0], m0);
+    b.cz_if(c_in, acc_ext[0], m0);
+    b.cx(a[0], c_in);
+    b.cx(a[0], acc_ext[0]);
+
+    b.free_vec(&carries);
+}
+
 /// Windowed measured add: `acc += a + c_in (mod 2^n)`, reusing the proven
 /// `cuccaro_add_fast` block-wise but threading the inter-block carry through a
 /// 1-bit register extension. Only ~n/blocks measured-carry ancillae are live at
@@ -1697,6 +1784,112 @@ fn cuccaro_sub_fast_windowed(
     }
 }
 
+fn cuccaro_add_fast_windowed_low_to_ext(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    c_in: QubitId,
+    blocks: usize,
+) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    let ext_n = acc_ext.len();
+    if ext_n == 0 {
+        return;
+    }
+    let blocks = blocks.max(1).min(ext_n);
+    if blocks == 1 {
+        cuccaro_add_fast_low_to_ext(b, a, acc_ext, c_in);
+        return;
+    }
+
+    let mut carry = c_in;
+    let mut lo = 0usize;
+    let mut couts: Vec<(QubitId, usize)> = Vec::new();
+    for blk in 0..blocks {
+        let hi = ((blk + 1) * ext_n) / blocks;
+        if hi <= lo {
+            continue;
+        }
+        if blk == blocks - 1 || hi == ext_n {
+            cuccaro_add_fast_low_to_ext(b, &a[lo..n], &acc_ext[lo..hi], carry);
+            break;
+        }
+        let cout = b.alloc_qubit();
+        let zero = b.alloc_qubit();
+        let mut a_block: Vec<QubitId> = a[lo..hi].to_vec();
+        a_block.push(zero);
+        let mut acc_block: Vec<QubitId> = acc_ext[lo..hi].to_vec();
+        acc_block.push(cout);
+        cuccaro_add_fast(b, &a_block, &acc_block, carry);
+        b.free(zero);
+        couts.push((cout, hi));
+        carry = cout;
+        lo = hi;
+    }
+
+    for &(cout, p) in couts.iter().rev() {
+        cmp_lt_into_fast(b, &acc_ext[..p], &a[..p], cout);
+        b.free(cout);
+    }
+}
+
+fn cuccaro_sub_fast_windowed_low_to_ext(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    c_in: QubitId,
+    blocks: usize,
+) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    let ext_n = acc_ext.len();
+    if ext_n == 0 {
+        return;
+    }
+    let blocks = blocks.max(1).min(ext_n);
+    if blocks == 1 {
+        cuccaro_sub_fast_low_to_ext(b, a, acc_ext, c_in);
+        return;
+    }
+
+    let mut borrow = c_in;
+    let mut lo = 0usize;
+    let mut bouts: Vec<(QubitId, usize)> = Vec::new();
+    for blk in 0..blocks {
+        let hi = ((blk + 1) * ext_n) / blocks;
+        if hi <= lo {
+            continue;
+        }
+        if blk == blocks - 1 || hi == ext_n {
+            cuccaro_sub_fast_low_to_ext(b, &a[lo..n], &acc_ext[lo..hi], borrow);
+            break;
+        }
+        let bout = b.alloc_qubit();
+        let zero = b.alloc_qubit();
+        let mut a_block: Vec<QubitId> = a[lo..hi].to_vec();
+        a_block.push(zero);
+        let mut acc_block: Vec<QubitId> = acc_ext[lo..hi].to_vec();
+        acc_block.push(bout);
+        cuccaro_sub_fast(b, &a_block, &acc_block, borrow);
+        b.free(zero);
+        bouts.push((bout, hi));
+        borrow = bout;
+        lo = hi;
+    }
+
+    for &(bout, p) in bouts.iter().rev() {
+        for i in 0..p {
+            b.x(a[i]);
+        }
+        cmp_lt_into_fast(b, &a[..p], &acc_ext[..p], bout);
+        for i in 0..p {
+            b.x(a[i]);
+        }
+        b.free(bout);
+    }
+}
+
 /// Self-test for `cuccaro_add_fast_windowed`: classically simulates the windowed
 /// adder for several (a, acc) and block counts and checks acc = a+acc mod 2^n,
 /// a restored, c_in cleared. Returns Err on first mismatch. Callable from the
@@ -1728,21 +1921,34 @@ pub fn mbuc_windowed_add_selftest() -> Result<(), String> {
             let mut xof = Shake128::default().finalize_xof();
             let mut sim = Simulator::new(nq, nb, &mut xof);
             for (i, &q) in a.iter().enumerate() {
-                if (av >> i) & 1 != 0 { *sim.qubit_mut(q) |= 1; }
+                if (av >> i) & 1 != 0 {
+                    *sim.qubit_mut(q) |= 1;
+                }
             }
             for (i, &q) in acc.iter().enumerate() {
-                if (accv >> i) & 1 != 0 { *sim.qubit_mut(q) |= 1; }
+                if (accv >> i) & 1 != 0 {
+                    *sim.qubit_mut(q) |= 1;
+                }
             }
             sim.apply_iter(ops.iter());
-            let mut got = 0u64; let mut a_out = 0u64;
-            for (i, &q) in acc.iter().enumerate() { got |= (sim.qubit(q) & 1) << i; }
-            for (i, &q) in a.iter().enumerate() { a_out |= (sim.qubit(q) & 1) << i; }
+            let mut got = 0u64;
+            let mut a_out = 0u64;
+            for (i, &q) in acc.iter().enumerate() {
+                got |= (sim.qubit(q) & 1) << i;
+            }
+            for (i, &q) in a.iter().enumerate() {
+                a_out |= (sim.qubit(q) & 1) << i;
+            }
             let want = av.wrapping_add(accv);
             if got != want {
-                return Err(format!("SUM blocks={blocks} a={av:#x} acc={accv:#x} got={got:#x} want={want:#x}"));
+                return Err(format!(
+                    "SUM blocks={blocks} a={av:#x} acc={accv:#x} got={got:#x} want={want:#x}"
+                ));
             }
             if a_out != av {
-                return Err(format!("A-NOT-RESTORED blocks={blocks} a={av:#x} a_out={a_out:#x}"));
+                return Err(format!(
+                    "A-NOT-RESTORED blocks={blocks} a={av:#x} a_out={a_out:#x}"
+                ));
             }
             if sim.qubit(c_in) & 1 != 0 {
                 return Err(format!("CIN-NOT-CLEARED blocks={blocks}"));
@@ -1764,15 +1970,30 @@ pub fn mbuc_windowed_add_selftest() -> Result<(), String> {
             let sops = bs.ops.clone();
             let mut sxof = Shake128::default().finalize_xof();
             let mut ssim = Simulator::new(snq, snb, &mut sxof);
-            for (i, &q) in sa.iter().enumerate() { if (av >> i) & 1 != 0 { *ssim.qubit_mut(q) |= 1; } }
-            for (i, &q) in sacc.iter().enumerate() { if (accv >> i) & 1 != 0 { *ssim.qubit_mut(q) |= 1; } }
+            for (i, &q) in sa.iter().enumerate() {
+                if (av >> i) & 1 != 0 {
+                    *ssim.qubit_mut(q) |= 1;
+                }
+            }
+            for (i, &q) in sacc.iter().enumerate() {
+                if (accv >> i) & 1 != 0 {
+                    *ssim.qubit_mut(q) |= 1;
+                }
+            }
             ssim.apply_iter(sops.iter());
-            let mut sgot = 0u64; let mut sa_out = 0u64;
-            for (i, &q) in sacc.iter().enumerate() { sgot |= (ssim.qubit(q) & 1) << i; }
-            for (i, &q) in sa.iter().enumerate() { sa_out |= (ssim.qubit(q) & 1) << i; }
+            let mut sgot = 0u64;
+            let mut sa_out = 0u64;
+            for (i, &q) in sacc.iter().enumerate() {
+                sgot |= (ssim.qubit(q) & 1) << i;
+            }
+            for (i, &q) in sa.iter().enumerate() {
+                sa_out |= (ssim.qubit(q) & 1) << i;
+            }
             let swant = accv.wrapping_sub(av);
             if sgot != swant {
-                return Err(format!("DIFF blocks={blocks} a={av:#x} acc={accv:#x} got={sgot:#x} want={swant:#x}"));
+                return Err(format!(
+                    "DIFF blocks={blocks} a={av:#x} acc={accv:#x} got={sgot:#x} want={swant:#x}"
+                ));
             }
             if sa_out != av {
                 return Err(format!("SUB-A-NOT-RESTORED blocks={blocks} a={av:#x}"));
@@ -1791,7 +2012,6 @@ pub fn mbuc_windowed_add_selftest() -> Result<(), String> {
     Ok(())
 }
 
-
 fn cuccaro_sub_fast_borrowed_carries(
     b: &mut B,
     a: &[QubitId],
@@ -23844,19 +24064,19 @@ fn dialog_gcd_cmod_add_materialized_pseudomersenne(
     }
 
     let (acc_ext, acc_ovf) = ext_reg(b, acc);
-    let f_ovf = b.alloc_qubit();
-    let mut f_ext = f.clone();
-    f_ext.push(f_ovf);
     let c_in = b.alloc_qubit();
 
     b.set_phase("dialog_gcd_materialized_special_raw_sum");
     if let Some(w) = dialog_gcd_apply_window_blocks() {
-        cuccaro_add_fast_windowed(b, &f_ext, &acc_ext, c_in, w);
+        cuccaro_add_fast_windowed_low_to_ext(b, &f, &acc_ext, c_in, w);
     } else {
+        let f_ovf = b.alloc_qubit();
+        let mut f_ext = f.clone();
+        f_ext.push(f_ovf);
         cuccaro_add_fast(b, &f_ext, &acc_ext, c_in);
+        b.free(f_ovf);
     }
     b.free(c_in);
-    b.free(f_ovf);
 
     b.set_phase("dialog_gcd_materialized_special_overflow_fold");
     if let Some(w) = fold_carry_trunc_window() {
@@ -23884,7 +24104,10 @@ fn dialog_gcd_cmod_add_materialized_pseudomersenne(
 }
 
 fn dialog_gcd_measured_apply_sub_enabled() -> bool {
-    std::env::var("DIALOG_GCD_MEASURED_APPLY_SUB").ok().as_deref() == Some("1")
+    std::env::var("DIALOG_GCD_MEASURED_APPLY_SUB")
+        .ok()
+        .as_deref()
+        == Some("1")
 }
 
 fn dialog_gcd_apply_window_blocks() -> Option<usize> {
@@ -23912,9 +24135,6 @@ fn dialog_gcd_cmod_sub_materialized_pseudomersenne(
     }
 
     let (acc_ext, acc_ovf) = ext_reg(b, acc);
-    let f_ovf = b.alloc_qubit();
-    let mut f_ext = f.clone();
-    f_ext.push(f_ovf);
 
     b.set_phase("dialog_gcd_materialized_special_raw_difference");
     if dialog_gcd_measured_apply_sub_enabled() {
@@ -23923,15 +24143,22 @@ fn dialog_gcd_cmod_sub_materialized_pseudomersenne(
         // already runs cuccaro_add_fast with its carry lane in this same phase.
         let c_in = b.alloc_qubit();
         if let Some(w) = dialog_gcd_apply_window_blocks() {
-            cuccaro_sub_fast_windowed(b, &f_ext, &acc_ext, c_in, w);
+            cuccaro_sub_fast_windowed_low_to_ext(b, &f, &acc_ext, c_in, w);
         } else {
+            let f_ovf = b.alloc_qubit();
+            let mut f_ext = f.clone();
+            f_ext.push(f_ovf);
             cuccaro_sub_fast(b, &f_ext, &acc_ext, c_in);
+            b.free(f_ovf);
         }
         b.free(c_in);
     } else {
+        let f_ovf = b.alloc_qubit();
+        let mut f_ext = f.clone();
+        f_ext.push(f_ovf);
         sub_nbit_qq(b, &f_ext, &acc_ext);
+        b.free(f_ovf);
     }
-    b.free(f_ovf);
 
     b.set_phase("dialog_gcd_materialized_special_underflow_fold");
     if let Some(w) = fold_carry_trunc_window() {
@@ -24340,7 +24567,10 @@ fn dialog_gcd_measured_underflow_gate_enabled() -> bool {
     // Measured (Gidney) uncompute of acc_ovf = ctrl & underflow_pred in the
     // materialized_special underflow_clean (HMR + cz_if = 0 Toffoli vs 1 CCX/iter).
     // Exact on the validated reroll island. Default OFF.
-    std::env::var("DIALOG_GCD_MEASURED_UNDERFLOW_GATE").ok().as_deref() == Some("1")
+    std::env::var("DIALOG_GCD_MEASURED_UNDERFLOW_GATE")
+        .ok()
+        .as_deref()
+        == Some("1")
 }
 
 fn round763_dedup_enabled() -> bool {
@@ -28751,7 +28981,9 @@ fn builder_from_ops(ops: Vec<Op>) -> B {
     b.counted_registers = regs;
     b.next_qubit = num_qubits.try_into().expect("qubit count fits in u32");
     b.next_bit = num_bits.try_into().expect("bit count fits in u32");
-    b.next_register = num_registers.try_into().expect("register count fits in u32");
+    b.next_register = num_registers
+        .try_into()
+        .expect("register count fits in u32");
     b.peak_qubits = num_qubits.try_into().expect("qubit count fits in u32");
     b.peak_phase = "materialized_ops";
     b.counted_phase_rows = phase_resources(&ops, &[]);
@@ -28813,6 +29045,10 @@ fn configure_ecdsafail_submission_route() {
     // New op stream (windowed apply + Karatsuba x-tail) needs its own clean
     // Fiat-Shamir island: REROLL=0 with WIDTH_MARGIN=27 validates 0/0/0 over 9024.
     set_default_env("DIALOG_REROLL", "9");
+    // LOWEXT changes circuit bytes by removing the explicit high-zero Apply
+    // source bit. This late identity pad lands the lowext stream on a clean
+    // 9024-shot island without changing Q or T.
+    set_default_env("DIALOG_POST_SUB_REROLL", "10");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
@@ -29005,6 +29241,17 @@ fn build_builder() -> B {
     // Step 1-2: Px -= Qx, Py -= Qy
     mod_sub_qb(b, &tx, &ox, p);
     mod_sub_qb(b, &ty, &oy, p);
+    if let Some(k) = std::env::var("DIALOG_POST_SUB_REROLL")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .filter(|&k| k > 0)
+    {
+        b.set_phase("dialog_post_sub_reroll");
+        for _ in 0..k {
+            b.x(tx[1]);
+            b.x(tx[1]);
+        }
+    }
 
     let route_transport = round218_b5_source_live_transport_pa_enabled();
     let route_history = round218_b5_history_stream_pa_enabled();
```

