# bde4caa — Deeper GCD body-carry trims (3 bits on steps 10–59 and 230–257, 1 bit on 60–229), measured overflow clears in the apply double, and apply cut 190 → 189 (1306 → 1302 qubits)

| | |
| --- | --- |
| Contestant | zuiris |
| Date | 2026-06-07 |
| Submission | `c2f0c6e` |
| Commit | `bde4caa7783ca621854e9a433422a150e0ab58cf` |
| Result | 1302 qubits × 1,456,963 Toffoli = **1,896,965,826** |
| Base | `a88c9a1` (odinfree): 1306 qubits × 1,459,421 Toffoli = 1,906,003,826 |
| Change vs base | qubits −4, Toffoli −2,458, score −9,038,000 |
| Leaderboard Δ | −2,596,188, measured against the frontier at the time, `013f1f7` (the author's own 1302 × 1,458,957), which is **not** this commit's base |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the author's third take on the band-trim lever of
[99b9cff](99b9cff.md) and [013f1f7](013f1f7.md), rebuilt directly on
`a88c9a1` and stacked with two apply-phase cuts.

1. **Deeper body-carry trims.** The dialog-GCD walk's controlled add/sub
   body now skips the top 3 bits on steps 10–59 and 230–257, and the top bit on
   steps 60–229. The trim on the full-width binder steps 10 and 11 lowers the
   peak from 1306 to 1302, and the extra trimmed bits save 1,168 Toffoli.
2. **Measured overflow clears.** It switches on the measured clear of `ovf1`
   and `ovf2` in the apply cell `dialog_gcd_fused_double_y`. `a88c9a1` had
   added that code but left it off. This saves 3 CCX per call, 774 Toffoli in
   total.
3. **One cut moved.** The last chunk cut of the apply adder moves from bit 190
   to 189. That shortens the boundary-carry clear by one bit per apply call,
   516 Toffoli in total.

The sum, −2,458 Toffoli, matches the measured change exactly. The nonce was
re-hunted.

## What changed and why it saves qubits and Toffoli

### `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`

1. **`DIALOG_GCD_BODY_CARRY_BAND_TRIMS`: `0,1,2` →
   `0,3,3,3,3,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,3,3`.**
   - With 26 entries and 258 steps, the bands are 10 steps wide (see
     `dialog_gcd_body_carry_band_trim` in [99b9cff](99b9cff.md)).
   - Old: steps 0–85 trim 0, 86–171 trim 1, 172–257 trim 2. That is 258
     bit-steps.
   - New: steps 0–9 trim 0, 10–59 trim 3, 60–229 trim 1, 230–257 trim 3. That
     is 404 bit-steps.
   - Each trimmed body bit saves a gated-load CCX and a carry CCX in each of
     the 4 walks (forward and reverse, two divisions): (404 − 258) × 8 =
     −1,168 Toffoli.
   - **Peak.** The forward-walk scratch pool asks for `want = 2·body_len − 1`
     lanes. At the 256-wide binder steps 10 and 11, a 3-bit trim lowers it by
     6. The measured peak falls by 4, to 1302, the same tier as `99b9cff`'s
     2-bit trim. So the third bit does not lower the peak: some other phase
     binds at 1302. On these steps it only saves Toffoli.
2. **`DIALOG_GCD_FUSED_OVFCLEAR_MEASURED` = `1`** (new pin; the code is from
   `a88c9a1`).
   - At the end of `dialog_gcd_fused_double_y` (`rounds/dialog/compressed.rs`),
     `ovf1 = (s2 ? y[1] : y[0])` and `ovf2 = s2 ∧ y[0]` hold exactly. The
     stock clears were `ccx(s2, y[1], ovf1)`, an X-wrapped `ccx(¬s2, y[0], ovf1)`,
     and `ccx(s2, y[0], ovf2)`.
   - With the knob on, each overflow bit is cleared by `hmr` plus `cz_if` on
     the same expression (two `cz_if` for the multiplexer form of `ovf1`).
     That costs no Toffoli. See
     [measurement-uncompute](../concepts/measurement-uncompute.md).
   - This saves 3 CCX per call. `double_y` runs once per apply step of one
     division: 258 × 3 = −774.
3. **`DIALOG_GCD_APPLY_CHUNKED_F_CUT4`: 190 → 189.**
   - The apply's controlled modular add/sub (`dialog_gcd_add_ctrl_chunked_low_to_ext`
     and its subtract twin) is split at bits 50, 100, 150 and `CUT4`. The
     boundary carries are cleared afterwards by a prefix comparator over
     `acc[..CUT4]`, one Toffoli per bit. See [21fbfc7](21fbfc7.md).
   - The final chunk here is a plain fast Cuccaro (`APPLY_FINAL_WINDOWED_FAST_BLOCKS=0`,
     `APPLY_FINAL_LOWQ=0`), so moving the cut changes no other cost.
   - This saves 1 Toffoli per apply call: 258 × 2 = −516.
4. **`DIALOG_TAIL_NONCE`: 805000159304 → 11201395269**, with a comment that
   records the validated result.

### Inert additions

- `rounds/dialog/mod.rs`: `dialog_gcd_binder_notch_steps()` and
  `dialog_gcd_binder_notch_extra()`. They add an extra trim at the steps listed
  in `DIALOG_GCD_BINDER_NOTCH_STEPS`. That variable is not set, so this is a
  no-op.
- `rounds/dialog/compressed.rs`: a `PROBE_SCRATCH` debug print in
  `dialog_gcd_build_composite_scratch`.

## Why it is still correct, and what it risks

- **The measured overflow clears are exact.** The stock CCX clears already
  relied on the same Boolean identities, so the measurement resets each bit
  and the phase fix cancels exactly.
- **The cut move is exact.** The chunks still add the same bits, and the
  comparator still recomputes the true boundary carry.
- **The trims are a width truncation.** Each trimmed step is exact only if
  the top 1 or 3 bits of `u` and `v` in the active window, and the carry into
  them, are zero. Three bits at steps 10–59, where the window is still clamped
  at 256, and a 1-bit trim now on every mid-walk step, make this the riskiest
  trim schedule of the series. A violated step gives a wrong GCD state, seen as
  a classical mismatch and as ancilla garbage.

Nonce `11201395269` validated with 0 classical, 0 phase and 0 ancilla failures
over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label is measurement uncompute, which covers the `ovf1`/`ovf2`
clears. That is only −774 of the −2,458 Toffoli and none of the 4-qubit drop.
The larger lever, and the source of the qubit cut, is the deeper body-carry
trim schedule, which is comparator/width truncation (the label of `99b9cff`
and `013f1f7`). The cut move is a small apply-adder retune.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a88c9a1 -- src/point_add`. The author rebuilt this
   tree on `a88c9a1`, not on the git parent `013f1f7`, their own previous
   commit. Against the parent (59 lines) the trim schedule would appear to
   change from `013f1f7`'s `0,2,…` schedule, and the commit would look like it
   undoes `013f1f7`'s steps 60–139 2-bit trims instead of replacing the
   original `0,1,2`. `git diff --ignore-cr-at-eol a88c9a1 bde4caa -- src/point_add`
   is 55 lines in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol bde4caa -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` or `PROBE_*` environment variables set, because
   `set_default_env` only fills in unset variables. Expect:
   - 1302 qubits
   - 1,456,963 average Toffoli (rounded)
   - score 1,896,965,826
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=11201395269` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index e11eba1..ee6ba71 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1244,7 +1244,10 @@ fn configure_ecdsafail_submission_route() {
     // compare schedule frees enough Toffoli to pay back the ~1,088 this saved AND
     // remove that hazard class, making the island materially easier to land while
     // net Toffoli still beats the flat-50 baseline (1,512,823 -> 1,506,043 @ 1313).
-    set_default_env("DIALOG_GCD_BODY_CARRY_BAND_TRIMS", "0,1,2");
+    // Stacked peak-1302 band-trim schedule + measured-ovfclear + F_CUT4=189 (tier-3 "safe lock"):
+    // trims average executed Toffoli to 1,456,963 at peak 1302 qubits.
+    set_default_env("DIALOG_GCD_BODY_CARRY_BAND_TRIMS", "0,3,3,3,3,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,3,3,3");
+    set_default_env("DIALOG_GCD_FUSED_OVFCLEAR_MEASURED", "1");
     // 1320q apply teardown: low-q final chunk plus a hosted boundary split at
     // the second custom-five cut. The retained carry at bit 100 hosts the
     // high-window comparator carry-in, avoiding the generic split's extra
@@ -1267,7 +1270,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "50");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "100");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT3", "150");
-    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT4", "190");
+    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT4", "189");
     // WIDTH_SLOPE tightening: the per-step GCD width envelope shrink rate
     // (ideal = N - step*SLOPE + MARGIN) was left at the default 0.7075 by the
     // whole frontier lineage; only the constant MARGIN was ever tuned. The
@@ -1352,7 +1355,9 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=262 route:
     // nonce 2432 validates 0/0/0 over all 9024 shots at
     // 1309q x 1,497,795 T = 1,960,613,655.
-    set_default_env("DIALOG_TAIL_NONCE", "805000159304");
+    // Re-hunted clean Fiat-Shamir island for the tier-3 schedule:
+    // nonce 11201395269 validates 0/0/0 over all 9024 shots at 1302q x 1,456,963 T = 1,896,965,826.
+    set_default_env("DIALOG_TAIL_NONCE", "11201395269");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
diff --git a/src/point_add/rounds/dialog/compressed.rs b/src/point_add/rounds/dialog/compressed.rs
index 37676c8..a252218 100644
--- a/src/point_add/rounds/dialog/compressed.rs
+++ b/src/point_add/rounds/dialog/compressed.rs
@@ -448,6 +448,18 @@ pub(crate) fn dialog_gcd_build_composite_scratch(
         }
     }
     let owned = b.alloc_qubits(want - lanes.len());
+    if std::env::var("PROBE_SCRATCH").is_ok() && active_width >= 254 {
+        eprintln!(
+            "SCRATCH step={} aw={} body_w={} body_len={} want={} borrowed={} owned={}",
+            step,
+            active_width,
+            body_w,
+            body_len,
+            want,
+            lanes.len() - owned.len(),
+            owned.len()
+        );
+    }
     lanes.extend_from_slice(&owned);
     DialogGcdCompositeScratch { lanes, owned }
 }
diff --git a/src/point_add/rounds/dialog/mod.rs b/src/point_add/rounds/dialog/mod.rs
index 72d8809..1d24f5f 100644
--- a/src/point_add/rounds/dialog/mod.rs
+++ b/src/point_add/rounds/dialog/mod.rs
@@ -218,9 +218,41 @@ pub(crate) fn dialog_gcd_body_carry_trunc_width(active_width: usize, step: usize
     if dialog_gcd_trio_width_notch_enabled() && step == dialog_gcd_trio_width_notch_step() {
         w = w.saturating_add(dialog_gcd_trio_width_notch_extra());
     }
+    // Multi-step binder notch (gated, default OFF). When
+    // DIALOG_GCD_BINDER_NOTCH_STEPS lists `step`, trim an extra
+    // DIALOG_GCD_BINDER_NOTCH_EXTRA (default 2) high bits off the materialized
+    // sub/add body at THIS step too. Under the active nocin body the composite
+    // scratch ask is want = 2*body_len-1, so trimming body_w by k drops the
+    // owned deficit (and thus the compressed-block trio peak) by k at each
+    // listed binder step. Value-exact on the reachable GCD support: at the
+    // width-clamped binder steps the realizable bitlen sits WIDTH_MARGIN below
+    // active_width, so the trimmed top bits of both operands are |0> (the gated
+    // load there is ctrl & 0 = 0 and the carry ripple above the cut is 0).
+    // Absent the env this is a no-op -> byte-identical to the accepted stream.
+    if dialog_gcd_binder_notch_steps().contains(&step) {
+        w = w.saturating_add(dialog_gcd_binder_notch_extra());
+    }
     active_width.saturating_sub(w).max(2)
 }
 
+pub(crate) fn dialog_gcd_binder_notch_steps() -> Vec<usize> {
+    std::env::var("DIALOG_GCD_BINDER_NOTCH_STEPS")
+        .ok()
+        .map(|s| {
+            s.split(',')
+                .filter_map(|t| t.trim().parse::<usize>().ok())
+                .collect()
+        })
+        .unwrap_or_default()
+}
+
+pub(crate) fn dialog_gcd_binder_notch_extra() -> usize {
+    std::env::var("DIALOG_GCD_BINDER_NOTCH_EXTRA")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(2)
+}
+
 pub(crate) fn dialog_gcd_trio_width_notch_enabled() -> bool {
     // Default-on successor from aaf9616: the current route inherited its body
     // geometry, and this one-step notch is needed to reclaim the 1306q tier.
```

