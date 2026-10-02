# 2dabd9d — Keep MERGE25's op-5 AND product and reuse it, so a 5-control Toffoli becomes 4-control (E209)

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-08-11 |
| Submission | `bb54b65` |
| Commit | `2dabd9d70c9042c313d8f066389b3ccdc6261b5d` |
| Result | 1154 qubits × 1,284,573 Toffoli = **1,482,397,242** |
| Base | `892b03b` (gopikannappan's 832-key strip): 1154 qubits × 1,284,916 Toffoli = 1,482,793,064 |
| Change vs base | qubits ±0, Toffoli −343, score −395,822 |
| Leaderboard Δ | −379,666, measured against the frontier at the time, `16351d8` (1154 × 1,284,902 = 1,482,776,908), which is **not** this commit's base |
| Family | Register and Scratch Allocation → scratch/ancilla reuse |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The trailmix GCD packs its step decisions into a compressed tape with a
base-5 codec. The `Triple` window runs a fixed gate list called `MERGE25`.
Two gates in that list share a sub-product: op 5 computes `w13·w14` and
throws it away, and op 18 is a 5-control Toffoli whose control set contains
`w13` and `w14` again.

This commit keeps op 5's product in a fresh ancilla and hands it to op 18,
which then needs only 4 controls. A 5-control Toffoli costs 4 Toffoli here and
a 4-control one costs 3, so every `MERGE25` call saves one Toffoli. The
retained ancilla is erased by measurement for free. The rewrite is exact, and
qubits stay at 1154. The total saving is 343 average Toffoli.

## What changed and why it saves Toffoli

All circuit changes are in `apply_merge25` in
`src/point_add/trailmix_ludicrous/codec.rs`. The tail nonce in
`src/point_add/mod.rs` goes from 902265393175 to 365918044.

**The two ops.** `MERGE25_OPS` is a list of `(kind, a, b, t)` codec gates
over the window wires `w6..w16`. Kind 2 is `ccx(a, b → t)`.
- Op 5 is `(2, 13, 14, 12)`: `w12 ^= w13·w14`.
- Ops 18–26 form one 5-control Toffoli, `w12 ^= w8·w9·w10·w13·w14`. Since
  E208 this is emitted by one call `mcx_clean_k(&[w8, w9, w10, w13, w14], w12)`,
  and ops 19–26 are skipped.

**Why the product can be reused.** Between op 5 and op 18 the list writes
`w13` only once, with the X at op 17, and never writes `w14`. So at op 18,
`w13_now · w14 = (w13_old ⊕ 1) · w14 = (w13_old · w14) ⊕ w14`. The old
product needs one CX from `w14` to become the product op 18 needs.

**Forward pass** (encode, `reverse = false`):
1. At op 5: `q = alloc_qubit(); ccx(w13, w14 → q); cx(q → w12)`. This has the
   same effect on `w12` as the original op 5 and also keeps `q = w13·w14`.
2. At op 18: `cx(w14 → q)` turns `q` into `w13_now·w14`. Then
   `mcx_clean_k(&[w8, w9, w10, q], w12)` runs with 4 controls.
3. `clear_and(q, w13, w14)` erases `q`: `hmr` measures it, and a CZ on
   `(w13, w14)` conditioned on the outcome removes the phase. This is exact,
   because `q` equals `w13·w14` at that moment. Then `zero_and_free(q)`.

**Reverse pass** (decode, `reverse = true`) walks the list backwards:
1. At op 18: `q = alloc_qubit(); ccx(w13, w14 → q)`, then the 4-control
   `mcx_clean_k`, then `cx(w14 → q)`, which leaves `q = w13_old·w14` for op 5.
2. At op 5: `cx(q → w12)` replaces the original `ccx`. Then `clear_and` and
   `zero_and_free` retire `q`.

**Cost.** `mcx_clean_k` in `trailmix_ludicrous/mcx.rs` builds a 5-control
gate from 4 CCX (`t01`, `t23`, `t0123`, then the target) and a 4-control gate
from 3 CCX (`t01`, `t23`, then the target). The internal ANDs are erased by
`mbu_clear_and`, an `hmr` plus a conditional CZ, at no Toffoli cost. Per call:

| | op 5 | op 18 | erase | total |
|---|---|---|---|---|
| before (forward or reverse) | 1 CCX | 4 CCX | — | 5 |
| after, forward | 1 CCX (into `q`) | 3 CCX | 0 | 4 |
| after, reverse | 0 (a CX) | 1 + 3 CCX | 0 | 4 |

So each `MERGE25` call saves exactly one Toffoli. `compress_3sym` runs
`MERGE25` forward for every `Triple` window, and `compress_3sym_reverse` runs
it backwards. With `ITERS = 261` the tape has 86 `Triple` windows, and each
point addition runs four GCD walks (two encode, two decode). That is 344
calls, which matches the measured −343. See
[trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) for the codec and
[measurement-uncompute](../concepts/measurement-uncompute.md) for `clear_and`.

**Qubits.** `q` lives from op 5 to op 18. At op 18 the 4-control
`mcx_clean_k` allocates two more ancillas, so 3 clean ancillas are live
together, the same as the 3 that the old 5-control call allocated. The code
comment says the peak clean ancilla count stays at 3. The circuit peak stays
at 1154.

## Why it is still correct, and what it risks

- **The rewrite is exact.** The identity `w13_now·w14 = (w13_old·w14) ⊕ w14`
  holds on every input, because only an X touches `w13` and nothing touches
  `w14` in between. The measured erase is exact because `q` holds exactly
  `w13·w14` when it is measured. It adds no hard inputs, and λ is unchanged.
- `debug_assert!(shared.is_none(), …)` checks that the ancilla never leaks
  past the call. A leaked or dirty ancilla would show up as ancilla garbage,
  and a wrong CZ repair as phase garbage.
- Any op-stream change re-rolls the test draw. The shipped nonce `365918044`
  draws a clean set: 0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from keeping a sub-product in a scratch ancilla and reusing
it in a later multi-control gate, which is scratch/ancilla reuse. The runner-up
is measurement uncompute, which is only the tool that erases the reused wire.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 892b03b -- src/point_add`.
   - `git diff --ignore-cr-at-eol 892b03b 2dabd9d -- src/point_add` is 81
     changed lines in 2 files.
   - Do not start from the git parent `16351d8`. Against it the diff is
     32,524 lines in 4 files. Besides this change, it would remove gnuchev's
     post-strip fanout loop from `mod.rs`, put back the dormant
     `TLM_ADAPTIVE_FINAL_NO_COUT` block in `gidney.rs`, and reorder the whole
     key table in `deep_strip_keys.rs` (the key set is the same).
2. **Apply the patch below** from the repo root with
   `git apply --ignore-whitespace`. The flag lets the patch apply whether the
   files use LF or CRLF line endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 2dabd9d -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   or `TLM_*` overrides set. Expect:
   - 1154 qubits
   - 1,284,573 average Toffoli (rounded)
   - score 1,482,397,242
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `365918044` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index eda4ba5..659f32b 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2382,7 +2382,7 @@ pub fn build() -> Vec<Op> {
     let nonce: u64 = std::env::var("SUB4_TAIL_NONCE")
         .ok()
         .and_then(|s| s.parse().ok())
-        .unwrap_or(902265393175);
+        .unwrap_or(365918044);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
diff --git a/src/point_add/trailmix_ludicrous/codec.rs b/src/point_add/trailmix_ludicrous/codec.rs
index 14f6962..d45b0c0 100644
--- a/src/point_add/trailmix_ludicrous/codec.rs
+++ b/src/point_add/trailmix_ludicrous/codec.rs
@@ -224,23 +224,73 @@ fn apply_op_off(circ: &mut B, w: &[&QubitId], op: (u8, u8, u8, u8), off: u8) {
 fn apply_merge25(circ: &mut B, w: &[&QubitId], off: u8, reverse: bool) {
     let clear: &[usize] = if reverse { &MERGE25_CLEAR_REV } else { &MERGE25_CLEAR_FWD };
     let n = MERGE25_OPS.len();
+    // E209: op 5 is ccx(w13,w14 -> w12); it computes the product w13*w14 and
+    // discards it. Between op 5 and op 18 the source touches w13 only with the
+    // single X at op 17 and never touches w14, so the product op 18's AND tree
+    // needs satisfies w13_cur*w14 = (w13_old*w14) ^ w14. Retaining op 5's
+    // product in a clean ancilla therefore hands the tree one finished node and
+    // collapses the 5-control Toffoli (4 T) to a 4-control one (3 T).
+    // Forward the ancilla is allocated at op 5 and retired at op 18; the reverse
+    // pass walks the same span backwards, so it allocates at op 18 and retires
+    // at op 5. Peak clean ancilla is unchanged at 3.
+    let mut shared: Option<QubitId> = None;
     for step in 0..n {
         let i = if reverse { n - 1 - step } else { step };
-        // E208: ops 18..=26 form one 5-control Toffoli w12 ^= AND(w8,w9,w10,w13,w14),
-        // 9 Toffoli-class gates (2 clean anc). Replace with mcx_clean_k: 7 gates, 3 clean anc.
-        // 5-ctrl Toffoli is an involution => same call for forward and reverse.
+        if i == 5 {
+            debug_assert_eq!(MERGE25_OPS[5], (2u8, 13u8, 14u8, 12u8));
+            let w13 = w[(13 - off) as usize];
+            let w14 = w[(14 - off) as usize];
+            let w12 = w[(12 - off) as usize];
+            if reverse {
+                let q = shared.take().expect("merge25 shared product missing on reverse");
+                circ.cx(q, *w12);
+                clear_and(circ, &q, w13, w14); // free: q == w13 * w14 here
+                circ.zero_and_free(q);
+            } else {
+                let q = circ.alloc_qubit();
+                circ.ccx(*w13, *w14, q); // q = w13 * w14
+                circ.cx(q, *w12); // same net effect on w12 as the original ccx
+                shared = Some(q);
+            }
+            continue;
+        }
+        // E208 + E209: ops 18..=26 form one 5-control Toffoli
+        // w12 ^= AND(w8,w9,w10,w13,w14). With op 5's product retained this is a
+        // 4-control Toffoli on (w8, w9, w10, q): 3 Toffoli, 2 clean anc.
         if i == 18 {
-            super::mcx::mcx_clean_k(
-                circ,
-                &[
-                    w[(8 - off) as usize],
-                    w[(9 - off) as usize],
-                    w[(10 - off) as usize],
-                    w[(13 - off) as usize],
-                    w[(14 - off) as usize],
-                ],
-                w[(12 - off) as usize],
-            );
+            let w13 = w[(13 - off) as usize];
+            let w14 = w[(14 - off) as usize];
+            if reverse {
+                let q = circ.alloc_qubit();
+                circ.ccx(*w13, *w14, q); // q = w13_cur * w14
+                super::mcx::mcx_clean_k(
+                    circ,
+                    &[
+                        w[(8 - off) as usize],
+                        w[(9 - off) as usize],
+                        w[(10 - off) as usize],
+                        &q,
+                    ],
+                    w[(12 - off) as usize],
+                );
+                circ.cx(*w14, q); // q = w13_old * w14, for op 5 to retire
+                shared = Some(q);
+            } else {
+                let q = shared.take().expect("merge25 shared product missing on forward");
+                circ.cx(*w14, q); // q = (w13_old*w14) ^ w14 = w13_cur * w14
+                super::mcx::mcx_clean_k(
+                    circ,
+                    &[
+                        w[(8 - off) as usize],
+                        w[(9 - off) as usize],
+                        w[(10 - off) as usize],
+                        &q,
+                    ],
+                    w[(12 - off) as usize],
+                );
+                clear_and(circ, &q, w13, w14); // free: q == w13_cur * w14 here
+                circ.zero_and_free(q);
+            }
             continue;
         }
         if (19..=26).contains(&i) {
@@ -258,6 +308,7 @@ fn apply_merge25(circ: &mut B, w: &[&QubitId], off: u8, reverse: bool) {
             apply_op_off(circ, w, op, off);
         }
     }
+    debug_assert!(shared.is_none(), "merge25 shared product leaked");
 }
 
 fn compress_3sym(circ: &mut B, w: &[&QubitId; 11]) {
```

