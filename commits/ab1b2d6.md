# ab1b2d6 — Fold the step-0 shift flag t1 into the step-0 transcript code and drop the step-0 swap flag (1167 → 1166 qubits)

| | |
| --- | --- |
| Contestant | PhantasticUniverse |
| Date | 2026-06-19 |
| Submission | `33392f6` |
| Commit | `ab1b2d64452887d302180a2f0e421252dd8d0edd` |
| Result | 1166 qubits × 1,422,616 Toffoli = **1,658,770,256** |
| Base | `615ce9a` (git parent, jackylee0424): 1167 qubits × 1,422,588 Toffoli = 1,660,160,196 |
| Change vs base | qubits −1, Toffoli +28, score −1,389,940 (leaderboard Δ −1,389,940) |
| Family | Codec / Encoding → trailmix / K5 codec |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In the trailmix jump-GCD, step 0 is special in two ways:
- its first halving is controlled by a flag `t1` ("x is even");
- its swap decision is always equal to its subtract bit, because `u = q > v = x`.

The base kept `t1` as a separate qubit at the front of the compressed
transcript for the whole GCD, next to the 2-bit step-0 code. This commit packs
`t1` and the step-0 symbol into the same 2 bits, which makes the transcript one
qubit shorter for its whole lifetime. It also stops allocating a separate swap
flag at step 0. Peak qubits drop from 1167 to 1166. Average Toffoli rises by 28: the new
step-0 code adds one CCX to each compress and each decompress (four per point
add, over the two GCDs), and the rest comes from the new nonce's draw.

## What changed and why it saves a qubit

### `trailmix_ludicrous/codec.rs`

- New `compress_step0_with_t1(t1, [sub, swap, s2]) → [t1, s2]`. Only four
  triples `(t1, sub, s2)` can occur at step 0: `(0,1,0)`, `(1,1,0)`, `(1,1,1)`
  and `(1,0,1)`. At step 0 we also have `swap = sub`. The map is:
  1. `cx(sub, swap)`, which clears `swap`;
  2. `cx(sub, t1)`;
  3. `x(sub)`;
  4. `ccx(t1, s2, sub)`, which clears `sub` on all four cases;
  5. free `sub` and `swap`.

  The four cases land on the four distinct values of `(t1, s2)`: (1,0), (0,0),
  (0,1) and (1,1). So the four reachable states fit in 2 qubits. The four
  states do not form an affine subspace, so one CCX is needed, as the doc
  comment says.
- New `decompress_step0_with_t1`, which is the exact inverse: allocate `sub`
  and `swap`, `ccx(t1, s2, sub)`, `x(sub)`, `cx(sub, t1)`, `cx(sub, swap)`.
- `dialog_tape_qubits(n3, iters)` loses the `1 +` for the separate `t1`
  prefix. Its assertion fixes the resident tape length, which is now one
  qubit shorter.

### `trailmix_ludicrous/gcd.rs`

- **`forward_gcd_jump`.**
  - `swap_flag` becomes an `Option`, allocated lazily at step 1. At step 0 the
    swap control `swp` is `subtracted` itself, since the old code did
    `cx(subtracted, swap_flag)` there.
  - When the symbol is recorded at step 0, `slots[1]` gets
    `cx(slots[0], slots[1])` instead of a swap. Then
    `compress_step0_with_t1(t1, slots)` produces the 2 tape bits directly, and
    the loop continues.
  - The old `tape.insert(0, t1)` is removed.
- **`reverse_gcd_jump`.**
  - The Step0 window is decompressed with `decompress_step0_with_t1`, which
    gives back `t1` (kept in `step0_t1`) and the raw symbol.
  - At step 0 the swap bit is cleared with `cx(subtracted, cur[1])`, and
    `subtracted` is used as the swap control.
  - The reusable `swap_flag` is freed at the end of step 1, so it is not live
    during step 0.
  - The shift-1 inverse and `apply_step_forward` read `t1` from `step0_t1`
    instead of `tape[0]`.
  - `t1` is freed at the end of step 0, as before.
- The old step-0 swap-flag uncompute (`cx(subtracted, swap_flag)`) is gone,
  because there is no step-0 flag to clear.

Why it lowers the peak: the compressed tape is live from the first GCD step
until the reverse pass drains it, and the circuit's peak lies in that span.
One tape qubit fewer for the whole span lowers every point by one. Dropping
the swap flag near step 0 keeps the reverse pass's step-0 point from becoming
the new maximum. See
[peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md) and
[trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md).

### `src/point_add/mod.rs`

`DIALOG_TAIL_NONCE` default in `build()`: `"75501"` → `"6147"`. The comment
is updated to the new operating point.

## Why it is still correct, and what it risks

- **Exact.** The new step-0 code is a bijection on the four reachable
  step-0 states.
- **Why only four states.** At step 0, `u = q` and `v = x < q`:
  - the swap equals the subtract bit, because `v < u` always;
  - only those four combinations of `t1`, `sub` and `s2` can occur.
- **What else could reach step 0.** The only other possibility is a step-0
  state that the previous code also did not handle, such as `x = 0`. So the
  change adds no new failure mode.
- **Cost.** The extra Toffoli are the CCX in each step-0 compress and
  decompress (four per point add), plus the shift in the average that a new
  draw brings.
- **Nonce.** Nonce `6147` draws a clean test set: 0 classical, 0 phase and 0
  ancilla failures over 9,024 shots. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The qubit comes from a tighter transcript encoding: `t1` is merged into the
step-0 code. That is a codec change, which fits Codec / Encoding → trailmix /
K5 codec. The lazy swap flag is a small qubit-lifetime fix in the same commit.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 615ce9a -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 615ce9a ab1b2d6 -- src/point_add` is
   134 lines in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol ab1b2d6 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*` or `LUD_*` environment variables set. Expect:
   - 1166 qubits
   - 1,422,616 average Toffoli (1,422,616.408 before rounding)
   - score 1,658,770,256
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `6147` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index d514858..2c224cd 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1969,10 +1969,10 @@ pub fn build() -> Vec<Op> {
         }
     }
     // Submitted circuit: the trailmix-ludicrous product-min secp256k1 point-add
-    // at the nonce-ground operating point (1167 qubits x 1,422,591 executed
+    // at the nonce-ground operating point (1166 qubits x 1,422,616 executed
     // Toffoli). The tail nonce reseeds the Fiat-Shamir inputs so all 9024
     // verifier draws land in the schedule-supported set.
-    set_default_env("DIALOG_TAIL_NONCE", "75501");
+    set_default_env("DIALOG_TAIL_NONCE", "6147");
     trailmix_ludicrous::build_trailmix_ludicrous_ops()
 }
 
diff --git a/src/point_add/trailmix_ludicrous/codec.rs b/src/point_add/trailmix_ludicrous/codec.rs
index 4d736eb..ca1f24c 100644
--- a/src/point_add/trailmix_ludicrous/codec.rs
+++ b/src/point_add/trailmix_ludicrous/codec.rs
@@ -313,6 +313,41 @@ impl DialogCodec {
     }
 }
 
+/// Step-0-only codec that folds the separate `t1` prefix into the first dialog
+/// symbol. The reachable triples `(t1, subtracted, s2)` are only four cases:
+/// `(0,1,0)`, `(1,1,0)`, `(1,1,1)`, `(1,0,1)`. They are not an affine subspace,
+/// so one nonlinear gate is needed to clear a wire while keeping a reversible map.
+#[must_use]
+pub fn compress_step0_with_t1(circ: &mut B, t1: QubitId, raw: &[QubitId]) -> Vec<QubitId> {
+    assert_eq!(raw.len(), 3, "step0 raw symbol is [sub, swap, s2]");
+    let sub = raw[0];
+    let swap = raw[1];
+    let s2 = raw[2];
+    circ.cx(sub, swap);
+    circ.cx(sub, t1);
+    circ.x(sub);
+    circ.ccx(t1, s2, sub);
+    circ.zero_and_free(sub);
+    circ.zero_and_free(swap);
+    vec![t1, s2]
+}
+
+/// Inverse of [`compress_step0_with_t1`]. Returns the restored `t1` qubit plus
+/// the raw `[sub, swap, s2]` symbol slots.
+#[must_use]
+pub fn decompress_step0_with_t1(circ: &mut B, data: &[QubitId]) -> (QubitId, Vec<QubitId>) {
+    assert_eq!(data.len(), 2, "step0+t1 code is two bits");
+    let t1 = data[0];
+    let s2 = data[1];
+    let sub = circ.alloc_qubit();
+    let swap = circ.alloc_qubit();
+    circ.ccx(t1, s2, sub);
+    circ.x(sub);
+    circ.cx(sub, t1);
+    circ.cx(sub, swap);
+    (t1, vec![sub, swap, s2])
+}
+
 /// Ordered region schedule for the all-triple product-min config: Step0 first,
 /// then triples, then a small Pair/Raw tail. `(n3, n5)` are sized as the
 /// product-min selector does (`n3 = iters/3`, `n5 = 0`); `iters` is the schedule
@@ -349,12 +384,12 @@ pub fn jump_dialog_regions(n3: usize, iters: usize) -> Vec<(DialogCodec, usize)>
 }
 
 /// Persistent compressed-tape qubits for the `(n3)` all-triple dialog codec at
-/// `iters` symbols: `1` (t1) + sum over regions of `code_bits * count`.
+/// `iters` symbols: sum over regions of `code_bits * count`. Step0's code bits
+/// include the first-shift `t1` bit, so no separate prefix is resident.
 #[must_use]
 pub fn dialog_tape_qubits(n3: usize, iters: usize) -> usize {
-    1 + jump_dialog_regions(n3, iters)
+    jump_dialog_regions(n3, iters)
         .into_iter()
         .map(|(codec, count)| codec.code_bits() * count)
         .sum::<usize>()
 }
-
diff --git a/src/point_add/trailmix_ludicrous/gcd.rs b/src/point_add/trailmix_ludicrous/gcd.rs
index 32cc0df..beb5a10 100644
--- a/src/point_add/trailmix_ludicrous/gcd.rs
+++ b/src/point_add/trailmix_ludicrous/gcd.rs
@@ -196,7 +196,7 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
     }
 
     let subtracted = circ.alloc_qubit();
-    let swap_flag = circ.alloc_qubit();
+    let mut swap_flag: Option<QubitId> = None;
     let s2 = circ.alloc_qubit(); // the single jump=2 extra-shift flag
     let t1 = circ.alloc_qubit(); // step-0 shift1-fired flag (= x even)
 
@@ -247,23 +247,25 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         circ.cx(v[0], subtracted);
 
         // 3) swap decision. Step 0: u=q, v=x<q always, so (v<u)=1 deterministically,
-        //    so swap_flag = subtracted (one CX). Else the narrow top-k comparator
+        //    so swap = subtracted and no separate swap flag is needed. Else the narrow top-k comparator
         //    decides swap_flag ^= subtracted AND (v < u).
-        if i == 0 {
-            circ.cx(subtracted, swap_flag);
+        let swp = if i == 0 {
+            subtracted
         } else {
+            let sf = *swap_flag.get_or_insert_with(|| circ.alloc_qubit());
             controlled_swap_decision_v_lt_u(
                 circ,
                 &subtracted,
                 &v[..current_n],
                 &u[..current_n],
                 cmp_eff,
-                &swap_flag,
+                &sf,
             );
-        }
+            sf
+        };
         // 4) cswap(swap_flag, u, v).
         for j in 0..current_n {
-            circ.cswap(swap_flag, u[j], v[j]);
+            circ.cswap(swp, u[j], v[j]);
         }
         // 5) v -= subtracted * u (controlled mod-free subtract on the active width;
         //    post-swap v >= u so no borrow on a fitting input). X-sandwich add.
@@ -280,14 +282,25 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         // tape. Forward iter order matches apply_step_reverse's order, so the tape is
         // never materialized for the apply -> the apply adders run in the GCD's headroom.
         if let Some((xr, yr)) = apply_inv {
-            apply_step_reverse(circ, i, &subtracted, &swap_flag, &s2, &t1, xr, yr);
+            apply_step_reverse(circ, i, &subtracted, &swp, &s2, &t1, xr, yr);
         }
 
         // 6) record the symbol into fresh |0> slots (returning the ancilla to |0>).
         let slots: Vec<QubitId> = (0..sym_bits).map(|_| circ.alloc_qubit()).collect();
         circ.swap(subtracted, slots[0]);
-        circ.swap(swap_flag, slots[1]);
+        if i == 0 {
+            circ.cx(slots[0], slots[1]);
+        } else {
+            circ.swap(swp, slots[1]);
+        }
         circ.swap(s2, slots[2]);
+        if i == 0 {
+            debug_assert_eq!(window_plan[win_idx], super::codec::DialogCodec::Step0);
+            let data = super::codec::compress_step0_with_t1(circ, t1, &slots);
+            tape.extend(data);
+            win_idx += 1;
+            continue;
+        }
         pending.extend(slots);
 
         // When the current window's symbols are complete, compress it inline.
@@ -311,10 +324,10 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         circ.zero_and_free(q);
     }
     circ.zero_and_free(subtracted);
-    circ.zero_and_free(swap_flag);
+    if let Some(swap_flag) = swap_flag {
+        circ.zero_and_free(swap_flag);
+    }
     circ.zero_and_free(s2);
-    // Prepend t1: tape = [t1, win_0 code bits, ..]  (compressed layout).
-    tape.insert(0, t1);
     assert_eq!(tape.len(), super::codec::dialog_tape_qubits(n3, iters));
     tape
 }
@@ -351,8 +364,9 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
     circ.x(u[0]);
 
     let subtracted = circ.alloc_qubit();
-    let swap_flag = circ.alloc_qubit();
+    let mut swap_flag: Option<QubitId> = Some(circ.alloc_qubit());
     let s2 = circ.alloc_qubit();
+    let mut step0_t1: Option<QubitId> = None;
 
     for i in (0..iters).rev() {
         let current_n = (SCHED_J2[i] as usize).max(1);
@@ -372,13 +386,28 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
             let cb = codec.code_bits();
             let tlen = tape.len();
             let data: Vec<QubitId> = tape.split_off(tlen - cb);
-            pending = codec.decompress_window(circ, &data);
+            if codec == super::codec::DialogCodec::Step0 {
+                let (t1, raw) = super::codec::decompress_step0_with_t1(circ, &data);
+                step0_t1 = Some(t1);
+                pending = raw;
+            } else {
+                pending = codec.decompress_window(circ, &data);
+            }
         }
         // Pull the last symbol (3 bits) off `pending` into the ancilla.
         let plen = pending.len();
         let cur: Vec<QubitId> = pending.split_off(plen - 3);
         circ.swap(subtracted, cur[0]);
-        circ.swap(swap_flag, cur[1]);
+        let swp = if i == 0 {
+            circ.cx(subtracted, cur[1]);
+            subtracted
+        } else {
+            let sf = *swap_flag
+                .as_ref()
+                .expect("swap flag live for non-step0 replay");
+            circ.swap(sf, cur[1]);
+            sf
+        };
         circ.swap(s2, cur[2]);
         // Free the 3 now-|0> symbol slots here -- before the apply -- so they are not
         // carried as dead live qubits through the apply + GCD-undo, where they would
@@ -393,8 +422,8 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
         // order matching apply_step_forward's order, so the tape is never materialized
         // for the apply -> the apply adders run in the (reverse) GCD's headroom.
         if let Some((xr, yr)) = apply_fwd {
-            let t1 = tape[0];
-            apply_step_forward(circ, i, &subtracted, &swap_flag, &s2, &t1, xr, yr);
+            let t1 = step0_t1.unwrap_or(subtracted);
+            apply_step_forward(circ, i, &subtracted, &swp, &s2, &t1, xr, yr);
         }
 
         // Inverse step (reverse op order): sub^-1, cswap^-1, cmp^-1, subtracted^-1,
@@ -403,22 +432,20 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
         controlled_add_active(circ, &subtracted, &u[..current_n], &v[..current_n]);
         // b) cswap^-1 (involutory).
         for j in 0..current_n {
-            circ.cswap(swap_flag, u[j], v[j]);
+            circ.cswap(swp, u[j], v[j]);
         }
         // c) uncompute swap_flag. Step 0 is a CNOT (swap_flag == subtracted). For
         //    i>=1 the flag holds `subtracted AND (v<u)`; clear it by measurement-vent
         //    (hmr + capped Z-recompute under push_condition) -- ~half the normal
         //    comparator's Toffoli, scorer-discounted ~0.5 more.
-        if i == 0 {
-            circ.cx(subtracted, swap_flag);
-        } else {
+        if i != 0 {
             super::comparator::swap_decision_uncompute_vented(
                 circ,
                 &subtracted,
                 &v[..current_n],
                 &u[..current_n],
                 cmp_eff,
-                &swap_flag,
+                &swp,
             );
         }
         // d) subtracted^-1: cx(v[0], subtracted) (v[0] still post-shift parity).
@@ -429,18 +456,23 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
         circ.cx(v[0], s2);
         // f) shift1 inverse: i>=1 unconditional left-shift; i==0 gated on t1.
         if i == 0 {
-            controlled_left_shift(circ, &tape[0], &v[..current_n]);
-            circ.x(tape[0]);
-            circ.cx(v[0], tape[0]);
+            let t1 = step0_t1.expect("step0 t1 decompressed");
+            controlled_left_shift(circ, &t1, &v[..current_n]);
+            circ.x(t1);
+            circ.cx(v[0], t1);
         } else {
             left_shift(circ, &v[..current_n]);
         }
 
         // (symbol slots already freed before the apply, above). At i==0 drain t1.
         if i == 0 {
-            let t1 = tape.pop().expect("t1 prefix");
+            let t1 = step0_t1.take().expect("step0 t1 present");
             circ.zero_and_free(t1);
         }
+        if i == 1 {
+            let sf = swap_flag.take().expect("swap flag still allocated");
+            circ.zero_and_free(sf);
+        }
     }
     assert!(tape.is_empty(), "tape not fully drained");
 
@@ -455,7 +487,9 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
         circ.zero_and_free(q);
     }
     circ.zero_and_free(subtracted);
-    circ.zero_and_free(swap_flag);
+    if let Some(swap_flag) = swap_flag {
+        circ.zero_and_free(swap_flag);
+    }
     circ.zero_and_free(s2);
 }
 
@@ -719,4 +753,3 @@ fn clear_zeroed_drift(circ: &mut B, reg: &[QubitId]) {
         }
     }
 }
-
```

