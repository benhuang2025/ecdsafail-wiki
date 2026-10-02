# 0aa33ed — Narrow the double/halve carry window from 24 to 20 bits and the fold carry window from 22 to 18 bits

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-02 |
| Submission | `634abd5` |
| Commit | `0aa33ed06dd15c9bac929ff166ad53f959706c2f` |
| Result | 1698 qubits × 1,691,097 Toffoli = **2,871,482,706** |
| Base | `ad02935` (the author's previous submission): 1698 qubits × 1,697,569 Toffoli = 2,882,472,162 |
| Change vs base | qubits ±0, Toffoli −6,472, score −10,989,456 |
| Leaderboard Δ | −1,837,955, measured against the frontier at the time, `dd103cd` (1693 × 1,697,177), which is **not** this commit's base |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit tightens two carry-truncation windows that the author added
earlier.

- **Double/halve window: 24 → 20 bits.** The truncated constant adder in the
  modular double and halve now stops its carry ripple 20 bits above bit 32.
  This window came from [`f8a36ba`](f8a36ba.md).
- **Fold window: 22 → 18 bits.** The same kind of adder in the apply-phase
  pseudo-Mersenne fold now stops 18 bits above bit 32. This window came from
  [`ad02935`](ad02935.md).

Every carry position that is removed lies above the constant's top set bit,
so each one costs exactly one Toffoli. Removing four positions from each
adder saves 4 Toffoli per call:

- 820 double/halve calls give 3,280.
- 798 fold calls give 3,192.

The total is 6,472 Toffoli. Qubits stay at 1698. The reroll goes from 22 to
11.

## What changed and why it saves Toffoli

`configure_ecdsafail_submission_route()` in `src/point_add/mod.rs` changes
three pins:

- **`KAL_DOUBLE_CARRY_TRUNC_W`: 24 → 20.**
  `cadd_nbit_const_direct_trunc_fast` and its borrow twin make carry wires
  only up to `last = hi + window`, where `hi = 32` is the top set bit of
  `c = 2^32 + 977`. The last carry moves from 56 to 52. The constant has no
  set bits above 32, so each of carries 53–56 cost 1 CCX
  (`ccx(acc[i], carry_{i−1}, carry_i)`). That is 4 CCX per call. The callers
  are the 399 + 399 apply-loop doubles and halves, the 20 in the x-tail
  square and the 2 in `mod_add_double_qb`, so 820 × 4 = 3,280.
- **`KAL_FOLD_CARRY_TRUNC_W`: 22 → 18.** The 73-bit overflow and underflow
  folds in `dialog_gcd_cmod_add/sub_materialized_pseudomersenne` move their
  last carry from 54 to 50, for the same 4 CCX per call. There are 399 adds
  and 399 subtracts, so 798 × 4 = 3,192.
- **`DIALOG_REROLL`: 22 → 11.** The number of identity `X;X` pairs on
  `tx[0]` that reseed the test set.

`src/point_add/memory/2026-06-02-cswap-floor-analysis.md` is rewritten. It
records that on this base `DIALOG_GCD_WIDTH_MARGIN=27` no longer finds a
clean seed in 24 tries. It also gives where the Toffoli goes: pair 1 about
783k, pair 2 about 764k, the square about 148k. And it recommends replacing
pair 2's GCD-based multiply with a direct multiplier.

The total is 3,280 + 3,192 = 6,472, exactly the measured drop.

## Why it is still correct, and what it risks

Both windows are probabilistic. The truncated adder is wrong only when a carry
from the low bits runs through all of the bits above 32 up to the window edge.
That means a run of about `window + 1` ones in the register just above bit 32.
Each window shrinks by 4 bits, so the per-call failure rate grows about 16
times:

- double/halve: from about 2^−25 to about 2^−21;
- fold: from about 2^−23 to about 2^−19.

There are about 1,600 such calls per shot, so Lambda rises well above the
base's. A trigger corrupts the high bits of y, which is a classical failure. In
the fold, the wrong high bits can also make the following 20-bit clean
compare misjudge, which leaves `acc_ovf` dirty and shows up as ancilla or
phase garbage. The kept carries themselves are still erased exactly, and the
add and subtract twins share each window. Reroll 11
draws a clean set: 0 classical, 0 phase and 0 ancilla failures over 9,024
shots.

## Classification rationale

The published label is "Uncompute Strategy → measurement uncompute", but the
diff changes no uncompute. It narrows two carry-truncation windows, so it is
**Dead-Code and Redundancy Elimination → fold/carry truncation**, the same
type as [`f8a36ba`](f8a36ba.md), which introduced the double/halve window.
The measured erase of the carries was already present and does not change.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout ad02935 -- src/point_add`.
   - Do not start from the git parent `dd103cd`. This commit was built on
     the author's `ad02935`.
   - Against the parent, the diff is 247 lines. It would also revert M3kko's
     396-step cut from [`dd103cd`](dd103cd.md) and pldallairedemers' compare
     cap 62 from [`27530d2`](27530d2.md).
   - Against `ad02935`, `git diff --ignore-cr-at-eol ad02935 0aa33ed -- src/point_add`
     is 59 lines in 2 files, most of them in the memory note.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 0aa33ed -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or other route environment variables set. Expect:
   - 1698 qubits
   - 1,691,097 average Toffoli (rounded)
   - score 2,871,482,706
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL` = 11 and an identical op
stream. Any other change needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/memory/2026-06-02-cswap-floor-analysis.md b/src/point_add/memory/2026-06-02-cswap-floor-analysis.md
index 7915108..b053b46 100644
--- a/src/point_add/memory/2026-06-02-cswap-floor-analysis.md
+++ b/src/point_add/memory/2026-06-02-cswap-floor-analysis.md
@@ -1,6 +1,11 @@
-# 2026-06-02 cswap reduction — FLOOR analysis (mostly negative)
+# 2026-06-02 cswap reduction — FLOOR analysis (NEGATIVE)
 
-Target phases (clean baseline, 1,704,086 / 1698):
+Base during this study moved (concurrent commit 48d2cdf = 1,697,569 / 1698,
+score 2,882,472,162: fold-W22 + round763-dedup + measured-underflow + reroll22).
+cswap phases are IDENTICAL on both bases (tobit 113,860 / apply 102,144), so the
+analysis below holds regardless.
+
+Target phases:
 - `dialog_gcd_compressed_block_tobitvector_cswap` fwd+rev = 227,720 (over u/v, active_width-truncated, 2 pairs)
 - `dialog_gcd_compressed_block_apply_cswap` fwd + `..._reverse_cswap` = 204,288 (full-width N=256 over x/y; 399*256 each)
 
@@ -50,19 +55,35 @@ swap needs all 256 bits. No envelope. (Probe reverted; baseline byte-identical.)
 
 ## Confirmed floors
 - ACTIVE_ITERATIONS=399 = convergence floor (397 -> 1 input fails to converge).
-- margin 27, slope 0.7075 = envelope floor.
+- slope 0.7075 = true GCD shrink rate (0.74 -> 303 mism).
+- margin: on the OLD base (1,704,086) margin 27 reroll 5 was a clean -4,636 win;
+  on the NEW base (1,697,569, reroll22 + fold/dedup/underflow levers baked) that
+  slack is GONE — margin 27 fails over 24 rerolls tried (1-6 mism). So margin is
+  now floored at 28. No clean width win remains for cswap on the current base.
+
+## Net: cswap (432k, 25% of circuit) is at its structural floor. No local lever.
+
+## Where the cswaps actually live (measured via STOP flags)
+- pair1 quotient (GCD division dy/dx):           782,978 CCX
+- pair2 ipmul   (GCD multiply  λ·(x1-x3)):       764,464 CCX  <-- 45% of circuit!
+- round84 square + c-step:                       ~147,571 CCX
+pair2's cswaps = tobit 56,930 + apply-fwd 102,144 (+ reverse). pair1's cswaps =
+tobit 56,930 + apply-reverse 102,144. (apply_cswap phase = pair2 fwd; apply_
+reverse_cswap = pair1.) pair1 and pair2 use DIFFERENT factors (dx vs x1-x3), so
+their transcripts can't be shared.
 
-## Only clean win (width lever, NOT cswap-structural, mostly sub/add)
-`DIALOG_GCD_WIDTH_MARGIN=27 DIALOG_REROLL=5` -> avg Toffoli 1,704,086 ->
-**1,699,450 (-4,636)**, peak 1698, 0/0/0 over 9024. cswap share only ~1,432
-(tobit 113,860 -> 113,144); rest is co-located sub/add. No code change.
-(May not stack cleanly with the stray uncommitted KAL_DOUBLE_CARRY_TRUNC_W=20
-reroll=1 lever — both need their own reroll island; coordinator to merge.)
+## Two viable paths to a BIG cswap cut — both ARCHITECTURAL, not cswap-local
+1. **Replace pair2's GCD-replay multiply with a direct Karatsuba/schoolbook
+   modular multiply.** pair2 is a PURE multiply (λ·(x1-x3)) currently paying 764k
+   CCX of GCD just to multiply (a deliberate qubit-for-Toffoli trade to hold peak
+   1698). A direct mul is ~135-150k CCX (cf round84 square = 135k) -> would erase
+   pair2's 159k cswaps AND ~450k of its add/sub. RISK: peak. Peak 1698 sits in
+   the apply materialized add/sub; a direct mul needs a ~2N product register, so
+   peak-neutrality is NOT guaranteed and must be engineered (reuse freed GCD
+   scratch: compressed_log + raw_block + u). High value, high risk, big change.
+2. Batched / jump GCD (safegcd-style) for pair1: fold T per-step swaps into a 2×2
+   transition matrix on the LOW ~2T bits, apply once to full width (no per-step
+   swaps). Major dialog-GCD core rewrite (see kaliski_jump.rs/round185_halfgcd_*).
 
-## Only viable path to a BIG cswap cut = algorithmic
-Batched / jump GCD (safegcd-style): fold T per-step swaps into a 2×2 transition
-matrix computed on the LOW ~2T bits (cheap swaps), then apply the matrix to the
-full-width values once (full-width mul-add, NO per-step swaps). This is a major
-rewrite of the dialog-GCD core (see kaliski_jump.rs / round185_halfgcd_*). Not a
-safe single-session flag. Recommend the swarm spend cswap effort here or move to
-the reducible phases (materialized add/sub LOAD 227k, materialized_special 408k).
+Recommend: the swarm's cswap/Toffoli budget is best spent on (1). Pure cswap
+local restructuring is exhausted.
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 8ff4591..ffbd509 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -28498,8 +28498,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE", "1");
     set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "8");
-    set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "24");
-    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "22");
+    set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "20");
+    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
     set_default_env("DIALOG_GCD_MEASURED_UNDERFLOW_GATE", "1");
     set_default_env("DIALOG_GCD_COMPARE_BITS", "63");
@@ -28529,7 +28529,7 @@ fn configure_ecdsafail_submission_route() {
     // co-tune the Fiat-Shamir reroll (1 -> 5) to land a clean 9024-shot island.
     // Pure Toffoli reduction (1981734 -> 1952382), peak-neutral at 1698.
     // (Validated 0/0/0 over 9024 via eval_circuit.)
-    set_default_env("DIALOG_REROLL", "22");
+    set_default_env("DIALOG_REROLL", "11");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

