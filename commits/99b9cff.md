# 99b9cff — Re-cut the GCD body-carry trim schedule into 26 bands: trim 2 top bits on steps 10–59 and 230–257 instead of 1–2 bits on steps 86–257 (1306 → 1302 qubits)

| | |
| --- | --- |
| Contestant | zuiris |
| Date | 2026-06-07 |
| Submission | `330ce4f` |
| Commit | `99b9cff8556e866f350ad02a9f51e337ad84ce60` |
| Result | 1302 qubits × 1,460,237 Toffoli = **1,901,228,574** |
| Base | `a88c9a1` (odinfree, git parent and frontier at the time): 1306 qubits × 1,459,421 Toffoli = 1,906,003,826 |
| Change vs base | qubits −4, Toffoli +816, score −4,775,252 (leaderboard Δ −4,775,252) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Each dialog-GCD walk step (background in [98416e4](98416e4.md) and
[3409fbd](3409fbd.md); see [dialog-gcd-early](../concepts/dialog-gcd-early.md)) does a controlled
subtract or add of `u` and `v` over the active window. A per-band "body carry
trim" `w` lets the body skip the top `w` bits of that window. This is safe as
long as those bits of both operands are zero.

The old schedule trimmed nothing on steps 0–85, 1 bit on 86–171 and 2 bits
on 172–257. The new schedule has 26 bands of 10 steps and trims 2 bits on
steps 10–59 and 230–257, and nothing elsewhere.

The point is the early steps. Steps 10 and 11 are the qubit binders: they
still run at the full 256-bit width and ask for the largest scratch pool,
`2·body_len − 1` wires. Two fewer body bits there means 4 fewer scratch wires,
and the peak falls from 1306 to 1302. Dropping the mid-walk trims costs
+816 Toffoli. That is a good trade: 4 qubits are worth about 4,480 Toffoli of
score at this size. The nonce was re-hunted.

## What changed and why it saves qubits

All changes are in `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`.

1. **`DIALOG_GCD_BODY_CARRY_BAND_TRIMS`: `0,1,2` →
   `0,2,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,2,2`.**
   - `dialog_gcd_body_carry_band_trim(step)` in `rounds/dialog/mod.rs` splits
     the `DIALOG_GCD_ACTIVE_ITERATIONS = 258` steps into `len(trims)` bands of
     `ceil(258 / len)` steps. Step `s` is in band `min(s / band_size, len − 1)`.
   - `dialog_gcd_body_carry_trunc_width(active_width, step)` returns
     `active_width − trim` (plus the step-11 notch of `3409fbd`, still on). That
     is the width of the controlled add/sub body and of its gated load. The
     comparator and the cswap keep the full active width.

   | steps | old trim (3 bands of 86) | new trim (26 bands of 10) |
   | --- | --- | --- |
   | 0–9 | 0 | 0 |
   | 10–59 | 0 | 2 |
   | 60–85 | 0 | 0 |
   | 86–171 | 1 | 0 |
   | 172–229 | 2 | 0 |
   | 230–257 | 2 | 2 |

   Total trimmed bit-steps go from 258 to 156.
2. **`DIALOG_TAIL_NONCE`: 805000159304 → 10201428572.** A new comment records
   the validated result.

**Why the peak drops by 4.** In the compressed-block forward walk, each step's
body needs `want = 2·body_len − 1` scratch lanes: one gated-load lane per body
bit and one carry lane per carry (`dialog_gcd_build_composite_scratch`).
Steps 0–11 all have active width 256. Steps 10 and 11 set the 1306 peak (see
[3409fbd](3409fbd.md)). With a 2-bit trim, `body_len` falls by 2 on those
steps, so `want` falls by 4 and the owned scratch falls by 4. The other phases
evidently sit at or below 1302, because the measured peak lands exactly 4
lower. See [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).

**Why Toffoli goes up by 816.** Each trimmed body bit saves 2 Toffoli (one
gated-load CCX and one carry CCX) in each of the 4 walks (forward and reverse,
two divisions). The schedule trims 102 fewer bit-steps than before, so the
cost is 102 × 2 × 4 = +816, exactly the measured change.

## Why it is still correct, and what it risks

The body trim is a width truncation. The body is exact only when the top `w`
bits of `u` and `v` in the active window, and the carry into them, are zero.
The width envelope sits `WIDTH_MARGIN = 10` bits above the expected bit length,
so this holds for almost every input. But the margin is a statistical bound,
not a proof. An earlier comment in the same file records that the old
late-step trims had been switched off once because "the converged operand
bitlen reaches active_width on a handful of reachable inputs".

Moving the trims to steps 10–59 puts them where `u` and `v` are still large and
the envelope is still clamped at 256. The 2-bit trim there relies on the
operands having lost at least 2 bits of length by step 10. Removing the
mid-walk trims takes away some hazard, so the net effect on λ could go either
way.

A failing input gives a wrong GCD state. That shows up as a classical
mismatch, and as ancilla garbage after the reverse walk. Nonce `10201428572`
validated with 0 classical, 0 phase and 0 ancilla failures over all 9,024
shots. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The knob is a width truncation of the GCD body, so comparator/width truncation
matches the mechanism. The purpose and the effect, though, are a 4-qubit peak
cut that pays Toffoli. Register and Scratch Allocation → scratch/ancilla reuse
(as for `3409fbd`), or a peak-reduction label, would describe the outcome
better.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a88c9a1 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol a88c9a1 99b9cff -- src/point_add` is
   8 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 99b9cff -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` only fills
   in unset variables. Expect:
   - 1302 qubits
   - 1,460,237 average Toffoli (rounded)
   - score 1,901,228,574
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=10201428572` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index e11eba1..b399977 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1244,7 +1244,9 @@ fn configure_ecdsafail_submission_route() {
     // compare schedule frees enough Toffoli to pay back the ~1,088 this saved AND
     // remove that hazard class, making the island materially easier to land while
     // net Toffoli still beats the flat-50 baseline (1,512,823 -> 1,506,043 @ 1313).
-    set_default_env("DIALOG_GCD_BODY_CARRY_BAND_TRIMS", "0,1,2");
+    // Stacked peak-1302 band-trim schedule (supersedes the 0,1,2 rationale above):
+    // trims average executed Toffoli to 1,460,237 at peak 1302 qubits.
+    set_default_env("DIALOG_GCD_BODY_CARRY_BAND_TRIMS", "0,2,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,2,2");
     // 1320q apply teardown: low-q final chunk plus a hosted boundary split at
     // the second custom-five cut. The retained carry at bit 100 hosts the
     // high-window comparator carry-in, avoiding the generic split's extra
@@ -1352,7 +1354,9 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=262 route:
     // nonce 2432 validates 0/0/0 over all 9024 shots at
     // 1309q x 1,497,795 T = 1,960,613,655.
-    set_default_env("DIALOG_TAIL_NONCE", "805000159304");
+    // Re-hunted clean Fiat-Shamir island for the stacked band-trim schedule:
+    // nonce 10201428572 validates 0/0/0 over all 9024 shots at 1302q x 1,460,237 T = 1,901,228,574.
+    set_default_env("DIALOG_TAIL_NONCE", "10201428572");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
```

