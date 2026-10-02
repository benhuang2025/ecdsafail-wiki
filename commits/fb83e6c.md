# fb83e6c — Measured carry uncompute in the Karatsuba z2 square, with the carry lane parked on the square's own unwritten high zeros

| | |
| --- | --- |
| Contestant | nikhiljha |
| Date | 2026-06-03 |
| Submission | `bce2763` |
| Commit | `fb83e6c5bc609c35fa439ac93a08b07e5a10da0f` |
| Result | 1434 qubits × 1,716,807 Toffoli = **2,461,901,238** |
| Base | `bdfc7df` (git parent and frontier at the time, aburan28): 1434 qubits × 1,723,493 Toffoli = 2,471,488,962. The census base is `b343178` (BitWonka, 1434 × 1,729,113 = 2,479,548,042); see Reproduce for why the parent is used |
| Change vs base | qubits ±0, Toffoli −6,686, score −9,587,724 (leaderboard Δ −9,587,724). Against `b343178`: Toffoli −12,306, score −17,646,804 |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [adders-and-carries](../concepts/adders-and-carries.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The x-tail computes `λ²` with a one-level Karatsuba square. Its `z2 = hi²`
lobe used the ancilla-free "lowq" schoolbook square: each row is added into
the product register with an in-place Cuccaro adder, which pays one Toffoli
in the MAJ sweep and another in the UMA sweep for every bit. This commit adds
a self-hosted variant whose row adds use the fast Cuccaro adder: one Toffoli
per bit forward, and a measurement (`hmr` plus a conditional `CZ`) instead of
the UMA Toffoli. The fast adder needs a carry lane. It is hosted on the high
part of the product slice that the square has not written yet, which is
still |0⟩, plus 3 freshly allocated qubits. That removes about 16,800
Toffoli at the unchanged 1434-qubit peak.

The author also gave back the dialog-GCD truncation tightenings of the
previous few hours (comparator cap, apply-clean comparator, schedule margin,
one GCD step and, relative to the parent, its width margin). These cost
Toffoli but lower λ, so that a clean reroll pair can be found. The net saving
is 12,306 against the author's starting tree `b343178` and 6,686 against the
parent `bdfc7df`, whose width-margin cut this commit does not keep.

## What changed and why it saves Toffoli

All changes are in `src/point_add/mod.rs`.

1. **New `schoolbook_square_symmetric_lowq_selfhosted` and
   `schoolbook_square_symmetric_lowq_selfhosted_inverse`.**
   - They are copies of `schoolbook_square_symmetric_lowq` (and its inverse).
     Row `i` (width `n − i + 1`, or 1 for the last row) is built from
     `x[i]` and the cross products `x[i]·x[i+1+k]`, then added into the
     product slice `tmp_ext[2i .. hi]` with `hi = 2i + width + 1`.
   - The only change is the row adder: `cuccaro_add` (in place, MAJ then
     UMA, `2(L − 1)` CCX for `L` bits) becomes
     `cuccaro_add_fast_borrowed_carries` (`L − 1` CCX forward; the carries
     are cleared by `hmr` and `cz_if`, no Toffoli). The inverse uses
     `cuccaro_sub` → `cuccaro_sub_fast_borrowed_carries` the same way. With
     the padded row (`L = width + 1`) that saves `width` Toffoli per row.
   - **Carry lane.** The fast adder needs `width` clean carry qubits. It
     takes `tmp_ext[hi ..]` first. Rows `0..=i` only write
     `tmp_ext[..hi]`, so those higher wires are still |0⟩. There are
     `2n − hi = n − i − 2` of them, so the remaining 3 come from
     `b.alloc_qubits(from_global)` and are freed after the row. The fast
     adder's measured uncompute returns the borrowed wires to |0⟩. See
     [venting-and-wire-loans](../concepts/venting-and-wire-loans.md) for the
     borrowing idea.
   - The row's cross products are still cleared by `hmr` + `cz_if`, as in
     the base.
2. **Routing.**
   - `squaring_sub_from_acc_karatsuba`: when `KARA_Z02_LOWQ=1` (set by the
     route), the forward and the inverse `z2 = hi²` squares on `x_hi`
     (128 bits) call the self-hosted variants if `kara_z2_selfhost_enabled()`
     (`KARA_Z2_SELFHOST`, default on; the route also sets it to `1`). The
     `z0 = lo²` lobe already used a hosted fast square on the still-clean
     `z2` slice, so this was the remaining CCX-uncompute lobe.
   - With `n = 128` the row widths sum to 8,383, so one forward plus one
     inverse `z2` square saves 16,766 Toffoli. The x-tail
     (`round84_emit_fused_square_xtail`, `ROUND84_XTAIL_KARATSUBA=1`) runs
     this once per point add.
   - `squaring_sub_from_acc_schoolbook_lowq_shift22` gets the same switch,
     `XTAIL_SQ_SELFHOST` (default on). It is only reached on non-default
     routes (for example `SECP_D1_LOWQ_SQUARE` or the round564 y-tail), so it
     does not change the shipped count; a 256-bit square there would save
     about 33,000 per direction, which the measured total rules out.
   - The 3 extra carry qubits sit below the peak, which is set elsewhere, so
     the peak stays at 1434.
3. **Loosened knobs in `configure_ecdsafail_submission_route()`**, back
   to the values of the author's "handoff" support envelope. Old values are
   the parent's; the `b343178` value is given where it differs.
   - `DIALOG_GCD_COMPARE_BITS` 56 (`b343178`: 57) → 58: the cap on the GCD
     branch comparator. The comments put 58 → 57 at −1,064 Toffoli.
   - `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` 19 → 20: the apply-phase
     correction comparator (20 → 19 was −790).
   - `DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN` 5 → 7: the margin added to
     the per-step comparator schedule (7 → 5 was −452).
   - `DIALOG_GCD_ACTIVE_ITERATIONS` 395 → 396: one more GCD step.
   - `DIALOG_GCD_WIDTH_MARGIN` 25 (`b343178`: 26) → 26: the width-envelope
     margin that the parent [`bdfc7df`](bdfc7df.md) had just cut for
     −4,576 Toffoli. This commit was built on the older tree and never had it.
   - Against `b343178`, the first four account for the gap between the
     16,766 saved and the 12,306 measured. Each is a wider or longer
     approximation, so the circuit fails on fewer inputs.
4. **Reroll pair:** `DIALOG_REROLL` 643155 (`b343178`: 1844) → 102,
   `DIALOG_POST_SUB_REROLL` 208158 (`b343178`: 3532) → 100. These are counts of identity `X;X`
   pairs that re-seed the Fiat–Shamir test inputs. See
   [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Why it is still correct, and what it risks

- **The square change is exact.** The fast Cuccaro adder computes the same
  sum as the in-place one. Its measured uncompute is the standard one: after
  `hmr` of a carry, `cz_if(a, b, m)` fixes the phase, so the borrowed wires
  come back as |0⟩ with no phase error. The borrowed `tmp_ext` wires are
  |0⟩ by construction, because no earlier row writes above `hi`. If that
  were wrong, the adder would add garbage and the run would show classical
  failures. A missed phase fix would show up as phase failures. See
  [measurement-uncompute](../concepts/measurement-uncompute.md) and
  [adders-and-carries](../concepts/adders-and-carries.md).
- **The loosened knobs lower the risk.** All of them are truncation or step
  budgets of the dialog GCD (see
  [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)).
  Widening them makes fewer inputs fail, which lowers λ and makes clean
  reroll pairs common again. The author's note says the later tightenings had
  made clean draws scarce.
- The shipped pair (102, 100) is clean: 0 classical, 0 phase and 0 ancilla
  failures over all 9,024 shots.

## Classification rationale

The Toffoli saving comes entirely from replacing a CCX uncompute (the UMA
sweep) with a measurement-based one. That is measurement uncompute. Hosting
the carry lane on dead high zeros (scratch reuse) is what keeps it
peak-neutral, but it is the enabler, not the saving. The knob
give-backs cost Toffoli and are a λ choice, not a separate lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout bdfc7df -- src/point_add`.
   - The census base is `b343178` (BitWonka). The author's knob values and
     comments descend from it, and `git diff --ignore-cr-at-eol b343178
     fb83e6c -- src/point_add` is only 138 lines in `mod.rs`. But this
     commit's tree also holds 209 macOS AppleDouble files (`._*`, 4 KB of
     binary metadata each) that came in with `2bd707e` and that `b343178`
     lacks. They are not source and do not affect the build, but they cannot
     be inlined as a text patch, and macOS `tar` mangles them on extraction.
   - The git parent `bdfc7df` already has the same 209 files, so it is used
     here. Its diff is 140 lines in `mod.rs`. Read against it, the patch also
     shows `DIALOG_GCD_WIDTH_MARGIN` going back from 25 to 26, the comparator
     cap going from 56 rather than 57 to 58, and the parent's reroll pair
     being replaced. Those lines undo the parent's [`bdfc7df`](bdfc7df.md)
     cut; they are not a new choice by this author.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol fb83e6c -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KARA_*`, `XTAIL_*` or `ROUND84_*` environment variables set,
   because `set_default_env` keeps any value already in the environment.
   Expect:
   - 1434 qubits
   - 1,716,807 average Toffoli (rounded)
   - score 2,461,901,238
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=102`,
`DIALOG_POST_SUB_REROLL=100` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 249204b..81dfd94 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -6047,6 +6047,107 @@ fn schoolbook_square_symmetric_hosted_inverse(
     }
 }
 
+/// Like `schoolbook_square_symmetric_lowq` but converts the per-row Cuccaro
+/// UMA-uncompute (CCX, executed every shot) into measurement-based (fast)
+/// uncompute, WITHOUT a separate clean host register. The fast carry lane is
+/// hosted on the slice's OWN not-yet-written high zeros
+/// (`tmp_ext[2i+width+1 ..]`, which rows 0..=i never touch) topped up with a
+/// small global remainder (<=3 qubits, since the lane width exceeds the clean
+/// tail by exactly the 3-bit diagonal/gap/pad overhead). Unlike
+/// `schoolbook_square_symmetric_hosted` this needs no sibling clean register,
+/// so it applies where the sibling slice is occupied (the Karatsuba z2 square).
+/// Peak rises only by the global remainder (<=3); Toffoli drops by the whole
+/// UMA-uncompute. The borrowed carries are returned clean by the HMR uncompute.
+fn schoolbook_square_symmetric_lowq_selfhosted(b: &mut B, x: &[QubitId], tmp_ext: &[QubitId]) {
+    let n = x.len();
+    debug_assert_eq!(tmp_ext.len(), 2 * n);
+    for i in 0..n {
+        let width = if i == n - 1 { 1 } else { n - i + 1 };
+        let num_cross = if i + 1 < n { n - i - 1 } else { 0 };
+        let row = b.alloc_qubits(width);
+        b.cx(x[i], row[0]);
+        for k in 0..num_cross {
+            b.ccx(x[i], x[i + 1 + k], row[k + 2]);
+        }
+        let pad = b.alloc_qubit();
+        let mut row_padded = row.clone();
+        row_padded.push(pad);
+        let hi = 2 * i + width + 1;
+        let slice: Vec<QubitId> = tmp_ext[2 * i..hi].to_vec();
+        let need = row_padded.len() - 1;
+        let avail = tmp_ext.len() - hi;
+        let from_tmp = need.min(avail);
+        let from_global = need - from_tmp;
+        let gpool = b.alloc_qubits(from_global);
+        let mut carries: Vec<QubitId> = tmp_ext[hi..hi + from_tmp].to_vec();
+        carries.extend_from_slice(&gpool);
+        let c_in = b.alloc_qubit();
+        cuccaro_add_fast_borrowed_carries(b, &row_padded, &slice, c_in, &carries);
+        b.free(c_in);
+        b.free_vec(&gpool);
+        b.free(pad);
+        b.cx(x[i], row[0]);
+        for k in 0..num_cross {
+            let m = b.alloc_bit();
+            b.hmr(row[k + 2], m);
+            b.cz_if(x[i], x[i + 1 + k], m);
+        }
+        b.free_vec(&row);
+    }
+}
+
+fn schoolbook_square_symmetric_lowq_selfhosted_inverse(b: &mut B, x: &[QubitId], tmp_ext: &[QubitId]) {
+    let n = x.len();
+    debug_assert_eq!(tmp_ext.len(), 2 * n);
+    for i in (0..n).rev() {
+        let width = if i == n - 1 { 1 } else { n - i + 1 };
+        let num_cross = if i + 1 < n { n - i - 1 } else { 0 };
+        let row = b.alloc_qubits(width);
+        b.cx(x[i], row[0]);
+        for k in 0..num_cross {
+            b.ccx(x[i], x[i + 1 + k], row[k + 2]);
+        }
+        let pad = b.alloc_qubit();
+        let mut row_padded = row.clone();
+        row_padded.push(pad);
+        let hi = 2 * i + width + 1;
+        let slice: Vec<QubitId> = tmp_ext[2 * i..hi].to_vec();
+        let need = row_padded.len() - 1;
+        let avail = tmp_ext.len() - hi;
+        let from_tmp = need.min(avail);
+        let from_global = need - from_tmp;
+        let gpool = b.alloc_qubits(from_global);
+        let mut carries: Vec<QubitId> = tmp_ext[hi..hi + from_tmp].to_vec();
+        carries.extend_from_slice(&gpool);
+        let c_in = b.alloc_qubit();
+        cuccaro_sub_fast_borrowed_carries(b, &row_padded, &slice, c_in, &carries);
+        b.free(c_in);
+        b.free_vec(&gpool);
+        b.free(pad);
+        b.cx(x[i], row[0]);
+        for k in 0..num_cross {
+            let m = b.alloc_bit();
+            b.hmr(row[k + 2], m);
+            b.cz_if(x[i], x[i + 1 + k], m);
+        }
+        b.free_vec(&row);
+    }
+}
+
+/// Gate for the measured-uncompute (self-hosted) Karatsuba z2 square. Defaults
+/// ON; set KARA_Z2_SELFHOST=0 to fall back to the plain ancilla-free lowq z2
+/// square (CCX UMA-uncompute).
+fn kara_z2_selfhost_enabled() -> bool {
+    std::env::var("KARA_Z2_SELFHOST").ok().as_deref() != Some("0")
+}
+
+/// Gate for the measured-uncompute (self-hosted) round84 x-tail full-width
+/// lam^2 square. Defaults ON; set XTAIL_SQ_SELFHOST=0 to fall back to the plain
+/// ancilla-free lowq square (CCX UMA-uncompute).
+fn xtail_sq_selfhost_enabled() -> bool {
+    std::env::var("XTAIL_SQ_SELFHOST").ok().as_deref() != Some("0")
+}
+
 /// Schoolbook squarer with Bennett uncompute. For squaring `tmp_ext = x*x`
 /// (2n bits, no mod reduction), then ADD with Solinas reduction to acc,
 /// then uncompute tmp_ext via gate-level inverse.
@@ -6401,7 +6502,11 @@ fn squaring_sub_from_acc_karatsuba(b: &mut B, acc: &[QubitId], x: &[QubitId], p:
     {
         let slice: Vec<QubitId> = tmp_ext[2 * h..4 * h].to_vec();
         if z02_lowq {
-            schoolbook_square_symmetric_lowq(b, &x_hi, &slice);
+            if kara_z2_selfhost_enabled() {
+                schoolbook_square_symmetric_lowq_selfhosted(b, &x_hi, &slice);
+            } else {
+                schoolbook_square_symmetric_lowq(b, &x_hi, &slice);
+            }
         } else {
             schoolbook_square_symmetric(b, &x_hi, &slice);
         }
@@ -6586,7 +6691,11 @@ fn squaring_sub_from_acc_karatsuba(b: &mut B, acc: &[QubitId], x: &[QubitId], p:
     {
         let slice: Vec<QubitId> = tmp_ext[2 * h..4 * h].to_vec();
         if z02_lowq {
-            schoolbook_square_symmetric_lowq_inverse(b, &x_hi, &slice);
+            if kara_z2_selfhost_enabled() {
+                schoolbook_square_symmetric_lowq_selfhosted_inverse(b, &x_hi, &slice);
+            } else {
+                schoolbook_square_symmetric_lowq_inverse(b, &x_hi, &slice);
+            }
         } else {
             schoolbook_square_symmetric_inverse(b, &x_hi, &slice);
         }
@@ -6628,7 +6737,11 @@ fn squaring_sub_from_acc_schoolbook_lowq_shift22(
     let c = U256::MAX.wrapping_sub(p).wrapping_add(U256::from(1));
 
     let tmp_ext = b.alloc_qubits(2 * n);
-    schoolbook_square_symmetric_lowq(b, x, &tmp_ext);
+    if xtail_sq_selfhost_enabled() {
+        schoolbook_square_symmetric_lowq_selfhosted(b, x, &tmp_ext);
+    } else {
+        schoolbook_square_symmetric_lowq(b, x, &tmp_ext);
+    }
 
     let lo: Vec<QubitId> = tmp_ext[0..n].to_vec();
     let hi: Vec<QubitId> = tmp_ext[n..2 * n].to_vec();
@@ -6654,7 +6767,11 @@ fn squaring_sub_from_acc_schoolbook_lowq_shift22(
         mod_halve_inplace_direct_const_fast(b, &hi, p);
     }
 
-    schoolbook_square_symmetric_lowq_inverse(b, x, &tmp_ext);
+    if xtail_sq_selfhost_enabled() {
+        schoolbook_square_symmetric_lowq_selfhosted_inverse(b, x, &tmp_ext);
+    } else {
+        schoolbook_square_symmetric_lowq_inverse(b, x, &tmp_ext);
+    }
     b.free_vec(&tmp_ext);
 }
 
@@ -29923,7 +30040,7 @@ fn configure_ecdsafail_submission_route() {
     // low/mid-width GCD steps (below the 57 cap) for -452 executed Toffoli,
     // peak-neutral at 1434q, orthogonal to compare57. The late-game lineage ran
     // margin=5; the base had reverted to 7. Clean island at REROLL=1844/POST_SUB=3532.
-    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "5");
+    set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "7");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "20");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "20");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
@@ -29940,15 +30057,15 @@ fn configure_ecdsafail_submission_route() {
     // island documented below.
     // Branch comparator 58 -> 57: -1,064 executed Toffoli, peak-neutral at 1434q,
     // stacked on the active395 base. Clean island at REROLL=4959 / POST_SUB=5983.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "56");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "58");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     // 399 -> 396. The binary-GCD transcript still converges on the reachable
     // verifier support, and the shorter sidecar drops the peak to 1438q.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "395");
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "396");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -29989,7 +30106,7 @@ fn configure_ecdsafail_submission_route() {
     // PA9024_COMPARE_SCHEDULE_MARGIN 8->7: -5,576 executed Toffoli at the 1434
     // peak. Re-rolled Fiat-Shamir island lands clean (0/0/0 over 9024) at
     // DIALOG_REROLL=0 / DIALOG_POST_SUB_REROLL=44. 1434q x 1,733,573 T = 2,485,943,682.
-    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "25");
+    set_default_env("DIALOG_GCD_WIDTH_MARGIN", "26");
     // Measured (Gidney) uncompute for the apply-phase modular subtract's raw
     // difference, mirroring the already-measured apply ADD. ~n Toffoli instead
     // of ~2n per call; peak-neutral (same carry lane the ADD already uses).
@@ -30034,6 +30151,7 @@ fn configure_ecdsafail_submission_route() {
     // Global peak 1542 -> 1500; cost +~36,558 avg-executed Toffoli (1,682,159 ->
     // 1,718,717) for -42q: 1500 x 1,718,717 = 2,578,075,500.
     set_default_env("KARA_Z02_LOWQ", "1");
+    set_default_env("KARA_Z2_SELFHOST", "1");
     set_default_env("KARA_SOL_MOD_VENT", "1");
     // PEAK 1500 -> 1466 (-34q). On the 1500 floor the peak was a co-binder tie between
     // the GCD-core branch comparator (tobitvector_branch_bits / _reverse) and the apply
@@ -30079,8 +30197,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "130");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "643155");
-    set_default_env("DIALOG_POST_SUB_REROLL", "208158");
+    set_default_env("DIALOG_REROLL", "102");
+    set_default_env("DIALOG_POST_SUB_REROLL", "100");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

