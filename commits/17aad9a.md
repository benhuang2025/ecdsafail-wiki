# 17aad9a — Replace the 6 → 5 transcript compressor with a 4-CCX code that only has to work on the 27 reachable inputs

| | |
| --- | --- |
| Contestant | mpjunior92 |
| Date | 2026-06-02 |
| Submission | `51d09c7` |
| Commit | `17aad9a49f1fafef6865a16039f41641b526819d` |
| Result | 1571 qubits × 1,738,981 Toffoli = **2,731,939,151** |
| Base | `6e7ca2c` (the author's previous submission): 1571 qubits × 1,742,173 Toffoli = 2,736,953,783 |
| Change vs base | qubits ±0, Toffoli −3,192, score −5,014,632 |
| Leaderboard Δ | −4,956,505, measured against the frontier at the time, `7408de1` (prasiddhnaik, 1571 × 1,742,136 = 2,736,895,656), which is **not** this commit's base |
| Family | Constant Propagation and Classical Specialization → host-derived / classical specialization |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The dialog-GCD walk records two bits per step, `b0` and `b0_and_b1`. The
second is `b0 AND (u > v)`, so the pair (0, 1) never occurs, and each step has
only 3 possible values. Three steps therefore have 27 values. A reversible
6-qubit circuit, the "round763" compressor, maps them into 5 qubits and leaves
the sixth at |0⟩. The base compressor used 7 CCX. This commit replaces it with
a different 8-gate circuit with only 4 CCX. That circuit is not a valid
compressor on all 64 inputs, but it is on the 27 that occur. The compressor or
its inverse runs 8 times per block of three steps, and there are 133 blocks,
so 3 CCX saved per call is 3 × 8 × 133 = 3,192 Toffoli. The change is exact.
Qubits are unchanged.

## What changed and why it saves Toffoli

Background on the walk and the compressed log is in [8316db1](8316db1.md).
The compressor works on a 6-qubit raw block: slot `k` (k = 0, 1, 2) holds
`b0` in bit `2k` and `b0_and_b1` in bit `2k+1`. After compression, bits 0–4
are swapped or copied into the 5-qubit compressed block, and bit 5 must be 0.

Changes in `src/point_add/mod.rs`:

- New switch `round763_compress_lever_enabled()`
  (`DIALOG_GCD_ROUND763_COMPRESS_LEVER`), set to `"1"` in
  `configure_ecdsafail_submission_route()`.
- `emit_dialog_gcd_round763_compressor`, with the switch on, emits:

  ```
  cx(5→3); ccx(3,4→5); cx(1→4); cx(1→0); ccx(4,5→1); cx(0→2); ccx(2,5→0); ccx(0,1→5)
  ```

  The base, with the already-on `ROUND763_DEDUP`, emitted
  `ccx(4,5→3); ccx(3,4→5); ccx(1,2→4); cx(1→0); ccx(4,5→1); ccx(0,5→2); ccx(2,5→0); ccx(0,1→5)`.
  That is 7 CCX, now 4: three CCX became CX.
- `emit_dialog_gcd_round763_compressor_inverse` gets the exact gate-reversed
  sequence.
- `DIALOG_REROLL` 1 → 6 and `DIALOG_POST_SUB_REROLL` 0 → 3: the two identity
  `X;X` pads, re-searched for a clean draw.

Where the 3,192 comes from. Each block of three steps passes through the
compressor or its inverse 8 times per point addition:
- the forward walk compresses it once and the reverse walk decompresses it
  once, in both GCD uses (4 calls);
- each apply pass decompresses a copy (`dialog_gcd_copy_compressed_block_to_raw`)
  and recompresses it to clear the copy (`dialog_gcd_clear_raw_block_copy`),
  in both uses (4 calls).

So the total is 8 × 133 blocks × 3 CCX = 3,192, exactly the measured drop.

## Why it is still correct, and what it risks

I checked both circuits by simulation on all 27 reachable inputs. Each slot
must avoid `(b0, b0_and_b1) = (0, 1)`.
- The new forward map is injective (27 distinct outputs).
- It always leaves bit 5 at 0.
- The new inverse undoes it on every input.

The new map is **not** the same code as the old one: 10 of the 27 inputs get
a different 5-bit code. The commit comment and the submission note say the
three CCX "collapse to CX". That is misleading. It is a different valid
encoding, not a gate-by-gate simplification of the old one. That is fine here,
because every reader of the compressed log goes through the same compressor
or its inverse: the reverse walk, the apply-pass copy and clear, and the
per-step swapper. No code reads the 5-bit codes directly.

The invariant holds on every input, including ones where a truncated
comparator gives the wrong branch, because `b0_and_b1` is always computed as
`b0 AND (...)`. So the change adds no failure mode. The rerolls were rescanned
because the op stream changed. The shipped pair (6, 3) draws 0 classical, 0
phase and 0 ancilla failures. If an unreachable state did occur, bit 5 would
be left dirty, which would show as ancilla garbage.

## Classification rationale

The saving comes from a fact about which inputs can occur (the (0, 1) slot
state never does), which is specialization to the reachable input set. The
census label fits. The runner-up is an exact peephole (see
[dead-gate-strip](../concepts/dead-gate-strip.md)). Strictly it is neither, but
a re-synthesis of a small reversible circuit on its reachable domain.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6e7ca2c -- src/point_add`.
   - Do not start from the git parent `7408de1`. Against it, the diff also
     deletes prasiddhnaik's memory note, restores
     `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` 19 → 20, and brings in
     `DIALOG_GCD_COMPARE_BITS` 61 and its comments. The author built on their
     own `6e7ca2c` instead.
   - `git diff --ignore-cr-at-eol 6e7ca2c 17aad9a -- src/point_add` is 50
     lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 17aad9a -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set.
   Expect:
   - 1571 qubits
   - 1,738,981 average Toffoli (rounded)
   - score 2,731,939,151
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_REROLL = 6`,
`DIALOG_POST_SUB_REROLL = 3` and an identical op stream. Any other change
needs a new reroll scan.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index c406eae..121d14a 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -24592,8 +24592,35 @@ fn round763_dedup_enabled() -> bool {
     std::env::var("DIALOG_GCD_ROUND763_DEDUP").ok().as_deref() == Some("1")
 }
 
+fn round763_compress_lever_enabled() -> bool {
+    // EXACT (reachable-input) rewrite of the round763 6->5 sidecar packer.
+    // Provable: each raw slot is (b0, b0_and_b1) with b0_and_b1 = b0 AND (v<u),
+    // so state (0,1) is UNREACHABLE on every GCD input. On that 27-code support
+    // three dedup'd CCX collapse to CX (verified by exhaustive 27-input search):
+    //   ccx(4,5->3)->cx(5->3); ccx(1,2->4)->cx(1->4); ccx(0,5->2)->cx(0->2).
+    // With the unconditional ccx(1,3->4) bracket dedup, 9 CCX -> 4 CCX/direction.
+    // Forward/inverse stay mutual inverses + 27-distinct injection with scratch->0
+    // on reachable inputs. Default OFF (the new op stream reseeds Fiat-Shamir).
+    std::env::var("DIALOG_GCD_ROUND763_COMPRESS_LEVER")
+        .ok()
+        .as_deref()
+        == Some("1")
+}
+
 fn emit_dialog_gcd_round763_compressor(b: &mut B, block: &[QubitId]) {
     assert_eq!(block.len(), 6);
+    if round763_compress_lever_enabled() {
+        // 4-CCX reachable-support form (see round763_compress_lever_enabled).
+        b.cx(block[5], block[3]);
+        b.ccx(block[3], block[4], block[5]);
+        b.cx(block[1], block[4]);
+        b.cx(block[1], block[0]);
+        b.ccx(block[4], block[5], block[1]);
+        b.cx(block[0], block[2]);
+        b.ccx(block[2], block[5], block[0]);
+        b.ccx(block[0], block[1], block[5]);
+        return;
+    }
     b.ccx(block[4], block[5], block[3]);
     b.ccx(block[3], block[4], block[5]);
     b.ccx(block[1], block[2], block[4]);
@@ -24612,6 +24639,18 @@ fn emit_dialog_gcd_round763_compressor(b: &mut B, block: &[QubitId]) {
 
 fn emit_dialog_gcd_round763_compressor_inverse(b: &mut B, block: &[QubitId]) {
     assert_eq!(block.len(), 6);
+    if round763_compress_lever_enabled() {
+        // Exact gate-reverse of the 4-CCX reachable-support forward form.
+        b.ccx(block[0], block[1], block[5]);
+        b.ccx(block[2], block[5], block[0]);
+        b.cx(block[0], block[2]);
+        b.ccx(block[4], block[5], block[1]);
+        b.cx(block[1], block[0]);
+        b.cx(block[1], block[4]);
+        b.ccx(block[3], block[4], block[5]);
+        b.cx(block[5], block[3]);
+        return;
+    }
     b.ccx(block[0], block[1], block[5]);
     b.ccx(block[2], block[5], block[0]);
     b.ccx(block[0], block[5], block[2]);
@@ -29022,6 +29061,13 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "20");
     set_default_env("KAL_FOLD_CARRY_TRUNC_W", "20");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
+    // EXACT round763 compressor rewrite: the 6->5 sidecar packer's input slot
+    // (b0, b0_and_b1) has state (0,1) UNREACHABLE on all GCD inputs (b0_and_b1 =
+    // b0 AND (v<u)). On that 27-code support, 3 dedup'd CCX collapse to CX,
+    // taking the compressor 9 CCX -> 4 CCX/direction. −3,192 executed Toffoli,
+    // peak-neutral 1571, validated 0/0/0. (DIALOG_GCD_ROUND763_COMPRESS_LEVER=0
+    // restores the 9-CCX form.)
+    set_default_env("DIALOG_GCD_ROUND763_COMPRESS_LEVER", "1");
     set_default_env("DIALOG_GCD_MEASURED_UNDERFLOW_GATE", "1");
     // Branch comparator width tightened 63 -> 61 (−1,160 executed Toffoli),
     // STACKED on the PA9024 margin-5 cut. Two within-budget truncations coexist
@@ -29063,8 +29109,8 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_WINDOW_BLOCKS", "2");
     // New low-bit body op stream needs its own clean Fiat-Shamir island:
     // REROLL=1, POST_SUB_REROLL=12 validates 0/0/0 over 9024.
-    set_default_env("DIALOG_REROLL", "1");
-    set_default_env("DIALOG_POST_SUB_REROLL", "0");
+    set_default_env("DIALOG_REROLL", "6");
+    set_default_env("DIALOG_POST_SUB_REROLL", "3");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

