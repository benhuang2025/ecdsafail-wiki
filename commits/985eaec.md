# 985eaec — Narrow the last 20 GCD step widths by 2 bits, take the classical `3·ox` step, and regenerate the dead-CCX list

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-23 |
| Submission | `12e5529` |
| Commit | `985eaecccc37353331213725f2c277c707db5954` |
| Result | 1156 qubits × 1,365,020 Toffoli = **1,577,963,120** |
| Base | `6c0769f` (the author's K1 + dead-CCX commit): 1156 qubits × 1,366,238 Toffoli = 1,579,371,128 |
| Change vs base | qubits ±0, Toffoli −1,218, score −1,408,008 |
| Leaderboard Δ | −1,086,640, measured against the frontier at the time, `27d4627` (the author's classical-`3·ox` commit, 1156 × 1,365,960 = 1,579,049,760), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the generated index list is copied from the commit; the patch covers the rest |

## Summary

The trailmix GCD runs 258 fixed steps on two registers `u` and `v`. Their
active width at step `i` is the baked `SCHED_J2[i]`. Bits above that width are
assumed to be zero and are dropped. By the last steps, almost every input has
shrunk to a few dozen bits.

This commit lowers `SCHED_J2` by 2 bits for each of the last 20 steps
(238–257). Every subtract, controlled swap, compare and shift of those steps
then runs on 2 fewer bits, in each of the four GCD passes.

It also switches the `x2 += 3·ox` step to the classical form, the same edit
as [`27d4627`](27d4627.md). It regenerates the positional dead-CCX list for
the new stream: 13,766 entries, against 14,361 in the base.

The net is −1,218 average Toffoli at 1156 qubits. The narrower widths are
probabilistic: an input that still needs those bits is now computed wrong,
and the nonce hunt avoids such inputs.

## What changed and why it saves Toffoli

1. **`src/point_add/trailmix_ludicrous/schedule.rs`, `SCHED_J2`.** The table
   is reflowed to 12 entries per line. Only indices 238–257 change, each by −2:

   | step `i` | 238 | 239 | 240 | 241 | 242 | 243 | 244 | 245 | 246 | 247 |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | old → new | 28→26 | 27→25 | 26→24 | 25→23 | 24→22 | 23→21 | 23→21 | 22→20 | 22→20 | 21→19 |

   | step `i` | 248 | 249 | 250 | 251 | 252 | 253 | 254 | 255 | 256 | 257 |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | old → new | 20→18 | 19→17 | 19→17 | 18→16 | 18→16 | 18→16 | 16→14 | 16→14 | 14→12 | 13→11 |

   - In `forward_gcd_jump` and `reverse_gcd_jump`, `current_n = SCHED_J2[i]`
     sets how many bits of `u` and `v` are kept live (the rest are freed or
     regrown).
   - It also sets the width of the step's work: the shifts, the
     `cswap(swp, u[j], v[j])` for `j < current_n`, the controlled subtract
     `controlled_add_active` and the swap-decision compare. The compare uses
     `min(GAP_J2[i], current_n)` bits.
   - The schedule's own comment states the risk: "a step whose
     `max(bitlen(u), bitlen(v)) > SCHED_J2[i]` truncates a needed bit". See
     [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) and
     [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
   - Saving: 2 bits × 20 steps of these per-bit gates, in both directions of
     both GCD calls.
2. **`src/point_add/trailmix_ludicrous/ec_add.rs`, `ec_add`**:
   `coord_add3x_orig` → `coord_add3x`.
   - `3·ox mod q` is computed with free classical-bit ops, and one exact
     `mod_add_exact` replaces two quantum modular adds and a doubling and
     halving.
   - `advance_ffg_call_index(3)` keeps the per-call `+f` reserve indices
     aligned. [`27d4627`](27d4627.md) explains this step.
3. **New data file `src/point_add/dead_coord3x_sched_notc.idx`** (generated).
   It has an `idx` header, then 13,766 never-firing CCX positions, from 11,317
   to 10,153,503, on the new post-fanout stream.
   - `src/point_add/mod.rs` points the drop block's `include_str!` at it. The
     base's `dead_k1_nocoord3x.idx` stays in the tree, unused.
   - The list is shorter than the base's. Some formerly dead gates sat in the
     bits that were cut, and the stream also changed.
   - See [dead-gate-strip](../concepts/dead-gate-strip.md).
4. **Nonce:** `DIALOG_TAIL_NONCE` 9500055003049 → 200060214302.

## Why it is still correct, and what it risks

- **The width cut is probabilistic.** An input whose GCD state still has more
  than `SCHED_J2[i]` significant bits at step `i` loses its top bits there.
  That gives a wrong inverse, a classical failure, or leaves residue that shows
  up as a phase or ancilla failure.
- Lambda therefore goes up. The author's note argues that these tail steps
  have converged "to a few dozen bits" on almost every input.
- **The `3·ox` change is exact.** It also removes two truncated compares.
- **The dead-CCX list is empirical and positional**, as in
  [`4a90d04`](4a90d04.md).
- The shipped nonce `200060214302` draws a clean set: 9,024 of 9,024 shots,
  with 0 classical, 0 phase and 0 ancilla failures (average 1,365,020.256). See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this as dead-gate removal because of the new index list. But
the list only follows the circuit change, and it is shorter than the base's.
The new lever is the width schedule: fewer bits for the converged tail steps.
The diff suggests Dead-Code and Redundancy Elimination → comparator/width
truncation as the better change-type. The `3·ox` switch is a classical
specialization that was already shipped in `27d4627`.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6c0769f -- src/point_add`.
   - The git parent `b0bff4e` is not an accepted submission. It is an organizer
     merge, "Compress ops.bin with zstd", on top of `27d4627`, so its
     `src/point_add` equals `27d4627`.
   - This commit was built on `6c0769f` instead. Against the parent, the diff
     (42,667 lines) would show `27d4627`'s `dead_k1_coord3x.idx` deleted and
     `6c0769f`'s `dead_k1_nocoord3x.idx` re-added.
   - Against `6c0769f`, `git diff --ignore-cr-at-eol 6c0769f 985eaec -- src/point_add`
     is 13,808 lines in 4 files. 13,767 of them are the new index file.
2. **Copy the generated index list from the commit:**
   `git checkout 985eaec -- src/point_add/dead_coord3x_sched_notc.idx`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It covers
   `mod.rs`, `ec_add.rs` and `schedule.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol 985eaec -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*`, `LUD_*`, `CONSTPROP_*`, `SINGLE_CCX_FANOUT_*` or
   `DROP_DEAD_*` environment variables set. Expect:
   - 1156 qubits
   - 1,365,020 average Toffoli (1,365,020.256 before rounding)
   - score 1,577,963,120
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `200060214302` and an identical op
stream. Any other change needs a new nonce hunt and a regenerated list.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 048d1b0..76959ac 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2027,7 +2027,7 @@ pub fn build() -> Vec<Op> {
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
-    set_default_env("DIALOG_TAIL_NONCE", "9500055003049"); // confirmed island, 0/0/0, score 1,579,371,128
+    set_default_env("DIALOG_TAIL_NONCE", "200060214302"); // confirmed island 0/0/0, score 1,577,963,120 (peak 1156 x avgT 1,365,020)
     // Stack the latest frontier square fold: use shifted-low folding for all
     // square lanes instead of the older `a`-only direct32 ramp shortcut.
     set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "");
@@ -2131,7 +2131,7 @@ pub fn build() -> Vec<Op> {
         let drop_txt: String = match std::env::var("DROP_DEAD_IDX_FILE") {
             Ok(idx_path) => std::fs::read_to_string(&idx_path)
                 .unwrap_or_else(|e| panic!("DROP_DEAD_IDX_FILE {idx_path}: {e}")),
-            Err(_) => include_str!("dead_k1_nocoord3x.idx").to_string(),
+            Err(_) => include_str!("dead_coord3x_sched_notc.idx").to_string(),
         };
         let mut drop: std::collections::HashSet<usize> = std::collections::HashSet::new();
         for line in drop_txt.lines() {
diff --git a/src/point_add/trailmix_ludicrous/ec_add.rs b/src/point_add/trailmix_ludicrous/ec_add.rs
index 57fc325..5fe9299 100644
--- a/src/point_add/trailmix_ludicrous/ec_add.rs
+++ b/src/point_add/trailmix_ludicrous/ec_add.rs
@@ -373,7 +373,7 @@ pub fn ec_add(
 
     // Step 7: x2 += 3*ox.  => (P.x + 2*Q.x, lambda)  [x2 currently = dx = P.x-Q.x].
     circ.set_phase("tlm_coord_add3x");
-    coord_add3x_orig(circ, x2, ox);
+    coord_add3x(circ, x2, ox);
 
     // Step 10: x2 -= lambda^2 mod q.  (lambda = y2[..N]).
     circ.set_phase("tlm_square");
diff --git a/src/point_add/trailmix_ludicrous/schedule.rs b/src/point_add/trailmix_ludicrous/schedule.rs
index 8051410..0950f31 100644
--- a/src/point_add/trailmix_ludicrous/schedule.rs
+++ b/src/point_add/trailmix_ludicrous/schedule.rs
@@ -26,19 +26,28 @@ pub const PAD: usize = 20;
 /// `SCHED_J2[i]` bits of the GCD state; a step whose
 /// `max(bitlen(u), bitlen(v)) > SCHED_J2[i]` truncates a needed bit.
 pub static SCHED_J2: &[u16] = &[
-    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 255, 254, 253, 252, 251, 250, 249, 248,
-    247, 246, 245, 244, 243, 242, 241, 240, 239, 238, 237, 236, 235, 234, 233, 232, 231, 230, 229,
-    228, 227, 226, 225, 224, 223, 222, 221, 220, 219, 218, 217, 216, 215, 214, 213, 212, 211, 210,
-    209, 208, 207, 206, 205, 204, 203, 202, 201, 200, 199, 198, 197, 196, 195, 194, 193, 192, 191,
-    190, 189, 188, 187, 186, 185, 184, 183, 182, 181, 180, 179, 178, 177, 176, 175, 174, 173, 173,
-    172, 170, 169, 168, 167, 166, 166, 164, 164, 163, 162, 160, 160, 159, 157, 157, 156, 155, 154,
-    153, 152, 151, 149, 148, 147, 146, 145, 145, 144, 143, 141, 141, 140, 139, 138, 137, 136, 135,
-    134, 133, 131, 130, 129, 128, 127, 126, 126, 125, 124, 122, 122, 120, 119, 118, 117, 116, 115,
-    114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95,
-    94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75, 74, 73, 72, 71,
-    70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47,
-    46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28, 27, 26, 25, 24, 23,
-    23, 22, 22, 21, 20, 19, 19, 18, 18, 18, 16, 16, 14, 13,
+    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 255,
+    254, 253, 252, 251, 250, 249, 248, 247, 246, 245, 244, 243,
+    242, 241, 240, 239, 238, 237, 236, 235, 234, 233, 232, 231,
+    230, 229, 228, 227, 226, 225, 224, 223, 222, 221, 220, 219,
+    218, 217, 216, 215, 214, 213, 212, 211, 210, 209, 208, 207,
+    206, 205, 204, 203, 202, 201, 200, 199, 198, 197, 196, 195,
+    194, 193, 192, 191, 190, 189, 188, 187, 186, 185, 184, 183,
+    182, 181, 180, 179, 178, 177, 176, 175, 174, 173, 173, 172,
+    170, 169, 168, 167, 166, 166, 164, 164, 163, 162, 160, 160,
+    159, 157, 157, 156, 155, 154, 153, 152, 151, 149, 148, 147,
+    146, 145, 145, 144, 143, 141, 141, 140, 139, 138, 137, 136,
+    135, 134, 133, 131, 130, 129, 128, 127, 126, 126, 125, 124,
+    122, 122, 120, 119, 118, 117, 116, 115, 114, 113, 112, 111,
+    110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 99,
+    98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87,
+    86, 85, 84, 83, 82, 81, 80, 79, 78, 77, 76, 75,
+    74, 73, 72, 71, 70, 69, 68, 67, 66, 65, 64, 63,
+    62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51,
+    50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39,
+    38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 26, 25,
+    24, 23, 22, 21, 21, 20, 20, 19, 18, 17, 17, 16,
+    16, 16, 14, 14, 12, 11,
 ];
 
 /// Per-step swap-decision comparator window for jump=2: at GCD step `i` the
```

