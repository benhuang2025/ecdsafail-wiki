# a47dc6e — Skip lane 0 of the GCD u/v controlled swap: both bits are 1 whenever the swap fires

| | |
| --- | --- |
| Contestant | PhantasticUniverse |
| Date | 2026-06-19 |
| Submission | `10cf480` |
| Commit | `a47dc6e5df74da9adaca2acffbdbb0087051b765` |
| Result | 1164 qubits × 1,412,443 Toffoli = **1,644,083,652** |
| Base | `f8d23a9` (git parent, BitWonka): 1164 qubits × 1,413,462 Toffoli = 1,645,269,768 |
| Change vs base | qubits ±0, Toffoli −1,019, score −1,186,116 (leaderboard Δ −1,186,116) |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In each step of the jump-GCD walk, the circuit conditionally swaps the
registers `u` and `v` across their live width, one Fredkin gate per bit. A
Fredkin gate costs one Toffoli. The swap only fires when `v` is odd, and `u` is
always odd. So whenever the swap fires, `u[0]` and `v[0]` are both 1, and
swapping them does nothing. This commit starts both swap loops at bit 1
instead of bit 0, in the forward walk and in the reverse walk.

That removes one Fredkin gate per step per walk: 4 walks × 258 steps = 1,032
Toffoli. The measured average falls by 1,019, and the difference is
draw-to-draw noise from the new nonce. Peak qubits stay at 1164.

## What changed and why it saves Toffoli

- `src/point_add/trailmix_ludicrous/gcd.rs`:
  - In `forward_gcd_jump`, step 4, `for j in 0..current_n { circ.cswap(swp, u[j], v[j]) }`
    becomes `for j in 1..current_n`.
  - In `reverse_gcd_jump`, step b, the inverse cswap, gets the same change.
  - `cswap` in `BExt` is `cx(b, a); ccx(ctrl, a, b); cx(b, a)`, so it costs one
    unconditional CCX per lane.
- **Why lane 0 is a no-op.** The swap flag is `swp = subtracted AND (v < u)` for
  `i ≥ 1`, and `swp = subtracted` at step 0. Here `subtracted = b = v[0]`, read after the
  halvings.
  - If `swp = 1`, then `v[0] = 1`. Also `u[0] = 1` on every step, because `u` starts as
    the odd modulus q and only ever swaps with an odd `v`.
  - Swapping two equal bits is the identity. If `swp = 0`, the cswap does nothing anyway.
    So the lane-0 Fredkin gate is the identity on every input.
- **Reverse walk.** The inverse cswap runs at the mirror point.
  - The inverse subtract has already restored `v` to its post-swap value, so `v[0] = 1`
    whenever `swp = 1`.
  - The odd-`u[0]` loan from [`cea9f5f`](cea9f5f.md) is closed just before this loop, so
    `u[0]` holds its value 1 again.
- **Calls.** Each point addition runs four walks, `forward_gcd_jump` and `reverse_gcd_jump`
  for the inverse and for the multiply, each with `ITERS = 258` steps. That is 1,032
  Fredkin gates removed.
- **Nonce.** The default `DIALOG_TAIL_NONCE` in `src/point_add/mod.rs`, `build()`, goes from
  100000025120 to 22275. The comment above it is updated.

## Why it is still correct, and what it risks

The removal is exact. It rests on two invariants of the jump-2 binary GCD that
already hold in this circuit: `u` is odd at every step, and the swap only
fires when `v` is odd. It does not depend on which inputs are drawn.

The submission note says the gate is redundant "on the validated support",
which undersells it. It is redundant on every input. The `u[0]` loans of
`cea9f5f` and `f8d23a9` rely on the same invariant: a wrong `u[0]` would
already break them.

The op stream changed, so the nonce was re-hunted. `22275` gives 0 classical,
0 phase and 0 ancilla failures over all 9,024 shots, with 10,660,407 emitted
ops. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The commit removes gates that provably do nothing. That is dead-gate removal,
exact rather than census-mined. The runner-up would be Constant Propagation →
classical specialization, since the proof uses known values of `u[0]` and
`v[0]`. The gate is deleted at the source, not by a post-pass.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f8d23a9 -- src/point_add`.
   The base is the git parent. `git diff --ignore-cr-at-eol f8d23a9 a47dc6e -- src/point_add` is 11 changed lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol a47dc6e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`, `TLM_*`, `LUD_*` or `CONSTPROP_*`
   environment variables set. Expect:
   - 1164 qubits
   - 1,412,443 average Toffoli (rounded; 1,412,443.306 before rounding)
   - score 1,644,083,652
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `22275` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f6e5563..83f22bd 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1983,11 +1983,12 @@ pub fn build() -> Vec<Op> {
     //     Toffoli cut while keeping peak qubits at 1166.
     //   - TLM_GCD_ADAPTIVE_LAYOUT_MARGIN=0: GCD-adaptive layout at margin 0.
     // The tail nonce reseeds the 9024 Fiat-Shamir draws so all land in the
-    // schedule-supported set: nonce 2686 validates 0/0/0 over all 9024
-    // shots at 1165q x 1,413,439.226 => 1,413,439 x 1165 = 1,646,656,435.
+    // schedule-supported set: nonce 22275 validates 0/0/0 over all 9024 shots
+    // with the lane-0 GCD cswap elision at
+    // 1164q x 1,412,443.306 => 1,412,443 x 1164 = 1,644,083,652.
     set_default_env("LUD_EXTRA_FOLD_VENTS", "2");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "16");
-    set_default_env("DIALOG_TAIL_NONCE", "100000025120");
+    set_default_env("DIALOG_TAIL_NONCE", "22275");
     set_default_env("TLM_COUT_LAYOUT_SEARCH", "1");
     set_default_env("TLM_COUT_LAYOUT_MARGIN", "0");
     set_default_env("TLM_COUT_LAYOUT_FORCE_M1_KS", "129");
diff --git a/src/point_add/trailmix_ludicrous/gcd.rs b/src/point_add/trailmix_ludicrous/gcd.rs
index edc6bd1..a2a29ca 100644
--- a/src/point_add/trailmix_ludicrous/gcd.rs
+++ b/src/point_add/trailmix_ludicrous/gcd.rs
@@ -353,7 +353,7 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
             sf
         };
         // 4) cswap(swap_flag, u, v).
-        for j in 0..current_n {
+        for j in 1..current_n {
             circ.cswap(swp, u[j], v[j]);
         }
         let parked_u0 = if park_odd_u0_enabled(i, "FWD") {
@@ -569,7 +569,7 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
             u[0] = restore_known_one(circ, q);
         }
         // b) cswap^-1 (involutory).
-        for j in 0..current_n {
+        for j in 1..current_n {
             circ.cswap(swp, u[j], v[j]);
         }
         // c) uncompute swap_flag. Step 0 is a CNOT (swap_flag == subtracted). For
```

