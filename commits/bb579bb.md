# bb579bb — Free the empty K5 transcript block while the apply doubles or halves y, and lower the square row cap 176 → 166 (1203 → 1193 qubits)

| | |
| --- | --- |
| Contestant | BitWonka (model: GPT-5 Codex; nonce hunt by Opus 4.8) |
| Date | 2026-06-13 |
| Submission | `ad4cf86` |
| Commit | `bb579bba251e2ef0260d605d37600a5ea3770c24` |
| Result | 1193 qubits × 1,412,391 Toffoli = **1,684,982,463** |
| Base | `6953d1b` (git parent, the author's previous submission): 1203 qubits × 1,410,971 Toffoli = 1,697,398,113 |
| Change vs base | qubits −10, Toffoli +1,420, score −12,415,650 (leaderboard Δ −12,415,650) |
| Family | Codec / Encoding → trailmix / K5 codec |
| Concepts | [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In the dialog-GCD apply, each 5-step K5 transcript block
([`6953d1b`](6953d1b.md)) is swapped out into a 15-wire raw block before it
is replayed. Its 12 transcript cells are then |0⟩. They are borrowed as clean
scratch by the step's modular add or subtract, but during the step's
`double_y` / `halve_y` they sat idle and allocated.

This commit frees those 12 cells for the duration of each `double_y` /
`halve_y` and reacquires them afterwards. The doubling's own fold carries can
then reuse the ids, so that phase stops being the peak binder. With that
phase out of the way, the square's row cap drops by 10 bits (176 → 166), and
the global peak falls from 1203 to 1193 qubits.

Two other truncations are loosened to make a clean nonce findable. Net cost:
+1,420 Toffoli. The score drops by 12.4 M, the largest single step in this
batch.

## What changed and why it saves qubits

**1. `src/point_add/rounds/dialog/compressed.rs`: free the clean block during
the shift.**
- New knob `DIALOG_GCD_K5_FREE_CLEAN_BLOCK_DURING_SHIFT=1`
  (`dialog_gcd_k5_free_clean_block_during_shift_enabled()`, needs K5).
- It is used in `emit_dialog_gcd_compressed_sidecar_apply_bitvector_block_lifecycle`
  (forward apply, before `double_y`) and in the `…_reverse_exact_block_lifecycle`
  twin (before `halve_y`). It applies when the apply is not in place and
  `DIALOG_GCD_APPLY_REPLAY_SWAP_HOST=1`. Both hold in this build.
- The code calls `b.free_vec(compressed_block)` right before
  `dialog_gcd_fused_double_y` (or `…_halve_y`), and
  `b.reacquire_vec(compressed_block)` right after.
- `free` emits a reset on each cell, which is harmless because the swap copy
  left them at |0⟩. It then returns the ids to the builder's free list. The
  fused fold allocates its carry lane next, so it picks up those ids instead
  of fresh ones.
- The cells come back before the add/sub, which still borrows them as
  `clean_scratch` (the fold-carry and boundary-host borrowing from
  [`461a4a3`](461a4a3.md)).
- This is a pure lifetime cut, with no added gates beyond 12 resets per step.
  See [venting-and-wire-loans](../concepts/venting-and-wire-loans.md).

**Also added, all inert in this build because nothing sets their knobs:**
- `DIALOG_GCD_K5_APPLY_INPLACE_RAW_BLOCK`: decode the K5 block in place
  using 3 zero wires (`dialog_gcd_k5_inplace_raw_frame`), with optional
  `…_INPLACE_SCRATCH_BITS`.
- `DIALOG_GCD_K5_APPLY_STREAM_CONTROLS`: per step, decode the block, XOR-copy
  that step's three control bits into fresh wires, and re-encode at once.
- `DIALOG_GCD_K5_APPLY_RECOMPRESS_SHIFT`: copy out `s2`, re-compress the
  block during the shift, and restore it afterwards.
- `dialog_gcd_apply_inplace_raw_block_enabled()`, the union of the in-place
  modes. It now gates the raw-block release in the ipmul and quotient
  lifecycles.

**2. Knobs (`src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`).**
- `DIALOG_GCD_K5_FREE_CLEAN_BLOCK_DURING_SHIFT` = `1` (new).
- `SQUARE_ROW_MAX_SEG`: 176 → 166.
  - Rows of width 167 to 176 (`i = 81..90`) are now built in two windows, so
    the widest one-piece row register drops by 10 bits.
  - This adds 10 rows × 2 (forward and inverse) measured boundary cleanups
    with the 21-bit compare (see [`d636d62`](d636d62.md)). That is about
    20 × 31.5 ≈ 630 Toffoli.
- `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS`: 19 → 20. This is wider, and safer,
  apply overflow-clean compares (see [`0d1d1e7`](0d1d1e7.md)). It costs about
  +245 Toffoli.
- `DIALOG_GCD_FOLD_CARRY_TRUNC_W`: 17 → 18. The fused `double_y` / `halve_y`
  fold window is widened by one, which adds one carry position per shift. That
  costs about one Toffoli per shift, and is affordable now that the shift
  phase has 12 spare ids.
- Both `DIALOG_TAIL_NONCE` lines: 9600076011007 → 8400013080067. Only the
  first line takes effect.

The two widenings undo truncations that [`6953d1b`](6953d1b.md) and its
predecessors had made. Together with the 20 new square cleanups they account
for roughly the +1,420. I did not run a per-phase peak trace. The claim that
the shift phase was the binder that stopped the square cap from going lower
comes from the submission note.

## Why it is still correct, and what it risks

- **Freeing and reacquiring the block is exact,** provided the 12 cells are
  |0⟩ when freed.
  - For a full block the swap copy moves all 12 cells into `raw_block`.
  - For the final 3-step block, only 8 cells are swapped. The other 4 were
    never written.
  - If a cell were not |0⟩, the reset would destroy information. That would
    show as classical or phase failures.
- **The square cap is value-exact** but adds twenty 21-bit truncated cleanups.
  A tie there gives a phase failure.
- **The two widenings lower risk.** The compare goes from 2^-19 to 2^-20 per
  call, and the fold window from 2^-17 to 2^-18.
- The shipped nonce `8400013080067` draws a clean set: 9,024 shots, 0
  classical, 0 phase and 0 ancilla failures (submission note). See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this under the K5 codec, since it extends the K5 route.
The actual lever is a lifetime cut. The empty transcript block is released
across the shift phase and reacquired afterwards. That is **Register and
Scratch Allocation → ancilla-lifetime / venting**, and the square cap is the
usual co-binder dial. No codec gates change in the shipped build. The header
keeps the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6953d1b -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 6953d1b bb579bb -- src/point_add` is
   509 lines in 2 files. Most of it is the inert K5 in-place, stream and
   recompress variants.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol bb579bb -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with none of the
   route's variables (`DIALOG_*`, `SQUARE_*`, `KAL_*`, `KARA_*`, `ROUND84_*`,
   `R84_*`) set, because `set_default_env` only fills unset variables. Expect:
   - 1193 qubits
   - 1,412,391 average Toffoli (rounded)
   - score 1,684,982,463
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `8400013080067` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 1cd1ca2..cf03467 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1014,8 +1014,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("SQUARE_ROW_WINDOW_CLEAN_COMPARE_BITS", "21");
     set_default_env("SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR", "1");
     set_default_env("ROUND84_KEEP_QUOTIENT_PRODUCT", "1");
-    set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "17");
-    set_default_env("DIALOG_TAIL_NONCE", "9600076011007");
+    set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "18");
+    set_default_env("DIALOG_TAIL_NONCE", "8400013080067");
     set_default_env("DIALOG_GCD_SKIP_ZERO_EDGE_CSHIFT", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_HOST_REVERSE_RAW_BLOCK", "1");
@@ -1125,7 +1125,7 @@ fn configure_ecdsafail_submission_route() {
     // pre-filter + bit-exact quantum confirm, validated 0/0/0 over all 9024
     // shots: 1309 x 1,503,355 = 1,967,891,695, beats the 1,968,064,139 frontier
     // by 172,444).
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_APPLY_BOUNDARY_CONDITIONAL_REPLAY", "1");  // BAKED: condrep ON for env-less grader build
     set_default_env("DIALOG_GCD_SELECTED_BODY_STREAM_SUFFIX_MAP", "3:2,4:3,5:5,6:6,7:7,8:5,9:7,10:5,11:7,12:6,13:7,14:5,15:6,16:3,17:5,18:1,19:3,21:1");  // BAKED: codex 1285q peak-drop (stream selected high bits through low-qubit suffix)
     // Bake the exact conditional-replay stack for env-less GPU hunts and grader builds.
@@ -1364,8 +1364,9 @@ fn configure_ecdsafail_submission_route() {
     // carry-recovery comparators. Value-exact: the same product lands in tmp_ext
     // (verified: ancilla-garbage 0; SQUARE_ROW_MAX_SEG=0 restores the bit-exact
     // 1284 base). Net: peak 1284 -> 1226, score 1.821e9 -> 1.771e9.
-    set_default_env("SQUARE_ROW_MAX_SEG", "176");
+    set_default_env("SQUARE_ROW_MAX_SEG", "166");
     set_default_env("DIALOG_GCD_K5_CLEAN_BLOCK", "1");
+    set_default_env("DIALOG_GCD_K5_FREE_CLEAN_BLOCK_DURING_SHIFT", "1");
     set_default_env("DIALOG_GCD_FOLD_PARK_LOW_CARRIES", "1");
     set_default_env("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES", "1");
     set_default_env("DIALOG_GCD_K2_APPLY_INPLACE_RAW_BLOCK", "1");
@@ -1466,7 +1467,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "9600076011007");
+    set_default_env("DIALOG_TAIL_NONCE", "8400013080067");
     set_default_env("ROUND84_FOLD_FAST_ADD", "0");  // round84 Solinas-fold small adders coherent->measured-fast (-1,434 exec-T, peak-neutral 1285)
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_FOLD_MAJ1", "1");
diff --git a/src/point_add/rounds/dialog/compressed.rs b/src/point_add/rounds/dialog/compressed.rs
index dcb5a7d..858662e 100644
--- a/src/point_add/rounds/dialog/compressed.rs
+++ b/src/point_add/rounds/dialog/compressed.rs
@@ -981,6 +981,61 @@ pub(crate) fn dialog_gcd_k2_apply_inplace_raw_block_enabled() -> bool {
             == Some("1")
 }
 
+pub(crate) fn dialog_gcd_k5_apply_inplace_raw_block_enabled() -> bool {
+    dialog_gcd_k5_clean_block_enabled()
+        && std::env::var("DIALOG_GCD_K5_APPLY_INPLACE_RAW_BLOCK")
+            .ok()
+            .as_deref()
+            == Some("1")
+}
+
+pub(crate) fn dialog_gcd_k5_apply_stream_controls_enabled() -> bool {
+    dialog_gcd_k5_clean_block_enabled()
+        && std::env::var("DIALOG_GCD_K5_APPLY_STREAM_CONTROLS")
+            .ok()
+            .as_deref()
+            == Some("1")
+}
+
+pub(crate) fn dialog_gcd_k5_apply_recompress_shift_enabled() -> bool {
+    dialog_gcd_k5_clean_block_enabled()
+        && std::env::var("DIALOG_GCD_K5_APPLY_RECOMPRESS_SHIFT")
+            .ok()
+            .as_deref()
+            == Some("1")
+}
+
+pub(crate) fn dialog_gcd_k5_free_clean_block_during_shift_enabled() -> bool {
+    dialog_gcd_k5_clean_block_enabled()
+        && std::env::var("DIALOG_GCD_K5_FREE_CLEAN_BLOCK_DURING_SHIFT")
+            .ok()
+            .as_deref()
+            == Some("1")
+}
+
+pub(crate) fn dialog_gcd_apply_inplace_raw_block_enabled() -> bool {
+    dialog_gcd_k2_apply_inplace_raw_block_enabled()
+        || dialog_gcd_k5_apply_inplace_raw_block_enabled()
+        || dialog_gcd_k5_apply_stream_controls_enabled()
+}
+
+fn dialog_gcd_apply_inplace_clean_scratch_bits() -> usize {
+    if dialog_gcd_k5_apply_inplace_raw_block_enabled() {
+        return std::env::var("DIALOG_GCD_K5_APPLY_INPLACE_SCRATCH_BITS")
+            .ok()
+            .and_then(|s| s.parse::<usize>().ok())
+            .map_or(dialog_gcd_block_bits(), |bits| bits.min(dialog_gcd_block_bits()));
+    }
+    dialog_gcd_block_bits()
+}
+
+fn dialog_gcd_k5_stream_clean_scratch_bits() -> usize {
+    std::env::var("DIALOG_GCD_K5_APPLY_STREAM_SCRATCH_BITS")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .map_or(0, |bits| bits.min(dialog_gcd_block_bits()))
+}
+
 pub(crate) fn dialog_gcd_reverse_raw_block_host<'a>(
     u: &'a [QubitId],
     compressed_log: &'a [QubitId],
@@ -1238,6 +1293,106 @@ pub(crate) fn dialog_gcd_k2_pair_inplace_clear_block(
     emit_dialog_gcd_k2_pair_core_encoder(b, &core);
 }
 
+pub(crate) fn dialog_gcd_k5_inplace_raw_frame(
+    compressed_block: &[QubitId],
+    zeros: [QubitId; 3],
+) -> [QubitId; 15] {
+    assert_eq!(compressed_block.len(), 12);
+    [
+        zeros[0],             // raw0, cleared by the pair01 encoder
+        compressed_block[0],  // raw1
+        compressed_block[2],  // raw2
+        compressed_block[3],  // raw3
+        zeros[1],             // raw4, cleared by the pair23 encoder
+        compressed_block[5],  // raw5
+        compressed_block[7],  // raw6
+        compressed_block[8],  // raw7
+        zeros[2],             // raw8, cleared by the 13->12 K5 codec
+        compressed_block[10], // raw9
+        compressed_block[1],  // s2_0
+        compressed_block[4],  // s2_1
+        compressed_block[6],  // s2_2
+        compressed_block[9],  // s2_3
+        compressed_block[11], // s2_4
+    ]
+}
+
+pub(crate) fn dialog_gcd_k5_inplace_decompress_block(
+    b: &mut B,
+    compressed_block: &[QubitId],
+    zeros: [QubitId; 3],
+    steps: usize,
+) -> [QubitId; 15] {
+    assert_eq!(steps, 5, "in-place K5 apply currently requires full blocks");
+    let raw_frame = dialog_gcd_k5_inplace_raw_frame(compressed_block, zeros);
+    let data = dialog_gcd_k5_data_from_raw(&raw_frame);
+    let ancilla = b.alloc_qubit();
+    emit_dialog_gcd_k5_clean_compressor_inverse(b, &data, ancilla);
+    b.free(ancilla);
+    emit_dialog_gcd_k5_pair_encoder_inverse(b, &dialog_gcd_k5_pair23(&raw_frame));
+    emit_dialog_gcd_k5_pair_encoder_inverse(b, &dialog_gcd_k5_pair01(&raw_frame));
+    raw_frame
+}
+
+pub(crate) fn dialog_gcd_k5_inplace_clear_block(
+    b: &mut B,
+    compressed_block: &[QubitId],
+    zeros: [QubitId; 3],
+    steps: usize,
+) {
+    assert_eq!(steps, 5, "in-place K5 apply currently requires full blocks");
+    let raw_frame = dialog_gcd_k5_inplace_raw_frame(compressed_block, zeros);
+    emit_dialog_gcd_k5_pair_encoder(b, &dialog_gcd_k5_pair01(&raw_frame));
+    emit_dialog_gcd_k5_pair_encoder(b, &dialog_gcd_k5_pair23(&raw_frame));
+    let data = dialog_gcd_k5_data_from_raw(&raw_frame);
+    let ancilla = b.alloc_qubit();
+    emit_dialog_gcd_k5_clean_compressor(b, &data, ancilla);
+    b.free(ancilla);
+}
+
+fn dialog_gcd_k5_xor_stream_controls(
+    b: &mut B,
+    compressed_block: &[QubitId],
+    zeros: [QubitId; 3],
+    slot: usize,
+    controls: [QubitId; 3],
+) {
+    assert!(slot < 5);
+    let raw_frame = dialog_gcd_k5_inplace_decompress_block(b, compressed_block, zeros, 5);
+    b.cx(raw_frame[2 * slot], controls[0]);
+    b.cx(raw_frame[2 * slot + 1], controls[1]);
+    b.cx(raw_frame[2 * dialog_gcd_sidecar_group_size() + slot], controls[2]);
+    dialog_gcd_k5_inplace_clear_block(b, compressed_block, zeros, 5);
+}
+
+fn dialog_gcd_k5_recompressed_shift_s2(
+    b: &mut B,
+    compressed_block: &[QubitId],
+    raw: &[QubitId],
+    slot: usize,
+    steps: usize,
+) -> QubitId {
+    let s2 = b.alloc_qubit();
+    b.cx(raw[2 * dialog_gcd_sidecar_group_size() + slot], s2);
+    dialog_gcd_clear_raw_block_copy(b, compressed_block, raw, steps);
+    b.free_vec(raw);
+    s2
+}
+
+fn dialog_gcd_k5_restore_recompressed_shift_s2(
+    b: &mut B,
+    compressed_block: &[QubitId],
+    raw: &[QubitId],
+    slot: usize,
+    steps: usize,
+    s2: QubitId,
+) {
+    b.reacquire_vec(raw);
+    dialog_gcd_copy_compressed_block_to_raw(b, compressed_block, raw, steps);
+    b.cx(raw[2 * dialog_gcd_sidecar_group_size() + slot], s2);
+    b.free(s2);
+}
+
 pub(crate) fn emit_dialog_gcd_compressed_sidecar_tobitvector_steps_block_lifecycle(
     b: &mut B,
     u: &[QubitId],
@@ -1671,30 +1826,127 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_block_lifecycle
 ) {
     assert_eq!(x.len(), N);
     assert_eq!(y.len(), N);
-    let inplace_raw = dialog_gcd_k2_apply_inplace_raw_block_enabled();
+    let inplace_k2 = dialog_gcd_k2_apply_inplace_raw_block_enabled();
+    let inplace_k5 = dialog_gcd_k5_apply_inplace_raw_block_enabled();
+    let inplace_stream = dialog_gcd_k5_apply_stream_controls_enabled();
+    let inplace_raw = inplace_k2 || inplace_k5 || inplace_stream;
     if inplace_raw {
         assert!(raw_block.is_empty());
     } else {
         assert_eq!(raw_block.len(), dialog_gcd_raw_block_len());
     }
-    let inplace_raw0 = if inplace_raw {
+    let inplace_raw0 = if inplace_k2 {
         Some(b.alloc_qubit())
     } else {
         None
     };
+    let inplace_k5_zeros = if inplace_k5 {
+        Some([b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()])
+    } else {
+        None
+    };
 
     for block in (0..dialog_gcd_compressed_sidecar_blocks()).rev() {
         let (start, end) = dialog_gcd_compressed_sidecar_block_step_range(block);
         let compressed_block = dialog_gcd_compressed_sidecar_block(compressed_log, start);
+        let steps = end - start;
+
+        if dialog_gcd_k5_apply_stream_controls_enabled() && steps == 5 {
+            for step in (start..end).rev() {
+                let slot = step - start;
+                let controls = [b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()];
+                let zeros = [b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()];
+                b.set_phase("dialog_gcd_compressed_block_apply_decompress_block");
+                dialog_gcd_k5_xor_stream_controls(b, compressed_block, zeros, slot, controls);
+                for zero in zeros {
+                    b.free(zero);
+                }
+                let b0 = controls[0];
+                let b0_and_b1 = controls[1];
+                let s2 = controls[2];
+
+                b.set_phase("dialog_gcd_compressed_block_apply_double_y");
+                let apply_k2 = dialog_gcd_k2_enabled()
+                    && std::env::var("DIALOG_GCD_K2_NO_APPLY").ok().as_deref() != Some("1");
+                if apply_k2 && dialog_gcd_apply_fused_fold_enabled() {
+                    dialog_gcd_fused_double_y(b, y, p, s2);
+                } else {
+                    mod_double_inplace_fast(b, y, p);
+                    if apply_k2 {
+                        cmod_double_inplace_lazy(b, y, p, s2);
+                    }
+                }
+
+                b.set_phase("dialog_gcd_compressed_block_apply_cadd");
+                if dialog_gcd_raw_apply_materialized_special_add_enabled() {
+                    let owned_clean_scratch =
+                        b.alloc_qubits(dialog_gcd_k5_stream_clean_scratch_bits());
+                    dialog_gcd_cmod_add_materialized_pseudomersenne_with_clean_scratch_at_step(
+                        b,
+                        y,
+                        x,
+                        b0,
+                        p,
+                        owned_clean_scratch.as_slice(),
+                        Some(step),
+                    );
+                    b.free_vec(&owned_clean_scratch);
+                } else if dialog_gcd_raw_apply_direct_special_add_enabled() {
+                    dialog_gcd_cmod_add_pseudomersenne_lowq(b, y, x, b0, p);
+                } else {
+                    cmod_add_qq_lowq(b, y, x, b0, p);
+                }
+
+                b.set_phase("dialog_gcd_compressed_block_apply_cswap");
+                for (&xi, &yi) in x.iter().zip(y.iter()) {
+                    cswap(b, b0_and_b1, xi, yi);
+                }
+
+                let zeros = [b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()];
+                b.set_phase("dialog_gcd_compressed_block_apply_clear_block_copy");
+                dialog_gcd_k5_xor_stream_controls(b, compressed_block, zeros, slot, controls);
+                for zero in zeros {
+                    b.free(zero);
+                }
+                for control in controls {
+                    b.free(control);
+                }
+            }
+            continue;
+        }
 
         b.set_phase("dialog_gcd_compressed_block_apply_decompress_block");
-        let raw_frame = inplace_raw0.map(|raw0| {
-            dialog_gcd_k2_pair_inplace_decompress_block(b, compressed_block, raw0, end - start)
-        });
+        let raw_frame = if let Some(raw0) = inplace_raw0 {
+            Some(dialog_gcd_k2_pair_inplace_decompress_block(
+                b,
+                compressed_block,
+                raw0,
+                steps,
+            ).to_vec())
+        } else if let Some(zeros) = inplace_k5_zeros.filter(|_| steps == 5) {
+            Some(dialog_gcd_k5_inplace_decompress_block(
+                b,
+                compressed_block,
+                zeros,
+                steps,
+            ).to_vec())
+        } else {
+            None
+        };
+        let owned_raw_block = if raw_frame.is_none() && inplace_raw {
+            b.alloc_qubits(dialog_gcd_raw_block_len())
+        } else {
+            Vec::new()
+        };
+        let raw_copy = if owned_raw_block.is_empty() {
+            raw_block
+        } else {
+            &owned_raw_block
+        };
         if raw_frame.is_none() {
-            dialog_gcd_copy_compressed_block_to_raw(b, compressed_block, raw_block, end - start);
+            dialog_gcd_copy_compressed_block_to_raw(b, compressed_block, raw_copy, steps);
         }
-        let raw = raw_frame.as_ref().map_or(raw_block, |frame| &frame[..]);
+        let raw = raw_frame.as_ref().map_or(raw_copy, |frame| &frame[..]);
         let block_clean_scratch = if !inplace_raw && dialog_gcd_apply_replay_swap_host_enabled() {
             compressed_block
         } else {
@@ -1709,10 +1961,32 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_block_lifecycle
             b.set_phase("dialog_gcd_compressed_block_apply_double_y");
             let apply_k2 = dialog_gcd_k2_enabled()
                 && std::env::var("DIALOG_GCD_K2_NO_APPLY").ok().as_deref() != Some("1");
+            let recompressed_s2 = if !inplace_raw && dialog_gcd_k5_apply_recompress_shift_enabled()
+            {
+                b.set_phase("dialog_gcd_compressed_block_apply_recompress_shift");
+                Some(dialog_gcd_k5_recompressed_shift_s2(
+                    b,
+                    compressed_block,
+                    raw,
+                    slot,
+                    steps,
+                ))
+            } else {
+                None
+            };
+            let free_clean_block_during_shift = !inplace_raw
+                && recompressed_s2.is_none()
+                && dialog_gcd_apply_replay_swap_host_enabled()
+                && dialog_gcd_k5_free_clean_block_during_shift_enabled();
+            if free_clean_block_during_shift {
+                b.free_vec(compressed_block);
+            }
+            b.set_phase("dialog_gcd_compressed_block_apply_double_y");
             if apply_k2 && dialog_gcd_apply_fused_fold_enabled() {
                 // Fuse mod_double_inplace_fast + cmod_double_inplace_lazy into a
                 // single shared carry chain (value-identical; see fn doc).
-                let s2 = raw[2 * dialog_gcd_sidecar_group_size() + slot];
+                let s2 = recompressed_s2
+                    .unwrap_or_else(|| raw[2 * dialog_gcd_sidecar_group_size() + slot]);
                 dialog_gcd_fused_double_y(b, y, p, s2);
             } else {
                 mod_double_inplace_fast(b, y, p);
@@ -1720,15 +1994,30 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_block_lifecycle
                     // mirror the forward K=2 second shift: conditional 2nd double of y.
                     // MUST use the lazy (Solinas, truncated) controlled double so it
                     // composes with the uncontrolled mod_double_inplace_fast above.
-                    let s2 = raw[2 * dialog_gcd_sidecar_group_size() + slot];
+                    let s2 = recompressed_s2
+                        .unwrap_or_else(|| raw[2 * dialog_gcd_sidecar_group_size() + slot]);
                     cmod_double_inplace_lazy(b, y, p, s2);
                 }
             }
+            if free_clean_block_during_shift {
+                b.reacquire_vec(compressed_block);
+            }
+            if let Some(s2) = recompressed_s2 {
+                b.set_phase("dialog_gcd_compressed_block_apply_restore_shift");
+                dialog_gcd_k5_restore_recompressed_shift_s2(
+                    b,
+                    compressed_block,
+                    raw,
+                    slot,
+                    steps,
+                    s2,
+                );
+            }
 
             b.set_phase("dialog_gcd_compressed_block_apply_cadd");
             if dialog_gcd_raw_apply_materialized_special_add_enabled() {
                 let owned_clean_scratch = if inplace_raw {
-                    b.alloc_qubits(dialog_gcd_block_bits())
+                    b.alloc_qubits(dialog_gcd_apply_inplace_clean_scratch_bits())
                 } else {
                     Vec::new()
                 };
@@ -1763,15 +2052,25 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_block_lifecycle
 
         b.set_phase("dialog_gcd_compressed_block_apply_clear_block_copy");
         if let Some(raw0) = inplace_raw0 {
-            dialog_gcd_k2_pair_inplace_clear_block(b, compressed_block, raw0, end - start);
+            dialog_gcd_k2_pair_inplace_clear_block(b, compressed_block, raw0, steps);
+        } else if let Some(zeros) = inplace_k5_zeros.filter(|_| steps == 5) {
+            dialog_gcd_k5_inplace_clear_block(b, compressed_block, zeros, steps);
         } else {
-            dialog_gcd_clear_raw_block_copy(b, compressed_block, raw_block, end - start);
+            dialog_gcd_clear_raw_block_copy(b, compressed_block, raw, steps);
+        }
+        if !owned_raw_block.is_empty() {
+            b.free_vec(&owned_raw_block);
         }
     }
 
     if let Some(raw0) = inplace_raw0 {
         b.free(raw0);
     }
+    if let Some(zeros) = inplace_k5_zeros {
+        for zero in zeros {
+            b.free(zero);
+        }
+    }
 }
 
 pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_reverse_exact_block_lifecycle(
@@ -1784,30 +2083,130 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_reverse_exact_b
 ) {
     assert_eq!(x.len(), N);
     assert_eq!(y.len(), N);
-    let inplace_raw = dialog_gcd_k2_apply_inplace_raw_block_enabled();
+    let inplace_k2 = dialog_gcd_k2_apply_inplace_raw_block_enabled();
+    let inplace_k5 = dialog_gcd_k5_apply_inplace_raw_block_enabled();
+    let inplace_stream = dialog_gcd_k5_apply_stream_controls_enabled();
+    let inplace_raw = inplace_k2 || inplace_k5 || inplace_stream;
     if inplace_raw {
         assert!(raw_block.is_empty());
     } else {
         assert_eq!(raw_block.len(), dialog_gcd_raw_block_len());
     }
-    let inplace_raw0 = if inplace_raw {
+    let inplace_raw0 = if inplace_k2 {
         Some(b.alloc_qubit())
     } else {
         None
     };
+    let inplace_k5_zeros = if inplace_k5 {
+        Some([b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()])
+    } else {
+        None
+    };
 
     for block in 0..dialog_gcd_compressed_sidecar_blocks() {
         let (start, end) = dialog_gcd_compressed_sidecar_block_step_range(block);
         let compressed_block = dialog_gcd_compressed_sidecar_block(compressed_log, start);
+        let steps = end - start;
+
+        if dialog_gcd_k5_apply_stream_controls_enabled() && steps == 5 {
+            for step in start..end {
+                let slot = step - start;
+                let controls = [b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()];
+                let zeros = [b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()];
+                b.set_phase("dialog_gcd_compressed_block_apply_reverse_decompress_block");
+                dialog_gcd_k5_xor_stream_controls(b, compressed_block, zeros, slot, controls);
+                for zero in zeros {
+                    b.free(zero);
+                }
+                let b0 = controls[0];
+                let b0_and_b1 = controls[1];
+                let s2 = controls[2];
+
+                b.set_phase("dialog_gcd_compressed_block_apply_reverse_cswap");
+                for (&xi, &yi) in x.iter().zip(y.iter()) {
+                    cswap(b, b0_and_b1, xi, yi);
+                }
+
+                b.set_phase("dialog_gcd_compressed_block_apply_reverse_csub");
+                if dialog_gcd_raw_apply_reverse_materialized_special_sub_enabled() {
+                    let owned_clean_scratch =
+                        b.alloc_qubits(dialog_gcd_k5_stream_clean_scratch_bits());
+                    dialog_gcd_cmod_sub_materialized_pseudomersenne_with_clean_scratch_at_step(
+                        b,
+                        y,
+                        x,
+                        b0,
+                        p,
+                        owned_clean_scratch.as_slice(),
+                        Some(step),
+                    );
+                    b.free_vec(&owned_clean_scratch);
+                } else if dialog_gcd_raw_apply_reverse_fast_sub_enabled() {
+                    cmod_sub_qq(b, y, x, b0, p);
+                } else {
+                    cmod_sub_qq_lowq(b, y, x, b0, p);
+                }
+
+                b.set_phase("dialog_gcd_compressed_block_apply_reverse_halve_y");
+                let apply_k2 = dialog_gcd_k2_enabled()
+                    && std::env::var("DIALOG_GCD_K2_NO_APPLY").ok().as_deref() != Some("1");
+                if apply_k2
+                    && dialog_gcd_apply_fused_fold_enabled()
+                    && std::env::var("DIALOG_GCD_FUSE_HALVE_OFF").ok().as_deref() != Some("1")
+                {
+                    dialog_gcd_fused_halve_y(b, y, p, s2);
+                } else {
+                    mod_halve_inplace_fast(b, y, p);
+                    if apply_k2 {
+                        cmod_halve_inplace_lazy(b, y, p, s2);
+                    }
+                }
+
+                let zeros = [b.alloc_qubit(), b.alloc_qubit(), b.alloc_qubit()];
+                b.set_phase("dialog_gcd_compressed_block_apply_reverse_clear_block_copy");
+                dialog_gcd_k5_xor_stream_controls(b, compressed_block, zeros, slot, controls);
+                for zero in zeros {
+                    b.free(zero);
+                }
+                for control in controls {
+                    b.free(control);
+                }
+            }
+            continue;
+        }
 
         b.set_phase("dialog_gcd_compressed_block_apply_reverse_decompress_block");
-        let raw_frame = inplace_raw0.map(|raw0| {
-            dialog_gcd_k2_pair_inplace_decompress_block(b, compressed_block, raw0, end - start)
-        });
+        let raw_frame = if let Some(raw0) = inplace_raw0 {
+            Some(dialog_gcd_k2_pair_inplace_decompress_block(
+                b,
+                compressed_block,
+                raw0,
+                steps,
+            ).to_vec())
+        } else if let Some(zeros) = inplace_k5_zeros.filter(|_| steps == 5) {
+            Some(dialog_gcd_k5_inplace_decompress_block(
+                b,
+                compressed_block,
+                zeros,
+                steps,
+            ).to_vec())
+        } else {
+            None
+        };
+        let owned_raw_block = if raw_frame.is_none() && inplace_raw {
+            b.alloc_qubits(dialog_gcd_raw_block_len())
+        } else {
+            Vec::new()
+        };
+        let raw_copy = if owned_raw_block.is_empty() {
+            raw_block
+        } else {
+            &owned_raw_block
+        };
         if raw_frame.is_none() {
-            dialog_gcd_copy_compressed_block_to_raw(b, compressed_block, raw_block, end - start);
+            dialog_gcd_copy_compressed_block_to_raw(b, compressed_block, raw_copy, steps);
         }
-        let raw = raw_frame.as_ref().map_or(raw_block, |frame| &frame[..]);
+        let raw = raw_frame.as_ref().map_or(raw_copy, |frame| &frame[..]);
         let block_clean_scratch = if !inplace_raw && dialog_gcd_apply_replay_swap_host_enabled() {
             compressed_block
         } else {
@@ -1827,7 +2226,7 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_reverse_exact_b
             b.set_phase("dialog_gcd_compressed_block_apply_reverse_csub");
             if dialog_gcd_raw_apply_reverse_materialized_special_sub_enabled() {
                 let owned_clean_scratch = if inplace_raw {
-                    b.alloc_qubits(dialog_gcd_block_bits())
+                    b.alloc_qubits(dialog_gcd_apply_inplace_clean_scratch_bits())
                 } else {
                     Vec::new()
                 };
@@ -1857,6 +2256,27 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_reverse_exact_b
             b.set_phase("dialog_gcd_compressed_block_apply_reverse_halve_y");
             let apply_k2 = dialog_gcd_k2_enabled()
                 && std::env::var("DIALOG_GCD_K2_NO_APPLY").ok().as_deref() != Some("1");
+            let recompressed_s2 = if !inplace_raw && dialog_gcd_k5_apply_recompress_shift_enabled()
+            {
+                b.set_phase("dialog_gcd_compressed_block_apply_reverse_recompress_shift");
+                Some(dialog_gcd_k5_recompressed_shift_s2(
+                    b,
+                    compressed_block,
+                    raw,
+                    slot,
+                    steps,
+                ))
+            } else {
+                None
+            };
+            let free_clean_block_during_shift = !inplace_raw
+                && recompressed_s2.is_none()
+                && dialog_gcd_apply_replay_swap_host_enabled()
+                && dialog_gcd_k5_free_clean_block_during_shift_enabled();
+            if free_clean_block_during_shift {
+                b.free_vec(compressed_block);
+            }
+            b.set_phase("dialog_gcd_compressed_block_apply_reverse_halve_y");
             if apply_k2
                 && dialog_gcd_apply_fused_fold_enabled()
                 && std::env::var("DIALOG_GCD_FUSE_HALVE_OFF").ok().as_deref() != Some("1")
@@ -1864,30 +2284,56 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_apply_bitvector_reverse_exact_b
                 // Fuse mod_halve_inplace_fast + cmod_halve_inplace_lazy into a
                 // single shared borrow chain (exact inverse of the fused double;
                 // see fn doc on dialog_gcd_fused_halve_y).
-                let s2 = raw[2 * dialog_gcd_sidecar_group_size() + slot];
+                let s2 = recompressed_s2
+                    .unwrap_or_else(|| raw[2 * dialog_gcd_sidecar_group_size() + slot]);
                 dialog_gcd_fused_halve_y(b, y, p, s2);
             } else {
                 mod_halve_inplace_fast(b, y, p);
                 if apply_k2 {
                     // mirror the forward K=2 second shift: conditional 2nd halve of y.
                     // MUST use the lazy (Solinas, truncated) controlled halve to match.
-                    let s2 = raw[2 * dialog_gcd_sidecar_group_size() + slot];
+                    let s2 = recompressed_s2
+                        .unwrap_or_else(|| raw[2 * dialog_gcd_sidecar_group_size() + slot]);
                     cmod_halve_inplace_lazy(b, y, p, s2);
                 }
             }
+            if free_clean_block_during_shift {
+                b.reacquire_vec(compressed_block);
+            }
+            if let Some(s2) = recompressed_s2 {
+                b.set_phase("dialog_gcd_compressed_block_apply_reverse_restore_shift");
+                dialog_gcd_k5_restore_recompressed_shift_s2(
+                    b,
+                    compressed_block,
+                    raw,
+                    slot,
+                    steps,
+                    s2,
+                );
+            }
         }
 
         b.set_phase("dialog_gcd_compressed_block_apply_reverse_clear_block_copy");
         if let Some(raw0) = inplace_raw0 {
-            dialog_gcd_k2_pair_inplace_clear_block(b, compressed_block, raw0, end - start);
+            dialog_gcd_k2_pair_inplace_clear_block(b, compressed_block, raw0, steps);
+        } else if let Some(zeros) = inplace_k5_zeros.filter(|_| steps == 5) {
+            dialog_gcd_k5_inplace_clear_block(b, compressed_block, zeros, steps);
         } else {
-            dialog_gcd_clear_raw_block_copy(b, compressed_block, raw_block, end - start);
+            dialog_gcd_clear_raw_block_copy(b, compressed_block, raw, steps);
+        }
+        if !owned_raw_block.is_empty() {
+            b.free_vec(&owned_raw_block);
         }
     }
 
     if let Some(raw0) = inplace_raw0 {
         b.free(raw0);
     }
+    if let Some(zeros) = inplace_k5_zeros {
+        for zero in zeros {
+            b.free(zero);
+        }
+    }
 }
 
 pub(crate) fn emit_dialog_gcd_compressed_sidecar_tobitvector_steps(
@@ -2188,7 +2634,7 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_ipmul_block_lifecycle(
         dialog_gcd_release_terminal_u(b, &u, runway.as_ref());
 
         b.set_phase("dialog_gcd_compressed_block_ipmul_apply_bitvector_reuse_factor_zero");
-        let inplace_apply_raw = dialog_gcd_k2_apply_inplace_raw_block_enabled();
+        let inplace_apply_raw = dialog_gcd_apply_inplace_raw_block_enabled();
         if inplace_apply_raw && !raw_block.is_empty() {
             b.free_vec(&raw_block);
         }
@@ -2468,7 +2914,7 @@ pub(crate) fn emit_dialog_gcd_compressed_sidecar_quotient_block_lifecycle(
         dialog_gcd_release_terminal_u(b, &u, runway.as_ref());
 
         b.set_phase("dialog_gcd_compressed_block_quotient_apply_reverse_reuse_factor_zero");
-        let inplace_apply_raw = dialog_gcd_k2_apply_inplace_raw_block_enabled();
+        let inplace_apply_raw = dialog_gcd_apply_inplace_raw_block_enabled();
         if inplace_apply_raw && !raw_block.is_empty() {
             b.free_vec(&raw_block);
         }
```

