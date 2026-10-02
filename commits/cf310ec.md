# cf310ec — Store the first K5 transcript block in 11 qubits, drop the apply chunks' zero pad, park more fold carries, and lower the square row cap 165 → 158 (1192 → 1185 qubits)

| | |
| --- | --- |
| Contestant | nasqret (model: GPT-5, with Codex) |
| Date | 2026-06-13 |
| Submission | `3182d2b` |
| Commit | `cf310ecb9a0bb938bb961fcd18019e891c5b7d12` |
| Result | 1185 qubits × 1,418,587 Toffoli = **1,681,025,595** |
| Base | `6953d1b` (BitWonka), **not** the git parent: 1203 qubits × 1,410,971 Toffoli = 1,697,398,113 |
| Change vs base | qubits −18, Toffoli +7,616, score −16,372,518. Against the git parent `cf99209` (1192 × 1,411,983), whose levers this commit keeps: qubits −7, Toffoli +6,604, score −2,058,141 |
| Leaderboard Δ | −2,058,141, measured against the frontier at the time, `cf99209`, which is **not** this commit's base |
| Family | Codec / Encoding → trailmix / K5 codec |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **B**: three large hand-written files are copied from the commit; the patch covers the other four |

## Summary

This commit takes the circuit of its git parent [`cf99209`](cf99209.md),
1192 qubits, and lowers every phase that sat near the peak by a few qubits.
The final peak is 1185.

- **Head codec.** The first 5-step K5 transcript block is stored in 11 qubits
  instead of 12. The first five GCD steps start from the fixed `u = p`, so
  only 2,048 transcript patterns occur there.
- **Implicit high zero.** The apply's chunked controlled add no longer
  allocates an explicit zero wire on top of each chunk's source.
- **More fold carries parked.** The fused `double_y` / `halve_y` fold now
  parks 7 low carries instead of 1, and the special modular-add fold parks 5.
  Each parked carry is erased by measurement and recomputed later.
- **Co-binder knobs.** The square row cap goes from 165 to 158, and the apply
  ripple uses 18 chunks instead of 16.

The extra recomputes and square cleanups cost +6,604 Toffoli against the
parent. Seven qubits at about 1,190 Toffoli each is worth more, so the score
improves by 2.06 M.

Most of the 7,221-line diff is not in the shipped circuit. It consists of
default-off codec experiments, an extended classical prefilter for the nonce
hunt, and self-tests.

## What changed and why it saves qubits

**How the configuration is set.** `configure_ecdsafail_submission_route()`
in `src/point_add/mod.rs` now ends with a block of `std::env::set_var` (and
one `remove_var`) calls.
- Unlike `set_default_env`, these *override* the environment. So the built
  circuit no longer depends on the shell.
- The block repeats the parent's effective settings. That includes the
  `cf99209` square row map, `DIALOG_GCD_K5_FREE_CLEAN_BLOCK_DURING_SHIFT=1`
  from [`bb579bb`](bb579bb.md), and `DIALOG_GCD_FOLD_CARRY_TRUNC_W=18`.
- Some earlier `set_default_env` lines in the file still carry older
  `6953d1b` values, for example `SQUARE_ROW_MAX_SEG` 176. Those lines are dead,
  because the block at the end overrides them.

Compared with the parent's effective configuration, the shipped knobs that
change are:

| Knob | `cf99209` | `cf310ec` |
| --- | --- | --- |
| `DIALOG_GCD_K5_HEAD11_CODEC` | unset | 1 |
| `DIALOG_GCD_APPLY_IMPLICIT_HIGH_ZERO` | unset | 1 |
| `DIALOG_GCD_FOLD_PARK_LOW_CARRIES` | 1 | 7 |
| `DIALOG_GCD_SPECIAL_FOLD_PARK_LOW_CARRIES` | unset | 5 |
| `DIALOG_GCD_SPECIAL_FOLD_RELEASE_SCRATCH` | unset | 1 |
| `DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS` | 16 | 18 |
| `DIALOG_GCD_APPLY_BORROW_FUTURE_BOUNDARY_CARRIES` | unset | 0 (new knob, off) |
| `SQUARE_ROW_MAX_SEG` | 165 | 158 |
| `DIALOG_TAIL_NONCE` | 11556565 | 3452376 |

**1. Head-11 codec (`rounds/dialog/compressed.rs`, `DIALOG_GCD_K5_HEAD11_CODEC=1`).**
- `dialog_gcd_compressed_sidecar_block_bits(0)` becomes 11. The block offsets
  are now computed per block (`dialog_gcd_compressed_sidecar_block_offset`),
  so the whole transcript register is one qubit shorter for its entire
  lifetime.
- `dialog_gcd_k5_head11_compress_raw_to_block` runs:
  1. The two 3-CCX pair encoders, as in the K5 codec of
     [`6953d1b`](6953d1b.md).
  2. A new 2-CCX "preconditioner" on the 13 data wires:
     `x(d0); ccx(d0,d1,d3); ccx(d2,d3,d0); cx(d0,d3)`.
  3. The 17-CCX Fable codec.
  4. A swap of 11 survivors (`DIALOG_GCD_K5_HEAD11_DATA_WIRES`, which skips
     data wires 3 and 10) into the block.
- On the supported patterns, the preconditioner leaves data wire 3 at 0. The
  Fable codec already zeroes wire 10.
- `dialog_gcd_k5_head11_decompress_block_to_raw` is the exact reverse.
- Both dispatch sites (walk compress and decompress, apply copy and clear) use
  these for block 0.
- In the forward and reverse apply of block 0, `raw_block[1]` (step 0's
  `b0_and_b1`) is freed after the decode, and step 0's swap control reads
  `raw[0]` (step 0's `b0`) instead. The wire is reacquired before the
  re-encode. The code treats the two bits as equal on the head support, which
  removes one more wire during that block's apply.
- `dialog_gcd_k5_head11_codec_selftest`, run with
  `DIALOG_GCD_K5_HEAD11_SELFTEST=1`, checks three things: that exactly 2^11
  patterns are supported, that the codes are distinct, and that the circuit is
  reversible and phase-clean on them.

**2. Implicit high zero (`rounds/dialog/mod.rs` and `config.rs`,
`DIALOG_GCD_APPLY_IMPLICIT_HIGH_ZERO=1`).**
- `dialog_gcd_add_ctrl_chunked_low_to_ext` and its `sub` twin used to add
  `f ‖ 0` into `acc[lo..hi] ‖ cout` with `cuccaro_add_fast`. Here `f` is the
  chunk of `ctrl & a`. The top source bit was a borrowed wire held at |0⟩,
  the "zero host".
- They now call `cuccaro_{add,sub}_fast_low_to_ext_borrowed_carries`, through
  the new `dialog_gcd_{add,sub}_fast_low_to_ext_with_borrowed_carries`. That
  primitive treats the missing top source bit as a constant 0.
- No zero host is reserved. That frees one more `clean_scratch` cell for
  boundary carries, and removes one wire from each chunk's live set.
- The same files add an optional explicit cut list,
  `DIALOG_GCD_APPLY_CHUNKED_F_CUTS` (removed, so unused here), and
  `…_BORROW_FUTURE_BOUNDARY_CARRIES` (set to 0, off).

**3. Fold carry parking (`arith/const_arith.rs`).**
- **Fused fold** (`fold_ripple_freed_tail_ed`, used by `double_y` /
  `halve_y`). `DIALOG_GCD_FOLD_PARK_LOW_CARRIES` goes from 1 to 7. This is the
  same mechanism as [`cf3c6f1`](cf3c6f1.md), applied to carries 0 to 6
  instead of carry 0 only.
  - Before the wide tail is allocated, the code erases those carries with
    `hmr` plus a post-sum phase fix. After the tail, it recomputes them with
    `fold_postsum_carry_compute`.
  - That removes 6 more wires from the fused fold's high-water.
  - The recompute costs 1 to 3 CCX per parked position, 15 CCX in all for
    positions 0 to 6 against 1 before. It runs on every double and halve.
- **Special fold** (the `acc[..73] ± c` overflow correction of each apply
  add/sub). The new `cconst_nbit_direct_trunc_fast_parked` splits the carry
  lane at `split = last − P`, with `P = DIALOG_GCD_SPECIAL_FOLD_PARK_LOW_CARRIES = 5`.
  1. It computes and sums the prefix.
  2. It erases the lowest `P` prefix carries (`hmr` plus phase fix).
  3. It allocates only `P` tail carries and runs the tail.
  4. It uncomputes the tail, recomputes the parked carries, and uncomputes
     the prefix.
  - The live carry count at the tail is `last + 1 − P`, so 5 wires fewer.
- **Release scratch.** With `DIALOG_GCD_SPECIAL_FOLD_RELEASE_SCRATCH=1`,
  `cadd/csub_nbit_const_direct_trunc_fast_releasing_scratch` frees the whole
  `clean_scratch` before the parked fold and reacquires it after.
  - `clean_scratch` here is the emptied K5 block cells plus the chunk carry-in.
  - Freeing them lets the fold allocate those ids instead of fresh ones.
  - The code asserts `DIALOG_GCD_K2_APPLY_INPLACE_RAW_BLOCK=1` as a guard. That
    knob is set, but it is otherwise inert under K5.
  - The borrowed-carry path now also includes the chunk carry-in wire
    (`clean_scratch` rather than `inner_scratch`).
- Self-test: `SPECIAL_FOLD_PARK_SELFTEST=1`.

**4. Square row cap and apply chunks.**
- `SQUARE_ROW_MAX_SEG` 165 → 158: rows of width 159 to 165 (`i = 92..98`) are
  now windowed. That drops the square's largest transient row by 7 bits and
  adds 14 measured boundary cleanups. The cleanup default stays 19 bits with
  the `cf99209` row map.
- `square_row_window_clean_compare_bits` gains `(row, window, reverse)`
  arguments and an optional per-site map, `SQUARE_ROW_WINDOW_CLEAN_SITE_BITS`.
  That map is not set here.
- `DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS` 16 → 18: the apply chunks become about
  14 bits wide instead of 16.

**Not active in the shipped build** (all default-off, or used only by tools):
- K5 tail codecs: `…_TAIL7…`, `…_TAIL6_GRAPH…`, `…_TAIL6_GRAPH9…`,
  `…_TAIL_PAIR1…`, and a fixed-tail apply.
- Fold control hosting and streaming: `DIALOG_GCD_FOLD_HOST_*`,
  `fold_ripple_freed_tail_ed_streamed` and `_hosted`.
- Per-step fold-window maps: `DIALOG_GCD_FOLD_CARRY_TRUNC_STEP_WINDOWS` and
  `DIALOG_GCD_SPECIAL_FOLD_CARRY_TRUNC_STEP_WINDOWS`. The next commit,
  [`674d0d8`](674d0d8.md), switches several of these on.
- About 1,500 new lines in `dialog_gcd_classical_filter.rs`. This is the
  classical prefilter used by the nonce hunt, not by `build()`. It now
  replays the apply (fused double/halve, special add/sub carry escapes, compare
  suffix requirements), the square row-window cleanup sites and the head-11
  support, so that a candidate nonce can be screened for these hazards.
- Self-tests in `build()`, gated by `*_SELFTEST` variables.

**Cost.** The +6,604 Toffoli comes mainly from the fused-fold recompute
(about +14 CCX per double/halve), the special-fold recompute (a few CCX per
apply add/sub), the 14 new square cleanups (about 30 each) and two more
apply chunk boundaries. I did not measure each part.

## Why it is still correct, and what it risks

- **Exact parts.**
  - Carry parking, in both folds: each parked carry is a fixed function of
    post-sum bits and controls, which the tail does not touch.
  - The implicit zero: the constant-0 source bit is handled by the
    low-to-ext primitive.
  - Releasing and reacquiring |0⟩ scratch.
  - The square cap, which is value-exact.
- **The head-11 codec is exact only on its 2,048 supported patterns.** The
  author says exhaustive enumeration shows these are exactly the reachable
  first-block transcripts. The classical filter also rejects any input whose
  first five steps fall outside them (`HardReason::HeadK5Mismatch`). An
  unsupported pattern would leave data wire 3 nonzero. That gives a dirty
  wire (ancilla) or a wrong transcript (classical).
- **Probabilistic parts** are the same classes as the parent. The 14 new
  square cleanups use truncated compares, where a tie gives a phase failure.
  The fold windows are unchanged.
- The shipped nonce `3452376` draws a clean set: 9,024 shots, 0 classical,
  0 phase and 0 ancilla failures. The author found it with a CUDA search,
  confirmed it with an independent Rust replay, and then ran the stock
  evaluator. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this under the K5 codec, because of the head-11 block. That
saves one qubit. The other six come from lifetime cuts (carry parking,
releasing scratch, dropping the zero pad) and the square cap. So
**Register and Scratch Allocation → ancilla-lifetime / venting** describes
most of the qubit saving better. The codec is a real but minor part. The
header keeps the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6953d1b -- src/point_add`.
   - The base is `6953d1b` because its `src/point_add` is textually closest:
     7,221 diff lines against 7,602 for the git parent `cf99209`.
   - Against the parent, the diff would also delete
     [`bb579bb`](bb579bb.md)'s inert K5 in-place, stream and recompress
     variants, which are not in this tree.
   - It would also appear to revert several `set_default_env` lines to their
     `6953d1b` values. Those reverts have no effect, because the `set_var`
     block at the end of `configure_ecdsafail_submission_route()` overrides
     them. That block keeps the parent's levers.
2. **Copy three large hand-written files from the commit:**
   `git checkout cf310ec -- src/point_add/arith/const_arith.rs src/point_add/rounds/dialog/compressed.rs src/point_add/dialog_gcd_classical_filter.rs`.
   - `const_arith.rs` (+2,465 / −95 lines) holds the parked special fold, the
     release-scratch wrappers, and the parked, hosted and streamed fused-fold
     variants.
   - `compressed.rs` (+2,137 / −229) holds the head-11 codec,
     per-block offsets, the inert tail codecs, and the shift-phase block
     release.
   - `dialog_gcd_classical_filter.rs` (+1,469 / −61) is the extended hunt
     prefilter.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   It covers `mod.rs`, `rounds/dialog/mod.rs`, `rounds/dialog/config.rs` and
   `arith/multiply.rs`. The flag lets the patch apply whether the files use
   LF or CRLF line endings.
4. **Check the tree.** `git diff --ignore-cr-at-eol cf310ec -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. The route's
   knobs are forced by `set_var`, so shell variables of the same names have no
   effect. Expect:
   - 1185 qubits
   - 1,418,587 average Toffoli (rounded; 1,418,586.774 in the submission note)
   - score 1,681,025,595
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `3452376` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/multiply.rs b/src/point_add/arith/multiply.rs
index aaa8f50..8e147fc 100644
--- a/src/point_add/arith/multiply.rs
+++ b/src/point_add/arith/multiply.rs
@@ -609,11 +609,60 @@ fn square_row_max_seg() -> usize {
 /// compares only the high suffix of the segment and final partial sum.  This is
 /// a deliberate island-hunt knob: it keeps the same low peak and saves Toffoli,
 /// but wrong suffix ties leave the boundary carry dirty.
-fn square_row_window_clean_compare_bits() -> usize {
-    std::env::var("SQUARE_ROW_WINDOW_CLEAN_COMPARE_BITS")
+fn square_cleanup_direction(raw: &str) -> Option<bool> {
+    match raw.trim().to_ascii_lowercase().as_str() {
+        "f" | "forward" | "false" | "0" => Some(false),
+        "r" | "reverse" | "true" | "1" => Some(true),
+        _ => None,
+    }
+}
+
+fn square_row_window_clean_compare_bits(
+    row: usize,
+    window: usize,
+    reverse: bool,
+) -> usize {
+    let default_bits = std::env::var("SQUARE_ROW_WINDOW_CLEAN_COMPARE_BITS")
         .ok()
         .and_then(|s| s.parse::<usize>().ok())
-        .unwrap_or(0)
+        .unwrap_or(0);
+    let row_bits = std::env::var("SQUARE_ROW_WINDOW_CLEAN_ROW_BITS")
+        .ok()
+        .and_then(|spec| {
+            spec.split(',').rev().find_map(|item| {
+                let (raw_row, raw_bits) = item.trim().split_once(':')?;
+                if raw_row.trim().parse::<usize>().ok()? != row {
+                    return None;
+                }
+                raw_bits
+                    .trim()
+                    .parse::<usize>()
+                    .ok()
+                    .filter(|bits| (1..=N).contains(bits))
+            })
+        })
+        .unwrap_or(default_bits);
+    let Ok(spec) = std::env::var("SQUARE_ROW_WINDOW_CLEAN_SITE_BITS") else {
+        return row_bits;
+    };
+    for item in spec.split(',').rev() {
+        let fields: Vec<_> = item.trim().split(':').map(str::trim).collect();
+        if fields.len() != 4 {
+            continue;
+        }
+        if fields[0].parse::<usize>().ok() != Some(row)
+            || fields[1].parse::<usize>().ok() != Some(window)
+            || square_cleanup_direction(fields[2]) != Some(reverse)
+        {
+            continue;
+        }
+        if let Ok(bits) = fields[3].parse::<usize>() {
+            if (1..=N).contains(&bits) {
+                return bits;
+            }
+        }
+    }
+    row_bits
 }
 
 fn square_row_window_measured_carry_clear_enabled() -> bool {
@@ -731,7 +780,7 @@ fn square_row_windowed_apply(
     // carry/borrow-in for window 0 is a clean zero.
     let mut carry_in = b.alloc_qubit();
     let first_carry = carry_in;
-    let mut couts: Vec<(QubitId, usize, usize, QubitId)> = Vec::new();
+    let mut couts: Vec<(QubitId, usize, usize, QubitId, usize)> = Vec::new();
     for (wi, &(lo, hi)) in bounds.iter().enumerate() {
         let last = wi == nwin - 1;
         let seg = build_seg(b, lo, hi);
@@ -759,7 +808,7 @@ fn square_row_windowed_apply(
         if last {
             // nothing extra: carry already in tmp_ext[base+width].
         } else {
-            couts.push((high, lo, hi, carry_in));
+            couts.push((high, lo, hi, carry_in, wi));
             carry_in = high;
         }
         clear_seg(b, lo, &seg);
@@ -770,9 +819,10 @@ fn square_row_windowed_apply(
     // SQUARE_ROW_WINDOW_SLOW_CMP=1 falls back to the carry-array-free slow
     // comparator (~2n CCX, also peak-flat) for cross-checking.
     let slow_cmp = std::env::var("SQUARE_ROW_WINDOW_SLOW_CMP").ok().as_deref() == Some("1");
-    let clean_cmp_bits = square_row_window_clean_compare_bits();
     let measured_clear = square_row_window_measured_carry_clear_enabled();
-    for &(cout, lo, hi, cin) in couts.iter().rev() {
+    for &(cout, lo, hi, cin, window) in couts.iter().rev() {
+        let clean_cmp_bits =
+            square_row_window_clean_compare_bits(i, window, !forward);
         let seg_w = hi - lo;
         let trunc_w = if clean_cmp_bits == 0 {
             seg_w
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 1cd1ca2..e90b93d 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1485,6 +1485,65 @@ fn configure_ecdsafail_submission_route() {
     // to a CX, and the lane-0 tobitvector add/sub body has no carry/borrow into
     // lane 1, so the body can start at bit 1. Co-tuned with the reroll island.
     set_default_env("DIALOG_GCD_ODD_U_LOWBIT_FASTPATH", "1");
+
+    // q1185 head11/implicit-zero record candidate. These assignments make the
+    // submitted circuit independent of the optimizer shell environment.
+    std::env::set_var("DIALOG_GCD_ACTIVE_ITERATIONS", "258");
+    std::env::set_var("DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS", "18");
+    std::env::remove_var("DIALOG_GCD_APPLY_CHUNKED_F_CUTS");
+    std::env::set_var("DIALOG_GCD_APPLY_BORROW_FUTURE_BOUNDARY_CARRIES", "0");
+    std::env::set_var("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
+    std::env::set_var("DIALOG_GCD_APPLY_IMPLICIT_HIGH_ZERO", "1");
+    std::env::set_var("DIALOG_GCD_BINDER_NOTCH_EXTRA", "3");
+    std::env::set_var("DIALOG_GCD_BINDER_NOTCH_MAP", "11:1,12:1,13:1");
+    std::env::set_var("DIALOG_GCD_BINDER_NOTCH_STEPS", "8,9,10");
+    std::env::set_var(
+        "DIALOG_GCD_BODY_CARRY_BAND_TRIMS",
+        "0,3,3,3,3,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,3,3",
+    );
+    std::env::set_var("DIALOG_GCD_COMPARE_BITS", "46");
+    std::env::set_var("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "18");
+    std::env::set_var("DIALOG_GCD_FOLD_FREED_TAIL", "1");
+    std::env::set_var("DIALOG_GCD_FOLD_FREED_TAIL_ED", "1");
+    std::env::set_var("DIALOG_GCD_FOLD_MAJ1", "1");
+    std::env::set_var("DIALOG_GCD_FOLD_MAJ2", "1");
+    std::env::set_var("DIALOG_GCD_FOLD_PARK_LOW_CARRIES", "7");
+    std::env::set_var("DIALOG_GCD_K2", "1");
+    std::env::set_var("DIALOG_GCD_K5_CLEAN_BLOCK", "1");
+    std::env::set_var("DIALOG_GCD_K5_HEAD11_CODEC", "1");
+    std::env::set_var("DIALOG_GCD_K5_FREE_CLEAN_BLOCK_DURING_SHIFT", "1");
+    std::env::set_var("DIALOG_GCD_ODD_U_LOWBIT_FASTPATH", "1");
+    std::env::set_var("DIALOG_GCD_PA9024_COMPARE_SCHEDULE", "1");
+    std::env::set_var("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "0");
+    std::env::set_var("DIALOG_GCD_PERPOS_MAJ2", "1");
+    std::env::set_var("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
+    std::env::set_var("DIALOG_GCD_RAW_TOBITVECTOR_MATERIALIZED_SUB", "0");
+    std::env::set_var("DIALOG_GCD_RAW_TOBITVECTOR_VARIABLE_WIDTH", "1");
+    std::env::set_var("DIALOG_GCD_SKIP_ZERO_EDGE_CSHIFT", "1");
+    std::env::set_var("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES", "1");
+    std::env::set_var("DIALOG_GCD_SPECIAL_FOLD_PARK_LOW_CARRIES", "5");
+    std::env::set_var("DIALOG_GCD_SPECIAL_FOLD_RELEASE_SCRATCH", "1");
+    std::env::set_var(
+        "DIALOG_GCD_SPECIAL_OVERFLOW_CLEAN_STEP_BITS",
+        "113:21,131:21,142:22,187:23,205:22,210:21",
+    );
+    std::env::set_var(
+        "DIALOG_GCD_SPECIAL_UNDERFLOW_CLEAN_STEP_BITS",
+        "42:22,91:22,118:22,149:21",
+    );
+    std::env::set_var("DIALOG_GCD_TOBITVECTOR_CSWAP_BODY_TRIM", "0");
+    std::env::set_var("DIALOG_GCD_WIDTH_MARGIN", "10");
+    std::env::set_var("DIALOG_GCD_WIDTH_SLOPE_X1000", "1015");
+    std::env::set_var("KAL_DOUBLE_CARRY_TRUNC_W", "19");
+    std::env::set_var("KAL_FOLD_CARRY_TRUNC_W", "18");
+    std::env::set_var("SQUARE_ROW_MAX_SEG", "158");
+    std::env::set_var("SQUARE_ROW_WINDOW_CLEAN_COMPARE_BITS", "19");
+    std::env::set_var(
+        "SQUARE_ROW_WINDOW_CLEAN_ROW_BITS",
+        "2:20,11:20,12:20,13:21,16:22,19:20,20:21,21:20,26:21,29:21,32:21,37:21,44:22,46:20,53:21,56:20,64:20,70:20,75:20,78:20,87:20",
+    );
+    std::env::set_var("SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR", "1");
+    std::env::set_var("DIALOG_TAIL_NONCE", "3452376");
 }
 
 pub fn build_builder() -> B {
@@ -1693,6 +1752,81 @@ pub fn build_builder() -> B {
 }
 
 pub fn build() -> Vec<Op> {
+    if std::env::var("DIALOG_GCD_K5_HEAD11_SELFTEST").is_ok() {
+        match dialog_gcd_k5_head11_codec_selftest() {
+            Ok(()) => eprintln!(
+                "DIALOG_GCD_K5_HEAD11_SELFTEST: PASS (2048-word head codec reversible and phase clean)"
+            ),
+            Err(e) => panic!("DIALOG_GCD_K5_HEAD11_SELFTEST: FAIL: {e}"),
+        }
+        if std::env::var("DIALOG_GCD_K5_HEAD11_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
+    }
+    if std::env::var("DIALOG_GCD_K5_TAIL6_GRAPH9_SELFTEST").is_ok() {
+        match dialog_gcd_k5_tail6_graph9_codec_selftest() {
+            Ok(()) => eprintln!(
+                "DIALOG_GCD_K5_TAIL6_GRAPH9_SELFTEST: PASS (75-word graph codec reversible and phase clean)"
+            ),
+            Err(e) => panic!("DIALOG_GCD_K5_TAIL6_GRAPH9_SELFTEST: FAIL: {e}"),
+        }
+        if std::env::var("DIALOG_GCD_K5_TAIL6_GRAPH9_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
+    }
+    if std::env::var("DIALOG_GCD_K5_TAIL6_GRAPH_SELFTEST").is_ok() {
+        match dialog_gcd_k5_tail6_graph_codec_selftest() {
+            Ok(()) => eprintln!(
+                "DIALOG_GCD_K5_TAIL6_GRAPH_SELFTEST: PASS (32-word graph codec reversible and phase clean)"
+            ),
+            Err(e) => panic!("DIALOG_GCD_K5_TAIL6_GRAPH_SELFTEST: FAIL: {e}"),
+        }
+        if std::env::var("DIALOG_GCD_K5_TAIL6_GRAPH_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
+    }
+    if std::env::var("DIALOG_GCD_K5_TAIL7_SELFTEST").is_ok() {
+        match dialog_gcd_k5_tail7_codec_selftest() {
+            Ok(()) => eprintln!(
+                "DIALOG_GCD_K5_TAIL7_SELFTEST: PASS (20-word codec reversible and phase clean)"
+            ),
+            Err(e) => panic!("DIALOG_GCD_K5_TAIL7_SELFTEST: FAIL: {e}"),
+        }
+        if std::env::var("DIALOG_GCD_K5_TAIL7_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
+    }
+    if std::env::var("DIALOG_GCD_K5_TAIL7_FIXED_APPLY_SELFTEST").is_ok() {
+        match dialog_gcd_k5_tail7_fixed_apply_selftest() {
+            Ok(()) => eprintln!(
+                "DIALOG_GCD_K5_TAIL7_FIXED_APPLY_SELFTEST: PASS (fixed digit-4 apply matches fused apply)"
+            ),
+            Err(e) => panic!("DIALOG_GCD_K5_TAIL7_FIXED_APPLY_SELFTEST: FAIL: {e}"),
+        }
+        if std::env::var("DIALOG_GCD_K5_TAIL7_FIXED_APPLY_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
+    }
     if std::env::var("SQUARE_WINDOW_SELFTEST").is_ok() {
         match square_window_selftest() {
             Ok(()) => eprintln!("SQUARE_WINDOW_SELFTEST: PASS"),
@@ -1707,6 +1841,43 @@ pub fn build() -> Vec<Op> {
             Ok(()) => eprintln!("FOLD_FREED_TAIL_SELFTEST: PASS (freed-tail ≡ baseline, ancilla & phase clean)"),
             Err(e) => panic!("FOLD_FREED_TAIL_SELFTEST: FAIL: {e}"),
         }
+        if std::env::var("FOLD_FREED_TAIL_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
+    }
+    if std::env::var("SPECIAL_FOLD_PARK_SELFTEST").is_ok() {
+        match special_fold_park_selftest() {
+            Ok(()) => eprintln!(
+                "SPECIAL_FOLD_PARK_SELFTEST: PASS (parked fold ≡ baseline, ancilla & phase clean)"
+            ),
+            Err(e) => panic!("SPECIAL_FOLD_PARK_SELFTEST: FAIL: {e}"),
+        }
+        if std::env::var("SPECIAL_FOLD_PARK_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
+    }
+    if std::env::var("DIALOG_GCD_FUSED_APPLY_SELFTEST").is_ok() {
+        match dialog_gcd_k5_tail7_fixed_apply_selftest() {
+            Ok(()) => eprintln!(
+                "DIALOG_GCD_FUSED_APPLY_SELFTEST: PASS (fused double/halve value, ancilla, phase)"
+            ),
+            Err(e) => panic!("DIALOG_GCD_FUSED_APPLY_SELFTEST: FAIL: {e}"),
+        }
+        if std::env::var("DIALOG_GCD_FUSED_APPLY_SELFTEST_ONLY")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            return Vec::new();
+        }
     }
     build_builder().ops
 }
@@ -1876,9 +2047,6 @@ pub fn square_window_selftest() -> Result<(), String> {
 /// `FOLD_FREED_TAIL_SELFTEST=1 build_circuit`.
 pub fn fold_freed_tail_selftest() -> Result<(), String> {
     use sha3::digest::{ExtendableOutput, Update};
-    let cprime = U256::MAX
-        .wrapping_sub(SECP256K1_P)
-        .wrapping_add(U256::from(1u64)); // c = 2^32 + 977
     let hi_delta = 33usize;
     let hi_c = 32usize;
     let nbits = 64usize; // y width for the test (covers the active+tail span)
@@ -1893,22 +2061,32 @@ pub fn fold_freed_tail_selftest() -> Result<(), String> {
             let d_val = (ed >> 1) & 1;
             for &is_add in &[true, false] {
                 // Build both circuits over identical qubit layout.
-                let build_one = |freed: bool| -> (Vec<Op>, Vec<QubitId>, Vec<QubitId>, usize, usize) {
+                let build_one = |freed: bool| -> (Vec<Op>, Vec<QubitId>, usize, usize) {
                     let mut b = B::new();
                     let y = b.alloc_qubits(nbits);
+                    let ovf1 = b.alloc_qubit();
+                    let ovf2 = b.alloc_qubit();
+                    let s2 = b.alloc_qubit();
                     let e = b.alloc_qubit();
                     let d = b.alloc_qubit();
                     let h = b.alloc_qubit();
                     let xed = b.alloc_qubit();
                     let eord = b.alloc_qubit();
                     let n10 = b.alloc_qubit();
-                    // set e,d classically via X (per-shot identical); derive controls
-                    if e_val == 1 {
-                        b.x(e);
-                    }
+                    // Exercise the real caller relation for every (e,d) pair:
+                    // s2=1, ovf1=d, ovf2=e gives
+                    // d=ovf1&s2 and e=ovf1^d^ovf2.
+                    b.x(s2);
                     if d_val == 1 {
-                        b.x(d);
+                        b.x(ovf1);
                     }
+                    if e_val == 1 {
+                        b.x(ovf2);
+                    }
+                    b.ccx(ovf1, s2, d);
+                    b.cx(ovf1, e);
+                    b.cx(d, e);
+                    b.cx(ovf2, e);
                     b.ccx(e, d, h); // h = e&d
                     b.cx(e, xed);
                     b.cx(d, xed); // xed = e^d
@@ -1916,9 +2094,21 @@ pub fn fold_freed_tail_selftest() -> Result<(), String> {
                     b.cx(h, eord); // eord = e|d
                     b.cx(d, n10);
                     b.cx(h, n10); // n10 = !e&d
-                    let ancilla = vec![e, d, h, xed, eord, n10];
                     if freed {
-                        fold_ripple_freed_tail(&mut b, &y, e, d, h, xed, eord, n10, last, is_add);
+                        fold_ripple_freed_tail_ed(
+                            &mut b,
+                            &y,
+                            e,
+                            d,
+                            h,
+                            xed,
+                            eord,
+                            n10,
+                            Some((ovf1, ovf2, s2)),
+                            None,
+                            last,
+                            is_add,
+                        );
                     } else {
                         let controls =
                             secp_fold_controls(e, d, h, xed, eord, n10, hi_delta, hi_c);
@@ -1937,24 +2127,23 @@ pub fn fold_freed_tail_selftest() -> Result<(), String> {
                     b.cx(d, xed);
                     b.cx(e, xed);
                     b.ccx(e, d, h);
+                    b.cx(ovf2, e);
+                    b.cx(d, e);
+                    b.cx(ovf1, e);
+                    b.ccx(ovf1, s2, d);
                     if e_val == 1 {
-                        b.x(e);
+                        b.x(ovf2);
                     }
                     if d_val == 1 {
-                        b.x(d);
+                        b.x(ovf1);
                     }
+                    b.x(s2);
                     let nq = b.next_qubit as usize;
                     let nb = b.next_bit as usize;
-                    (b.ops, y, ancilla, nq, nb)
+                    (b.ops, y, nq, nb)
                 };
-                let (ops_base, y_b, anc_b, nq_b, nb_b) = build_one(false);
-                let (ops_freed, y_f, anc_f, nq_f, nb_f) = build_one(true);
-
-                let mut seed = sha3::Shake128::default();
-                seed.update(b"fold-freed-tail-selftest");
-                seed.update(&[ed as u8, is_add as u8, windowed as u8]);
-                let mut xof = seed.finalize_xof();
-
+                let (ops_base, y_b, nq_b, nb_b) = build_one(false);
+                let (ops_freed, y_f, nq_f, nb_f) = build_one(true);
                 // deterministic random y per shot, including adversarial
                 // carry-propagation patterns (long runs of 1s above bit 33 that
                 // force the truncated tail carry to escape / saturate).
@@ -1978,7 +2167,7 @@ pub fn fold_freed_tail_selftest() -> Result<(), String> {
                     })
                     .collect();
 
-                let run = |ops: &[Op], y: &[QubitId], anc: &[QubitId], nq: usize, nb: usize| -> (Vec<u64>, bool, u64) {
+                let run = |ops: &[Op], y: &[QubitId], nq: usize, nb: usize| -> (Vec<u64>, bool, u64) {
                     let mut s2 = sha3::Shake128::default();
                     s2.update(b"fold-sim");
                     let mut xof2 = s2.finalize_xof();
@@ -2001,17 +2190,12 @@ pub fn fold_freed_tail_selftest() -> Result<(), String> {
                             v
                         })
                         .collect();
-                    let mut anc_clean = true;
-                    for &a in anc {
-                        if sim.qubit(a) != 0 {
-                            anc_clean = false;
-                        }
-                    }
+                    let anc_clean =
+                        (nbits..nq).all(|q| sim.qubit(QubitId(q as u64)) == 0);
                     (outs, anc_clean, sim.phase)
                 };
-                let _ = (&xof, nq_b, nb_b);
-                let (out_b, clean_b, phase_b) = run(&ops_base, &y_b, &anc_b, nq_b, nb_b);
-                let (out_f, clean_f, phase_f) = run(&ops_freed, &y_f, &anc_f, nq_f, nb_f);
+                let (out_b, clean_b, phase_b) = run(&ops_base, &y_b, nq_b, nb_b);
+                let (out_f, clean_f, phase_f) = run(&ops_freed, &y_f, nq_f, nb_f);
 
                 if !clean_b {
                     return Err(format!("baseline left ancilla dirty (ed={ed} add={is_add} win={windowed})"));
@@ -2037,6 +2221,123 @@ pub fn fold_freed_tail_selftest() -> Result<(), String> {
     Ok(())
 }
 
+pub fn special_fold_park_selftest() -> Result<(), String> {
+    use sha3::digest::{ExtendableOutput, Update};
+
+    let c = U256::MAX
+        .wrapping_sub(SECP256K1_P)
+        .wrapping_add(U256::from(1u64));
+    let nbits = 64usize;
+    let window = 20usize;
+
+    for ctrl_value in 0u64..=1 {
+        for &is_add in &[true, false] {
+            let build_one = |parked: bool| {
+                let mut b = B::new();
+                let acc = b.alloc_qubits(nbits);
+                let ctrl = b.alloc_qubit();
+                let scratch = b.alloc_qubits(5);
+                if ctrl_value != 0 {
+                    b.x(ctrl);
+                }
+                if parked {
+                    if is_add {
+                        cadd_nbit_const_direct_trunc_fast_releasing_scratch(
+                            &mut b, &acc, c, ctrl, window, &scratch,
+                        );
+                    } else {
+                        csub_nbit_const_direct_trunc_fast_releasing_scratch(
+                            &mut b, &acc, c, ctrl, window, &scratch,
+                        );
+                    }
+                } else if is_add {
+                    cadd_nbit_const_direct_trunc_fast_borrowed_carries(
+                        &mut b, &acc, c, ctrl, window, &scratch,
+                    );
+                } else {
+                    csub_nbit_const_direct_trunc_fast_borrowed_carries(
+                        &mut b, &acc, c, ctrl, window, &scratch,
+                    );
+                }
+                if ctrl_value != 0 {
+                    b.x(ctrl);
+                }
+                (b.ops, acc, b.next_qubit as usize, b.next_bit as usize)
+            };
+
+            let (base_ops, base_acc, base_nq, base_nb) = build_one(false);
+            let (parked_ops, parked_acc, parked_nq, parked_nb) = build_one(true);
+            let inputs: Vec<u64> = (0..64u64)
+                .map(|shot| {
+                    let mixed = shot
+                        .wrapping_mul(0x9E37_79B9_7F4A_7C15)
+                        .wrapping_add(0xD1B5_4A32_D192_ED03);
+                    match shot % 4 {
+                        0 => mixed | (!0u64 << 33),
+                        1 => mixed & ((1u64 << 34) - 1),
+                        _ => mixed ^ (mixed >> 29),
+                    }
+                })
+                .collect();
+
+            let run = |ops: &[Op], acc: &[QubitId], nq: usize, nb: usize| {
+                let mut seed = Shake256::default();
+                seed.update(b"special-fold-park-selftest");
+                seed.update(&[ctrl_value as u8, is_add as u8]);
+                let mut xof = seed.finalize_xof();
+                let mut sim = Simulator::new(nq, nb, &mut xof);
+                sim.clear_for_shot();
+                for (shot, &input) in inputs.iter().enumerate() {
+                    for bit_index in 0..nbits {
+                        if (input >> bit_index) & 1 != 0 {
+                            *sim.qubit_mut(acc[bit_index]) |= 1u64 << shot;
+                        }
+                    }
+                }
+                sim.apply_iter(ops.iter());
+                let outputs: Vec<u64> = (0..64)
+                    .map(|shot| {
+                        let mut value = 0u64;
+                        for bit_index in 0..nbits {
+                            value |= ((sim.qubit(acc[bit_index]) >> shot) & 1) << bit_index;
+                        }
+                        value
+                    })
+                    .collect();
+                let clean = (nbits..nq).all(|q| sim.qubit(QubitId(q as u64)) == 0);
+                (outputs, clean, sim.phase)
+            };
+
+            let (base_out, base_clean, base_phase) =
+                run(&base_ops, &base_acc, base_nq, base_nb);
+            let (parked_out, parked_clean, parked_phase) =
+                run(&parked_ops, &parked_acc, parked_nq, parked_nb);
+            if !base_clean || base_phase != 0 {
+                return Err(format!(
+                    "baseline dirty: ctrl={ctrl_value} add={is_add} clean={base_clean} phase=0x{base_phase:x}"
+                ));
+            }
+            if !parked_clean || parked_phase != 0 {
+                return Err(format!(
+                    "parked dirty: ctrl={ctrl_value} add={is_add} clean={parked_clean} phase=0x{parked_phase:x}"
+                ));
+            }
+            if base_out != parked_out {
+                let shot = base_out
+                    .iter()
+                    .zip(&parked_out)
+                    .position(|(base, parked)| base != parked)
+                    .unwrap_or(0);
+                return Err(format!(
+                    "value mismatch shot {shot}: base=0x{:x} parked=0x{:x} input=0x{:x} ctrl={ctrl_value} add={is_add}",
+                    base_out[shot], parked_out[shot], inputs[shot]
+                ));
+            }
+        }
+    }
+    Ok(())
+}
+
 
 #[cfg(test)]
 mod direct_const_tests {
diff --git a/src/point_add/rounds/dialog/config.rs b/src/point_add/rounds/dialog/config.rs
index d204a2b..116360d 100644
--- a/src/point_add/rounds/dialog/config.rs
+++ b/src/point_add/rounds/dialog/config.rs
@@ -75,6 +75,22 @@ pub(crate) fn dialog_gcd_apply_chunked_f_blocks() -> Option<usize> {
         .filter(|&blocks| blocks >= 2)
 }
 
+pub(crate) fn dialog_gcd_apply_chunked_f_cuts() -> Option<Vec<usize>> {
+    std::env::var("DIALOG_GCD_APPLY_CHUNKED_F_CUTS")
+        .ok()
+        .filter(|value| !value.trim().is_empty())
+        .map(|value| {
+            value
+                .split(',')
+                .map(|item| {
+                    item.trim()
+                        .parse::<usize>()
+                        .expect("DIALOG_GCD_APPLY_CHUNKED_F_CUTS")
+                })
+                .collect()
+        })
+}
+
 pub(crate) fn dialog_gcd_apply_chunked_f_cut() -> Option<usize> {
     std::env::var("DIALOG_GCD_APPLY_CHUNKED_F_CUT")
         .ok()
@@ -131,6 +147,20 @@ pub(crate) fn dialog_gcd_apply_chunked_f_fuse_boundary_clears_enabled() -> bool
         != Some("0")
 }
 
+pub(crate) fn dialog_gcd_apply_borrow_future_boundary_carries_enabled() -> bool {
+    std::env::var("DIALOG_GCD_APPLY_BORROW_FUTURE_BOUNDARY_CARRIES")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
+pub(crate) fn dialog_gcd_apply_implicit_high_zero_enabled() -> bool {
+    std::env::var("DIALOG_GCD_APPLY_IMPLICIT_HIGH_ZERO")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
 pub(crate) fn dialog_gcd_apply_final_lowq_enabled() -> bool {
     std::env::var("DIALOG_GCD_APPLY_FINAL_LOWQ").ok().as_deref() == Some("1")
 }
diff --git a/src/point_add/rounds/dialog/mod.rs b/src/point_add/rounds/dialog/mod.rs
index 4ffc51e..5e3cdec 100644
--- a/src/point_add/rounds/dialog/mod.rs
+++ b/src/point_add/rounds/dialog/mod.rs
@@ -247,6 +247,17 @@ fn dialog_gcd_step_map_value(env: &str, step: usize) -> usize {
         .sum()
 }
 
+fn dialog_gcd_step_map_override(env: &str, step: usize) -> Option<usize> {
+    let map = std::env::var(env).ok()?;
+    map.split(',').rev().find_map(|entry| {
+        let (raw_step, raw_value) = entry.trim().split_once(':')?;
+        if raw_step.trim().parse::<usize>().ok()? != step {
+            return None;
+        }
+        raw_value.trim().parse::<usize>().ok()
+    })
+}
+
 pub(crate) fn dialog_gcd_width_step_bump(step: usize) -> usize {
     dialog_gcd_step_map_value("DIALOG_GCD_WIDTH_STEP_BUMPS", step)
 }
@@ -255,6 +266,17 @@ pub(crate) fn dialog_gcd_body_step_giveback(step: usize) -> usize {
     dialog_gcd_step_map_value("DIALOG_GCD_BODY_STEP_GIVEBACKS", step)
 }
 
+pub(crate) fn dialog_gcd_fused_fold_carry_trunc_window(
+    step: Option<usize>,
+) -> Option<usize> {
+    step.and_then(|step| {
+        dialog_gcd_step_map_override("DIALOG_GCD_FOLD_CARRY_TRUNC_STEP_WINDOWS", step)
+    })
+    .filter(|&window| window > 0)
+    .or_else(fold_only_carry_trunc_window)
+    .or_else(double_carry_trunc_window)
+}
+
 /// Carry-tail truncation window for the materialized controlled sub/add BODY
 /// (and its gated LOAD). Default 0 (OFF). When `w > 0`, the controlled
 /// `acc -= ctrl·subtrahend` / `acc += ctrl·addend` only loads + ripples the
@@ -1191,7 +1213,7 @@ pub(crate) fn dialog_gcd_cmod_add_materialized_pseudomersenne_with_clean_scratch
     b.free(c_in);
 
     b.set_phase("dialog_gcd_materialized_special_overflow_fold");
-    if let Some(w) = fold_carry_trunc_window() {
+    if let Some(w) = dialog_gcd_special_fold_carry_trunc_window(step) {
         cadd_nbit_const_direct_trunc_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf, w);
     } else {
         cadd_nbit_const_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf);
@@ -1278,6 +1300,19 @@ pub(crate) fn dialog_gcd_special_overflow_clean_compare_bits(step: Option<usize>
     )
 }
 
+pub(crate) fn dialog_gcd_special_fold_carry_trunc_window(
+    step: Option<usize>,
+) -> Option<usize> {
+    step.and_then(|step| {
+        dialog_gcd_step_map_override(
+            "DIALOG_GCD_SPECIAL_FOLD_CARRY_TRUNC_STEP_WINDOWS",
+            step,
+        )
+    })
+    .filter(|&window| window > 0)
+    .or_else(fold_carry_trunc_window)
+}
+
 pub(crate) fn dialog_gcd_special_clean_compare_bits_from_env(
     step: Option<usize>,
     env_name: &str,
@@ -1337,6 +1372,22 @@ pub(crate) fn dialog_gcd_clear_controlled_slice_hmr(
 }
 
 pub(crate) fn dialog_gcd_chunk_hi(blocks: usize, block: usize, ext_n: usize) -> usize {
+    if let Some(cuts) = dialog_gcd_apply_chunked_f_cuts() {
+        assert_eq!(
+            cuts.len() + 1,
+            blocks,
+            "DIALOG_GCD_APPLY_CHUNKED_F_CUTS must contain blocks-1 cuts"
+        );
+        assert!(
+            cuts.first().is_some_and(|&cut| cut > 0)
+                && cuts.windows(2).all(|pair| pair[0] < pair[1])
+                && cuts.last().is_some_and(|&cut| cut < ext_n),
+            "DIALOG_GCD_APPLY_CHUNKED_F_CUTS must be strictly increasing in 1..{ext_n}: {cuts:?}"
+        );
+        if block < cuts.len() {
+            return cuts[block];
+        }
+    }
     if blocks == 4 && dialog_gcd_apply_chunked_f_custom4_enabled() {
         let cuts = [
             dialog_gcd_apply_chunked_f_cut().unwrap_or(ext_n / 4),
@@ -1379,6 +1430,74 @@ pub(crate) fn dialog_gcd_chunk_hi(blocks: usize, block: usize, ext_n: usize) ->
     ((block + 1) * ext_n) / blocks
 }
 
+fn dialog_gcd_add_fast_with_borrowed_carries(
+    b: &mut B,
+    a: &[QubitId],
+    acc: &[QubitId],
+    c_in: QubitId,
+    borrowed: &[QubitId],
+) {
+    let needed = a.len().saturating_sub(1);
+    let borrowed = &borrowed[..borrowed.len().min(needed)];
+    let owned = b.alloc_qubits(needed - borrowed.len());
+    let mut carries = Vec::with_capacity(needed);
+    carries.extend_from_slice(borrowed);
+    carries.extend_from_slice(&owned);
+    cuccaro_add_fast_borrowed_carries(b, a, acc, c_in, &carries);
+    b.free_vec(&owned);
+}
+
+fn dialog_gcd_sub_fast_with_borrowed_carries(
+    b: &mut B,
+    a: &[QubitId],
+    acc: &[QubitId],
+    c_in: QubitId,
+    borrowed: &[QubitId],
+) {
+    let needed = a.len().saturating_sub(1);
+    let borrowed = &borrowed[..borrowed.len().min(needed)];
+    let owned = b.alloc_qubits(needed - borrowed.len());
+    let mut carries = Vec::with_capacity(needed);
+    carries.extend_from_slice(borrowed);
+    carries.extend_from_slice(&owned);
+    cuccaro_sub_fast_borrowed_carries(b, a, acc, c_in, &carries);
+    b.free_vec(&owned);
+}
+
+fn dialog_gcd_add_fast_low_to_ext_with_borrowed_carries(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    c_in: QubitId,
+    borrowed: &[QubitId],
+) {
+    let needed = a.len();
+    let borrowed = &borrowed[..borrowed.len().min(needed)];
+    let owned = b.alloc_qubits(needed - borrowed.len());
+    let mut carries = Vec::with_capacity(needed);
+    carries.extend_from_slice(borrowed);
+    carries.extend_from_slice(&owned);
+    cuccaro_add_fast_low_to_ext_borrowed_carries(b, a, acc_ext, c_in, &carries);
+    b.free_vec(&owned);
+}
+
+fn dialog_gcd_sub_fast_low_to_ext_with_borrowed_carries(
+    b: &mut B,
+    a: &[QubitId],
+    acc_ext: &[QubitId],
+    c_in: QubitId,
+    borrowed: &[QubitId],
+) {
+    let needed = a.len();
+    let borrowed = &borrowed[..borrowed.len().min(needed)];
+    let owned = b.alloc_qubits(needed - borrowed.len());
+    let mut carries = Vec::with_capacity(needed);
+    carries.extend_from_slice(borrowed);
+    carries.extend_from_slice(&owned);
+    cuccaro_sub_fast_low_to_ext_borrowed_carries(b, a, acc_ext, c_in, &carries);
+    b.free_vec(&owned);
+}
+
 fn dialog_gcd_conditional_boundary_replay(
     b: &mut B,
     u: &[QubitId],
@@ -1431,12 +1550,14 @@ pub(crate) fn dialog_gcd_add_ctrl_chunked_low_to_ext(
     let blocks = blocks.max(2).min(ext_n);
     let mut carry = c_in;
     let mut lo = 0usize;
-    // Reserve the first borrowed cell as the transient high-zero lane.  It is
-    // restored after every chunk and may be reused if REUSE_CIN_ZERO=0.  The
-    // remaining cells can hold dirty boundary carries until the exact
-    // cumulative comparator sweep clears them.
-    let zero_host = clean_scratch.first().copied();
-    let boundary_hosts = &clean_scratch[usize::from(zero_host.is_some())..];
+    // The low-to-extended-register primitive represents the source high zero
+    // implicitly. Otherwise reserve one borrowed cell for that transient lane.
+    let implicit_high_zero = dialog_gcd_apply_implicit_high_zero_enabled();
+    let zero_host = (!implicit_high_zero)
+        .then(|| clean_scratch.first().copied())
+        .flatten();
+    let boundary_hosts = &clean_scratch
+        [usize::from(!implicit_high_zero && zero_host.is_some())..];
     let mut couts: Vec<(QubitId, usize, bool)> = Vec::new();
 
     for blk in 0..blocks {
@@ -1488,12 +1609,33 @@ pub(crate) fn dialog_gcd_add_ctrl_chunked_low_to_ext(
             .get(couts.len())
             .copied()
             .map_or_else(|| (b.alloc_qubit(), true), |q| (q, false));
-        let mut a_block = f.clone();
-        a_block.push(zero);
         let mut acc_block = acc_ext[lo..hi].to_vec();
         acc_block.push(cout);
+        let future_boundary_carries = if dialog_gcd_apply_borrow_future_boundary_carries_enabled() {
+            boundary_hosts.get(couts.len() + 1..).unwrap_or(&[])
+        } else {
+            &[]
+        };
         b.set_phase("dialog_gcd_apply_chunk_add_ripple");
-        cuccaro_add_fast(b, &a_block, &acc_block, carry);
+        if implicit_high_zero {
+            dialog_gcd_add_fast_low_to_ext_with_borrowed_carries(
+                b,
+                &f,
+                &acc_block,
+                carry,
+                future_boundary_carries,
+            );
+        } else {
+            let mut a_block = f.clone();
+            a_block.push(zero);
+            dialog_gcd_add_fast_with_borrowed_carries(
+                b,
+                &a_block,
+                &acc_block,
+                carry,
+                future_boundary_carries,
+            );
+        }
         if owned_zero {
             b.free(zero);
         }
@@ -1569,10 +1711,12 @@ pub(crate) fn dialog_gcd_sub_ctrl_chunked_low_to_ext(
     let blocks = blocks.max(2).min(ext_n);
     let mut borrow = c_in;
     let mut lo = 0usize;
-    // Symmetric to the add path: reserve one clean transient high-zero host and
-    // retain borrowed boundary-borrow cells until their comparator clear.
-    let zero_host = clean_scratch.first().copied();
-    let boundary_hosts = &clean_scratch[usize::from(zero_host.is_some())..];
+    let implicit_high_zero = dialog_gcd_apply_implicit_high_zero_enabled();
+    let zero_host = (!implicit_high_zero)
+        .then(|| clean_scratch.first().copied())
+        .flatten();
+    let boundary_hosts = &clean_scratch
+        [usize::from(!implicit_high_zero && zero_host.is_some())..];
     let mut bouts: Vec<(QubitId, usize, bool)> = Vec::new();
 
     for blk in 0..blocks {
@@ -1624,12 +1768,33 @@ pub(crate) fn dialog_gcd_sub_ctrl_chunked_low_to_ext(
             .get(bouts.len())
             .copied()
             .map_or_else(|| (b.alloc_qubit(), true), |q| (q, false));
-        let mut a_block = f.clone();
-        a_block.push(zero);
         let mut acc_block = acc_ext[lo..hi].to_vec();
         acc_block.push(bout);
+        let future_boundary_carries = if dialog_gcd_apply_borrow_future_boundary_carries_enabled() {
+            boundary_hosts.get(bouts.len() + 1..).unwrap_or(&[])
+        } else {
+            &[]
+        };
         b.set_phase("dialog_gcd_apply_chunk_sub_ripple");
-        cuccaro_sub_fast(b, &a_block, &acc_block, borrow);
+        if implicit_high_zero {
+            dialog_gcd_sub_fast_low_to_ext_with_borrowed_carries(
+                b,
+                &f,
+                &acc_block,
+                borrow,
+                future_boundary_carries,
+            );
+        } else {
+            let mut a_block = f.clone();
+            a_block.push(zero);
+            dialog_gcd_sub_fast_with_borrowed_carries(
+                b,
+                &a_block,
+                &acc_block,
+                borrow,
+                future_boundary_carries,
+            );
+        }
         if owned_zero {
             b.free(zero);
         }
@@ -1728,20 +1893,50 @@ pub(crate) fn dialog_gcd_cmod_add_materialized_pseudomersenne_chunked(
     }
 
     b.set_phase("dialog_gcd_materialized_special_overflow_fold");
-    if let Some(w) = fold_carry_trunc_window() {
-        let borrowed_carries = if std::env::var("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES").ok().as_deref() == Some("1") {
-            inner_scratch
+    if let Some(w) = dialog_gcd_special_fold_carry_trunc_window(step) {
+        let borrowed_carries = if std::env::var("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            // The chunk carry-in is back to |0> after the raw sum and is idle
+            // during the fold, so it is a valid carry host alongside the
+            // remaining clean scratch.
+            clean_scratch
         } else {
             &[]
         };
-        cadd_nbit_const_direct_trunc_fast_borrowed_carries(
-            b,
-            &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS],
-            c,
-            acc_ovf,
-            w,
-            borrowed_carries,
-        );
+        if std::env::var("DIALOG_GCD_SPECIAL_FOLD_RELEASE_SCRATCH")
+            .ok()
+            .as_deref()
+            == Some("1")
+            && !borrowed_carries.is_empty()
+        {
+            assert_eq!(
+                std::env::var("DIALOG_GCD_K2_APPLY_INPLACE_RAW_BLOCK")
+                    .ok()
+                    .as_deref(),
+                Some("1"),
+                "special-fold scratch release requires owned in-place apply scratch"
+            );
+            cadd_nbit_const_direct_trunc_fast_releasing_scratch(
+                b,
+                &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS],
+                c,
+                acc_ovf,
+                w,
+                borrowed_carries,
+            );
+        } else {
+            cadd_nbit_const_direct_trunc_fast_borrowed_carries(
+                b,
+                &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS],
+                c,
+                acc_ovf,
+                w,
+                borrowed_carries,
+            );
+        }
     } else {
         cadd_nbit_const_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf);
     }
@@ -1800,20 +1995,49 @@ pub(crate) fn dialog_gcd_cmod_sub_materialized_pseudomersenne_chunked(
     }
 
     b.set_phase("dialog_gcd_materialized_special_underflow_fold");
-    if let Some(w) = fold_carry_trunc_window() {
-        let borrowed_carries = if std::env::var("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES").ok().as_deref() == Some("1") {
-            inner_scratch
+    if let Some(w) = dialog_gcd_special_fold_carry_trunc_window(step) {
+        let borrowed_carries = if std::env::var("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES")
+            .ok()
+            .as_deref()
+            == Some("1")
+        {
+            // The chunk borrow-in is back to |0> after the raw difference and
+            // can host one fold borrow without increasing the live set.
+            clean_scratch
         } else {
             &[]
         };
-        csub_nbit_const_direct_trunc_fast_borrowed_carries(
-            b,
-            &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS],
-            c,
-            acc_ovf,
-            w,
-            borrowed_carries,
-        );
+        if std::env::var("DIALOG_GCD_SPECIAL_FOLD_RELEASE_SCRATCH")
+            .ok()
+            .as_deref()
+            == Some("1")
+            && !borrowed_carries.is_empty()
+        {
+            assert_eq!(
+                std::env::var("DIALOG_GCD_K2_APPLY_INPLACE_RAW_BLOCK")
+                    .ok()
+                    .as_deref(),
+                Some("1"),
+                "special-fold scratch release requires owned in-place apply scratch"
+            );
+            csub_nbit_const_direct_trunc_fast_releasing_scratch(
+                b,
+                &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS],
+                c,
+                acc_ovf,
+                w,
+                borrowed_carries,
+            );
+        } else {
+            csub_nbit_const_direct_trunc_fast_borrowed_carries(
+                b,
+                &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS],
+                c,
+                acc_ovf,
+                w,
+                borrowed_carries,
+            );
+        }
     } else {
         csub_nbit_const_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf);
     }
@@ -1933,7 +2157,7 @@ pub(crate) fn dialog_gcd_cmod_sub_materialized_pseudomersenne_with_clean_scratch
     }
 
     b.set_phase("dialog_gcd_materialized_special_underflow_fold");
-    if let Some(w) = fold_carry_trunc_window() {
+    if let Some(w) = dialog_gcd_special_fold_carry_trunc_window(step) {
         csub_nbit_const_direct_trunc_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf, w);
     } else {
         csub_nbit_const_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf);
@@ -2096,7 +2320,7 @@ pub(crate) fn dialog_gcd_cmod_sub_materialized_pseudomersenne_borrowed_subtrahen
     b.free(f_ovf);
 
     b.set_phase("dialog_gcd_materialized_special_borrowed_underflow_fold");
-    if let Some(w) = fold_carry_trunc_window() {
+    if let Some(w) = dialog_gcd_special_fold_carry_trunc_window(step) {
         csub_nbit_const_direct_trunc_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf, w);
     } else {
         csub_nbit_const_fast(b, &acc[..DIALOG_GCD_SPECIAL_ADD_LSBS], c, acc_ovf);
```

