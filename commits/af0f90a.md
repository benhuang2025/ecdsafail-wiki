# af0f90a — Narrow the apply-phase Solinas fold carry window from 24 to 23 bits (plus 37 uncompiled files)

| | |
| --- | --- |
| Contestant | 10d9e |
| Date | 2026-06-05 |
| Submission | `cade2d0` |
| Commit | `af0f90a5ec10387e71fe51b6ae3df4e7eb41e94a` |
| Result | 1390 qubits × 1,531,353 Toffoli = **2,128,580,670** |
| Base | `dda7bfd` (git parent and frontier at the time, robertkodra): 1390 qubits × 1,531,871 Toffoli = 2,129,300,690 |
| Change vs base | qubits ±0, Toffoli −518, score −720,020 (leaderboard Δ −720,020) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **B**: 37 new files that the build never compiles are copied from the commit; the patch covers `mod.rs` |

## Summary

The only live change is one knob. In the GCD apply pass, every modular add
ends with a pseudo-Mersenne fold: if the 256-bit add overflowed, add the
constant c = 2^32 + 977 into the low bits. That constant add uses a ripple
carry, and `KAL_FOLD_CARRY_TRUNC_W` sets how far above bit 32 the carry is
allowed to run. This commit cuts the window from 24 to 23 bits. That is one
Toffoli fewer per fold, and with one fold per apply step in each of two GCD
calls (2 × 259 = 518 folds), the saving is exactly the measured 518 Toffoli.
Qubits are unchanged. The tail nonce was re-hunted.

The commit also adds 37 files, about 9,300 lines, that `mod.rs` never declares
as modules, so they are not compiled. They are a start at splitting `mod.rs`
into smaller files, plus a prototype "divstep dialog" inverter and research
notes. They do not affect the circuit.

## What changed and why it saves Toffoli

**Background.** The circuit is the dialog-GCD route (`emit_dialog_gcd_raw_pa`
in `src/point_add/mod.rs`). Two calls each run a reversible binary GCD on
(u, v) = (p, factor): the quotient dy/dx and the product with c = ox − Rx.
[98416e4](98416e4.md) lists one GCD step. After the forward GCD, the *apply*
pass replays the recorded branch bits on a register pair (x, y). For each step,
in reverse step order, `emit_dialog_gcd_compressed_sidecar_apply_bitvector_block_lifecycle`
does this:

```
y = 2·y mod p                     # mod_double_inplace_fast (and a second, controlled double for K=2)
y = y + b0·x mod p                # dialog_gcd_cmod_add_materialized_pseudomersenne_*  <- the fold is in here
cswap(x, y) if b0_and_b1
```

The quotient call runs the inverse of this sequence, with halvings and
subtractions, and the subtract has the matching fold.

**The modular add.** `dialog_gcd_cmod_add_materialized_pseudomersenne_chunked`
first does a 257-bit raw add into `acc` plus an overflow bit `acc_ovf`. Then it
runs this:

```
set_phase("dialog_gcd_materialized_special_overflow_fold")
if let Some(w) = fold_carry_trunc_window():                       // KAL_FOLD_CARRY_TRUNC_W
    cadd_nbit_const_direct_trunc_fast(acc[..73], c, acc_ovf, w)   // acc += acc_ovf · c, carries only up to bit 32 + w
```

`cadd_nbit_const_direct_trunc_fast` computes carries only at positions
`0 ..= hi + w`, where `hi = 32` is the top set bit of c. Above bit 32, c has
only zero bits, so each extra position costs one CCX. The carries are erased by
measurement, which costs no Toffoli. So the window costs one Toffoli per bit per
fold. The subtract paths (`…underflow_fold`, `…borrowed_underflow_fold`) use
`csub_nbit_const_direct_trunc_fast` with the same window. See
[modular-fold](../concepts/modular-fold.md) for the fold in general.

**The changes in `configure_ecdsafail_submission_route()`:**

- `KAL_FOLD_CARRY_TRUNC_W`: 24 → 23. Each fold has one fewer carry position,
  and there are 259 apply steps in each of 2 GCD calls, so 518 folds × 1 Toffoli
  = 518. `KAL_DOUBLE_CARRY_TRUNC_W`, the same idea for the doublings, stays at 24.
- `DIALOG_TAIL_NONCE`: 73633164035081 → 3155.

**The new, uncompiled files** (copied in Reproduce step 2). None is named in a
`mod` line of `mod.rs`, and nothing else in `src/` refers to them:

- `arith/` (22 files: `adder/`, `modular/`, `multiply/`, `compare.rs`,
  `const_arith.rs`, …), `builder.rs`, `emit.rs`, `rounds/` (6 files, including `rounds/dialog/{apply,compressed,compressor,raw}.rs`)
  and `kaliski/`. These are copies of `mod.rs` code split into topic files, each
  carrying `#![allow(unused_imports, dead_code, clippy::all)]`.
- `divstep_dialog.rs`: a Bernstein–Yang divstep forward pass with a 1-bit-per-step
  transcript. Its header gives its status as "forward pass + simulator
  validation"; nothing declares it as a module.
- `memory/2026-06-04-*.md` and `memory/2026-06-05-directcross-square-island-density.md`:
  session notes on the divstep feasibility, the Kaliski 1200-qubit idea, the
  1350-qubit floor and a Karatsuba square variant.

The files survive on this line, through `b84d15c` and `f0e2891`. The
`fc27501` line, which became the frontier, does not have them.

## Why it is still correct, and what it risks

The fold is exact unless the carry out of bit 32 has to run through all `w`
window positions. That needs a long run of 1 bits in `acc` just above bit 32. The
function's doc comment puts this at about 2^-(w+1) per call, and only calls
where the fold fires (`acc_ovf = 1`) can fail. The commit comment calls the
lever "value-exact on the reachable support", but that is too strong. Going
from 24 to 23 bits roughly doubles the per-call risk. At 2^-24 per call and
about 259 firing folds per shot, that is still only about 0.1 expected failing
shots per 9,024-shot draw, so the other truncations dominate λ. On a failure
the high bits of `y` stay wrong, which is a classical failure.

The author measured 6 broken test inputs at the inherited nonce, the gentlest
lever on this tree. The local full-validation searcher found `3155` after about
3,200 nonces. That nonce draws a clean set: 0 classical, 0 phase and 0 ancilla
failures over all 9,024 shots.

## Classification rationale

The census files this under comparator/width truncation. What it narrows is the
carry window of the modular fold's constant add, so "fold/carry truncation" is
the more precise change-type. That is the label used for the same knob family in
[`438ef00`](438ef00.md). The uncompiled files are not a lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout dda7bfd -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol dda7bfd af0f90a -- src/point_add` is 9,324 lines
   in 38 files. All but 10 of those lines are the 37 new files.
2. **Copy the new files from the commit:**
   `git checkout af0f90a -- src/point_add/arith src/point_add/rounds src/point_add/kaliski src/point_add/builder.rs src/point_add/emit.rs src/point_add/divstep_dialog.rs src/point_add/memory/2026-06-04-divstep-phase0-feasibility.md src/point_add/memory/2026-06-04-kaliski-1200q-revisit-verdict.md src/point_add/memory/2026-06-04-qubit-floor-and-island-density.md src/point_add/memory/2026-06-05-directcross-square-island-density.md`.
   They are hand-written, but nothing compiles them. They are copied because they
   are large and have no effect on the circuit.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It covers `mod.rs`, the only edited file.
4. **Check the tree.** `git diff --ignore-cr-at-eol af0f90a -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set.
   `set_default_env` only fills variables that are unset. Expect:
   - 1390 qubits
   - 1,531,353 average Toffoli (rounded)
   - score 2,128,580,670
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `3155` and an identical op stream. Any
other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 56700dd..0aa40b6 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -31277,7 +31277,11 @@ fn configure_ecdsafail_submission_route() {
     // comparator on low/mid-width GCD steps, orthogonal to the slope envelope.
     set_default_env("DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN", "6");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "24");
-    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "24");
+    // FOLD-carry lazy-Solinas window tightened 24 -> 23 (-518 avg executed
+    // Toffoli, peak-neutral at 1390q). The narrower fold-reduction carry window
+    // re-rolls the Fiat-Shamir island; the identity tail nonce below was
+    // re-found (DIALOG_TAIL_NONCE=3155) for a clean 9024-shot validation.
+    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "23");
     set_default_env("DIALOG_GCD_ROUND763_DEDUP", "1");
     set_default_env("DIALOG_GCD_ROUND763_COMPRESS_LEVER", "1");
     set_default_env("DIALOG_GCD_MEASURED_UNDERFLOW_GATE", "1");
@@ -31463,7 +31467,9 @@ fn configure_ecdsafail_submission_route() {
     // clean island: validated 0/0/0 over all 9024 shots at 1350q x 1,763,987 T.
     // Fiat-Shamir island for the K=2 apply rebalance above: 0/0/0 over all
     // 9024 shots at 1390q x 1,630,487 T.
-    set_default_env("DIALOG_TAIL_NONCE", "73633164035081");
+    // Re-found for the KAL_FOLD_CARRY_TRUNC_W=23 op stream: nonce=3155 lands a
+    // clean island, validated 0/0/0 over all 9024 shots at 1390q x 1,531,353 T.
+    set_default_env("DIALOG_TAIL_NONCE", "3155");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

