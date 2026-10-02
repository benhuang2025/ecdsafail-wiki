# c9c03de — Cap the trailmix fold schedule at 52 clean carries (an exact re-shape with the same Toffoli count) and re-roll the nonce

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-06-19 |
| Submission | `1bc49b0` |
| Commit | `c9c03de2475cc172c47463a5a3d3fbd6ccbb7f40` |
| Result | 1166 qubits × 1,422,586 Toffoli = **1,658,735,276** |
| Base | `5407215` (git parent, the author's previous submission): 1166 qubits × 1,422,590 Toffoli = 1,658,739,940 |
| Change vs base | qubits ±0, Toffoli −4, score −4,664 (leaderboard Δ −4,664) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [modular-fold](../concepts/modular-fold.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit adds a set of environment-driven "overlays" that can edit the
baked trailmix schedules when they are loaded. It turns on one of them,
`TRAILMIX_FOLD_LOW_BITS = 52`. That caps every fused-fold entry of the
schedule at 52 clean carries; 384 of the 514 entries were 53, meaning
fully clean. Those folds now use the "clean-tail" form: a 52-carry chain plus
a 2-bit increment for the pure-propagation top.

The two forms compute the same value and contain the same number of Toffoli
gates. The clean-tail form only drops 8 non-Toffoli ops per call (3,072 in
all) and one carry ancilla. The 4-Toffoli drop in the score therefore comes
from the new nonce's test draw, not from cheaper arithmetic.

## What changed and why the score moves

### `src/point_add/trailmix_ludicrous/mod.rs`

- New `apply_route_overlays(&mut Sched)`, called at the end of
  `load_schedule()`. It reads optional variables:
  - `TRAILMIX_APPLY_COUT_K_DELTA`, `TRAILMIX_CMP_K_DELTA`,
    `TRAILMIX_FFG_G_DELTA`, `TRAILMIX_HYB_V_DELTA` and
    `TRAILMIX_SQ_ROW_K_DELTA` add a signed delta to every entry of that table
    (`apply_delta_usize`);
  - `TRAILMIX_FOLD_LOW_BITS` caps every non-negative `FOLD_SCHED` entry at the
    given value, clamped to `LSBS − 1 = 53` (`cap_positive_fold`);
  - `TRAILMIX_FOLD_SCHED_DELTA` adds deltas to the `all`, `first`, `mid` or
    `last` third of `FOLD_SCHED` (`apply_fold_sched_delta`).
- Only `TRAILMIX_FOLD_LOW_BITS` is set by this commit.

### `src/point_add/mod.rs`, `build()`

- `std::env::set_var("TRAILMIX_FOLD_LOW_BITS", "52")`.
- `std::env::set_var("DIALOG_TAIL_NONCE", "62632")`. It was
  `set_default_env(…, "46193")`.
- Both now use `set_var`, so they overwrite any value in the caller's
  environment.

### What the cap does (`trailmix_ludicrous/fused.rs`, unchanged code)

- `fused_double_cdouble` (the GCD-step `y := 2y(1 + s2)`) and its reverse call
  `fused_fold`. That function reads the next `FOLD_SCHED` code. Negative
  means the chunked fold. Otherwise the code is `nv`, the number of clean
  carries, and goes to `build_fold_at` with the fold window `L = LSBS = 54`.
- Base: 384 entries are `53 = L − 1`, so `build_fold_at` takes
  `add_mf_fold_clean`. That is a Gidney-style clean carry chain over bits 0 to
  52, with the top bit 53 set by a CNOT from carry 52. Each carry is
  uncomputed with `hmr` plus a conditional Z. See
  [measurement-uncompute](../concepts/measurement-uncompute.md).
- New: the entries become 52, which is at least `PROP_FROM = 34`, so it takes
  `add_mf_fold_clean_tail(…, Some(52))`. This version builds carries 1 to 51.
  For the top bits 52 and 53, where the `(e + 2d)·f` addend is zero, it adds
  carry 51 with `add_carry_into_tail_prefix`: a `ccx(c, y52, y53)` and a
  `cx(c, y52)`.
- Toffoli count per call: the full-clean chain has one CCX per carry for
  carries 1 to 52, and the top bit costs nothing. The tail form has carries 1
  to 51 plus one CCX in the 2-bit increment. Both total the same.
  - The tail form saves the CNOTs, the allocation and the `hmr`/`cz` of
    carry 52, about 8 ops per call. 384 × 8 = 3,072, which matches the
    submission note's emitted-op count (10,752,822 against 10,755,894 for the
    1166-qubit trailmix tree).
  - The carry ancilla it saves is not at the peak, so qubits stay at 1166.
- **Why the score changed anyway.** The score uses average *executed*
  Toffoli. Many of these are classically conditioned on measurement outcomes,
  so the average depends on the test draw: 1,422,589.641 for the base's
  nonce against 1,422,585.725 here. See
  [scoring-and-validation](../concepts/scoring-and-validation.md).

## Why it is still correct, and what it risks

- **Exact.** Both fold forms compute the same sum in the 54-bit window. The
  only approximation, dropping the carry out of bit 53 (the `PAD` truncation),
  is the same in both. The change adds no new hard input.
- **Nonce.** The op stream changed, so the nonce was re-hunted. The author
  calibrated a trailmix GPU scanner on the known-good nonce 6147, scanned
  100k nonces and confirmed `62632` with the CPU `eval_circuit`. It gives 0
  classical, 0 phase and 0 ancilla failures over 9,024 shots. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label is fold/carry truncation. The code does lower the fold
schedule's "clean vents" number. But for these entries (53 → 52, still at
least 34) the lower number selects an equivalent construction with the same
Toffoli count; it does not narrow the fold window. The −4 Toffoli is draw
noise. The diff suggests either "Verifier Search → nonce/island reroll" for the
score effect, or a small exact restructure of the fold top. The header keeps
the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 5407215 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 5407215 c9c03de -- src/point_add` is
   91 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol c9c03de -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `TRAILMIX_*`, `DIALOG_*`, `TLM_*` or `LUD_*` environment variables set.
   `build()` now forces the fold cap and the nonce with `set_var`. Expect:
   - 1166 qubits
   - 1,422,586 average Toffoli (1,422,585.725 before rounding)
   - score 1,658,735,276
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `62632` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 058b487..19181c8 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1968,11 +1968,10 @@ pub fn build() -> Vec<Op> {
             return Vec::new();
         }
     }
-    // Submitted circuit: the trailmix-ludicrous product-min secp256k1 point-add
-    // at the nonce-ground operating point (1166 qubits x 1,422,616 executed
-    // Toffoli). The tail nonce reseeds the Fiat-Shamir inputs so all 9024
-    // verifier draws land in the schedule-supported set.
-    set_default_env("DIALOG_TAIL_NONCE", "46193");
+    // Submitted circuit: trailmix-ludicrous with the low fold schedule capped at
+    // 52 and a nonce-ground operating point found by the trailmix GPU scanner.
+    std::env::set_var("TRAILMIX_FOLD_LOW_BITS", "52");
+    std::env::set_var("DIALOG_TAIL_NONCE", "62632");
     trailmix_ludicrous::build_trailmix_ludicrous_ops()
 }
 
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index cb7a19d..e75fd81 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -119,6 +119,87 @@ fn step<T: Copy>(slot: &mut (Vec<T>, usize), exhausted: T) -> T {
     v
 }
 
+fn env_i32(name: &str) -> Option<i32> {
+    std::env::var(name).ok()?.parse::<i32>().ok()
+}
+
+fn apply_delta_usize(values: &mut [usize], delta: i32, max: Option<usize>) {
+    let mag = delta.saturating_abs() as usize;
+    for value in values {
+        let next = if delta < 0 {
+            value.saturating_sub(mag)
+        } else {
+            value.saturating_add(mag)
+        };
+        *value = max.map_or(next, |m| next.min(m));
+    }
+}
+
+fn fold_max_clean_vents() -> i32 {
+    (arith::LSBS - 1) as i32
+}
+
+fn cap_positive_fold(values: &mut [i32], cap: i32) {
+    let cap = cap.clamp(0, fold_max_clean_vents());
+    for value in values {
+        if *value > cap {
+            *value = cap;
+        }
+    }
+}
+
+fn apply_fold_delta_range(values: &mut [i32], start: usize, end: usize, delta: i32) {
+    for value in &mut values[start..end] {
+        if *value >= 0 {
+            *value = (*value + delta).clamp(0, fold_max_clean_vents());
+        }
+    }
+}
+
+fn apply_fold_sched_delta(values: &mut [i32], spec: &str) {
+    for token in spec.split(',') {
+        let Some((region, delta)) = token.split_once(':') else {
+            continue;
+        };
+        let Ok(delta) = delta.parse::<i32>() else {
+            continue;
+        };
+        let len = values.len();
+        let (start, end) = match region.trim() {
+            "all" => (0, len),
+            "first" | "prefix" => (0, len / 3),
+            "mid" | "middle" => (len / 3, (2 * len) / 3),
+            "last" | "suffix" => ((2 * len) / 3, len),
+            _ => continue,
+        };
+        apply_fold_delta_range(values, start, end, delta);
+    }
+}
+
+fn apply_route_overlays(s: &mut Sched) {
+    if let Some(delta) = env_i32("TRAILMIX_APPLY_COUT_K_DELTA") {
+        apply_delta_usize(&mut s.cout_k.0, delta, None);
+    }
+    if let Some(delta) = env_i32("TRAILMIX_CMP_K_DELTA") {
+        apply_delta_usize(&mut s.cmp_k.0, delta, None);
+    }
+    if let Some(delta) = env_i32("TRAILMIX_FFG_G_DELTA") {
+        apply_delta_usize(&mut s.ffg.0, delta, Some(arith::LSBS - 1));
+    }
+    if let Some(delta) = env_i32("TRAILMIX_HYB_V_DELTA") {
+        apply_delta_usize(&mut s.hyb_v.0, delta, None);
+    }
+    if let Some(delta) = env_i32("TRAILMIX_SQ_ROW_K_DELTA") {
+        apply_delta_usize(&mut s.sqrow_k.0, delta, None);
+    }
+    if let Some(cap) = env_i32("TRAILMIX_FOLD_LOW_BITS") {
+        cap_positive_fold(&mut s.fold.0, cap);
+    }
+    if let Ok(spec) = std::env::var("TRAILMIX_FOLD_SCHED_DELTA") {
+        apply_fold_sched_delta(&mut s.fold.0, &spec);
+    }
+}
+
 fn next_gcd_k() -> usize { SCHED.with(|s| step(&mut s.borrow_mut().gcd_k, usize::MAX)) }
 fn next_cout_k() -> usize { SCHED.with(|s| step(&mut s.borrow_mut().cout_k, usize::MAX)) }
 fn next_fold() -> i32 { SCHED.with(|s| step(&mut s.borrow_mut().fold, i32::MAX)) }
@@ -141,6 +222,7 @@ fn load_schedule() {
         s.ffg.0 = schedule::FFG_G.to_vec();
         s.hyb_v.0 = schedule::HYB_V.to_vec();
         s.sqrow_k.0 = schedule::SQ_ROW_K.to_vec();
+        apply_route_overlays(&mut s);
     });
 }
 
```

