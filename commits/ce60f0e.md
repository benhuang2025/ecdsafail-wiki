# ce60f0e — Compute the swap-merge STEP 1 fix-up once and fan it out, instead of two Toffolis with the same controls

| | |
| --- | --- |
| Contestant | Gajesh2007 |
| Date | 2026-06-01 |
| Submission | `fde221f` |
| Commit | `ce60f0ef4d157b41374106d062b732ea9e39177b` |
| Result | 2310 qubits × 3,356,758 Toffoli = **7,754,110,980** |
| Base | [`f910ba3`](f910ba3.md) (git parent, the author's previous submission): 2310 qubits × 3,357,772 Toffoli = 7,756,453,320 |
| Change vs base | qubits ±0, Toffoli −1,014, score −2,342,340 (leaderboard Δ −2,342,340) |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The `(u, v_w)` swap merge of [`36a2989`](36a2989.md) has to correct two
STEP 1 flags, `a_f` and `m_i`, by the same bit `frame & (u0 ⊕ v0)`. It did
that with two CCX gates that have identical controls. This commit computes the
bit once into a fresh ancilla `t` with one CCX, copies it into both flags with
two CX, and erases `t` by X-basis measurement plus a classically conditioned
CZ, which costs no Toffoli. That saves one Toffoli per merged iteration. There
are 1,014 merged iterations per shot, so the saving is exactly 1,014 Toffoli.
Qubits are unchanged.

## What changed and why it saves Toffoli

`src/point_add/kaliski_walk.rs`, behind the new flag `KAL_UV_STEP1_FANOUT`
(default on, `=0` restores the old gates).

- **Forward, `kaliski_iteration_bulk_prefix3`, STEP 1 fix-up** (runs when the
  iteration receives a deferred `frame` from the previous one). Between
  `cx(v_w[0], u[0])` and its undo, `u[0]` temporarily holds `u0 ⊕ v0`.
  - Old: `ccx(frame, u[0], a_f); ccx(frame, u[0], m_i)`, 2 CCX.
  - New:
    ```
    t = alloc;  ccx(frame, u[0], t)      // t = frame & (u0 ^ v0)   1 CCX
    cx(t, a_f); cx(t, m_i)               // fan out                  0 CCX
    hmr(t, tm); cz_if(frame, u[0], tm)   // measure t away, fix phase
    free(t)
    ```
- **Backward, `kaliski_iteration_bulk_prefix3_backward`**: the mirrored fix-up
  with `frame_out`, same rewrite (the CX targets are in the reverse order,
  `m_i` then `a_f`).
- **Count.** The fix-up runs in every iteration with `uv_merge_in` and an
  incoming frame: iterations 1 to 253 for pair1 (cap 254) and 1 to 254 for
  pair2 (cap 255), forward and backward. That is 2 × 253 + 2 × 254 = 1,014
  fix-ups, each now 1 CCX instead of 2. This matches the measured −1,014
  exactly.
- `hmr` measures `t` in the X basis and resets it. When the outcome `tm` is 1,
  the state picks up the phase `(-1)^t`, and since `t = frame & u[0]` at that
  moment, `cz_if(frame, u[0], tm)` cancels it exactly. See
  [measurement-uncompute](../concepts/measurement-uncompute.md).

## Why it is still correct, and what it risks

The rewrite is exact.
- After the fan-out, `a_f` and `m_i` get the same XOR as before.
- `t` is reset by the measurement.
- The conditional CZ restores the phase on every branch, because its controls
  are exactly the two bits `t` was computed from, and both are unchanged at
  that point.
- No probabilistic assumption is added. A mistake would show as phase garbage.

The extra ancilla `t` lives only inside STEP 1, not at the STEP 4 peak, so the
peak stays at 2310. The changed op stream draws a new hashed test set (no
tail nonce in this era). It is clean: 0 classical, 0 phase and 0 ancilla
failures.

## Classification rationale

The saving comes from erasing a shared AND by measurement instead of paying a
second Toffoli: Uncompute Strategy → measurement uncompute. Fusion → gate/op
fusion (two CCX with the same controls merged) is the runner-up. The fused
form only pays off because the shared AND is erased for free.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f910ba3 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol f910ba3 ce60f0e -- src/point_add` is
   30 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ce60f0e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `KAL_*`,
   `POINT_ADD_*` or `BY_*` environment variables set. Expect:
   - 2310 qubits
   - 3,356,758 average Toffoli (rounded)
   - score 7,754,110,980
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era: the test set is a hash of the op stream,
so the score only reproduces with an identical op stream.

### Patch

```diff
diff --git a/src/point_add/kaliski_walk.rs b/src/point_add/kaliski_walk.rs
index ff268cf..ef72879 100644
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
@@ -887,8 +898,19 @@ pub(crate) fn kaliski_iteration_bulk_prefix3_backward(
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

