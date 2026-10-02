# fed64cf — Clamp every adder, compare and fold to a 1159-qubit target with per-call reserves, and free several carry and flag wires early

| | |
| --- | --- |
| Contestant | nasqret |
| Date | 2026-06-20 |
| Submission | `6c1a65d` |
| Commit | `fed64cf6ec83e31d97af62886f842322d8d18860` |
| Result | 1159 qubits × 1,388,180 Toffoli = **1,608,900,620** |
| Base | `94d44be` (git parent and frontier at the time, odinfree): 1162 qubits × 1,389,036 Toffoli = 1,614,059,832 |
| Change vs base | qubits −3, Toffoli −856, score −5,159,212 (leaderboard Δ −5,159,212) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [adders-and-carries](../concepts/adders-and-carries.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **A**: the patch below is the whole change (about 1,900 lines, no generated files) |

## Summary

Up to this commit the trailmix circuit got its scratch budgets from a baked
schedule plus uniform trims (see [`31421df`](31421df.md) and
[`7b7bd12`](7b7bd12.md)). This commit adds a live cap instead:
`TLM_TARGET_Q = 1159`. Every adder, comparator and `+f` fold now looks at how
many qubits are live when it is emitted and shrinks its own carry or vent
budget so that it stays under 1159. Two fold types get hand-fitted per-call
reserve maps, so that each call keeps room for the extra wires it needs
internally. Several primitives also free wires earlier: carry and flag wires
that `hmr` has just reset are reused at once, a comparator no longer copies
its result to a separate flag wire, and the derived controls of the chunked
fused fold are released between the two passes.

Peak qubits fall from 1162 to 1159. Smaller budgets cost Toffoli, but three
Toffoli cuts at no qubit cost more than make up for it: measurement-based
cleanup of the fold's nonlinear controls, one fewer Toffoli per GCD swap
compare, and a constprop pass that closes chains of equal-control CCX within
one sweep. Net −856 average Toffoli. Much of the diff is tracing, phase
labels and experiments that are off by default. They are listed at the end.

## What changed and why it saves qubits and Toffoli

### Qubits

Background for all of this: the peak is the largest number of wires live at
one moment, and every primitive allocates its carries transiently. See
[peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md) and
[venting-and-wire-loans](../concepts/venting-and-wire-loans.md).

### 1. A live qubit target (`TLM_TARGET_Q=1159`)

`trailmix_ludicrous/mod.rs`: new `target_qubit_headroom(circ)` returns
`TLM_TARGET_Q − active_qubits`, or `None` if the variable is unset. Each
budget is then clamped:

| Primitive (file, function) | Budget | New clamp |
| --- | --- | --- |
| Gidney hybrid add (`gidney.rs::controlled_hybrid_add_refs_impl`) | vented carries | `min(schedule, headroom)` |
| Apply cofactor add (`gidney.rs::controlled_hybrid_add_cout_refs`) | carry budget `k` | `min(schedule, headroom)` |
| GCD subtract (`gidney.rs::controlled_hybrid_add_capped_branch`) | carry budget `k` | `min(schedule, headroom)` |
| Chunked comparator (`comparator.rs::compare_geq_chunked_middle_direct`) | held carries | `min(k, headroom − 1)` |
| `+f` window (`arith.rs::add_f_window`) | clean carries `g` | `min(schedule, headroom − reserve)` |
| Fused double fold, clean-vent form (`fused.rs::fused_fold`) | `nv` | `min(code, headroom − reserve)` |

A clamped budget picks a layout with fewer clean wires and more Toffoli, the
same trade as the uniform trims before, but only where the cap actually binds.

**Per-call reserves.** A `+f` window or fused fold allocates more than its
`g` or `nv` clean carries internally, so the headroom has to keep a reserve.
- `add_f_window` counts its calls (`FFG_CALL_INDEX`, reset in
  `load_schedule`). The reserve is `TLM_TARGET_FFG_RESERVE = 9` by default, and
  `TLM_TARGET_FFG_CALL_RESERVES` overrides it per call index. The map in
  `build()` sets reserves 0–8 for calls 163–254 and 509–600 (the window calls
  near the GCD/apply peak).
- `fused_fold` counts its calls (`FOLD_CALL_INDEX`). The default reserve is
  `TLM_TARGET_FOLD_RESERVE = 4`, and `TLM_TARGET_FOLD_CALL_RESERVES` gives
  per-call values 0–3 for calls 170–195, 251–262 and 318–343.
- These maps are hand-fitted numbers. Lower reserves keep more clean carries
  (fewer Toffoli). Each value is as low as it can be without that call
  pushing the peak above 1159.

### 2. Wires freed earlier

- **Carry lane reused after `hmr`.** In `gidney.rs`, the carry-erase
  `controlled_erase_carry_gated_impl` and, in `arith.rs`,
  `controlled_erase_carry_gated_const` measure out a chunk carry with `hmr` and
  then run a phase-repair comparison. The `hmr` leaves the carry wire at |0⟩,
  so the commit returns it to the allocator at once with `loan_zero_qubit`
  (no reset op). The comparison's first ancilla can then take that wire.
  Before, the carry was freed only after the comparison.
- **The carry wire as the zero carry-in.** For the lowest chunk the carry-in is
  0. The new `controlled_erase_carry_gated_zero_cin` and
  `controlled_erase_carry_gated_capped_zero_cin` use the reset carry wire
  itself as that zero, instead of a separate `cin0` / `zcin` wire. In the
  adaptive, chunked-then-Cuccaro and variable-chunk layouts, `cin0` is now
  freed before the erase loop.
- **Comparator without a flag copy.** `comparator.rs`: the new
  `compare_geq_chunked_middle_direct` hands the final carry `c_n = [a ≥ b]`
  straight to the callback, instead of CNOT-copying it to a separate `flag`
  wire and back. The old `compare_geq_chunked_middle` is now a wrapper of it
  for callers that need a flag. The two GCD swap-decision users,
  `controlled_swap_decision_lt_truncated` and `swap_decision_uncompute_vented`,
  call the direct form and spend the saved wire on one more held carry
  (`next_cmp_k() + 1`). The included test checks that this gives the same peak
  and exactly one fewer Toffoli per call.
- **Fold controls released between passes** (`TLM_FOLD_RELEASE_CONTROLS=1`).
  `fused.rs::add_mf_fold_chunked` builds four derived controls of the two
  overflow bits `e`, `d` (`e∧d`, `e⊕d`, `e∨d`, `d∧¬e`), which are needed
  only at fold bits 7–11 (`fold_ctl`). The commit uncomputes them right after the last chunk
  that touches bit 11 and rebuilds them before the reverse (erase) pass reaches
  that chunk again. The upper chunks then run without those wires.

### 3. Layout changes

- `TLM_GCD_RESELECT_LAYOUT=1`: the GCD subtract ignores the baked branch code
  (`GCD_BRANCH`) and picks variable-chunk or adaptive by the cost model
  (`controlled_hybrid_add_knob_capped_refs`) at the clamped `k`. The baked
  branches were chosen for the old budgets.
- `TLM_DIRECT_VARCHUNK=1`: in `controlled_hybrid_add_varchunk_gated_refs` each
  chunk is a `controlled_clean_add_threaded` with the previous chunk's carry as
  carry-in, instead of the padded `controlled_vented_chunk_add`, and no `cin0`
  is allocated. It still advances the `HYB_V` cursor so later calls read the
  same schedule entries.
- `searched_cout_layout` and `searched_gcd_adaptive_layout` now also consider
  `plain_len = 0` (fully chunked layouts).

### Toffoli

- **Nonlinear fold controls cleared by measurement.** `fused.rs::on_ctl_free`:
  an owned derived control `q` = OR (kind 4), `d∧¬e` (kind 5) or AND (kind 6)
  was cleared by recomputing it with a CCX. Now
  `on_ctl_clear_nonlinear_hmr` measures it with `hmr` and repairs the phase
  `m·q` with classically conditioned Clifford gates. Over GF(2)
  `e∨d = e + d + ed`, `d∧¬e = d + ed` and `e∧d = ed`, so `Z^m` on `e` and/or
  `d` plus a conditioned `CZ(e, d)` gives exactly the same phase. Each clear
  saves one Toffoli; the XOR control (kind 3) keeps its two CNOTs. See
  [measurement-uncompute](../concepts/measurement-uncompute.md).
- **One fewer Toffoli per swap compare** (see the comparator item above).
- **Constprop closes equal-control chains in one sweep.**
  `constprop.rs::analyze_affine`: when a CCX is proved to have equal controls
  and becomes `CX(a, t)`, the target's affine form is now updated to
  `t ⊕ a` (unless the gate is conditional, or the set exceeds `CAP_SET`)
  instead of being made a fresh unknown. A chain of such CCX now folds in one
  sweep. Before, it needed one whole-stream sweep per link. The sweep cap
  `CONSTPROP_MAX_ITERS=16` is unchanged, so more folds fit under it. See
  [dead-gate-strip](../concepts/dead-gate-strip.md) and [`d2643bc`](d2643bc.md).

The −856 Toffoli is the net of these cuts and the extra cost of the clamped
budgets. The commit does not report the parts separately.

### Off by default, or not part of the circuit

- `ec_add.rs`: `TLM_COORD_SPLIT_LOW3` (unset) would subtract the top 253 bits
  of a classical coordinate with `mod_sub_shifted_low` and the low 3 bits with
  the new exact `arith::mod_sub_classical_low3`. That uses the new
  `toggle_geq_p_minus_low3`, `toggle_geq_small_const`, and the Khattar–Gidney
  incrementers `inc_khattar_gidney` / `cinc_khattar_gidney` in `mcx.rs`.
- `codec.rs`: a `Tail4Top32` tape codec, five symbols in 8 wires through
  ANF-synthesized encoder and decoder tables, behind `TLM_TAIL4_TOP32` (unset),
  plus its handling in `forward_gcd_jump` / `reverse_gcd_jump`.
- `gidney.rs`: a dirty-vent pool (`with_dirty_vent_pool`, `TLM_DIRTY_VENTS`
  unset, so 0 dirty lanes). `gcd.rs` passes `x_reg[..3]` / `u[1..4]` to it.
- Overrides: `TLM_*_CALL_DELTAS`, `TLM_*_CALL_OVERRIDES`, `TLM_FFG_FORCE_G`,
  `TLM_FOLD_CHUNK_FORCE`, `TLM_TARGET_FFG_RESERVE8_CALLS`,
  `TLM_FOLD_HMR_CONTROL_CLEANUP_DISABLE`, a `TLM_GCD_K_EXTRA_*` second adjust
  in `gcd.rs`, and `SINGLE_CCX_FANOUT_DISABLE` in `build()`.
- Traces and tests: `TRACE_TLM_*`, the `set_phase("tlm_…")` labels (no ops),
  `TLM_FOLD_HMR_CONTROL_SELFTEST`, and new unit tests in `comparator.rs`,
  `constprop.rs` and `fused.rs`.
- Tail nonce: `DIALOG_TAIL_NONCE` 300322437 → 453700.

## Why it is still correct, and what it risks

- **Exact.** All budget clamps only choose between exact decompositions of
  the same addition or comparison. Reusing a wire that `hmr` has reset, using
  it as a zero carry-in, and dropping the flag copy are exact. The fold-control
  release recomputes the same Boolean functions of `e`, `d`. The HMR clear of
  the nonlinear controls is phase-exact by the ANF identities above; the
  built-in selftest checks every `(e, d, m)` case. The constprop transfer is
  the exact GF(2) update of a CX.
- **Probabilistic, as before.** A smaller GCD `k` or a reselected layout can
  give more chunks, and each chunk erase compares only the top `cap = 20` bits.
  A smaller fold `g` changes how a window's carries are made but not its
  52-bit width. The failure set may change a little, so a new nonce was
  needed.
- **Which channel catches it.** A layout or reserve error that leaves a wire
  dirty is an ancilla failure. A wrong phase repair is a phase failure.
  Changed values are classical failures.
- The shipped nonce 453700 draws a clean set: 9,024 of 9,024 shots pass,
  with 0 classical, 0 phase and 0 ancilla failures. The author reports an
  exact average of 1,388,179.655 Toffoli and ops SHA-256 `a840394…`.

## Classification rationale

The main lever is fitting every primitive's scratch use under a qubit target,
and freeing carry, flag and control wires earlier. That is register and
scratch allocation (ancilla lifetime / venting), the published label. The
Toffoli cuts (HMR control cleanup, direct comparator carry, constprop
transfer) are secondary and hold qubits flat.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 94d44be -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 94d44be fed64cf -- src/point_add` is
   1,893 lines in 11 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol fed64cf -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*`, `LUD_*`, `CONSTPROP_*` or `TRACE_*` environment
   variables set, because they override the defaults in `build()`. Expect:
   - 1159 qubits
   - 1,388,180 average Toffoli (1,388,179.655 before rounding)
   - score 1,608,900,620
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `453700` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f67020d..ee6ff1f 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1968,26 +1968,37 @@ pub fn build() -> Vec<Op> {
             return Vec::new();
         }
     }
-    // Submitted circuit: the trailmix-ludicrous product-min secp256k1 point-add on
-    // the constant-propagation base, with the carry-out and GCD-adaptive layout
-    // searches both pushed to their tightest q1166 setting and a 2-vent fold.
-    // Stacked levers (all value-exact, peak-neutral at 1166q):
-    //   - LUD_EXTRA_FOLD_VENTS=2, MIN_G=16: two extra FFG_G>=16 fold vents; the
-    //     fresh nonce below lands on a clean lower-average island at q1165.
-    //   - TLM_COUT_LAYOUT_MARGIN=0 with TLM_COUT_LAYOUT_FORCE_M1_KS=129: the cout
-    //     layout search runs at margin 0 everywhere EXCEPT the single peak-critical
-    //     k=129 call (forced back to margin 1), capturing nearly all of the cout
-    //     Toffoli cut while keeping peak qubits at 1166.
-    //   - TLM_GCD_ADAPTIVE_LAYOUT_MARGIN=0: GCD-adaptive layout at margin 0.
-    // The tail nonce reseeds the 9024 Fiat-Shamir draws so all land in the
-    // schedule-supported set. Island nonce 300322437 validates 0/0/0 over all
-    // 9024 shots at peak 1162 => score 1,614,059,832.
+    // GPT-Codex Q1159 product route. Per-call FFG/fold reserves fit every local
+    // arithmetic peak under the target width; direct comparator carries and HMR
+    // cleanup remove Toffolis without increasing liveness. Nonce 453700 passed
+    // the trusted 9024-shot evaluator with 0 classical, phase, and ancilla
+    // failures at rounded T=1,388,180 and Q=1159 (score 1,608,900,620).
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
-    set_default_env("DIALOG_TAIL_NONCE", "300322437");
+    set_default_env("DIALOG_TAIL_NONCE", "453700");
     set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "a");
     set_default_env("CONSTPROP_MAX_ITERS", "16");
+    set_default_env("TLM_TARGET_Q", "1159");
+    set_default_env("TLM_FOLD_RELEASE_CONTROLS", "1");
+    set_default_env("TLM_TARGET_FFG_RESERVE", "9");
+    set_default_env(
+        "TLM_TARGET_FFG_CALL_RESERVES",
+        concat!(
+            "163:8,165:8,166:7,167:8,168:7,169:6,170:7,171:6,172:5,173:6,174:5,175:4,176:5,177:4,178:3,179:4,180:3,181:2,182:3,183:2,184:1,185:2,186:1,187:0,188:1,189:0,190:3,191:0,192:3,193:3,194:3,195:3,196:4,197:3,198:4,199:4,200:4,201:4,202:4,203:4,204:4,205:5,206:4,207:5,208:5,209:5,210:5,211:5,212:5,213:5,214:5,215:5,216:5,217:6,218:5,219:6,220:6,221:6,222:6,223:6,224:6,225:6,226:6,227:6,228:6,229:6,230:6,231:6,232:7,233:6,234:7,235:7,236:7,237:7,238:7,239:7,240:7,241:7,242:7,243:7,244:7,245:7,246:7,247:7,248:8,249:8,250:8,251:8,252:8,253:8,254:8,",
+            "509:8,510:8,511:8,512:8,513:8,514:8,515:8,516:7,517:7,518:7,519:7,520:7,521:7,522:7,523:7,524:7,525:7,526:7,527:7,528:7,529:7,530:6,531:7,532:6,533:6,534:6,535:6,536:6,537:6,538:6,539:6,540:6,541:6,542:6,543:6,544:6,545:5,546:6,547:5,548:5,549:5,550:5,551:5,552:5,553:5,554:5,555:5,556:5,557:4,558:5,559:4,560:4,561:4,562:4,563:4,564:4,565:4,566:3,567:4,568:3,569:3,570:3,571:3,572:0,573:3,574:0,575:1,576:0,577:1,578:2,579:1,580:2,581:3,582:2,583:3,584:4,585:3,586:4,587:5,588:4,589:5,590:6,591:5,592:6,593:7,594:6,595:7,596:8,597:7,598:8,600:8",
+        ),
+    );
+    set_default_env("TLM_TARGET_FOLD_RESERVE", "4");
+    set_default_env(
+        "TLM_TARGET_FOLD_CALL_RESERVES",
+        concat!(
+            "170:3,172:3,173:2,174:3,175:2,176:1,177:2,178:1,179:0,180:1,181:0,182:0,183:0,184:0,185:3,186:0,187:3,188:3,189:3,190:3,191:3,192:3,193:3,195:3,",
+            "251:3,252:3,253:3,254:3,255:3,256:3,257:3,258:3,259:3,260:3,261:3,262:3,318:3,320:3,321:3,322:3,323:3,324:3,325:3,326:3,327:0,328:3,329:0,330:0,331:0,332:0,333:1,334:0,335:1,336:2,337:1,338:2,339:3,340:2,341:3,343:3",
+        ),
+    );
+    set_default_env("TLM_GCD_RESELECT_LAYOUT", "1");
+    set_default_env("TLM_DIRECT_VARCHUNK", "1");
     set_default_env("TLM_COUT_LAYOUT_SEARCH", "1");
     set_default_env("TLM_COUT_LAYOUT_MARGIN", "0");
     set_default_env("TLM_COUT_LAYOUT_FORCE_M1_KS", "129");
@@ -2008,6 +2019,13 @@ pub fn build() -> Vec<Op> {
     set_default_env("TLM_GCD_K_ADJUST_BEFORE", "196");
     set_default_env("TLM_GCD_K_ADJUST", "-2");
     let mut ops = trailmix_ludicrous::build_trailmix_ludicrous_ops();
+    if std::env::var("SINGLE_CCX_FANOUT_DISABLE")
+        .ok()
+        .as_deref()
+        == Some("1")
+    {
+        return ops;
+    }
     let input_ops = ops.len();
     let mut fanout_passes = 0usize;
     loop {
diff --git a/src/point_add/trailmix_ludicrous/arith.rs b/src/point_add/trailmix_ludicrous/arith.rs
index b2c0183..868769a 100644
--- a/src/point_add/trailmix_ludicrous/arith.rs
+++ b/src/point_add/trailmix_ludicrous/arith.rs
@@ -26,6 +26,38 @@
 
 use super::{B, BExt};
 use crate::circuit::{BitId, QubitId};
+use std::cell::Cell;
+
+thread_local! {
+    static FFG_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
+}
+
+pub(super) fn reset_ffg_call_index() {
+    FFG_CALL_INDEX.with(|index| index.set(0));
+}
+
+fn next_ffg_call_index() -> usize {
+    FFG_CALL_INDEX.with(|index| {
+        let current = index.get();
+        index.set(current + 1);
+        current
+    })
+}
+
+fn env_index_value(name: &str, index: usize) -> Option<usize> {
+    std::env::var(name)
+        .ok()
+        .and_then(|value| {
+            value
+                .split(',')
+                .filter_map(|item| item.trim().split_once(':'))
+                .find_map(|(call, value)| {
+                    (call.parse::<usize>().ok()? == index)
+                        .then(|| value.parse::<usize>().ok())
+                        .flatten()
+                })
+        })
+}
 
 /// secp256k1 reduction constant f = 2^256 - q.
 pub const F_SECP256K1: u64 = (1u64 << 32) + 977;
@@ -662,6 +694,9 @@ fn compare_geq_const_cin_middle<F: FnOnce(&mut B, &QubitId, &QubitId, bool)>(cir
 fn controlled_erase_carry_gated_const(circ: &mut B, ctrl: &QubitId, a: &[QubitId], c: &[u8], coff: usize, cin: &QubitId, carry: QubitId) {
     let bit = circ.alloc_bit();
     circ.hmr(carry, bit);
+    // HMR resets the boundary carry before the phase-recovery comparator. Its
+    // physical lane can therefore host the comparator's first clean ancilla.
+    circ.loan_zero_qubit(carry);
     circ.push_condition(bit);
     compare_geq_const_cin_middle(circ, a, c, coff, cin, |cc, a_top, cy_top, ctop| {
         // Z^(ctrl . NOT cy_s); const_top=1 (AND): cy_s=a&cy; =0 (OR): cy_s=a|cy.
@@ -673,7 +708,6 @@ fn controlled_erase_carry_gated_const(circ: &mut B, ctrl: &QubitId, a: &[QubitId
         }
     });
     circ.pop_condition();
-    circ.zero_and_free(carry);
 }
 
 /// GRADUATED staircase const add on a suffix: chunk `i` width `k-3-i`.
@@ -787,6 +821,8 @@ fn add_f_window_hybrid(circ: &mut B, ctrl: &QubitId, reg: &[QubitId], lsbs: usiz
 /// register bits for the overflow, so the fold never inflates the peak past the
 /// ceiling.
 fn add_f_window(circ: &mut B, ctrl: &QubitId, reg: &[QubitId], lsbs: usize, c: &[u8], g_sched: Option<usize>) {
+    let call_index = next_ffg_call_index();
+    let timeline_start = circ.active_timeline.len();
     let n = lsbs;
     assert!(n <= reg.len(), "register too short for +f window");
     if n == 0 { return; }
@@ -797,7 +833,38 @@ fn add_f_window(circ: &mut B, ctrl: &QubitId, reg: &[QubitId], lsbs: usize, c: &
     // `g` = clean-vent count. Schedule-driven for the apply cofactor folds (g_sched =
     // the baked `g`, deterministic -> phase-clean); live-headroom read (CEILING - live)
     // for the doublings (always clean -- high headroom).
-    let g = g_sched.map_or_else(|| CEILING.saturating_sub(circ.active_qubits as usize), |g| g).min(n - 1);
+    let target_g = super::target_qubit_headroom(circ).map(|headroom| {
+        let mut reserve = std::env::var("TLM_TARGET_FFG_RESERVE")
+            .ok()
+            .and_then(|value| value.parse::<usize>().ok())
+            .unwrap_or(4);
+        if let Some(call_reserve) =
+            env_index_value("TLM_TARGET_FFG_CALL_RESERVES", call_index)
+        {
+            reserve = call_reserve;
+        } else if std::env::var("TLM_TARGET_FFG_RESERVE8_CALLS")
+            .ok()
+            .map(|value| {
+                value
+                    .split(',')
+                    .filter_map(|item| item.trim().parse::<usize>().ok())
+                    .any(|candidate| candidate == call_index)
+            })
+            .unwrap_or(false)
+        {
+            reserve = 8;
+        }
+        headroom.saturating_sub(reserve)
+    });
+    let scheduled_g = g_sched
+        .map_or_else(|| CEILING.saturating_sub(circ.active_qubits as usize), |g| g)
+        .min(target_g.unwrap_or(usize::MAX))
+        .min(n - 1);
+    let g = std::env::var("TLM_FFG_FORCE_G")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .map_or(scheduled_g, |forced| forced.min(n - 1));
+    let trace_entry_active = circ.active_qubits;
     if g >= n - 1 {
         add_f_window_clean(circ, ctrl, reg, lsbs, c); // all-clean path
     } else if g == 0 {
@@ -809,6 +876,23 @@ fn add_f_window(circ: &mut B, ctrl: &QubitId, reg: &[QubitId], lsbs: usize, c: &
     } else {
         add_f_window_hybrid(circ, ctrl, reg, lsbs, c, g);
     }
+    if std::env::var_os("TRACE_TLM_FFG").is_some() {
+        let local_peak = circ.active_timeline[timeline_start..]
+            .iter()
+            .map(|(_, active)| *active)
+            .max()
+            .unwrap_or(trace_entry_active);
+        eprintln!(
+            "TLM_FFG call={} phase={} g={} entry_active={} local_peak={} phase_max={} ops={}",
+            call_index,
+            circ.phase,
+            g,
+            trace_entry_active,
+            local_peak,
+            circ.current_phase_active_max,
+            circ.current_ops_len(),
+        );
+    }
 }
 
 fn add_f_window_clean(circ: &mut B, ctrl: &QubitId, reg: &[QubitId], lsbs: usize, c: &[u8]) {
@@ -1021,6 +1105,7 @@ pub fn controlled_mod_add_k(circ: &mut B, ctrl: &QubitId, x: &[QubitId], y: &[Qu
     let f_bytes = F_SECP256K1.to_le_bytes();
     let anc = circ.alloc_qubit();
     // 1) y += ctrl*x; carry-out (overflow) captured into the transient anc.
+    circ.set_phase("tlm_apply_forward_mod_add_register");
     match sched_k {
         Some(k) => {
             let yr: Vec<&QubitId> = y.iter().collect();
@@ -1030,6 +1115,7 @@ pub fn controlled_mod_add_k(circ: &mut B, ctrl: &QubitId, x: &[QubitId], y: &[Qu
         None => controlled_add_vented_chunked_cout(circ, ctrl, x, y, APPLY_CHUNK, Some(&anc)),
     }
     // 2) gated +f reduction (anc holds ctrl AND overflow); carry beyond LSBS dropped.
+    circ.set_phase("tlm_apply_forward_mod_add_fold");
     add_f_window(circ, &anc, y, LSBS, &f_bytes, ffg_g);
     // 3) less-than comparator erases anc back to |0>: anc holds `ctrl AND (y_final < x)`. The
     //    ludicrous profile truncates this comparator to the top `MSBS = PAD = 21`
@@ -1041,6 +1127,7 @@ pub fn controlled_mod_add_k(circ: &mut B, ctrl: &QubitId, x: &[QubitId], y: &[Qu
     debug_assert_eq!(MSBS, PAD); // the +f comparator is truncated to the top PAD bits
     // The less-than erase consumes `anc`: it HMRs it then frees it BEFORE the recompute
     // comparator (so the overflow flag is not held live across the chunked comparator).
+    circ.set_phase("tlm_apply_forward_mod_add_clean");
     controlled_lt_msbs_conditional(circ, Some(ctrl), &y[..n], &x[..n], MSBS, anc);
 }
 
@@ -1194,6 +1281,164 @@ pub fn mod_sub_shifted_low(circ: &mut B, x: &[QubitId], y: &[QubitId], shift: us
     circ.zero_and_free(anc);
 }
 
+fn toggle_pattern_mcx(circ: &mut B, pattern: &[(QubitId, bool)], target: &QubitId) {
+    for &(q, expected) in pattern {
+        if !expected {
+            circ.x(q);
+        }
+    }
+    let ctrls: Vec<&QubitId> = pattern.iter().map(|(q, _)| q).collect();
+    super::mcx::mcx_clean_k(circ, &ctrls, target);
+    for &(q, expected) in pattern.iter().rev() {
+        if !expected {
+            circ.x(q);
+        }
+    }
+}
+
+/// Toggle `target` iff the little-endian register `a` is at least `threshold`.
+fn toggle_geq_small_const(circ: &mut B, a: &[QubitId], threshold: usize, target: &QubitId) {
+    assert!(threshold < (1usize << a.len()));
+    for j in (0..a.len()).rev() {
+        if (threshold >> j) & 1 != 0 {
+            continue;
+        }
+        let mut pattern = Vec::with_capacity(a.len() - j);
+        for k in (j + 1)..a.len() {
+            pattern.push((a[k], (threshold >> k) & 1 != 0));
+        }
+        pattern.push((a[j], true));
+        toggle_pattern_mcx(circ, &pattern, target);
+    }
+    let equality: Vec<(QubitId, bool)> = a
+        .iter()
+        .enumerate()
+        .map(|(i, &q)| (q, (threshold >> i) & 1 != 0))
+        .collect();
+    toggle_pattern_mcx(circ, &equality, target);
+}
+
+/// Toggle `target` iff `y >= p-c`, for canonical `y < p` and a three-bit `c`.
+fn toggle_geq_p_minus_low3(circ: &mut B, y: &[QubitId], c: &[QubitId], target: &QubitId) {
+    debug_assert_eq!(y.len(), 256);
+    debug_assert_eq!(c.len(), 3);
+
+    let sum: Vec<QubitId> = (0..11).map(|_| circ.alloc_qubit()).collect();
+    for i in 0..10 {
+        circ.cx(y[i], sum[i]);
+    }
+    let zeros: Vec<QubitId> = (0..8).map(|_| circ.alloc_qubit()).collect();
+    let mut c11 = c.to_vec();
+    c11.extend(zeros.iter().copied());
+    cuccaro_carry(circ, None, &c11, &sum, None, None);
+
+    // Since p-c = 2^256-(2^32+977+c), the low predicate is bit 32 or
+    // (bits 10..31 all one and low10+c >= 47).
+    let low_ge = circ.alloc_qubit();
+    toggle_geq_small_const(circ, &sum, 47, &low_ge);
+    let lower = circ.alloc_qubit();
+    circ.cx(y[32], lower);
+    let mut lower_pattern = Vec::with_capacity(24);
+    lower_pattern.push((y[32], false));
+    lower_pattern.extend(y[10..32].iter().map(|&q| (q, true)));
+    lower_pattern.push((low_ge, true));
+    toggle_pattern_mcx(circ, &lower_pattern, &lower);
+
+    let mut full_pattern = Vec::with_capacity(224);
+    full_pattern.push((lower, true));
+    full_pattern.extend(y[33..].iter().map(|&q| (q, true)));
+    toggle_pattern_mcx(circ, &full_pattern, target);
+
+    toggle_pattern_mcx(circ, &lower_pattern, &lower);
+    circ.cx(y[32], lower);
+    circ.zero_and_free(lower);
+    toggle_geq_small_const(circ, &sum, 47, &low_ge);
+    circ.zero_and_free(low_ge);
+
+    for q in &sum {
+        circ.x(*q);
+    }
+    cuccaro_carry(circ, None, &c11, &sum, None, None);
+    for q in &sum {
+        circ.x(*q);
+    }
+    for i in 0..10 {
+        circ.cx(y[i], sum[i]);
+    }
+    for q in sum {
+        circ.zero_and_free(q);
+    }
+    for q in zeros {
+        circ.zero_and_free(q);
+    }
+}
+
+/// Exact `y -= c (mod p)` for the three low classical coordinate bits.
+pub fn mod_sub_classical_low3(circ: &mut B, y: &[QubitId], c: &[BitId]) {
+    assert_eq!(y.len(), 256, "mod_sub_classical_low3 expects 256-bit y");
+    assert_eq!(c.len(), 3, "mod_sub_classical_low3 expects three classical bits");
+
+    let cq: Vec<QubitId> = (0..3).map(|_| circ.alloc_qubit()).collect();
+    for i in 0..3 {
+        circ.x_if_bit(cq[i], c[i]);
+    }
+
+    let low_borrow = circ.alloc_qubit();
+    for q in &y[..3] {
+        circ.x(*q);
+    }
+    cuccaro_carry(circ, None, &cq, &y[..3], None, Some(&low_borrow));
+    for q in &y[..3] {
+        circ.x(*q);
+    }
+
+    let full_borrow = circ.alloc_qubit();
+    let mut borrow_pattern = Vec::with_capacity(254);
+    borrow_pattern.push((low_borrow, true));
+    borrow_pattern.extend(y[3..].iter().map(|&q| (q, false)));
+    toggle_pattern_mcx(circ, &borrow_pattern, &full_borrow);
+
+    for q in &y[3..] {
+        circ.x(*q);
+    }
+    super::mcx::cinc_khattar_gidney(circ, &y[3..], &low_borrow);
+    for q in &y[3..] {
+        circ.x(*q);
+    }
+
+    let low_copy: Vec<QubitId> = (0..3).map(|_| circ.alloc_qubit()).collect();
+    for i in 0..3 {
+        circ.cx(y[i], low_copy[i]);
+    }
+    cuccaro_carry(circ, None, &cq, &low_copy, None, Some(&low_borrow));
+    for q in &low_copy {
+        circ.x(*q);
+    }
+    cuccaro_carry(circ, None, &cq, &low_copy, None, None);
+    for q in &low_copy {
+        circ.x(*q);
+    }
+    for i in 0..3 {
+        circ.cx(y[i], low_copy[i]);
+    }
+    for q in low_copy {
+        circ.zero_and_free(q);
+    }
+    circ.zero_and_free(low_borrow);
+
+    let f_bytes = F_SECP256K1.to_le_bytes();
+    sub_f_window(circ, &full_borrow, y, LSBS, &f_bytes);
+    toggle_geq_p_minus_low3(circ, y, &cq, &full_borrow);
+    circ.zero_and_free(full_borrow);
+
+    for i in 0..3 {
+        circ.x_if_bit(cq[i], c[i]);
+    }
+    for q in cq {
+        circ.zero_and_free(q);
+    }
+}
+
 /// In-place modular negate `x := q - x (mod q)` for x in (0,q). Identity (since
 /// `q = 2^256 - f`): `q - x = ~(x + (f-1))`. So one exact full-width const-add of
 /// `(f-1)` (no carry escapes 2^256 since `x + (f-1) < q + f - 1 = 2^256 - 1`) then
diff --git a/src/point_add/trailmix_ludicrous/codec.rs b/src/point_add/trailmix_ludicrous/codec.rs
index eb7f4a2..f2ca18a 100644
--- a/src/point_add/trailmix_ludicrous/codec.rs
+++ b/src/point_add/trailmix_ludicrous/codec.rs
@@ -81,6 +81,149 @@ pub const TRIPLE_DATA_WIRES: [usize; 7] = [0, 1, 2, 3, 4, 7, 8];
 /// Wires freed to |0> after compress (pair's wire 5 + merge's wire 6).
 pub const TRIPLE_FREED_WIRES: [usize; 2] = [5, 6];
 
+const TAIL4_TOP32_CODE_BITS: usize = 5;
+const TAIL4_TOP32_CODE_CONSTANT: u8 = 22;
+const TAIL4_TOP32_ENCODER_ANF: [&[u16]; TAIL4_TOP32_CODE_BITS] = [
+    &[2, 4, 8, 16, 32, 1024, 65, 528],
+    &[1, 2, 4, 16, 32, 520],
+    &[1, 2, 4, 8, 1024, 72],
+    &[4, 16, 32, 256, 520],
+    &[1, 4, 1024, 10, 66],
+];
+const TAIL4_TOP32_DECODER_ANF: [&[u16]; 12] = [
+    &[0, 3, 7, 18, 20, 21, 25, 27, 29, 31],
+    &[5, 6, 7, 9, 11, 13, 16, 18, 19, 20, 21, 31],
+    &[0, 11, 15, 16, 18, 20, 23, 24, 26, 27, 28, 29, 31],
+    &[3, 4, 5, 6, 11, 18, 19, 20, 21, 24, 26, 27, 28, 30],
+    &[0, 2, 3, 5, 6, 9, 13, 18, 19, 20, 23, 25, 31],
+    &[30, 31],
+    &[3, 7, 9, 13, 19, 21, 25, 30],
+    &[],
+    &[2, 3, 5, 6, 8, 9, 11, 13, 16, 19, 25, 27, 29],
+    &[0, 1, 4, 9, 13, 18, 19, 20, 27, 29],
+    &[0, 3, 7, 9, 13, 19, 21, 25, 30],
+    &[0],
+];
+
+fn tail4_top32_enabled() -> bool {
+    std::env::var("TLM_TAIL4_TOP32").ok().as_deref() == Some("1")
+}
+
+fn toggle_mcx_with_dirty(
+    circ: &mut B,
+    controls: &[QubitId],
+    dirty: &[QubitId],
+    target: QubitId,
+) {
+    debug_assert!(!controls.contains(&target));
+    match controls.len() {
+        0 => circ.x(target),
+        1 => circ.cx(controls[0], target),
+        2 => circ.ccx(controls[0], controls[1], target),
+        count => {
+            let bridge = dirty
+                .iter()
+                .copied()
+                .find(|q| *q != target && !controls.contains(q))
+                .expect("tail4 codec needs a disjoint dirty bridge");
+            let rest: Vec<QubitId> = dirty.iter().copied().filter(|q| *q != bridge).collect();
+            toggle_mcx_with_dirty(circ, &controls[..count - 1], &rest, bridge);
+            circ.ccx(bridge, controls[count - 1], target);
+            toggle_mcx_with_dirty(circ, &controls[..count - 1], &rest, bridge);
+            circ.ccx(bridge, controls[count - 1], target);
+        }
+    }
+}
+
+fn toggle_anf_with_dirty(
+    circ: &mut B,
+    controls: &[QubitId],
+    target: QubitId,
+    dirty: &[QubitId],
+    terms: &[u16],
+) {
+    for &mask in terms {
+        let term_controls: Vec<QubitId> = controls
+            .iter()
+            .enumerate()
+            .filter_map(|(i, q)| ((mask >> i) & 1 != 0).then_some(*q))
+            .collect();
+        toggle_mcx_with_dirty(circ, &term_controls, dirty, target);
+    }
+}
+
+// The historical K5 codec stores each symbol's first two flags contiguously,
+// followed by all four s2 flags. The current tape stores contiguous triples.
+fn tail4_reordered_raw(raw: &[QubitId]) -> [QubitId; 12] {
+    assert_eq!(raw.len(), 12, "tail4 raw window must contain four symbols");
+    [
+        raw[0], raw[1], raw[3], raw[4], raw[6], raw[7], raw[9], raw[10],
+        raw[2], raw[5], raw[8], raw[11],
+    ]
+}
+
+fn tail4_toggle_code_from_raw(circ: &mut B, code: &[QubitId], raw: &[QubitId]) {
+    assert_eq!(code.len(), TAIL4_TOP32_CODE_BITS);
+    let wires = tail4_reordered_raw(raw);
+    for (i, terms) in TAIL4_TOP32_ENCODER_ANF.iter().enumerate() {
+        if (TAIL4_TOP32_CODE_CONSTANT >> i) & 1 != 0 {
+            circ.x(code[i]);
+        }
+        for &mask in *terms {
+            let controls: Vec<QubitId> = wires
+                .iter()
+                .enumerate()
+                .filter_map(|(j, q)| ((mask >> j) & 1 != 0).then_some(*q))
+                .collect();
+            toggle_mcx_with_dirty(circ, &controls, &wires, code[i]);
+        }
+    }
+}
+
+fn tail4_toggle_raw_from_code(circ: &mut B, code: &[QubitId], raw: &[QubitId]) {
+    assert_eq!(code.len(), TAIL4_TOP32_CODE_BITS);
+    let wires = tail4_reordered_raw(raw);
+    for (i, terms) in TAIL4_TOP32_DECODER_ANF.iter().enumerate() {
+        toggle_anf_with_dirty(circ, code, wires[i], &wires, terms);
+    }
+}
+
+fn compress_tail4_top32_payload(circ: &mut B, raw: &[QubitId]) -> Vec<QubitId> {
+    let code: Vec<QubitId> = (0..TAIL4_TOP32_CODE_BITS)
+        .map(|_| circ.alloc_qubit())
+        .collect();
+    tail4_toggle_code_from_raw(circ, &code, raw);
+    tail4_toggle_raw_from_code(circ, &code, raw);
+    for &q in raw {
+        circ.zero_and_free(q);
+    }
+    code
+}
+
+fn decompress_tail4_top32_payload(circ: &mut B, code: &[QubitId]) -> Vec<QubitId> {
+    let raw: Vec<QubitId> = (0..12).map(|_| circ.alloc_qubit()).collect();
+    tail4_toggle_raw_from_code(circ, code, &raw);
+    tail4_toggle_code_from_raw(circ, code, &raw);
+    for &q in code {
+        circ.zero_and_free(q);
+    }
+    raw
+}
+
+fn compress_tail4_top32(circ: &mut B, raw: &[QubitId]) -> Vec<QubitId> {
+    assert_eq!(raw.len(), 15, "tail4 hybrid window must contain five symbols");
+    let mut data = raw[..3].to_vec();
+    data.extend(compress_tail4_top32_payload(circ, &raw[3..]));
+    data
+}
+
+fn decompress_tail4_top32(circ: &mut B, data: &[QubitId]) -> Vec<QubitId> {
+    assert_eq!(data.len(), 3 + TAIL4_TOP32_CODE_BITS);
+    let mut raw = data[..3].to_vec();
+    raw.extend(decompress_tail4_top32_payload(circ, &data[3..]));
+    raw
+}
+
 /// Affine pair-code normalizer (s2,s3 pair-code set -> {0..24}). `(kind,a,b,c)`:
 /// 0 = `x a`, 1 = `cx a->b`, 2 = `ccx a,b->c`. Wires addressed in the 6..11
 /// reference layout; the 9->7 triple puts the same structure 6 wires lower.
@@ -191,6 +334,8 @@ pub enum DialogCodec {
     /// 1-symbol codec keeps `subtracted` + `s_2` (2 bits) and drops the redundant
     /// `swap`: compress `CX(sub->swap)` clears swap to |0>; decompress restores it.
     Step0,
+    /// One generic symbol plus four terminal symbols on the frozen support (15 -> 8).
+    Tail4Top32,
 }
 
 impl DialogCodec {
@@ -199,6 +344,7 @@ impl DialogCodec {
         match self {
             Self::Pair => 2,
             Self::Triple => 3,
+            Self::Tail4Top32 => 5,
             Self::Raw | Self::Step0 => 1,
         }
     }
@@ -207,6 +353,7 @@ impl DialogCodec {
         match self {
             Self::Pair => 5,
             Self::Triple => 7,
+            Self::Tail4Top32 => 3 + TAIL4_TOP32_CODE_BITS,
             Self::Raw => 3,
             Self::Step0 => 2,
         }
@@ -214,7 +361,7 @@ impl DialogCodec {
     /// Transient clean ancilla (|0> in and out), separate from the symbol wires.
     fn clean_anc(self) -> usize {
         match self {
-            Self::Pair | Self::Raw | Self::Step0 => 0,
+            Self::Pair | Self::Raw | Self::Step0 | Self::Tail4Top32 => 0,
             Self::Triple => 2,
         }
     }
@@ -225,6 +372,7 @@ impl DialogCodec {
             Self::Triple => &TRIPLE_DATA_WIRES,
             Self::Raw => &[0, 1, 2],
             Self::Step0 => &[0, 2], // keep subtracted(0) + s_2(2); swap(1) is freed
+            Self::Tail4Top32 => &[], // separate code wires; handled by the special path
         }
     }
     /// Symbol-window wires cleared to |0> by compress (freed by compaction).
@@ -234,6 +382,7 @@ impl DialogCodec {
             Self::Triple => &TRIPLE_FREED_WIRES,
             Self::Raw => &[],
             Self::Step0 => &[1], // swap (= subtracted; CX'd to |0>)
+            Self::Tail4Top32 => &[],
         }
     }
     /// Forward codec on a prebuilt window (compress: symbols -> code).
@@ -244,6 +393,7 @@ impl DialogCodec {
             Self::Raw => {}
             // swap == subtracted -> CX(sub, swap) clears swap to |0>.
             Self::Step0 => circ.cx(*win[0], *win[1]),
+            Self::Tail4Top32 => unreachable!("tail4 uses separate code wires"),
         }
     }
     /// Reverse codec (decompress: code -> symbols).
@@ -254,6 +404,7 @@ impl DialogCodec {
             Self::Raw => {}
             // restore swap = subtracted on the freshly expanded |0> swap wire.
             Self::Step0 => circ.cx(*win[0], *win[1]),
+            Self::Tail4Top32 => unreachable!("tail4 uses separate code wires"),
         }
     }
 
@@ -266,6 +417,9 @@ impl DialogCodec {
     #[must_use]
     pub fn decompress_window(self, circ: &mut B, data: &[QubitId]) -> Vec<QubitId> {
         assert_eq!(data.len(), self.code_bits(), "data len != code_bits");
+        if self == Self::Tail4Top32 {
+            return decompress_tail4_top32(circ, data);
+        }
         // Build the syms*3 raw slot vector: data qubits at data_wires positions,
         // fresh |0> at freed_wires positions.
         let mut slots: Vec<Option<QubitId>> = (0..self.syms() * 3).map(|_| None).collect();
@@ -293,6 +447,9 @@ impl DialogCodec {
     #[must_use]
     pub fn compress_window(self, circ: &mut B, raw: &[QubitId]) -> Vec<QubitId> {
         assert_eq!(raw.len(), self.syms() * 3, "raw len != syms*3");
+        if self == Self::Tail4Top32 {
+            return compress_tail4_top32(circ, raw);
+        }
         let clean: Vec<QubitId> = (0..self.clean_anc()).map(|_| circ.alloc_qubit()).collect();
         let win: Vec<&QubitId> = raw.iter().chain(clean.iter()).collect();
         self.compress(circ, &win);
@@ -357,7 +514,8 @@ pub fn decompress_step0_with_t1(circ: &mut B, data: &[QubitId]) -> (QubitId, Vec
 #[must_use]
 pub fn jump_dialog_regions(n3: usize, iters: usize) -> Vec<(DialogCodec, usize)> {
     // Symbol 0 is the 1-symbol Step0 codec. The remaining iters-1 symbols tile.
-    let codec_syms = iters - 1;
+    let tail4 = usize::from(tail4_top32_enabled() && iters >= 6) * 5;
+    let codec_syms = iters - 1 - tail4;
     let mut n3 = n3;
     while 3 * n3 > codec_syms {
         n3 -= 1;
@@ -380,6 +538,9 @@ pub fn jump_dialog_regions(n3: usize, iters: usize) -> Vec<(DialogCodec, usize)>
             }
         }
     }
+    if tail4 != 0 {
+        r.push((DialogCodec::Tail4Top32, 1));
+    }
     r
 }
 
diff --git a/src/point_add/trailmix_ludicrous/comparator.rs b/src/point_add/trailmix_ludicrous/comparator.rs
index 5f45170..75f4148 100644
--- a/src/point_add/trailmix_ludicrous/comparator.rs
+++ b/src/point_add/trailmix_ludicrous/comparator.rs
@@ -19,28 +19,32 @@
 //! is full Gidney.
 
 use super::{B, BExt};
-use crate::circuit::{QubitId};
+use crate::circuit::QubitId;
 
-/// Chunked `a >= b` comparator with a middle callback, the backend the GCD swap
-/// comparator uses. `k` is the held-carry count (clamped to `n`).
-/// `body(circ, flag)` sees `flag = (a >= b)`; `a`/`b` restored, `flag` cleaned.
-pub fn compare_geq_chunked_middle<F: FnOnce(&mut B, &QubitId)>(
+/// Direct-final-carry form of the chunked `a >= b` comparator. `k` is the held
+/// carry count (clamped to `n`). `body(circ, carry)` sees
+/// `carry = (a >= b)` and must restore it before returning; `a`/`b` and all
+/// carries are then cleaned.
+fn compare_geq_chunked_middle_direct<F: FnOnce(&mut B, &QubitId)>(
     circ: &mut B,
     a: &[QubitId],
     b: &[QubitId],
-    flag: &QubitId,
     body: F,
     k: usize,
 ) {
     let n = a.len();
-    assert_eq!(b.len(), n, "compare_geq_chunked_middle: a,b equal width");
-    if n == 0 {
-        circ.x(*flag);
-        body(circ, flag);
-        circ.x(*flag);
-        return;
-    }
-    let k = k.min(n);
+    assert_eq!(
+        b.len(),
+        n,
+        "compare_geq_chunked_middle_direct: a,b equal width"
+    );
+    assert!(
+        n > 0,
+        "compare_geq_chunked_middle_direct: nonempty operands"
+    );
+    let k = super::target_qubit_headroom(circ)
+        .map_or(k, |headroom| k.min(headroom.saturating_sub(1)))
+        .min(n);
     let split = n - k; // bottom [0, split) in-place; top [split, n) held.
     let mut cy: Vec<Option<QubitId>> = (0..=n).map(|_| None).collect();
     let c = circ.alloc_qubit();
@@ -66,11 +70,7 @@ pub fn compare_geq_chunked_middle<F: FnOnce(&mut B, &QubitId)>(
         }
         cy[i + 1] = Some(next);
     }
-    let cn = cy[n].as_ref().unwrap();
-    circ.cx(*cn, *flag); // flag = c_n = (a >= b)
-    body(circ, flag);
-    let cn = cy[n].as_ref().unwrap();
-    circ.cx(*cn, *flag); // clean flag
+    body(circ, cy[n].as_ref().unwrap());
     // Reverse top: measure-erase the held carries.
     for i in (split..n).rev() {
         let next = cy[i + 1].take().unwrap();
@@ -95,6 +95,40 @@ pub fn compare_geq_chunked_middle<F: FnOnce(&mut B, &QubitId)>(
     circ.zero_and_free(c);
 }
 
+/// Compatibility form for callers that need a persistent predicate qubit.
+/// New middle-only users should use the direct-final-carry form above.
+pub fn compare_geq_chunked_middle<F: FnOnce(&mut B, &QubitId)>(
+    circ: &mut B,
+    a: &[QubitId],
+    b: &[QubitId],
+    flag: &QubitId,
+    body: F,
+    k: usize,
+) {
+    assert_eq!(
+        b.len(),
+        a.len(),
+        "compare_geq_chunked_middle: a,b equal width"
+    );
+    if a.is_empty() {
+        circ.x(*flag);
+        body(circ, flag);
+        circ.x(*flag);
+        return;
+    }
+    compare_geq_chunked_middle_direct(
+        circ,
+        a,
+        b,
+        |c, carry| {
+            c.cx(*carry, *flag);
+            body(c, flag);
+            c.cx(*carry, *flag);
+        },
+        k,
+    );
+}
+
 /// Controlled form: `target ^= ctrl AND (u_top < v_top)` on the top `k` MSBs.
 /// Used where the swap decision is itself gated.
 pub fn controlled_swap_decision_lt_truncated(
@@ -105,26 +139,27 @@ pub fn controlled_swap_decision_lt_truncated(
     k: usize,
     target: &QubitId,
 ) {
-    assert!(k <= u.len() && k <= v.len(), "k must fit in both operands");
+    assert!(
+        k > 0 && k <= u.len() && k <= v.len(),
+        "k must fit in both operands"
+    );
     let u_top: Vec<QubitId> = u[u.len() - k..].to_vec();
     let v_top: Vec<QubitId> = v[v.len() - k..].to_vec();
-    // Held-carry count for the chunked comparator, supplied per call by the
-    // schedule (`ck` Gidney carries held, `ck+1` live).
-    let ck = super::next_cmp_k();
-    let lt_flag = circ.alloc_qubit();
-    compare_geq_chunked_middle(
+    // The callback consumes the final carry directly, eliminating the old
+    // predicate-copy lane. Spend exactly that lane on one additional held carry;
+    // compare_geq_chunked_middle_direct's target-Q clamp still bounds the same peak.
+    let ck = super::next_cmp_k().saturating_add(1);
+    compare_geq_chunked_middle_direct(
         circ,
         &u_top,
         &v_top,
-        &lt_flag,
-        |c, flag| {
-            c.x(*flag);
-            c.ccx(*ctrl, *flag, *target);
-            c.x(*flag);
+        |c, carry| {
+            c.x(*carry);
+            c.ccx(*ctrl, *carry, *target);
+            c.x(*carry);
         },
         ck,
     );
-    circ.zero_and_free(lt_flag);
 }
 
 /// Measurement-vented `a + b + cin` carry chain with a middle callback. Computes
@@ -196,13 +231,12 @@ pub fn compare_geq_cin_middle<F: FnOnce(&mut B, &QubitId, &QubitId, &QubitId)>(
 /// Vented uncompute of a GCD swap-decision flag that holds `ctrl AND (v_top <
 /// u_top)` (the forward decision). HMR the flag to |0> (0 Toffoli), then
 /// under the HMR `push_condition` recompute the predicate as a deferred Z, using
-/// `compare_geq_chunked_middle(v_top, u_top)`. `v`,`u` restored. The forward
+/// the direct-final-carry comparator on `(v_top, u_top)`. `v`,`u` restored. The forward
 /// computes the flag normally (a value); only this reverse clear vents.
 ///
 /// `[v >= u] = carryout(v + ~u + 1)` over the top-`k` window; the predicate is
-/// `ctrl AND (v < u) = ctrl AND NOT[v>=u]`. With `lt_flag = [v_top >= u_top]`,
-/// deposit `Z^(ctrl AND NOT lt_flag)` via `X(lt_flag); CZ(ctrl, lt_flag);
-/// X(lt_flag)`.
+/// `ctrl AND (v < u) = ctrl AND NOT[v>=u]`. Deposit the phase directly through
+/// the final carry via `X(carry); CZ(ctrl, carry); X(carry)`.
 pub fn swap_decision_uncompute_vented(
     circ: &mut B,
     ctrl: &QubitId,
@@ -211,31 +245,194 @@ pub fn swap_decision_uncompute_vented(
     k: usize,
     flag: &QubitId,
 ) {
-    assert!(k <= v.len() && k <= u.len(), "k must fit in both operands");
+    assert!(
+        k > 0 && k <= v.len() && k <= u.len(),
+        "k must fit in both operands"
+    );
     let v_top: Vec<QubitId> = v[v.len() - k..].to_vec();
     let u_top: Vec<QubitId> = u[u.len() - k..].to_vec();
-    // Held-carry count for the chunked comparator, supplied per call by the
-    // schedule (matches the forward decision).
-    let ck = super::next_cmp_k();
+    // Match the forward decision: removing the predicate-copy lane funds one
+    // additional held carry without changing peak liveness.
+    let ck = super::next_cmp_k().saturating_add(1);
     let bit = circ.alloc_bit();
     circ.hmr(*flag, bit);
     circ.push_condition(bit);
-    let lt_flag = circ.alloc_qubit(); // = [v >= u]
-    compare_geq_chunked_middle(
+    compare_geq_chunked_middle_direct(
         circ,
         &v_top,
         &u_top,
-        &lt_flag,
-        |c, fl| {
-            // deposit Z^(ctrl AND NOT fl) = Z^(ctrl AND [v < u]), gated by the HMR
+        |c, carry| {
+            // Deposit Z^(ctrl AND NOT carry) = Z^(ctrl AND [v < u]), gated by the HMR
             // condition (push_condition). Same phase as the cin (ta,tb,c_prev) form.
-            c.x(*fl);
-            c.cz(*ctrl, *fl);
-            c.x(*fl);
+            c.x(*carry);
+            c.cz(*ctrl, *carry);
+            c.x(*carry);
         },
         ck,
     );
-    circ.zero_and_free(lt_flag);
     circ.pop_condition();
 }
 
+#[cfg(test)]
+mod tests {
+    use super::*;
+    use crate::circuit::OperationType;
+    use crate::sim::Simulator;
+    use sha3::{
+        digest::{ExtendableOutput, Update},
+        Shake256,
+    };
+
+    fn alloc_case(circ: &mut B, n: usize) -> (Vec<QubitId>, Vec<QubitId>, QubitId, QubitId) {
+        let a = (0..n).map(|_| circ.alloc_qubit()).collect();
+        let b = (0..n).map(|_| circ.alloc_qubit()).collect();
+        let ctrl = circ.alloc_qubit();
+        let target = circ.alloc_qubit();
+        (a, b, ctrl, target)
+    }
+
+    fn xor_value(circ: &mut B, qs: &[QubitId], value: usize) {
+        for (i, &q) in qs.iter().enumerate() {
+            if (value >> i) & 1 != 0 {
+                circ.x(q);
+            }
+        }
+    }
+
+    fn simulate(circ: &B) -> (Vec<u64>, u64) {
+        let mut shake = Shake256::default();
+        shake.update(b"comparator-direct-final-carry-test");
+        let mut xof = shake.finalize_xof();
+        let mut sim =
+            Simulator::new(circ.next_qubit as usize, circ.next_bit as usize, &mut xof);
+        sim.apply_iter(circ.ops.iter());
+        (sim.qubits, sim.phase)
+    }
+
+    fn read_uniform(qs: &[QubitId], qubits: &[u64]) -> usize {
+        qs.iter().enumerate().fold(0usize, |value, (i, q)| {
+            let lane = qubits[q.0 as usize];
+            assert!(
+                lane == 0 || lane == u64::MAX,
+                "nonuniform data lane q{}",
+                q.0
+            );
+            value | (usize::from(lane == u64::MAX) << i)
+        })
+    }
+
+    fn toffoli_count(circ: &B) -> usize {
+        circ.ops
+            .iter()
+            .filter(|op| matches!(op.kind, OperationType::CCX | OperationType::CCZ))
+            .count()
+    }
+
+    #[test]
+    fn direct_final_carry_is_exhaustive_for_small_widths() {
+        for n in 1..=4 {
+            let limit = 1usize << n;
+            for held in 0..=n {
+                for a_value in 0..limit {
+                    for b_value in 0..limit {
+                        for ctrl_value in 0..=1usize {
+                            for target_value in 0..=1usize {
+                                let mut circ = B::new();
+                                let (a, b, ctrl, target) = alloc_case(&mut circ, n);
+                                xor_value(&mut circ, &a, a_value);
+                                xor_value(&mut circ, &b, b_value);
+                                if ctrl_value != 0 {
+                                    circ.x(ctrl);
+                                }
+                                if target_value != 0 {
+                                    circ.x(target);
+                                }
+                                compare_geq_chunked_middle_direct(
+                                    &mut circ,
+                                    &a,
+                                    &b,
+                                    |c, carry| {
+                                        c.x(*carry);
+                                        c.ccx(ctrl, *carry, target);
+                                        c.cz(ctrl, *carry);
+                                        c.x(*carry);
+                                    },
+                                    held,
+                                );
+
+                                assert_eq!(circ.active_qubits as usize, 2 * n + 2);
+                                let (qubits, phase) = simulate(&circ);
+                                let predicate = ctrl_value != 0 && a_value < b_value;
+                                assert_eq!(read_uniform(&a, &qubits), a_value);
+                                assert_eq!(read_uniform(&b, &qubits), b_value);
+                                assert_eq!(
+                                    qubits[ctrl.0 as usize],
+                                    if ctrl_value != 0 { u64::MAX } else { 0 }
+                                );
+                                assert_eq!(
+                                    qubits[target.0 as usize],
+                                    if (target_value != 0) ^ predicate {
+                                        u64::MAX
+                                    } else {
+                                        0
+                                    },
+                                );
+                                assert_eq!(phase, if predicate { u64::MAX } else { 0 });
+                                assert!(qubits[2 * n + 2..].iter().all(|&q| q == 0));
+                            }
+                        }
+                    }
+                }
+            }
+        }
+    }
+
+    #[test]
+    fn freed_predicate_lane_funds_one_held_carry() {
+        for n in 1..=8 {
+            for held in 0..n {
+                let mut legacy = B::new();
+                let (a, b, ctrl, target) = alloc_case(&mut legacy, n);
+                let flag = legacy.alloc_qubit();
+                compare_geq_chunked_middle(
+                    &mut legacy,
+                    &a,
+                    &b,
+                    &flag,
+                    |c, flag| {
+                        c.x(*flag);
+                        c.ccx(ctrl, *flag, target);
+                        c.x(*flag);
+                    },
+                    held,
+                );
+                legacy.zero_and_free(flag);
+
+                let mut direct = B::new();
+                let (a, b, ctrl, target) = alloc_case(&mut direct, n);
+                compare_geq_chunked_middle_direct(
+                    &mut direct,
+                    &a,
+                    &b,
+                    |c, carry| {
+                        c.x(*carry);
+                        c.ccx(ctrl, *carry, target);
+                        c.x(*carry);
+                    },
+                    held + 1,
+                );
+
+                assert_eq!(
+                    direct.peak_qubits, legacy.peak_qubits,
+                    "n={n} held={held}"
+                );
+                assert_eq!(
+                    toffoli_count(&direct) + 1,
+                    toffoli_count(&legacy),
+                    "n={n} held={held}",
+                );
+            }
+        }
+    }
+}
+
diff --git a/src/point_add/trailmix_ludicrous/constprop.rs b/src/point_add/trailmix_ludicrous/constprop.rs
index 0192878..f9f1536 100644
--- a/src/point_add/trailmix_ludicrous/constprop.rs
+++ b/src/point_add/trailmix_ludicrous/constprop.rs
@@ -452,20 +452,37 @@ fn analyze_affine(
                             keep_ctrl: op.q_control1,
                         };
                         fold_eq += 1;
+
+                        // The rewritten gate is CX(a,t). Propagate that exact
+                        // affine transfer now so equal-control chains close in
+                        // this sweep instead of one whole-stream pass per link.
+                        if af.cond_maybe_false(op) {
+                            af.set[t] = af.fresh();
+                            af.cst[t] = false;
+                        } else {
+                            let ns = xor_set(&af.set[t], &af.set[a]);
+                            af.cst[t] ^= af.cst[a];
+                            if ns.len() > CAP_SET {
+                                af.set[t] = af.fresh();
+                                af.cst[t] = false;
+                            } else {
+                                af.set[t] = ns;
+                            }
+                        }
                     } else {
                         decisions[i] = Decision::DropComplementCtrls {
                             a: op.q_control1,
                             b: op.q_control2,
                         };
                         drop_comp += 1;
+                        // Complementary controls cannot both be one. The
+                        // rewritten gate is a no-op, so retain the target form.
                     }
+                } else {
+                    // An unresolved CCX is nonlinear in its controls.
+                    af.set[t] = af.fresh();
+                    af.cst[t] = false;
                 }
-                // Target becomes a fresh (nonlinear) variable. If we proved the
-                // controls equal, the gate behaves as CX(a,t) -> t ^= a; but a
-                // fresh var is a sound over-approximation of the resulting value
-                // and keeps the analysis simple/exact for relations.
-                af.set[t] = af.fresh();
-                af.cst[t] = false;
             }
             OperationType::Swap => {
                 let x = op.q_control1.0 as usize;
@@ -1244,6 +1261,60 @@ fn step_and_check<R: sha3::digest::XofReader>(
     }
 }
 
+#[cfg(test)]
+mod affine_transfer_tests {
+    use super::*;
+
+    fn gate(kind: OperationType, c1: u64, c2: u64, target: u64) -> Op {
+        let mut op = Op::empty();
+        op.kind = kind;
+        op.q_control1 = QubitId(c1);
+        op.q_control2 = QubitId(c2);
+        op.q_target = QubitId(target);
+        op
+    }
+
+    #[test]
+    fn closes_equal_and_complementary_chains_conservatively() {
+        let equal_chain = vec![
+            gate(OperationType::CX, 0, u64::MAX, 1),
+            gate(OperationType::CCX, 0, 1, 2),
+            gate(OperationType::CCX, 2, 0, 3),
+        ];
+        let (decisions, fold_eq, drop_comp) =
+            analyze_affine(&equal_chain, 4, 0, &[QubitId(0)]);
+        assert_eq!((fold_eq, drop_comp), (2, 0));
+        assert!(matches!(decisions[1], Decision::FoldEqualCtrls { .. }));
+        assert!(matches!(decisions[2], Decision::FoldEqualCtrls { .. }));
+
+        let complement_chain = vec![
+            gate(OperationType::CX, 0, u64::MAX, 1),
+            gate(OperationType::X, u64::MAX, u64::MAX, 1),
+            gate(OperationType::CX, 0, u64::MAX, 2),
+            gate(OperationType::CCX, 0, 1, 2),
+            gate(OperationType::CCX, 2, 0, 3),
+        ];
+        let (decisions, fold_eq, drop_comp) =
+            analyze_affine(&complement_chain, 4, 0, &[QubitId(0)]);
+        assert_eq!((fold_eq, drop_comp), (1, 1));
+        assert!(matches!(decisions[3], Decision::DropComplementCtrls { .. }));
+        assert!(matches!(decisions[4], Decision::FoldEqualCtrls { .. }));
+
+        let mut conditional = gate(OperationType::CCX, 0, 1, 2);
+        conditional.c_condition = BitId(0);
+        let conditional_chain = vec![
+            gate(OperationType::CX, 0, u64::MAX, 1),
+            conditional,
+            gate(OperationType::CCX, 2, 0, 3),
+        ];
+        let (decisions, fold_eq, drop_comp) =
+            analyze_affine(&conditional_chain, 4, 1, &[QubitId(0)]);
+        assert_eq!((fold_eq, drop_comp), (1, 0));
+        assert!(matches!(decisions[1], Decision::FoldEqualCtrls { .. }));
+        assert!(matches!(decisions[2], Decision::Keep));
+    }
+}
+
 /// Empirically corroborate inverse-pair cancellations over `nonces` x 9024 shots.
 /// For each cancelled pair (G1@first, G2@second) we replay the ORIGINAL stream
 /// and assert, across all live shots, that:
diff --git a/src/point_add/trailmix_ludicrous/ec_add.rs b/src/point_add/trailmix_ludicrous/ec_add.rs
index ec718f1..11e6052 100644
--- a/src/point_add/trailmix_ludicrous/ec_add.rs
+++ b/src/point_add/trailmix_ludicrous/ec_add.rs
@@ -34,7 +34,10 @@
 //! `mod_mul_inverse_in_place`, so it is never resident at the GCD peak nor
 //! across the square step.
 
-use super::arith::{mod_add, mod_double, mod_double_reverse, mod_neg, mod_sub_vented};
+use super::arith::{
+    mod_add, mod_double, mod_double_reverse, mod_neg, mod_sub_classical_low3,
+    mod_sub_shifted_low, mod_sub_vented,
+};
 use super::gcd::{mod_mul_inverse_in_place, Direction};
 use super::square::mod_square_sub_pm_secp256k1_symmetric;
 use super::{B, BExt};
@@ -53,6 +56,27 @@ const N: usize = 256;
 fn coord_addsub(circ: &mut B, dst: &[QubitId], coord: &[BitId], subtract: bool) {
     debug_assert_eq!(dst.len(), N);
     debug_assert_eq!(coord.len(), N);
+    let split_low3 = subtract
+        && std::env::var("TLM_COORD_SPLIT_LOW3")
+            .ok()
+            .as_deref()
+            .unwrap_or("0")
+            != "0";
+    if split_low3 {
+        let temp = circ.alloc_qubits(N - 3);
+        for i in 3..N {
+            circ.x_if_bit(temp[i - 3], coord[i]);
+        }
+        mod_sub_shifted_low(circ, &temp, dst, 3);
+        for i in 3..N {
+            circ.x_if_bit(temp[i - 3], coord[i]);
+        }
+        for q in temp {
+            circ.zero_and_free(q);
+        }
+        mod_sub_classical_low3(circ, dst, &coord[..3]);
+        return;
+    }
     let temp = circ.alloc_qubits(N);
     for i in 0..N {
         circ.x_if_bit(temp[i], coord[i]); // load: temp := coord (per-shot classical)
@@ -158,29 +182,37 @@ pub fn ec_add(
     assert_eq!(oy.len(), N, "oy is 256 classical bits");
 
     // Step 3/4: x2 -= ox ; y2 -= oy.  => (dx, dy).
+    circ.set_phase("tlm_coord_x_sub");
     coord_addsub(circ, x2, ox, true);
+    circ.set_phase("tlm_coord_y_sub");
     coord_addsub(circ, &y2[..N], oy, true);
 
     // Step 6: y2 *= x2^-1 (gcd inversion). The multiplicand starts in y2[..N]
     // (= dy); after the inverse apply y2 holds lambda = dy * dx^-1 mod q, and x2
     // is restored to dx. `mod_mul_inverse_in_place` takes/returns the 256-bit x
     // register; y2 and the internal tmp scratch are 256-bit.
+    circ.set_phase("tlm_inverse");
     let xv = std::mem::take(x2);
     *x2 = mod_mul_inverse_in_place(circ, xv, y2, Direction::Inverse);
 
     // Step 7: x2 += 3*ox.  => (P.x + 2*Q.x, lambda)  [x2 currently = dx = P.x-Q.x].
+    circ.set_phase("tlm_coord_add3x");
     coord_add3x(circ, x2, ox);
 
     // Step 10: x2 -= lambda^2 mod q.  (lambda = y2[..N]).
+    circ.set_phase("tlm_square");
     mod_square_sub_pm_secp256k1_symmetric(circ, &y2[..N], x2);
 
     // Step 11: y2 *= x2 (gcd forward multiply). x2 restored to the post-square
     // value; y2 = lambda * x2 mod q.
+    circ.set_phase("tlm_forward_multiply");
     let xv = std::mem::take(x2);
     *x2 = mod_mul_inverse_in_place(circ, xv, y2, Direction::Forward);
 
     // Step 14: y2 -= oy.   Step 15: x2 := ox - x2.  => (P+Q).x.
+    circ.set_phase("tlm_coord_y_sub_final");
     coord_addsub(circ, &y2[..N], oy, true);
+    circ.set_phase("tlm_coord_rsub_final");
     coord_rsub(circ, x2, ox);
 }
 
diff --git a/src/point_add/trailmix_ludicrous/fused.rs b/src/point_add/trailmix_ludicrous/fused.rs
index 970514b..1b23654 100644
--- a/src/point_add/trailmix_ludicrous/fused.rs
+++ b/src/point_add/trailmix_ludicrous/fused.rs
@@ -7,6 +7,39 @@
 use super::arith::{F_SECP256K1, LSBS};
 use super::{B, BExt};
 use crate::circuit::{BitId, QubitId};
+use std::cell::Cell;
+
+thread_local! {
+    static FOLD_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
+}
+
+pub(super) fn reset_fold_call_index() {
+    FOLD_CALL_INDEX.with(|index| index.set(0));
+}
+
+fn next_fold_call_index() -> usize {
+    FOLD_CALL_INDEX.with(|index| {
+        let current = index.get();
+        index.set(current + 1);
+        current
+    })
+}
+
+fn fold_call_reserve(index: usize, default: usize) -> usize {
+    std::env::var("TLM_TARGET_FOLD_CALL_RESERVES")
+        .ok()
+        .and_then(|value| {
+            value
+                .split(',')
+                .filter_map(|item| item.trim().split_once(':'))
+                .find_map(|(call, reserve)| {
+                    (call.parse::<usize>().ok()? == index)
+                        .then(|| reserve.parse::<usize>().ok())
+                        .flatten()
+                })
+        })
+        .unwrap_or(default)
+}
 
 /// secp256k1 `(e+2d)*f` combined-fold addend control per low-bit position `p`
 /// (encodes the bit pattern of `f` and `2f`, f = 2^32+977). 0 = None.
@@ -355,10 +388,16 @@ fn fold_boundary_erase(circ: &mut B, ctl: &[Option<QubitId>], y: &[QubitId], cin
 
 fn add_mf_fold_chunked(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId], s_chunk: usize) {
     let l = y.len();
-    let (cc, sxor, sor, dne) = build_fold_controls(circ, e, d);
-    let ctl = fold_ctl_map(*e, *d, cc, sxor, sor, dne, l);
+    let release_controls = std::env::var("TLM_FOLD_RELEASE_CONTROLS")
+        .ok()
+        .as_deref()
+        == Some("1");
+    let mut controls = Some(build_fold_controls(circ, e, d));
+    let (cc, sxor, sor, dne) = controls.expect("fold controls present");
+    let mut ctl = fold_ctl_map(*e, *d, cc, sxor, sor, dne, l);
     let cin0 = circ.alloc_qubit();
     let nch = l.div_ceil(s_chunk);
+    let last_control_chunk = 11usize.min(l - 1) / s_chunk;
     let mut boundary: Vec<QubitId> = Vec::with_capacity(nch);
     for j in 0..nch {
         let lo = j * s_chunk;
@@ -367,8 +406,17 @@ fn add_mf_fold_chunked(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId], s_
         let cin = if j == 0 { cin0 } else { boundary[j - 1] };
         fold_chunk_clean(circ, &ctl[lo..hi], &y[lo..hi], Some(&cin), &cout);
         boundary.push(cout);
+        if release_controls && j == last_control_chunk && j + 1 < nch {
+            let (cc, sxor, sor, dne) = controls.take().expect("fold controls present");
+            uncompute_fold_controls(circ, e, d, cc, sxor, sor, dne);
+        }
     }
     for j in (0..nch).rev() {
+        if release_controls && j == last_control_chunk && controls.is_none() {
+            let rebuilt = build_fold_controls(circ, e, d);
+            ctl = fold_ctl_map(*e, *d, rebuilt.0, rebuilt.1, rebuilt.2, rebuilt.3, l);
+            controls = Some(rebuilt);
+        }
         let lo = j * s_chunk;
         let hi = ((j + 1) * s_chunk).min(l);
         let bnd = boundary.pop().expect("boundary present");
@@ -376,6 +424,7 @@ fn add_mf_fold_chunked(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId], s_
         fold_boundary_erase(circ, &ctl[lo..hi], &y[lo..hi], &cin, bnd);
     }
     circ.zero_and_free(cin0);
+    let (cc, sxor, sor, dne) = controls.take().expect("fold controls restored");
     uncompute_fold_controls(circ, e, d, cc, sxor, sor, dne);
 }
 
@@ -441,9 +490,53 @@ fn on_ctl_ref(c: &OnCtl, e: &QubitId, d: &QubitId) -> Option<QubitId> {
     }
 }
 
+/// Measurement-based clear for the nonlinear on-demand controls.
+///
+/// HMR contributes the phase `m * q`, where `m` is the measurement bit.  The
+/// feedback below uses the algebraic-normal forms
+///
+///   e | d      = e + d + e*d
+///   d & !e     = d + e*d
+///   e & d      = e*d
+///
+/// over GF(2), so it contributes the same phase and cancels HMR exactly.
+fn on_ctl_clear_nonlinear_hmr(
+    circ: &mut B,
+    e: &QubitId,
+    d: &QubitId,
+    k: u8,
+    q: &QubitId,
+) {
+    let bit = circ.alloc_bit();
+    circ.hmr(*q, bit);
+    match k {
+        4 => {
+            circ.z_if_bit(*e, bit);
+            circ.z_if_bit(*d, bit);
+            circ.cz_if_bit(*e, *d, bit);
+        }
+        5 => {
+            circ.z_if_bit(*d, bit);
+            circ.cz_if_bit(*e, *d, bit);
+        }
+        6 => circ.cz_if_bit(*e, *d, bit),
+        _ => unreachable!("HMR clear requires a nonlinear fold control"),
+    }
+}
+
 fn on_ctl_free(circ: &mut B, e: &QubitId, d: &QubitId, p: usize, c: OnCtl) {
     if let OnCtl::Owned(q) = c {
-        on_ctl_apply(circ, e, d, fold_ctl(p), &q);
+        let k = fold_ctl(p);
+        let hmr_disabled = std::env::var("TLM_FOLD_HMR_CONTROL_CLEANUP_DISABLE")
+            .ok()
+            .as_deref()
+            == Some("1");
+        if k == 3 || hmr_disabled {
+            // XOR is cheaper reversibly; the flag preserves the exact old baseline.
+            on_ctl_apply(circ, e, d, k, &q);
+        } else {
+            on_ctl_clear_nonlinear_hmr(circ, e, d, k, &q);
+        }
         circ.zero_and_free(q);
     }
 }
@@ -695,11 +788,47 @@ fn build_fold_at(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId], dirty: &
 /// Dispatch the fused fold on the schedule code: -s = chunked; else nv = clean vents
 /// (full-clean / clean-tail / dirty gradual via [`build_fold_at`]).
 fn fused_fold(circ: &mut B, e: &QubitId, d: &QubitId, ylow: &[QubitId], dirty: &[QubitId]) {
+    let call_index = next_fold_call_index();
+    let timeline_start = circ.active_timeline.len();
+    let entry_active = circ.active_qubits;
     let code = super::next_fold();
+    let mut selected_nv = None;
     if code < 0 {
-        add_mf_fold_chunked(circ, e, d, ylow, (-code) as usize);
+        let chunk = std::env::var("TLM_FOLD_CHUNK_FORCE")
+            .ok()
+            .and_then(|value| value.parse::<usize>().ok())
+            .filter(|&value| value > 0)
+            .unwrap_or((-code) as usize);
+        add_mf_fold_chunked(circ, e, d, ylow, chunk);
     } else {
-        build_fold_at(circ, e, d, ylow, dirty, code as usize);
+        let default_reserve = std::env::var("TLM_TARGET_FOLD_RESERVE")
+            .ok()
+            .and_then(|value| value.parse::<usize>().ok())
+            .unwrap_or(4);
+        let reserve = fold_call_reserve(call_index, default_reserve);
+        let nv = super::target_qubit_headroom(circ)
+            .map_or(code as usize, |headroom| {
+                (code as usize).min(headroom.saturating_sub(reserve))
+            });
+        selected_nv = Some(nv);
+        build_fold_at(circ, e, d, ylow, dirty, nv);
+    }
+    if std::env::var_os("TRACE_TLM_FOLD").is_some() {
+        let local_peak = circ.active_timeline[timeline_start..]
+            .iter()
+            .map(|(_, active)| *active)
+            .max()
+            .unwrap_or(circ.active_qubits);
+        eprintln!(
+            "TLM_FOLD call={} phase={} code={} nv={} entry_active={} local_peak={} ops={}",
+            call_index,
+            circ.phase,
+            code,
+            selected_nv.map_or(-1, |value| value as i32),
+            entry_active,
+            local_peak,
+            circ.current_ops_len(),
+        );
     }
 }
 
@@ -707,6 +836,7 @@ fn fused_fold(circ: &mut B, e: &QubitId, d: &QubitId, ylow: &[QubitId], dirty: &
 /// == 256`; the doubling uses two transient overflow bits (a 258-bit working view),
 /// not a persistent reg slot.
 pub fn fused_double_cdouble(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
+    maybe_run_gradual_fold_nonlinear_control_hmr_selftest();
     let n = 256usize;
     assert_eq!(y.len(), n, "fused double expects 256-bit y (transient overflow)");
     let _ = F_SECP256K1;
@@ -738,6 +868,7 @@ pub fn fused_double_cdouble(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
 /// Exact gate-inverse: `y := y / (2*(1+s2)) mod q`. Reverse of [`fused_double_cdouble`]:
 /// compute the overflow bits, subtract m*f, shift right.
 pub fn fused_double_cdouble_reverse(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
+    maybe_run_gradual_fold_nonlinear_control_hmr_selftest();
     let n = 256usize;
     assert_eq!(y.len(), n, "fused halve expects 256-bit y (transient overflow)");
     let hi = circ.alloc_qubit();
@@ -767,3 +898,108 @@ pub fn fused_double_cdouble_reverse(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
     circ.zero_and_free(hi);
     circ.zero_and_free(hi2);
 }
+
+/// Exhaust every `(e,d,HMR outcome)` basis case for each nonlinear derived
+/// control.  This is available in normal builds because this worktree's wider
+/// `cfg(test)` suite currently has unrelated compile failures.
+fn gradual_fold_nonlinear_control_hmr_selftest() {
+    use crate::circuit::OperationType;
+    use crate::sim::Simulator;
+    use sha3::{
+        digest::{ExtendableOutput, Update},
+        Shake128,
+    };
+
+    // Positions 8, 10, and 11 select OR, d&!e, and AND respectively.
+    for &(position, kind) in &[(8usize, 4u8), (10, 5), (11, 6)] {
+        assert_eq!(fold_ctl(position), kind);
+
+        let mut circ = B::new();
+        let e = circ.alloc_qubit();
+        let d = circ.alloc_qubit();
+        let q = circ.alloc_qubit();
+        on_ctl_apply(&mut circ, &e, &d, kind, &q);
+        on_ctl_free(&mut circ, &e, &d, position, OnCtl::Owned(q));
+
+        assert_eq!(circ.active_qubits, 2, "owned control was not released");
+        assert_eq!(circ.peak_qubits, 3, "cleanup increased peak width");
+        assert_eq!(circ.next_bit, 1, "expected one HMR result bit");
+        assert_eq!(
+            circ.ops
+                .iter()
+                .filter(|op| matches!(op.kind, OperationType::CCX | OperationType::CCZ))
+                .count(),
+            1,
+            "cleanup must add no Toffoli-class gate",
+        );
+        assert_eq!(
+            circ.ops
+                .iter()
+                .filter(|op| op.kind == OperationType::Hmr)
+                .count(),
+            1,
+        );
+
+        // Pack every (e,d) basis state sixteen times.  The fixed SHAKE seed
+        // deterministically supplies both HMR outcomes for every state; the
+        // coverage assertion below keeps that part of the proof explicit.
+        let mut e_mask = 0u64;
+        let mut d_mask = 0u64;
+        for shot in 0..64usize {
+            let state = shot & 3;
+            e_mask |= ((state & 1) as u64) << shot;
+            d_mask |= (((state >> 1) & 1) as u64) << shot;
+        }
+
+        let mut seed = Shake128::default();
+        seed.update(b"gradual-fold-derived-control-hmr");
+        seed.update(&[kind]);
+        let mut xof = seed.finalize_xof();
+        let mut sim = Simulator::new(
+            circ.next_qubit as usize,
+            circ.next_bit as usize,
+            &mut xof,
+        );
+        *sim.qubit_mut(e) = e_mask;
+        *sim.qubit_mut(d) = d_mask;
+        sim.apply_iter(circ.ops.iter());
+
+        assert_eq!(sim.qubit(e), e_mask, "e changed for control kind {kind}");
+        assert_eq!(sim.qubit(d), d_mask, "d changed for control kind {kind}");
+        assert_eq!(sim.qubit(q), 0, "owned control remained dirty for kind {kind}");
+        assert_eq!(sim.phase, 0, "phase feedback failed for control kind {kind}");
+
+        let measured = sim.bits[0];
+        for state in 0..4usize {
+            let mut outcomes = 0u8;
+            for shot in (state..64usize).step_by(4) {
+                outcomes |= 1 << ((measured >> shot) & 1);
+            }
+            assert_eq!(
+                outcomes, 0b11,
+                "HMR outcomes not exhaustive for kind {kind}, state {state}",
+            );
+        }
+    }
+}
+
+fn maybe_run_gradual_fold_nonlinear_control_hmr_selftest() {
+    if std::env::var_os("TLM_FOLD_HMR_CONTROL_SELFTEST").is_none() {
+        return;
+    }
+    static SELFTEST: std::sync::Once = std::sync::Once::new();
+    SELFTEST.call_once(|| {
+        gradual_fold_nonlinear_control_hmr_selftest();
+        eprintln!("TLM_FOLD_HMR_CONTROL_SELFTEST_OK");
+    });
+}
+
+#[cfg(test)]
+mod tests {
+    use super::*;
+
+    #[test]
+    fn gradual_fold_nonlinear_control_hmr_cleanup_is_exact() {
+        gradual_fold_nonlinear_control_hmr_selftest();
+    }
+}
diff --git a/src/point_add/trailmix_ludicrous/gcd.rs b/src/point_add/trailmix_ludicrous/gcd.rs
index fc67bf0..76c602e 100644
--- a/src/point_add/trailmix_ludicrous/gcd.rs
+++ b/src/point_add/trailmix_ludicrous/gcd.rs
@@ -68,26 +68,68 @@ pub fn n3_for_iters(iters: usize) -> usize {
     iters / 3
 }
 
-fn maybe_adjust_late_gcd_k(i: usize, k: usize) -> usize {
-    let after = std::env::var("TLM_GCD_K_ADJUST_AFTER")
-        .ok()
-        .and_then(|s| s.parse::<usize>().ok())
-        .unwrap_or(usize::MAX);
-    let before = std::env::var("TLM_GCD_K_ADJUST_BEFORE")
+fn env_i32(name: &str, default: i32) -> i32 {
+    std::env::var(name)
         .ok()
-        .and_then(|s| s.parse::<usize>().ok())
-        .unwrap_or(usize::MAX);
-    let adj = std::env::var("TLM_GCD_K_ADJUST")
+        .and_then(|value| value.parse::<i32>().ok())
+        .unwrap_or(default)
+}
+
+fn env_usize(name: &str, default: usize) -> usize {
+    std::env::var(name)
         .ok()
-        .and_then(|s| s.parse::<i32>().ok())
-        .unwrap_or(0);
-    if i >= after && i < before && adj != 0 {
-        (k as i32).saturating_add(adj).max(0) as usize
+        .and_then(|value| value.parse::<usize>().ok())
+        .unwrap_or(default)
+}
+
+fn adjust_gcd_k(prefix: &str, i: usize, k: usize) -> usize {
+    if k == usize::MAX {
+        return k;
+    }
+    let adjust = env_i32(&format!("{prefix}_ADJUST"), 0);
+    let after = env_usize(&format!("{prefix}_ADJUST_AFTER"), 0);
+    let before = env_usize(&format!("{prefix}_ADJUST_BEFORE"), usize::MAX);
+    if i >= after && i < before && adjust != 0 {
+        (k as i32).saturating_add(adjust).max(0) as usize
     } else {
         k
     }
 }
 
+fn maybe_adjust_late_gcd_k(i: usize, k: usize) -> usize {
+    let k = adjust_gcd_k("TLM_GCD_K", i, k);
+    adjust_gcd_k("TLM_GCD_K_EXTRA", i, k)
+}
+
+fn trace_step_regions(circ: &mut B, direction: &str, i: usize, region_start: usize) {
+    if std::env::var("TRACE_TLM_GCD_STEPS").is_err() {
+        return;
+    }
+    let threshold = std::env::var("TRACE_TLM_GCD_MIN_Q")
+        .ok()
+        .and_then(|value| value.parse::<u32>().ok())
+        .unwrap_or(1150);
+    let step_max = circ.phase_active_regions[region_start..]
+        .iter()
+        .map(|(_, _, active)| *active)
+        .max()
+        .unwrap_or(circ.active_qubits);
+    if step_max >= threshold {
+        eprintln!(
+            "TLM_GCD_STEP direction={direction} i={i} active_max={step_max} global_peak={} ops={}",
+            circ.peak_qubits,
+            circ.current_ops_len(),
+        );
+        for (_, phase, active) in &circ.phase_active_regions[region_start..] {
+            if *active >= threshold {
+                eprintln!(
+                    "TLM_GCD_STAGE direction={direction} i={i} active_max={active} phase={phase}",
+                );
+            }
+        }
+    }
+}
+
 // =====================================================================
 // MBU AND-uncompute (HMR + conditional-Z), measurement-vented. `t` holds
 // `a AND b` and is returned to |0>.
@@ -323,7 +365,14 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
     let mut tape: Vec<QubitId> = Vec::with_capacity(super::codec::dialog_tape_qubits(n3, iters));
     let mut win_idx = 0usize; // current window
     let mut pending: Vec<QubitId> = Vec::new(); // raw symbol slots of the current window
+    let mut tail4_prefix_encoded = false;
     for i in 0..iters {
+        let trace_region_start = circ.phase_active_regions.len();
+        circ.set_phase(if apply_inv.is_some() {
+            "tlm_inverse_gcd_forward_shift"
+        } else {
+            "tlm_multiply_gcd_forward_shift"
+        });
         let current_n = (SCHED_J2[i] as usize).max(1);
         while u.len() > current_n {
             let q = u.pop().expect("u nonempty");
@@ -358,6 +407,11 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         // 3) swap decision. Step 0: u=q, v=x<q always, so (v<u)=1 deterministically,
         //    so swap = subtracted and no separate swap flag is needed. Else the narrow top-k comparator
         //    decides swap_flag ^= subtracted AND (v < u).
+        circ.set_phase(if apply_inv.is_some() {
+            "tlm_inverse_gcd_forward_compare"
+        } else {
+            "tlm_multiply_gcd_forward_compare"
+        });
         let swp = if i == 0 {
             subtracted
         } else {
@@ -384,6 +438,11 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         };
         // 5) v -= subtracted * u (controlled mod-free subtract on the active width;
         //    post-swap v >= u so no borrow on a fitting input). X-sandwich add.
+        circ.set_phase(if apply_inv.is_some() {
+            "tlm_inverse_gcd_forward_body"
+        } else {
+            "tlm_multiply_gcd_forward_body"
+        });
         for q in &v[..current_n] {
             circ.x(*q);
         }
@@ -394,6 +453,7 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
             &u[..current_n],
             &v[..current_n],
             GcdBit0Mode::ForwardKnownOneAfterCx,
+            apply_inv.map_or(&[], |(xr, _)| &xr[..3]),
         );
         for q in &v[..current_n] {
             circ.x(*q);
@@ -403,6 +463,19 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         // coordinate pair using the live symbol bits, before they are swapped to the
         // tape. Forward iter order matches apply_step_reverse's order, so the tape is
         // never materialized for the apply -> the apply adders run in the GCD's headroom.
+        circ.set_phase(if apply_inv.is_some() {
+            "tlm_inverse_gcd_forward_apply"
+        } else {
+            "tlm_multiply_gcd_forward_apply"
+        });
+        if i >= 250 && std::env::var_os("TRACE_TLM_TAIL").is_some() {
+            eprintln!(
+                "TLM_TAIL direction=forward i={i} active={} tape={} pending={} encoded={tail4_prefix_encoded}",
+                circ.active_qubits,
+                tape.len(),
+                pending.len(),
+            );
+        }
         let parked_v0 = if apply_inv.is_some() && park_even_v0_enabled() {
             let q = v[0];
             Some(park_known_zero(circ, q))
@@ -410,7 +483,17 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
             None
         };
         if let Some((xr, yr)) = apply_inv {
-            apply_step_reverse(circ, i, &subtracted, &swp, &s2, &t1, xr, yr);
+            apply_step_reverse(
+                circ,
+                i,
+                &subtracted,
+                &swp,
+                &s2,
+                &t1,
+                xr,
+                yr,
+                &u[1..4],
+            );
         }
         if let Some(q) = parked_v0 {
             v[0] = restore_known_zero(circ, q);
@@ -420,6 +503,11 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         }
 
         // 6) record the symbol into fresh |0> slots (returning the ancilla to |0>).
+        circ.set_phase(if apply_inv.is_some() {
+            "tlm_inverse_gcd_forward_codec"
+        } else {
+            "tlm_multiply_gcd_forward_codec"
+        });
         let slots: Vec<QubitId> = (0..sym_bits).map(|_| circ.alloc_qubit()).collect();
         circ.swap(subtracted, slots[0]);
         if i == 0 {
@@ -433,18 +521,56 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
             let data = super::codec::compress_step0_with_t1(circ, t1, &slots);
             tape.extend(data);
             win_idx += 1;
+            circ.set_phase("tlm_gcd_step_end");
+            trace_step_regions(
+                circ,
+                if apply_inv.is_some() {
+                    "inverse-forward"
+                } else {
+                    "multiply-forward"
+                },
+                i,
+                trace_region_start,
+            );
             continue;
         }
         pending.extend(slots);
 
         // When the current window's symbols are complete, compress it inline.
         let codec = window_plan[win_idx];
-        if pending.len() == codec.syms() * sym_bits {
+        if codec == super::codec::DialogCodec::Tail4Top32 {
+            if !tail4_prefix_encoded && pending.len() == 3 * sym_bits {
+                pending = super::codec::DialogCodec::Triple.compress_window(circ, &pending);
+                tail4_prefix_encoded = true;
+            } else if tail4_prefix_encoded
+                && pending.len() == super::codec::DialogCodec::Triple.code_bits() + 2 * sym_bits
+            {
+                let last = pending.split_off(super::codec::DialogCodec::Triple.code_bits());
+                let mut raw = super::codec::DialogCodec::Triple.decompress_window(circ, &pending);
+                raw.extend(last);
+                let data = codec.compress_window(circ, &raw);
+                tape.extend(data);
+                pending.clear();
+                tail4_prefix_encoded = false;
+                win_idx += 1;
+            }
+        } else if pending.len() == codec.syms() * sym_bits {
             let data = codec.compress_window(circ, &pending);
             tape.extend(data);
             pending.clear();
             win_idx += 1;
         }
+        circ.set_phase("tlm_gcd_step_end");
+        trace_step_regions(
+            circ,
+            if apply_inv.is_some() {
+                "inverse-forward"
+            } else {
+                "multiply-forward"
+            },
+            i,
+            trace_region_start,
+        );
     }
     assert_eq!(win_idx, window_plan.len(), "all windows compressed");
     assert!(pending.is_empty(), "no leftover symbols");
@@ -492,6 +618,8 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
     // `pending` holds the raw symbol slots of the currently-decompressed window,
     // consumed symbol-by-symbol from the end (reverse symbol order).
     let mut pending: Vec<QubitId> = Vec::new();
+    let mut pending_tail4 = false;
+    let mut tail4_prefix_encoded = false;
 
     // u regrows from 1 bit (forward ended u=0 post-X; re-init u_final=1 via X).
     let mut u: Vec<QubitId> = vec![circ.alloc_qubit()];
@@ -503,6 +631,12 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
     let mut step0_t1: Option<QubitId> = None;
 
     for i in (0..iters).rev() {
+        let trace_region_start = circ.phase_active_regions.len();
+        circ.set_phase(if apply_fwd.is_some() {
+            "tlm_multiply_gcd_reverse_decode"
+        } else {
+            "tlm_inverse_gcd_reverse_decode"
+        });
         let current_n = (SCHED_J2[i] as usize).max(1);
         while u.len() < current_n {
             u.push(circ.alloc_qubit());
@@ -527,10 +661,32 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
             } else {
                 pending = codec.decompress_window(circ, &data);
             }
+            pending_tail4 = codec == super::codec::DialogCodec::Tail4Top32;
+        } else if tail4_prefix_encoded {
+            let suffix = pending.split_off(super::codec::DialogCodec::Triple.code_bits());
+            pending = super::codec::DialogCodec::Triple.decompress_window(circ, &pending);
+            pending.extend(suffix);
+            tail4_prefix_encoded = false;
         }
         // Pull the last symbol (3 bits) off `pending` into the ancilla.
         let plen = pending.len();
         let cur: Vec<QubitId> = pending.split_off(plen - 3);
+        if pending_tail4 && pending.len() == 12 {
+            let suffix = pending.split_off(9);
+            pending = super::codec::DialogCodec::Triple.compress_window(circ, &pending);
+            pending.extend(suffix);
+            tail4_prefix_encoded = true;
+        } else if pending_tail4 && pending.is_empty() {
+            pending_tail4 = false;
+        }
+        if i >= 250 && std::env::var_os("TRACE_TLM_TAIL").is_some() {
+            eprintln!(
+                "TLM_TAIL direction=reverse i={i} active={} tape={} pending={} encoded={tail4_prefix_encoded}",
+                circ.active_qubits,
+                tape.len(),
+                pending.len(),
+            );
+        }
         circ.swap(subtracted, cur[0]);
         let swp = if i == 0 {
             circ.cx(subtracted, cur[1]);
@@ -551,6 +707,11 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
             circ.zero_and_free(q);
         }
 
+        circ.set_phase(if apply_fwd.is_some() {
+            "tlm_multiply_gcd_reverse_apply"
+        } else {
+            "tlm_inverse_gcd_reverse_apply"
+        });
         let parked_u0 = if park_odd_u0_enabled(i, "REV") {
             let q = u[0];
             Some(park_known_one(circ, q))
@@ -570,7 +731,17 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
         };
         if let Some((xr, yr)) = apply_fwd {
             let t1 = step0_t1.unwrap_or(subtracted);
-            apply_step_forward(circ, i, &subtracted, &swp, &s2, &t1, xr, yr);
+            apply_step_forward(
+                circ,
+                i,
+                &subtracted,
+                &swp,
+                &s2,
+                &t1,
+                xr,
+                yr,
+                &u[1..4],
+            );
         }
         if let Some(q) = parked_v0 {
             v[0] = restore_known_zero(circ, q);
@@ -579,6 +750,11 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
         // Inverse step (reverse op order): sub^-1, cswap^-1, cmp^-1, subtracted^-1,
         // s_2^-1, shift1^-1.
         // a) sub^-1: v += subtracted*u (X-sandwich cancels).
+        circ.set_phase(if apply_fwd.is_some() {
+            "tlm_multiply_gcd_reverse_body"
+        } else {
+            "tlm_inverse_gcd_reverse_body"
+        });
         controlled_add_active(
             circ,
             i,
@@ -586,6 +762,7 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
             &u[..current_n],
             &v[..current_n],
             GcdBit0Mode::ReverseKnownZeroBeforeCx,
+            apply_fwd.map_or(&[], |(xr, _)| &xr[..3]),
         );
         if let Some(q) = parked_u0 {
             u[0] = restore_known_one(circ, q);
@@ -633,6 +810,17 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
             let sf = swap_flag.take().expect("swap flag still allocated");
             circ.zero_and_free(sf);
         }
+        circ.set_phase("tlm_gcd_step_end");
+        trace_step_regions(
+            circ,
+            if apply_fwd.is_some() {
+                "multiply-reverse"
+            } else {
+                "inverse-reverse"
+            },
+            i,
+            trace_region_start,
+        );
     }
     assert!(tape.is_empty(), "tape not fully drained");
 
@@ -693,6 +881,7 @@ fn controlled_add_active(
     x: &[QubitId],
     y: &[QubitId],
     bit0_mode: GcdBit0Mode,
+    dirty_vents: &[QubitId],
 ) {
     // The GCD subtract `v -= u` (here `y += x` inside the X-sandwich):
     // a = target = y (= v), b = addend = x (= u). cap = PAD.
@@ -727,7 +916,17 @@ fn controlled_add_active(
     if x.len() > 1 {
         let yr: Vec<&QubitId> = y[1..].iter().collect();
         let xr: Vec<&QubitId> = x[1..].iter().collect();
-        super::gidney::controlled_hybrid_add_capped_branch(circ, ctrl, &yr, &xr, k, super::PAD, branch);
+        super::gidney::with_dirty_vent_pool(dirty_vents, || {
+            super::gidney::controlled_hybrid_add_capped_branch(
+                circ,
+                ctrl,
+                &yr,
+                &xr,
+                k,
+                super::PAD,
+                branch,
+            );
+        });
     }
     if loan_y0 {
         match bit0_mode {
@@ -756,21 +955,34 @@ fn apply_step_forward(
     t1: &QubitId,
     x_reg: &[QubitId],
     y_reg: &[QubitId],
+    dirty_vents: &[QubitId],
 ) {
     let n = 256usize;
 
     // 1) if subtracted: y += x mod q. Apply cofactor add -> cout adder at the
     // schedule's k.
+    circ.set_phase("tlm_apply_forward_mod_add");
     let k = super::next_cout_k();
     let ffg = super::next_ffg();
-    arith::controlled_mod_add_k(circ, sub, &x_reg[..n], &y_reg[..n], Some(k), Some(ffg));
+    super::gidney::with_dirty_vent_pool(dirty_vents, || {
+        arith::controlled_mod_add_k(
+            circ,
+            sub,
+            &x_reg[..n],
+            &y_reg[..n],
+            Some(k),
+            Some(ffg),
+        );
+    });
     // 2) if swap: swap(x, y).
+    circ.set_phase("tlm_apply_forward_swap");
     for j in 0..n {
         circ.cswap(*swp, x_reg[j], y_reg[j]);
     }
     // 3) y := 2*(1+s2)*y mod q. i==0: two separate controlled doublings (shift1 is
     //    t1-gated). i>0: the fused double+cdouble -- one combined (e+2d)*f fold
     //    (the unfused form costs extra inversion Toffoli).
+    circ.set_phase("tlm_apply_forward_fold");
     if i == 0 {
         controlled_mod_double(circ, t1, y_reg);
         controlled_mod_double(circ, s2, y_reg);
@@ -790,11 +1002,13 @@ fn apply_step_reverse(
     t1: &QubitId,
     x_reg: &[QubitId],
     y_reg: &[QubitId],
+    dirty_vents: &[QubitId],
 ) {
     let n = 256usize;
 
     // inverse of 3): i==0 two separate reverse-doublings (s2 halve then t1 halve);
     // i>0 the fused inverse double+cdouble.
+    circ.set_phase("tlm_apply_inverse_fold");
     if i == 0 {
         controlled_mod_double_reverse(circ, s2, y_reg);
         controlled_mod_double_reverse(circ, t1, y_reg);
@@ -802,14 +1016,18 @@ fn apply_step_reverse(
         super::fused::fused_double_cdouble_reverse(circ, s2, y_reg);
     }
     // inverse of 2): swap (involutory).
+    circ.set_phase("tlm_apply_inverse_swap");
     for j in 0..n {
         circ.cswap(*swp, x_reg[j], y_reg[j]);
     }
     // inverse of 1): y -= x mod q. The apply-path operands carry pseudo-Mersenne
     // representation drift, so the borrow clean uses the MBU form.
     // Apply cofactor sub -> schedule cout k.
+    circ.set_phase("tlm_apply_inverse_mod_sub");
     let k = super::next_cout_k();
-    controlled_mod_sub_vented(circ, sub, &x_reg[..n], &y_reg[..n], Some(k));
+    super::gidney::with_dirty_vent_pool(dirty_vents, || {
+        controlled_mod_sub_vented(circ, sub, &x_reg[..n], &y_reg[..n], Some(k));
+    });
 }
 
 /// Apply-path `y := y - ctrl * x (mod q)` whose borrow ancilla is cleaned by
@@ -823,6 +1041,7 @@ fn controlled_mod_sub_vented(circ: &mut B, ctrl: &QubitId, x: &[QubitId], y: &[Q
     let f_bytes = F_SECP256K1.to_le_bytes();
     let anc = circ.alloc_qubit();
     // X-sandwich: ~y += ctrl*x => y -= ctrl*x; cout = ctrl AND borrow.
+    circ.set_phase("tlm_apply_inverse_mod_sub_register");
     for q in y {
         circ.x(*q);
     }
@@ -831,6 +1050,7 @@ fn controlled_mod_sub_vented(circ: &mut B, ctrl: &QubitId, x: &[QubitId], y: &[Q
         circ.x(*q);
     }
     // gated -f fold on the borrow.
+    circ.set_phase("tlm_apply_inverse_mod_sub_fold");
     for q in &y[..arith::LSBS] {
         circ.x(*q);
     }
@@ -847,6 +1067,7 @@ fn controlled_mod_sub_vented(circ: &mut B, ctrl: &QubitId, x: &[QubitId], y: &[Q
     // Z via the Gidney `a + ~b + ~cin` carry chain (~1 Toffoli/bit); cz_if_bit(ctrl,
     // carry) cancels the phase. This never asserts |0>, so operand drift is tolerated.
     // Flip x_top so the comparator's internal `~b` yields `+x_top` (carryout(y+x+1)).
+    circ.set_phase("tlm_apply_inverse_mod_sub_clean");
     let k = arith::MSBS.min(n);
     let lo = n - k;
     let ctrl = *ctrl;
diff --git a/src/point_add/trailmix_ludicrous/gidney.rs b/src/point_add/trailmix_ludicrous/gidney.rs
index 172e225..7c599b1 100644
--- a/src/point_add/trailmix_ludicrous/gidney.rs
+++ b/src/point_add/trailmix_ludicrous/gidney.rs
@@ -12,6 +12,67 @@
 use super::comparator::compare_geq_cin_middle;
 use super::{B, BExt};
 use crate::circuit::{QubitId};
+use std::cell::RefCell;
+
+thread_local! {
+    static DIRTY_VENT_POOL: RefCell<Vec<QubitId>> = const { RefCell::new(Vec::new()) };
+}
+
+pub fn with_dirty_vent_pool<R>(dirty: &[QubitId], body: impl FnOnce() -> R) -> R {
+    let count = std::env::var("TLM_DIRTY_VENTS")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .unwrap_or(0)
+        .min(dirty.len());
+    let prior = DIRTY_VENT_POOL.with(|pool| {
+        std::mem::replace(&mut *pool.borrow_mut(), dirty[..count].to_vec())
+    });
+    let result = body();
+    DIRTY_VENT_POOL.with(|pool| {
+        *pool.borrow_mut() = prior;
+    });
+    result
+}
+
+fn dirty_vent_pool() -> Vec<QubitId> {
+    DIRTY_VENT_POOL.with(|pool| pool.borrow().clone())
+}
+
+fn trace_schedule_fit(
+    trace_env: &str,
+    family: &str,
+    mode: &str,
+    fit: super::ScheduleFit,
+    effective: usize,
+    width: usize,
+    entry_active: u32,
+    timeline_start: usize,
+    ops_start: usize,
+    circ: &B,
+) {
+    if std::env::var_os(trace_env).is_none() {
+        return;
+    }
+    let local_peak = circ.active_timeline[timeline_start..]
+        .iter()
+        .map(|(_, active)| *active)
+        .max()
+        .unwrap_or(entry_active);
+    eprintln!(
+        "TLM_{family} call={} phase={} mode={} width={} base={} selected={} effective={} entry_active={} local_peak={} ops_added={} ops={}",
+        fit.call_index,
+        circ.phase,
+        mode,
+        width,
+        fit.base,
+        fit.selected,
+        effective,
+        entry_active,
+        local_peak,
+        circ.current_ops_len().saturating_sub(ops_start),
+        circ.current_ops_len(),
+    );
+}
 
 // ============================================================================
 // controlled_hybrid_add_refs  (plain Gidney AND-carry adder)
@@ -42,10 +103,15 @@ fn controlled_hybrid_add_refs_impl(circ: &mut B, ctrl: &QubitId, a: &[&QubitId],
         return;
     }
     // Effective vent count, read from the baked schedule; no decision logic here.
-    // When no schedule is loaded (standalone primitive unit tests) `next_hyb_v`
-    // returns usize::MAX, which the `i < vents` loop reads as "vent every carry"
+    // When no schedule is loaded (standalone primitive unit tests), the schedule
+    // value is usize::MAX, which the `i < vents` loop reads as "vent every carry"
     // -- still value-correct.
-    let vents = super::next_hyb_v();
+    let fit = super::next_hyb_v_fit();
+    let timeline_start = circ.active_timeline.len();
+    let entry_active = circ.active_qubits;
+    let ops_start = circ.current_ops_len();
+    let vents = super::target_qubit_headroom(circ)
+        .map_or(fit.selected, |headroom| fit.selected.min(headroom));
 
     // b is the addend (carry-threaded); a is the target.
     for i in 1..n {
@@ -57,13 +123,29 @@ fn controlled_hybrid_add_refs_impl(circ: &mut B, ctrl: &QubitId, a: &[&QubitId],
 
     // Forward carry chain. First `vents` carries land in measurement-vent ancillae;
     // the rest are Toffoli'd straight into b.
-    let mut vent_ancs: Vec<Option<QubitId>> = (0..n - 1).map(|_| None).collect();
+    #[derive(Clone, Copy)]
+    enum VentLane {
+        Clean(QubitId),
+        Dirty(QubitId),
+    }
+    let dirty_pool = dirty_vent_pool();
+    let mut vent_ancs: Vec<Option<VentLane>> = (0..n - 1).map(|_| None).collect();
     for i in 0..n - 1 {
         if i < vents {
-            let anc = circ.alloc_qubit();
-            circ.ccx(*a[i], *b[i], anc); // anc = a[i] & b[i]
-            circ.cx(anc, *b[i + 1]);
-            vent_ancs[i] = Some(anc);
+            if let Some(&dirty) = dirty_pool.get(i) {
+                debug_assert_ne!(dirty, *a[i]);
+                debug_assert_ne!(dirty, *b[i]);
+                debug_assert_ne!(dirty, *b[i + 1]);
+                circ.cx(dirty, *b[i + 1]);
+                circ.ccx(*a[i], *b[i], dirty);
+                circ.cx(dirty, *b[i + 1]);
+                vent_ancs[i] = Some(VentLane::Dirty(dirty));
+            } else {
+                let anc = circ.alloc_qubit();
+                circ.ccx(*a[i], *b[i], anc); // anc = a[i] & b[i]
+                circ.cx(anc, *b[i + 1]);
+                vent_ancs[i] = Some(VentLane::Clean(anc));
+            }
         } else {
             circ.ccx(*a[i], *b[i], *b[i + 1]);
         }
@@ -73,13 +155,21 @@ fn controlled_hybrid_add_refs_impl(circ: &mut B, ctrl: &QubitId, a: &[&QubitId],
     // lanes measure-erase; the rest re-Toffoli.
     for i in (0..n - 1).rev() {
         circ.ccx(*ctrl, *b[i + 1], *a[i + 1]); // controlled sum bit i+1
-        if let Some(anc) = vent_ancs[i].take() {
-            circ.cx(anc, *b[i + 1]); // undo the forward cx
-            // AND-carry erase.
-            let bit = circ.alloc_bit();
-            circ.hmr(anc, bit);
-            circ.zero_and_free(anc);
-            circ.cz_if_bit(*a[i], *b[i], bit);
+        if let Some(lane) = vent_ancs[i].take() {
+            match lane {
+                VentLane::Clean(anc) => {
+                    circ.cx(anc, *b[i + 1]); // undo the forward cx
+                    let bit = circ.alloc_bit();
+                    circ.hmr(anc, bit);
+                    circ.zero_and_free(anc);
+                    circ.cz_if_bit(*a[i], *b[i], bit);
+                }
+                VentLane::Dirty(dirty) => {
+                    circ.cx(dirty, *b[i + 1]);
+                    circ.ccx(*a[i], *b[i], dirty);
+                    circ.cx(dirty, *b[i + 1]);
+                }
+            }
         } else {
             circ.ccx(*a[i], *b[i], *b[i + 1]);
         }
@@ -94,6 +184,18 @@ fn controlled_hybrid_add_refs_impl(circ: &mut B, ctrl: &QubitId, a: &[&QubitId],
     for i in 1..n {
         circ.cx(*b[i], *a[i]);
     }
+    trace_schedule_fit(
+        "TRACE_TLM_HYB",
+        "HYB",
+        if skip_low_ctrl_sum { "skiplow" } else { "plain" },
+        fit,
+        vents,
+        n,
+        entry_active,
+        timeline_start,
+        ops_start,
+        circ,
+    );
 }
 
 // ============================================================================
@@ -182,20 +284,60 @@ fn deref(s: &[&QubitId]) -> Vec<QubitId> {
     s.iter().map(|q| **q).collect()
 }
 
-fn controlled_erase_carry_gated(circ: &mut B, ctrl: &QubitId, a: &[&QubitId], b: &[&QubitId], cin: &QubitId, carry: QubitId) {
+fn controlled_erase_carry_gated_impl(
+    circ: &mut B,
+    ctrl: &QubitId,
+    a: &[&QubitId],
+    b: &[&QubitId],
+    cin: Option<&QubitId>,
+    carry: QubitId,
+) {
     let bit = circ.alloc_bit();
     circ.hmr(carry, bit);
     circ.push_condition(bit);
     let (av, bv) = (deref(a), deref(b));
     let ctrl = *ctrl;
-    compare_geq_cin_middle(circ, &av, &bv, cin, |c, ta, tb, c_prev| {
+    let cin = match cin {
+        Some(cin) => {
+            // HMR has already reset `carry` to |0>. Return that physical lane to
+            // the allocator while the phase-recovery comparator uses the real
+            // incoming carry.
+            circ.loan_zero_qubit(carry);
+            *cin
+        }
+        None => carry,
+    };
+    compare_geq_cin_middle(circ, &av, &bv, &cin, |c, ta, tb, c_prev| {
         // ctrl . NOT c_n = ctrl.1 ^ ctrl.(ta&tb) ^ ctrl.c_prev:
         c.z(ctrl);
         c.ccz(ctrl, *ta, *tb);
         c.cz(ctrl, *c_prev);
     });
     circ.pop_condition();
-    circ.zero_and_free(carry);
+    if cin == carry {
+        circ.zero_and_free(carry);
+    }
+}
+
+fn controlled_erase_carry_gated(
+    circ: &mut B,
+    ctrl: &QubitId,
+    a: &[&QubitId],
+    b: &[&QubitId],
+    cin: &QubitId,
+    carry: QubitId,
+) {
+    controlled_erase_carry_gated_impl(circ, ctrl, a, b, Some(cin), carry);
+}
+
+fn controlled_erase_carry_gated_zero_cin(
+    circ: &mut B,
+    ctrl: &QubitId,
+    a: &[&QubitId],
+    b: &[&QubitId],
+    carry: QubitId,
+) {
+    controlled_erase_carry_gated_impl(circ, ctrl, a, b, None, carry);
 }
 
 fn controlled_erase_carry_gated_capped(
@@ -216,19 +358,35 @@ fn controlled_erase_carry_gated_capped(
     let bit = circ.alloc_bit();
     circ.hmr(carry, bit);
     circ.push_condition(bit);
-    let zcin = circ.alloc_qubit();
     let (av, bv) = (deref(&a[lo..]), deref(&b[lo..]));
     let ctrl = *ctrl;
-    compare_geq_cin_middle(circ, &av, &bv, &zcin, |c, ta, tb, c_prev| {
+    compare_geq_cin_middle(circ, &av, &bv, &carry, |c, ta, tb, c_prev| {
         c.z(ctrl);
         c.ccz(ctrl, *ta, *tb);
         c.cz(ctrl, *c_prev);
     });
-    circ.zero_and_free(zcin);
     circ.pop_condition();
     circ.zero_and_free(carry);
 }
 
+
+fn controlled_erase_carry_gated_capped_zero_cin(
+    circ: &mut B,
+    ctrl: &QubitId,
+    a: &[&QubitId],
+    b: &[&QubitId],
+    carry: QubitId,
+    cap: usize,
+) {
+    if a.len() <= cap {
+        controlled_erase_carry_gated_zero_cin(circ, ctrl, a, b, carry);
+    } else {
+        // The capped comparator starts above the incoming carry and therefore
+        // has the same implementation for a known-zero or retained carry-in.
+        controlled_erase_carry_gated_capped(circ, ctrl, a, b, &carry, carry, cap);
+    }
+}
+
 // ============================================================================
 // controlled_vented_chunk_add  (padded plain-Gidney add with cin/cout)
 // ============================================================================
@@ -342,7 +500,7 @@ fn searched_cout_layout(n: usize, k: usize) -> Option<AdaptiveLayout> {
     }
     let mut best: Option<(usize, AdaptiveLayout)> = None;
     for c in 1..=n {
-        for plain_len in 1..=n {
+        for plain_len in 0..=n {
             let chunked_len = n - plain_len;
             let nchunks = chunked_len.div_ceil(c);
             if nchunks + plain_len + margin > k {
@@ -391,9 +549,7 @@ fn emit_cout_layout(
         let (lo, hi) = bounds[j];
         let carry = carries.pop().expect("carry present");
         if j == 0 {
-            let cin0 = circ.alloc_qubit();
-            controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], &cin0, carry);
-            circ.zero_and_free(cin0);
+            controlled_erase_carry_gated_zero_cin(circ, ctrl, &a[lo..hi], &b[lo..hi], carry);
         } else {
             controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], &carries[j - 1], carry);
         }
@@ -410,7 +566,7 @@ fn searched_gcd_adaptive_layout(n: usize, k: usize) -> Option<AdaptiveLayout> {
         .unwrap_or(1);
     let mut best: Option<(usize, AdaptiveLayout)> = None;
     for c in 1..=n {
-        for plain_len in 1..=n {
+        for plain_len in 0..=n {
             let chunked_len = n - plain_len;
             let nchunks = chunked_len.div_ceil(c);
             if nchunks + plain_len + margin > k {
@@ -458,13 +614,16 @@ fn emit_adaptive_layout_no_cout(
         let cin: &QubitId = carries.last().unwrap_or(&cin0);
         controlled_clean_add_threaded(circ, ctrl, &a[l..n], &b[l..n], Some(cin), None, layout.plain_len);
     }
+    circ.zero_and_free(cin0);
     for j in (0..bounds.len()).rev() {
         let (lo, hi) = bounds[j];
         let carry = carries.pop().expect("carry present");
-        let cin: &QubitId = if j == 0 { &cin0 } else { &carries[j - 1] };
-        controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], cin, carry);
+        if j == 0 {
+            controlled_erase_carry_gated_zero_cin(circ, ctrl, &a[lo..hi], &b[lo..hi], carry);
+        } else {
+            controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], &carries[j - 1], carry);
+        }
     }
-    circ.zero_and_free(cin0);
 }
 
 fn adaptive_add_cost_tof(n: usize, k: usize, controlled: bool) -> u64 {
@@ -520,13 +679,16 @@ fn controlled_chunked_then_cuccaro(circ: &mut B, ctrl: &QubitId, a: &[&QubitId],
     } else if let Some(co) = cout {
         circ.cx(*carries.last().unwrap_or(&cin0), *co);
     }
+    circ.zero_and_free(cin0);
     for j in (0..bounds.len()).rev() {
         let (clo, chi) = bounds[j];
         let carry = carries.pop().expect("carry present");
-        let cin: &QubitId = if j == 0 { &cin0 } else { &carries[j - 1] };
-        controlled_erase_carry_gated(circ, ctrl, &a[clo..chi], &b[clo..chi], cin, carry);
+        if j == 0 {
+            controlled_erase_carry_gated_zero_cin(circ, ctrl, &a[clo..chi], &b[clo..chi], carry);
+        } else {
+            controlled_erase_carry_gated(circ, ctrl, &a[clo..chi], &b[clo..chi], &carries[j - 1], carry);
+        }
     }
-    circ.zero_and_free(cin0);
 }
 
 // ============================================================================
@@ -589,13 +751,16 @@ fn controlled_hybrid_add_adaptive_refs(circ: &mut B, ctrl: &QubitId, a: &[&Qubit
         let cin: &QubitId = carries.last().unwrap_or(&cin0);
         controlled_clean_add_threaded(circ, ctrl, &a[l..n], &b[l..n], Some(cin), None, plain_len);
     }
+    circ.zero_and_free(cin0);
     for j in (0..bounds.len()).rev() {
         let (lo, hi) = bounds[j];
         let carry = carries.pop().expect("carry present");
-        let cin: &QubitId = if j == 0 { &cin0 } else { &carries[j - 1] };
-        controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], cin, carry);
+        if j == 0 {
+            controlled_erase_carry_gated_zero_cin(circ, ctrl, &a[lo..hi], &b[lo..hi], carry);
+        } else {
+            controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], &carries[j - 1], carry);
+        }
     }
-    circ.zero_and_free(cin0);
 }
 
 // ============================================================================
@@ -609,26 +774,70 @@ fn controlled_hybrid_add_varchunk_gated_refs(circ: &mut B, ctrl: &QubitId, a: &[
     }
     let sizes = varchunk_schedule(n, k);
     assert!(!sizes.is_empty(), "varchunk infeasible at k={k} for n={n}");
-    let cin0 = circ.alloc_qubit();
+    let direct = std::env::var("TLM_DIRECT_VARCHUNK")
+        .ok()
+        .as_deref()
+        == Some("1");
+    let cin0 = (!direct).then(|| circ.alloc_qubit());
     let mut carries: Vec<QubitId> = Vec::with_capacity(sizes.len());
     let mut bounds: Vec<(usize, usize)> = Vec::with_capacity(sizes.len());
     let mut lo = 0usize;
     for (j, &s) in sizes.iter().enumerate() {
         let hi = lo + s;
         let cout = circ.alloc_qubit();
-        let cin: &QubitId = if j == 0 { &cin0 } else { &carries[j - 1] };
-        controlled_vented_chunk_add(circ, ctrl, &a[lo..hi], &b[lo..hi], cin, &cout);
+        if direct {
+            // Preserve the baked HYB cursor even though the direct threaded form
+            // does not need a separate vent-count decision.
+            let fit = super::next_hyb_v_fit();
+            let timeline_start = circ.active_timeline.len();
+            let entry_active = circ.active_qubits;
+            let ops_start = circ.current_ops_len();
+            let cin = (j != 0).then(|| &carries[j - 1]);
+            controlled_clean_add_threaded(
+                circ,
+                ctrl,
+                &a[lo..hi],
+                &b[lo..hi],
+                cin,
+                Some(&cout),
+                hi - lo,
+            );
+            trace_schedule_fit(
+                "TRACE_TLM_HYB",
+                "HYB",
+                "direct-varchunk",
+                fit,
+                hi - lo,
+                hi - lo,
+                entry_active,
+                timeline_start,
+                ops_start,
+                circ,
+            );
+        } else {
+            let cin: &QubitId = if j == 0 {
+                cin0.as_ref().expect("legacy cin0")
+            } else {
+                &carries[j - 1]
+            };
+            controlled_vented_chunk_add(circ, ctrl, &a[lo..hi], &b[lo..hi], cin, &cout);
+        }
         carries.push(cout);
         bounds.push((lo, hi));
         lo = hi;
     }
+    if let Some(cin0) = cin0 {
+        circ.zero_and_free(cin0);
+    }
     for j in (0..sizes.len()).rev() {
         let (lo, hi) = bounds[j];
         let carry = carries.pop().expect("carry present");
-        let cin: &QubitId = if j == 0 { &cin0 } else { &carries[j - 1] };
-        controlled_erase_carry_gated_capped(circ, ctrl, &a[lo..hi], &b[lo..hi], cin, carry, cap);
+        if j == 0 {
+            controlled_erase_carry_gated_capped_zero_cin(circ, ctrl, &a[lo..hi], &b[lo..hi], carry, cap);
+        } else {
+            controlled_erase_carry_gated_capped(circ, ctrl, &a[lo..hi], &b[lo..hi], &carries[j - 1], carry, cap);
+        }
     }
-    circ.zero_and_free(cin0);
 }
 
 // ============================================================================
@@ -656,6 +865,15 @@ fn controlled_hybrid_add_knob_capped_refs(circ: &mut B, ctrl: &QubitId, a: &[&Qu
 /// reproduces it.
 pub fn controlled_hybrid_add_capped_branch(circ: &mut B, ctrl: &QubitId, a: &[&QubitId], b: &[&QubitId], k: usize, cap: usize, branch: u8) {
     let n = a.len();
+    let k = super::target_qubit_headroom(circ).map_or(k, |headroom| k.min(headroom));
+    if std::env::var("TLM_GCD_RESELECT_LAYOUT")
+        .ok()
+        .as_deref()
+        == Some("1")
+    {
+        controlled_hybrid_add_knob_capped_refs(circ, ctrl, a, b, k, cap);
+        return;
+    }
     if branch == 1 && n > 0 && !varchunk_schedule(n, k).is_empty() {
         controlled_hybrid_add_varchunk_gated_refs(circ, ctrl, a, b, k, cap);
     } else if branch == 0 {
@@ -676,6 +894,28 @@ pub fn controlled_hybrid_add_capped_branch(circ: &mut B, ctrl: &QubitId, a: &[&Q
 // entry). The apply cofactor-add's q-q core. `k` from the schedule.
 // ============================================================================
 pub fn controlled_hybrid_add_cout_refs(circ: &mut B, ctrl: &QubitId, a: &[&QubitId], b: &[&QubitId], cout: &QubitId, k: usize) {
+    let fit = super::take_cout_fit(k);
+    let timeline_start = circ.active_timeline.len();
+    let entry_active = circ.active_qubits;
+    let ops_start = circ.current_ops_len();
+    let effective = super::target_qubit_headroom(circ)
+        .map_or(fit.selected, |headroom| fit.selected.min(headroom));
+    controlled_hybrid_add_cout_refs_impl(circ, ctrl, a, b, cout, effective);
+    trace_schedule_fit(
+        "TRACE_TLM_COUT",
+        "COUT",
+        "dispatch",
+        fit,
+        effective,
+        a.len(),
+        entry_active,
+        timeline_start,
+        ops_start,
+        circ,
+    );
+}
+
+fn controlled_hybrid_add_cout_refs_impl(circ: &mut B, ctrl: &QubitId, a: &[&QubitId], b: &[&QubitId], cout: &QubitId, k: usize) {
     let n = a.len();
     assert_eq!(b.len(), n, "controlled cout add: a,b width mismatch");
     assert!(n >= 1, "controlled cout add: empty operands");
@@ -721,9 +961,7 @@ pub fn controlled_hybrid_add_cout_refs(circ: &mut B, ctrl: &QubitId, a: &[&Qubit
         let (lo, hi) = bounds[j];
         let carry = carries.pop().expect("carry present");
         if j == 0 {
-            let cin0 = circ.alloc_qubit();
-            controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], &cin0, carry);
-            circ.zero_and_free(cin0);
+            controlled_erase_carry_gated_zero_cin(circ, ctrl, &a[lo..hi], &b[lo..hi], carry);
         } else {
             controlled_erase_carry_gated(circ, ctrl, &a[lo..hi], &b[lo..hi], &carries[j - 1], carry);
         }
diff --git a/src/point_add/trailmix_ludicrous/mcx.rs b/src/point_add/trailmix_ludicrous/mcx.rs
index 0452afc..6039600 100644
--- a/src/point_add/trailmix_ludicrous/mcx.rs
+++ b/src/point_add/trailmix_ludicrous/mcx.rs
@@ -284,3 +284,59 @@ pub fn mcx_clean_k(circ: &mut B, ctrls: &[&QubitId], target: &QubitId) {
         }
     }
 }
+
+/// Increment `a` modulo `2^a.len()` with the Khattar-Gidney prefix ladder.
+pub fn inc_khattar_gidney(circ: &mut B, a: &[QubitId]) {
+    let refs: Vec<&QubitId> = a.iter().collect();
+    inc_khattar_gidney_refs_inner(circ, &refs, false);
+}
+
+/// Controlled increment `a += ctrl (mod 2^a.len())`.
+pub fn cinc_khattar_gidney(circ: &mut B, a: &[QubitId], ctrl: &QubitId) {
+    if a.is_empty() {
+        return;
+    }
+    let mut combined: Vec<&QubitId> = Vec::with_capacity(a.len() + 1);
+    combined.push(ctrl);
+    combined.extend(a.iter());
+    inc_khattar_gidney_refs_inner(circ, &combined, true);
+}
+
+fn inc_khattar_gidney_refs_inner(circ: &mut B, a: &[&QubitId], skip_lsb_x: bool) {
+    let n = a.len();
+    if n == 0 {
+        return;
+    }
+    if n == 1 {
+        if !skip_lsb_x {
+            circ.x(*a[0]);
+        }
+        return;
+    }
+
+    let anc_owned: Vec<QubitId> = (0..kg_prefix_ancilla_count(n - 1))
+        .map(|_| circ.alloc_qubit())
+        .collect();
+    let anc_refs: Vec<&QubitId> = anc_owned.iter().collect();
+    let layers = kg_get_layers_for_prefix_and(&a[..n - 1], &anc_refs);
+
+    for layer in &layers {
+        for &op in &layer.ops {
+            op.emit(circ);
+        }
+    }
+    for (i, layer) in layers.iter().enumerate().rev() {
+        if i < n && !(i == 0 && skip_lsb_x) {
+            kg_apply_prefix_controlled_x(circ, &layer.ctrls, a[i]);
+        }
+        for &op in layer.ops.iter().rev() {
+            op.emit(circ);
+        }
+    }
+
+    drop(layers);
+    drop(anc_refs);
+    for q in anc_owned {
+        circ.zero_and_free(q);
+    }
+}
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index f4d8f46..55cf483 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -26,7 +26,7 @@ pub use schedule::PAD;
 
 use super::B;
 use crate::circuit::{BitId, Op, OperationType, QubitId};
-use std::cell::RefCell;
+use std::cell::{Cell, RefCell};
 use std::collections::HashMap;
 
 const N: usize = 256;
@@ -127,6 +127,19 @@ struct Sched {
 
 thread_local!(static SCHED: RefCell<Sched> = RefCell::new(Sched::default()));
 
+#[derive(Clone, Copy, Debug)]
+pub(super) struct ScheduleFit {
+    pub call_index: usize,
+    pub base: usize,
+    pub selected: usize,
+}
+
+thread_local! {
+    static HYB_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
+    static COUT_CALL_INDEX: Cell<usize> = const { Cell::new(0) };
+    static PENDING_COUT_FIT: Cell<Option<ScheduleFit>> = const { Cell::new(None) };
+}
+
 /// Read the next entry of a `(values, cursor)` slot, returning `exhausted` past
 /// the end (a sentinel meaning "no schedule constraint": full headroom).
 fn step<T: Copy>(slot: &mut (Vec<T>, usize), exhausted: T) -> T {
@@ -150,8 +163,81 @@ fn sub_delta(v: usize, name: &str) -> usize {
     }
 }
 
+fn env_call_value(name: &str, call_index: usize) -> Option<usize> {
+    std::env::var(name).ok().and_then(|value| {
+        value
+            .split(',')
+            .filter_map(|item| item.trim().split_once(':'))
+            .find_map(|(call, value)| {
+                (call.parse::<usize>().ok()? == call_index)
+                    .then(|| value.parse::<usize>().ok())
+                    .flatten()
+            })
+    })
+}
+
+fn next_call_index(counter: &'static std::thread::LocalKey<Cell<usize>>) -> usize {
+    counter.with(|index| {
+        let current = index.get();
+        index.set(current + 1);
+        current
+    })
+}
+
+// Per-call maps use zero-based `call:value` entries separated by commas. An
+// exact override wins; otherwise the global and per-call deltas are cumulative.
+fn fit_schedule_value(
+    base: usize,
+    call_index: usize,
+    global_delta: &str,
+    call_deltas: &str,
+    call_overrides: &str,
+) -> ScheduleFit {
+    let selected = env_call_value(call_overrides, call_index).unwrap_or_else(|| {
+        let globally_adjusted = sub_delta(base, global_delta);
+        match env_call_value(call_deltas, call_index) {
+            Some(delta) if globally_adjusted != usize::MAX => {
+                globally_adjusted.saturating_sub(delta)
+            }
+            _ => globally_adjusted,
+        }
+    });
+    ScheduleFit {
+        call_index,
+        base,
+        selected,
+    }
+}
+
+fn reset_schedule_fit_call_indices() {
+    HYB_CALL_INDEX.with(|index| index.set(0));
+    COUT_CALL_INDEX.with(|index| index.set(0));
+    PENDING_COUT_FIT.with(|pending| pending.set(None));
+}
+
+fn target_qubit_headroom(circ: &B) -> Option<usize> {
+    std::env::var("TLM_TARGET_Q")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .map(|target| target.saturating_sub(circ.active_qubits as usize))
+}
+
 fn next_gcd_k() -> usize { SCHED.with(|s| step(&mut s.borrow_mut().gcd_k, usize::MAX)) }
-fn next_cout_k() -> usize { SCHED.with(|s| sub_delta(step(&mut s.borrow_mut().cout_k, usize::MAX), "TLM_COUT_K_DELTA")) }
+fn next_cout_k() -> usize {
+    let base = SCHED.with(|s| step(&mut s.borrow_mut().cout_k, usize::MAX));
+    let fit = fit_schedule_value(
+        base,
+        next_call_index(&COUT_CALL_INDEX),
+        "TLM_COUT_K_DELTA",
+        "TLM_COUT_K_CALL_DELTAS",
+        "TLM_COUT_K_CALL_OVERRIDES",
+    );
+    PENDING_COUT_FIT.with(|pending| {
+        debug_assert!(pending.get().is_none(), "previous COUT schedule call was not consumed");
+        pending.set(Some(fit));
+    });
+    fit.selected
+}
 fn next_fold() -> i32 {
     SCHED.with(|s| {
         let v = step(&mut s.borrow_mut().fold, i32::MAX);
@@ -166,11 +252,37 @@ fn next_fold() -> i32 {
 fn next_gcd_branch() -> u8 { SCHED.with(|s| step(&mut s.borrow_mut().gcd_branch, 255)) }
 fn next_cmp_k() -> usize { SCHED.with(|s| step(&mut s.borrow_mut().cmp_k, usize::MAX)) }
 fn next_ffg() -> usize { SCHED.with(|s| sub_delta(step(&mut s.borrow_mut().ffg, usize::MAX), "TLM_FFG_DELTA")) }
-fn next_hyb_v() -> usize { SCHED.with(|s| sub_delta(step(&mut s.borrow_mut().hyb_v, usize::MAX), "TLM_HYB_V_DELTA")) }
+fn next_hyb_v_fit() -> ScheduleFit {
+    let base = SCHED.with(|s| step(&mut s.borrow_mut().hyb_v, usize::MAX));
+    fit_schedule_value(
+        base,
+        next_call_index(&HYB_CALL_INDEX),
+        "TLM_HYB_V_DELTA",
+        "TLM_HYB_V_CALL_DELTAS",
+        "TLM_HYB_V_CALL_OVERRIDES",
+    )
+}
+
+fn take_cout_fit(selected: usize) -> ScheduleFit {
+    PENDING_COUT_FIT.with(|pending| {
+        pending.take().unwrap_or_else(|| {
+            fit_schedule_value(
+                selected,
+                next_call_index(&COUT_CALL_INDEX),
+                "TLM_COUT_K_DELTA",
+                "TLM_COUT_K_CALL_DELTAS",
+                "TLM_COUT_K_CALL_OVERRIDES",
+            )
+        })
+    })
+}
 fn next_sqrow_k() -> usize { SCHED.with(|s| step(&mut s.borrow_mut().sqrow_k, usize::MAX)) }
 
 /// Load the product-min jump schedule onto the thread-local cursors.
 fn load_schedule() {
+    reset_schedule_fit_call_indices();
+    arith::reset_ffg_call_index();
+    fused::reset_fold_call_index();
     SCHED.with(|s| {
         let mut s = s.borrow_mut();
         *s = Sched::default();
@@ -284,6 +396,22 @@ pub fn build_trailmix_ludicrous_ops() -> Vec<Op> {
         }
     }
 
+    if std::env::var("TRACE_TLM_PROFILE").is_ok() {
+        circ.close_phase_active_region();
+        eprintln!(
+            "TLM_PROFILE peak_qubits={} peak_phase={} peak_ops_idx={} emitted_ops={}",
+            circ.peak_qubits,
+            circ.peak_phase,
+            circ.peak_ops_idx,
+            circ.current_ops_len(),
+        );
+        let mut phases: Vec<_> = circ.phase_active_max.iter().collect();
+        phases.sort_by(|left, right| right.1.cmp(left.1).then_with(|| left.0.cmp(right.0)));
+        for (phase, active) in phases.into_iter().take(24) {
+            eprintln!("TLM_PHASE active_max={active} phase={phase}");
+        }
+    }
+
     let ops = std::mem::take(&mut circ.ops);
 
     // Sound classical constant-propagation peephole: drop CCX with a provably
```

