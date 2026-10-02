# aacf05c — Square, `A` lane: add the `2^32` NAF term of `f·A_hi` as a direct shifted add instead of 22 more modular doublings (on the 1162-qubit tree)

| | |
| --- | --- |
| Contestant | gnuchev |
| Date | 2026-06-20 |
| Submission | `a6fe4c2` |
| Commit | `aacf05c604adce757b9e03adc0107408033ce2b2` |
| Result | 1162 qubits × 1,389,099 Toffoli = **1,614,133,038** |
| Base | `31421df` (jieyilong, the 1162-qubit tree): 1162 qubits × 1,391,406 Toffoli = 1,616,813,772 |
| Change vs base | qubits ±0, Toffoli −2,307, score −2,680,734 |
| Leaderboard Δ | −1,831,866, measured against the frontier at the time, `e25c7d8` (0xLucqs, 1164 × 1,388,286 = 1,615,964,904), which is **not** this commit's base |
| Family | Strength Reduction → solinas / NAF fold |
| Concepts | [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This ports the idea of [`e25c7d8`](e25c7d8.md) onto jieyilong's 1162-qubit
tree [`31421df`](31421df.md). In the Karatsuba square, the high half of
`A = lo²`, call it `A_hi` (128 bits), has to be added as `f·A_hi` with
`f = 2^32 + 2^10 − 2^6 + 2^4 + 1`. The base did that by doubling a copy of
`A_hi` modulo p 32 times, adding it at each NAF term, and halving it back 32
times. Since `A_hi·2^32 < 2^160` needs no reduction, this commit stops the
ramp after 10 doublings and adds the `2^32` term directly at bit offset 32.

That removes 22 doublings and 22 halvings, each a 52-bit `+f` window of 51
Toffoli on this tree (`PAD = 19`), about 2,244 Toffoli. The direct add also
uses the implicit-low-zero `mod_add_shifted_low`, a 224-bit adder instead of a
256-bit one, about 64 more. The measured drop is 2,307. Qubits stay at 1162.
The change is value-exact; the tail nonce was re-hunted.

## What changed and why it saves Toffoli

All circuit changes are in `src/point_add/trailmix_ludicrous/square.rs`.

**Background.** `mod_square_sub_pm_secp256k1_symmetric` computes
`out −= λ²` as `A + (C − A − B)·2^128 + B·2^256` (see
[`28fe2f2`](28fe2f2.md) and
[squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md)). For the
`A` lane it calls `apply_shifted_128(A, out, Add)`. That adds the low 128 bits
of `A` at bit 128 and passes `A[128..]` to `apply_f_times_value`, because
`A[128..]·2^256 ≡ f·A[128..]`. `apply_f_times_value` walks
`F_NAF_TERMS = [(0,Sub),(4,Sub),(6,Add),(10,Sub),(32,Sub)]` with
`arith::mod_double` before each term, a full-width `mod_add_lowpeak` /
`mod_sub` per term, and 32 `mod_double_reverse` at the end. Each doubling or
halving is one `+f` window over `LSBS = PAD + 33` bits. With `arith::PAD = 19`
on this tree that is 52 bits and 51 CCX (see
[modular-fold](../concepts/modular-fold.md)).

**The change.**

- New `apply_f_times_value_direct_shift32(value, out, op)`:
  - runs the same ramp over only `F_NAF_TERMS[..4]` (shifts 0, 4, 6, 10), so 10
    doublings, 4 full-width terms, 10 halvings;
  - then calls the new `apply_shift32_low_value(value, out, op)` for the
    `2^32` term.
- `apply_shift32_low_value` pads the value with zeros to 224 bits and calls
  `arith::mod_add_shifted_low` (or `mod_sub_shifted_low`) with shift 32. These
  were added in [`4ea8b74`](4ea8b74.md). They add the 224-bit operand into
  `out[32..256]` with an uncontrolled Cuccaro (about 2 Toffoli per bit), fold
  the carry-out with the usual `+f` window and clear it with the top-`MSBS`
  measured compare. The 32 low zeros are implicit, so no pad qubits and no
  adder bits are spent on them.
- The sign is the caller's `op`: for the `A` lane `op = Add`, and the
  `(32, Sub)` term flipped for an add is an add.
- `apply_shifted_128` becomes a wrapper of the new
  `apply_shifted_128_inner(value, out, op, direct_shift32_high)`. Only the
  `A` lane passes `env_flag("TLM_SQUARE_A_DIRECT_SHIFT32")`. The `C` lane
  (130-bit high part) and the `B` lanes keep the full ramp.
- `src/point_add/mod.rs`, `configure_q1162_rebased_ffg1_route()`: new default
  `TLM_SQUARE_A_DIRECT_SHIFT32=1`, and `DIALOG_TAIL_NONCE` 168011267 → 21059.

**Count.** 44 fewer fold windows × 51 = 2,244 Toffoli, plus a 224-bit instead of
256-bit register add for the last term, about 64. That is 2,308, against a
measured 2,307.

**Compared with `e25c7d8`.** 0xLucqs's version (on the 1164-qubit tree) has the
same ramp cut but adds the `2^32` term as a full 256-bit operand with 32 low
zero pads, through `mod_add_lowpeak`. This version uses the shifted-low adder
instead and is gated by its own knob, `TLM_SQUARE_A_DIRECT_SHIFT32`, instead of
`TLM_SQUARE_F_RAMP10_DIRECT32_TAGS`.

## Why it is still correct, and what it risks

- **Value-exact.** `A[128..]` is below `2^128`, so `A[128..]·2^k < 2^160` for
  every `k ≤ 32`. In the old ramp, doublings 11–32 never shifted out a 1, so
  their `+f` windows never fired, and the ramp value at shift 32 equalled the
  plain shifted limb. The new direct add computes the same value. The
  removed windows could not fire, so they carried no error.
- The direct add has the same kind of approximation as every other modular
  add: one `+f` window and one 19-bit truncated compare. It replaces one such
  add, so the failure set is essentially the base's.
- A failure would show as a classical error (wrong coordinate) or a phase
  error (wrong compare repair).
- The shipped nonce 21059 draws a clean set: 9,024 of 9,024 shots pass, with
  0 classical, 0 phase and 0 ancilla failures (avg 1,389,098.818 Toffoli, per
  the author's run).

## Classification rationale

This is a cheaper way to apply one NAF term of the Solinas fold by `f`: a
direct shifted add instead of a modular-doubling chain. That is strength
reduction of the NAF fold, the published label. As for `e25c7d8`, the
runner-up is dead-gate removal, since the dropped windows never fire.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 31421df -- src/point_add`.
   - Do not start from the git parent `e25c7d8`. That is 0xLucqs's 1164-qubit
     tree, and this commit was built on jieyilong's 1162-qubit `31421df`.
   - Against the parent, the diff is 400 lines in 6 files. It would add the
     whole q1162 budget-trim route of `31421df` (`gcd.rs`, `mod.rs`,
     `schedule.rs`, `arith.rs` `PAD`) and swap `e25c7d8`'s tagged
     `TLM_SQUARE_F_*` paths for this commit's.
   - Against `31421df`, `git diff --ignore-cr-at-eol 31421df aacf05c -- src/point_add`
     is 86 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol aacf05c -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*`, `LUD_*` or `CONSTPROP_*` environment variables set,
   because they override the defaults in `build()`. Expect:
   - 1162 qubits
   - 1,389,099 average Toffoli (1,389,098.818 before rounding)
   - score 1,614,133,038
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `21059` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 7cd3d1a..4d764e9 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1014,7 +1014,8 @@ fn configure_q1162_rebased_ffg1_route() {
     // This must run before the trailmix-ludicrous build() defaults below. The
     // env-scanned circuit used these as process env vars; setting them later in
     // configure_ecdsafail_submission_route() does not affect the trailmix path.
-    set_default_env("DIALOG_TAIL_NONCE", "168011267");
+    set_default_env("DIALOG_TAIL_NONCE", "21059");
+    set_default_env("TLM_SQUARE_A_DIRECT_SHIFT32", "1");
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
diff --git a/src/point_add/trailmix_ludicrous/square.rs b/src/point_add/trailmix_ludicrous/square.rs
index 5fe155d..ddb4957 100644
--- a/src/point_add/trailmix_ludicrous/square.rs
+++ b/src/point_add/trailmix_ludicrous/square.rs
@@ -270,7 +270,70 @@ fn apply_f_times_value(circ: &mut B, value: &[QubitId], output_reg: &[QubitId],
     free_zeroes(circ, pads);
 }
 
-fn apply_shifted_128(circ: &mut B, value: &[QubitId], output_reg: &[QubitId], op: ShiftOp) {
+fn env_flag(name: &str) -> bool {
+    std::env::var(name)
+        .ok()
+        .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
+        .unwrap_or(false)
+}
+
+fn apply_shift32_low_value(circ: &mut B, value: &[QubitId], output_reg: &[QubitId], op: ShiftOp) {
+    const SHIFT: usize = 32;
+    assert!(
+        value.len() <= N - SHIFT,
+        "direct shift32 lane expects the value to fit below bit 224"
+    );
+    let pads = alloc_zeroes(circ, N - SHIFT - value.len());
+    let mut operand = Vec::with_capacity(N - SHIFT);
+    operand.extend_from_slice(value);
+    operand.extend_from_slice(&pads);
+    match op {
+        ShiftOp::Add => mod_add_shifted_low(circ, &operand, output_reg, SHIFT),
+        ShiftOp::Sub => mod_sub_shifted_low(circ, &operand, output_reg, SHIFT),
+    }
+    free_zeroes(circ, pads);
+}
+
+fn apply_f_times_value_direct_shift32(
+    circ: &mut B,
+    value: &[QubitId],
+    output_reg: &[QubitId],
+    op: ShiftOp,
+) {
+    assert!(value.len() <= N - 32, "direct shift32 f-fold value must fit below overflow");
+    let pads = alloc_zeroes(circ, N + 1 - value.len());
+    let mut ext = Vec::with_capacity(N + 1);
+    ext.extend_from_slice(value);
+    ext.extend_from_slice(&pads);
+
+    let mut shifted = 0usize;
+    for &(shift, sub_f_op) in &F_NAF_TERMS[..4] {
+        while shifted < shift {
+            arith::mod_double(circ, &ext);
+            shifted += 1;
+        }
+        let term_op = match op {
+            ShiftOp::Sub => sub_f_op,
+            ShiftOp::Add => flipped(sub_f_op),
+        };
+        apply_full_width(circ, &ext[..N], output_reg, term_op);
+    }
+    while shifted > 0 {
+        arith::mod_double_reverse(circ, &ext);
+        shifted -= 1;
+    }
+    free_zeroes(circ, pads);
+
+    apply_shift32_low_value(circ, value, output_reg, op);
+}
+
+fn apply_shifted_128_inner(
+    circ: &mut B,
+    value: &[QubitId],
+    output_reg: &[QubitId],
+    op: ShiftOp,
+    direct_shift32_high: bool,
+) {
     assert!(value.len() <= N + 2, "128-shifted half product must be at most 258 bits");
     let low_len = value.len().min(128);
     let low_pads = alloc_zeroes(circ, 128);
@@ -284,10 +347,18 @@ fn apply_shifted_128(circ: &mut B, value: &[QubitId], output_reg: &[QubitId], op
     free_zeroes(circ, low_pads);
 
     if value.len() > 128 {
-        apply_f_times_value(circ, &value[128..], output_reg, op);
+        if direct_shift32_high {
+            apply_f_times_value_direct_shift32(circ, &value[128..], output_reg, op);
+        } else {
+            apply_f_times_value(circ, &value[128..], output_reg, op);
+        }
     }
 }
 
+fn apply_shifted_128(circ: &mut B, value: &[QubitId], output_reg: &[QubitId], op: ShiftOp) {
+    apply_shifted_128_inner(circ, value, output_reg, op, false);
+}
+
 fn build_sum_hi_lo(circ: &mut B, lambda: &[QubitId]) -> Vec<QubitId> {
     let sum = alloc_zeroes(circ, 129);
     for i in 0..128 {
@@ -358,7 +429,13 @@ pub fn mod_square_sub_pm_secp256k1_symmetric(circ: &mut B, lambda: &[QubitId], o
     let mut a_prod: Vec<QubitId> = Vec::with_capacity(2 * lo.len());
     symmetric_square_into_prod(circ, lo, &mut a_prod);
     apply_unshifted_value(circ, &a_prod, output_reg, ShiftOp::Sub);
-    apply_shifted_128(circ, &a_prod, output_reg, ShiftOp::Add);
+    apply_shifted_128_inner(
+        circ,
+        &a_prod,
+        output_reg,
+        ShiftOp::Add,
+        env_flag("TLM_SQUARE_A_DIRECT_SHIFT32"),
+    );
     symmetric_square_into_prod_reverse(circ, lo, a_prod);
 
     let hi = &lambda[128..N];
```

