# 4b9cfbb — Erase the 20-bit apply-phase overflow and underflow compares by measurement (40 → 20 Toffoli per call)

| | |
| --- | --- |
| Contestant | saucegodbased |
| Date | 2026-06-02 |
| Submission | `690bdb9` |
| Commit | `4b9cfbb55d002bb23ca020ae101d3e332fe275e5` |
| Result | 1698 qubits × 1,928,442 Toffoli = **3,274,494,516** |
| Base | `3c30191` (git parent and frontier at the time, jtrose24): 1698 qubits × 1,952,382 Toffoli = 3,315,144,636 |
| Change vs base | qubits ±0, Toffoli −23,940, score −40,650,120 (leaderboard Δ −40,650,120) |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In the early-June dialog-GCD circuit, every apply step does a controlled
modular add or subtract. The add or subtract leaves an overflow bit, and the
circuit clears that bit with a comparison of the top 20 bits of two registers.
Those comparisons used `cmp_lt_into`, a comparator with no carry wires that
runs its carry chain forward and then backward. That costs 2 Toffoli per bit.
This commit switches the five call sites (in three functions) to `cmp_lt_into_fast`. That version
writes the carries into fresh wires and erases them by measurement, so it costs
1 Toffoli per bit. The window stays at 20 bits, so each call saves 20 Toffoli.
There are 1,197 calls, which saves 23,940 Toffoli. The 21 extra wires are
alive only while no larger scratch is alive, so the peak stays at 1698. The
reroll count changes from 5 to 2 because the op stream changed.

## What changed and why it saves Toffoli

**Circuit context (early June).** `build_builder()` in `src/point_add/mod.rs`
first calls `configure_ecdsafail_submission_route()`, which pins the route's
defaults with `set_default_env`. It then runs `emit_dialog_gcd_raw_pa`:

- Pair 1, `emit_dialog_gcd_raw_quotient`, computes λ = dy/dx.
- `round84_emit_fused_square_xtail` forms x3.
- Pair 2, `emit_dialog_gcd_raw_ipmul`, multiplies λ·(x1 − x3).

Both pairs use the same reversible binary GCD, the "dialog"; see
[trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) for its lineage. A
*tobitvector* walk runs `DIALOG_GCD_ACTIVE_ITERATIONS` = 399 steps on
(u, v) = (p, factor). Each step logs two bits:

- `b0` = v is odd;
- `b0_and_b1` = v is odd and u > v (the swap bit).

An *apply* loop then replays the log on a second register pair (x, y). Pair 2
runs it forward: double y, add x to y if `b0`, swap if `b0_and_b1`. Pair 1 runs
it in reverse: swap, subtract, halve. A reverse walk erases the log at the end.

**The change.** In the apply-step adder `dialog_gcd_cmod_add_materialized_pseudomersenne`:

1. The addend is materialized as `f = ctrl · x` (256 CCX), and the raw
   257-bit sum `acc + f` sets an overflow wire `acc_ovf`.
2. If `acc_ovf` is set, the constant `c = 2^256 − p` is added into the low
   73 bits (`DIALOG_GCD_SPECIAL_ADD_LSBS`).
3. `acc_ovf` is cleared by XOR-ing in the comparison `acc < f`. Because
   `DIALOG_GCD_RAW_APPLY_TRUNCATED_CLEAN=1`, that comparison only looks at
   the top `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` = 20 bits.

The subtract twins, `dialog_gcd_cmod_sub_materialized_pseudomersenne` and
`..._borrowed_subtrahend`, clear the underflow the same way. They compute an
`underflow_pred` with a 20-bit compare, apply `ccx(ctrl, underflow_pred, acc_ovf)`,
and then run the same compare again to clear `underflow_pred`. So each subtract
makes two compare calls.

This commit replaces `cmp_lt_into` with `cmp_lt_into_fast` at all five call
sites (one call in the add, two in each subtract):

- **`cmp_lt_into(u, v, flag)`** negates `u` and runs `n` MAJ gates forward
  (1 CCX each). The top carry is then left in `u[n−1]`, and the function
  copies it to `flag`. It then runs `n` inverse MAJ gates back (1 CCX each).
  The total is 2n Toffoli, with one extra wire, `c_in`.
- **`cmp_lt_into_fast(u, v, flag)`** allocates `c_in` and `n` carry wires.
  It writes each carry with one CCX, copies the top carry to `flag`, and then
  erases each carry with `hmr(carry, m)` followed by `cz_if(u[i−1], v[i], m)`.
  The total is n Toffoli, with n + 1 extra wires that live only during the
  call. See [measurement-uncompute](../concepts/measurement-uncompute.md).

With n = 20, each call saves 20 Toffoli. The forward apply of pair 2 makes 399
add calls, and the reverse apply of pair 1 makes 399 × 2 subtract calls. That
is 1,197 calls, and 1,197 × 20 = 23,940, which is exactly the measured drop.
The `_borrowed_subtrahend` variant is only reached when
`DIALOG_GCD_RAW_QUOTIENT_KEEP_TERMINAL_U` is set, and nothing sets it here, so
it adds nothing to the count.

The new comment at the add site says "peak-safe: add carries already freed".
The 256 carry wires of the raw sum are freed before the clean compare runs, so
the compare's 21 wires fit under the 1698 peak.

`configure_ecdsafail_submission_route()`: `DIALOG_REROLL` goes from 5 to 2.
With `DIALOG_REROLL` = k, `build_builder()` emits k pairs `X(tx[0]); X(tx[0])`
right after the registers are declared. The pairs are the identity and cost
nothing. They only change the hash of the op stream, and so the 9,024 test
inputs. In this era that count plays the role of the later tail nonce.

## Why it is still correct, and what it risks

- **The uncompute is exact.** `cmp_lt_into_fast` computes the same function as
  `cmp_lt_into` on the same 20-bit window. The measured erase is exact on every
  input, because each carry wire still holds exactly the AND that `cz_if`
  undoes. The commit adds no new approximation.
- **The existing approximation is unchanged.** The 20-bit window was already
  approximate. If the two operands agree on all 20 top bits, the compare can
  give the wrong flag and leave `acc_ovf` or `underflow_pred` dirty. A failure
  like that shows up as ancilla or phase garbage. The probability per call is
  still about 2^−20.
- The op stream changed, so the test set changed too. Reroll 2 draws a clean
  set: 0 classical, 0 phase and 0 ancilla failures over 9,024 shots.

## Classification rationale

The comparison and its window are the same. Only the way the comparator's
carries are erased changes, from a coherent reverse sweep to measurement. That
is measurement uncompute. The same edit was later re-applied by the same author
on another line as [`acf2bdb`](acf2bdb.md), and by josusanmartin as
[`985ae0f`](985ae0f.md).

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 3c30191 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 3c30191 4b9cfbb -- src/point_add` is
   15 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 4b9cfbb -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or other route environment variables set, because they
   override the defaults that `configure_ecdsafail_submission_route()` pins.
   Expect:
   - 1698 qubits
   - 1,928,442 average Toffoli (rounded)
   - score 3,274,494,516
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL` = 2 and an identical op stream.
Any other change needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ac90da4..b586ce3 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -23066,7 +23066,8 @@ fn dialog_gcd_cmod_add_materialized_pseudomersenne(
     b.set_phase("dialog_gcd_materialized_special_overflow_clean");
     if dialog_gcd_raw_apply_truncated_clean_enabled() {
         let compare_start = N - dialog_gcd_apply_clean_compare_bits();
-        cmp_lt_into(b, &acc[compare_start..], &f[compare_start..], acc_ovf);
+        // Measured comparator (peak-safe: add carries already freed).
+        cmp_lt_into_fast(b, &acc[compare_start..], &f[compare_start..], acc_ovf);
     } else {
         cmp_lt_into(b, acc, &f, acc_ovf);
     }
@@ -23131,14 +23132,14 @@ fn dialog_gcd_cmod_sub_materialized_pseudomersenne(
         for &q in &a[compare_start..] {
             b.x(q);
         }
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
             underflow_pred,
         );
         b.ccx(ctrl, underflow_pred, acc_ovf);
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
@@ -23293,14 +23294,14 @@ fn dialog_gcd_cmod_sub_materialized_pseudomersenne_borrowed_subtrahend(
         for &q in &a[compare_start..] {
             b.x(q);
         }
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
             underflow_pred,
         );
         b.ccx(ctrl, underflow_pred, acc_ovf);
-        cmp_lt_into(
+        cmp_lt_into_fast(
             b,
             &acc[compare_start..],
             &a[compare_start..],
@@ -27886,7 +27887,9 @@ fn configure_ecdsafail_submission_route() {
     // co-tune the Fiat-Shamir reroll (1 -> 5) to land a clean 9024-shot island.
     // Pure Toffoli reduction (1981734 -> 1952382), peak-neutral at 1698.
     // (Validated 0/0/0 over 9024 via eval_circuit.)
-    set_default_env("DIALOG_REROLL", "5");
+    // Apply-phase clean compares also use the measured comparator
+    // (cmp_lt_into_fast); op stream changes, reroll=2 lands a clean island.
+    set_default_env("DIALOG_REROLL", "2");
 }
 
 fn build_builder() -> B {
```

