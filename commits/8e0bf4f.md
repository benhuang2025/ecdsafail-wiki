# 8e0bf4f — Four one-notch truncations: apply double and fold carry windows, apply clean compare, and the GCD branch-compare cap 48 → 46

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-10 |
| Submission | `62d9029` |
| Commit | `8e0bf4f8a70e7aa96e84fe058a09c9a5ac4ce66c` |
| Result | 1285 qubits × 1,374,414 Toffoli = **1,766,121,990** |
| Base | `f6f9536` (git parent, the author's previous submission): 1285 qubits × 1,376,005 Toffoli = 1,768,166,425 |
| Change vs base | qubits ±0, Toffoli −1,591, score −2,044,435 (leaderboard Δ −2,044,435) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Four truncation knobs of the K=2 dialog GCD each get one notch tighter (the
branch-compare cap gets two). Three are in the apply phase, where the
transcript is replayed on the 256-bit payload; one is in the GCD walk. Each
drops a bit that is zero on almost every input, and each saves roughly one
Toffoli per call. The author's count-only measurement was −518, −516, −506 and
−404 emitted Toffoli; the scored average falls by 1,591. Qubits stay at 1285.

All four are probabilistic, so the tail nonce was re-hunted. The author's note
says they measured, before the hunt, that this bundle barely raised the
expected number of failing shots per draw, so the hunt was cheap.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`. The apply phase runs twice per shot (forward apply in
the in-place multiply, reverse apply in the division), each over 258 steps.

1. **`KAL_DOUBLE_CARRY_TRUNC_W`: 20 → 19.**
   - Read by `double_carry_trunc_window()` (`arith/const_arith.rs`). In
     `dialog_gcd_fused_double_y` and `dialog_gcd_fused_halve_y`
     (`rounds/dialog/compressed.rs`), the shared fold adds or subtracts
     `c·e + 2c·d` (with `c = 2^32 + 977`) through
     `cadd/csub_per_position_controls_trunc`, and the carry ripple stops at
     `last = min(254, 33 + w)`.
   - One bit less shortens every fused double and halve ripple by one stage:
     2 × 258 calls, which matches the author's −518 emitted.
   - Above bit 33 the constant has no set bits, so the ripple only carries a
     run of 1s in `y`. Cutting it at `33 + w` is wrong only if the carry
     survives `w + 1` more bits, about 2^−(w+1) per call. See
     [modular-fold](../concepts/modular-fold.md).
2. **`KAL_FOLD_CARRY_TRUNC_W`: 19 → 18.**
   - Read by `fold_carry_trunc_window()`. In the materialized pseudo-Mersenne
     apply add and subtract (`dialog_gcd_cmod_add_materialized_pseudomersenne_*`
     and `..._cmod_sub_...` in `rounds/dialog/mod.rs`), phase
     `..._overflow_fold`, the overflow correction `acc[..LSBS] += c` is done by
     `cadd_nbit_const_direct_trunc_fast(..., w)` (and its subtract mirror),
     whose carry tail stops `w` bits above the top bit of `c`.
   - One bit less per apply add or subtract: 2 × 258 calls, the author's −516.
     Same 2^−(w+1)-per-call risk.
3. **`DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS`: 20 → 19.**
   - After the fold, the overflow flag `acc_ovf` is cleared by a compare:
     after a modular add, "the sum wrapped" is the same as "the result is
     below the addend", and only the top `k` bits are compared
     (`dialog_gcd_special_overflow_clean_compare_bits(step)`). On this route
     (`APPLY_CHUNKED_F_BLOCKS=5`) the chunked add does it as `hmr(acc_ovf)`
     plus the conditioned `cmp_lt_phase_conditioned_with_cin(&acc[N−k..], &a[N−k..], …)`
     of [98dd2ad](98dd2ad.md). The subtract's underflow clean
     (`dialog_gcd_clean_truncated_underflow`) is the mirror, with
     `dialog_gcd_special_underflow_clean_compare_bits(step)`.
   - The global value goes 20 → 19. Six add steps keep their own value from
     `DIALOG_GCD_SPECIAL_OVERFLOW_CLEAN_STEP_BITS`
     (`113:21,131:21,142:22,187:23,205:22,210:21`) and four subtract steps
     from `DIALOG_GCD_SPECIAL_UNDERFLOW_CLEAN_STEP_BITS`
     (`42:22,91:22,118:22,149:21`), so this saves one bit on
     (258 − 6) + (258 − 4) = 506 calls, the author's −506.
   - The compare is wrong when `acc` and the addend tie on their top 19 bits, about
     2^−19 per call. The flag then stays dirty, which is an ancilla or phase
     failure.
4. **`DIALOG_GCD_COMPARE_BITS`: 48 → 46.**
   - With `DIALOG_GCD_PA9024_COMPARE_SCHEDULE=1` the walk's branch compare at
     step `s` uses `min(SCHEDULE[s], cap, active_width)` top bits
     (`dialog_gcd_compare_bits_for_step`, `rounds/dialog/config.rs`).
     `SCHEDULE` is a 258-entry table of the largest width observed to be
     needed at each step over 8 million sampled inputs.
   - This knob is the cap. Replaying the schedule with slope 1.015 and margin
     10, the cap binds on 55 of the 258 steps, and saves 101 compare bits per
     walk pass. The compare (`dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted`)
     costs about one Toffoli per bit, so four walk passes give 404, exactly the
     author's emitted figure.
   - The schedule entries above 46 (up to 55) are the maxima seen in sampling,
     so capping them means some sampled inputs needed more bits. A compare that
     ties on its top 46 bits picks the wrong branch; the walk then records a
     wrong decision, a classical mismatch.
5. **`DIALOG_TAIL_NONCE`: 1000005782829 → 1200069204974.**

**Emitted against executed.** The four emitted savings add up to 1,944, but
the scored average falls by 1,591. Part of the cleanup in these phases runs
only under a measurement outcome (see
[measurement-uncompute](../concepts/measurement-uncompute.md)), so a bit
removed there counts less than one Toffoli on average, and the new nonce draws
a different set of shots. The per-knob split of the 1,591 was not measured.

## Why it is still correct, and what it risks

None of the four is exact. Each cut makes some rare input fail:

- The double and fold carry windows fail when a carry runs further than `w`
  bits past the top bit of the folded constant (bit 33 for the double, bit 32
  for the add/sub fold), about 2^−20 and 2^−19 per call. The dropped carry
  makes the result wrong, which is a classical mismatch.
- The apply clean compare fails on a top-19-bit tie, which leaves a dirty
  flag: ancilla or phase garbage.
- The branch-compare cap fails when `u` and `v` agree on their top 46 bits at
  a step where the branch matters, which gives a wrong transcript and a
  classical mismatch.

The code comments call these "value-exact on the reachable support", meaning
the dropped bits are zero on the inputs that occur in practice. The shipped
nonce `1200069204974` draws a clean set: 9,024 of 9,024 shots, with 0
classical, 0 phase and 0 ancilla failures. The submission note describes the
two carry windows as being "in the Kaliski path"; in this tree they are read
by the dialog-GCD apply phase. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

All four knobs narrow a carry window or a comparator, so this is
comparator/width truncation. There is no runner-up.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f6f9536 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol f6f9536 8e0bf4f -- src/point_add` is 10 lines
   in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 8e0bf4f -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or `ROUND84_*` environment variables set, because they
   override the route defaults. Expect:
   - 1285 qubits
   - 1,374,414 average Toffoli (rounded)
   - score 1,766,121,990
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=1200069204974` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 5dbdf3e..eb79381 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1044,14 +1044,14 @@ fn configure_ecdsafail_submission_route() {
     // prior #1 2,017,979,899 by 1,362,894). Value-exact on the reachable support
     // (dropped double-carry bit is 0 there, ~2^-22/call otherwise); residual
     // failures are Fiat-Shamir phase, dodged by a fresh tail nonce (re-hunted below).
-    set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "20");
+    set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "19");
     // Likewise give back the FOLD-carry truncation bit for the final-window W2
     // island; the Toffoli budget still beats the 1320q frontier.
     // Re-tighten 24 -> 22 on the W2 base (the lazy-Solinas fold-carry window had
     // been left loose). Value-exact on the reachable support (the dropped fold
     // carry bits are 0 there); residual failures are pure Fiat-Shamir, dodged by
     // the shared re-rolled tail nonce below.
-    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "19");
+    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
     set_default_env("DIALOG_GCD_ROUND763_COMPRESS_LEVER", "1");
     set_default_env("DIALOG_GCD_MEASURED_UNDERFLOW_GATE", "1");
@@ -1085,7 +1085,7 @@ fn configure_ecdsafail_submission_route() {
     // Both-phase apply fold-fusion: spend comparator bits back to cb=52 (the
     // exact-screen zone) while preserving a clean Fiat-Shamir
     // nonce; the fold-fusion's -25k Toffoli keeps the score well under 2B.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "48");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "46");
     // Apply-phase overflow-clean comparator narrowed 23 -> 22 -> 21 -> 20. The
     // materialized_special "overflow_clean" cmp_lt only needs the top
     // `apply_clean_compare_bits` of (acc, f) to resolve the modular-overflow
@@ -1097,7 +1097,7 @@ fn configure_ecdsafail_submission_route() {
     // pre-filter + bit-exact quantum confirm, validated 0/0/0 over all 9024
     // shots: 1309 x 1,503,355 = 1,967,891,695, beats the 1,968,064,139 frontier
     // by 172,444).
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "19");
     set_default_env("DIALOG_GCD_APPLY_BOUNDARY_CONDITIONAL_REPLAY", "1");  // BAKED: condrep ON for env-less grader build
     set_default_env("DIALOG_GCD_SELECTED_BODY_STREAM_SUFFIX_MAP", "3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:2,11:2,12:2,13:2,14:2,15:2,16:2,17:2,18:1,19:2,21:1");  // BAKED: codex 1285q peak-drop (stream selected high bits through low-qubit suffix)
     set_default_env("DIALOG_GCD_SELECTED_BODY_STREAM_TOPCLEAN_MAP", "4:2,5:6,6:8,7:10,8:6,9:10,10:18,11:8,12:6,13:10,14:6,15:8,16:2,17:6,19:2");  // BAKED: replace expensive streamed carry relief with cheaper top-clean carry relief
@@ -1408,7 +1408,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "1000005782829");
+    set_default_env("DIALOG_TAIL_NONCE", "1200069204974");
     set_default_env("ROUND84_FOLD_FAST_ADD", "1");  // round84 Solinas-fold small adders coherent->measured-fast (-1,434 exec-T, peak-neutral 1285)
     set_default_env("ROUND84_BIGFOLD_SPLIT", "34");  // round84 BIG-fold adders -> asymmetric 2-block windowed measured (s=34 peak-neutral 1285, -2,124 exec-T)
     set_default_env("DIALOG_GCD_CTRL_LOWQ_MEASURED", "1");  // body stream-suffix ctrl-ride uncompute coherent->measured (-528 exec-T, peak-neutral 1285); island re-hunted to nonce above
```

