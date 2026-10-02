# 1d2cbc9 — Move the apply-pass chunk split from bit 126 to 128 (1446 → 1443 qubits), plus a partial-hosting fallback for the branch comparator

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-02 |
| Submission | `80326f1` |
| Commit | `1d2cbc9898dc13da6f3a89f744652a41de6b2c6b` |
| Result | 1443 qubits × 1,736,647 Toffoli = **2,505,981,621** |
| Base | `6189d5f` (git parent and frontier at the time, alexander-sei): 1446 qubits × 1,735,059 Toffoli = 2,508,895,314 |
| Change vs base | qubits −3, Toffoli +1,588, score −2,913,693 (leaderboard Δ −2,913,693) |
| Family | Register and Scratch Allocation → scratch/ancilla reuse |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [adders-and-carries](../concepts/adders-and-carries.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

After [`6189d5f`](6189d5f.md) the 1446 peak was set by the apply pass, which
adds and subtracts a controlled 256-bit value into a 257-bit accumulator in
two chunks split at bit `F_CUT`. The upper chunk was the larger one. This
commit moves the split from 126 to 128. The upper chunk's scratch shrinks by
about 4 wires and the lower chunk's grows by about 4, so the two are nearly
balanced. The peak drops by 3, to 1443. The price is the exact compare that
clears the lower chunk's carry-out, which is 2 bits wider at each of
2 × 397 apply sites: 2 × 2 × 397 = 1,588 Toffoli, exactly the measured change.

The commit also adds a "partial hosting" fallback to the branch-bit
comparator, switched on by default. By my reading of the code it never
triggers on this route, because `6189d5f`'s u-high borrow already hands the
comparator a long enough clean slice at every step. It is Toffoli-neutral
either way.

## What changed and why it saves qubits

All changes are in `src/point_add/mod.rs`.

1. **`DIALOG_GCD_APPLY_CHUNKED_F_CUT`: 126 → 128** (in
   `configure_ecdsafail_submission_route`).
   - Context: the dialog GCD's apply pass replays the transcript on 257-bit
     coefficient registers. Each of the 397 steps does a controlled modular
     add and a controlled modular subtract
     (`dialog_gcd_cmod_add_materialized_pseudomersenne_chunked` and its
     subtract twin, phases `materialized_special_chunked_raw_sum` /
     `_difference`). With `DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS=2`, the raw add
     `dialog_gcd_add_ctrl_chunked_low_to_ext` works in two blocks:
     - Block 0 is bits `[0, F_CUT)`. It loads `f = ctrl & source[0..F_CUT]`
       into fresh wires, adds with `cuccaro_add_fast` into
       `acc[0..F_CUT] ++ cout` (a pad wire plus an internal carry lane), and
       clears `f` with `hmr` + `cz_if`. `cout` stays live.
     - Block 1 is bits `[F_CUT, 257)`. It loads the rest of `f` and runs
       `cuccaro_add_fast_low_to_ext` with `cout` as the carry-in.
     - Afterwards the boundary carry `cout` is cleared exactly by recomputing
       it: `ccx_cmp_lt_into_fast(acc[..F_CUT], source[..F_CUT], ctrl, cout)`,
       which costs about one Toffoli per bit.
   - Each block's scratch is about 2 × its width: the loaded `f` slice plus a
     carry lane. At 126 the upper block (131 bits) was wider than the lower
     (126 bits). At 128 they are 129 and 128 bits. This takes about 4 wires off
     the binding block. The global peak falls by 3, so the next-highest phase
     sits at 1443.
   - The boundary compare grows from 126 to 128 bits, in both the add and the
     subtract (`dialog_gcd_sub_ctrl_chunked_low_to_ext`), at every step:
     +1,588 Toffoli.
   - See [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md)
     and [adders-and-carries](../concepts/adders-and-carries.md).
2. **Partial hosting in `dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted`**
   (new `DIALOG_GCD_PARTIAL_HOST_COMPARATOR`, on unless set to `"0"`).
   - The branch comparator (it decides `u > v` for the step's `b0_and_b1` bit)
     needs `need = compare_bits + 1` clean wires: a carry-in and
     `compare_bits` carries. The old rule was all or nothing. If the borrowed
     slice was at least `need` long, everything was hosted on it. Otherwise
     `ccx_cmp_lt_into_fast` allocated all `need` wires fresh.
   - New rule: if `0 < avail < need`, use the whole borrowed slice and
     allocate only `need − avail` extra wires, gathered into one vector. The
     comparator indexes each wire separately, so the result is the same.
   - Why it is dead code here (my reading): the slice comes from
     `dialog_gcd_pick_borrow_slice`. When the future-log slice is shorter than
     `2n − 1` (`n = active_width ≥ 4` at every step), it returns
     `u[n .. 3n − 1]` instead, which is `2n − 1 ≥ n + 1 ≥ need` long.
     Otherwise the future slice is at least `2n − 1` long, or `n ≥ 86` and it
     is at least `n − 1 ≥ 85 > 59 ≥ need` long. So `avail < need` never
     happens. The commit's comment says the late-step comparator self-allocated
     and pinned 1446. That was true on [`8ab5f90`](8ab5f90.md)'s tree, which
     has no u-high borrow, but not on this base.
3. **Reroll pair: `DIALOG_REROLL` 37 → 52, `DIALOG_POST_SUB_REROLL` 1 → 7.**
   These are the counts of identity `X;X` pairs that only re-draw the 9,024
   test inputs.

## Why it is still correct, and what it risks

Both circuit changes are exact. The chunked apply add and subtract give the
same result at any cut: the carry crosses the boundary through `cout`, and
`cout` is erased by an exact full-width compare of the lower bits. The
partial-hosting path, if it ran, would only change which wires hold the
comparator's carries. Borrowed wires are |0⟩ on entry and are returned to |0⟩
by the comparator's measured uncompute. A bookkeeping error there would show
up as ancilla or phase garbage.

No new approximation is added. The existing ones (397 steps, 58-bit branch
compare, width envelope) are unchanged, and the reroll pair (52, 7) draws a
clean set for them: 9,024 of 9,024 shots pass with 0 classical, 0 phase and
0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this as scratch/ancilla reuse, which matches the
comparator-hosting part of the diff. By my reading, though, that part is
inactive on this route, and the qubits come only from re-balancing the two
apply chunks: a window/split re-tune that trades a wider boundary compare for
a lower peak. "Windowing → windowed carry/shift blocks" would describe the
effective lever better.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6189d5f -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 6189d5f 1d2cbc9 -- src/point_add` is
   34 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 1d2cbc9 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`,
   `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set, because
   `set_default_env` keeps any value already in the environment. Expect:
   - 1443 qubits
   - 1,736,647 average Toffoli (rounded)
   - score 2,505,981,621
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the reroll pair `DIALOG_REROLL=52`,
`DIALOG_POST_SUB_REROLL=7` and an identical op stream. Any other change needs
a new reroll search.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 5fb16cf..99b30b9 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -23763,8 +23763,25 @@ fn dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted(
     let cmp_u = &v[start..];
     let cmp_v = &u[start..];
     let n = cmp_u.len();
-    // Need c_in (1) + carries (n) = n+1 borrowed lanes.
-    if let Some(slice) = borrowed.filter(|s| s.len() >= n + 1) {
+    // Need c_in (1) + carries (n) = n+1 clean lanes. PARTIAL hosting: borrow the
+    // future-log prefix that fits and allocate only the deficit, instead of
+    // all-or-nothing (which fully self-allocs n+1 at the late GCD steps where the
+    // slice runs short, pinning the branch_bits peak at 1446). The borrowed-carries
+    // comparator indexes c_in and each carries[i] independently, so a gathered
+    // [borrowed_prefix ++ owned] vec is value-identical; borrowed lanes are restored
+    // to |0> by the measured backward inv-MAJ sweep, owned lanes are freed.
+    let need = n + 1;
+    let avail = borrowed.map(|s| s.len()).unwrap_or(0);
+    if dialog_gcd_partial_host_comparator_enabled() && avail > 0 && avail < need {
+        let slice = borrowed.expect("avail>0");
+        let owned = b.alloc_qubits(need - avail);
+        let mut clean: Vec<QubitId> = Vec::with_capacity(need);
+        clean.extend_from_slice(slice);
+        clean.extend_from_slice(&owned);
+        let (c_in, carries) = clean.split_first().expect("need >= 1");
+        ccx_cmp_lt_into_fast_borrowed_carries(b, cmp_u, cmp_v, ctrl, target, *c_in, &carries[..n]);
+        b.free_vec(&owned);
+    } else if let Some(slice) = borrowed.filter(|s| s.len() >= need) {
         let (c_in, carries) = slice.split_first().expect("slice len >= n+1 > 0");
         ccx_cmp_lt_into_fast_borrowed_carries(b, cmp_u, cmp_v, ctrl, target, *c_in, &carries[..n]);
     } else {
@@ -23772,6 +23789,13 @@ fn dialog_gcd_ccx_cmp_gt_truncated_into_width_hosted(
     }
 }
 
+fn dialog_gcd_partial_host_comparator_enabled() -> bool {
+    std::env::var("DIALOG_GCD_PARTIAL_HOST_COMPARATOR")
+        .ok()
+        .as_deref()
+        != Some("0")
+}
+
 fn dialog_gcd_cmp_gt_truncated_into(b: &mut B, u: &[QubitId], v: &[QubitId], flag: QubitId) {
     dialog_gcd_cmp_gt_truncated_into_width(b, u, v, flag, dialog_gcd_compare_bits().min(u.len()));
 }
@@ -29894,15 +29918,15 @@ fn configure_ecdsafail_submission_route() {
     // 399 T/qubit, far inside break-even. Score 1446 x 1,740,263 = 2,516,420,298.
     set_default_env("DIALOG_GCD_BODY_HOST_CIN", "1");
     set_default_env("DIALOG_GCD_LATE_BORROW_UV_HIGH", "1");
-    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "126");
+    set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "128");
     // TOFFOLI STACK on the 1446 base: with body-host-cin + uv-high-borrow + F_CUT=126,
     // the two public proven tightenings COMPARE_BITS 59->58 (−952) and
     // ACTIVE_ITERATIONS 399->397 (−4,252) stack for −5,204 executed Toffoli at the
     // same 1446 peak. The combined op-stream re-rolls the Fiat-Shamir island; a 2-D
     // (DIALOG_REROLL x DIALOG_POST_SUB_REROLL) search lands 37/1 clean 0/0/0 over all
     // 9024 shots. Validated via eval_circuit: 1446q x 1,735,059 T = 2,508,895,314.
-    set_default_env("DIALOG_REROLL", "37");
-    set_default_env("DIALOG_POST_SUB_REROLL", "1");
+    set_default_env("DIALOG_REROLL", "52");
+    set_default_env("DIALOG_POST_SUB_REROLL", "7");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

