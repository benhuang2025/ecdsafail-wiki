# cddd5df — Replace the Kaliski inversions with a dialog binary-GCD that divides once and multiplies once, 2708 → 1698 qubits

| | |
| --- | --- |
| Contestant | pldallairedemers |
| Date | 2026-06-02 |
| Submission | `0c1d4d9` |
| Commit | `cddd5dfeca39a1f92e957b164a331931b7689e67` |
| Result | 1698 qubits × 2,447,846 Toffoli = **4,156,442,508** |
| Base | `8631b04` (Gajesh2007, 30 May): 2708 qubits × 3,904,100 Toffoli = 10,572,302,800 |
| Change vs base | qubits −1010, Toffoli −1,456,254, score −6,415,860,292 |
| Leaderboard Δ | −964,247,614, measured against the frontier at the time, the git parent `cef001a` (owizdom, 2006 × 2,552,687 = 5,120,690,122), which is **not** this commit's base. That is the largest single leaderboard Δ of the contest |
| Family | Windowing → two-jump inversion base (published label; see Classification rationale) |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **B**: almost the whole of `src/point_add` is copied from the commit; the patch covers only `fermat_inv.rs` |

## Summary

Point addition needs λ = (y₁ − y₂)/(x₁ − x₂) mod p, and later a multiply by
λ. Before this commit the frontier did this with reversible Kaliski
inversions. Each Kaliski walk keeps `u`, `v`, and both Bézout coefficients
`r`, `s` live, plus one history bit per iteration, and the result then has to
be multiplied in separately.

This commit replaces the whole point-addition code with the author's own
research tree ("TensorFurnace"). Its shipped route is a **dialog GCD**, in
Schrottenloher's sense:

1. Run a plain binary GCD on `(u, v) = (p, a)` and record only its branch
   decisions, 2 bits per step, in a quantum transcript (the "dialog").
2. Replay those decisions on a second pair of registers, mod p. Replayed
   forwards, they divide by `a`. Replayed backwards, they multiply by `a`.
3. Run the GCD backwards to restore `a` and erase the transcript.

The point addition uses this twice: once to divide (`dy/dx = λ`) and once to
multiply (`λ·(x₂ − x₃)`). The GCD never holds Bézout coefficients. The
transcript is packed 3 steps into 5 qubits. During the replay, the GCD
registers that are known to be finished are released or reused. So the peak
drops from 2708 to 1698. That is 308 fewer than the 2006-qubit Kaliski
frontier `cef001a`, and Toffoli is also 104,841 lower than that frontier.
Against the stated base `8631b04`, the score falls by 61%.

## What changed and why it is cheaper

### The shipped route (`src/point_add/mod.rs`, 30,707 lines)

The file holds many alternative routes, benches and research probes. All of
them are behind environment variables. `build_builder()` first calls
`configure_ecdsafail_submission_route()`, which sets these defaults (only if
unset):

| variable | value | meaning |
| --- | --- | --- |
| `DIALOG_GCD_RAW_PA` | 1 | take the `emit_dialog_gcd_raw_pa` route |
| `DIALOG_GCD_ACTIVE_ITERATIONS` | 399 | GCD steps per run (max 402) |
| `DIALOG_GCD_COMPARE_BITS` | 75 | width of the truncated `u > v` compare |
| `DIALOG_GCD_PA9024_COMPARE_SCHEDULE` | 0 | do not use the per-step compare table `DIALOG_GCD_PA9024_COMPARE_SCHEDULE[399]` |
| `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` | 20 | width of the compare that clears the overflow flag in the replay adds |
| `DIALOG_GCD_COMPRESSED_SIDECAR_LOG`, `..._COMPRESSED_BLOCK_LIFECYCLE` | 1 | 3-steps-in-5-qubits transcript, decoded one block at a time |
| `DIALOG_GCD_RAW_TOBITVECTOR_VARIABLE_WIDTH` | 1 | shrink the GCD register widths with the step number |
| `DIALOG_GCD_RAW_TOBITVECTOR_MATERIALIZED_SUB` | 1 | controlled subtract as "load `ctrl·u`, fast subtract, measure the load out" |
| `DIALOG_GCD_RAW_TOBITVECTOR_BORROW_FUTURE_LOG_CARRIES` | 1 | the adder's carry register is lent from still-empty transcript slots |
| `DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE`, `..._IPMUL_TERMINAL_REUSE`, `..._IPMUL_CLEAR_P_RESIDUAL` | 1 | free `u` and reuse the zeroed `v` register during the replay |
| `DIALOG_GCD_RAW_APPLY_MATERIALIZED_SPECIAL_ADD`, `..._REVERSE_MATERIALIZED_SPECIAL_SUB`, `..._TRUNCATED_CLEAN` | 1 | replay adds and subtracts in the "special pseudo-Mersenne" form below |
| `ROUND84_XTAIL_SCHOOLBOOK` | 1 | the λ² step uses `squaring_sub_from_acc_schoolbook` |
| `SKIP_ALT_SEED_CHECKS` | 1 | skip the builder's own alternate-seed self-check |

**Point-addition shell, `emit_dialog_gcd_raw_pa(tx, ty, ox, oy)`.** Here
`(tx, ty)` is the quantum point and `(ox, oy)` the classical one.

1. `tx -= ox`, `ty -= oy` give `dx`, `dy`.
2. `emit_dialog_gcd_raw_quotient(tx, ty)`: `ty := dy/dx = λ`, and `tx` is
   restored to `dx`.
3. `round84_emit_fused_square_xtail`: `tx -= λ²`, `tx += 2·ox`, negate. This
   gives `tx = x₃`.
4. `tx -= ox`, negate: `tx = ox − x₃`.
5. `emit_dialog_gcd_raw_ipmul(tx, ty)`: `ty := λ·(ox − x₃)`, and `tx` is
   restored.
6. `ty -= oy` gives `y₃`. Then negate `tx` and add `ox` to get back `x₃`.

**One GCD step** (`emit_dialog_gcd_compressed_sidecar_tobitvector_steps_block_lifecycle`).
Start with `u = p` (X gates on a fresh register) and `v = a`, the factor
register itself. Step `s` works on the low `w(s)` bits only:

```
b0  ^= v[0]                       # v odd?
cmp  = [u > v] on the top 75 bits of the w(s)-bit slices   (computed, used, uncomputed)
b01 ^= b0 AND cmp
if b01: swap(u, v)                # w(s) controlled swaps
if b0:  v -= u                    # now v is even and >= 0
v >>= 1                           # wire rotation, 0 Toffoli
```

This is Stein's binary GCD with "swap so that `u ≤ v`, then subtract".
Starting from `(p, a)` with gcd 1, it ends at `(u, v) = (1, 0)`. After that,
further steps do nothing. The pair `(b0, b0∧b1)` takes only three values:
00, 10 or 11.

- Width schedule `dialog_gcd_tobitvector_active_width(s)`:
  `w(s) = 256 − 0.7075·s + 37`, rounded up to even and clamped to 256. It is
  full width through step 55 and falls to 12 at step 398. It is an empirical
  envelope of `max(bitlen(u), bitlen(v))`, with a margin of 37 bits.
- The compare is `dialog_gcd_cmp_gt_truncated_into_width`: `cmp_lt_into` on
  the top `min(75, w)` bits, at 2 Toffoli per bit, and run twice per step.
- The controlled subtract is `dialog_gcd_controlled_sub_selected`. It loads
  `gated = b0·u` with `w` CCX, runs `sub_nbit_qq_fast_borrowed_carries`, then
  clears `gated` with `hmr` + `cz_if` (measured uncompute, 0 Toffoli). The
  `w − 1` carry qubits are lent from transcript slots that later blocks have
  not written yet (`dialog_gcd_compressed_sidecar_future_carry_slice`). Late
  in the run, when not enough future slots remain, the adder allocates its
  own carries.
- Cost per step: about `3·w(s)` for the swap, load and subtract, plus
  `4·min(75, w(s))` for the two compares. This model reproduces the Toffoli
  deltas of the follow-up commits exactly (see [`541bd85`](541bd85.md) and
  [`8cb350c`](8cb350c.md)).

**Transcript compression** (`emit_dialog_gcd_round763_compressor`). Three
steps give 6 raw bits but only 3³ = 27 reachable patterns, which fit in 5
bits. The steps of one block write into a 6-qubit `raw_block`. A fixed
reversible circuit (9 CCX and 1 CX) then maps every reachable pattern to one
whose 6th bit is 0, and the 5 code bits are swapped into the block's slot of
`compressed_log`. The log is 133 blocks × 5 = 665 qubits, against 798 raw.
Decoding is the inverse circuit. The replay works on a CX copy of the block
(`dialog_gcd_copy_compressed_block_to_raw`) and erases the copy afterwards.
Each encode or decode costs 9 Toffoli.

**Replay as divide** (`..._apply_bitvector_reverse_exact_block_lifecycle`, steps 0 → 398).
For a fixed transcript, the GCD is a linear map `M` with `M(p, a) = (1, 0)`.
Mod p, `p ≡ 0`, so `M(0, a) = (1, 0)` and `M(0, y) = (y/a, 0)`. The replay
applies `M` mod p to `(x, y) = (factor, target)` = `(0, dy)`, where `factor`
is the GCD's `v` register, now 0. Per step it runs:

1. `cswap(b0∧b1, x, y)`, 256 bits;
2. `y -= b0·x mod p` (`dialog_gcd_cmod_sub_materialized_pseudomersenne`);
3. `y := y/2 mod p` (`mod_halve_inplace_fast`).

The result `dy/dx` ends in the factor lane, and the code swaps it into
`target`.

**Replay as multiply** (`..._apply_bitvector_block_lifecycle`, steps 398 → 0).
Here the inverse step is applied: `y := 2y mod p`, then `y += b0·x mod p`,
then `cswap`. This gives `M⁻¹(t, 0) = t·(p, a)`. Starting from
`(x, y) = (target, factor) = (t, 0)`, the factor lane ends holding `t·a`. The
target lane ends holding the bit pattern of p, which
`..._clear_p_residual_source_lane` erases with X gates. The two lanes are then
swapped. So a multiply costs the same as a divide: 2 GCD passes plus 1
replay, and it needs no 512-bit product register.

**Terminal reuse.** After the forward GCD, `u = 1` and `v = 0`. The code
applies `X(u[0])` and frees all of `u` (256 qubits) for the replay. It uses
the zeroed `v` (the caller's factor register) as the second replay lane.
Afterwards it re-acquires `u`, seeds it with `X(u[0])` = 1, and runs the GCD
backwards (`..._tobitvector_steps_reverse_block_lifecycle`) from `(1, 0)`.
That restores `(p, a)` and clears the transcript.

**Replay adds** ("special pseudo-Mersenne", `c = 2²⁵⁶ − p = 2³² + 977`).

- Load `f = ctrl·x` (256 CCX), then a fast 257-bit add into `y`. If that
  overflows, add `c` to only the low 73 bits (`DIALOG_GCD_SPECIAL_ADD_LSBS`).
- The overflow flag is cleared by recomputing it as `y < f`, compared only on
  the top 20 bits.
- `f` is cleared by measurement.
- A sum in `[p, 2²⁵⁶)` is left unreduced. The source comment calls this "the
  approximation budgeted by the caller". It has probability about 2⁻²²⁴.
- The subtract is the mirror image. In this commit it still uses a slow
  `sub_nbit_qq` (later made fast by [`c813ee5`](c813ee5.md)) and clears `f`
  with 256 CCX (later measured, [`6447611`](6447611.md)).

**Where the Toffoli goes.** From the width schedule, the four GCD passes (a
forward and a backward pass for each run) cost about 1.16 M. Most of the other
~1.29 M is the two 399-step replays, at roughly 1,400–1,600 Toffoli per step
(a 256-bit cswap, the load and add or subtract, the fold, and the
double or halve). The λ² square and the small modular ops make up the rest.
These figures are my estimates from the code. I did not run a phase trace.

**Where the qubits go.** At the first GCD step of the divide, the live
registers are `tx`, `ty` (512), `compressed_log` (665), `raw_block` (6), `u`
(256) and `gated` (256, with its carries borrowed from the log). That is
1,695 plus a few single-qubit temporaries, which matches the reported 1698.
The replay phases sit at about the same level, because `u` is freed and the
256-bit `f` load register takes its place. In the Kaliski tree, by contrast,
`u`, `v_w`, `r`, `s` (4 × 256) and the history bits were all live inside the
inversion.

### Other files copied from the commit

- **`venting.rs` (rewritten, 3,410 lines) and `fermat_inv.rs` (patched below).**
  They add vented and dirty-borrow adders and "clean" Fermat-inversion, Horner
  multiply and square helpers, used by the alternative `COMPACT_POINT_ADD` and
  `one_inv` routes. I did not trace whether the shipped route calls any of
  them.
- **26 new `.rs` modules**, all off the shipped route. 16 are declared
  `pub mod` in `mod.rs` and compiled; 8 more are declared only under
  `#[cfg(test)]` (`coset_proto`, `kaliski_linear_transform`, `kim_inv_circuit`,
  `kim_proto`, `luo_proto`, `primitive_costs`, `scratch600_frontier`,
  `single_inv_numeric`); `round326_b5_exact_cover_terms.rs` is `include!`d by
  `round218_b5_transport.rs`; and `lut_proto.rs` is not declared, so it is not
  compiled. They are: Bernstein–Yang research (`by.rs`, 16,365 lines),
  single-inversion numerics (`single_inv_numeric.rs`, 45,615 lines),
  half-GCD and Kaliski-variant prototypes (`halfgcd_*`, `kaliski_jump.rs`,
  `kaliski_linear_transform.rs`, `kaliski_equiv.rs`,
  `kaliski_classical_replay.rs`, `unconditional_kal.rs`), the "round218 b5"
  transport and selector routes, the Kim, Luo, LUT and coset prototypes, cost
  models (`primitive_costs.rs`, `microbench.rs`), `scratch600_frontier.rs`,
  `source_live_d1.rs` and `test_timeout.rs`.
- **`round331_b5_old_g0_full_eraser.kmx`**: a generated gate list
  (`APPEND_TO_REGISTER …`) that `round218_b5_transport.rs` loads by name. It is
  vendored so that every compile-time include resolves inside
  `src/point_add`. It is off the shipped route.
- **23 `.md` research notes** (plans, cost models, logs). They are not
  compiled.

## Why it is still correct, and what it risks

- **Exact parts.** The binary-GCD recurrence and its replay are exact linear
  algebra mod p. The swap, halving, transcript codec and terminal reuse are
  exact whenever the GCD really ends at `(1, 0)`. The measured clears (`hmr`
  plus `cz_if`) are exact uncomputes.
- **Probabilistic parts.** Each of these can fail on rare inputs.
  - *Step count 399.* An input whose GCD needs more steps does not reach
    `(1, 0)`. Then `X(u[0])` and the free of `u` leave garbage, and the replay
    lane is not zero.
  - *Width schedule (margin 37).* An input whose `u` or `v` is still wider
    than `w(s)` loses its top bits.
  - *75-bit compare.* If the top bits of the two slices are equal, the swap
    decision can be wrong, and `v −= u` goes negative.
  - *Replay overflow handling.* The 20-bit compare that clears the overflow
    flag can fail when `y` and `f` agree on their top 20 bits after an
    overflow, with probability about 2⁻²⁰ per such add. The 73-bit fold drops
    a carry with probability about 2⁻⁴¹, and the unreduced-sum case is about
    2⁻²²⁴.
- A GCD failure shows as a classical mismatch, with phase and ancilla garbage
  from the reset of a nonzero `u`. A failed overflow clear shows as ancilla or
  phase garbage, because the flag is freed while nonzero.
- This commit has no reroll knob. The op stream as built happens to draw a
  clean set. The author reports 9,024 of 9,024 shots, with 0 classical, 0
  phase and 0 ancilla failures, and says tighter per-step compare schedules
  "were not stable under the ecdsa.fail full 9024-shot seed". The next commit,
  [`541bd85`](541bd85.md), adds the `DIALOG_GCD_REROLL` knob, and every later
  tightening of this route uses it. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label is Windowing → two-jump inversion base. I read
"two-jump" as the two dialog-GCD runs, one dividing and one multiplying. The
code has no jump-2 (double-halving) step and no windowed table lookup. Each
step halves once and records one 2-bit symbol. The change is a replacement
of the inversion and multiplication algorithm, from Kaliski with separate
multiplies to a dialog binary GCD used as both divider and multiplier, with
the affine shell kept the same. That fits **Algorithmic Substitution →
inversion/division algorithm swap** better, the label used for the later
ping-pong swap [`897dda2`](897dda2.md).

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 8631b04 -- src/point_add`.
   - The base has only three files (`mod.rs`, `fermat_inv.rs`, `venting.rs`),
     all of which this commit rewrites or edits, so it is the closest accepted
     tree. Even so, `git diff --ignore-cr-at-eol 8631b04 cddd5df -- src/point_add`
     is 143,660 lines in 53 files.
   - The git parent `cef001a` is worse: 155,346 lines. Against it, the diff
     would also delete the 17 split-out Kaliski modules (`kaliski_walk.rs`,
     `kaliski_state.rs`, `point_add.rs`, `solinas.rs`, …) of the 2006-qubit
     line. This commit was not built on that line.
2. **Copy the commit's files.** Nothing is deleted by this commit, so no
   `rm` is needed. These are
   hand-written research code, notes and one generated `.kmx` gate list,
   described above. They are copied because together they are about 143,000
   lines.

   ```sh
   git checkout cddd5df -- src/point_add/mod.rs src/point_add/venting.rs
   git checkout cddd5df -- src/point_add/by.rs src/point_add/coset_proto.rs src/point_add/halfgcd_coeff_decoder.rs src/point_add/halfgcd_live_pa.rs src/point_add/kaliski_classical_replay.rs src/point_add/kaliski_equiv.rs src/point_add/kaliski_jump.rs src/point_add/kaliski_linear_transform.rs src/point_add/kim_inv_circuit.rs src/point_add/kim_proto.rs src/point_add/luo_proto.rs src/point_add/lut_proto.rs src/point_add/microbench.rs
   git checkout cddd5df -- src/point_add/primitive_costs.rs src/point_add/round125_jsf.rs src/point_add/round158_halfgcd_splice_live.rs src/point_add/round185_halfgcd_fixed_depth64_pa.rs src/point_add/round218_b5_program.rs src/point_add/round218_b5_selector.rs src/point_add/round218_b5_transport.rs src/point_add/round326_b5_exact_cover_terms.rs src/point_add/scratch600_frontier.rs src/point_add/single_inv_numeric.rs src/point_add/source_live_d1.rs src/point_add/test_timeout.rs src/point_add/unconditional_kal.rs
   git checkout cddd5df -- src/point_add/round331_b5_old_g0_full_eraser.kmx
   git checkout cddd5df -- src/point_add/blockers_and_paths.md src/point_add/by_sota_architecture.md src/point_add/coset_proto.md src/point_add/cost_model.md src/point_add/creative_attempts_log.md src/point_add/google_harness_match.md src/point_add/kaliski_1200q_feasibility.md src/point_add/kim_costs.md src/point_add/lit_tricks.md src/point_add/luo_compact_inv_plan.md src/point_add/next_session_plan.md src/point_add/qubit_target_analysis.md
   git checkout cddd5df -- src/point_add/research_log_2026_04_27.md src/point_add/research_notes.md src/point_add/s_equals_p_insight.md src/point_add/scratch600_ground_up.md src/point_add/session_summary.md src/point_add/single_inv_plan.md src/point_add/sota_gap_analysis.md src/point_add/sota_plan.md src/point_add/sota_rebuild_plan.md src/point_add/strategy_c_schedule.md src/point_add/structural_sota_plan_2026_04_28.md
   ```
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It covers `fermat_inv.rs` only, 528 diff lines.
4. **Check the tree.** `git diff --ignore-cr-at-eol cddd5df -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_GCD_*`, `ROUND*`, `KAL_*` or `BY_*` environment variables set,
   because `configure_ecdsafail_submission_route()` only fills in variables
   that are unset. Expect:
   - 1698 qubits
   - 2,447,846 average Toffoli (rounded)
   - score 4,156,442,508
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with an identical op stream. This commit has no
reroll count or nonce, so any change, even an identity padding, draws a new
test set that must be validated again.

### Patch

```diff
diff --git a/src/point_add/fermat_inv.rs b/src/point_add/fermat_inv.rs
index 649d79a..02b0f39 100644
--- a/src/point_add/fermat_inv.rs
+++ b/src/point_add/fermat_inv.rs
@@ -15,9 +15,12 @@
 
 use alloy_primitives::U256;
 
+use crate::circuit::{Op, OperationType, NO_BIT};
+
 use super::{
-    bit, mod_add_qq_fast, mod_double_inplace_fast, mod_halve_inplace_fast, mod_sub_qq_fast,
-    QubitId, B,
+    bit, mod_add_qb, mod_add_qq, mod_add_qq_fast, mod_add_qq_fast_from_zero, mod_double_inplace,
+    mod_double_inplace_fast, mod_halve_inplace, mod_halve_inplace_fast, mod_neg_inplace_fast,
+    mod_sub_qb, mod_sub_qq, mod_sub_qq_fast, QubitId, B, SECP256K1_P,
 };
 
 /// Horner-style modular multiply: acc += x * y mod p.
@@ -73,6 +76,170 @@ pub fn horner_mul_add(b: &mut B, acc: &[QubitId], x: &[QubitId], y: &[QubitId],
     b.free_vec(&yw);
 }
 
+/// Phase-clean Horner multiply-add: acc += x*y mod p.
+///
+/// This is the same low-width Horner shape as [`horner_mul_add`], but it
+/// reverses every fanout explicitly and uses the phase-clean modular
+/// add/double/halve primitives. It is much larger in T, but it is suitable for
+/// a Q-first full PA route where HMR phase debt is not allowed.
+pub fn horner_mul_add_clean(b: &mut B, acc: &[QubitId], x: &[QubitId], y: &[QubitId], p: U256) {
+    let n = x.len();
+    debug_assert_eq!(n, y.len());
+    debug_assert_eq!(n, acc.len());
+
+    let yw = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+
+    for i in 0..n {
+        let fo = b.alloc_qubits(n);
+        for j in 0..n {
+            b.ccx(x[i], yw[j], fo[j]);
+        }
+        mod_add_qq(b, acc, &fo, p);
+        for j in (0..n).rev() {
+            b.ccx(x[i], yw[j], fo[j]);
+        }
+        b.free_vec(&fo);
+
+        if i < n - 1 {
+            mod_double_inplace(b, &yw, p);
+        }
+    }
+
+    for _ in 0..(n - 1) {
+        mod_halve_inplace(b, &yw, p);
+    }
+
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+    b.free_vec(&yw);
+}
+
+fn emit_controlled_clean_op(b: &mut B, ctrl: QubitId, helper: QubitId, op: Op) {
+    assert_eq!(
+        op.c_condition, NO_BIT,
+        "controlled clean block does not support classical conditions"
+    );
+    match op.kind {
+        OperationType::X => b.cx(ctrl, op.q_target),
+        OperationType::Z => b.cz(ctrl, op.q_target),
+        OperationType::CX => b.ccx(ctrl, op.q_control1, op.q_target),
+        OperationType::CZ => b.ccz(ctrl, op.q_control1, op.q_target),
+        OperationType::CCX => {
+            b.ccx(op.q_control2, op.q_control1, helper);
+            b.ccx(ctrl, helper, op.q_target);
+            b.ccx(op.q_control2, op.q_control1, helper);
+        }
+        OperationType::CCZ => {
+            b.ccx(op.q_control2, op.q_control1, helper);
+            b.ccz(ctrl, helper, op.q_target);
+            b.ccx(op.q_control2, op.q_control1, helper);
+        }
+        OperationType::Swap => {
+            b.ccx(ctrl, op.q_control1, op.q_target);
+            b.ccx(ctrl, op.q_target, op.q_control1);
+            b.ccx(ctrl, op.q_control1, op.q_target);
+        }
+        OperationType::R
+        | OperationType::Register
+        | OperationType::AppendToRegister
+        | OperationType::DebugPrint => {}
+        _ => panic!(
+            "unsupported op kind {:?} in controlled clean block",
+            op.kind
+        ),
+    }
+}
+
+fn emit_controlled_clean_block<F: FnOnce(&mut B)>(b: &mut B, ctrl: QubitId, f: F) {
+    let helper = b.alloc_qubit();
+    if b.count_only {
+        let snap = b.count_snapshot();
+        f(b);
+        let delta = b.count_delta_since(snap);
+        b.restore_count_snapshot(snap);
+        b.add_counted_kind(OperationType::CX, delta[OperationType::X as usize]);
+        b.add_counted_kind(OperationType::CZ, delta[OperationType::Z as usize]);
+        b.add_counted_kind(OperationType::CCX, delta[OperationType::CX as usize]);
+        b.add_counted_kind(OperationType::CCZ, delta[OperationType::CZ as usize]);
+        b.add_counted_kind(OperationType::CCX, 3 * delta[OperationType::CCX as usize]);
+        b.add_counted_kind(OperationType::CCX, 2 * delta[OperationType::CCZ as usize]);
+        b.add_counted_kind(OperationType::CCZ, delta[OperationType::CCZ as usize]);
+        b.add_counted_kind(OperationType::CCX, 3 * delta[OperationType::Swap as usize]);
+        b.free(helper);
+        return;
+    }
+    let start = b.ops.len();
+    f(b);
+    let fwd: Vec<_> = b.ops[start..].to_vec();
+    b.ops.truncate(start);
+    for op in fwd {
+        emit_controlled_clean_op(b, ctrl, helper, op);
+    }
+    b.free(helper);
+}
+
+fn controlled_mod_add_qq_clean(
+    b: &mut B,
+    acc: &[QubitId],
+    addend: &[QubitId],
+    ctrl: QubitId,
+    p: U256,
+) {
+    emit_controlled_clean_block(b, ctrl, |b| mod_add_qq(b, acc, addend, p));
+}
+
+fn controlled_mod_sub_qq_clean(
+    b: &mut B,
+    acc: &[QubitId],
+    addend: &[QubitId],
+    ctrl: QubitId,
+    p: U256,
+) {
+    emit_controlled_clean_block(b, ctrl, |b| mod_sub_qq(b, acc, addend, p));
+}
+
+/// Low-width phase-clean Horner multiply-add.
+///
+/// This avoids the 256-qubit `ctrl AND yw` fanout word by emitting the
+/// controlled modular add directly. T is sacrificed for the Q<2000
+/// representation milestone.
+pub fn horner_mul_add_clean_lowq(
+    b: &mut B,
+    acc: &[QubitId],
+    x: &[QubitId],
+    y: &[QubitId],
+    p: U256,
+) {
+    let n = x.len();
+    debug_assert_eq!(n, y.len());
+    debug_assert_eq!(n, acc.len());
+
+    let yw = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+
+    for i in 0..n {
+        controlled_mod_add_qq_clean(b, acc, &yw, x[i], p);
+        if i < n - 1 {
+            mod_double_inplace(b, &yw, p);
+        }
+    }
+
+    for _ in 0..(n - 1) {
+        mod_halve_inplace(b, &yw, p);
+    }
+
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+    b.free_vec(&yw);
+}
+
 /// Horner-style modular multiply-subtract: acc -= x * y mod p.
 pub fn horner_mul_sub(b: &mut B, acc: &[QubitId], x: &[QubitId], y: &[QubitId], p: U256) {
     let n = x.len();
@@ -109,6 +276,77 @@ pub fn horner_mul_sub(b: &mut B, acc: &[QubitId], x: &[QubitId], y: &[QubitId],
     b.free_vec(&yw);
 }
 
+/// Phase-clean Horner multiply-subtract: acc -= x*y mod p.
+pub fn horner_mul_sub_clean(b: &mut B, acc: &[QubitId], x: &[QubitId], y: &[QubitId], p: U256) {
+    let n = x.len();
+    debug_assert_eq!(n, y.len());
+    debug_assert_eq!(n, acc.len());
+
+    let yw = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+
+    for i in 0..n {
+        let fo = b.alloc_qubits(n);
+        for j in 0..n {
+            b.ccx(x[i], yw[j], fo[j]);
+        }
+        mod_sub_qq(b, acc, &fo, p);
+        for j in (0..n).rev() {
+            b.ccx(x[i], yw[j], fo[j]);
+        }
+        b.free_vec(&fo);
+
+        if i < n - 1 {
+            mod_double_inplace(b, &yw, p);
+        }
+    }
+
+    for _ in 0..(n - 1) {
+        mod_halve_inplace(b, &yw, p);
+    }
+
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+    b.free_vec(&yw);
+}
+
+/// Low-width phase-clean Horner multiply-subtract.
+pub fn horner_mul_sub_clean_lowq(
+    b: &mut B,
+    acc: &[QubitId],
+    x: &[QubitId],
+    y: &[QubitId],
+    p: U256,
+) {
+    let n = x.len();
+    debug_assert_eq!(n, y.len());
+    debug_assert_eq!(n, acc.len());
+
+    let yw = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+
+    for i in 0..n {
+        controlled_mod_sub_qq_clean(b, acc, &yw, x[i], p);
+        if i < n - 1 {
+            mod_double_inplace(b, &yw, p);
+        }
+    }
+
+    for _ in 0..(n - 1) {
+        mod_halve_inplace(b, &yw, p);
+    }
+
+    for i in 0..n {
+        b.cx(y[i], yw[i]);
+    }
+    b.free_vec(&yw);
+}
+
 /// In-place modular squaring: a = a² mod p.
 ///
 /// Uses 3-register Bennett pattern:
@@ -146,6 +384,52 @@ pub fn mod_square_inplace(b: &mut B, a: &[QubitId], p: U256) {
     b.free_vec(&save);
 }
 
+/// Phase-clean in-place modular squaring.
+pub fn mod_square_inplace_clean(b: &mut B, a: &[QubitId], p: U256) {
+    let n = a.len();
+
+    let save = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], save[i]);
+    }
+
+    let tmp = b.alloc_qubits(n);
+    horner_mul_add_clean(b, &tmp, a, a, p);
+
+    for i in 0..n {
+        b.swap(a[i], tmp[i]);
+    }
+
+    mod_sub_qq(b, &tmp, &save, p);
+    b.free_vec(&tmp);
+    b.free_vec(&save);
+}
+
+pub fn mod_square_inplace_clean_lowq_with_tmp(b: &mut B, a: &[QubitId], tmp: &[QubitId], p: U256) {
+    let n = a.len();
+    assert_eq!(tmp.len(), n, "borrowed square tmp width mismatch");
+
+    let save = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], save[i]);
+    }
+
+    horner_mul_add_clean_lowq(b, tmp, a, a, p);
+
+    for i in 0..n {
+        b.swap(a[i], tmp[i]);
+    }
+
+    mod_sub_qq(b, tmp, &save, p);
+    b.free_vec(&save);
+}
+
+pub fn mod_square_inplace_clean_lowq(b: &mut B, a: &[QubitId], p: U256) {
+    let tmp = b.alloc_qubits(a.len());
+    mod_square_inplace_clean_lowq_with_tmp(b, a, &tmp, p);
+    b.free_vec(&tmp);
+}
+
 /// In-place modular multiply: a = a * b mod p.
 ///
 /// Same 3-register Bennett pattern as squaring.
@@ -170,6 +454,59 @@ pub fn mod_mul_inplace(b: &mut B, a: &[QubitId], b_reg: &[QubitId], p: U256) {
     b.free_vec(&save);
 }
 
+/// Phase-clean in-place modular multiply.
+pub fn mod_mul_inplace_clean(b: &mut B, a: &[QubitId], b_reg: &[QubitId], p: U256) {
+    let n = a.len();
+
+    let save = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], save[i]);
+    }
+
+    let tmp = b.alloc_qubits(n);
+    horner_mul_add_clean(b, &tmp, a, b_reg, p);
+
+    for i in 0..n {
+        b.swap(a[i], tmp[i]);
+    }
+
+    mod_sub_qq(b, &tmp, &save, p);
+    b.free_vec(&tmp);
+    b.free_vec(&save);
+}
+
+pub fn mod_mul_inplace_clean_lowq_with_tmp(
+    b: &mut B,
+    a: &[QubitId],
+    b_reg: &[QubitId],
+    tmp: &[QubitId],
+    p: U256,
+) {
+    let n = a.len();
+    assert_eq!(b_reg.len(), n);
+    assert_eq!(tmp.len(), n, "borrowed multiply tmp width mismatch");
+
+    let save = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], save[i]);
+    }
+
+    horner_mul_add_clean_lowq(b, tmp, a, b_reg, p);
+
+    for i in 0..n {
+        b.swap(a[i], tmp[i]);
+    }
+
+    mod_sub_qq(b, tmp, &save, p);
+    b.free_vec(&save);
+}
+
+pub fn mod_mul_inplace_clean_lowq(b: &mut B, a: &[QubitId], b_reg: &[QubitId], p: U256) {
+    let tmp = b.alloc_qubits(a.len());
+    mod_mul_inplace_clean_lowq_with_tmp(b, a, b_reg, &tmp, p);
+    b.free_vec(&tmp);
+}
+
 /// Fermat inversion: result = x^{-1} mod p = x^{p-2} mod p.
 ///
 /// Left-to-right square-and-multiply:
@@ -181,6 +518,7 @@ pub fn mod_mul_inplace(b: &mut B, a: &[QubitId], b_reg: &[QubitId], p: U256) {
 /// result register must be zero on entry (we load 1 into it).
 /// x is preserved.
 pub fn fermat_inv(b: &mut B, x: &[QubitId], result: &[QubitId], p: U256) {
+    let n = x.len();
     let exp = p - U256::from(2u64); // p - 2
 
     // result = 1
@@ -206,6 +544,59 @@ pub fn fermat_inv(b: &mut B, x: &[QubitId], result: &[QubitId], p: U256) {
     }
 }
 
+/// Phase-clean Fermat inversion into a zero result register.
+pub fn fermat_inv_clean(b: &mut B, x: &[QubitId], result: &[QubitId], p: U256) {
+    let exp = p - U256::from(2u64);
+    b.x(result[0]);
+
+    let mut top_bit = 0usize;
+    for i in 0..256 {
+        if bit(exp, i) {
+            top_bit = i;
+        }
+    }
+
+    for i in (0..top_bit).rev() {
+        mod_square_inplace_clean(b, result, p);
+        if bit(exp, i) {
+            mod_mul_inplace_clean(b, result, x, p);
+        }
+    }
+}
+
+pub fn fermat_inv_clean_lowq(b: &mut B, x: &[QubitId], result: &[QubitId], p: U256) {
+    let tmp = b.alloc_qubits(result.len());
+    fermat_inv_clean_lowq_with_tmp(b, x, result, &tmp, p);
+    b.free_vec(&tmp);
+}
+
+pub fn fermat_inv_clean_lowq_with_tmp(
+    b: &mut B,
+    x: &[QubitId],
+    result: &[QubitId],
+    tmp: &[QubitId],
+    p: U256,
+) {
+    let exp = p - U256::from(2u64);
+    assert_eq!(x.len(), result.len());
+    assert_eq!(tmp.len(), result.len());
+    b.x(result[0]);
+
+    let mut top_bit = 0usize;
+    for i in 0..256 {
+        if bit(exp, i) {
+            top_bit = i;
+        }
+    }
+
+    for i in (0..top_bit).rev() {
+        mod_square_inplace_clean_lowq_with_tmp(b, result, tmp, p);
+        if bit(exp, i) {
+            mod_mul_inplace_clean_lowq_with_tmp(b, result, x, tmp, p);
+        }
+    }
+}
+
 /// In-place modular multiply-sub: a -= x * y mod p.
 /// Uses 3-register Bennett: save=a; compute a-x*y into tmp; swap; tmp-=save=0.
 pub fn mod_mul_sub_inplace(b: &mut B, a: &[QubitId], x: &[QubitId], y: &[QubitId], p: U256) {
@@ -236,3 +627,136 @@ pub fn mod_mul_sub_inplace(b: &mut B, a: &[QubitId], x: &[QubitId], y: &[QubitId
     b.free_vec(&save);
 }
 
+/// Phase-clean in-place modular multiply-subtract.
+pub fn mod_mul_sub_inplace_clean(b: &mut B, a: &[QubitId], x: &[QubitId], y: &[QubitId], p: U256) {
+    let n = a.len();
+
+    let save = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], save[i]);
+    }
+
+    let tmp = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], tmp[i]);
+    }
+    horner_mul_sub_clean(b, &tmp, x, y, p);
+
+    for i in 0..n {
+        b.swap(a[i], tmp[i]);
+    }
+
+    mod_sub_qq(b, &tmp, &save, p);
+    b.free_vec(&tmp);
+    b.free_vec(&save);
+}
+
+pub fn mod_mul_sub_inplace_clean_lowq(
+    b: &mut B,
+    a: &[QubitId],
+    x: &[QubitId],
+    y: &[QubitId],
+    p: U256,
+) {
+    let n = a.len();
+
+    let save = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], save[i]);
+    }
+
+    let tmp = b.alloc_qubits(n);
+    for i in 0..n {
+        b.cx(a[i], tmp[i]);
+    }
+    horner_mul_sub_clean_lowq(b, &tmp, x, y, p);
+
+    for i in 0..n {
+        b.swap(a[i], tmp[i]);
+    }
+
+    mod_sub_qq(b, &tmp, &save, p);
+    b.free_vec(&tmp);
+    b.free_vec(&save);
+}
+
+#[cfg(test)]
+mod tests {
+    use super::*;
+    use crate::circuit::{analyze_ops, Op};
+    use crate::sim::Simulator;
+    use crate::weierstrass_elliptic_curve::WeierstrassEllipticCurve;
+    use alloy_primitives::U256;
+    use sha3::digest::{ExtendableOutput, Update, XofReader};
+    use sha3::Shake256;
+
+    fn secp256k1() -> WeierstrassEllipticCurve {
+        WeierstrassEllipticCurve {
+            modulus: SECP256K1_P,
+            a: U256::from(0),
+            b: U256::from(7),
+            gx: U256::from_str_radix(
+                "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
+                16,
+            )
+            .unwrap(),
+            gy: U256::from_str_radix(
+                "483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
+                16,
+            )
+            .unwrap(),
+            order: U256::from_str_radix(
+                "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
+                16,
+            )
+            .unwrap(),
+        }
+    }
+
+    /// Test Horner mul at small n
+    #[test]
+    fn test_horner_mul_small() {
+        let p = SECP256K1_P;
+        // Test the secp256k1-width helper on a tiny value: 7 * 5 = 35.
+        let n = 256;
+
+        let mut b = B::new();
+        let x = b.alloc_qubits(n);
+        let y = b.alloc_qubits(n);
+        let acc = b.alloc_qubits(n);
+
+        horner_mul_add(&mut b, &acc, &x, &y, p);
+
+        // Check acc = 35 = 0b100011
+        let (total_qubits, _num_bits, _num_regs, regs) = analyze_ops(b.ops.iter().copied());
+
+        let mut xof_seed = [0u8; 32];
+        let mut xof = Shake256::default().chain(&xof_seed).finalize_xof();
+        let mut sim = Simulator::new(total_qubits as usize, _num_bits as usize, &mut xof);
+
+        // Set x=7, y=5 on shot 0
+        for &i in &[0usize, 1, 2] {
+            *sim.qubit_mut(x[i]) |= 1;
+        }
+        for &i in &[0usize, 2] {
+            *sim.qubit_mut(y[i]) |= 1;
+        }
+
+        sim.apply(&b.ops);
+
+        let acc_val = (0..n).fold(U256::ZERO, |v, i| {
+            v | if (*sim.qubit_mut(acc[i]) & 1) != 0 {
+                U256::from(1) << i
+            } else {
+                U256::ZERO
+            }
+        });
+
+        assert_eq!(
+            acc_val,
+            U256::from(35),
+            "7 * 5 mod secp256k1 should be 35, got {}",
+            acc_val
+        );
+    }
+}
```

