# ea73b1a — Stop lending the square's retained AND and cross2 wires in the B branch

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-09-27 |
| Submission | `038ee63` |
| Commit | `ea73b1a27f15f119f1b1e890a1bdeb741734640a` |
| Result | 1250 qubits × 889,081 Toffoli = **1,111,351,250** |
| Base | `8bba91b` (git parent, dysnasia's frontier): 1250 qubits × 889,085 Toffoli = 1,111,356,250 |
| Change vs base | qubits ±0, Toffoli −4, score −5,000 (leaderboard Δ −5,000) |
| Family | Register and Scratch Allocation → scratch/ancilla reuse |
| Concepts | [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit changes two pins and the nonce. `SQ_LEND_RETAINED_ANDS` and
`SQ_LEND_RETAINED_CROSS2` go from 2 to 0. Both are branch bitmasks
(1 = A, 2 = B, 4 = C) for a wire loan inside the square. With the value 2, the
B branch's Karatsuba square erased some retained scratch bits, lent their wires
to its folds, and rebuilt the bits with CCX gates afterwards. At value 0 the
bits simply stay where they are.

At this frontier the B folds fit under the 1250-qubit cap without those wires,
so the rebuild CCXs cost more than the extra room saves. Turning the loans off
saves a net 4 average Toffoli at the same peak. The contestant had made the
same change to an earlier frontier in `c8da745`. dysnasia's
[`265a9e9`](265a9e9.md) was built on the tree before `c8da745`, so the lever
was missing from the frontier again, and this commit puts it back.

## What changed and why it saves Toffoli

**The loan** (`src/point_add/square.rs`, `with_square`, unchanged; see
[venting-and-wire-loans](../concepts/venting-and-wire-loans.md)):
- `with_square` builds `x²` with `tri_square_k2r`, which keeps some retained
  scratch for an exact uncompute. It then runs the folds that consume the
  product, and then uncomputes. The branch number is 1, 2 or 4 for A, B or C.
- **`SQ_LEND_RETAINED_ANDS & branch`**:
  - For each Karatsuba node, `retained_and_bits` lists the retained bit
    `cross[1] = a0 AND NOT t0`, where `t = a + b`.
  - Before the folds, each such bit is erased with `hmr` plus a CZ phase fix
    (`x(t); cz_if(a, t, m); x(t)`), and its wire is lent out.
  - After the folds, the bit is rebuilt with one CCX: `x(t); ccx(a, t, q); x(t)`.
- **`SQ_LEND_RETAINED_CROSS2 & branch`**:
  - For each node, `retained_cross2_bits` lists
    `cross[2] = a0·t1 XOR a1·t0 XOR a0·t0 XOR a0`.
  - `cross2_erase` erases it by measurement, with CZ and Z fixes and no
    Toffoli.
  - `cross2_restore` rebuilds it with two CCX.
- So each lent AND bit costs one CCX, and each lent cross2 bit costs two. In
  return the folds of that branch get one more free wire each under
  `PP_WALK_MAX_QUBITS`.

**The change** (`src/point_add/mod.rs`, `env_raw`):
- `SQ_LEND_RETAINED_ANDS`: 2 → 0, which turns the B-branch AND loans off.
- `SQ_LEND_RETAINED_CROSS2`: 2 → 0, which turns the B-branch cross2 loans off.
- `TAIL_NONCE`: 29234024713 → 280927324351371.
- The raw diff is 368 lines, because the commit also rewrites `mod.rs` from
  CRLF to LF line endings. Ignoring line endings, it is 6 lines.

**Why the net saving is small.** The B folds now see fewer free wires, and
several adders inside them size themselves to the room left. The code shows
two ways this can cost a little back. It does not report the actual split.
- `peak_fitted_add` cuts an add into an exact leading chunk and a high chunk
  sized to the room. With less room, the leading chunk of a split add gets
  wider, and its `PP_F_PEAKCMP = 24`-bit mid-carry compare moves up by the
  same number of bits. The compare costs the same, but it reads different
  bits.
- The WCIN windows from [`a231a39`](a231a39.md) fall back to a one-CCX
  Cuccaro stage when they are one wire short.
- The measured net of everything is −4.

## Why it is still correct, and what it risks

- **Keeping a value in place is exact.** It removes an erase-and-rebuild pair,
  which was itself exact.
- **The peak is unchanged.** The cap is still 1250, and the B folds' ladders
  size themselves to the room left. See
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
- **Moved compare windows are a small risk.** Any `PEAKCMP` compare in the
  B folds whose leading chunk changed now sits on different bits. Each compare is still 24 bits wide,
  so it still has the same ~2^-24 tie rate, but the hard inputs are different
  ones. This is why the nonce must be re-hunted even for such a small change. A
  wrong compare would show up as a phase failure.
- The shipped nonce `280927324351371` draws a clean test set: 9,024 of 9,024
  shots pass, with 0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The change switches off a scratch-reuse loan (lend a reconstructible wire,
then rebuild it) where it no longer helps the peak. That is a register- and
scratch-allocation decision, and the change-type is scratch/ancilla reuse. It
does not narrow any precision knob.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 8bba91b -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 8bba91b ea73b1a -- src/point_add` is
   6 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   This matters here, because the base's `mod.rs` is CRLF. It is the complete
   diff against the base, apart from the line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol ea73b1a -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`.
   - All settings are fixed arms of `env_raw` in `mod.rs`, and the process
     environment is never read. Leave `SQ_*`, `PP_*` and `SUB4_*` unset anyway.
   - Expect 1250 qubits and 889,081 average Toffoli (rounded).
   - Expect a score of 1,111,351,250.
   - Expect 0 classical, 0 phase and 0 ancilla failures.

The score only reproduces with `TAIL_NONCE` `280927324351371` and an identical
op stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index f32fdb5..7d974c6 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -112,8 +112,8 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_DIAG_PRELOAD" => "1",
         "SQ_FIT_CROSS" => "1",
         "SQ_LEND_ASSEMBLY_ZEROS" => "1",
-        "SQ_LEND_RETAINED_ANDS" => "2",
-        "SQ_LEND_RETAINED_CROSS2" => "2",
+        "SQ_LEND_RETAINED_ANDS" => "0",
+        "SQ_LEND_RETAINED_CROSS2" => "0",
         "SQ_LEND_RETAINED_ZEROS" => "1",
         "SQ_ODD_NODE_TOPS" => "1",
         "SQ_ROW0_CARRY" => "1",
@@ -127,7 +127,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "29234024713",
+        "TAIL_NONCE" => "280927324351371",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
```

