# f9fae31 — Re-apply the one-Toffoli STEP 1 fan-out of the swap-merge fix-up on top of W-TRUNC

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `77a20f9` |
| Commit | `f9fae31f5784a9c4b0881da4de587ad34405ecd9` |
| Result | 2310 qubits × 3,062,668 Toffoli = **7,074,763,080** |
| Base | [`36e8578`](36e8578.md) (git parent, the author's previous submission): 2310 qubits × 3,063,680 Toffoli = 7,077,100,800 |
| Change vs base | qubits ±0, Toffoli −1,012, score −2,337,720 (leaderboard Δ −2,337,720) |
| Family | Fusion → gate/op fusion |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

[`36e8578`](36e8578.md) (W-TRUNC) was built on an older tree that did not have
the STEP 1 fan-out of [`ce60f0e`](ce60f0e.md). This commit ports that
fan-out to the W-TRUNC tree; the code is the same.

In the `(u, v_w)` swap merge, the flags `a_f` and `m_i` both need a toggle by
`frame & (u0 ⊕ v0)`. Two CCX with the same controls become one CCX into a
temporary, two CX fan-outs, and a measurement erase of the temporary with a
conditioned CZ phase fix. That saves one Toffoli per merged iteration. The
W-TRUNC tree uses the global swap-merge cap of 254 for both pairs, which gives
253 fix-ups per Kaliski run. Over 4 runs that is 1,012 fix-ups, and the
measured saving is exactly 1,012 Toffoli. Qubits are unchanged.

## What changed and why it saves Toffoli

`src/point_add/kaliski_walk.rs`, behind `KAL_UV_STEP1_FANOUT` (default on):

- **`kaliski_iteration_bulk_prefix3`, STEP 1 fix-up** (when `uv_frame_in` is
  set). While `u[0]` temporarily holds `u0 ⊕ v0` (after `cx(v_w[0], u[0])`):
  - Old: `ccx(frame, u[0], a_f); ccx(frame, u[0], m_i)`.
  - New: `t = alloc; ccx(frame, u[0], t); cx(t, a_f); cx(t, m_i); hmr(t, tm); cz_if(frame, u[0], tm); free(t)`.
- **`kaliski_iteration_bulk_prefix3_backward`**: the same rewrite on the
  mirrored fix-up with `frame_out`.

The fix-up runs in iterations 1 to 253 of each forward and backward bulk run,
for both pairs (`kal_cswap_uv_merge_safe_iters()` = 254 in this tree):
4 × 253 = 1,012 CCX removed. In [`ce60f0e`](ce60f0e.md) the same edit saved
1,014, because there pair2's cap was 255. For why `hmr` plus `cz_if` erases
`t` exactly, see [measurement-uncompute](../concepts/measurement-uncompute.md).

## Why it is still correct, and what it risks

The rewrite is exact.
- `a_f` and `m_i` receive the same XOR as before.
- `t` is reset by the measurement.
- `cz_if(frame, u[0], tm)` uses exactly the two controls that produced `t`,
  so it cancels the measurement's phase on every branch.

The temporary is live only inside STEP 1, not at the STEP 4 peak. The new op
stream draws a new hashed test set (no tail nonce in this era). It is clean:
0 classical, 0 phase and 0 ancilla failures. The probabilistic parts of the
circuit (W-TRUNC, iteration counts, bulk and R_SMALL thresholds) are unchanged,
but they are evaluated on this new draw.

## Classification rationale

The published label is Fusion → gate/op fusion: two Toffolis with identical
controls are fused into one shared AND. The same edit in [`ce60f0e`](ce60f0e.md)
is filed as Uncompute Strategy → measurement uncompute. Both labels fit,
because the fusion only pays off when the shared AND is erased by measurement.
The two filings of identical code are inconsistent.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 36e8578 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 36e8578 f9fae31 -- src/point_add` is
   30 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol f9fae31 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`,
   `POINT_ADD_*` or `BY_*` environment variables set. Expect:
   - 2310 qubits
   - 3,062,668 average Toffoli (rounded)
   - score 7,074,763,080
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era: the test set is a hash of the op stream,
so the score only reproduces with an identical op stream.

### Patch

```diff
diff --git a/src/point_add/kaliski_walk.rs b/src/point_add/kaliski_walk.rs
index 03cede0..01bcd9b 100644
--- a/src/point_add/kaliski_walk.rs
+++ b/src/point_add/kaliski_walk.rs
@@ -64,8 +64,19 @@ pub(crate) fn kaliski_iteration_bulk_prefix3(
         // u/v are conditionally exchanged by frame_in. Correct STEP-1 flags
         // to canonical basis by toggling on frame_in & (u0 xor v0).
         b.cx(v_w[0], u[0]);
-        b.ccx(frame_in, u[0], a_f);
-        b.ccx(frame_in, u[0], m_i);
+        if env_flag_enabled("KAL_UV_STEP1_FANOUT", true) {
+            let t = b.alloc_qubit();
+            b.ccx(frame_in, u[0], t);
+            b.cx(t, a_f);
+            b.cx(t, m_i);
+            let tm = b.alloc_bit();
+            b.hmr(t, tm);
+            b.cz_if(frame_in, u[0], tm);
+            b.free(t);
+        } else {
+            b.ccx(frame_in, u[0], a_f);
+            b.ccx(frame_in, u[0], m_i);
+        }
         b.cx(v_w[0], u[0]);
     }
     b.cx(a_f, b_f);
@@ -906,8 +917,19 @@ pub(crate) fn kaliski_iteration_bulk_prefix3_backward(
     b.cx(a_f, b_f);
     if let Some(frame_out) = uv_frame_out {
         b.cx(v_w[0], u[0]);
-        b.ccx(frame_out, u[0], m_i);
-        b.ccx(frame_out, u[0], a_f);
+        if env_flag_enabled("KAL_UV_STEP1_FANOUT", true) {
+            let t = b.alloc_qubit();
+            b.ccx(frame_out, u[0], t);
+            b.cx(t, m_i);
+            b.cx(t, a_f);
+            let tm = b.alloc_bit();
+            b.hmr(t, tm);
+            b.cz_if(frame_out, u[0], tm);
+            b.free(t);
+        } else {
+            b.ccx(frame_out, u[0], m_i);
+            b.ccx(frame_out, u[0], a_f);
+        }
         b.cx(v_w[0], u[0]);
     }
     b.x(v_w[0]);
```

