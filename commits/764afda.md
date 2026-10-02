# 764afda — Two extra clean vents (instead of one) in the apply +f folds from g ≥ 18, plus the GCD layout margin 0

| | |
| --- | --- |
| Contestant | gnuchev |
| Date | 2026-06-19 |
| Submission | `a21cbeb` |
| Commit | `764afdaa9064b74f73ca911afde5296f43a5e527` |
| Result | 1166 qubits × 1,416,037 Toffoli = **1,651,099,142** |
| Base | `bc2334a` (BitWonka): 1166 qubits × 1,416,103 Toffoli = 1,651,176,098 |
| Change vs base | qubits ±0, Toffoli −66, score −76,956 |
| Leaderboard Δ | −39,644, measured against the frontier at the time, `916c0e3` (git parent, 1166 × 1,416,071), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit changes two env defaults in `build()` and adds a third.

- The first two change the baked per-call vent counts of the apply-step `+f` overflow folds.
  - Before, every fold whose scheduled count `g` was at least 24 got one extra clean carry wire.
  - Now every fold with `g ≥ 18` gets two, capped at 53.
  - More clean carries move bits out of the more expensive chunked part of the fold adder,
    which saves Toffoli at the cost of more live wires during the fold.
- The third sets the GCD adaptive layout margin to 0. That is the same lever as
  [`916c0e3`](916c0e3.md), found independently on the same base.

Average Toffoli drops by 66 against `bc2334a`, and the peak stays at 1166. The
tail nonce was re-hunted.

## What changed and why it saves Toffoli

All effective changes are `set_default_env` lines in `build()`, `src/point_add/mod.rs`:

1. **`LUD_EXTRA_FOLD_VENTS`: 1 → 2, `LUD_EXTRA_FOLD_MIN_G`: 24 → 18.**
   - `load_schedule()` in `trailmix_ludicrous/mod.rs` copies the baked list
     `schedule::FFG_G` (516 entries, one per apply cofactor add/sub, in emission
     order). It maps each entry `x` with `x ≥ MIN_G` to `min(x + VENTS, 53)`.
   - **What `g` is.** Each apply step's `controlled_mod_add_k` ends with
     `add_f_window`, which adds the folding constant `f = 2^32 + 977` into the low
     `LSBS = 54` bits under the overflow flag. That is the pseudo-Mersenne fold of the
     carry-out; see [modular-fold](../concepts/modular-fold.md).
     - With `g = 53 = n − 1`, the add is fully clean (`add_f_window_clean`). Every carry
       gets its own wire and is erased by `hmr` plus `cz_if_bit`, at about one
       Toffoli per bit.
     - With `g < 53`, `add_f_window_hybrid` gives only the low `g` bits clean
       measured carries. The upper `54 − g` bits are added by
       `controlled_add_const_chunked_graduated_off`, a chunked constant adder whose
       boundary carries need extra compare Toffoli to erase.
     - So a larger `g` means fewer Toffoli and more wires held during the fold. The
       schedule sized `g` to the free headroom at each call.
   - **Which calls change.** Of the 516 entries, 389 are already 53. In the base,
     with `V = 1` and `G ≥ 24`, 100 entries got +1. Now those 100 get +2, and the 12
     entries with values 18 to 23 also get +2. The 15 entries below 18 (9 to 16) are unchanged.
     These counts come from the table, and the arithmetic is mine.
   - The peak stays at 1166, so the extra wires fit under the high-water mark at all
     112 calls.
2. **`TLM_GCD_ADAPTIVE_LAYOUT_MARGIN=0`** (new). It removes the one spare wire that
   `searched_gcd_adaptive_layout()` kept in the 48 GCD branch-2 subtracts. It is the
   same edit and the same reasoning as in [`916c0e3`](916c0e3.md).
3. **Nonce.** The default `DIALOG_TAIL_NONCE` in `build()` goes from 100000004549 to
   333000003142. A stale comment in `build()` about the layout search is dropped.

`configure_ecdsafail_submission_route()` gets the same knobs. Its three
nonce lines change, including an unrelated older one, 200005858317, all to
333000003142. These edits are dead: that function is only called by
`build_builder()`, and nothing calls `build_builder()` on the trailmix route.

The submission does not split the saving between the two levers. The
margin change alone gave −32 in [`916c0e3`](916c0e3.md), but that figure includes
nonce noise. The fold change is therefore worth roughly −34.

## Why it is still correct, and what it risks

Both edits are exact.

- The fold adder computes `reg[..54] += ctrl·f mod 2^54` with any `g`. Changing `g`
  only moves the boundary between clean measured carries and the chunked suffix.
  The fold's own approximation is unchanged: it drops the carry out of bit 53, an
  error of about 2^−PAD with PAD = 21.
- The layout margin also only changes the geometry of an exact adder.

The real risk is the peak. A larger `g`, or a zero margin, uses one or two more
wires at that call. If a fold sat at the high-water mark, Q would rise. The
measured peak is still 1166. The nonce was re-hunted for the new op stream:
`333000003142` gives 0 classical, 0 phase and 0 ancilla failures over all
9,024 shots, and the emitted op count is 10,674,109. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The fold edit tunes the vent schedule of a fold adder, and the fold itself is
truncated. That is why the census calls it fold/carry truncation. Strictly, the
truncation window does not move. More carries become measured-vented instead of
chunked, so **Register and Scratch Allocation → ancilla-lifetime / venting**
describes the mechanism better. The header keeps the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout bc2334a -- src/point_add`.
   - `git diff --ignore-cr-at-eol bc2334a 764afda -- src/point_add` is 23 changed lines in 1 file.
   - The git parent `916c0e3` is also a valid start; its diff is 26 lines. That diff would
     not show the margin-0 line, which the parent already has, and would hide that this
     commit found that lever on its own.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol 764afda -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`, `TLM_*` or `LUD_*`
   environment variables set, because they override the defaults in the source. Expect:
   - 1166 qubits
   - 1,416,037 average Toffoli (rounded; 1,416,036.679 before rounding)
   - score 1,651,099,142
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `333000003142` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 9113895..7790b92 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1108,9 +1108,13 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_TOBITVECTOR_CSWAP_BODY_TRIM", "0");
     set_default_env("DIALOG_GCD_WIDTH_MARGIN", "10");
     set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1017");
-    set_default_env("DIALOG_TAIL_NONCE", "100000004549");
-    set_default_env("LUD_EXTRA_FOLD_VENTS", "1");
-    set_default_env("LUD_EXTRA_FOLD_MIN_G", "24");
+    set_default_env("DIALOG_TAIL_NONCE", "333000003142");
+    set_default_env("LUD_EXTRA_FOLD_VENTS", "2");
+    set_default_env("LUD_EXTRA_FOLD_MIN_G", "18");
+    set_default_env("TLM_COUT_LAYOUT_SEARCH", "1");
+    set_default_env("TLM_COUT_LAYOUT_MARGIN", "1");
+    set_default_env("TLM_GCD_ADAPTIVE_LAYOUT_SEARCH", "1");
+    set_default_env("TLM_GCD_ADAPTIVE_LAYOUT_MARGIN", "0");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "19");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "18");
     set_default_env("SQUARE_ROW_MAX_SEG", "141");
@@ -1135,7 +1139,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR", "1");
     set_default_env("ROUND84_KEEP_QUOTIENT_PRODUCT", "1");
     set_default_env("DIALOG_GCD_FOLD_CARRY_TRUNC_W", "17");
-    set_default_env("DIALOG_TAIL_NONCE", "100000004549");
+    set_default_env("DIALOG_TAIL_NONCE", "333000003142");
     set_default_env("DIALOG_GCD_SKIP_ZERO_EDGE_CSHIFT", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
     set_default_env("DIALOG_GCD_HOST_REVERSE_RAW_BLOCK", "1");
@@ -1586,7 +1590,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "200005858317");
+    set_default_env("DIALOG_TAIL_NONCE", "333000003142");
     set_default_env("ROUND84_FOLD_FAST_ADD", "0");  // round84 Solinas-fold small adders coherent->measured-fast (-1,434 exec-T, peak-neutral 1285)
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_FOLD_MAJ1", "1");
@@ -1975,14 +1979,13 @@ pub fn build() -> Vec<Op> {
     // Toffoli). One extra fold vent from FFG_G >= 24 trims the schedule; the
     // tail nonce reseeds the Fiat-Shamir inputs so all 9024 verifier draws land
     // in the schedule-supported set.
-    set_default_env("LUD_EXTRA_FOLD_VENTS", "1");
-    set_default_env("LUD_EXTRA_FOLD_MIN_G", "24");
-    set_default_env("DIALOG_TAIL_NONCE", "100000004549");
-    // REC: codex trailmix Toffoli-layout edge (cout-search margin1 + gcd-adaptive),
-    // baked so the env-less grader/engine reproduce it (~-7.53M score-if-clean).
+    set_default_env("LUD_EXTRA_FOLD_VENTS", "2");
+    set_default_env("LUD_EXTRA_FOLD_MIN_G", "18");
+    set_default_env("DIALOG_TAIL_NONCE", "333000003142");
     set_default_env("TLM_COUT_LAYOUT_SEARCH", "1");
     set_default_env("TLM_COUT_LAYOUT_MARGIN", "1");
     set_default_env("TLM_GCD_ADAPTIVE_LAYOUT_SEARCH", "1");
+    set_default_env("TLM_GCD_ADAPTIVE_LAYOUT_MARGIN", "0");
     trailmix_ludicrous::build_trailmix_ludicrous_ops()
 }
 
```

