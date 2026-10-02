# cc409de — Lift a stale `TLM_FFG_MAX_G = 47` clamp so the shell's 14 constant folds use the clean carry ladder

| | |
| --- | --- |
| Contestant | odinfree (co-author tag: welttowelt) |
| Date | 2026-08-26 |
| Submission | `340b9d0` |
| Commit | `cc409dea6de6cc8f5e40ea78af8ff82b6e427d17` |
| Result | 1266 qubits × 906,709 Toffoli = **1,147,893,594** |
| Base | `1f99759` (git parent, the author's previous submission): 1266 qubits × 906,770 Toffoli = 1,147,970,820 |
| Change vs base | qubits ±0, Toffoli −61, score −77,226 (leaderboard Δ −77,226) |
| Family | Strength Reduction → fast-adder reroute |
| Concepts | [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Outside the divider, the affine-add shell still uses the trailmix-era modular
add/sub helpers in `trailmix_ludicrous/arith.rs`. Each of them ends with a
controlled `+f` fold, `add_f_window`, over the low 56 bits. That routine picks
between a clean carry ladder (one fresh ancilla per carry, cheapest in
Toffoli) and a hybrid that borrows dirty high bits of the register as carries
(fewer ancillas, more Toffoli).

A setting left over from the retired 1153-qubit route capped the number of
clean carries at 47, eight short of the 55 needed. So every one of the 14 live
folds took the hybrid. This commit sets the cap to 55, and all 14 folds now
take the clean ladder. It saves 61 average Toffoli. The extra carry wires are
live only inside the shell's folds, far below the divider's peak, so Q is
unchanged.

## What changed and why it saves Toffoli

- **`src/point_add/mod.rs`, `build()`**: a new `std::env::set_var("TLM_FFG_MAX_G", "55")`
  at the top of the "Q1267 fallback composition" block. The comment explains
  that `configure_q1153_second512_submission_defaults()` pins the value to 47
  for the retired Q1153 route, but the value still applies on this path.
  - Because it is `set_var` and not `set_default_env`, it also overrides any
    value set in the environment.
- **How the cap is used (unchanged code, `add_f_window` in `trailmix_ludicrous/arith.rs`).**
  For a window of `n = lsbs = 56` bits:
  - The routine computes `scheduled_g`: the caller's requested carry count,
    or the free headroom, limited by `TLM_TARGET_Q` reserves and by `n − 1 = 55`.
    It then takes `capped_g = min(scheduled_g, TLM_FFG_MAX_G)`.
  - If `g ≥ n − 1`, it calls `add_f_window_clean`. This allocates 55 fresh
    carry wires, computes each carry with one CCX, and erases the carries with
    `hmr` plus a classically controlled CZ, at no Toffoli. See
    [measurement-uncompute](../concepts/measurement-uncompute.md).
  - Otherwise it calls `add_f_window_hybrid(…, k = g)`. That uses `k` clean
    carries for the low positions and, for the remaining `n − k − 1`
    positions, borrows dirty wires from `reg[lsbs..]`. A dirty-borrow carry
    has to be computed and then undone so the borrowed wire comes back
    unchanged, so it costs more Toffoli per position than a clean carry.
  - With the cap at 47, the top 8 carry positions of each fold went through
    the dirty path. At 55 none do.
- **The callers.** `add_f_window` is called from the shell's modular helpers
  (`controlled_mod_add_k`, `mod_add`, `mod_add_exact`, `mod_add_lowpeak`,
  `mod_add_shifted_low`, `mod_sub_vented`, `mod_rsub_vented_loaded`,
  `mod_double`, and `sub_f_window`). The comment counts 14 live calls in this
  build and measured −45.6 Toffoli over 8 frozen seeds. On the shipped draw it
  is −61. See [modular-fold](../concepts/modular-fold.md) and
  [adders-and-carries](../concepts/adders-and-carries.md).
- **Tail nonce:** `SUB4_PINGPONG_TAIL_NONCE` default 11024017180859 →
  12023044890526.

## Why it is still correct, and what it risks

- **Exact.** Both ladders compute the same 56-bit windowed `+f` add. The
  window itself, and so its dropped top carry, is unchanged, so the set of
  failing inputs is the same. The comment reports bit-identical classical
  failure sets on 8 of 8 frozen seeds.
- **Qubits.** The clean ladder needs up to 8 more carry wires while a fold is
  running. These folds run in the coordinate phases, well below the replay
  peak, so Q stays at 1266. If they had pushed a phase over the peak, the
  qubit count would show it, not a failure channel. See
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
- The op stream changed, so the nonce was re-hunted. The shipped nonce draws a
  clean set: 0 classical, 0 phase and 0 ancilla failures.

## Classification rationale

The same constant add is routed to a cheaper existing adder variant, paid for
with local qubit headroom. That is a fast-adder reroute. Nothing is truncated
or removed, and no new arithmetic is added.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 1f99759 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 1f99759 cc409de -- src/point_add` is
   12 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol cc409de -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   or `TLM_*` environment variables set. Expect:
   - 1266 qubits
   - 906,709 average Toffoli (rounded)
   - score 1,147,893,594
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `12023044890526` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 935b7be..1af218e 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2460,6 +2460,16 @@ pub fn build() -> Vec<Op> {
     // Freeze the Q1267 fallback composition while keeping each knob
     // externally overridable for focused reliability experiments. The
     // pingpong tail nonce intentionally remains at the frontier fallback.
+    // SW-1: TLM_FFG_MAX_G is clamped to 47 by
+    // configure_q1153_second512_submission_defaults(), which belongs to the
+    // RETIRED Q1153 route. It still governs all 14 live add_f_window folds on
+    // this path, where the clamp is not needed: 55 is the width limit and any
+    // value >= 55 is bit-identical. Lifting it converts all 14 to the clean
+    // ladder. Measured -45.566 executed Toffoli, paired over 8 frozen seeds;
+    // lambda_c delta 0 by bit-identical frozen failure sets 8/8; peak unchanged.
+    // Set here, in the promoted route's own block, rather than by editing the
+    // retired installer.
+    std::env::set_var("TLM_FFG_MAX_G", "55");
     set_default_env("SUB4_PINGPONG_LOW56_FOLD", "1");
     set_default_env("SUB4_PP_ROUNDS", "696");
     // Keep one additional multiply traversal round as a bounded reliability
@@ -2581,7 +2591,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(11024017180859);
+            .unwrap_or(12023044890526);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
```

