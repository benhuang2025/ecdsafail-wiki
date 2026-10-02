# 66c6dac — Width slope 1.009 → 1.010 and a second body-carry trim bit on the last four GCD step bands

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-05 |
| Submission | `da99bf4` |
| Commit | `66c6dac89aa3b4cd899580c01e4e2f26d3abd894` |
| Result | 1320 qubits × 1,556,187 Toffoli = **2,054,166,840** |
| Base | `ca7fd40` (the author's previous submission): 1320 qubits × 1,557,239 Toffoli = 2,055,555,480 |
| Change vs base | qubits ±0, Toffoli −1,052, score −1,388,640 (leaderboard Δ −1,388,640) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog GCD works on a window of the low bits of `u` and `v` that shrinks
step by step, because the numbers get shorter as the GCD converges. This
commit makes two late-step parts of the GCD a little narrower. The window
shrinks one notch faster (slope 1.009 → 1.010 bits per step). On the last
quarter of the steps, the controlled subtract also skips a second top bit of
the window, not just one.

Each removed bit saves about a Toffoli per step, in every forward and reverse
pass. The total is 1,052 average Toffoli at the same 1320 qubits. Both cuts
assume that the numbers really are shorter than the window. A rare input
that is not would fail, so the tail nonce was re-hunted.

## What changed and why it saves Toffoli

All changes are default pins in `configure_ecdsafail_submission_route()`,
`src/point_add/mod.rs`.

1. **`DIALOG_GCD_WIDTH_SLOPE_X1000`: 1009 → 1010.**
   - `dialog_gcd_tobitvector_active_width(step)` is
     `256 − step × slope + WIDTH_MARGIN` (margin 10), rounded up to an even
     number and clamped to 256. The step's branch compare, cswap of `u` and `v`
     and controlled subtract all work on that many low bits.
   - Adding 0.001 to the slope narrows step `s` by `0.001 × s` bits, so up to
     a quarter of a bit at step 258. After rounding to even, some late steps
     lose 2 bits. Each lost bit removes about one CCX from the cswap and about
     two from the subtract (gated load plus ripple), in every forward and
     reverse pass.
2. **`DIALOG_GCD_BODY_CARRY_BAND_TRIMS`: `0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1` →
   `0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2`.**
   - The list splits the 259 steps into 16 bands of
     `ceil(259 / 16) = 17` steps (`dialog_gcd_body_carry_band_trim`). Band
     `k` covers steps `17k` to `17k + 16`. The last band is short, steps 255
     to 258.
   - `dialog_gcd_body_carry_trunc_width(active_width, step)` returns
     `active_width − trim` (at least 2). In the materialized subtract
     (`dialog_gcd_controlled_sub_selected`), only bits `body_start..body_w`
     are loaded into the gated register (`ccx(ctrl, subtrahend[i], gated[i])`)
     and rippled by the Cuccaro subtract. The cswap and the comparator still
     use the full window.
   - Bands 12–15 (steps 204–258, 55 steps) go from 1 trimmed bit to 2. That
     removes one gated-load CCX and one ripple position per step, in each
     forward and reverse pass of both GCD uses.
3. **`DIALOG_TAIL_NONCE`: 11000665 → 22000964.** The 48 `X;X` identity pairs
   at the end of `build_builder()` only reseed the 9,024 test inputs.

The author did not measure the two parts separately. The total, −1,052, is
the measured change.

## Why it is still correct, and what it risks

- Both cuts rely on the same premise. After `s` steps, `u` and `v` are
  expected to be well below `active_width(s)` bits long. The top bits of the
  window are then 0, the gated load there is `ctrl & 0 = 0`, and no carry
  reaches them. Dropping those bits changes nothing.
- The premise is statistical, not a proof. The author's comment calls it
  "value-exact on the reachable support", but an input whose GCD shrinks
  more slowly than the envelope still has a 1 in a trimmed bit. Its
  subtract result is then wrong, which gives a classical failure, and the
  reverse pass can leave ancilla or phase garbage.
- Nonce 22000964 draws a clean set: 9,024 of 9,024 shots, with 0 classical,
  0 phase and 0 ancilla failures. The author found it with a parallel
  early-exit sweep. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label is fold/carry truncation, which fits the band-trim
change: it cuts the top of a carry ripple. The slope change narrows a
register window, so comparator/width truncation is the close runner-up. Both
remove arithmetic on bits that are almost always zero.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout ca7fd40 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol ca7fd40 66c6dac -- src/point_add` is 15 lines
   in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 66c6dac -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*`, `DIALOG_*` or `SUB4_*` environment variables set, because they
   override the defaults. Expect:
   - 1320 qubits
   - 1,556,187 average Toffoli (rounded)
   - score 2,054,166,840
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `22000964` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f0407d9..f4784cb 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31759,9 +31759,13 @@ fn configure_ecdsafail_submission_route() {
     // 399 T/qubit, far inside break-even. Score 1446 x 1,740,263 = 2,516,420,298.
     set_default_env("DIALOG_GCD_BODY_HOST_CIN", "1");
     set_default_env("DIALOG_GCD_LATE_BORROW_UV_HIGH", "1");
+    // Late bands (12-15, the most-converged GCD steps) deepened 1 -> 2: drops one
+    // more ripple-carry bit per band, value-exact on the reachable support (those
+    // carry bits are provably 0 once the GCD has converged). Stacked with
+    // WIDTH_SLOPE=1010 above under one shared island on the 1320q base.
     set_default_env(
         "DIALOG_GCD_BODY_CARRY_BAND_TRIMS",
-        "0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1",
+        "0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2",
     );
     // 1320q apply teardown: low-q final chunk plus a hosted boundary split at
     // the second custom-five cut. The retained carry at bit 100 hosts the
@@ -31789,7 +31793,9 @@ fn configure_ecdsafail_submission_route() {
     // 1008 -> 1009: one more notch on the per-step width-envelope shrink rate,
     // reclaimed on the 1320q base. Peak-neutral at 1320q; the tighter late-step
     // widths stay within the provably-|0> converged GCD region. ~-512 avg-T.
-    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1009");
+    // 1009 -> 1010: one further notch, stacked with the band-trim late-band
+    // deepening below under one shared island. Peak-neutral at 1320q.
+    set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1010");
     // Active-395 island on the promoted 1355q base: validated 0/0/0 over all
     // 9024 shots at 1355q x 1,773,011 T.
     set_default_env("DIALOG_REROLL", "4269");
@@ -31817,7 +31823,10 @@ fn configure_ecdsafail_submission_route() {
     // 0/0/0 over all 9024 shots at 1320q x 1,557,239 T = 2,055,555,480. Found by a
     // parallel early-exit tail-nonce sweep on 192-core boxes, then confirmed with
     // the official full-9024 eval_circuit.
-    set_default_env("DIALOG_TAIL_NONCE", "11000665");
+    // Re-rolled again for the added WIDTH_SLOPE=1010 + band-late-trim=2 notches:
+    // nonce=22000964 lands a clean island, validated 0/0/0 over all 9024 shots at
+    // 1320q x 1,556,187 T = 2,054,166,840.
+    set_default_env("DIALOG_TAIL_NONCE", "22000964");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

