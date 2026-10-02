# 89abe1b — Drop 2 qubits at zero Toffoli: a 256-wide constant load and a borrowed carry-in in the square's mid-subtract, plus the s2 cell as GCD-body scratch

| | |
| --- | --- |
| Contestant | zuiris |
| Date | 2026-06-06 |
| Submission | `b43ef81` |
| Commit | `89abe1bd58fc4666d3266fd39abe20a56f308d10` |
| Result | 1307 qubits × 1,489,212 Toffoli = **1,946,400,084** |
| Base | `f5f0f61` (jieyilong, git parent and frontier at the time): 1309 qubits × 1,489,212 Toffoli = 1,949,378,508 |
| Change vs base | qubits −2, Toffoli ±0, score −2,978,424 (leaderboard Δ −2,978,424) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [adders-and-carries](../concepts/adders-and-carries.md), [modular-fold](../concepts/modular-fold.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

A pure qubit cut, 1309 → 1307, with the same gates doing the same work. Two
phases bound the peak:

1. **The x-tail square's mid-subtract** (1309). Inside
   `squaring_sub_from_acc_schoolbook_lowq_shift22`, the `acc −= hi·2^32` step
   runs while the 512-bit square and the shifter's 24 flags are alive. Its
   modular subtract loaded the Solinas constant `2^256 − p` into a fresh
   257-qubit register and took a fresh carry-in. A new copy of the modular
   add/sub loads the constant into 256 qubits and puts the carry straight into
   the accumulator's extension bit (−1 qubit). It also lends the idle extension
   bit of the addend as the carry-in (−1 qubit).
2. **The dialog-GCD walk body** (1308 after the first cut). At the widest
   steps the subtract/add body still had to allocate a few fresh scratch lanes.
   The current step's K2 `s2` log cell is provably `|0⟩` during the body, so it
   is now lent as one of those lanes (−1 qubit).

Toffoli is unchanged at 1,489,212, so the score drops by 2 × 1,489,212 =
2,978,424. All three cuts are exact. The tail nonce was re-hunted because the
op stream changed.

## What changed and why it saves qubits

### 1. Ancilla-light modular subtract in the square (`R84_LOWQ=1`)

- **Where.** `squaring_sub_from_acc_schoolbook_lowq_shift22`
  (`arith/multiply.rs`) computes `acc −= x² mod p`. It folds the high half
  `hi` in at shifts 0, 4, 6, 10 and 32, because `2^256 ≡ 2^32 + 977` (see
  [modular-fold](../concepts/modular-fold.md)). The shift-32 term is
  `mod_shift_left_by_k_lowq(hi, 22)` → `mod_sub_qq(acc, hi)` →
  `mod_shift_right_by_k_lowq`. During that subtract, `tmp_ext` (512), `acc`,
  `x` and the shifter's spill, `ovf` and `flag_inv` (24) are all live. That is
  the 1309 high-water mark. This tree is the `88079e6` line, which never took
  the shifter-free walk of [33c072d](33c072d.md).
- **Old `mod_sub_qq`** = `emit_inverse(mod_add_qq)`. `mod_add_qq` widens `acc`
  and `a` to 257 bits, adds them, then does `add_nbit_const(acc_ext, c)` and a
  controlled `csub_nbit_const(acc_ext, c, flag)` with `c = 2^256 − p`. Both
  constant adds load `c` into a fresh 257-qubit register (`load_const(b, 257, c)`
  or a CX-loaded 257-qubit `a`) and run a textbook 257-bit `cuccaro_add` with
  a fresh carry-in. That is 257 + 1 transient qubits.
- **New `mod_sub_qq_lowq`** = `emit_inverse(mod_add_qq_lowq)` in
  `arith/modular.rs`. It has the same six steps, but the two constant adds call
  the new `add_nbit_const_extcarry_clean_with_cin` and
  `csub_nbit_const_extcarry_clean_with_cin` (`arith/const_arith.rs`). These
  load `c` into only 256 qubits, which is enough since `c < 2^33`. They run
  `cuccaro_add_low_to_ext_clean` (or its subtract inverse): a full 256-step
  MAJ sweep, a CX of the carry-out into `acc_ext[256]`, and a full UMA sweep.
  That is 512 Toffoli, the same as the old 257-bit textbook Cuccaro
  (2 × 256), and it uses no measurement, so it is safe under `emit_inverse`.
  **−1 qubit.**
- **`R84_LOWQ_CIN_BORROW=1`.** In `mod_add_qq_lowq`, the addend's extension bit
  `a_ovf` is `|0⟩` and untouched after step 1 (`a_ext` is only read again in
  its low 256 bits). It is passed as `borrow_cin`, so the Cuccaro carry-in is
  not allocated. The clean MAJ/UMA sweep returns it to `|0⟩`. **−1 qubit**
  (see [venting-and-wire-loans](../concepts/venting-and-wire-loans.md)).
- Only the mid-subtract under the shifter calls the new function (behind
  `r84_lowq_enabled()`). The other `mod_sub_qq` / `mod_add_qq` calls in the
  square are unchanged. The two cuts take this phase from 1309 to 1307.
- Also added, but not called on this route: `add_nbit_const_extcarry_clean`,
  `sub_nbit_const_extcarry_clean`, `cadd_nbit_const_extcarry_clean` and
  `csub_nbit_const_extcarry_clean` (wrappers without a borrowed carry-in).

### 2. Lend the current `s2` cell to the GCD body (`DIALOG_GCD_BORROW_CURRENT_S2=1`)

- **Where.** `dialog_gcd_build_composite_scratch` (`rounds/dialog/compressed.rs`)
  collects `want` clean lanes for the walk body's gated operand and carries. It
  borrows unwritten future-log cells, the current block's compressed cells
  (`BORROW_CURRENT_BLOCK`), and the high bits of `u` and `v` above
  `active_width`. It allocates fresh qubits only for the remainder. At the
  early steps where `active_width` is clamped at 256, that remainder is
  positive and set the 1308 compressed-block to-bitvector phases.
- **New.** If `DIALOG_GCD_BORROW_CURRENT_S2=1` and `raw_block` is non-empty, it
  also pushes `s2 = raw_block[2·group_size + step % group_size]`. That is the
  current step's K2 second-shift log bit. Forward, `s2` is written only by the
  shift phase after the body. In reverse, it has already been uncomputed by
  `reverse_unshift` before the add body. Either way it is `|0⟩` during the body,
  and the body's measured uncompute returns every borrowed lane to `|0⟩`. The
  usual guards apply: not already in the pool, not part of the active `u` or
  `v`. **−1 fresh lane**, with no gates added.

### 3. Other knobs

- New helpers `r84_lowq_enabled()` and `r84_lowq_cin_borrow_enabled()` in
  `mod.rs`. Defaults `R84_LOWQ=1`, `R84_LOWQ_CIN_BORROW=1` and
  `DIALOG_GCD_BORROW_CURRENT_S2=1` are set in
  `configure_ecdsafail_submission_route()`.
- `DIALOG_TAIL_NONCE`: 78338 → 201664.

## Why it is still correct, and what it risks

All three changes are exact.

- The 256-wide constant load holds `c = 2^32 + 977` exactly. The extended-carry
  Cuccaro computes the same 257-bit sum as the old 257-wide add.
- The borrowed carry-in and the borrowed `s2` lane are provably `|0⟩` when
  lent, and they are restored to `|0⟩` before their owners read them.
- Toffoli is unchanged, as the measured counts confirm.

If a borrow assumption were wrong, it would show up as ancilla garbage, or as
a corrupted `s2` log bit (a classical failure). None appears. The arithmetic
truncations (width envelope, 49-bit branch comparator, body trim, 20-bit
apply-clean comparator, 259 iterations) are unchanged, so the hazard set is the
same as [f5f0f61](f5f0f61.md). The op stream changed, so a new nonce was needed:
`201664` draws a test set with 0 classical, 0 phase and 0 ancilla failures over
all 9,024 shots. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The commit removes transient ancillas at the two peak-binding phases by
lending idle zero wires and narrowing one load, with no Toffoli change. That is
register and scratch allocation (ancilla lifetime and wire loans).

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f5f0f61 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol f5f0f61 89abe1b -- src/point_add` is
   345 lines in 5 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 89abe1b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `R84_*` environment variables set, because `set_default_env`
   only fills in unset variables. Expect:
   - 1307 qubits
   - 1,489,212 average Toffoli (rounded)
   - score 1,946,400,084
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=201664` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/adder.rs b/src/point_add/arith/adder.rs
index e02d10d..d4ee2d0 100644
--- a/src/point_add/arith/adder.rs
+++ b/src/point_add/arith/adder.rs
@@ -194,6 +194,82 @@ pub(crate) fn cuccaro_sub(b: &mut B, a: &[QubitId], acc: &[QubitId], c_in: Qubit
     inv_maj(b, c_in, acc[0], a[0]);
 }
 
+/// Clean (X/CX/CCX only, emit_inverse-safe) Cuccaro add of an n-bit register
+/// `a` into an (n+1)-bit accumulator `acc_ext`, capturing the carry-out into
+/// `acc_ext[n]`. `acc_ext` may hold any (n+1)-bit value on entry; `c_in` is a
+/// fresh ancilla at |0> that returns to |0>.
+///
+/// Unlike [`cuccaro_add`] (which discards the carry-out, omitting the top MAJ),
+/// this runs the *full* n-step MAJ sweep so the carry-out is materialized in
+/// `a[n-1]` after the sweep; we CX it into `acc_ext[n]`, then run the full UMA
+/// sweep to write the sum bits and restore `a` and `c_in`. This is the
+/// MAJ/UMA analogue of [`cuccaro_add_fast_low_to_ext`] (no measurement), so it
+/// is safe inside `emit_inverse` blocks. `a` is preserved.
+pub(crate) fn cuccaro_add_low_to_ext_clean(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    c_in: QubitId,
+) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    if n == 0 {
+        // acc_ext[0] += c_in.
+        b.cx(c_in, acc_ext[0]);
+        return;
+    }
+
+    // Full forward MAJ sweep (bits 0..=n-1). After this, a[n-1] holds the
+    // carry-out of the whole addition.
+    maj(b, c_in, acc_ext[0], a[0]);
+    for i in 1..n {
+        maj(b, a[i - 1], acc_ext[i], a[i]);
+    }
+
+    // Carry-out into the extension bit.
+    b.cx(a[n - 1], acc_ext[n]);
+
+    // Full reverse UMA sweep: writes sum bits into acc_ext[0..n], restores a
+    // and c_in to their entry values.
+    for i in (1..n).rev() {
+        uma(b, a[i - 1], acc_ext[i], a[i]);
+    }
+    uma(b, c_in, acc_ext[0], a[0]);
+}
+
+/// Gate-level inverse of [`cuccaro_add_low_to_ext_clean`]: computes
+/// `acc_ext := acc_ext - (a + c_in)` capturing the borrow-out into
+/// `acc_ext[n]` (the same bit toggles, since add and subtract share the carry
+/// identity under the running ext bit). `a` is preserved; `c_in` clean in/out.
+pub(crate) fn cuccaro_sub_low_to_ext_clean(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    c_in: QubitId,
+) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    if n == 0 {
+        b.cx(c_in, acc_ext[0]);
+        return;
+    }
+
+    // Inverse of the forward UMA sweep.
+    inv_uma(b, c_in, acc_ext[0], a[0]);
+    for i in 1..n {
+        inv_uma(b, a[i - 1], acc_ext[i], a[i]);
+    }
+
+    // Inverse of the carry-out write (CX is self-inverse).
+    b.cx(a[n - 1], acc_ext[n]);
+
+    // Inverse of the forward MAJ sweep.
+    for i in (1..n).rev() {
+        inv_maj(b, a[i - 1], acc_ext[i], a[i]);
+    }
+    inv_maj(b, c_in, acc_ext[0], a[0]);
+}
+
 
 pub(crate) fn load_const(b: &mut B, n: usize, c: U256) -> Vec<QubitId> {
     let qs = b.alloc_qubits(n);
diff --git a/src/point_add/arith/const_arith.rs b/src/point_add/arith/const_arith.rs
index 3544eb1..3a3f633 100644
--- a/src/point_add/arith/const_arith.rs
+++ b/src/point_add/arith/const_arith.rs
@@ -217,6 +217,149 @@ pub(crate) fn cadd_nbit_const_direct_fast(b: &mut B, acc: &[QubitId], c: U256, c
     b.free_vec(&carries);
 }
 
+// ═══════════════════════════════════════════════════════════════════════════
+//  Ancilla-light extended-carry constant adders (clean, emit_inverse-safe)
+// ═══════════════════════════════════════════════════════════════════════════
+//
+// These add/subtract a classical constant `c` to an (n+1)-bit accumulator
+// `acc_ext` (= n-bit register + a top extension bit), capturing the carry/borrow
+// into `acc_ext[n]` — exactly like the load-a-full-(n+1)-register + Cuccaro
+// pattern in `add_nbit_const`/`csub_nbit_const`, but the loaded constant register
+// is only `n = acc_ext.len() - 1` qubits wide (not n+1). For the round84 Solinas
+// constant c = 2^256 - p = 2^32 + 977, which has highest set bit 32 ≪ n, the
+// low-n register trivially holds it, and the clean carry-capturing Cuccaro
+// (`cuccaro_add/sub_low_to_ext_clean`, X/CX/CCX only) folds the overflow into
+// `acc_ext[n]`. This drops the +1-qubit transient of the materialized 257-wide
+// `load_const` at the mid-sub peak. All four are measurement-free, so they are
+// safe to replay under `emit_inverse`.
+
+/// `acc_ext := (acc_ext + c) mod 2^(n+1)` capturing carry into the top bit.
+/// Drop-in value-replacement for `add_nbit_const` when the caller passes an
+/// extended (n+1)-wide register and `c < 2^n`.
+pub(crate) fn add_nbit_const_extcarry_clean(b: &mut B, acc_ext: &[QubitId], c: U256) {
+    add_nbit_const_extcarry_clean_with_cin(b, acc_ext, c, None);
+}
+
+/// Same as [`add_nbit_const_extcarry_clean`] but optionally sources the Cuccaro
+/// carry-in ancilla from a caller-supplied **clean (|0>) idle** qubit instead of
+/// allocating a fresh one. When `borrow_cin = Some(q)`, `q` must be |0> on entry
+/// and idle for the duration of this call; it is used as the carry-in slot and
+/// returned to |0> (the clean MAJ/UMA sweep restores it). Sourcing the carry-in
+/// from an existing live-but-idle lane removes the sole +1 fresh allocation that
+/// pins the round84-lowq mid-sub peak at 1308 → 1307. Value-/phase-identical to
+/// the fresh-ancilla path (the borrowed qubit plays the identical role).
+pub(crate) fn add_nbit_const_extcarry_clean_with_cin(
+    b: &mut B,
+    acc_ext: &[QubitId],
+    c: U256,
+    borrow_cin: Option<QubitId>,
+) {
+    let ext = acc_ext.len();
+    debug_assert!(ext >= 1);
+    let n = ext - 1;
+    let ca = load_const(b, n, c);
+    let (c_in, fresh) = match borrow_cin {
+        Some(q) => (q, false),
+        None => (b.alloc_qubit(), true),
+    };
+    cuccaro_add_low_to_ext_clean(b, &ca, acc_ext, c_in);
+    if fresh {
+        b.free(c_in);
+    }
+    unload_const(b, &ca, c);
+}
+
+/// `acc_ext := (acc_ext - c) mod 2^(n+1)` capturing borrow into the top bit.
+/// Drop-in value-replacement for `sub_nbit_const`.
+pub(crate) fn sub_nbit_const_extcarry_clean(b: &mut B, acc_ext: &[QubitId], c: U256) {
+    let ext = acc_ext.len();
+    debug_assert!(ext >= 1);
+    let n = ext - 1;
+    let ca = load_const(b, n, c);
+    let c_in = b.alloc_qubit();
+    cuccaro_sub_low_to_ext_clean(b, &ca, acc_ext, c_in);
+    b.free(c_in);
+    unload_const(b, &ca, c);
+}
+
+/// Controlled `acc_ext += (ctrl ? c : 0)` (mod 2^(n+1)), carry into top bit.
+/// The constant is loaded as `(ctrl ? c : 0)` via CX-from-ctrl, so the
+/// unconditional clean adder realizes the controlled add. Drop-in for
+/// `cadd_nbit_const`.
+pub(crate) fn cadd_nbit_const_extcarry_clean(
+    b: &mut B,
+    acc_ext: &[QubitId],
+    c: U256,
+    ctrl: QubitId,
+) {
+    let ext = acc_ext.len();
+    debug_assert!(ext >= 1);
+    let n = ext - 1;
+    let ca = b.alloc_qubits(n);
+    for i in 0..n {
+        if bit(c, i) {
+            b.cx(ctrl, ca[i]);
+        }
+    }
+    let c_in = b.alloc_qubit();
+    cuccaro_add_low_to_ext_clean(b, &ca, acc_ext, c_in);
+    b.free(c_in);
+    for i in 0..n {
+        if bit(c, i) {
+            b.cx(ctrl, ca[i]);
+        }
+    }
+    b.free_vec(&ca);
+}
+
+/// Controlled `acc_ext -= (ctrl ? c : 0)` (mod 2^(n+1)), borrow into top bit.
+/// Drop-in for `csub_nbit_const`.
+pub(crate) fn csub_nbit_const_extcarry_clean(
+    b: &mut B,
+    acc_ext: &[QubitId],
+    c: U256,
+    ctrl: QubitId,
+) {
+    csub_nbit_const_extcarry_clean_with_cin(b, acc_ext, c, ctrl, None);
+}
+
+/// Same as [`csub_nbit_const_extcarry_clean`] but optionally sources the Cuccaro
+/// borrow-in ancilla from a caller-supplied clean (|0>) idle qubit. See
+/// [`add_nbit_const_extcarry_clean_with_cin`] for the borrow contract. This is
+/// the peak-binding call inside the round84-lowq mid-sub; borrowing its `c_in`
+/// from the idle `a_ovf` lane drops the mid-sub peak 1308 → 1307.
+pub(crate) fn csub_nbit_const_extcarry_clean_with_cin(
+    b: &mut B,
+    acc_ext: &[QubitId],
+    c: U256,
+    ctrl: QubitId,
+    borrow_cin: Option<QubitId>,
+) {
+    let ext = acc_ext.len();
+    debug_assert!(ext >= 1);
+    let n = ext - 1;
+    let ca = b.alloc_qubits(n);
+    for i in 0..n {
+        if bit(c, i) {
+            b.cx(ctrl, ca[i]);
+        }
+    }
+    let (c_in, fresh) = match borrow_cin {
+        Some(q) => (q, false),
+        None => (b.alloc_qubit(), true),
+    };
+    cuccaro_sub_low_to_ext_clean(b, &ca, acc_ext, c_in);
+    if fresh {
+        b.free(c_in);
+    }
+    for i in 0..n {
+        if bit(c, i) {
+            b.cx(ctrl, ca[i]);
+        }
+    }
+    b.free_vec(&ca);
+}
+
 pub(crate) fn add_nbit_const_direct_uncontrolled_fast(b: &mut B, acc: &[QubitId], c: U256) {
     let ctrl = b.alloc_qubit();
     b.x(ctrl);
diff --git a/src/point_add/arith/modular.rs b/src/point_add/arith/modular.rs
index 69feea2..7e1ec8d 100644
--- a/src/point_add/arith/modular.rs
+++ b/src/point_add/arith/modular.rs
@@ -58,6 +58,70 @@ pub(crate) fn mod_sub_qq(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
     emit_inverse(b, move |b| mod_add_qq(b, acc, &a_copy, p));
 }
 
+/// Ancilla-light copy of [`mod_add_qq`]. The only difference: the two Solinas
+/// constant corrections (`+c` in step 2 and the conditional `-c` in step 4) use
+/// the extended-carry clean adders, which load `c = 2^256 - p` into a 256-qubit
+/// register (= `acc_ext.len() - 1`) and fold the overflow into `acc_ext[n]` via a
+/// measurement-free Cuccaro. The stock `mod_add_qq` instead calls
+/// `add_nbit_const`/`csub_nbit_const`, which materialize a full 257-qubit loaded
+/// constant — the sole +1 transient that pins the round84 mid-sub peak at 1309.
+/// Replacing it with the 256-wide load drops that peak to 1308. Value- and
+/// phase-identical to `mod_add_qq`; clean (no `b.hmr`), so `emit_inverse`-safe.
+pub(crate) fn mod_add_qq_lowq(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
+    let n = acc.len();
+    assert_eq!(n, a.len());
+    debug_assert_eq!(n, 256);
+
+    let (acc_ext, acc_ovf) = ext_reg(b, acc);
+    let (a_ext, a_ovf) = ext_reg(b, a);
+
+    // Step 1: (n+1)-bit add. acc_ext ∈ [0, 2p).
+    add_nbit_qq(b, &a_ext, &acc_ext);
+
+    // The addend `a_ext` is preserved by every step below (the only later read of
+    // it, the step-6 compare, touches a_ext[..n] only), so `a_ovf = a_ext[n]` is
+    // provably |0> and idle during the two const corrections (steps 2 & 4). Under
+    // the borrow flag we lend it to the Cuccaro as the carry-in slot, removing the
+    // sole fresh +1 transient that pins the round84-lowq mid-sub peak at 1308.
+    let borrow = if r84_lowq_cin_borrow_enabled() {
+        Some(a_ovf)
+    } else {
+        None
+    };
+
+    // Step 2: add c (ancilla-light: 256-wide const load + clean carry capture).
+    let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
+    add_nbit_const_extcarry_clean_with_cin(b, &acc_ext, c, borrow);
+
+    // Step 3: flag := acc_ovf (= top bit of sum + c).
+    let flag = b.alloc_qubit();
+    b.cx(acc_ovf, flag);
+
+    // Step 4: if flag=0 (no reduction needed), undo the add of c.
+    b.x(flag);
+    csub_nbit_const_extcarry_clean_with_cin(b, &acc_ext, c, flag, borrow);
+    b.x(flag);
+
+    // Step 5: if flag=1, clear the top bit (drops 2^n → yields sum - p).
+    b.cx(flag, acc_ovf);
+
+    // Step 6: uncompute flag (same identity as mod_add_qq).
+    cmp_lt_into(b, &acc_ext[..n], &a_ext[..n], flag);
+    b.free(flag);
+
+    unext_reg(b, a_ovf);
+    unext_reg(b, acc_ovf);
+    let _ = (acc_ext, a_ext);
+}
+
+/// Ancilla-light `acc := (acc - a) mod p`. Exact gate-level inverse of
+/// [`mod_add_qq_lowq`] (which is clean), so `emit_inverse` replays it as
+/// `(acc, a) ↦ (acc - a mod p, a)` with operand preserved and zero phase.
+pub(crate) fn mod_sub_qq_lowq(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
+    let a_copy: Vec<QubitId> = a.to_vec();
+    emit_inverse(b, move |b| mod_add_qq_lowq(b, acc, &a_copy, p));
+}
+
 /// Fast `acc := (acc - a) mod p`. Direct sub + conditional add-p + flag
 /// uncompute via neg+cmp_lt+neg. All ops use measurement-based Cuccaro.
 pub(crate) fn mod_sub_qq_fast(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
diff --git a/src/point_add/arith/multiply.rs b/src/point_add/arith/multiply.rs
index e7babc9..2bf765e 100644
--- a/src/point_add/arith/multiply.rs
+++ b/src/point_add/arith/multiply.rs
@@ -1154,7 +1154,11 @@ pub(crate) fn squaring_sub_from_acc_schoolbook_lowq_shift22(
     }
     mod_sub_qq(b, acc, &hi, p);
     let (spill, flag_inv, ovf) = mod_shift_left_by_k_lowq(b, &hi, p, 22);
-    mod_sub_qq(b, acc, &hi, p);
+    if r84_lowq_enabled() {
+        mod_sub_qq_lowq(b, acc, &hi, p);
+    } else {
+        mod_sub_qq(b, acc, &hi, p);
+    }
     mod_shift_right_by_k_lowq(b, &hi, p, 22, spill, flag_inv, ovf);
     for _ in 0..10 {
         mod_halve_inplace_direct_const_fast(b, &hi, p);
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 6a6469a..4f612ea 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -559,6 +559,14 @@ fn secp_direct_const_arith_enabled() -> bool {
     std::env::var("SECP_DIRECT_CONST_ARITH").ok().as_deref() == Some("1")
 }
 
+fn r84_lowq_enabled() -> bool {
+    std::env::var("R84_LOWQ").ok().as_deref() == Some("1")
+}
+
+fn r84_lowq_cin_borrow_enabled() -> bool {
+    std::env::var("R84_LOWQ_CIN_BORROW").ok().as_deref() == Some("1")
+}
+
 fn kal_vent_modadd_enabled() -> bool {
     std::env::var("KAL_VENT_MODADD").ok().as_deref() == Some("1")
 }
@@ -1238,6 +1246,11 @@ fn configure_ecdsafail_submission_route() {
     // high-window comparator carry-in, avoiding the generic split's extra
     // boundary qubit and low-window recompute.
     set_default_env("DIALOG_GCD_APPLY_FINAL_LOWQ", "0");
+    // Round84 mid-sub: ancilla-light Cuccaro const-add + carry-in borrow (1309->1307);
+    // compressed-block: current-step s2 composite-scratch fold (1308->1307).
+    set_default_env("R84_LOWQ", "1");
+    set_default_env("R84_LOWQ_CIN_BORROW", "1");
+    set_default_env("DIALOG_GCD_BORROW_CURRENT_S2", "1");
     set_default_env("DIALOG_GCD_APPLY_BOUNDARY_SPLIT", "100");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "50");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "100");
@@ -1327,7 +1340,7 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=262 route:
     // nonce 2432 validates 0/0/0 over all 9024 shots at
     // 1309q x 1,497,795 T = 1,960,613,655.
-    set_default_env("DIALOG_TAIL_NONCE", "78338");
+    set_default_env("DIALOG_TAIL_NONCE", "201664");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
diff --git a/src/point_add/rounds/dialog/compressed.rs b/src/point_add/rounds/dialog/compressed.rs
index e78547a..1628639 100644
--- a/src/point_add/rounds/dialog/compressed.rs
+++ b/src/point_add/rounds/dialog/compressed.rs
@@ -323,6 +323,24 @@ pub(crate) fn dialog_gcd_borrow_current_block_enabled() -> bool {
         == Some("1")
 }
 
+pub(crate) fn dialog_gcd_borrow_current_s2_enabled() -> bool {
+    // Successor lever to BORROW_CURRENT_BLOCK for the K2 path. The current step's
+    // own shift2 (`s2`) cell is provably |0> across its sub/add body window
+    // (forward: written only by the later shift phase; reverse: already
+    // uncomputed by reverse_unshift) and is restored to |0> by the body's
+    // measured uncompute before the shift/unshift consumer. Folding it into the
+    // composite-scratch borrow removes one fresh-allocated deficit lane at the
+    // width-clamped GCD-walk binder steps (where active_width is pinned at N and
+    // the future-log borrow has already shrunk a block), dropping the three
+    // compressed-block tobitvector near-binders one qubit. Pure relabel, 0 added
+    // Toffoli, value-exact on the reachable GCD support. Default off keeps the
+    // accepted op stream byte-identical.
+    std::env::var("DIALOG_GCD_BORROW_CURRENT_S2")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
 pub(crate) struct DialogGcdCompositeScratch {
     lanes: Vec<QubitId>,
     owned: Vec<QubitId>,
@@ -396,6 +414,29 @@ pub(crate) fn dialog_gcd_build_composite_scratch(
             push(q);
         }
     }
+    if dialog_gcd_borrow_current_s2_enabled() && !raw_block.is_empty() {
+        // The CURRENT step's own K2 shift2 (`s2`) cell is |0> across this step's
+        // body window: forward it is written only by the later SHIFT phase
+        // (after the sub body), reverse it has just been uncomputed by
+        // reverse_unshift (before the add body). It is restored to |0> by the
+        // body's measured uncompute before either consumer runs. Folding it into
+        // the body-scratch borrow shrinks the fresh deficit by one lane at the
+        // width-clamped binder steps (the same retiming trick as the current-block
+        // compressed cells; pure relabel, 0 added Toffoli). The `push` closure
+        // excludes all raw_block cells, so add it explicitly with the same
+        // operand/duplicate guards. Disjoint from b0/b0_and_b1 (different slot
+        // offset) and from u/v (raw_block is its own register).
+        let group_size = dialog_gcd_sidecar_group_size();
+        let slot = step % group_size;
+        let s2 = raw_block[2 * group_size + slot];
+        if lanes.len() < want
+            && !lanes.contains(&s2)
+            && !u[..active_width].contains(&s2)
+            && !v[..active_width].contains(&s2)
+        {
+            lanes.push(s2);
+        }
+    }
     let owned = b.alloc_qubits(want - lanes.len());
     lanes.extend_from_slice(&owned);
     DialogGcdCompositeScratch { lanes, owned }
```

