# f6ce76d — Port the drop-final-carry `+f` and first-cswap skip onto bket7's 5f3a0e3 tree

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-20 |
| Submission | `1905e06` |
| Commit | `f6ce76d9d9ca98bf086e2b2b78a9d31d1d5a9749` |
| Result | 1159 qubits × 1,378,636 Toffoli = **1,597,839,124** |
| Base | `5f3a0e3` (bket7): 1159 qubits × 1,379,217 Toffoli = 1,598,512,503 |
| Change vs base | qubits ±0, Toffoli −581, score −673,379 |
| Leaderboard Δ | −229,482, measured against the frontier at the time, `5c34dd1` (the author's own previous commit, 1159 × 1,378,834 = 1,598,068,606), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This is the same edit as the author's [`5c34dd1`](5c34dd1.md), applied to a
different tree. `5c34dd1` was built on `f0c1c42`. Twenty minutes earlier, bket7's
`5f3a0e3` had become the frontier with its own improvements. This commit puts
the same two value-exact removals on top of `5f3a0e3`, so it gets both
savings:

1. The last chunk of the graduated `+f` suffix no longer computes, and then
   erases, the carry out of the top bit, which the window discards anyway.
2. The first forward-apply step skips its 256-wire controlled swap, because
   `x` and `y` are equal there.

Against `5f3a0e3` the saving is 581 average Toffoli, at the same 1159 qubits.
The tail nonce was re-hunted for the new op stream.

## What changed and why it saves Toffoli

The code lines are identical to `5c34dd1`. Only the comment in `build()` and
the nonce differ. [`5c34dd1`](5c34dd1.md) has the full walk-through.

1. **`src/point_add/trailmix_ludicrous/arith.rs`, switch
   `TLM_GRAD_FINAL_NO_COUT=1`.**
   - `add_f_window_hybrid` adds `ctrl·f` into `reg[..LSBS]`. It adds the bits
     above its clean prefix with `controlled_add_const_chunked_graduated_off`,
     a chain of chunks of width `k−3, k−4, …`. Each chunk's carry-out sits on a
     qubit that is later erased by `controlled_erase_carry_gated_const`: an
     `hmr`, then a chunk-wide const comparator that runs only on shots whose
     outcome bit is 1.
   - The last chunk's carry-out is the carry out of bit `LSBS−1`, which the
     window drops (mod `2^LSBS`).
   - New `const_chunk_add_clean_drop_cout` handles the last chunk. It builds
     only `s−1` internal carries and writes the top sum bit as
     `a[s−1] ^= ctrl·c[s−1] ⊕ carry_{s−2}`. The erase loop now runs over
     `carries.len()`, so no erase is emitted for the last chunk.
   - Saving per hybrid `+f` call: one CCX, plus the last chunk's conditional
     comparator on about half the shots.
2. **`src/point_add/trailmix_ludicrous/gcd.rs`, `apply_step_forward`, switch
   `TLM_APPLY_FWD_FIRST_CSWAP_SKIP=1`.**
   - In `Direction::Forward` the apply pair starts as `x_reg = z`, `y_reg = 0`.
     The first step executed is `i = ITERS−1`. After `y += sub·x`, either
     `sub = 0` (and then `swp = sub AND (v<u)` is 0), or `y = z = x`.
   - Either way the `cswap(swp, x, y)` loop is the identity, so it is skipped
     when `i + 1 == ITERS`.
   - One `cswap` is `cx; ccx; cx`, and the forward multiply runs once, so this
     saves 256 Toffoli.
3. **`src/point_add/mod.rs`, `build()`**: `set_default_env` turns both switches
   on. `DIALOG_TAIL_NONCE` goes from 550000025725 to 200003194569.

The measured saving here (−581) is 19 more than on `f0c1c42` (−562). The
average depends on the draw, and `5f3a0e3` also has a slightly different
schedule (`GAP_J2`), so the hybrid `+f` calls land differently.

## Why it is still correct, and what it risks

- **Exact.** The dropped carry was discarded by the window anyway. The skipped
  swap acts on two equal registers, or it has a zero control. No approximation
  is added, so Lambda is the base's.
- The new nonce `200003194569` draws a clean set: 9,024 of 9,024 shots, with
  0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census calls this fold/carry truncation. The `+f` change does stop
computing a fold carry that the window truncates away, so the label fits the
arith.rs half. The cswap skip is a dead-gate removal. Note that the identical
edit in [`5c34dd1`](5c34dd1.md) was filed differently, as measurement
uncompute. Dead-gate/self-inverse removal would be the more consistent label
for both.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 5f3a0e3 -- src/point_add`.
   - Do not start from the git parent `5c34dd1`. That is the same edit on the
     older `f0c1c42` tree. Diffing against it (363 lines) would show
     everything that differs between the two trees, mainly the wide `GAP_J2`
     band one bit narrower in `schedule.rs` and the loss of `662e267`'s
     classical `coord_add3x` in `ec_add.rs` (`5f3a0e3` was built on `d11bdbb`),
     instead of this commit's edit.
   - Against `5f3a0e3`, `git diff --ignore-cr-at-eol 5f3a0e3 f6ce76d -- src/point_add`
     is 80 lines in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol f6ce76d -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*`, `LUD_*` or `CONSTPROP_*` environment variables set,
   because they override the defaults in `build()`. Expect:
   - 1159 qubits
   - 1,378,636 average Toffoli (1,378,635.594 before rounding)
   - score 1,597,839,124
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `200003194569` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a104d02..eb6b6b0 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1976,11 +1976,16 @@ pub fn build() -> Vec<Op> {
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
-    set_default_env("DIALOG_TAIL_NONCE", "550000025725");
+    set_default_env("DIALOG_TAIL_NONCE", "200003194569");
     // Stack the latest frontier square fold: use shifted-low folding for all
     // square lanes instead of the older `a`-only direct32 ramp shortcut.
     set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "");
     set_default_env("TLM_SQUARE_F_SHIFTED_LOW", "1");
+    // Post-5f3a0e3 avg-Toffoli reductions (Codex): graduated final +f without
+    // materializing/erasing the dropped carry-out + skip the no-op first
+    // forward-apply cswap. Peak-neutral (1159), -580.9 avgT.
+    set_default_env("TLM_GRAD_FINAL_NO_COUT", "1");
+    set_default_env("TLM_APPLY_FWD_FIRST_CSWAP_SKIP", "1");
     set_default_env("CONSTPROP_MAX_ITERS", "16");
     set_default_env("TLM_TARGET_Q", "1159");
     set_default_env("TLM_FOLD_RELEASE_CONTROLS", "1");
diff --git a/src/point_add/trailmix_ludicrous/arith.rs b/src/point_add/trailmix_ludicrous/arith.rs
index 868769a..4886421 100644
--- a/src/point_add/trailmix_ludicrous/arith.rs
+++ b/src/point_add/trailmix_ludicrous/arith.rs
@@ -644,6 +644,64 @@ fn const_chunk_add_clean(circ: &mut B, ctrl: &QubitId, a: &[QubitId], c: &[u8],
     }
 }
 
+fn const_chunk_add_clean_drop_cout(circ: &mut B, ctrl: &QubitId, a: &[QubitId], c: &[u8], coff: usize, cin: &QubitId) {
+    let s = a.len();
+    if s == 0 {
+        return;
+    }
+    if s == 1 {
+        if cbit(c, coff) {
+            circ.cx(*ctrl, a[0]);
+        }
+        circ.cx(*cin, a[0]);
+        return;
+    }
+    let mut int: Vec<Option<QubitId>> = (0..s - 1).map(|_| Some(circ.alloc_qubit())).collect();
+    for i in 0..s - 1 {
+        let on = cbit(c, coff + i);
+        let cin_ref: QubitId = if i == 0 { *cin } else { *int[i - 1].as_ref().unwrap() };
+        let cout_ref: QubitId = *int[i].as_ref().unwrap();
+        circ.cx(cin_ref, a[i]);
+        if on {
+            circ.cx(*ctrl, cin_ref);
+        }
+        circ.ccx(a[i], cin_ref, cout_ref);
+        if on {
+            circ.cx(*ctrl, cin_ref);
+        }
+        circ.cx(cin_ref, cout_ref);
+    }
+    for i in 0..s - 1 {
+        if cbit(c, coff + i) {
+            circ.cx(*ctrl, a[i]);
+        }
+    }
+    if cbit(c, coff + s - 1) {
+        circ.cx(*ctrl, a[s - 1]);
+    }
+    circ.cx(*int[s - 2].as_ref().unwrap(), a[s - 1]);
+    for i in (0..s - 1).rev() {
+        let on = cbit(c, coff + i);
+        let int_i = int[i].take().unwrap();
+        let cin_ref: QubitId = if i == 0 { *cin } else { *int[i - 1].as_ref().unwrap() };
+        if on {
+            circ.cx(*ctrl, a[i]);
+        }
+        circ.cx(cin_ref, int_i);
+        if on {
+            circ.cx(*ctrl, cin_ref);
+        }
+        let b = circ.alloc_bit();
+        circ.hmr(int_i, b);
+        circ.zero_and_free(int_i);
+        circ.cz_if_bit(a[i], cin_ref, b);
+        if on {
+            circ.cx(*ctrl, cin_ref);
+            circ.cx(*ctrl, a[i]);
+        }
+    }
+}
+
 /// No-temp const carry comparator with a middle callback handing `(a_top, cy_top,
 /// const_top)`.
 fn compare_geq_const_cin_middle<F: FnOnce(&mut B, &QubitId, &QubitId, bool)>(circ: &mut B, a: &[QubitId], c: &[u8], coff: usize, cin: &QubitId, body: F) {
@@ -727,12 +785,17 @@ fn controlled_add_const_chunked_graduated_off(circ: &mut B, ctrl: &QubitId, a: &
     assert_eq!(lo, n, "graduated staircase (k={k}) covers {lo} < n={n}");
     let mut carries: Vec<QubitId> = Vec::with_capacity(bounds.len());
     for (j, &(clo, chi)) in bounds.iter().enumerate() {
+        if std::env::var("TLM_GRAD_FINAL_NO_COUT").ok().as_deref() == Some("1") && j + 1 == bounds.len() {
+            let cin_ref: QubitId = if j == 0 { *cin } else { carries[j - 1] };
+            const_chunk_add_clean_drop_cout(circ, ctrl, &a[clo..chi], c, coff + clo, &cin_ref);
+            break;
+        }
         let cout = circ.alloc_qubit();
         let cin_ref: QubitId = if j == 0 { *cin } else { carries[j - 1] };
         const_chunk_add_clean(circ, ctrl, &a[clo..chi], c, coff + clo, &cin_ref, &cout);
         carries.push(cout);
     }
-    for j in (0..bounds.len()).rev() {
+    for j in (0..carries.len()).rev() {
         let (clo, chi) = bounds[j];
         let carry = carries.pop().expect("carry present");
         let cin_ref: QubitId = if j == 0 { *cin } else { carries[j - 1] };
diff --git a/src/point_add/trailmix_ludicrous/gcd.rs b/src/point_add/trailmix_ludicrous/gcd.rs
index 76c602e..ea188ea 100644
--- a/src/point_add/trailmix_ludicrous/gcd.rs
+++ b/src/point_add/trailmix_ludicrous/gcd.rs
@@ -976,8 +976,12 @@ fn apply_step_forward(
     });
     // 2) if swap: swap(x, y).
     circ.set_phase("tlm_apply_forward_swap");
-    for j in 0..n {
-        circ.cswap(*swp, x_reg[j], y_reg[j]);
+    if !(std::env::var("TLM_APPLY_FWD_FIRST_CSWAP_SKIP").ok().as_deref() == Some("1")
+        && i + 1 == ITERS)
+    {
+        for j in 0..n {
+            circ.cswap(*swp, x_reg[j], y_reg[j]);
+        }
     }
     // 3) y := 2*(1+s2)*y mod q. i==0: two separate controlled doublings (shift1 is
     //    t1-gated). i>0: the fused double+cdouble -- one combined (e+2d)*f fold
```

