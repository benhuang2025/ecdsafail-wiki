# ed94ad2 — Build the λ²-fold quotient·c product from the signed form 977 = 2^10 − 2^5 − 2^4 + 1 (four shifted adds instead of six)

| | |
| --- | --- |
| Contestant | SamrendraS |
| Date | 2026-06-09 |
| Submission | `985a4d3` |
| Commit | `ed94ad2aac81e052766436b16789397674f666f0` |
| Result | 1285 qubits × 1,384,984 Toffoli = **1,779,704,440** |
| Base | `b7515d5` (zuiris, git parent and frontier at the time): 1285 qubits × 1,385,437 Toffoli = 1,780,286,545 |
| Change vs base | qubits ±0, Toffoli −453, score −582,105 (leaderboard Δ −582,105) |
| Family | Strength Reduction → solinas / NAF fold |
| Concepts | [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The in-place Solinas reduction of λ² (the `round84` fold, see
[c27e8a5](c27e8a5.md)) gathers a 33-bit quotient `q`. It then needs
`q · c` with `c = 2^256 − p = 2^32 + 977` in a 66-bit register. The base built
that product from the binary expansion `977 = 1 + 2^4 + 2^6 + 2^7 + 2^8 + 2^9`:
a copy of `q`, then six shifted adds (at shifts 4, 6, 7, 8, 9 and 32).

This commit uses the signed-digit (NAF-like) form
`977 = 2^10 − 2^5 − 2^4 + 1`. That needs only four shifted operations
(+2^10, +2^32, −2^5, −2^4). The shifted adds are measured-carry adders at
about one CCX per target bit, and the total target width falls from 330 to
213 bits. The product is built and unbuilt twice per point add (fold and
unfold), so the saving is about 4 × 117 = 468 Toffoli (−453 measured).
Qubits are unchanged.

## What changed and why it saves Toffoli

1. **New pin `R84_QPROD_NAF=1`** in `configure_ecdsafail_submission_route()`
   (`src/point_add/mod.rs`), read by the new `round84_qprod_naf_enabled()` in
   `arith/multiply.rs`.
2. **`round84_compute_quotient_c_product`.** After the existing
   `product[i] ^= q[i]` copy, it now runs, for
   `(shift, add) in [(10,+), (32,+), (5,−), (4,−)]`,
   `round84_add_small` or `round84_sub_small` of the zero-padded `q` into
   `product[shift..]`.
   - Old target widths: 62 + 60 + 59 + 58 + 57 + 34 = 330 bits.
   - New target widths: 56 + 34 + 61 + 62 = 213 bits.
   - With `ROUND84_FOLD_FAST_ADD=1` these are measured-carry Cuccaro adders
     (`add_nbit_qq_fast` / `sub_nbit_qq_fast`), about 1 CCX per bit. That is
     about −117 Toffoli per call.
3. **`round84_uncompute_quotient_c_product`** runs the same list in reverse,
   with each add replaced by a subtract and each subtract by an add, before
   the final copy-undo. Another −117 per call.
4. The fold (`round84_fold_hi_into_lo_aggregate`) and the unfold
   (`round84_unfold_hi_from_lo_aggregate`) each compute and uncompute the
   product once, so the change applies 4 times per point add, about −468
   Toffoli in all.
5. **`DIALOG_TAIL_NONCE`: 32800438302 → 4591773.**

See [modular-fold](../concepts/modular-fold.md) for why a sparse signed
representation of `c` reduces the number of shifted adds.

## Why it is still correct, and what it risks

The change is exact. Each operation acts on `product[shift..]` modulo
`2^(66 − shift)`, which is arithmetic modulo 2^66 on the whole register.
`q · (1 + 2^10 + 2^32 − 2^5 − 2^4) = q · c` holds as integers. The true
product `q · c < 2^66` fits in the register, so wrap-around in the
intermediate steps cancels. The two adds come before the two subtracts,
so the intermediate values stay non-negative in any case. The uncompute is
the exact inverse sequence.

There are no truncations and no new hard inputs. The nonce was re-hunted
only because the op stream changed. An error would show up as a classical
mismatch and ancilla garbage in the λ² register. The shipped nonce
`4591773` draws a test set with 0 classical, 0 phase and 0 ancilla failures
over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Rewriting a constant multiplication with a sparser signed-digit expansion,
which needs fewer shifted adds, is exactly the solinas / NAF fold change
type.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout b7515d5 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol b7515d5 ed94ad2 -- src/point_add` is
   68 lines in 2 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol ed94ad2 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `MOD_*`, `R84_*` or `ROUND84_*` environment variables
   set. Expect:
   - 1285 qubits
   - 1,384,984 average Toffoli (1,384,983.801 before rounding)
   - score 1,779,704,440
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `4591773` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/arith/multiply.rs b/src/point_add/arith/multiply.rs
index 9bc4a9b..1ddf9ac 100644
--- a/src/point_add/arith/multiply.rs
+++ b/src/point_add/arith/multiply.rs
@@ -866,6 +866,10 @@ fn round84_inplace_vent_carry_enabled() -> bool {
         == Some("1")
 }
 
+fn round84_qprod_naf_enabled() -> bool {
+    std::env::var("R84_QPROD_NAF").ok().as_deref() == Some("1")
+}
+
 struct Round84FoldStep {
     shift: usize,
     add: bool,
@@ -924,26 +928,59 @@ fn round84_compute_quotient_c_product(b: &mut B, quotient: &[QubitId]) -> Vec<Qu
     for i in 0..q.len() {
         b.cx(q[i], product[i]);
     }
-    for shift in [4usize, 6, 7, 8, 9, 32] {
-        let target = &product[shift..];
-        let pad = b.alloc_qubits(target.len() - q.len());
-        let mut source = q.to_vec();
-        source.extend_from_slice(&pad);
-        round84_add_small(b, &source, target);
-        b.free_vec(&pad);
+    if round84_qprod_naf_enabled() {
+        for (shift, add) in [(10usize, true), (32, true), (5, false), (4, false)] {
+            let target = &product[shift..];
+            let pad = b.alloc_qubits(target.len() - q.len());
+            let mut source = q.to_vec();
+            source.extend_from_slice(&pad);
+            if add {
+                round84_add_small(b, &source, target);
+            } else {
+                round84_sub_small(b, &source, target);
+            }
+            b.free_vec(&pad);
+        }
+    } else {
+        for shift in [4usize, 6, 7, 8, 9, 32] {
+            let target = &product[shift..];
+            let pad = b.alloc_qubits(target.len() - q.len());
+            let mut source = q.to_vec();
+            source.extend_from_slice(&pad);
+            round84_add_small(b, &source, target);
+            b.free_vec(&pad);
+        }
     }
     product
 }
 
 fn round84_uncompute_quotient_c_product(b: &mut B, quotient: &[QubitId], product: &[QubitId]) {
     let q = &quotient[..33];
-    for shift in [4usize, 6, 7, 8, 9, 32].into_iter().rev() {
-        let target = &product[shift..];
-        let pad = b.alloc_qubits(target.len() - q.len());
-        let mut source = q.to_vec();
-        source.extend_from_slice(&pad);
-        round84_sub_small(b, &source, target);
-        b.free_vec(&pad);
+    if round84_qprod_naf_enabled() {
+        for (shift, add) in [(10usize, true), (32, true), (5, false), (4, false)]
+            .into_iter()
+            .rev()
+        {
+            let target = &product[shift..];
+            let pad = b.alloc_qubits(target.len() - q.len());
+            let mut source = q.to_vec();
+            source.extend_from_slice(&pad);
+            if add {
+                round84_sub_small(b, &source, target);
+            } else {
+                round84_add_small(b, &source, target);
+            }
+            b.free_vec(&pad);
+        }
+    } else {
+        for shift in [4usize, 6, 7, 8, 9, 32].into_iter().rev() {
+            let target = &product[shift..];
+            let pad = b.alloc_qubits(target.len() - q.len());
+            let mut source = q.to_vec();
+            source.extend_from_slice(&pad);
+            round84_sub_small(b, &source, target);
+            b.free_vec(&pad);
+        }
     }
     for i in 0..q.len() {
         b.cx(q[i], product[i]);
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 617b916..b750141 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1300,6 +1300,7 @@ fn configure_ecdsafail_submission_route() {
     // compressed-block: current-step s2 composite-scratch fold (1308->1307).
     set_default_env("R84_LOWQ", "1");
     set_default_env("R84_LOWQ_CIN_BORROW", "1");
+    set_default_env("R84_QPROD_NAF", "1");  // quotient*c product uses 977 = 2^10 - 2^5 - 2^4 + 1; clean tail nonce above
     // Fold the square's high half into its low half in place, accumulate the
     // resulting 33-bit quotient, apply quotient*(2^256-p) once, subtract once,
     // then reversibly unfold before Bennett-uncomputing the square. The final
@@ -1404,7 +1405,7 @@ fn configure_ecdsafail_submission_route() {
     // Fiat-Shamir island:
     // Binder-notch fallback 8,9: nonce 169924627 validates 0/0/0 over all
     // 9024 shots at 1300q x 1,454,884 T = 1,891,349,200.
-    set_default_env("DIALOG_TAIL_NONCE", "32800438302");
+    set_default_env("DIALOG_TAIL_NONCE", "4591773");
     set_default_env("ROUND84_FOLD_FAST_ADD", "1");  // round84 Solinas-fold small adders coherent->measured-fast (-1,434 exec-T, peak-neutral 1285)
     set_default_env("ROUND84_BIGFOLD_SPLIT", "34");  // round84 BIG-fold adders -> asymmetric 2-block windowed measured (s=34 peak-neutral 1285, -2,124 exec-T)
     set_default_env("DIALOG_GCD_CTRL_LOWQ_MEASURED", "1");  // body stream-suffix ctrl-ride uncompute coherent->measured (-528 exec-T, peak-neutral 1285); island re-hunted to nonce above
```

