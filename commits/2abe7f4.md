# 2abe7f4 — Narrow the constant-subtract carry-tail window from 96 to 59 bits

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `f751e0b` |
| Commit | `2abe7f477ced6351aaf65f81fc4608c5f8771291` |
| Result | 2309 qubits × 2,842,943 Toffoli = **6,564,355,387** |
| Base | `fc8b9e6` (git parent, the author's previous submission): 2309 qubits × 2,865,661 Toffoli = 6,616,811,249 |
| Change vs base | qubits ±0, Toffoli −22,718, score −52,455,862 (leaderboard Δ −52,455,862) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [modular-fold](../concepts/modular-fold.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit changes one constant, the carry-tail window `W` of the
register-free controlled constant subtractor, from 96 to 59. Each call of the
subtractor now computes 37 fewer borrow bits, and each of those cost one
Toffoli. Over about 614 calls per point addition this saves 22,718 average
Toffoli at the same 2309 qubits.

The window is still far wider than any borrow run seen in simulation, so the
arithmetic is effectively exact. The value 59 was chosen because its op
stream draws a clean test set. The same knob was later cut again, from 49 to
36, in [`a97b4e9`](a97b4e9.md).

## What changed and why it saves Toffoli

- `src/point_add/kaliski_state.rs`, `kal_carrytail_w()`: the default of
  `KAL_CARRYTAIL_W` goes from 96 to 59. The comment on `kal_carrytail_mode()`
  is updated with a re-check of the ADD path (see below).
- **The subtractor.** `csub_nbit_const_direct_fast(acc, c, ctrl)` in
  `src/point_add/cuccaro.rs` subtracts `ctrl ? c : 0` from `acc` without
  loading `c` into a register. Here `c = 2^256 − p = 2^32 + 977`, the Solinas
  constant (see [modular-fold](../concepts/modular-fold.md)). It runs three
  passes:
  1. A forward borrow sweep writes `borrow_{i+1}` into a fresh wire for
     `i < cut`.
  2. The difference pass XORs the constant and the borrows into `acc`.
  3. A reverse sweep erases each borrow wire with `hmr` and repairs the phase
     with classically conditioned `CZ`s, which cost no Toffoli (see
     [measurement-uncompute](../concepts/measurement-uncompute.md)).
- **What `W` controls.** `cut = kal_carrytail_count(n) = min(n − 1, K0 + W)`,
  with `KAL_CARRYTAIL_K0 = 33`, one above the constant's top set bit 32. All
  three passes use the same `cut`, so the truncated adder stays
  self-consistent. The borrow chain now stops at bit 92 instead of bit 129.
- **Why it saves Toffoli.** Above bit 32 every constant bit is 0. A borrow
  there is `NOT acc_i AND borrow_i`, one CCX. 37 fewer positions save 37
  Toffoli per call. 22,718 / 37 = 614 calls. The callers are the pair1
  `mod_halve` steps in the Kaliski inverse, the Solinas folds and the
  low-scratch modular adders.
- **ADD path stays off.** The mode stays `"sub"`. The new comment records that
  truncating the matching constant adder (`KAL_CARRYTAIL_TRUNC=both` or `add`)
  gives exactly 141 phase-failure batches at margins 3, 4 and 5. That adder's
  reverse sweep uses `NOT acc_i_final`, which leaks phase when the chain is
  cut.

## Why it is still correct, and what it risks

Above bit 32, a borrow can only propagate through a run of 0-bits of `acc`.
A 3M-trial Monte Carlo in the code comments found the longest run is 19 bits,
which reaches bit 51. With `W = 59` the chain covers up to bit 92, so there
are about 40 bits of slack. A dropped borrow would leave a wrong difference
and a classical mismatch, with a probability far below 2^-30 per call.

The binding constraint is the test island. There is no nonce in this era:
each value of `W` changes the op stream and so draws a different 9,024-shot
test set. The author swept `W` at W-TRUNC margin 3 with the full trusted
evaluator. Clean sets came out at W ∈ {82, 75, 69, 59}. The neighbours of 59
(61, 57, 55, …) fail, and nothing clean was found down to 44. The failures
come from the other approximate knobs (W-TRUNC, iteration counts) meeting a
hard input in the new draw, not from the carry-tail. This draw is clean:
0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The change shortens a borrow chain, so fold/carry truncation fits. The
runner-up is comparator/width truncation, since `W` is a width, but the
thing being cut is a carry chain.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout fc8b9e6 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol fc8b9e6 2abe7f4 -- src/point_add` is
   23 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 2abe7f4 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`
   or other tuning environment variables set, and with `DUMMY_TOFFOLIS` unset.
   Expect:
   - 2309 qubits
   - 2,842,943 average Toffoli (rounded)
   - score 6,564,355,387
   - 0 classical, 0 phase and 0 ancilla failures

There is no nonce in this tree: the test set is a hash of the op stream, so the
score only reproduces with an identical op stream. Any other change draws a new
island.

### Patch

```diff
diff --git a/src/point_add/kaliski_state.rs b/src/point_add/kaliski_state.rs
index 312a4ac..3d60982 100644
--- a/src/point_add/kaliski_state.rs
+++ b/src/point_add/kaliski_state.rs
@@ -131,8 +131,11 @@ pub(crate) fn kal_wtrunc_width(iter_idx: usize, n: usize) -> usize {
 /// "0"/"off" = disabled.  DEFAULT = "sub": the SUB path's measured-uncompute is
 /// truncation-clean, while the ADD path's `!acc_i_final` reverse sweep leaks a
 /// relative phase under truncation (measured: 141 phase-garbage batches at every
-/// W/margin) and so is left OFF.  The banked default is the validated clean
-/// island SUB W=96 + WTRUNC margin=4 (9024-clean, score 6,626,924,669).
+/// W/margin) and so is left OFF.  Re-confirmed on the current island:
+/// KAL_CARRYTAIL_TRUNC=both/add = EXACTLY 141 phase-garbage at margins 3/4/5
+/// (structural !acc_i_final reverse-sweep wall, island-invariant).  The banked
+/// default is the validated clean island SUB W=59 + WTRUNC margin=3 (9024-clean,
+/// score 6,564,355,387).
 fn kal_carrytail_mode() -> &'static str {
     match std::env::var("KAL_CARRYTAIL_TRUNC").ok().as_deref() {
         Some("1") | Some("both") => "both",
@@ -152,9 +155,19 @@ pub(crate) fn kal_carrytail_sub_enabled() -> bool {
 }
 
 pub(crate) fn kal_carrytail_w() -> usize {
-    // Banked clean island: SUB W=96 (paired with WTRUNC margin=4). The cliff is
-    // below W=80 m=4 (2 mismatch / 1 phase); W=96 m=4 is 9024-clean.
-    env_usize("KAL_CARRYTAIL_W").unwrap_or(96)
+    // Banked clean island: SUB W=59 (paired with WTRUNC margin=3). The carry-tail
+    // SUB borrow chain runs to bit 33+59=92, far above the 3M-MC max realizable
+    // sub-borrow run (19, i.e. bit 51) → arithmetically exact. Below the SUB-borrow
+    // safety floor the truncation itself is sound; the validity constraint is the
+    // Fiat-Shamir ISLAND LOTTERY: each W value re-rolls the test inputs, and only
+    // some W land a 9024-clean island at margin=3. Full isolated-eval W-sweep at
+    // m=3 (each = trusted eval_circuit over 9024 shots) found the clean islands
+    // W∈{82,75,69,59}; W=59 is the deepest/best (2,842,943 avg-exec T × 2309 peak
+    // = 6,564,355,387, 0/0). Neighbours of 59 (61,57,55,..) all REJECT on island
+    // stragglers (not truncation errors). margin=3 is the floor on the W=59 island
+    // (W=59 m=2 and m=4 untested-here; the W-sweep used m=3 throughout). Down to
+    // W=44 no further clean island appeared. KAL_CARRYTAIL_W env override remains.
+    env_usize("KAL_CARRYTAIL_W").unwrap_or(59)
 }
 
 pub(crate) fn kal_carrytail_k0() -> usize {
```

