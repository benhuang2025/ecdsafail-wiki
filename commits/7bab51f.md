# 7bab51f — Re-map the tail3 transcript codec to a cheaper decoder and spend part of the saving on targeted width repairs

| | |
| --- | --- |
| Contestant | nasqret |
| Date | 2026-06-14 |
| Submission | `65e8bcb` |
| Commit | `7bab51f8402dd015c34c801adc9e0b3bbb0f58f0` |
| Result | 1170 qubits × 1,434,070 Toffoli = **1,677,861,900** |
| Base | `f50ae3b` (git parent, gnuchev): 1170 qubits × 1,434,496 Toffoli = 1,678,360,320 |
| Change vs base | qubits ±0, Toffoli −426, score −498,420 (leaderboard Δ −498,420) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The circuit is the 1170-qubit dialog-GCD route. Its GCD writes one small
transcript word per step, and the words are packed into compressed blocks
because only a few bit patterns can occur. The last three steps (258 = 5·51 + 3)
form a "tail3" block whose 9 raw bits take only 32 values, so they are stored
in 5 code bits. This commit replaces the code assignment (which 5-bit code
each of the 32 patterns gets) with one whose decoder polynomials are much
cheaper: 287 Toffoli per full decode instead of 393.

It then spends part of that saving on safety. A budgeted optimizer widened 17
fold carry windows by one bit and added about 190 per-step and per-site
overrides (131 apply-phase, 57 square-site) that make cleanup comparators
wider than the default. These
"repairs" lower the number of hard inputs, so a clean nonce is easier to find.
The net saving is 426 average Toffoli at the same 1170 qubits.

## What changed and why it saves Toffoli

### 1. New tail3 TOP32 codec (`src/point_add/rounds/dialog/compressed.rs`)

- Background (see [transcript-codecs](../concepts/transcript-codecs.md)): the three tail steps each leave a
  3-bit digit. `dialog_gcd_k5_tail3_top32_raw_word()` scatters the 9 bits onto
  raw-block wires `[0, 1, 2, 3, 4, 5, 10, 11, 12]`. Only the 32 patterns in
  `DIALOG_GCD_K5_TAIL3_TOP32_SUPPORT` are reachable, so the block keeps a 5-bit
  code instead of the 9 raw bits.
- The code is described by two polynomial maps over GF(2), in algebraic normal
  form (ANF). Each entry is a monomial given as a bit mask, and each output bit
  is the XOR of its monomials.
  - `..._ENCODER_ANF` (5 rows, monomials over the 9 raw bits, degree ≤ 2) plus
    `..._CODE_CONSTANT` give code = f(raw).
  - `..._DECODER_ANF` (9 rows, monomials over the 5 code bits, degree up to 5)
    give raw = g(code).
- `dialog_gcd_k5_tail3_top32_toggle_raw_from_code()` emits each decoder
  monomial with `dialog_gcd_toggle_mcx_with_dirty()`. A degree-d monomial
  costs 0, 0, 1, 4, 10 and 22 CCX for d = 0 to 5 (a dirty-ancilla ladder).
  Compress and decompress both run the decoder, and the streaming apply decodes
  slot by slot (`..._toggle_slot_raw_from_code`).
- Old → new values:
  - `DIALOG_GCD_K5_TAIL3_TOP32_CODE_CONSTANT`: 29 → 25.
  - `DIALOG_GCD_K5_TAIL3_TOP32_ENCODER_ANF`: new masks. Both versions have 12
    degree-2 monomials, so the encoder costs 12 CCX either way.
  - `DIALOG_GCD_K5_TAIL3_TOP32_DECODER_ANF`: new masks. Counting monomials by
    degree, the old decoder has 49, 35, 16 and 2 monomials of degree 2, 3, 4
    and 5, which is 393 CCX. The new one has 33, 30, 9 and 2, which is 287 CCX.
  - `..._SUPPORT` (the 32 reachable patterns) is unchanged.
- The submission note calls the new assignment "affine299". Both old and new
  maps are bijections on the support: for all 32 patterns,
  decode(encode(raw)) = raw (checked by porting `..._code_word` and
  `..._decode_word` to Python). The codec self-test
  `DIALOG_GCD_K5_TAIL3_TOP32_SELFTEST` checks the same thing in the circuit.

### 2. Width repairs (`src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`)

Every one of these makes a truncated operation wider than before. They cost
Toffoli and remove failure modes.

- **Fused-fold carry windows.** `DIALOG_GCD_FOLD_CARRY_TRUNC_STEP_WINDOWS` gets
  15 new entries at 19 bits (steps 9, 24, 41, 55, 77, 81, 82, 87, 129, 134,
  157, 160, 174, 205, 216), against the global `DIALOG_GCD_FOLD_CARRY_TRUNC_W
  = 18`. `dialog_gcd_fused_fold_carry_trunc_window(step)` uses it to cap the
  carry ripple of the fused pseudo-Mersenne fold in each GCD step. A wider cap
  means fewer carries escape and get dropped. See
  [modular-fold](../concepts/modular-fold.md). Each entry is paired with a
  matching `DIALOG_GCD_FOLD_PARK_LOW_CARRIES_STEP_MAP` entry at 16, against the
  default 15.
- **Special-fold carry windows.** `DIALOG_GCD_SPECIAL_FOLD_CARRY_TRUNC_STEP_WINDOWS`
  adds steps 110 and 204 at 19, paired with
  `DIALOG_GCD_SPECIAL_FOLD_PARK_LOW_CARRIES_STEP_MAP` at 14 (default 13). With
  item 1 this is the "17 one-bit fold-width repairs" of the submission note.
- **Apply-phase cleanup compares.** `DIALOG_GCD_SPECIAL_OVERFLOW_CLEAN_STEP_BITS`
  grows from 6 to 71 per-step entries, and
  `DIALOG_GCD_SPECIAL_UNDERFLOW_CLEAN_STEP_BITS` from 4 to 70. All values are
  20 to 26 bits against the default `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS = 19`,
  and the one changed old entry, step 131, goes from 21 to 22. These are the
  top-bit compares that clean the overflow/underflow flag after each
  controlled modular add or subtract in the apply phase (see
  [`f50ae3b`](f50ae3b.md)).
- **Square-row cleanup compares.** New `SQUARE_ROW_WINDOW_CLEAN_SITE_BITS`,
  with 57 entries `row:window:direction:bits` at 19 to 22 bits. It is read by
  `square_row_window_clean_compare_bits()` in `arith/multiply.rs` and
  overrides the per-row and default (18) widths for one boundary in one
  direction (`f` = forward square, `r` = inverse). Every entry is wider than
  what that site had before. See [`6878ef8`](6878ef8.md).
- The cleanup compares run as phase repairs after an `hmr`, only on the shots
  where the measurement bit is 1, so a wider compare costs about half a
  Toffoli per bit on average. See
  [measurement-uncompute](../concepts/measurement-uncompute.md). The
  submission note says the phase-cleanup repairs were chosen under an
  80-Toffoli emitted budget.
- `DIALOG_TAIL_NONCE`: `"26008558798"` → `"3480010331559"`.

The decoder saves about 106 Toffoli at each full-block decode, plus the
per-slot decodes. The repairs give some of that back. The measured net is
−426 average Toffoli.

## Why it is still correct, and what it risks

- **Exact.** The codec swap is exact: both maps encode the same 32 reachable
  patterns one-to-one and decode them back. A pattern outside the support
  could not be encoded by either version, and that risk is unchanged.
- **Safer.** All the width changes are widenings, so each one removes failure
  cases:
  - a fold carry that escaped an 18-bit window would have been a classical
    error;
  - a tied top-bit cleanup compare would have been a phase error.
- **Probabilistic.** The remaining truncations are the base's, at the base's
  widths or wider.
- **Nonce.** The submission note says the route was searched with the exact
  serialized-circuit filter over all 9,024 shots. Nonce `3480010331559` has 0
  hard failures, and the benchmark gives 0 classical, 0 phase and 0 ancilla
  failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label is comparator/width truncation. The diff does not narrow
anything, though: every width change widens a window. The Toffoli saving comes
from the tail3 codec re-map, which is a Codec / Encoding change (closest
existing type: trailmix / K5 codec, since this is the K5 transcript-block
codec). The repairs are a Lambda budget choice, as in the `ROUNDS_MUL`
give-back of [`8d7051b`](8d7051b.md). The header keeps the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f50ae3b -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol f50ae3b 7bab51f -- src/point_add` is
   48 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol 7bab51f -- src/point_add`
   should print nothing.
4. **Optional codec self-test:**
   `DIALOG_GCD_K5_TAIL3_TOP32_SELFTEST=1 DIALOG_GCD_K5_TAIL3_TOP32_SELFTEST_ONLY=1 cargo run --release --bin build_circuit`.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `SQUARE_*` or `KAL_*` environment variables set. Expect:
   - 1170 qubits
   - 1,434,070 average Toffoli (1,434,070.266 before rounding)
   - score 1,677,861,900
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `3480010331559` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index e92efae..bdbd38f 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1030,7 +1030,7 @@ fn configure_ecdsafail_submission_route() {
     );
     set_default_env(
         "DIALOG_GCD_FOLD_CARRY_TRUNC_STEP_WINDOWS",
-        "0:20,3:19,8:19,10:19,21:20,22:19,26:19,33:19,34:19,37:20,42:20,51:19,65:20,73:19,86:19,97:19,104:19,109:19,110:19,120:19,132:20,141:20,142:19,146:19,169:19,170:20,177:19,191:19,192:19,198:19,206:19,212:19,215:19,217:19,224:20,228:19",
+        "0:20,3:19,8:19,9:19,10:19,21:20,22:19,24:19,26:19,33:19,34:19,37:20,41:19,42:20,51:19,55:19,65:20,73:19,77:19,81:19,82:19,86:19,87:19,97:19,104:19,109:19,110:19,120:19,129:19,132:20,134:19,141:20,142:19,146:19,157:19,160:19,169:19,170:20,174:19,177:19,191:19,192:19,198:19,205:19,206:19,212:19,215:19,216:19,217:19,224:20,228:19",
     );
     set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("DIALOG_GCD_FOLD_FREED_TAIL", "1");
@@ -1041,7 +1041,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_FOLD_PARK_LOW_CARRIES", "15");
     set_default_env(
         "DIALOG_GCD_FOLD_PARK_LOW_CARRIES_STEP_MAP",
-        "0:17,3:16,8:16,10:16,21:17,22:16,26:16,33:16,34:16,37:17,42:17,51:16,65:17,73:16,86:16,97:16,104:16,109:16,110:16,120:16,132:17,141:17,142:16,146:16,169:16,170:17,177:16,191:16,192:16,198:16,206:16,212:16,215:16,217:16,224:17,228:16",
+        "0:17,3:16,8:16,9:16,10:16,21:17,22:16,24:16,26:16,33:16,34:16,37:17,41:16,42:17,51:16,55:16,65:17,73:16,77:16,81:16,82:16,86:16,87:16,97:16,104:16,109:16,110:16,120:16,129:16,132:17,134:16,141:17,142:16,146:16,157:16,160:16,169:16,170:17,174:16,177:16,191:16,192:16,198:16,205:16,206:16,212:16,215:16,216:16,217:16,224:17,228:16",
     );
     set_default_env("DIALOG_GCD_K2", "1");
     set_default_env("DIALOG_GCD_K5_CLEAN_BLOCK", "1");
@@ -1065,26 +1065,26 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_SPECIAL_FOLD_BORROW_CARRIES", "1");
     set_default_env(
         "DIALOG_GCD_SPECIAL_FOLD_CARRY_TRUNC_STEP_WINDOWS",
-        "10:19,11:19,21:20,63:19,74:19,100:19,107:19,118:19,135:19,136:19,137:19,188:20,227:20,241:19",
+        "10:19,11:19,21:20,63:19,74:19,100:19,107:19,110:19,118:19,135:19,136:19,137:19,188:20,204:19,227:20,241:19",
     );
     set_default_env("DIALOG_GCD_SPECIAL_FOLD_PARK_LOW_CARRIES", "13");
     set_default_env(
         "DIALOG_GCD_SPECIAL_FOLD_PARK_LOW_CARRIES_STEP_MAP",
-        "10:14,11:14,21:15,63:14,74:14,100:14,107:14,118:14,135:14,136:14,137:14,188:15,227:15,241:14",
+        "10:14,11:14,21:15,63:14,74:14,100:14,107:14,110:14,118:14,135:14,136:14,137:14,188:15,204:14,227:15,241:14",
     );
     set_default_env("DIALOG_GCD_SPECIAL_FOLD_RELEASE_SCRATCH", "1");
     set_default_env(
         "DIALOG_GCD_SPECIAL_OVERFLOW_CLEAN_STEP_BITS",
-        "113:21,131:21,142:22,187:23,205:22,210:21",
+        "1:24,4:21,6:25,7:20,10:22,11:20,19:21,21:21,22:21,23:23,28:21,30:22,32:20,33:24,34:25,48:21,49:22,55:22,62:23,64:20,66:21,71:22,86:20,92:21,113:21,116:21,118:20,119:24,120:21,121:20,127:20,129:22,131:22,142:22,144:21,145:23,147:21,151:23,153:23,154:23,155:20,156:24,159:22,161:24,165:21,166:21,168:21,173:20,175:21,178:21,184:22,185:20,187:23,188:22,190:20,193:21,194:22,196:20,197:21,199:21,203:22,205:22,209:20,210:21,213:20,217:22,221:21,222:23,229:21,236:21,241:21",
     );
     set_default_env(
         "DIALOG_GCD_SPECIAL_UNDERFLOW_CLEAN_STEP_BITS",
-        "42:22,91:22,118:22,149:21",
+        "3:21,5:21,10:23,11:22,14:22,17:20,27:22,33:20,34:22,38:21,42:22,47:21,50:22,51:21,53:20,54:21,58:21,60:21,65:21,67:23,68:25,73:20,74:20,75:23,77:21,78:20,84:21,89:23,91:22,95:22,98:26,103:21,109:22,110:22,114:22,118:22,127:26,135:20,136:20,137:22,143:21,149:21,152:20,154:26,155:20,156:22,157:20,158:26,166:20,178:20,181:20,186:24,188:25,191:21,194:20,198:20,200:21,201:21,202:23,203:23,204:22,212:25,213:20,214:22,221:20,223:21,228:21,231:23,243:21,246:20",
     );
     set_default_env("DIALOG_GCD_TOBITVECTOR_CSWAP_BODY_TRIM", "0");
     set_default_env("DIALOG_GCD_WIDTH_MARGIN", "10");
     set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1015");
-    set_default_env("DIALOG_TAIL_NONCE", "26008558798");
+    set_default_env("DIALOG_TAIL_NONCE", "3480010331559");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "19");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("SQUARE_ROW_MAX_SEG", "143");
@@ -1093,6 +1093,10 @@ fn configure_ecdsafail_submission_route() {
         "SQUARE_ROW_WINDOW_CLEAN_ROW_BITS",
         "2:20,11:20,12:20,13:21,16:22,19:20,20:21,21:20,26:21,29:21,32:21,37:21,44:22,46:20,53:21,56:20,64:20,70:20,75:20,78:20,87:20",
     );
+    set_default_env(
+        "SQUARE_ROW_WINDOW_CLEAN_SITE_BITS",
+        "1:0:f:19,3:0:r:21,9:0:f:22,10:0:r:21,13:0:r:22,14:0:r:20,15:0:r:19,17:0:r:20,26:0:f:22,36:0:f:20,38:0:f:20,38:0:r:20,39:0:r:19,40:0:r:22,41:0:r:19,42:0:r:20,43:0:r:19,45:0:r:19,47:0:f:22,47:0:r:19,48:0:r:20,50:0:f:22,50:0:r:22,51:0:f:22,54:0:f:19,57:0:r:19,59:0:f:19,60:0:f:19,62:0:f:22,62:0:r:21,63:0:f:20,65:0:f:19,66:0:f:21,66:0:r:21,67:0:f:19,68:0:r:21,71:0:r:20,72:0:f:21,73:0:r:21,74:0:r:19,76:0:r:21,79:0:r:20,81:0:f:20,83:0:r:22,89:0:r:19,90:0:r:21,91:0:f:21,92:0:r:21,95:0:r:20,97:0:r:21,102:0:f:20,103:0:r:19,104:0:r:19,107:0:f:20,109:0:f:21,110:0:f:19,110:0:r:20",
+    );
     set_default_env("SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR", "1");
 
     set_default_env("SKIP_ALT_SEED_CHECKS", "1");
diff --git a/src/point_add/rounds/dialog/compressed.rs b/src/point_add/rounds/dialog/compressed.rs
index d3151a5..2a41fd6 100644
--- a/src/point_add/rounds/dialog/compressed.rs
+++ b/src/point_add/rounds/dialog/compressed.rs
@@ -88,24 +88,24 @@ const DIALOG_GCD_K5_HEAD11_DATA_WIRES: [usize; 11] =
 const DIALOG_GCD_K5_TAIL3_DATA_WIRES: [usize; 5] = [1, 10, 2, 3, 11];
 const DIALOG_GCD_K5_TAIL3_TOP32_RAW_WIRES: [usize; 9] = [0, 1, 2, 3, 4, 5, 10, 11, 12];
 const DIALOG_GCD_K5_TAIL3_TOP32_STREAM_SCRATCH_WIRES: [usize; 5] = [6, 7, 8, 9, 13];
-const DIALOG_GCD_K5_TAIL3_TOP32_CODE_CONSTANT: u8 = 29;
+const DIALOG_GCD_K5_TAIL3_TOP32_CODE_CONSTANT: u8 = 25;
 const DIALOG_GCD_K5_TAIL3_TOP32_ENCODER_ANF: [&[u16]; 5] = [
-    &[1, 2, 4, 8, 16, 32, 64, 128, 5, 24],
-    &[1, 4, 8, 16, 32, 64, 256, 18, 34, 264],
-    &[1, 2, 16, 256, 18, 258, 132],
-    &[8, 32, 64, 128, 256, 65],
-    &[16, 256, 34, 72, 80],
+    &[1, 2, 4, 32, 34, 64, 128],
+    &[4, 10, 16, 20, 24, 32, 64, 136, 256],
+    &[1, 6, 8, 16, 34, 128],
+    &[6, 32, 64],
+    &[4, 6, 8, 10, 32, 80, 128, 130, 256],
 ];
 const DIALOG_GCD_K5_TAIL3_TOP32_DECODER_ANF: [&[u16]; 9] = [
-    &[0, 1, 5, 6, 7, 9, 14, 17, 18, 19, 20, 22, 24, 31],
-    &[4, 6, 7, 9, 10, 14, 16, 17, 18, 21, 22, 24, 27, 28],
-    &[2, 5, 8, 10, 13, 14, 15, 16, 18, 23, 24, 26, 30],
-    &[3, 7, 11, 15, 18, 19, 20, 21, 24, 26, 30],
-    &[0, 1, 3, 5, 6, 8, 9, 11, 12, 16, 18, 20, 23, 24, 25, 27, 28],
-    &[4, 5, 6, 7, 12, 13, 14, 15, 20, 22, 28, 30],
-    &[0, 3, 7, 10, 11, 12, 16, 19, 20, 22, 23, 29],
-    &[1, 3, 5, 6, 8, 9, 11, 12, 16, 20, 22, 23, 24, 25, 26, 29],
-    &[0, 3, 4, 5, 6, 11, 16, 17, 18, 21, 27, 29, 31],
+    &[0, 6, 7, 9, 10, 17, 19, 22, 23, 24, 25, 29, 31],
+    &[0, 2, 7, 8, 10, 14, 16, 19, 24],
+    &[0, 16, 17, 19, 20, 24, 25, 26, 28],
+    &[0, 1, 2, 3, 4, 5, 6, 8, 11, 12, 15, 16, 18, 21, 26, 28],
+    &[0, 3, 5, 6, 7, 8, 10, 11, 12, 14, 15, 16, 17, 18, 20, 21, 25],
+    &[26, 27],
+    &[2, 7, 10, 14, 16, 18, 22, 23, 24],
+    &[1, 6, 7, 8, 9, 10, 16, 18, 19, 20, 27, 28, 29, 30],
+    &[0, 9, 13, 22, 24, 28, 31],
 ];
 pub(crate) const DIALOG_GCD_K5_TAIL3_TOP32_SUPPORT: [u16; 32] = [
     0x124, 0x125, 0x12b, 0x129, 0x128, 0x12f, 0x12d, 0x14b,
```

