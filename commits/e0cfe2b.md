# e0cfe2b — Remove the z2 square's carry-in, run its top carry in place, and park one more transcript block on dead high-u wires (1413 → 1411 qubits)

| | |
| --- | --- |
| Contestant | nikhiljha |
| Date | 2026-06-03 |
| Submission | `457d964` |
| Commit | `e0cfe2b738faa73cba1d6ac7ce8fb635be59711b` |
| Result | 1411 qubits × 1,724,981 Toffoli = **2,433,948,191** |
| Base | `24a4076` (git parent, the author's previous submission): 1413 qubits × 1,724,727 Toffoli = 2,437,039,251 |
| Change vs base | qubits −2, Toffoli +254, score −3,091,060 (leaderboard Δ −3,091,060) |
| Family | Register and Scratch Allocation → scratch/ancilla reuse |
| Concepts | [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This continues [`24a4076`](24a4076.md). After that commit, the peak of 1413
was shared by the Karatsuba `z2 = hi²` square in the x-tail and by the dialog
GCD's terminal phases. This commit lowers both.

- **Square.** Each row add of the `z2` square loses its fresh carry-in qubit,
  which is always 0. Its topmost carry is computed in place with a plain
  MAJ/UMA pair instead of on a borrowed carry wire. That is two fewer
  transient qubits, for one extra Toffoli per row.
- **Dialog.** One more 5-qubit block of the compressed GCD transcript is
  parked on high `u` wires that are provably zero by then, instead of being
  allocated.

The peak drops from 1413 to 1411. The cost is exactly +254 Toffoli: 127 rows,
forward and inverse.

## What changed and why it saves qubits

All changes are in `src/point_add/mod.rs`.

1. **New adders `cuccaro_add_fast_low_to_ext_borrowed_carries_no_cin` and
   `cuccaro_sub_fast_low_to_ext_borrowed_carries_no_cin`.**
   - These are the [`24a4076`](24a4076.md) low-to-extended adders
     specialised to a zero carry-in. With `c_in = 0`, its only job was to hold
     a copy of `a[0]` until the carry erase. After the erase `a[0]` holds the
     same value, so the first carry is `ccx(a[0], acc_ext[0], carries[0])`.
     The final phase fix-up `cz_if(a[0], acc_ext[0], m0)` is controlled on
     `a[0]` directly.
   - They are used in
     `schoolbook_square_symmetric_lowq_selfhosted_with_clean_supplement` (and
     its inverse) on the `SQUARE_SELFHOST_SAFE_LANE_REUSE` path, which is the
     `z2 = hi²` square. The `let c_in = b.alloc_qubit()` per row is gone, which
     saves 1 transient qubit.
2. **New knob `SQUARE_SELFHOST_GATE_SUFFIX_CARRIES`, set to `1`.**
   - `square_selfhost_gate_suffix_carries(n)` returns `min(knob, n − 1)`. The
     top that-many carry positions of each row add use the in-place Cuccaro
     `maj`/`uma` gates. Each of those positions costs two CCX, one forward and
     one back, and needs no carry wire.
   - The other positions keep the measured carry: one CCX forward, and an
     `hmr` plus `cz_if` erase with no Toffoli.
   - The row needs one fewer borrowed carry lane
     (`need = row.len() − suffix`), which saves 1 more transient qubit.
   - The cost is +1 Toffoli per row whose width is at least 2. That is 127 of
     the 128 rows, in the forward and inverse square, so 127 × 2 = 254. This
     matches the measured +254 exactly. See
     [adders-and-carries](../concepts/adders-and-carries.md) for the
     one-Toffoli measured carry against the two-Toffoli in-place carry.
3. **`DIALOG_GCD_COMPRESSED_LOG_U_HIGH_RUNWAY_BLOCKS`: 3 → 4.**
   - The GCD forward pass records 2 branch bits per step. Every 3 steps the
     6 raw bits are compressed into a 5-qubit block of the `compressed_log`
     sidecar.
   - Under `DIALOG_GCD_COMPRESSED_LOG_U_HIGH_RUNWAY=1`,
     `dialog_gcd_runway_layout()` takes the last K blocks and places them on
     high wires of `u` (from index 249 downward) instead of allocating them.
     Those blocks are written only once the width envelope
     `dialog_gcd_tobitvector_active_width(step)` has shrunk below those
     wires, so the wires are |0⟩ and unused. The reverse pass consumes the
     blocks before `u` grows back into them.
   - `dialog_gcd_allocated_compressed_sidecar_bits()` therefore allocates
     5 fewer qubits per extra block. Going from 3 to 4 blocks takes 5 more
     qubits off the dialog phases. This uses the general wire-loan idea in
     [venting-and-wire-loans](../concepts/venting-and-wire-loans.md).
4. **Reroll counts:** `DIALOG_REROLL` 109 → 67 and `DIALOG_POST_SUB_REROLL`
   100 → 101. These are the counts of identity `X;X` pairs emitted before and
   after the input subtraction. They only re-seed the Fiat–Shamir test set.

## Why it is still correct, and what it risks

- **The square changes are exact.** A zero carry-in can be dropped from a
  ripple adder, and the in-place MAJ/UMA carry is the textbook exact carry.
- **The runway is not a new risk.** It relies on the same premise as the
  existing width truncation: when the envelope says `u` is narrower than a
  host index, `u`'s bit there is 0. An input that breaks this already fails
  the width truncation. If it ever did happen, the parked transcript cell
  would hold data that is not |0⟩, and the run would show classical or
  ancilla failures.
- The author reports 0 classical, 0 phase and 0 ancilla failures over all
  9,024 shots at `DIALOG_REROLL=67`, `DIALOG_POST_SUB_REROLL=101`. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Both qubit savings put work on wires that already exist: zero transcript
cells move onto dead `u` lanes, and a carry moves into the operands
themselves. The always-zero carry-in is dropped. That is scratch/ancilla
reuse. The +254 Toffoli is the price of the in-place carry, not a separate
lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 24a4076 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 24a4076 e0cfe2b -- src/point_add` is
   128 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol e0cfe2b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `SQUARE_*`, `KARA_*` or `KAL_*` environment variables set.
   Expect:
   - 1411 qubits
   - 1,724,981 average Toffoli (rounded)
   - score 2,433,948,191
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL=67`, `DIALOG_POST_SUB_REROLL=101`
and an identical op stream. Any other change needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 1a10660..964742d 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1885,6 +1885,107 @@ fn cuccaro_sub_fast_low_to_ext_borrowed_carries(
     b.cx(a[0], acc_ext[0]);
 }
 
+/// Zero-carry-in specialization of
+/// [`cuccaro_add_fast_low_to_ext_borrowed_carries`].  The omitted `c_in`
+/// register is known zero: its only forward role is to preserve the original
+/// low source bit until the measured carry clear.  After that clear `a[0]`
+/// holds the same value, so it can control the phase correction directly.
+fn cuccaro_add_fast_low_to_ext_borrowed_carries_no_cin(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    carries: &[QubitId],
+) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    if n == 0 {
+        return;
+    }
+    let gate_suffix = square_selfhost_gate_suffix_carries(n);
+    let borrowed = n - gate_suffix;
+    assert!(carries.len() >= borrowed);
+
+    b.cx(a[0], acc_ext[0]);
+    b.ccx(a[0], acc_ext[0], carries[0]);
+    b.cx(carries[0], a[0]);
+    for i in 1..borrowed {
+        b.cx(a[i], acc_ext[i]);
+        b.cx(a[i], a[i - 1]);
+        b.ccx(a[i - 1], acc_ext[i], carries[i]);
+        b.cx(carries[i], a[i]);
+    }
+    for i in borrowed..n {
+        maj(b, a[i - 1], acc_ext[i], a[i]);
+    }
+
+    b.cx(a[n - 1], acc_ext[n]);
+
+    for i in (borrowed..n).rev() {
+        uma(b, a[i - 1], acc_ext[i], a[i]);
+    }
+    for i in (1..borrowed).rev() {
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
+    b.cz_if(a[0], acc_ext[0], m0);
+}
+
+/// Zero-carry-in inverse of
+/// [`cuccaro_add_fast_low_to_ext_borrowed_carries_no_cin`].
+fn cuccaro_sub_fast_low_to_ext_borrowed_carries_no_cin(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    carries: &[QubitId],
+) {
+    let n = a.len();
+    assert_eq!(acc_ext.len(), n + 1);
+    if n == 0 {
+        return;
+    }
+    let gate_suffix = square_selfhost_gate_suffix_carries(n);
+    let borrowed = n - gate_suffix;
+    assert!(carries.len() >= borrowed);
+
+    b.ccx(a[0], acc_ext[0], carries[0]);
+    b.cx(carries[0], a[0]);
+    for i in 1..borrowed {
+        b.cx(a[i - 1], acc_ext[i]);
+        b.cx(a[i], a[i - 1]);
+        b.ccx(a[i - 1], acc_ext[i], carries[i]);
+        b.cx(carries[i], a[i]);
+    }
+    for i in borrowed..n {
+        inv_uma(b, a[i - 1], acc_ext[i], a[i]);
+    }
+
+    b.cx(a[n - 1], acc_ext[n]);
+
+    for i in (borrowed..n).rev() {
+        inv_maj(b, a[i - 1], acc_ext[i], a[i]);
+    }
+    for i in (1..borrowed).rev() {
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
+    b.cz_if(a[0], acc_ext[0], m0);
+    b.cx(a[0], acc_ext[0]);
+}
+
 /// Windowed measured add: `acc += a + c_in (mod 2^n)`, reusing the proven
 /// `cuccaro_add_fast` block-wise but threading the inter-block carry through a
 /// 1-bit register extension. Only ~n/blocks measured-carry ancillae are live at
@@ -6203,6 +6304,14 @@ fn assert_qubit_slices_disjoint(slices: &[&[QubitId]]) {
     }
 }
 
+fn square_selfhost_gate_suffix_carries(n: usize) -> usize {
+    std::env::var("SQUARE_SELFHOST_GATE_SUFFIX_CARRIES")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(0)
+        .min(n.saturating_sub(1))
+}
+
 /// Like `schoolbook_square_symmetric_lowq` but converts the per-row Cuccaro
 /// UMA-uncompute (CCX, executed every shot) into measurement-based (fast)
 /// uncompute, WITHOUT a separate clean host register. The fast carry lane is
@@ -6256,8 +6365,7 @@ fn schoolbook_square_symmetric_lowq_selfhosted_with_clean_supplement(
             b.free(c_in);
             b.free(pad);
         } else if safe_reuse {
-            let c_in = b.alloc_qubit();
-            let need = row.len();
+            let need = row.len() - square_selfhost_gate_suffix_carries(row.len());
             let avail = tmp_ext.len() - hi;
             let from_tmp = need.min(avail);
             let from_supplement = (need - from_tmp).min(clean_supplement.len());
@@ -6266,8 +6374,7 @@ fn schoolbook_square_symmetric_lowq_selfhosted_with_clean_supplement(
             let mut carries: Vec<QubitId> = tmp_ext[hi..hi + from_tmp].to_vec();
             carries.extend_from_slice(&clean_supplement[..from_supplement]);
             carries.extend_from_slice(&gpool);
-            cuccaro_add_fast_low_to_ext_borrowed_carries(b, &row, &slice, c_in, &carries);
-            b.free(c_in);
+            cuccaro_add_fast_low_to_ext_borrowed_carries_no_cin(b, &row, &slice, &carries);
             b.free_vec(&gpool);
         } else {
             let pad = b.alloc_qubit();
@@ -6335,8 +6442,7 @@ fn schoolbook_square_symmetric_lowq_selfhosted_inverse_with_clean_supplement(
             b.free(c_in);
             b.free(pad);
         } else if safe_reuse {
-            let c_in = b.alloc_qubit();
-            let need = row.len();
+            let need = row.len() - square_selfhost_gate_suffix_carries(row.len());
             let avail = tmp_ext.len() - hi;
             let from_tmp = need.min(avail);
             let from_supplement = (need - from_tmp).min(clean_supplement.len());
@@ -6345,8 +6451,7 @@ fn schoolbook_square_symmetric_lowq_selfhosted_inverse_with_clean_supplement(
             let mut carries: Vec<QubitId> = tmp_ext[hi..hi + from_tmp].to_vec();
             carries.extend_from_slice(&clean_supplement[..from_supplement]);
             carries.extend_from_slice(&gpool);
-            cuccaro_sub_fast_low_to_ext_borrowed_carries(b, &row, &slice, c_in, &carries);
-            b.free(c_in);
+            cuccaro_sub_fast_low_to_ext_borrowed_carries_no_cin(b, &row, &slice, &carries);
             b.free_vec(&gpool);
         } else {
             let pad = b.alloc_qubit();
@@ -30845,9 +30950,10 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_HOST_REVERSE_RAW_BLOCK", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_LOG_U_HIGH_RUNWAY", "1");
-    set_default_env("DIALOG_GCD_COMPRESSED_LOG_U_HIGH_RUNWAY_BLOCKS", "3");
+    set_default_env("DIALOG_GCD_COMPRESSED_LOG_U_HIGH_RUNWAY_BLOCKS", "4");
     set_default_env("DIALOG_GCD_APPLY_REPLAY_SWAP_HOST", "1");
     set_default_env("SQUARE_SELFHOST_SAFE_LANE_REUSE", "1");
+    set_default_env("SQUARE_SELFHOST_GATE_SUFFIX_CARRIES", "1");
     set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE", "1");
     // PA9024 compare-schedule margin retuned with ACTIVE_ITERATIONS=396 and
     // APPLY_CLEAN_COMPARE_BITS=21. The wider margin gives back a little Toffoli
@@ -31013,8 +31119,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "140");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "109");
-    set_default_env("DIALOG_POST_SUB_REROLL", "100");
+    set_default_env("DIALOG_REROLL", "67");
+    set_default_env("DIALOG_POST_SUB_REROLL", "101");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

