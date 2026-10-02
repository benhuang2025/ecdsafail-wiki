# da398df — Stream the high bits of the early GCD walk bodies through a controlled low-qubit Cuccaro instead of materializing them, and move the last apply cut to 196 (1297 → 1285 qubits)

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-08 |
| Submission | `6add50f` |
| Commit | `da398df8cff976125a0c30513eaf10079db9e84c` |
| Result | 1285 qubits × 1,390,532 Toffoli = **1,786,833,620** |
| Base | `98dd2ad` (the author's previous submission, git parent and frontier at the time): 1297 qubits × 1,386,820 Toffoli = 1,798,705,540 |
| Change vs base | qubits −12, Toffoli +3,712, score −11,871,920 (leaderboard Δ −11,871,920) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Each dialog-GCD walk step does a controlled subtract (forward walk) or add
(reverse walk) `acc ∓= ctrl·src` over the body width. The fast form used
here first *materializes* the controlled source, `gated[j] = ctrl ∧ src[j]`,
into scratch wires. It then runs a Cuccaro ripple with one measured carry
wire per bit. That needs `2·body_len − 1` scratch wires, and in the early
steps, where the body is about 250 bits wide, this scratch sets the peak.

This commit splits the body. The low `body_len − s` bits are still
materialized and rippled as before. The top `s` bits are added straight from
`src` by a *controlled* in-place Cuccaro (`cuccaro_add_ctrl_lowq`), which
needs no per-bit scratch, only one shared scratch wire. Streaming `s` bits
saves `2s − 2` wires. A per-step map picks the smallest `s` that brings each
step to 1285 qubits: 1 to 7 bits at steps 3–21.

The last apply-chunk cut also moves from 190 to 196, which brings the apply
phase down to the same 1285 floor. Peak: 1297 → 1285.

The cost is about 6 extra Toffoli per streamed bit, plus about 3 Toffoli per
apply call for the wider boundary replay, +3,712 in total. One qubit is
worth about 1,080 Toffoli here, so the score falls by 11.9 M.

## What changed and why it saves qubits

1. **New map `DIALOG_GCD_SELECTED_BODY_STREAM_SUFFIX_MAP`**, pinned in
   `configure_ecdsafail_submission_route()` (`src/point_add/mod.rs`) to
   `3:2,4:3,5:5,6:6,7:7,8:5,9:7,10:5,11:7,12:6,13:7,14:5,15:6,16:3,17:5,18:1,19:3,21:1`.
   - It is read by the new `dialog_gcd_selected_body_stream_suffix_bits(step, body_len)`
     in `rounds/dialog/mod.rs`, clamped to `body_len − 1`. The new
     `dialog_gcd_selected_body_stream_top_enabled` is true when the value
     is 1.
   - The map streams 84 bits in total per walk.
2. **Body with `s ≥ 2`**, in `dialog_gcd_controlled_sub_selected` and
   `dialog_gcd_controlled_add_selected`, on the no-carry-in (`nocin`) path:
   - The borrowed scratch is split into `carries[..p]`, `gated[..p]` and one
     `scratch` wire, with `p = body_len − s`. The demand `nocin_need` becomes
     `2·(body_len − s) + 1` instead of `2·body_len − 1`.
   - It loads `gated[j] = ctrl ∧ src[body_start + j]` for the low `p` bits
     only.
   - It calls the new `cuccaro_sub_fast_prefix_ctrl_suffix_no_cin` (or its
     add twin) in `arith/adder.rs`:
     - the low `p` bits get the usual fast ripple, one CCX per carry;
     - when the ripple reaches the top of the prefix, `prefix[p−1]` holds
       the prefix carry. It is passed as the carry-in of
       `cuccaro_sub_ctrl_lowq` / `cuccaro_add_ctrl_lowq(suffix = src[top s], acc[top s], ctrl, c_in, scratch)`.
       That function builds its chain from `ctrl_maj` / `ctrl_uma`
       (2 CCX plus a 3-control X through `scratch` each), so it reads
       `src` in place and never materializes it;
     - the prefix carries are then erased by measurement with `cz_if`
       fixes, as before.
   - It clears `gated` by `hmr` with `cz_if(ctrl, src)`.
   - The carry from a gated prefix is 0 whenever `ctrl = 0`, so feeding it
     to a controlled suffix adder is valid. The doc comment says the same.
3. **Body with `s = 1`** (steps 18 and 21): a cheaper special case.
   - The top bit is handled by a single `ccx(ctrl, src[top], acc[top])`,
     applied before the subtract or after the add.
   - The low `body_len − 1` bits use the existing
     `cuccaro_*_fast_low_to_ext_borrowed_carries_no_cin`, whose carry or
     borrow ripples into `acc[top]`.
   - Demand: `2·(body_len − 1)`, one wire less than before.
4. **Matching scratch request** in `dialog_gcd_build_composite_scratch`
   (`rounds/dialog/compressed.rs`). `want` uses the same three formulas, so
   the composite pool, and so the step's peak, shrinks by `2s − 2` (or 1
   wire when `s = 1`). See
   [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
5. **`DIALOG_GCD_APPLY_CHUNKED_F_CUT4`: 190 → 196.**
   - The final apply chunk `[196, 257)` loads 6 fewer addend bits into
     fresh wires, which lowers the apply binders to 1285.
   - The cost is 6 more bits in the conditioned boundary replay of
     [bfd3fa6](bfd3fa6.md), about 6 × 0.5 × 516 ≈ +1,550 Toffoli.
     [8983da8](8983da8.md) had found this cut too expensive while only
     one qubit was at stake.
6. **`DIALOG_TAIL_NONCE`: 9100005549463 → 9300021269076.**

**Toffoli.** A streamed bit costs the controlled MAJ plus UMA, about 8 CCX,
where the materialized bit cost about 2 (a load and a carry). Over 84 bits
and 4 walks (forward and reverse walk of both divisions), the remaining
+2,160 after the cut works out to about 6.4 extra Toffoli per streamed bit.
See [adders-and-carries](../concepts/adders-and-carries.md).

## Why it is still correct, and what it risks

The change is exact. The prefix-plus-streamed-suffix adder computes the
same `acc ∓ ctrl·src` over the body width as the fully materialized one,
and it returns every scratch wire to |0>. Moving the chunk cut is exact for
any cut. Body widths and truncations are unchanged, so no new hard inputs
appear. The nonce was re-hunted only because the op stream changed.

If the streamed suffix were wrong, the walk would leave `u` and `v`
corrupted. The run would then show classical mismatches and ancilla
garbage. The emitted op count is 9,831,654. The shipped nonce
`9300021269076` draws a test set with 0 classical, 0 phase and 0 ancilla
failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The qubits are saved by not giving the top body bits their own gated-copy
and carry wires, which shortens what is live at the walk peak. That matches
ancilla-lifetime / venting. The mechanism is an adder swap for those bits,
from the materialized fast Cuccaro to the controlled in-place Cuccaro,
which spends Toffoli to save wires. So Strength Reduction → fast-adder
reroute, as [639f12c](639f12c.md) was filed, is the close runner-up.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 98dd2ad -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 98dd2ad da398df -- src/point_add` is
   254 lines in 4 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol da398df -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*` or `MOD_*` environment variables set. Expect:
   - 1285 qubits
   - 1,390,532 average Toffoli (1,390,531.999 before rounding)
   - score 1,786,833,620
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9300021269076` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/adder.rs b/src/point_add/arith/adder.rs
index 27fbdb0..aa4115e 100644
--- a/src/point_add/arith/adder.rs
+++ b/src/point_add/arith/adder.rs
@@ -651,6 +651,91 @@ pub(crate) fn cuccaro_sub_fast_low_to_ext_borrowed_carries_no_cin(
     b.cx(a[0], acc_ext[0]);
 }
 
+/// Add a materialized low prefix and an unmaterialized controlled high suffix.
+/// The prefix's final carry is a valid controlled carry-in for the suffix.
+pub(crate) fn cuccaro_add_fast_prefix_ctrl_suffix_no_cin(
+    b: &mut B,
+    prefix: &[QubitId],
+    suffix: &[QubitId],
+    acc: &[QubitId],
+    ctrl: QubitId,
+    carries: &[QubitId],
+    scratch: QubitId,
+) {
+    let n = prefix.len();
+    assert!(n > 0);
+    assert!(!suffix.is_empty());
+    assert_eq!(acc.len(), n + suffix.len());
+    assert!(carries.len() >= n);
+
+    b.cx(prefix[0], acc[0]);
+    b.ccx(prefix[0], acc[0], carries[0]);
+    b.cx(carries[0], prefix[0]);
+    for i in 1..n {
+        b.cx(prefix[i], acc[i]);
+        b.cx(prefix[i], prefix[i - 1]);
+        b.ccx(prefix[i - 1], acc[i], carries[i]);
+        b.cx(carries[i], prefix[i]);
+    }
+
+    cuccaro_add_ctrl_lowq(b, suffix, &acc[n..], ctrl, prefix[n - 1], scratch);
+
+    for i in (1..n).rev() {
+        b.cx(carries[i], prefix[i]);
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        b.cz_if(prefix[i - 1], acc[i], m);
+        b.cx(prefix[i], prefix[i - 1]);
+        b.cx(prefix[i - 1], acc[i]);
+    }
+    b.cx(carries[0], prefix[0]);
+    let m0 = b.alloc_bit();
+    b.hmr(carries[0], m0);
+    b.cz_if(prefix[0], acc[0], m0);
+}
+
+/// Inverse of [`cuccaro_add_fast_prefix_ctrl_suffix_no_cin`].
+pub(crate) fn cuccaro_sub_fast_prefix_ctrl_suffix_no_cin(
+    b: &mut B,
+    prefix: &[QubitId],
+    suffix: &[QubitId],
+    acc: &[QubitId],
+    ctrl: QubitId,
+    carries: &[QubitId],
+    scratch: QubitId,
+) {
+    let n = prefix.len();
+    assert!(n > 0);
+    assert!(!suffix.is_empty());
+    assert_eq!(acc.len(), n + suffix.len());
+    assert!(carries.len() >= n);
+
+    b.ccx(prefix[0], acc[0], carries[0]);
+    b.cx(carries[0], prefix[0]);
+    for i in 1..n {
+        b.cx(prefix[i - 1], acc[i]);
+        b.cx(prefix[i], prefix[i - 1]);
+        b.ccx(prefix[i - 1], acc[i], carries[i]);
+        b.cx(carries[i], prefix[i]);
+    }
+
+    cuccaro_sub_ctrl_lowq(b, suffix, &acc[n..], ctrl, prefix[n - 1], scratch);
+
+    for i in (1..n).rev() {
+        b.cx(carries[i], prefix[i]);
+        let m = b.alloc_bit();
+        b.hmr(carries[i], m);
+        b.cz_if(prefix[i - 1], acc[i], m);
+        b.cx(prefix[i], prefix[i - 1]);
+        b.cx(prefix[i], acc[i]);
+    }
+    b.cx(carries[0], prefix[0]);
+    let m0 = b.alloc_bit();
+    b.hmr(carries[0], m0);
+    b.cz_if(prefix[0], acc[0], m0);
+    b.cx(prefix[0], acc[0]);
+}
+
 
 pub(crate) fn cuccaro_add_fast_windowed_low_to_ext(
     b: &mut B,
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 086c8d5..aa7034f 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1098,6 +1098,7 @@ fn configure_ecdsafail_submission_route() {
     // by 172,444).
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "20");
     set_default_env("DIALOG_GCD_APPLY_BOUNDARY_CONDITIONAL_REPLAY", "1");  // BAKED: condrep ON for env-less grader build
+    set_default_env("DIALOG_GCD_SELECTED_BODY_STREAM_SUFFIX_MAP", "3:2,4:3,5:5,6:6,7:7,8:5,9:7,10:5,11:7,12:6,13:7,14:5,15:6,16:3,17:5,18:1,19:3,21:1");  // BAKED: codex 1285q peak-drop (stream selected high bits through low-qubit suffix)
     // Bake the exact conditional-replay stack for env-less GPU hunts and grader builds.
     set_default_env("DIALOG_GCD_REVERSE_BRANCH_CONDITIONAL_REPLAY", "1");
     set_default_env("DIALOG_GCD_SPECIAL_CLEAN_CONDITIONAL_REPLAY", "1");
@@ -1314,7 +1315,7 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "50");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "100");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT3", "150");
-    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT4", "190");
+    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT4", "196");  // BAKED: codex 1285q (was 190)
     // WIDTH_SLOPE tightening: the per-step GCD width envelope shrink rate
     // (ideal = N - step*SLOPE + MARGIN) was left at the default 0.7075 by the
     // whole frontier lineage; only the constant MARGIN was ever tuned. The
@@ -1403,7 +1404,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "9100005549463");
+    set_default_env("DIALOG_TAIL_NONCE", "9300021269076");
     set_default_env("DIALOG_GCD_FOLD_MAJ2", "1");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
diff --git a/src/point_add/rounds/dialog/compressed.rs b/src/point_add/rounds/dialog/compressed.rs
index 0029d67..e227ef6 100644
--- a/src/point_add/rounds/dialog/compressed.rs
+++ b/src/point_add/rounds/dialog/compressed.rs
@@ -385,7 +385,13 @@ pub(crate) fn dialog_gcd_build_composite_scratch(
         && !dialog_gcd_selected_body_nocin_keep_pool()
         && body_start >= 1
         && body_len >= 1;
-    let want = if nocin {
+    let stream_suffix = dialog_gcd_selected_body_stream_suffix_bits(step, body_len);
+    let want = if nocin && stream_suffix >= 2 {
+        2 * (body_len - stream_suffix) + 1
+    } else if nocin && dialog_gcd_selected_body_stream_top_enabled(step, body_len) && body_len >= 2
+    {
+        2 * (body_len - 1)
+    } else if nocin {
         // Match the body's exact host demand; never exceed the legacy ask.
         (2 * body_len - 1).min(2 * active_width - 1)
     } else {
diff --git a/src/point_add/rounds/dialog/mod.rs b/src/point_add/rounds/dialog/mod.rs
index a47268d..6633edf 100644
--- a/src/point_add/rounds/dialog/mod.rs
+++ b/src/point_add/rounds/dialog/mod.rs
@@ -417,6 +417,28 @@ pub(crate) fn dialog_gcd_selected_body_nocin_keep_pool() -> bool {
     std::env::var("DIALOG_GCD_SELECTED_BODY_NOCIN").ok().as_deref() == Some("2")
 }
 
+/// Per-step count of high source bits streamed through the controlled low-q
+/// suffix instead of being materialized. A value of one uses the cheaper
+/// top-bit specialization. Default off when the map is absent.
+pub(crate) fn dialog_gcd_selected_body_stream_suffix_bits(step: usize, body_len: usize) -> usize {
+    let Ok(map) = std::env::var("DIALOG_GCD_SELECTED_BODY_STREAM_SUFFIX_MAP") else {
+        return 0;
+    };
+    map.split(',')
+        .find_map(|entry| {
+            let (entry_step, entry_bits) = entry.trim().split_once(':')?;
+            let entry_step = entry_step.parse::<usize>().ok()?;
+            let entry_bits = entry_bits.parse::<usize>().ok()?;
+            (entry_step == step).then_some(entry_bits)
+        })
+        .unwrap_or(0)
+        .min(body_len.saturating_sub(1))
+}
+
+pub(crate) fn dialog_gcd_selected_body_stream_top_enabled(step: usize, body_len: usize) -> bool {
+    dialog_gcd_selected_body_stream_suffix_bits(step, body_len) == 1
+}
+
 pub(crate) fn dialog_gcd_late_borrow_uv_high_enabled() -> bool {
     std::env::var("DIALOG_GCD_LATE_BORROW_UV_HIGH")
         .ok()
@@ -463,7 +485,17 @@ pub(crate) fn dialog_gcd_controlled_sub_selected(
         let odd_lowbit_fast = dialog_gcd_odd_u_lowbit_fastpath_enabled();
         let body_start = if odd_lowbit_fast { 1 } else { 0 };
         let body_len = body_w.saturating_sub(body_start);
-        let nocin_need = if dialog_gcd_selected_body_nocin_keep_pool() {
+        let stream_suffix = dialog_gcd_selected_body_stream_suffix_bits(step, body_len);
+        let nocin_need = if stream_suffix >= 2
+            && !dialog_gcd_selected_body_nocin_keep_pool()
+        {
+            2 * (body_len - stream_suffix) + 1
+        } else if dialog_gcd_selected_body_stream_top_enabled(step, body_len)
+            && !dialog_gcd_selected_body_nocin_keep_pool()
+            && body_len >= 2
+        {
+            2 * (body_len - 1)
+        } else if dialog_gcd_selected_body_nocin_keep_pool() {
             // Legacy gated offset c[n..n+body_len] needs the full 2n-1 pool.
             (n + body_len).max(2 * body_len - 1)
         } else {
@@ -474,6 +506,61 @@ pub(crate) fn dialog_gcd_controlled_sub_selected(
             && body_len >= 1
             && borrowed_carries.map_or(false, |c| c.len() >= nocin_need);
         if nocin {
+            if stream_suffix >= 2 {
+                let prefix_len = body_len - stream_suffix;
+                let c = borrowed_carries.expect("nocin requires borrowed carries");
+                let (carries, rest) = c.split_at(prefix_len);
+                let (gated, rest) = rest.split_at(prefix_len);
+                let scratch = rest[0];
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_sub_load");
+                for j in 0..prefix_len {
+                    b.ccx(ctrl, subtrahend[body_start + j], gated[j]);
+                }
+                b.cx(ctrl, acc[0]);
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_sub_body");
+                cuccaro_sub_fast_prefix_ctrl_suffix_no_cin(
+                    b,
+                    gated,
+                    &subtrahend[body_start + prefix_len..body_w],
+                    &acc[body_start..body_w],
+                    ctrl,
+                    carries,
+                    scratch,
+                );
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_sub_clear");
+                for j in 0..prefix_len {
+                    let m = b.alloc_bit();
+                    b.hmr(gated[j], m);
+                    b.cz_if(ctrl, subtrahend[body_start + j], m);
+                }
+                return;
+            }
+            if dialog_gcd_selected_body_stream_top_enabled(step, body_len) && body_len >= 2 {
+                let lower_len = body_len - 1;
+                let c = borrowed_carries.expect("nocin requires borrowed carries");
+                let (carries, gated) = c.split_at(lower_len);
+                let gated = &gated[..lower_len];
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_sub_load");
+                for j in 0..lower_len {
+                    b.ccx(ctrl, subtrahend[body_start + j], gated[j]);
+                }
+                b.cx(ctrl, acc[0]);
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_sub_body");
+                b.ccx(ctrl, subtrahend[body_w - 1], acc[body_w - 1]);
+                cuccaro_sub_fast_low_to_ext_borrowed_carries_no_cin(
+                    b,
+                    gated,
+                    &acc[body_start..body_w],
+                    carries,
+                );
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_sub_clear");
+                for j in 0..lower_len {
+                    let m = b.alloc_bit();
+                    b.hmr(gated[j], m);
+                    b.cz_if(ctrl, subtrahend[body_start + j], m);
+                }
+                return;
+            }
             // No-physical-c_in body: host demand 2*body_len-1 (== 2*body_w-3).
             // carries = borrowed[..body_len-1], gated = borrowed[body_len-1..2*body_len-1].
             // Diagnostic keep-pool (mode 2) instead uses the BODY_HOST_CIN offsets
@@ -600,7 +687,17 @@ pub(crate) fn dialog_gcd_controlled_add_selected(
         let odd_lowbit_fast = dialog_gcd_odd_u_lowbit_fastpath_enabled();
         let body_start = if odd_lowbit_fast { 1 } else { 0 };
         let body_len = body_w.saturating_sub(body_start);
-        let nocin_need = if dialog_gcd_selected_body_nocin_keep_pool() {
+        let stream_suffix = dialog_gcd_selected_body_stream_suffix_bits(step, body_len);
+        let nocin_need = if stream_suffix >= 2
+            && !dialog_gcd_selected_body_nocin_keep_pool()
+        {
+            2 * (body_len - stream_suffix) + 1
+        } else if dialog_gcd_selected_body_stream_top_enabled(step, body_len)
+            && !dialog_gcd_selected_body_nocin_keep_pool()
+            && body_len >= 2
+        {
+            2 * (body_len - 1)
+        } else if dialog_gcd_selected_body_nocin_keep_pool() {
             // Legacy gated offset c[n..n+body_len] needs the full 2n-1 pool.
             (n + body_len).max(2 * body_len - 1)
         } else {
@@ -611,6 +708,61 @@ pub(crate) fn dialog_gcd_controlled_add_selected(
             && body_len >= 1
             && borrowed_carries.map_or(false, |c| c.len() >= nocin_need);
         if nocin {
+            if stream_suffix >= 2 {
+                let prefix_len = body_len - stream_suffix;
+                let c = borrowed_carries.expect("nocin requires borrowed carries");
+                let (carries, rest) = c.split_at(prefix_len);
+                let (gated, rest) = rest.split_at(prefix_len);
+                let scratch = rest[0];
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_add_load");
+                for j in 0..prefix_len {
+                    b.ccx(ctrl, addend[body_start + j], gated[j]);
+                }
+                b.cx(ctrl, acc[0]);
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_add_body");
+                cuccaro_add_fast_prefix_ctrl_suffix_no_cin(
+                    b,
+                    gated,
+                    &addend[body_start + prefix_len..body_w],
+                    &acc[body_start..body_w],
+                    ctrl,
+                    carries,
+                    scratch,
+                );
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_add_clear");
+                for j in 0..prefix_len {
+                    let m = b.alloc_bit();
+                    b.hmr(gated[j], m);
+                    b.cz_if(ctrl, addend[body_start + j], m);
+                }
+                return;
+            }
+            if dialog_gcd_selected_body_stream_top_enabled(step, body_len) && body_len >= 2 {
+                let lower_len = body_len - 1;
+                let c = borrowed_carries.expect("nocin requires borrowed carries");
+                let (carries, gated) = c.split_at(lower_len);
+                let gated = &gated[..lower_len];
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_add_load");
+                for j in 0..lower_len {
+                    b.ccx(ctrl, addend[body_start + j], gated[j]);
+                }
+                b.cx(ctrl, acc[0]);
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_add_body");
+                cuccaro_add_fast_low_to_ext_borrowed_carries_no_cin(
+                    b,
+                    gated,
+                    &acc[body_start..body_w],
+                    carries,
+                );
+                b.ccx(ctrl, addend[body_w - 1], acc[body_w - 1]);
+                b.set_phase("dialog_gcd_raw_tobitvector_materialized_add_clear");
+                for j in 0..lower_len {
+                    let m = b.alloc_bit();
+                    b.hmr(gated[j], m);
+                    b.cz_if(ctrl, addend[body_start + j], m);
+                }
+                return;
+            }
             // No-physical-c_in inverse body: host demand 2*body_len-1 (==2*body_w-3).
             let c = borrowed_carries.expect("nocin requires borrowed carries");
             let (carries, gated): (&[QubitId], &[QubitId]) =
```

