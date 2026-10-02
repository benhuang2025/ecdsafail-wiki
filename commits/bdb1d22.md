# bdb1d22 — Replace the dialog-GCD circuit with the trailmix "ludicrous" jump-GCD point add

| | |
| --- | --- |
| Contestant | tob-joe |
| Date | 2026-06-19 |
| Submission | `af5abb1` |
| Commit | `bdb1d22261e6e5e86dba5f63a8339449430b167a` |
| Result | 1167 qubits × 1,422,591 Toffoli = **1,660,163,697** |
| Base | `ba3efc1` (BitWonka): 1168 qubits × 1,431,621 Toffoli = 1,672,133,328 |
| Change vs base | qubits −1, Toffoli −9,030, score −11,969,631 |
| Leaderboard Δ | −8,908,303, measured against the frontier at the time, `57eb64b` (1168 qubits, 1,669,072,000), which is **not** this commit's base |
| Family | Codec / Encoding → trailmix / K5 codec |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [modular-fold](../concepts/modular-fold.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md), [transcript-codecs](../concepts/transcript-codecs.md) |
| Reproduce tier | **B**: the new `trailmix_ludicrous/` module (11 files) is copied from the commit; the patch covers `mod.rs` |

## Summary

This commit swaps the whole circuit. `build()` stops building the dialog-GCD
route and instead returns the output of a new module,
`src/point_add/trailmix_ludicrous/`. That module is a port of Trail of Bits'
"trailmix ludicrous" point add onto the challenge's `B` builder.

The new circuit still divides with a jump-2 binary GCD that records a
transcript and replays it. Its differences from the dialog route are:
- it applies each step to the coefficient registers at the moment the step is
  computed, instead of in a separate apply phase;
- it packs three steps into 7 qubits with a base-5 codec;
- it drives every adder, carry cap, vent count and comparator window from
  baked per-call tables.

The result is one qubit and 9,030 average Toffoli below the base. All later
trailmix commits (19 June to 21 August) build on this module. The old dialog
code stays in the tree but is no longer called.

## What changed and why it is cheaper

### New module `src/point_add/trailmix_ludicrous/` (copied, 4,990 lines)

[trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) describes this circuit in
detail. In brief:

- **`ec_add.rs` (186 lines): the affine add.** For a quantum P and a
  classical Q (`ox`, `oy` as `BitId` registers):
  1. `x2 −= ox`, `y2 −= oy`.
  2. `y2 *= x2⁻¹`, so `y2` holds λ.
  3. `x2 += 3·ox`.
  4. `x2 −= λ²`.
  5. `y2 *= x2`.
  6. `y2 −= oy`.
  7. `x2 := ox − x2`.

  Each classical coordinate is loaded into a temporary quantum register only
  for its own add or subtract (`coord_addsub`), so it is never live at the GCD
  peak. Steps 2 and 5 both call `gcd::mod_mul_inverse_in_place` (`Direction::Inverse`
  and `Direction::Forward`).
- **`gcd.rs` (722 lines): the jump-GCD.** It runs the Schrottenloher jump-2
  GCD for `ITERS = 258` steps on `(u, v) = (q, x)`. Each step records a 3-bit
  symbol `(subtracted, swap, s_2)`.
  - The apply is fused into the passes. In the forward pass each step is
    applied to `[y, tmp]` right away, for the inverse. The reverse pass undoes
    the walk, restores `x`, drains the tape, and applies the forward step to
    `[tmp, y]` for the multiply.
  - The GCD registers are held at the per-step width `SCHED_J2[i]`. The swap
    comparator only looks at a top window `GAP_J2[i]`.
- **`codec.rs` (360 lines): the transcript codec.** Only 5 of the 8 symbol
  patterns can occur, so a window of three symbols (9 raw bits, log₂ 5³ ≈ 6.97)
  is packed into 7 bits (`TRIPLE_DATA_WIRES`) by a SAT-synthesized reversible
  network (`NORMALIZER_OPS`, `MERGE25_OPS`). Each window is compressed as soon
  as its symbols exist, and the reverse pass decompresses one window at a
  time. The submission note puts the resident tape at 603 qubits, against
  about 775 raw.
- **`schedule.rs` (139 lines): the baked tables.** It holds `SCHED_J2` and
  `GAP_J2` (258 entries each), `PAD = 21` (the +f fold carry cap), and
  per-call tables read in order by `mod.rs`'s `next_*` cursors:
  - `GCD_SUB_K`, `GCD_BRANCH`;
  - `APPLY_COUT_K`, `FOLD_SCHED`;
  - `CMP_K`, `FFG_G`, `HYB_V`, `SQ_ROW_K`.

  Each adder call (1,032 `GCD_SUB_K` entries for the GCD steps, 516
  `APPLY_COUT_K` entries for the apply) picks its carry cap, vent count and
  chunking from these, sized for the live-qubit count at that point. See
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
- **Arithmetic modules:**
  - `arith.rs` (1,286 lines): vented ripple adders and pseudo-Mersenne
    mod-add/sub/double. A +f fold only touches the low `PAD + bitlen(f)` bits,
    so a longer carry is dropped. See [modular-fold](../concepts/modular-fold.md).
  - `fused.rs` (763 lines): a fused `y := 2y(1 + s_2)` with one `(e + 2d)·f`
    reduction.
  - `comparator.rs` (241 lines): truncated top-window comparators.
  - `gidney.rs` (563 lines): measurement-based AND uncompute, `hmr` plus a
    conditional Z. See [measurement-uncompute](../concepts/measurement-uncompute.md).
  - `mcx.rs` (286 lines): multi-controlled X with few ancillas.
  - `square.rs` (223 lines): a symmetric schoolbook square-subtract, with
    row widths from `SQ_ROW_K`. See
    [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md).
- **`mod.rs` (221 lines).**
  - The `BExt` trait adds `z`, `ccz`, `neg`, `cswap` and bit-conditioned
    gates on `B`.
  - `load_schedule()` sets up the cursors.
  - `build_trailmix_ludicrous_ops()` allocates the four IO registers, runs
    `ec_add` and routes R.x back to reg0 with `route_swaps`.
  - It appends the tail nonce as 48 `X;X` pairs on `reg0[1]` (nonce bit = 1)
    or `reg0[0]` (bit = 0), with the nonce read from `DIALOG_TAIL_NONCE`.

### Edits to `src/point_add/mod.rs` (the patch)

- Declares `mod trailmix_ludicrous;`.
- `build()` now ends with
  `set_default_env("DIALOG_TAIL_NONCE", "28565"); trailmix_ludicrous::build_trailmix_ludicrous_ops()`
  instead of `build_builder().ops`. `build_builder()`, and with it
  `configure_ecdsafail_submission_route()` and all the `DIALOG_*`, `SQUARE_*`
  and `KAL_*` defaults, is no longer reached.

### Deleted files

The commit deletes `src/point_add/arith/compare.rs.patch`, a stray patch file,
and the six agent memory notes in `src/point_add/memory/`. None of them is
compiled.

## Why it is still correct, and what it risks

- **Exact.** The algorithm is exact when nothing is truncated. The walk's
  record and replay are reversible, the codec is a bijection on the 5³
  reachable windows, and the measured uncomputes are exact.
- **Probabilistic.** The input-dependent losses all come from baked
  truncations:
  - `SCHED_J2`: a step whose `max(bitlen(u), bitlen(v))` exceeds the scheduled
    width loses a bit;
  - `GAP_J2` / `CMP_K` swap windows: a wrong swap decision when the highest
    differing bit is below the window;
  - `PAD = 21`: a fold carry dropped with probability about 2^-21 per fire;
  - `ITERS = 258`: an input that has not converged by then.

  The submission note quotes the source's operating point as about 99.87%
  success per addition.
- **Channels.** Value errors are classical failures. Wrong swap or fold
  decisions that leave the tape or ancillas dirty are phase or ancilla
  failures.
- **Nonce.** Nonce `28565` draws a test set with none of these inputs: 0
  classical, 0 phase and 0 ancilla failures over 9,024 shots. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The published label is Codec / Encoding → trailmix / K5 codec. The codec is
only one part of the change, though. The commit replaces the whole
point-addition circuit, including the GCD walk, the apply, the adders, the
fold, the square and the schedule, with a different implementation of the same
jump-GCD idea. "Algorithmic Substitution" (a whole-circuit or architecture
swap, as in [`897dda2`](897dda2.md)) fits the diff better. The header keeps
the published label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout ba3efc1 -- src/point_add`.
   - The git parent is `57eb64b`, whose `src/point_add` differs from
     `ba3efc1` only in its vented-body band-trim lines and tail nonce in
     `configure_ecdsafail_submission_route()`.
   - Against the parent, the patch would also delete those two
     `DIALOG_GCD_VENTED_BODY_*` settings and revert 57eb64b's nonce. That
     looks like a revert, but those lines are dead code in this commit anyway.
   - `git diff --ignore-cr-at-eol ba3efc1 bdb1d22 -- src/point_add` is 5,915
     lines. Of those, 4,990 are the new module and 916 are deleted memory
     notes and the stray patch file.
2. **Copy the new module from the commit:**
   `git checkout bdb1d22 -- src/point_add/trailmix_ludicrous`. These are
   hand-written sources plus the baked tables in `schedule.rs`, copied because
   they are too large to inline. The section above describes them.
3. **Delete the removed files and apply the patch below** from the repo root
   with `git apply --ignore-whitespace`. The `rm` command above the diff
   handles the deletions. The flag lets the patch apply whether the files use
   LF or CRLF line endings.
4. **Check the tree.** `git diff --ignore-cr-at-eol bdb1d22 -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*` or `LUD_*` environment variables set. Expect:
   - 1167 qubits
   - 1,422,591 average Toffoli (1,422,590.97 before rounding)
   - score 1,660,163,697
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `28565` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

Delete these files first:

```sh
rm src/point_add/arith/compare.rs.patch \
   src/point_add/memory/2026-06-06-tony-anton-audit-loop.md \
   src/point_add/memory/2026-06-07-measured-frontier-leads.md \
   src/point_add/memory/2026-06-07-structural-breakthrough-leads.md \
   src/point_add/memory/2026-06-08-measured-frontier-optimizations.md \
   src/point_add/memory/2026-06-11-measured-square-carry-selective-k3.md \
   src/point_add/memory/2026-06-13-q1192-wmi-cuda-search.md
```

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f35c44d..a73bcee 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -79,6 +79,8 @@ pub(crate) use arith::*;
 mod rounds;
 pub(crate) use rounds::*;
 
+mod trailmix_ludicrous;
+
 thread_local! {
     static D1_PHASE_CORRECTED_PRODUCT_CORE_SCOPE: std::cell::Cell<bool> =
         std::cell::Cell::new(false);
@@ -1966,7 +1968,12 @@ pub fn build() -> Vec<Op> {
             return Vec::new();
         }
     }
-    build_builder().ops
+    // Submitted circuit: the trailmix-ludicrous product-min secp256k1 point-add
+    // at the nonce-ground operating point (1167 qubits x 1,422,591 executed
+    // Toffoli). The tail nonce reseeds the Fiat-Shamir inputs so all 9024
+    // verifier draws land in the schedule-supported set.
+    set_default_env("DIALOG_TAIL_NONCE", "28565");
+    trailmix_ludicrous::build_trailmix_ludicrous_ops()
 }
 
 pub fn square_window_selftest() -> Result<(), String> {
```

