# cc7f10e — "PR 419": lend provably known wires across the square, walk and replay, lower the cap 1259 → 1251, and buy back error with more rounds and wider guards

| | |
| --- | --- |
| Contestant | mochimodev (Matt Zweil with MAI-A.A.E., Mochimo Foundation) |
| Date | 2026-09-25 |
| Submission | `8186402` |
| Commit | `cc7f10e6951965379c14777a9845ee509f1df0b3` |
| Result | 1251 qubits × 897,597 Toffoli = **1,122,893,847** |
| Base | `a39e07e` (odinfree, the tree the author calls "HEAD"): 1259 qubits × 903,434 Toffoli = 1,137,423,406. This is neither the git parent nor the `data/bases.tsv` pick; see Reproduce. |
| Change vs base | qubits −8, Toffoli −5,837, score −14,529,559 |
| Leaderboard Δ | −14,474,017, measured against the frontier at the time, `9700396` (jackylee0424, 1258 × 904,108 = 1,137,367,864), which is the git parent but **not** this commit's base |
| Family | Register and Scratch Allocation → scratch/ancilla reuse |
| Concepts | [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [pingpong-division](../concepts/pingpong-division.md), [modular-fold](../concepts/modular-fold.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [adders-and-carries](../concepts/adders-and-carries.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: `pingpong.rs` is copied from the commit; the patch covers the rest |

## Summary

This is a large composite: 62 configured levers plus the code behind them.
The author's note catalogues each one. It keeps the ping-pong divider and the
Karatsuba square, and changes three things.

1. **Qubits (−8).**
   - The single qubit cap `PP_WALK_MAX_QUBITS` goes from 1259 to 1251, and
     every carry ladder sizes itself to the new room.
   - To make that affordable, the commit lends wires whose value is known.
     Examples: a sign bit that is a copy of the bit below it, a cross-term bit
     that is always zero, and a duplicate of an input bit. Each lent wire is
     cleared, used as scratch, and restored.
   - It also replaces some adders with exact adders that fit in less
     workspace, and it retunes the replay batches.
2. **Toffoli (net −5,837).**
   - Many square carries and terminal bits are known in advance. They are
     copied, rebuilt with CX, or measured out instead of computed with CCX.
   - Two carry phases are deferred to the inverse that recreates the same
     carry.
   - The replay cell's correction is restructured: reused selectors, a
     prebiased halving, and a retained final frame that removes the flag
     compare.
   - More truncated compares are seeded with a source bit.
3. **Error protection bought back (costs Toffoli).** 698 rounds in both
   directions instead of 696/694, one walk guard bit for widths ≤ 64,
   `FOLD_GUARD` 21 → 24, divide fold window 53 → 54, and wider short flag
   compares.

The score drops 1.28%. The note also attaches a "limiting contract": circuits
built on this one must keep λ ≤ 18 and must not trade error for score
directly. The later dysnasia commits follow it.

## What changed and why it saves qubits and Toffoli

Labels in brackets (W1, S4, …) are the author's catalogue items. Mechanisms
were checked against the code. Sizes are the author's, or rough gate counts
from reading the code, as marked.

### 0. Configuration: a fixed table (`src/point_add/mod.rs`)

- `env_raw(name)` no longer reads the environment. It returns values from a
  fixed `match` table. Unlisted knobs are absent, and so off.
- `set_default_env` is gone, and `build()` no longer pins anything.
- `PP_SIMPLIFY` is now read from the table too. It pins the same four-pass
  simplifier chain that `a39e07e` ran by default.
- In `pingpong.rs`, `a5_policy()` hard-codes `"mul-fb-seed"` instead of reading
  `A5_REPAIR`.
- Many new knobs are listed as `0`, which means off: `PP_SOURCE_SIGN_LOAN`,
  `PP_SPLIT_FOLD_OVERAGE`, `PP_SPRINT_MIXED`, `PP_MID_BATCH_DIV`,
  `SQ_BORROW_ROW_CARRIES`, `SQ_SPARSE_SPREAD` and `SQ_SPARSE_CORRECTION`.
- One exception: `PP_JOINT_GUARD=0` is an enable. Its planner starts with
  `optional_env("PP_JOINT_GUARD")?`, so the value 0 only sets the guard width.

### 1. The cap and the replay schedule [R1]

- **`PP_WALK_MAX_QUBITS`: 1259 → 1251.** This is the one budget that the walk
  splits, replay chunks, folds, endpoint and fitted square adds all size
  against. See [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
  The peak follows it to 1251.
- **Head boundary `r1`: computed → pinned.**
  - `Plan::new` reads `PP_HEAD_DIV=192` and `PP_HEAD_MUL=403`.
  - `head_boundary()` gave 312/307 at the old cap.
  - Rounds below `r1` are replayed in one batch.
- **Tail boundary `r2`: shared `PP_R2=648` → per direction.**
  - `PP_TAIL_DIV=684` and `PP_TAIL_MUL=645`. `PP_R2` stays in the table but is
    no longer read.
  - The trailing batches, replayed at the loaned terminal state, now start at
    rounds 685 and 646.
- **`PP_MID_BATCH_MUL=32`** (multiply middle rounds only).
  - The walk-back now goes in batches of up to 32 rounds.
  - A batch `[lo, hi]` grows downward while the live footprint
    `r + 1 + 2·value_width(r+1)` stays at least `footprint(hi)`.
  - All replays of the batch run at walk state `hi`, then all walk-backs run.
  - A replay touches only the coefficient pair and its own tape wire, so the
    reordering is exact.
  - Each replay sees at least as much room as before, so it chunks less.
  - `PP_MID_BATCH_DIV=0` keeps the divide's one-walk-one-replay interleave.

### 2. Walk side [W1–W3, R2]

Background: [pingpong-division](../concepts/pingpong-division.md),
[venting-and-wire-loans](../concepts/venting-and-wire-loans.md).

- **W1 `PP_CF_DEFER_WALK_PHASE=1`** (divide only).
  - When a forward walk add is split at bit `low` (`walk_add_split`), the
    boundary carry used to be measured and erased with `erase_boundary_carry`,
    a conditional compare over `low − 2` bits.
  - Now it is only measured. The outcome is kept as `DeferredWalkPhase {measured, low}`.
  - That round's walk-back runs a single-ladder ripple, which recreates the
    same carry as internal carry `low − 4`. The new
    `ripple_add_with_deferred_phase` / `ripple_add_lent_with_deferred_phase`
    apply `z_if(carry, measured)` just before that carry's own measured unwind.
  - This saves the whole boundary compare (about `(low − 3)/2` executed Toffoli
    per split round) at the cost of one classical bit. It is exact.
- **W2 `PP_SOURCE_SIGN_GROW=1`.**
  - On a walk-back round where `grow_to` has just widened the source, the
    source's top bit is a CX copy of the bit below.
  - `modular::ripple_add_source_sign_loan` clears it, uses it as the last carry
    wire, and restores it.
  - `walk_low_chunk(.., source_sign_loan)` counts that wire, so fewer adds
    split, and splits are one bit narrower. Exact.
- **W3 `PP_REPLAY_SIGN_LOAN=1`, `PP_REPLAY_SIGN_LOAN_MUL=1`.**
  - Around each replay cell, `with_forward_replay_sign_loans` (divide) and
    `with_reverse_replay_sign_loans` (multiply) look for walk registers whose
    top wire is a proved sign copy of the wire below. That holds when the
    width has not changed since the halving or `grow_to` that made the copy.
  - Each such wire is cleared with one CX, released to the allocator, and
    re-made after the cell.
  - The count goes into `REPLAY_SIGN_LOANS`. `chunked_add` still plans its
    approximate boundaries from the old room, and spends the loaned wires only
    on merging or shrinking an exact leading chunk. So no approximate boundary
    moves.
- **R2 `PP_Q1208_HELPERS=1`, walk part.** In `walk_add_single`, if the lent
  single ripple would not fit under the cap, `compact_chunk_add::add` (new
  file, 34 lines) runs it as an exact chunked add instead. Each block carry is
  erased high to low by a compare over the *whole* block with the live
  incoming carry, which is exact.
- **Inactive in the shipped build:**
  - the "quarter step" / mod-4 sign rule, the depth record and the barrel
    shifter (`mod4_sign`, `depth_*`, `barrel_*`, `replay_extra_shift`,
    `guard_xor`); `PP_MOD4_SIGN` is unset and `PP_DEPTH_PROFILE=0:0`;
  - the "C2" tape shedding (`c2_*`); `PP_C2_*` is unset;
  - `PP_SOURCE_SIGN_LOAN=0`.

  These account for several hundred of the new lines in `pingpong.rs`.

### 3. Square [S1–S10]

Background: [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md),
[measurement-uncompute](../concepts/measurement-uncompute.md). All of these are
exact: each uses an identity that holds on every input.

- **S6 deeper recursion: `SQ_A_POLICY = SQ_B_POLICY = SQ_C_POLICY = 7`.**
  - `with_square` stores the value as a bitmask for the whole recursion under
    that outer square. `policy_min(bit, …)` then splits:
    - the low half when it is ≥ 64 bits (bit 0);
    - the sum half when it is ≥ 65 bits (bit 1);
    - the **high** half when it is ≥ 64 bits (bit 2).
  - Bits 0 and 1 reproduce the old `SQ_SPLIT_LOW_MIN=64` / `SQ_SPLIT_SUM_MIN=65`
    defaults. Bit 2 is new: `square_b` now splits the 64/65-bit high half one
    level (`tri_square_k2r_flat`), restores `b` at once (`restore_square_sum`),
    and re-forms it in `square_b_inv`.
  - There are now 27 leaves of 32–34 bits, against 21 leaves with a 64-bit one
    before. That means fewer Toffoli, but one more retained cross word is live
    during the folds.
- **S6 `SQ_FIT_CROSS=1` and `width_composition.rs`** (new, 193 lines).
  - When the cross-term add `product[lo..] += 2ab` in `add_cross` has more
    carries than the room left, `direct_plan(n, room)` chunks it into an exact
    direct mapped add. Chunk `j` uses at most `room − j` work wires, and the
    zero `cross[0]` serves as the carry-in.
  - Each boundary carry is erased with `hmr` plus a conditional exact
    full-chunk `mapped_compare`.
  - By the room arithmetic, this is reached only at the three root nodes.
- **S9 `SQ_DEFER_CROSS_PHASE=1`.**
  - In that fitted forward add, the boundary outcomes are kept as classical
    bits in `K2Retained.cross_phase` instead of running the compare.
  - The inverse assembly reuses the same plan, recreates the same carries, and
    applies `z_if` before its own normal erase.
  - This saves the forward compares.
- **S1 `SQ_DIAG_PRELOAD=1`.** `diag_preload` copies the low half of the
  diagonal (`x_j → product[2j+1]` for `j < m/2`) into the still-zero product
  with CX before the rows run. The comment explains why this is safe: the rows
  leave `2^m − 1` of headroom. `diag_spread` then only adds the upper half.
- **S2 `SQ_ROW0_CARRY=1`.** With the preload, forward row 0's first carry is
  just `x[1]`, so it is a CX copy (`Carry0::IsAddend0`) instead of a CCX.
- **S3 `SQ_ROW0_INVERSE_CARRIES=1`.**
  - When row 0 is undone, the product holds only the known preload pattern.
    So every output bit of that subtraction is a known XOR expression.
  - `row0_inverse_known` passes these to `modular::add_wide_known_output`.
    That routine computes each carry as `addend ⊕ acc ⊕ sum` with CX instead
    of an AND.
- **S4 `SQ_ROW_ALL_MEASURE_TOP=1`.**
  - When inverse row `i` runs, its top bit `product[m+i]` must return to 0.
  - `addsub_wide_known_top` → `terminal_step_known` replaces the terminal CCX
    with `hmr` plus `z_if`/`cz_if` phase repair: "one terminal CCX with one
    extra measurement".
- **S5 `SQ_ZERO_TOP_SUM`, `SQ_ZERO_TOP_SPREAD`, `SQ_ZERO_TOP_CROSS` = 1.** The
  same known-top trick applies to `restore_square_sum` (`t − a = b`), the
  inverse `diag_spread`, and the `cross −= b²` subtract (`2ab < 2^(lo+hi+1)`).
- **S10 `SQ_LEND_ASSEMBLY_ZEROS=1`.** `assembly_loans` lends these wires during
  each cross assembly, then repays them:
  - `product[0]`, cleared with a CX from `x0`;
  - `product[1]`, always 0 in a square;
  - each child's always-zero cross bits.

  That gives the fitted root add about 9 more wires of room.
- **S7 `SQ_LEND_RETAINED_ZEROS=1`, `SQ_ALIAS_PRODUCT_LSB=1`.** During the
  consumer folds, `with_square` lends:
  - every retained cross word's zero bits;
  - `product[0]`. The consumers read `x[0]` in its place, because
    `product[0] = x[0]`.

  The fold adders (`peak_fitted_add`) then get more room and pay for a shorter
  leading chunk compare.
- **S8 `SQ_LEND_RETAINED_ANDS=2`, `SQ_LEND_RETAINED_CROSS2=2`.** These are
  bitmasks over the squares A=1, B=2, C=4, so they apply to square B only, the
  branch with six folds.
  - `cross[1] = a0 ∧ ¬t0` is measured out with `hmr` + `cz_if` and rebuilt
    with one CCX before the inverse.
  - `cross[2] = a0·(1 ⊕ t0 ⊕ t1) ⊕ a1·t0` is erased the same way, with a
    quadratic phase repair, and rebuilt with two CCX.
  - These are paid loans: about 6 wires for about 9 Toffoli.
- **Also new:** `Builder` gains a count-only "model" mode. It is hard-coded off,
  so it is reporting only. `set_phase` now starts each phase's peak at the
  live count.

### 4. Replay cell [A1–A7, R2, P5]

Background: [pingpong-division](../concepts/pingpong-division.md),
[modular-fold](../concepts/modular-fold.md),
[comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).

- **Which route a cell takes:**
  - Divide (`replay_add_halve`): `retained_prebias::try_replay`, else
    `joint_prebias_div`, else the old chunked add + fold + flag compare.
  - Multiply (`replay_double_add`): `joint_lowfold::try_replay`, else chunked
    add + `fold_double_joint` + flag compare.
- **A1 `PP_REUSE_DIV_PARITY=1`** (`fold_halve_reused`). The tape sign is
  swapped into `target[0]` and hosts the halving parity, so no parity wire is
  allocated. A swap restores the sign. Exact.
- **A1/A2 `PP_REUSE_MUL_SELECTORS=1`, `PP_JOINT_MUL_FOLD=1`** (`fold_double_joint`).
  - The `−f/+f/+2f` selectors are formed with three ANDs.
  - After bit 0 is updated, `z0 = s ⊕ v0 ⊕ d ⊕ o`. So the doubling's out wire
    `d` is X-cleared and released for the whole fold, then re-made.
  - The fold is a `width_composition::direct_add` over XOR-selected constant
    bits, so no correction word is materialised. Exact.
- **A3 `PP_JOINT_PREBIAS_DIV=1`** (new `joint_prebias.rs`, 92 lines).
  - The sum's parity is prepared before the add.
  - The add's bit-0 carry is made with one AND and erased by measurement.
  - The upper correction `J = (k·f − g)/2`, with `k = s + p(2o − 1)` and
    `g = s ⊕ p`, is added straight into the halved word.
  - The code says "two selector ANDs replace the old three". Exact.
- **A4 retained final frame** (new `retained_prebias.rs` (85 lines, divide) and
  `joint_lowfold.rs` (103 lines, multiply), enabled by `PP_PREBIAS_RETAIN_BITS=32`,
  `PP_JOINT_GUARD=0` and `PP_JOINT_LOW_BITS=32`).
  - The last chunk of the main add runs through `modular::ripple_add_consume`.
    That routine keeps the top carry frame live while a closure does the fold.
  - `erase_overflow_from_frame` then measures the overflow `o` and repairs its
    phase from the live source top `a`, sum top `s` and carry `c`, using
    `o = a·s ⊕ a ⊕ a·c ⊕ s·c ⊕ c`, with Z/CZ only.
  - This **removes the cell's truncated flag compare** at those sites, about
    `(k − 1)/2` executed Toffoli each. The phase-channel risk of that compare
    goes too.
  - If the fold workspace does not fit beside the live frame, a prefix of the
    last chunk is split off and its carry is erased with an exact compare.
  - A site is used only when the planner's `saving` estimate is positive.
- **A5 the 32-bit low cut.**
  - At retained sites that do not take A7, the fold of `f = 2^32 + 977` is
    split. The 977 part goes into bits 1–31, and the 2^32 part into bits
    32 and up (`split_half` / the `GUARD` branch of `fold_double_joint`).
  - The carry from the low part into bit 32 is dropped. This is a new
    approximation, roughly 2^-22 per site, and it shows up as a **classical**
    error.
- **A6 `PP_RETAIN_REBALANCE=1`.** This moves width from the last chunk into
  earlier non-exact chunks, so the retained last chunk is narrower and needs a
  smaller prefix. Compare widths and seed rules are kept, but boundary
  positions can move.
- **A7 `PP_RETAIN_EXACT_DIV=1`, `PP_RETAIN_EXACT_MUL=1`, `_EXTRA_*=4`.** Where
  at most 4 more prefix wires would make the full fold fit, the site takes the
  larger prefix and runs the full finite-window fold instead of the low cut.
  The author counts 83 divide and 11 multiply such sites.
- **R2 `PP_NEW_REPLAY=1`.** `chunked_add` prices its usual approximate chunk
  layout against an exact `width_composition::plan(N, room)`. That plan erases
  every boundary with a full-chunk compare and may use an in-place last chunk.
  The exact plan is used when it is cheaper.
- **R2 `PP_DIRECT_FOLD=1`, `PP_DIRECT_ENDPOINT=1`, `PP_CF_END_CHUNK=8`.**
  - When the fold's ladder would not fit, `fold_selected_single` runs it as a
    chunked `direct_add`.
  - The endpoint's `conditional_mod_negate` uses `endpoint_sparse_sub`, a
    direct mapped add of `f − 1` that skips its 4 zero low bits.
  - `CF_END_CHUNK=8` only selects that branch.
  - Both are exact apart from the existing top truncation.
- **R2 `PP_Q1208_HELPERS=1`, replay part.** When no chunk layout fits,
  `chunked_add` falls back to an exact in-place MAJ/UMA ripple instead of
  panicking.
- **P5 `CMP_SEED_ALL=1`.**
  - At divide flag compares and at replay boundary compares that were not yet
    seeded, the window shrinks by one bit (`k −= 1`). The bit just below the
    new window becomes the compare's borrow-in predictor
    (`source[N−k−1]` / `addend[phi−compare−1]`).
  - About −0.5 Toffoli per site on average.
  - This is probabilistic: it changes a phase predicate.
  - `compare.rs` gains alias handling for a seed that falls inside a window.
    That is unused here.

### 5. Protection bought back [P1–P4, P6]

These raise Toffoli and lower λ.

- **P1 rounds.** The divide schedule `PP_WIDTH_SCHEDULE` gains `,8x2` (696 →
  698 rounds). `PP_ROUNDS_MUL` goes 694 → 698. More rounds make it less likely
  that a slow input has not reached its fixed point.
- **P2 `PP_WALK_GUARD_BITS=1`, `PP_WALK_GUARD_MAX_WIDTH=64`.**
  - `value_width(round)` is now the physical walk width. It adds one bit
    wherever the schedule width is ≤ 64 (rounds 550–697), saturating at 65.
    The last rounds become 9 bits wide.
  - The new `policy_width(round)` returns the raw schedule. Fold profiles,
    compare shapes and seed rules now use it, so the guard bit does not shift
    them.
- **P3 `FOLD_GUARD`: 21 → 24.** `f_slice()` grows from 54 to 57 bits in every
  constant fold outside the replay windows: the coordinate shell, the square
  folds and `window_add`, the replay rounds 0/1, and the endpoint.
  `ERASE_COMPARE` stays 22.
- **P4 `PP_REPLAY_FOLD_WINDOW` (divide): 53 → 54.** The multiply base stays 54.
- **P6 `PP_FLAG_SHAPE`: `38:0,25:-2,0:-4` → `38:0,25:-2,0:-2`.** Flag compares
  at policy width < 25 grow from 16 to 18 bits.

### 6. Tail nonce and housekeeping

- `TAIL_NONCE` goes 2886213855485 → 7978492.
- The five `*_tests.rs` files from `a39e07e` are deleted, along with the
  `#[cfg(test)] mod tests;` lines in the four simplifier files.
- Most of the non-ASCII comments in `pingpong.rs` were re-encoded (for example
  `—` became `â€”`). This is diff noise only.

**Author's totals.** Research-cohort mean Toffoli went from 903,434.197 to
897,595.037 (−5,839.2). Emitted Toffoli went from 945,526 to 936,168. Peak
went from 1259 to 1251.

## Why it is still correct, and what it risks

- **Exact.** These hold on every input:
  - every square lever (S1–S10);
  - the walk deferral and loans (W1–W3);
  - the replay reuses (A1–A3);
  - the frame erase (A4);
  - the exact helpers (R2) and the reordered middle batches.
  The cap move itself is exact, though new chunk boundaries can bring their
  own truncated repairs.
- **Probabilistic, raises λ:**
  - the 32-bit low cut at retained sites (A5, classical channel);
  - the shorter seeded compares (P5, phase channel);
  - moved boundary endpoints (A6, phase channel);
  - narrower layouts under the lower cap.
- **Probabilistic, lowers λ:** P1–P4 and P6. A dropped fold carry or a walk
  overflow is a classical failure. A wrong compare is a phase failure.
- **Measured λ.** Over 40 paired draws of 9,024 shots, the author counts 588
  classical, 395 phase, 277 overlapping, 706 failing shots in total, and 0
  dirty ancillas. That is λ = 17.65, +0.70 over their previous intermediate
  build.
- The shipped nonce draws a clean set: 9,024 of 9,024 shots, with 0
  classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).
- **The contract.** The note asks later builders to keep λ ≤ 18, not to trade
  error for score directly, and to copy the note forward. The dysnasia
  follow-ups [`f812a29`](f812a29.md), [`b788efc`](b788efc.md),
  [`291d749`](291d749.md) and [`0a06121`](0a06121.md) all price their changes
  against it.

## Classification rationale

No single lever dominates. The qubit drop (−0.64% of score) and the Toffoli
drop (−0.65%) are about equal.

The coherent theme is the 8-qubit cap drop, made possible by lending wires
whose values are known: zero cross bits, sign copies, the duplicate product
bit 0, and the bits that can be measured out and rebuilt. That theme is
scratch/ancilla reuse.

The runner-up is Uncompute Strategy → measurement uncompute, for the many
CCX-to-measurement swaps in the square. Treat this as a multi-family
composite.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a39e07e -- src/point_add`.
   - The author's note names "HEAD" as Q1259 with 903,434.197 mean Toffoli,
     which is `a39e07e`.
   - Against `a39e07e` the diff is 7,531 lines. 2,717 of them only delete the
     five test files, and the other 4,814 are the change described above.
   - `data/bases.tsv` picks `e50a36f` (Rossnkama) because its raw diff is
     smaller: 6,196 lines, since `e50a36f` predates those test files. But that
     diff would credit this commit with all of `a39e07e`'s work: the four
     simplifier passes, `PP_CUT_WALKLOAN`, `PP_CUT_SQIDENT`, the A5 seeds and
     `PP_FLAG_WIDEN_DIV`.
   - Do not start from the git parent `9700396` (jackylee0424) either. Against
     it the diff is also 7,531 lines, and it would show this commit reverting
     jackylee's changes: the cap of 1258, the fold profile
     `38:0,32:-2,19:-5,0:-5`, and the A5 seeds on every round (`>= 0`).
2. **Copy `pingpong.rs` from the commit:**
   `git checkout cc7f10e -- src/point_add/pingpong.rs`.
   - It is hand-written, not generated. It is copied because its diff is about
     2,700 lines.
   - That diff includes the inactive mod-4/depth/C2 machinery and the comment
     re-encoding.
   - The active parts are described in sections 1, 2, 4 and 5.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It covers every other file. It deletes the five test files and
   adds the six new small files.
4. **Check the tree.** `git diff --ignore-cr-at-eol cc7f10e -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. From this commit
   on, every knob is read from the fixed `env_raw` table, so `SUB4_*`,
   `TLM_*`, `PP_*`, `HEO_*` or `A5_REPAIR` variables have no effect. Expect:
   - 1251 qubits
   - 897,597 average Toffoli (897,596.816 before rounding)
   - score 1,122,893,847
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `7978492` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

Delete these files first:

```sh
rm src/point_add/a2_square_tests.rs \
   src/point_add/affine_simplify_tests.rs \
   src/point_add/product_simplify_tests.rs \
   src/point_add/quadratic_simplify_tests.rs \
   src/point_add/truth_simplify_tests.rs
```

```diff
diff --git a/src/point_add/affine_simplify.rs b/src/point_add/affine_simplify.rs
index 94e2a73..acdef68 100644
--- a/src/point_add/affine_simplify.rs
+++ b/src/point_add/affine_simplify.rs
@@ -286,6 +286,3 @@ pub(crate) fn simplify(ops: Vec<Op>) -> Vec<Op> {
     result
 }
 
-#[cfg(test)]
-#[path = "affine_simplify_tests.rs"]
-mod tests;
diff --git a/src/point_add/builder.rs b/src/point_add/builder.rs
index 67d4e7b..9915f5d 100644
--- a/src/point_add/builder.rs
+++ b/src/point_add/builder.rs
@@ -15,6 +15,13 @@ const OP_KINDS: usize = OperationType::DebugPrint as usize + 1;
 
 pub struct Builder {
     ops: Vec<Op>,
+    model: bool,
+    model_depth: usize,
+    model_total: usize,
+    model_weighted: f64,
+    model_phase_native: usize,
+    model_phase_weighted: f64,
+    model_max: u32,
     /// Ops of each kind emitted since the last [`Builder::set_phase`]; only the
     /// two Toffoli kinds are reported, but indexing by `kind` is cheaper than
     /// branching on it.
@@ -36,6 +43,9 @@ impl Builder {
     pub fn new() -> Self {
         Self {
             ops: Vec::new(),
+            model: false, // Always emit operations; no count-only research mode.
+            model_depth: 0, model_total: 0, model_weighted: 0.0,
+            model_phase_native: 0, model_phase_weighted: 0.0, model_max: 0,
             phase_kind_ops: [0; OP_KINDS],
             next_qubit: 0,
             next_bit: 0,
@@ -51,6 +61,11 @@ impl Builder {
         }
     }
     pub fn take_ops(&mut self) -> Vec<Op> {
+        if self.model {
+            eprintln!("MODEL_PHASE {} {} {} {}", self.phase, self.peak_qubits,
+                self.model_phase_native, self.model_phase_weighted);
+            eprintln!("MODEL_TOTAL {} {} {}", self.model_max, self.model_total, self.model_weighted);
+        }
         std::mem::take(&mut self.ops)
     }
     fn push_op(&mut self, op: Op) {
@@ -66,12 +81,27 @@ impl Builder {
             );
         }
         self.phase_kind_ops[op.kind as usize] += 1;
-        self.ops.push(op);
+        if self.model {
+            match op.kind {
+                OperationType::PushCondition => self.model_depth += 1,
+                OperationType::PopCondition => self.model_depth -= 1,
+                OperationType::CCX | OperationType::CCZ => {
+                    let weight = 2.0_f64.powi(-(self.model_depth as i32));
+                    self.model_total += 1; self.model_weighted += weight;
+                    self.model_phase_native += 1; self.model_phase_weighted += weight;
+                }, _ => {}
+            }
+        } else { self.ops.push(op); }
     }
     /// Close the current phase: report its Toffoli count and peak width on
     /// stdout -- which is what `build_circuit` prints -- and start a new one.
     pub fn set_phase(&mut self, p: &'static str) {
-        self.peak_qubits = 0;
+        if self.model {
+            eprintln!("MODEL_PHASE {} {} {} {}", self.phase, self.peak_qubits,
+                self.model_phase_native, self.model_phase_weighted);
+        }
+        self.model_phase_native = 0; self.model_phase_weighted = 0.0;
+        self.peak_qubits = self.active_qubits;
         self.phase_kind_ops = [0; OP_KINDS];
         self.phase = p;
     }
@@ -94,6 +124,7 @@ impl Builder {
     /// `active_qubits`: a fresh `alloc_qubit` and a `reacquire` of a parked one.
     fn note_peak(&mut self) {
         self.peak_qubits = self.peak_qubits.max(self.active_qubits);
+        self.model_max = self.model_max.max(self.active_qubits);
     }
 
     #[track_caller]
diff --git a/src/point_add/compact_chunk_add.rs b/src/point_add/compact_chunk_add.rs
new file mode 100644
index 0000000..58ad7ec
--- /dev/null
+++ b/src/point_add/compact_chunk_add.rs
@@ -0,0 +1,34 @@
+//! Exact wrapped addition with measured block-carry erasure. No truncated
+//! comparison: each outgoing carry is reconstructed from every post-sum bit,
+//! the entire source block, and the still-live incoming carry.
+use super::{Builder,modular,compare};
+use crate::circuit::QubitId;
+
+fn and_phase(c:&mut Builder,bits:&[QubitId]){
+    assert!(bits.len()>=2);if bits.len()==2{c.cz(bits[0],bits[1]);return;}
+    let work=c.alloc_qubits(bits.len()-2);c.ccx(bits[0],bits[1],work[0]);
+    for i in 1..work.len(){c.ccx(work[i-1],bits[i+1],work[i]);}c.cz(work[work.len()-1],bits[bits.len()-1]);
+    for i in(0..work.len()).rev(){let m=c.alloc_bit();c.hmr(work[i],m);let a=if i==0{bits[0]}else{work[i-1]};c.cz_if(a,bits[i+1],m);c.free_bit(m);c.release_clean(work[i]);}
+}
+fn erase(c:&mut Builder,flag:QubitId,source:&[QubitId],sum:&[QubitId],incoming:Option<QubitId>){
+    if !source.is_empty()&&sum.len()>1{assert_eq!(source.len(),sum.len());compare::erase_with_compare(c,flag,sum,source,incoming);return;}
+    let m=c.alloc_bit();c.hmr(flag,m);c.push_condition(m);c.x_all(sum);
+    if source.is_empty(){let mut controls=sum.to_vec();controls.push(incoming.expect("zero source block has incoming carry"));and_phase(c,&controls);}
+    else{assert_eq!(sum.len(),1);c.cz(source[0],sum[0]);if let Some(q)=incoming{c.cz(source[0],q);c.cz(sum[0],q);}}
+    c.x_all(sum);c.pop_condition();c.free_bit(m);
+}
+pub(crate) fn add(c:&mut Builder,a:&[QubitId],b:&[QubitId],incoming:Option<QubitId>,negative:bool,chunk:usize){
+    assert!(!a.is_empty()&&a.len()<=b.len()&&chunk>=1);if negative{c.x_all(b);}
+    if b.len()<=chunk{modular::ripple_add(c,a,b,incoming,None);if negative{c.x_all(b);}return;}
+    // End a source block exactly at a.len(); no repeated zero aliases enter a
+    // comparison. Above it, one clean zero is reused by the native ripple.
+    let zero=if a.len()<b.len(){Some(c.alloc_qubit())}else{None};let mut stages=Vec::new();let mut at=0;let mut previous=incoming;
+    while at<b.len(){let end=(at+chunk).min(if at<a.len(){a.len()}else{b.len()});let flag=if end<b.len(){Some(c.alloc_qubit())}else{None};
+        let zeros:Vec<_>=zero.into_iter().collect();let source=if at<a.len(){&a[at..end]}else{&zeros};modular::ripple_add(c,source,&b[at..end],previous,flag);
+        if let Some(q)=flag{stages.push((at,end,previous,q));}previous=flag;at=end;
+    }
+    // Descending order preserves each incoming boundary until its successor's
+    // measurement phase is repaired. Then its own exact predicate is erased.
+    for(at,end,prev,q)in stages.into_iter().rev(){let source=if at<a.len(){&a[at..end]}else{&[]};erase(c,q,source,&b[at..end],prev);c.release_clean(q);}
+    if let Some(q)=zero{c.release_clean(q);}if negative{c.x_all(b);}
+}
diff --git a/src/point_add/compact_mapped_add.rs b/src/point_add/compact_mapped_add.rs
new file mode 100644
index 0000000..e550aea
--- /dev/null
+++ b/src/point_add/compact_mapped_add.rs
@@ -0,0 +1,19 @@
+//! A sparse or repeated-bit source is materialized one clean block at a time.
+//! The source mapping is read-only. A copied source block and a native carry
+//! ladder are both charged; boundaries remain live until exact phase repair.
+use super::{Builder,modular,compare};
+use crate::circuit::QubitId;
+pub(crate) type SourceBit=(Option<QubitId>,bool);
+fn copy(c:&mut Builder,map:&[SourceBit],buffer:&[QubitId]){for(i,&q)in buffer.iter().enumerate(){if let Some(&(src,one))=map.get(i){if let Some(s)=src{c.cx(s,q);}if one{c.x(q);}}}}
+fn erase(c:&mut Builder,flag:QubitId,source:&[QubitId],sum:&[QubitId],incoming:Option<QubitId>){
+    if sum.len()>1{compare::erase_with_compare(c,flag,sum,source,incoming);return;}
+    let m=c.alloc_bit();c.hmr(flag,m);c.push_condition(m);c.x(sum[0]);c.cz(source[0],sum[0]);if let Some(q)=incoming{c.cz(source[0],q);c.cz(sum[0],q);}c.x(sum[0]);c.pop_condition();c.free_bit(m);
+}
+pub(crate) fn add(c:&mut Builder,map:&[SourceBit],b:&[QubitId],negative:bool,chunk:usize){
+    assert!(!map.is_empty()&&map.len()<=b.len()&&chunk>=1);if negative{c.x_all(b);}let buffer=c.alloc_qubits(chunk.min(b.len()));let mut stages=Vec::new();let mut at=0;let mut previous=None;
+    while at<b.len(){let end=(at+chunk).min(b.len());let src=if at<map.len(){&map[at..end.min(map.len())]}else{&[]};let tmp=&buffer[..end-at];copy(c,src,tmp);let flag=if end<b.len(){Some(c.alloc_qubit())}else{None};modular::ripple_add(c,tmp,&b[at..end],previous,flag);copy(c,src,tmp);
+        if let Some(q)=flag{stages.push((at,end,previous,q));}previous=flag;at=end;
+    }
+    for(at,end,prev,q)in stages.into_iter().rev(){let src=if at<map.len(){&map[at..end.min(map.len())]}else{&[]};let tmp=&buffer[..end-at];copy(c,src,tmp);erase(c,q,tmp,&b[at..end],prev);copy(c,src,tmp);c.release_clean(q);}
+    for q in buffer{c.release_clean(q);}if negative{c.x_all(b);}
+}
diff --git a/src/point_add/compare.rs b/src/point_add/compare.rs
index 4b633c6..4a92be7 100644
--- a/src/point_add/compare.rs
+++ b/src/point_add/compare.rs
@@ -16,7 +16,7 @@ use crate::circuit::QubitId;
 /// starts clean, and after the first CX `u[0]` already holds what a clean
 /// carry-in wire would have held — so it serves as the first nonlinear control
 /// and no wire is needed either way.
-fn cmp_lt_phase(circ: &mut Builder, u: &[QubitId], v: &[QubitId], borrow_in: Option<QubitId>) {
+pub(crate) fn cmp_lt_phase(circ: &mut Builder, u: &[QubitId], v: &[QubitId], borrow_in: Option<QubitId>) {
     let n = u.len();
     assert_eq!(v.len(), n);
     // Two bits is the narrowest comparison any caller asks for: the walk's
@@ -24,6 +24,17 @@ fn cmp_lt_phase(circ: &mut Builder, u: &[QubitId], v: &[QubitId], borrow_in: Opt
     // `walk_low_chunk` only splits when `low >= 4`, which leaves it `low - 2`
     // bits wide.
     assert!(n > 1);
+    // A source-bit predictor may now lie inside a widened comparison window.
+    // If it is the first source bit, MAJ(!u0,v0,v0)=v0: that whole position
+    // is redundant. Otherwise restore the predictor before its operand bit
+    // is read, and recreate the first control only for the final phase erase.
+    // No separate predictor copy or extra nonlinear gate is necessary.
+    if borrow_in==Some(v[0]) {
+        assert!(n>=3,"aliased low seed needs at least two remaining comparison bits");
+        return cmp_lt_phase(circ,&u[1..],&v[1..],borrow_in);
+    }
+    let operand_seed=borrow_in.is_some_and(|q|v[1..].contains(&q));
+    assert!(!borrow_in.is_some_and(|q|u.contains(&q)),"seed cannot alias the accumulator");
     let last = n - 1;
 
     let carries = circ.alloc_qubits(last);
@@ -36,6 +47,7 @@ fn cmp_lt_phase(circ: &mut Builder, u: &[QubitId], v: &[QubitId], borrow_in: Opt
         p
     });
     circ.ccx(first_ctrl, v[0], carries[0]);
+    if operand_seed {circ.cx(u[0],borrow_in.unwrap());}
     circ.cx(carries[0], u[0]);
     for i in 1..last {
         circ.cx(u[i], v[i]);
@@ -64,6 +76,7 @@ fn cmp_lt_phase(circ: &mut Builder, u: &[QubitId], v: &[QubitId], borrow_in: Opt
     circ.hmr(carries[0], m0);
     match borrow_in {
         Some(p) => {
+            if operand_seed {circ.cx(u[0],p);}
             circ.cz_if(p, v[0], m0);
             circ.cx(u[0], p);
         }
diff --git a/src/point_add/joint_lowfold.rs b/src/point_add/joint_lowfold.rs
new file mode 100644
index 0000000..e28f5c3
--- /dev/null
+++ b/src/point_add/joint_lowfold.rs
@@ -0,0 +1,103 @@
+//! Joint retained-final-carry / overlapping low-constant fold experiment.
+//! It preserves the original B comparisons, exactly erases the inserted
+//! prefix boundary and final overflow, and explicitly changes the low fold.
+use super::*;
+thread_local! { pub(super) static GUARD:std::cell::Cell<Option<usize>>=const{std::cell::Cell::new(None)}; }
+
+fn low_bits(guard:usize)->usize { super::super::optional_env::<usize>("PP_JOINT_LOW_BITS").unwrap_or(32+guard) }
+
+#[derive(Debug)]
+struct Plan { bounds:Vec<(usize,usize)>, prefix:usize, guard:usize, bits:usize, saving:f64, exact:bool }
+
+fn plan(circ:&Builder,round:usize,multiply:bool,fw:usize)->Option<Plan> {
+    if !multiply && env_raw("PP_PREBIAS_RETAIN_BITS").is_some() {return None;}
+    let guard=super::super::optional_env::<usize>("PP_JOINT_GUARD")?;
+    let low=if env_flag("PP_SPRINT_MIXED") && multiply && (364..=402).contains(&round) {29}else{low_bits(guard)};assert!((12..=fw).contains(&low) && !split_fold());
+
+    assert!(env_flag("PP_REUSE_DIV_PARITY") && env_flag("PP_REUSE_MUL_SELECTORS"));
+    let room=walk_max_qubits().saturating_sub(circ.active_qubits()as usize);
+    let loans=REPLAY_SIGN_LOANS.with(|s|s.get());
+    let old_bounds=composition_bounds(circ,round,multiply)?;
+    let bounds=retained_rebalance(circ,&old_bounds,round,multiply);
+    if bounds.len()<2 {return None;}
+    let &(lo,hi)=bounds.last()?;
+    let (plo,phi)=bounds[bounds.len()-2];
+    let (k,seeded)=boundary_repair_spec(round,multiply,plo,phi);
+    if lo<fw || phi-k-usize::from(seeded)<fw {return None;}
+    let need=(low-3).max(fw-34);
+    let existing=walk_max_qubits()as isize-circ.active_qubits()as isize-(hi-lo)as isize-if multiply&&env_flag("PP_JOINT_MUL_FOLD"){3}else{4};
+    let missing=(need as isize-existing).max(0)as usize;
+    let prefix=if missing==0 {0} else {missing+1};
+    if prefix+1>=hi-lo {return None;}
+    let mut fk=if multiply {flag_compare(round)+usize::from(a5_policy()=="mul-f-plus1-early200"&&(2..202).contains(&round))}
+        else {flag_compare(round)+usize::from(policy_width(round)>=flag_widen_div())};
+    let seeded=if multiply {policy_width(round)>=38 && matches!(a5_policy(),"mul-f-seed"|"mul-fb-seed")}else{env_flag("CMP_SEED_ALL")};
+    if !multiply && seeded {fk-=1;}
+    if !seeded {fk=refined_unseeded_width(fk,N,"PP_REFINE_UNSEEDED_F");}
+    let saving=(fk-1)as f64/2.0-missing as f64/2.0-(low as f64-33.0);
+    if saving<=0.0 {return None;}
+    // Release a bounded additional carry prefix to fit the full finite fold.
+    // Outer B comparisons are unchanged; the inserted midpoint uses exact cleanup.
+    let limit=super::super::optional_env::<usize>("PP_RETAIN_EXACT_EXTRA_MUL").unwrap_or(0);
+    let exact_missing=((fw-3) as isize-existing).max(0) as usize;
+    let exact_prefix=if exact_missing==0 {0}else{exact_missing+1};
+    let exact=multiply && env_flag("PP_RETAIN_EXACT_MUL") && exact_missing<=limit && exact_prefix+1<hi-lo;
+    let prefix=if exact {exact_prefix}else{prefix};
+    let saving=if exact {saving-(exact_missing-missing) as f64/2.0-1.0}else{saving};
+    Some(Plan{bounds,prefix,guard,bits:low,saving,exact})
+}
+
+pub(super) fn try_replay(circ:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId],fw:usize,
+    round:usize,doubled:Option<QubitId>)->bool {
+    let multiply=doubled.is_some();
+    let Some(p)=plan(circ,round,multiply,fw)else{return false;};
+    eprintln!("JOINT_LOWFOLD r={} mul={} base={} last={} prefix={} guard={} saving={}",round,multiply as u8,
+        circ.active_qubits(),p.bounds.last().unwrap().1-p.bounds.last().unwrap().0,p.prefix,p.guard,p.saving);
+    if env_flag("PP_COMPOSE_TRACE"){eprintln!("COMPOSE_MUL {} {} {} {} {} {:?}",round,circ.active_qubits(),fw,p.bits,REPLAY_SIGN_LOANS.with(|s|s.get()),p.bounds);}
+    if p.exact {eprintln!("EXACT_RETAINED_FOLD mul {} {}",round,fw);}
+    let mut incoming=None;
+    let mut previous=None;
+    for &(lo,hi)in &p.bounds {
+        let next=circ.alloc_qubit();
+        if hi==N {
+            let split=lo+p.prefix;
+            let mid=if p.prefix==0 {incoming}else{
+                let m=circ.alloc_qubit();ripple_add(circ,&a[lo..split],&b[lo..split],incoming,Some(m));Some(m)
+            };
+            super::super::modular::ripple_add_consume(circ,&a[split..hi],&b[split..hi],mid,next,
+                |c,o,at,st,carry|{
+                    GUARD.with(|g|{assert!(g.replace(if p.exact {None}else{Some(p.bits)}).is_none());});
+                    if let Some(d)=doubled {
+                        if env_flag("PP_JOINT_MUL_FOLD"){fold_double_joint(c,&b[..fw],sign,a[0],d,o);}else{fold_double_reused(c,&b[..fw],sign,d,o);}
+                        c.cx(b[0],d);c.cx(sign,d);c.cx(a[0],d);c.cx(o,d);c.free(d);
+                    }else{fold_halve_reused(c,&b[..fw],sign,o);}
+                    GUARD.with(|g|g.set(None));
+                    super::super::modular::erase_overflow_from_frame(c,o,at,st,carry);
+                });
+            if p.prefix>0 {
+                let mid=mid.unwrap();
+                // Exact: carry(a+b+incoming) = [sum<a]+[sum=a]*incoming.
+                erase_with_compare(circ,mid,&b[lo..split],&a[lo..split],incoming);circ.free(mid);
+            }
+        }else{ripple_add(circ,&a[lo..hi],&b[lo..hi],incoming,Some(next));}
+        if let Some((q,plo,phi))=previous {
+            let(k,seeded)=boundary_repair_spec(round,multiply,plo,phi);
+            circ.record_replay_site('B',round,phi,k);
+            erase_with_compare(circ,q,&b[phi-k..phi],&a[phi-k..phi],seeded.then(||a[phi-k-1]));circ.free(q);
+        }
+        incoming=Some(next);previous=Some((next,lo,hi));
+    }
+    true
+}
+
+pub(super) fn fold(circ:&mut Builder,acc:&[QubitId],f:U256,plus:QubitId,twice:Option<QubitId>,minus:QubitId,first:QubitId,g:usize) {
+    assert_eq!(f>>32usize,U256::from(1));let low=g;assert!(low<=acc.len());
+    let small=f&((U256::from(1)<<32usize)-U256::from(1));
+    fold_selected_single(circ,&acc[..low],small,plus,twice,minus,first);
+    let boundary=circ.alloc_qubit();
+    with_selector_xor(circ,&[plus,minus],plus,|c,q|c.ccx(acc[32],q,boundary));
+    fold_selected_single(circ,&acc[32..],U256::from(1),plus,twice,minus,boundary);
+    with_selector_xor(circ,&[plus,minus],plus,|c,q|{
+        c.cx(q,acc[32]);and_uncompute(c,boundary,acc[32],q);c.cx(q,acc[32]);
+    });
+}
diff --git a/src/point_add/joint_prebias.rs b/src/point_add/joint_prebias.rs
new file mode 100644
index 0000000..5d963b7
--- /dev/null
+++ b/src/point_add/joint_prebias.rs
@@ -0,0 +1,92 @@
+//! Experimental finite-map variant. It creates a new precision boundary,
+//! and its outer B/F comparison debts must be qualified independently.
+use super::*;
+
+pub(super) fn initial_carry(c:&mut Builder,a:QubitId,p:QubitId,s:QubitId)->QubitId {
+    c.cx(s,a);c.x(a);let q=and_clean(c,p,a);c.x(a);c.cx(s,a);c.cx(a,q);q
+}
+pub(super) fn erase_initial(c:&mut Builder,q:QubitId,a:QubitId,p:QubitId,s:QubitId) {
+    let m=c.alloc_bit();c.hmr(q,m);
+    c.z_if(a,m);c.z_if(p,m);c.cz_if(p,a,m);c.cz_if(p,s,m);
+    c.free_bit(m);c.free(q);
+}
+
+/// Direct selector-mapped wrapped addition with initial carry exactly zero.
+/// This is the same ripple as direct_add, with its first carry specialized.
+pub(super) fn mapped_zero(c:&mut Builder,acc:&[QubitId],map:&[Vec<QubitId>]) {
+    let n=acc.len();assert!(n>=3);assert_eq!(map.len(),n);
+    assert!(!map[0].is_empty());
+    let room=walk_max_qubits().saturating_sub(c.active_qubits()as usize);
+    if n-2>room {
+        let first=c.alloc_qubit();
+        with_selector_xor(c,&map[0],acc[0],|c,src|{c.ccx(src,acc[0],first);c.cx(src,acc[0]);});
+        let room=walk_max_qubits().saturating_sub(c.active_qubits()as usize);
+        let plan=super::super::width_composition::direct_plan(n-1,room).expect("prebias bounded fold");
+        super::super::width_composition::direct_add(c,&map[1..],&acc[1..],first,&plan);
+        with_selector_xor(c,&map[0],acc[0],|c,src|{let m=c.alloc_bit();c.hmr(first,m);c.z_if(src,m);c.cz_if(src,acc[0],m);c.free_bit(m);});
+        c.free(first);return;
+    }
+    let carries=c.alloc_qubits(n-2);
+    with_selector_xor(c,&map[0],acc[0],|c,src|c.ccx(src,acc[0],carries[0]));
+    for i in 1..n-2 {fold_step(c,acc[i],carries[i-1],carries[i],&map[i],false);}
+    fold_step(c,acc[n-2],carries[n-3],acc[n-1],&map[n-2],true);
+    for &s in &map[n-1]{c.cx(s,acc[n-1]);}
+    for i in (1..n-2).rev(){unwind_fold_step(c,acc[i],carries[i-1],carries[i],&map[i]);}
+    with_selector_xor(c,&map[0],acc[0],|c,src| {
+        let m=c.alloc_bit();c.hmr(carries[0],m);c.cz_if(src,acc[0],m);c.free_bit(m);c.cx(src,acc[0]);
+    });
+    c.free_vec(&carries);
+}
+
+/// Add J=(k*f-g)/2 to the upper word, k=s+p*(2o-1), g=s XOR p.
+/// Original p,s,o survive; two selector ANDs replace the old three.
+pub(super) fn half_fold(c:&mut Builder,upper:&[QubitId],p:QubitId,s:QubitId,o:QubitId) {
+    c.cx(s,o);c.x(o);let q=and_clean(c,p,o);c.x(o);c.cx(s,o);
+    c.x(s);let minus=and_clean(c,q,s);c.x(s);
+    c.cx(minus,q); // q hosts plus_2f
+    c.cx(s,p);c.cx(minus,p); // p hosts plus_f
+    let fp=(f()-U256::from(1))>>1usize;
+    let fm=U256::ZERO.wrapping_sub((f()+U256::from(1))>>1usize);
+    let mut map=Vec::new();
+    for i in 0..upper.len(){let mut row=Vec::new();if fp.bit(i){row.push(p);}if f().bit(i){row.push(q);}if fm.bit(i){row.push(minus);}map.push(row);}
+    mapped_zero(c,upper,&map);
+    c.cx(minus,p);c.cx(s,p);c.cx(minus,q);
+    c.x(s);and_uncompute(c,minus,q,s);c.x(s);
+    c.cx(s,o);c.x(o);and_uncompute(c,q,p,o);c.x(o);c.cx(s,o);
+}
+
+pub(super) fn eligible(c:&Builder,round:usize)->bool {composition_bounds(c,round,false).is_some()}
+
+pub(super) fn joint_prebias_div(c:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId],fw:usize,round:usize) {
+    assert!(!split_fold()&&env_raw("PP_PIN_REPLAY_LAYOUT").is_none());
+    assert_eq!(a.len(),N);assert_eq!(b.len(),N);
+    let bounds=composition_bounds(c,round,false).expect("eligible I03 prebias receiver");
+    if env_flag("PP_COMPOSE_TRACE"){eprintln!("COMPOSE_PREBIAS {} {} {} {} {:?}",round,c.active_qubits(),fw,REPLAY_SIGN_LOANS.with(|s|s.get()),bounds);}
+    c.swap(sign,b[0]);c.cx(a[0],sign);c.cx(b[0],sign); // sign=p, b0=s
+    c.cx_all(b[0],&b[1..]);
+    let initial=initial_carry(c,a[0],sign,b[0]);
+    let mut cin=Some(initial);let mut previous:Option<(QubitId,usize,usize)>=None;
+    for (j,&(lo,hi)) in bounds.iter().enumerate(){
+        let out=c.alloc_qubit();let at=if j==0{1}else{lo};
+        ripple_add(c,&a[at..hi],&b[at..hi],cin,Some(out));
+        if j==0 {erase_initial(c,initial,a[0],sign,b[0]);}
+        if let Some((carry,plo,phi))=previous {
+            let(k,seeded)=boundary_repair_spec(round,false,plo,phi);
+            c.record_replay_site('B',round,phi,k);let w=phi-k..phi;
+            let full_first=plo==0 && phi==k;
+            if full_first {c.cx(b[0],sign);} // parity host temporarily holds g
+            let borrow=if full_first {Some(sign)}else{seeded.then(||a[phi-k-1])};
+            erase_with_compare(c,carry,&b[w.clone()],&a[w],borrow);c.free(carry);
+            if full_first {c.cx(b[0],sign);}
+        }
+        cin=Some(out);previous=Some((out,lo,hi));
+    }
+    let o=cin.unwrap();half_fold(c,&b[1..fw],sign,b[0],o);
+    c.swap(sign,b[0]);c.cx(o,b[0]); // original sign restored; b0=p XOR o
+    let mut k=flag_compare(round)+usize::from(policy_width(round)>=flag_widen_div());
+    let borrow=if env_flag("CMP_SEED_ALL"){k-=1;Some(a[N-k-1])}else{None};
+    if borrow.is_none(){k=refined_unseeded_width(k,N,"PP_REFINE_UNSEEDED_F");}
+    c.record_replay_site('F',round,N,k);erase_with_compare(c,o,&b[N-k..],&a[N-k..],borrow);c.free(o);
+    c.cx_all(sign,b);rotate_down(c,b);
+}
+
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 2002114..7bd64d7 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1,3 +1,6 @@
+mod width_composition;
+mod compact_mapped_add;
+mod compact_chunk_add;
 use std::str::FromStr;
 
 use alloy_primitives::U256;
@@ -29,90 +32,95 @@ const SECP256K1_P: U256 = U256::from_limbs([
     0xFFFF_FFFF_FFFF_FFFF,
 ]);
 
-/// Pin a tuning knob, unless the environment already overrides it.
-///
-/// **The single-line call shape is load-bearing.** `src/bin/grind` `include_str!`s
-/// this file and text-searches it for the literal needle
-/// `set_default_env("NAME", ` to recover a pinned value, because the grinder's
-/// model has to track the circuit's tuning and must not keep its own copy.
-/// Seven knobs are read that way today: `PP_ROUNDS_MUL`, `FOLD_GUARD`, both
-/// `PP_REPLAY_FOLD_WINDOW*`, `PP_FOLD_WIDEN`, `PP_FOLD_PROFILE` and
-/// `PP_WIDTH_SCHEDULE` -- the last two as string literals, the schedule as a
-/// `concat!` of them. So a pin's value must stay a literal right here in the
-/// call: routing it through a constant, a table or a helper compiles fine and
-/// makes the grinder panic at startup -- or, worse, screen against tuning the
-/// circuit no longer has. (It used to route the schedule and the band tables
-/// through `pub const DEFAULT_*` in `pingpong.rs`, which is exactly the shape
-/// that needed a second scraper and a second file.)
-///
-/// The `unsafe` is required from edition 2024 on, where `set_var` is an
-/// `unsafe fn`; this crate is on 2021, where it is merely allowed.
-fn set_default_env(name: &str, value: &str) {
-    if env_raw(name).is_none() {
-        unsafe {
-            std::env::set_var(name, value);
-        }
-    }
-}
-
-/// Defines a memoised `usize` accessor for a tuning knob that [`build`] pins.
-///
-/// The knob is read once through [`required_env`] and cached, so every consumer
-/// sees one value and the environment is not walked per call site. That reader
-/// deliberately has no fallback, so a dropped pin panics rather than silently
-/// emitting a different circuit.
-///
-/// Every knob that reaches a construction as a width in bits goes through here;
-/// ten do. The five that do not are the ones that are not a width: the tail
-/// nonce, read in [`build`], and the four strings, each read once behind its own
-/// `OnceLock` in `pingpong` -- the width schedule, and the three `width:offset`
-/// band tables (`PP_FOLD_PROFILE`, `PP_CHUNK_SHAPE`,
-/// `PP_FLAG_SHAPE`).
-macro_rules! pinned_env {
-    ($vis:vis $name:ident, $env:literal) => {
-        $vis fn $name() -> usize {
-            static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
-            *SLOT.get_or_init(|| $crate::point_add::required_env($env))
-        }
-    };
-}
-// The submodules are declared above this macro, so textual scoping does not
-// reach them; this re-export is what makes `crate::point_add::pinned_env` a path
-// they can import. No visibility marker: like everything else in this file it is
-// private to `point_add` and therefore already visible to its descendants, which
-// is all the submodules need. (`pub` would be E0364 anyway -- a `macro_rules!`
-// without `#[macro_export]` cannot be re-exported wider than the crate.)
-use pinned_env;
-
-/// The raw value of `name`, or `None` when it is unset, empty, or not UTF-8.
-///
-/// **Every environment read in this tree goes through here**, so the rule can be
-/// stated once: empty counts as unset. That makes `KNOB= ./build_circuit` clear
-/// an override rather than pin the empty string, and it is the same rule
-/// `src/bin/grind` applies when deciding whether an override beats a pinned
-/// literal -- the two have to agree, or the grinder models a different circuit
-/// than the one that was built.
-///
-/// `var` rather than `var_os`: a knob that is not UTF-8 is not a knob, and
-/// reading it as absent puts it on the pinned default instead of carrying a
-/// value nothing downstream can parse.
+/// Fixed I10 configuration. Unlisted research switches are absent/off.
+/// The submission emits the same circuit regardless of inherited environment.
 fn env_raw(name: &str) -> Option<String> {
-    std::env::var(name)
-        .ok()
-        .map(|v| v.trim().to_string())
-        .filter(|v| !v.is_empty())
+    let value = match name {
+        "CMP_SEED_ALL" => "1",
+        "ERASE_COMPARE" => "22",
+        "FOLD_GUARD" => "24",
+        "PP_CF_DEFER_WALK_PHASE" => "1",
+        "PP_CF_END_CHUNK" => "8",
+        "PP_CHUNK_SHAPE" => "38:0,25:-2,0:-4",
+        "PP_CUT_SQIDENT" => "1",
+        "PP_CUT_WALKLOAN" => "1",
+        "PP_DEPTH_PROFILE" => "0:0",
+        "PP_DIRECT_ENDPOINT" => "1",
+        "PP_DIRECT_FOLD" => "1",
+        "PP_FLAG_SHAPE" => "38:0,25:-2,0:-2",
+        "PP_FLAG_WIDEN_DIV" => "38",
+        "PP_FOLD_PROFILE" => "38:0,32:-1,19:-4,0:-4",
+        "PP_FOLD_WIDEN" => "242",
+        "PP_HEAD_DIV" => "192",
+        "PP_HEAD_MUL" => "403",
+        "PP_JOINT_GUARD" => "0",
+        "PP_JOINT_LOW_BITS" => "32",
+        "PP_JOINT_MUL_FOLD" => "1",
+        "PP_JOINT_PREBIAS_DIV" => "1",
+        "PP_MID_BATCH_DIV" => "0",
+        "PP_MID_BATCH_MUL" => "32",
+        "PP_NEW_REPLAY" => "1",
+        "PP_PREBIAS_RETAIN_BITS" => "32",
+        "PP_Q1208_HELPERS" => "1",
+        "PP_R2" => "648",
+        "PP_REPLAY_CHUNK_COMPARE" => "21",
+        "PP_REPLAY_FLAG_COMPARE" => "20",
+        "PP_REPLAY_FOLD_WINDOW" => "54",
+        "PP_REPLAY_FOLD_WINDOW_MUL" => "54",
+        "PP_REPLAY_SIGN_LOAN" => "1",
+        "PP_REPLAY_SIGN_LOAN_MUL" => "1",
+        "PP_RETAIN_EXACT_DIV" => "1",
+        "PP_RETAIN_EXACT_EXTRA_DIV" => "4",
+        "PP_RETAIN_EXACT_EXTRA_MUL" => "4",
+        "PP_RETAIN_EXACT_MUL" => "1",
+        "PP_RETAIN_REBALANCE" => "1",
+        "PP_REUSE_DIV_PARITY" => "1",
+        "PP_REUSE_MUL_SELECTORS" => "1",
+        "PP_ROUNDS_MUL" => "698",
+        "PP_SIMPLIFY" => "product,affine,quadratic,truth",
+        "PP_SOURCE_SIGN_GROW" => "1",
+        "PP_SOURCE_SIGN_LOAN" => "0",
+        "PP_SPLIT_FOLD" => "0",
+        "PP_SPLIT_FOLD_OVERAGE" => "0",
+        "PP_SPLIT_OVERLAP_BITS" => "1",
+        "PP_SPRINT_MIXED" => "0",
+        "PP_TAIL_DIV" => "684",
+        "PP_TAIL_MUL" => "645",
+        "PP_WALK_GUARD_BITS" => "1",
+        "PP_WALK_GUARD_MAX_WIDTH" => "64",
+        "PP_WALK_MAX_QUBITS" => "1251",
+        "PP_WIDTH_SCHEDULE" => "259,258x19,257x5,256x3,255x4,254x4,253x2,252x4,251x3,250x5,249x2,248x4,247x3,246x2,245x4,244x3,243x3,242x3,241x3,240x3,239x4,238x3,237x2,236x4,235x2,234x3,233x2,232x4,231x4,230x2,229x3,228x3,227x3,226x2,225x4,224x2,223x2,222x3,221x3,220x4,219x3,218x2,217x3,216x3,215x3,214x4,213x2,212x2,211x3,210x4,209x3,208x2,207x2,206x2,205x3,204x2,203x4,202x3,201x3,200x4,199x2,198x2,197x3,196x2,195x2,194x4,193x4,192x2,191x3,190x3,189x2,188x3,187x2,186x3,185x2,184x3,183x4,182x2,181x3,180x4,179x2,178x2,177x3,176x3,175,174x2,173x2,172x4,171x3,170x2,169x2,168x4,167x3,166x3,165x2,164x3,163x3,162x2,161x3,160x2,159x3,158x2,157x3,156x2,155x4,154x2,153x3,152x2,151x3,150x3,149x2,148x2,147x2,146x4,145x4,144x3,143x2,142x2,141x3,140x2,139x2,138x2,137x3,136x2,135x4,134x3,133x3,132x3,131x2,130x3,129x2,128x4,127x3,126x2,125x2,124x3,123x2,122x3,121x3,120x2,119x5,118x2,117x3,116x2,115x3,114x4,113x2,112x2,111x4,110x2,109x2,108x2,107x2,106x2,105x5,104x2,103x2,102x2,101x2,100x4,99x2,98x2,97x2,96x3,95x3,94x3,93x2,92x3,91x2,90x4,89x3,88x2,87x2,86x4,85x2,84,83x4,82x2,81x2,80x2,79x3,78x2,77x2,76x3,75,74x2,73x3,72x3,71x2,70x3,69x3,68x3,67x3,66x2,65x3,64x4,63x2,62x2,61x3,60x2,59x2,58x2,57x2,56x2,55x3,54x3,53x2,52x3,51x2,50x4,49x2,48x2,47x3,46x3,45x2,44x2,43x3,42x2,41x2,40x3,39x2,38x2,37x3,36x4,35x2,34x3,33x2,32x2,31x2,30x2,29x2,28x4,27x2,26x2,25x3,24x2,23x2,22x2,21x3,20x3,19x2,18x3,17x2,16x2,15x3,14x2,13x2,12x2,11x2,10x2,9x4,8x9,8x2",
+        "SQ_ALIAS_PRODUCT_LSB" => "1",
+        "SQ_A_POLICY" => "7",
+        "SQ_BORROW_ROW_CARRIES" => "0",
+        "SQ_B_POLICY" => "7",
+        "SQ_C_POLICY" => "7",
+        "SQ_DEFER_CROSS_PHASE" => "1",
+        "SQ_DIAG_PRELOAD" => "1",
+        "SQ_FIT_CROSS" => "1",
+        "SQ_LEND_ASSEMBLY_ZEROS" => "1",
+        "SQ_LEND_RETAINED_ANDS" => "2",
+        "SQ_LEND_RETAINED_CROSS2" => "2",
+        "SQ_LEND_RETAINED_ZEROS" => "1",
+        "SQ_ROW0_CARRY" => "1",
+        "SQ_ROW0_INVERSE_CARRIES" => "1",
+        "SQ_ROW_ALL_MEASURE_TOP" => "1",
+        "SQ_SPARSE_CORRECTION" => "0",
+        "SQ_SPARSE_SPREAD" => "0",
+        "SQ_SPLIT_LOW_MIN" => "64",
+        "SQ_SPLIT_SUM_MIN" => "65",
+        "SQ_ZERO_TOP_CROSS" => "1",
+        "SQ_ZERO_TOP_SPREAD" => "1",
+        "SQ_ZERO_TOP_SUM" => "1",
+        "TAIL_NONCE" => "7978492",
+        _ => return None,
+    };
+    Some(value.to_owned())
 }
 
-/// A diagnostic switch. Off when unset, empty, or set to a value that plainly
-/// means no -- `0`, `false`, `no`, `off`, in any case. Anything else is on, so
-/// `KNOB=1` and `KNOB=please` both enable and only a deliberate `KNOB=0`
-/// disables.
 fn env_flag(name: &str) -> bool {
     env_raw(name).is_some_and(|value| {
-        !matches!(
-            value.to_ascii_lowercase().as_str(),
-            "0" | "false" | "no" | "off"
-        )
+        !matches!(value.to_ascii_lowercase().as_str(), "0" | "false" | "no" | "off")
     })
 }
 
@@ -120,49 +128,24 @@ fn required_env<T: FromStr>(name: &str) -> T
 where
     <T as FromStr>::Err: std::fmt::Display,
 {
-    let Some(raw) = env_raw(name) else {
-        panic!("{name} is not set; every tuning knob must be pinned in point_add::build")
-    };
-    raw.parse().unwrap_or_else(|e| {
-        panic!(
-            "{name}={raw:?} is not a valid {}: {e}",
-            std::any::type_name::<T>()
-        )
-    })
+    let raw = env_raw(name).unwrap_or_else(|| panic!("missing fixed I10 setting {name}"));
+    raw.parse().unwrap_or_else(|e| panic!("invalid fixed I10 setting {name}: {e}"))
 }
 
-/// A knob that may be absent: `None` when unset, empty or unparseable.
-///
-/// The counterpart to [`required_env`], and the split is the point. Anything the
-/// *circuit* reads goes through `required_env` and panics on a missing pin,
-/// because quietly building a different circuit is the one failure nothing
-/// downstream can catch. Anything that merely *observes* the build -- the
-/// recorders in [`record`] -- have the opposite duty and must default to off, so
-/// it comes through here.
 fn optional_env<T: FromStr>(name: &str) -> Option<T> {
     env_raw(name)?.parse().ok()
 }
 
-// ─── The truncation width every constant fold shares ───────────────────────
-//
-// Every approximation outside the ping-pong replay is one of exactly two
-// shapes, and the balance rule says both want ONE value each, not one per
-// caller. Equalising `d(lambda)/d(Toffoli)` across sites gives `err / u` equal,
-// where `u` is 1 for an unconditional site and 1/2 for a compare (whose Toffoli
-// sit under a `push_condition` and execute half the time). So:
-//
-//   * every constant-fold site wants the same per-call error, and
-//   * every measured-erasure compare wants HALF that error, i.e. one bit more.
-//
-// Notably that does not depend on the call count: a 29-call site and a 2-call
-// site want the same width. The replay's own windows are not here because they
-// are pinned by peak geometry rather than by error.
-//
-// Only the first of the pair is declared here, because only the first is shared
-// -- `fold_guard` reaches `modular`, `square` and `pingpong`. The compare width
-// it is derived against lives with its single caller, as
-// `modular::erase_compare`; both are still pinned together in [`build`], which
-// is where the two values have to be read side by side to stay one bit apart.
+macro_rules! pinned_env {
+    ($vis:vis $name:ident, $env:literal) => {
+        $vis fn $name() -> usize {
+            static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+            *SLOT.get_or_init(|| $crate::point_add::required_env($env))
+        }
+    };
+}
+use pinned_env;
+
 pinned_env!(fold_guard, "FOLD_GUARD");
 
 /// Rewrite the 96-op identity tail to encode the ground nonce. Only `q_target`
@@ -233,188 +216,14 @@ fn build_point_add() -> Vec<Op> {
     circ.take_ops()
 }
 
-/// Pin every tuning knob, build the circuit, and bake the ground nonce into its
-/// tail.
-///
-/// These pins are the circuit's entire configuration. Everything under
-/// [`build_point_add`] reads them back through [`required_env`], which panics on
-/// a missing one, so a dropped pin stops the build instead of quietly emitting a
-/// different circuit. [`set_default_env`] does not overwrite, so a value already
-/// in the environment wins -- that is how the knobs are swept, and why
-/// `src/bin/grind` recovers the tuning by reading these lines as text rather
-/// than by trusting the environment it happens to run in.
-///
-/// Grouped by what each value shapes, with the measurement that fixed it.
+/// Emit the fixed I10 circuit and accepted public-validation nonce7978492.
 pub fn build() -> Vec<Op> {
-    // ── The two walks ──────────────────────────────────────────────────────
-
-    // Per-round register width for the divide's walk, run-length encoded as
-    // `width x rounds` (a bare `width` is a run of one). Its LENGTH is that
-    // walk's round count, so there is no separate rounds knob on this side.
-    // Run-length rather than 696 loose integers because the schedule is a
-    // staircase -- every width from 259 down to 8 appears as exactly one run --
-    // so it is the form an edit is least likely to corrupt, and a third the
-    // size. GENERATED, by fitting each round's width to the measured magnitude
-    // distribution of the recurrence, and WRONG for any other depth: to change
-    // the depth, regenerate rather than truncate or pad. See
-    // `pingpong::width_schedule`.
-    set_default_env(
-        "PP_WIDTH_SCHEDULE",
-        concat!(
-            "259,258x19,257x5,256x3,255x4,254x4,253x2,252x4,251x3,250x5,249x2,248x4,",
-            "247x3,246x2,245x4,244x3,243x3,242x3,241x3,240x3,239x4,238x3,237x2,236x4,",
-            "235x2,234x3,233x2,232x4,231x4,230x2,229x3,228x3,227x3,226x2,225x4,224x2,",
-            "223x2,222x3,221x3,220x4,219x3,218x2,217x3,216x3,215x3,214x4,213x2,212x2,",
-            "211x3,210x4,209x3,208x2,207x2,206x2,205x3,204x2,203x4,202x3,201x3,200x4,",
-            "199x2,198x2,197x3,196x2,195x2,194x4,193x4,192x2,191x3,190x3,189x2,188x3,",
-            "187x2,186x3,185x2,184x3,183x4,182x2,181x3,180x4,179x2,178x2,177x3,176x3,",
-            "175,174x2,173x2,172x4,171x3,170x2,169x2,168x4,167x3,166x3,165x2,164x3,",
-            "163x3,162x2,161x3,160x2,159x3,158x2,157x3,156x2,155x4,154x2,153x3,152x2,",
-            "151x3,150x3,149x2,148x2,147x2,146x4,145x4,144x3,143x2,142x2,141x3,140x2,",
-            "139x2,138x2,137x3,136x2,135x4,134x3,133x3,132x3,131x2,130x3,129x2,128x4,",
-            "127x3,126x2,125x2,124x3,123x2,122x3,121x3,120x2,119x5,118x2,117x3,116x2,",
-            "115x3,114x4,113x2,112x2,111x4,110x2,109x2,108x2,107x2,106x2,105x5,104x2,",
-            "103x2,102x2,101x2,100x4,99x2,98x2,97x2,96x3,95x3,94x3,93x2,92x3,91x2,",
-            "90x4,89x3,88x2,87x2,86x4,85x2,84,83x4,82x2,81x2,80x2,79x3,78x2,77x2,76x3,",
-            "75,74x2,73x3,72x3,71x2,70x3,69x3,68x3,67x3,66x2,65x3,64x4,63x2,62x2,61x3,",
-            "60x2,59x2,58x2,57x2,56x2,55x3,54x3,53x2,52x3,51x2,50x4,49x2,48x2,47x3,",
-            "46x3,45x2,44x2,43x3,42x2,41x2,40x3,39x2,38x2,37x3,36x4,35x2,34x3,33x2,",
-            "32x2,31x2,30x2,29x2,28x4,27x2,26x2,25x3,24x2,23x2,22x2,21x3,20x3,19x2,",
-            "18x3,17x2,16x2,15x3,14x2,13x2,12x2,11x2,10x2,9x4,8x9",
-        ),
-    );
-    // The multiply walk's round count. The divide's is the schedule's length
-    // above; only this side needs a number of its own. 695 is the cheapest
-    // lambda in the tree to buy, and funding it by narrowing the fold profile
-    // was measured and does not pay.
-    set_default_env("PP_ROUNDS_MUL", "694");
-    set_default_env("PP_SPLIT_FOLD", "0");
-    set_default_env("PP_CUT_SQIDENT", "1");
-    set_default_env("PP_CUT_WALKLOAN", "1");
-    set_default_env("PP_SIMPLIFY", "product,affine,quadratic,truth");
-    // The peak, and therefore half the score. Nothing else sets it: the walk's
-    // split adds and the replay's chunked adds both size themselves against this
-    // and land on it exactly. The replay folds used to floor it as well -- the
-    // divide's trailing batch at `1210 + window` -- but the fold profile below
-    // narrows those rounds to 49 and 50.
-    //
-    // Not free: the narrower ladder needs 64 more approximate chunk boundaries,
-    // ~0.06 lambda, for -0.033% of score. That is 0.56% per lambda, five times
-    // the rate anything else in the tree trades at, which is why it is taken --
-    // but it is still lambda, and lambda is paid in the cost of grinding a nonce.
-    set_default_env("PP_WALK_MAX_QUBITS", "1259");
-
-    // ── The replay fold window ─────────────────────────────────────────────
-
-    // The base truncation window each replay cell folds at, per direction.
-    set_default_env("PP_REPLAY_FOLD_WINDOW", "53");
-    // The multiply's is one bit wider, and that bit is a deliberate purchase in
-    // the opposite direction to the cap above: it pays 688 executed Toffoli
-    // (0.076% of score, and the peak does NOT move -- 1260 holds, it is 55 that
-    // breaks to 1261) to buy back 1.13 +/- 0.31 lambda, measured paired at a
-    // fixed `EVAL_SEED` over 600,000 shots a side. Nothing in the tree sells
-    // lambda at that rate, so this is not an arbitrage; it is bought because the
-    // binding constraint was grinding a nonce rather than the score. The
-    // divide's window stays at 53 because it holds about half the lambda the
-    // multiply's does, so the same bit buys proportionally less.
-    set_default_env("PP_REPLAY_FOLD_WINDOW_MUL", "54");
-    // Per-round offsets on those two windows, as `width:offset` bands keyed on
-    // the walk's width at that round. MEASURED, not derived: the rate at which
-    // the fold's dropped carry actually matters is flat for the first 85% of the
-    // walk and then collapses ~11x over the last hundred rounds. Keyed on the
-    // width rather than the round so that regenerating the schedule above
-    // carries the profile with it; `pingpong::fold_offset` applies it.
-    set_default_env("PP_FOLD_PROFILE", "38:0,32:-1,19:-4,0:-4");
-    // How many leading rounds carry one extra bit of window. The level, kept
-    // deliberately out of the shape above: the measured rate is flat across
-    // exactly the region this covers, so one threshold reads it more honestly
-    // than another band would.
-    set_default_env("PP_FOLD_WIDEN", "242");
-    // Where the trailing replay batch takes over. Everything above it is
-    // replayed at the terminal state, where `loan_terminal` has collapsed both
-    // walk registers to a sign wire and the tape is at its longest -- so the
-    // widest fold in that batch is the widest thing alive anywhere, and the peak
-    // floors at `1210 + window` for the batch's first round. Everything in
-    // `r1..=r2` is instead replayed beside its own walk round, where the walk
-    // register is still live and there is correspondingly less room.
-    //
-    // The emitted count does not move at all across this range -- 945,183 scored
-    // gates at every value from 630 to 656 -- so the choice is purely about the
-    // peak, and the peak gives a plateau with a hard edge at each end. MEASURED:
-    //
-    //   <= 614   the plan assertion fires
-    //   615..630 peak 1262
-    //   631..655 peak 1260   <- pinned mid-plateau
-    //   656..657 peak 1261
-    //   >= 658   peak 1262
-    //
-    // The lower edge is exactly derivable and worth understanding, because it
-    // moves whenever the schedule or the fold profile does. The fold window is
-    // keyed on the walk's width, and in round space this schedule crosses the
-    // profile's bands at 616 (width < 38, offset -1) and 632 (width < 32, offset
-    // -3). A trailing batch starting in 616..631 therefore folds at window 52 and
-    // floors the peak at 1262; from 632 the window is 50 and the floor is 1260.
-    // So the batch must not start before 632, i.e. `r2 >= 631` -- which is the
-    // measured edge to the round.
-    //
-    // The upper edge is the mirror: it is where the last interleaved fold stops
-    // fitting beside its live walk register. That is a footprint prediction of
-    // the same kind `head_boundary` makes for `r1`, not a closed form.
-    //
-    // Note the plan's own assertion is much weaker than the real constraint: it
-    // only requires the batch not to reach past `fold_ramp_start` (616), i.e.
-    // `r2 >= 615`, so 615..630 passes it and quietly costs two qubits.
-    set_default_env("PP_R2", "648");
-
-    // ── The two phase-channel compares ─────────────────────────────────────
-    //
-    // Both repair an approximation whose error appears as a PHASE rather than as
-    // a wrong bit, so no classical model of the values can see either one. Each
-    // is a base width plus a per-round band table, narrowing where the walk
-    // narrows for the same reason the fold window does and by the same kind of
-    // measurement.
-
-    // Chunk-boundary repair. `chunk_layout` reads this flat base, so narrowing
-    // the comparison does not move the boundaries themselves.
-    set_default_env("PP_REPLAY_CHUNK_COMPARE", "21");
-    set_default_env("PP_CHUNK_SHAPE", "38:0,25:-2,0:-4");
-    // The replay cell's overflow flag, same construction.
-    set_default_env("PP_REPLAY_FLAG_COMPARE", "20");
-    set_default_env("PP_FLAG_WIDEN_DIV", "38");
-    set_default_env("PP_FLAG_SHAPE", "38:0,25:-2,0:-4");
-
-    // ── The two widths every approximation outside the replay reads ────────
-    //
-    // 21 and 22 are the balance point against the replay folds' 289 executed
-    // Toffoli per lambda. The compare is one bit finer because its gates sit
-    // under a `push_condition` and so execute half the time, which halves what a
-    // bit of width costs there; the derivation is above `fold_guard`.
-    set_default_env("FOLD_GUARD", "21");
-    set_default_env("ERASE_COMPARE", "22");
-
-    // ── Square recursion policy ────────────────────────────────────────────
-    //
-    // A Karatsuba sum half of at least SUM_MIN bits is split again instead of
-    // squared triangularly (the sum children are 65/65/66 bits; 999 disables).
-    // The low half is split only from LOW_MIN bits (129 disables; the low
-    // children are 64 bits). Exact arithmetic only: no failure sites move.
-    set_default_env("SQ_SPLIT_SUM_MIN", "65");
-    set_default_env("SQ_SPLIT_LOW_MIN", "64");
-
-    // ── The ground nonce ───────────────────────────────────────────────────
-    //
-    // Diagnostic placeholder; not a passing nonce. The exact op stream
-    // selects all 9,024 graded shots; any stream change rerolls them.
-    // Check the compressed ops.bin SHA256 before grinding this candidate.
-    set_default_env("TAIL_NONCE", "2886213855485");
-
     let mut ops = build_point_add();
     // Exact op-stream post-passes, ported from the 2026-09-04 warpspeed
     // campaign (R10 affine, R33 quadratic, R41 truth, R46 product). Each pass
     // re-derives value supports from the stream's own ABI and drops or weakens
     // CCX ops it proves redundant, so composition is semantics-preserving.
-    // PP_SIMPLIFY is a comma-separated list applied left to right; defaults to
-    // the full four-pass chain when unset, "off" disables. Runs BEFORE the tail
+    // The fixed four-pass chain is applied left to right, BEFORE the tail
     // append so the 96-X identity tail and the nonce it encodes are never
     // reinterpreted by a proof.
     let simplify_config =
diff --git a/src/point_add/modular.rs b/src/point_add/modular.rs
index f82a76d..d6affd2 100644
--- a/src/point_add/modular.rs
+++ b/src/point_add/modular.rs
@@ -4,7 +4,7 @@ use super::compare::erase_with_compare;
 use super::const_arith::cadd_const_trunc;
 use super::pingpong::walk_max_qubits;
 use super::{fold_guard, pinned_env, Builder, SECP256K1_P};
-use crate::circuit::QubitId;
+use crate::circuit::{BitId, QubitId};
 
 // Width of the measured-erasure comparisons in this file, and nowhere else in
 // the tree. One bit finer than `fold_guard` by the balance rule derived in
@@ -59,12 +59,73 @@ pub fn ripple_add(
     carry_in: Option<QubitId>,
     carry_out: Option<QubitId>,
 ) {
-    ripple_add_proved(circ, addend, acc, carry_in, carry_out, Carry0::Full, Carry1::Full);
+    ripple_add_proved(circ, addend, acc, carry_in, carry_out, Carry0::Full, Carry1::Full, None, None, None, None);
+}
+
+/// Finish a vented sum, consume its overflow while the top arithmetic carry
+/// is still live, then perform the ordinary measured internal unwind.
+///
+/// The consumer receives (overflow, unchanged source top, sum top, carry into
+/// top). It must preserve the source/sum/carry frame and may mutate only
+/// disjoint operands. The lower positions in this slice remain folded until
+/// the unwind, so they are not yet readable as source or sum bits.
+pub(crate) fn ripple_add_consume(
+    circ: &mut Builder, addend: &[QubitId], acc: &[QubitId],
+    carry_in: Option<QubitId>, carry_out: QubitId,
+    consumer: impl FnOnce(&mut Builder, QubitId, QubitId, QubitId, Option<QubitId>),
+) {
+    let n=acc.len(); assert!(n>=1); assert_eq!(addend.len(),n);
+    let carries=circ.alloc_qubits(n-1);
+    let previous=|i:usize|if i==0 {carry_in} else {Some(carries[i-1])};
+    for i in 0..n {
+        carry_step(circ,addend[i],acc[i],previous(i),
+            if i+1==n {carry_out} else {carries[i]});
+    }
+    if let Some(p)=previous(n-1) {circ.cx(p,addend[n-1]);}
+    circ.cx(addend[n-1],acc[n-1]);
+    consumer(circ,carry_out,addend[n-1],acc[n-1],previous(n-1));
+    for i in (0..n-1).rev() {
+        unwind_carry_step(circ,addend[i],acc[i],previous(i),carries[i]);
+    }
+}
+
+/// X-erase an outgoing carry using the live completed top-bit frame.
+/// o = a*s XOR a XOR a*c XOR s*c XOR c, with c=0 when absent.
+pub(crate) fn erase_overflow_from_frame(
+    circ: &mut Builder, overflow: QubitId, source_top: QubitId,
+    sum_top: QubitId, carry_into_top: Option<QubitId>,
+) {
+    let m=circ.alloc_bit(); circ.hmr(overflow,m);
+    circ.z_if(source_top,m); circ.cz_if(source_top,sum_top,m);
+    if let Some(c)=carry_into_top {
+        circ.z_if(c,m); circ.cz_if(source_top,c,m); circ.cz_if(sum_top,c,m);
+    }
+    circ.free_bit(m); circ.free(overflow);
+}
+
+/// [`ripple_add`] with one deferred X-measurement phase applied to an arithmetic
+/// carry before that carry's own measurement unwind changes its representation.
+/// `carry_index == 0` names the carry out of the slice's bit 0.
+pub fn ripple_add_with_deferred_phase(
+    circ: &mut Builder,
+    addend: &[QubitId],
+    acc: &[QubitId],
+    carry_in: Option<QubitId>,
+    carry_out: Option<QubitId>,
+    deferred: Option<(usize, BitId)>,
+) {
+    ripple_add_proved(
+        circ, addend, acc, carry_in, carry_out, Carry0::Full, Carry1::Full, deferred, None, None, None,
+    );
 }
 
 fn ripple_add_proved(
     circ: &mut Builder, addend: &[QubitId], acc: &[QubitId],
     carry_in: Option<QubitId>, carry_out: Option<QubitId>, c0: Carry0, c1: Carry1,
+    mut deferred: Option<(usize, BitId)>,
+    known_output: Option<&[(bool, Vec<QubitId>)]>,
+    known_terminal: Option<bool>,
+    borrowed: Option<&[QubitId]>,
 ) {
     let width = acc.len();
     let k = addend.len();
@@ -81,7 +142,12 @@ fn ripple_add_proved(
     } else {
         width.saturating_sub(2)
     };
-    let mut carries = circ.alloc_qubits(owned);
+    let mut carries = if let Some(qs)=borrowed {
+        assert!(carry_out.is_none() && k+1==width);
+        assert_eq!(qs.len(),owned);
+        assert!(qs.iter().all(|q|!acc.contains(q) && !addend.contains(q)));
+        qs.to_vec()
+    } else {circ.alloc_qubits(owned)};
     carries.extend(carry_out);
     let previous = |i: usize| {
         if i == 0 {
@@ -95,8 +161,28 @@ fn ripple_add_proved(
     // and it always has a previous carry because `k >= 1`.
     let zero_prev = |i: usize| previous(i).expect("a zero-addend position always has a carry in");
 
+    if let Some(output)=known_output {
+        assert!(carry_in.is_none() && carry_out.is_none() && deferred.is_none());
+        assert_eq!(k+1,width);assert_eq!(output.len(),width);
+        // sum[j] = original_addend[j] XOR original_acc[j] XOR carry[j-1].
+        // The caller supplies a proved affine expression for the resulting
+        // sum. Compute ALL carries while those original source bits are still
+        // intact, before the normal ripple folds anything into its operands.
+        for (i,&q) in carries.iter().enumerate() {
+            let j=i+1;
+            circ.cx(addend[j],q);circ.cx(acc[j],q);
+            if output[j].0 {circ.x(q);}
+            for &s in &output[j].1 {circ.cx(s,q);}
+        }
+    }
+
     for i in 0..carries.len() {
-        if i == 0 && c0 != Carry0::Full {
+        if known_output.is_some() {
+            // Carries already contain arithmetic carries. Preserve the usual
+            // folded operand state so the terminal step and exact measured
+            // unwind below remain unchanged.
+            if let Some(prev)=previous(i) {circ.cx(prev,addend[i]);circ.cx(prev,acc[i]);}
+        } else if i == 0 && c0 != Carry0::Full {
             assert!(carry_in.is_none() && k >= 2 && width >= 4);
             if c0 == Carry0::IsAddend0 { circ.cx(addend[0], carries[0]); }
         } else if i == 1 && c1 == Carry1::CopiesCarry0 {
@@ -126,16 +212,31 @@ fn ripple_add_proved(
             circ.cx(addend[top], acc[top]);
         }
     } else {
-        terminal_step(circ, addend, acc, previous(width - 2));
+        let terminal=known_terminal.or_else(|| {
+            known_output.filter(|_|super::env_flag("SQ_ROW0_MEASURE_TOP") || super::env_flag("SQ_ROW_ALL_MEASURE_TOP"))
+                .map(|output| {assert!(output[width-1].1.is_empty());output[width-1].0})
+        });
+        if let Some(desired)=terminal {
+            terminal_step_known(circ,addend,acc,previous(width-2),desired);
+        } else {terminal_step(circ, addend, acc, previous(width - 2));}
     }
 
     for i in (0..owned).rev() {
+        if deferred.as_ref().is_some_and(|(at, _)| *at == i) {
+            let (_, phase) = deferred.take().unwrap();
+            // At this point `carries[i]` is still the arithmetic carry. The
+            // first CX in `unwind_carry_step` changes it to the CCX product.
+            circ.z_if(carries[i], phase);
+            circ.free_bit(phase);
+        }
         if i < k {
-            unwind_carry_step(circ, addend[i], acc[i], previous(i), carries[i]);
+            if borrowed.is_some() {unwind_carry_step_lent(circ,addend[i],acc[i],previous(i),carries[i]);}
+            else {unwind_carry_step(circ, addend[i], acc[i], previous(i), carries[i]);}
         } else {
             unwind_zero_step(circ, acc[i], zero_prev(i), carries[i]);
         }
     }
+    assert!(deferred.is_none(), "deferred phase did not name an owned ripple carry");
 }
 
 /// Undo a zero-addend stage: erase `carry = acc AND previous` in the X basis,
@@ -233,6 +334,29 @@ fn terminal_step(
     circ.cx(addend[i], acc[i]);
 }
 
+/// Exact inverse producer only: if the resulting top bit is the known
+/// constant d, recover its OLD value from the terminal carry expression and
+/// any top addend. X-measure it and repair all terms with Clifford gates.
+/// This replaces one terminal CCX with one extra measurement, no scratch wire.
+fn terminal_step_known(circ:&mut Builder,addend:&[QubitId],acc:&[QubitId],previous:Option<QubitId>,desired:bool) {
+    let n=acc.len();let k=addend.len();assert!(n>=2 && k<=n);let i=n-2;
+    if i>=k {
+        let p=previous.expect("padded stage has incoming carry");
+        let m=circ.alloc_bit();circ.hmr(acc[n-1],m);
+        if desired {circ.x(acc[n-1]);circ.z_if(acc[n-1],m);}
+        circ.cz_if(p,acc[i],m);circ.free_bit(m);
+        circ.cx(p,acc[i]);return;
+    }
+    if let Some(p)=previous {circ.cx(p,addend[i]);circ.cx(p,acc[i]);}
+    let m=circ.alloc_bit();circ.hmr(acc[n-1],m);
+    if desired {circ.x(acc[n-1]);circ.z_if(acc[n-1],m);}
+    if let Some(p)=previous {circ.z_if(p,m);}
+    if n-1<k {circ.z_if(addend[n-1],m);}
+    circ.cz_if(addend[i],acc[i],m);circ.free_bit(m);
+    if let Some(p)=previous {circ.cx(p,addend[i]);}
+    circ.cx(addend[i],acc[i]);
+}
+
 /// Controlled add of the folding constant `f = 2^32 + 977` into the low `lsbs`
 /// bits of `reg`, conditioned on `ctrl`. Carries past bit `lsbs` are dropped.
 ///
@@ -276,11 +400,24 @@ pub fn ripple_add_lent(
     acc: &[QubitId],
     carry_in: Option<QubitId>,
     lent: QubitId,
+) {
+    ripple_add_lent_with_deferred_phase(circ, addend, acc, carry_in, lent, None);
+}
+
+/// [`ripple_add_lent`] with a deferred phase attached to one arithmetic carry.
+/// The hook also supports the final carry stored on `lent` (index `width - 3`).
+pub fn ripple_add_lent_with_deferred_phase(
+    circ: &mut Builder,
+    addend: &[QubitId],
+    acc: &[QubitId],
+    carry_in: Option<QubitId>,
+    lent: QubitId,
+    mut deferred: Option<(usize, BitId)>,
 ) {
     let width = addend.len();
     assert_eq!(width, acc.len(), "ripple_add_lent: width mismatch");
     if width < 3 {
-        ripple_add(circ, addend, acc, carry_in, None);
+        ripple_add_with_deferred_phase(circ, addend, acc, carry_in, None, deferred);
         return;
     }
     // Owned carries for positions 0..width-3; the lent wire takes the carry out
@@ -301,10 +438,21 @@ pub fn ripple_add_lent(
     carry_step(circ, addend[owned], acc[owned], previous(owned), lent);
     terminal_step(circ, addend, acc, Some(lent));
 
+    if deferred.as_ref().is_some_and(|(at, _)| *at == owned) {
+        let (_, phase) = deferred.take().unwrap();
+        circ.z_if(lent, phase);
+        circ.free_bit(phase);
+    }
     unwind_carry_step_lent(circ, addend[owned], acc[owned], previous(owned), lent);
     for i in (0..owned).rev() {
+        if deferred.as_ref().is_some_and(|(at, _)| *at == i) {
+            let (_, phase) = deferred.take().unwrap();
+            circ.z_if(carries[i], phase);
+            circ.free_bit(phase);
+        }
         unwind_carry_step(circ, addend[i], acc[i], previous(i), carries[i]);
     }
+    assert!(deferred.is_none(), "deferred phase did not name a lent-ripple carry");
 }
 
 /// [`unwind_carry_step`] for a lent carry wire: same erasure and phase repair,
@@ -330,6 +478,40 @@ fn unwind_carry_step_lent(
     circ.cx(addend, acc);
 }
 
+/// Wrapped add on the structural subspace addend[n-1]==addend[n-2].
+/// Borrow the redundant top source bit for the last carry, in addition to an
+/// optional already-clean caller loan. Both are restored, with exact phase.
+pub(crate) fn ripple_add_source_sign_loan(
+    circ:&mut Builder,addend:&[QubitId],acc:&[QubitId],carry_in:Option<QubitId>,
+    lent:Option<QubitId>,mut deferred:Option<(usize,BitId)>,
+) {
+    let n=addend.len();assert_eq!(n,acc.len());
+    assert!(n>=3+usize::from(lent.is_some()));
+    let owned=n-3-usize::from(lent.is_some());
+    let high=addend[n-1];let copy=addend[n-2];
+    assert!(!acc.contains(&high));
+    if let Some(q)=lent{assert!(!acc.contains(&q)&&!addend.contains(&q));}
+    circ.cx(copy,high);
+    let mut carries=circ.alloc_qubits(owned);
+    carries.extend(lent);carries.push(high);
+    let previous=|i:usize|if i==0{carry_in}else{Some(carries[i-1])};
+    for i in 0..carries.len(){carry_step(circ,addend[i],acc[i],previous(i),carries[i]);}
+    // The terminal's incoming carry occupies the old source top. Restore the
+    // original penultimate source before adding the identical top source bit.
+    let i=n-2;
+    circ.cx(high,copy);circ.cx(high,acc[i]);
+    circ.ccx(copy,acc[i],acc[n-1]);circ.cx(high,acc[n-1]);
+    circ.cx(high,copy);circ.cx(copy,acc[n-1]);circ.cx(copy,acc[i]);
+    for i in (0..carries.len()).rev(){
+        if deferred.as_ref().is_some_and(|(at,_)|*at==i){
+            let(_,m)=deferred.take().unwrap();circ.z_if(carries[i],m);circ.free_bit(m);
+        }
+        if i<owned{unwind_carry_step(circ,addend[i],acc[i],previous(i),carries[i]);}
+        else{unwind_carry_step_lent(circ,addend[i],acc[i],previous(i),carries[i]);}
+    }
+    assert!(deferred.is_none());circ.cx(copy,high);
+}
+
 pub fn addsub_full(circ: &mut Builder, addend: &[QubitId], acc: &[QubitId], inverse: bool) {
     if inverse {
         circ.x_all(acc);
@@ -479,9 +661,28 @@ pub fn mod_sub_vented(circ: &mut Builder, x: &[QubitId], y: &[QubitId]) {
 pub enum Carry0 { Full, IsAddend0, Zero }
 #[derive(Clone, Copy, PartialEq, Eq)]
 pub enum Carry1 { Full, CopiesCarry0 }
+/// Wrapped wide add on a subspace with a proved affine output word. This is
+/// NOT an unrestricted adder: incorrect output expressions violate its ABI.
+pub(crate) fn add_wide_known_output(circ:&mut Builder, value:&[QubitId], acc:&[QubitId], output:&[(bool,Vec<QubitId>)],borrowed:Option<&[QubitId]>) {
+    ripple_add_proved(circ,value,acc,None,None,Carry0::Full,Carry1::Full,None,Some(output),None,borrowed);
+}
+/// Borrowed carries arrive zero and remain owned by the caller. This receiver
+/// is restricted to a wide triangular row, where every carry has an addend.
+pub(crate) fn addsub_wide_borrowed(circ:&mut Builder,value:&[QubitId],acc:&[QubitId],inverse:bool,c0:Carry0,c1:Carry1,result_top:Option<bool>,borrowed:&[QubitId]) {
+    if inverse {circ.x_all(acc);}
+    ripple_add_proved(circ,value,acc,None,None,c0,c1,None,None,result_top.map(|v|v^inverse),Some(borrowed));
+    if inverse {circ.x_all(acc);}
+}
+/// Caller proves the top result bit, without claiming any other output bits.
+/// The complement frame flips that bit for the inner adder when subtracting.
+pub(crate) fn addsub_wide_known_top(circ:&mut Builder,value:&[QubitId],acc:&[QubitId],inverse:bool,c0:Carry0,c1:Carry1,result_top:bool) {
+    if inverse {circ.x_all(acc);}
+    ripple_add_proved(circ,value,acc,None,None,c0,c1,None,None,Some(result_top^inverse),None);
+    if inverse {circ.x_all(acc);}
+}
 pub fn addsub_full_low(circ: &mut Builder, value: &[QubitId], acc: &[QubitId], inverse: bool, c0: Carry0, c1: Carry1) {
     if inverse { circ.x_all(acc); }
-    ripple_add_proved(circ, value, acc, None, None, c0, c1);
+    ripple_add_proved(circ, value, acc, None, None, c0, c1, None, None, None, None);
     if inverse { circ.x_all(acc); }
 }
 pub fn addsub_wide_low(circ: &mut Builder, value: &[QubitId], acc: &[QubitId], inverse: bool, c0: Carry0, c1: Carry1) {
diff --git a/src/point_add/product_simplify.rs b/src/point_add/product_simplify.rs
index bfd3ed0..77262e3 100644
--- a/src/point_add/product_simplify.rs
+++ b/src/point_add/product_simplify.rs
@@ -184,6 +184,3 @@ fn quantum_touches(op: &Op) -> Vec<usize> {
     }
 }
 
-#[cfg(test)]
-#[path = "product_simplify_tests.rs"]
-mod tests;
diff --git a/src/point_add/quadratic_simplify.rs b/src/point_add/quadratic_simplify.rs
index f173063..a8ef2b6 100644
--- a/src/point_add/quadratic_simplify.rs
+++ b/src/point_add/quadratic_simplify.rs
@@ -309,6 +309,3 @@ pub(crate) fn simplify(ops: Vec<Op>) -> Vec<Op> {
     result
 }
 
-#[cfg(test)]
-#[path = "quadratic_simplify_tests.rs"]
-mod tests;
diff --git a/src/point_add/retained_prebias.rs b/src/point_add/retained_prebias.rs
new file mode 100644
index 0000000..5baebe3
--- /dev/null
+++ b/src/point_add/retained_prebias.rs
@@ -0,0 +1,85 @@
+//! Native composition of retained overflow phase repair and prebiased division.
+//! Explicitly preserves the prebias map with a separately named finite low cut.
+use super::*;
+
+#[derive(Debug)]
+struct Plan {bounds:Vec<(usize,usize)>,prefix:usize,bits:usize,saving:f64,exact:bool}
+fn plan(c:&Builder,r:usize,fw:usize)->Option<Plan>{
+ let base_bits=super::super::optional_env::<usize>("PP_PREBIAS_RETAIN_BITS")?;
+ let bits=if env_flag("PP_SPRINT_MIXED") && (370..=402).contains(&r) {29}else{base_bits};
+ assert!(bits>=12&&bits<=fw&&fw>=36&&!split_fold());
+ let room=walk_max_qubits().saturating_sub(c.active_qubits()as usize);
+ let loans=REPLAY_SIGN_LOANS.with(|s|s.get());
+ let old_bounds=composition_bounds(c,r,false)?;
+ let bounds=retained_rebalance(c,&old_bounds,r,false);
+ if bounds.len()<2{return None;}
+ let &(lo,hi)=bounds.last()?;let(plo,phi)=bounds[bounds.len()-2];let(k,seed)=boundary_repair_spec(r,false,plo,phi);
+ if lo<fw||phi-k-usize::from(seed)<fw{return None;}
+ let need=(bits-3).max(fw-34);
+ let existing=room as isize-(hi-lo)as isize-3;
+ let missing=(need as isize-existing).max(0)as usize;
+ let prefix=if missing==0{0}else{missing+1};if prefix+1>=hi-lo{return None;}
+ let mut fk=flag_compare(r)+usize::from(policy_width(r)>=flag_widen_div());
+ if env_flag("CMP_SEED_ALL"){fk-=1;}else{fk=refined_unseeded_width(fk,N,"PP_REFINE_UNSEEDED_F");}
+ let saving=(fk-1)as f64/2.0-missing as f64/2.0-(bits as f64-33.0);
+ if saving<=0.0{return None;}
+ // Bound released carry wires, retaining the original outer B comparisons.
+ let limit=super::super::optional_env::<usize>("PP_RETAIN_EXACT_EXTRA_DIV").unwrap_or(0);
+ let exact_missing=((fw-3) as isize-existing).max(0) as usize;
+ let exact_prefix=if exact_missing==0{0}else{exact_missing+1};
+ let exact=env_flag("PP_RETAIN_EXACT_DIV") && exact_missing<=limit && exact_prefix+1<hi-lo;
+ let prefix=if exact{exact_prefix}else{prefix};
+ let saving=if exact{saving-(exact_missing-missing) as f64/2.0-1.0}else{saving};
+ Some(Plan{bounds,prefix,bits,saving,exact})
+}
+
+/// J0=488*plus+977*twice-489*minus; high word adds k.
+fn split_half(c:&mut Builder,b:&[QubitId],p:QubitId,s:QubitId,o:QubitId,bits:usize){
+ c.cx(s,o);c.x(o);let q=and_clean(c,p,o);c.x(o);c.cx(s,o);
+ c.x(s);let minus=and_clean(c,q,s);c.x(s);
+ c.cx(minus,q);c.cx(s,p);c.cx(minus,p);
+ let small=U256::from(977);let fp=(small-U256::from(1))>>1usize;
+ let fm=U256::ZERO.wrapping_sub((small+U256::from(1))>>1usize);
+ let mut map=Vec::new();
+ for i in 0..bits-1{let mut row=Vec::new();if fp.bit(i){row.push(p);}if small.bit(i){row.push(q);}if fm.bit(i){row.push(minus);}map.push(row);}
+ joint_prebias::mapped_zero(c,&b[1..bits],&map);
+ let mut high=Vec::new();for i in 0..b.len()-32{let mut row=vec![minus];if i==0{row.push(p);}if i==1{row.push(q);}high.push(row);}
+ joint_prebias::mapped_zero(c,&b[32..],&high);
+ c.cx(minus,p);c.cx(s,p);c.cx(minus,q);
+ c.x(s);and_uncompute(c,minus,q,s);c.x(s);
+ c.cx(s,o);c.x(o);and_uncompute(c,q,p,o);c.x(o);c.cx(s,o);
+}
+
+pub(super)fn try_replay(c:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId],fw:usize,r:usize)->bool{
+ let Some(p)=plan(c,r,fw)else{return false;};
+ eprintln!("RETAINED_PREBIAS {} {} {} {} {} {}",r,c.active_qubits(),fw,p.bits,p.prefix,p.saving);
+ if env_flag("PP_COMPOSE_TRACE"){eprintln!("COMPOSE_RETAIN {} {} {} {} {} {:?}",r,c.active_qubits(),fw,p.bits,REPLAY_SIGN_LOANS.with(|s|s.get()),p.bounds);}
+ if p.exact {eprintln!("EXACT_RETAINED_FOLD div {} {}",r,fw);}
+ c.swap(sign,b[0]);c.cx(a[0],sign);c.cx(b[0],sign);c.cx_all(b[0],&b[1..]);
+ let initial=joint_prebias::initial_carry(c,a[0],sign,b[0]);
+ let mut cin=Some(initial);let mut previous=None;
+ for(j,&(lo,hi))in p.bounds.iter().enumerate(){
+  let out=c.alloc_qubit();let at=if j==0{1}else{lo};
+  if hi==N{
+   let split=lo+p.prefix;
+   let mid=if p.prefix==0{cin}else{let m=c.alloc_qubit();ripple_add(c,&a[lo..split],&b[lo..split],cin,Some(m));Some(m)};
+   super::super::modular::ripple_add_consume(c,&a[split..hi],&b[split..hi],mid,out,|c,o,aa,bb,cc|{
+    if p.exact {joint_prebias::half_fold(c,&b[1..fw],sign,b[0],o);}else{split_half(c,&b[..fw],sign,b[0],o,p.bits);}
+    c.swap(sign,b[0]);c.cx(o,b[0]);
+    super::super::modular::erase_overflow_from_frame(c,o,aa,bb,cc);
+   });
+   if p.prefix>0{let m=mid.unwrap();erase_with_compare(c,m,&b[lo..split],&a[lo..split],cin);c.free(m);}
+  }else{ripple_add(c,&a[at..hi],&b[at..hi],cin,Some(out));}
+  if j==0{joint_prebias::erase_initial(c,initial,a[0],sign,b[0]);}
+  if let Some((carry,plo,phi))=previous{
+   let(k,seed)=boundary_repair_spec(r,false,plo,phi);c.record_replay_site('B',r,phi,k);
+   let full=plo==0&&phi==k;
+   if full{c.cx(b[0],sign);}
+   erase_with_compare(c,carry,&b[phi-k..phi],&a[phi-k..phi],if full{Some(sign)}else{seed.then(||a[phi-k-1])});c.free(carry);
+   if full{c.cx(b[0],sign);}
+  }
+  cin=Some(out);previous=Some((out,lo,hi));
+ }
+ c.cx_all(sign,b);rotate_down(c,b);true
+}
+
diff --git a/src/point_add/square.rs b/src/point_add/square.rs
index 5df46af..992a606 100644
--- a/src/point_add/square.rs
+++ b/src/point_add/square.rs
@@ -17,8 +17,29 @@
 
 use super::modular::{addsub_full_low, addsub_wide_low, Carry0, Carry1, add_wide, addsub_full, addsub_wide, mod_addsub, sub_wide};
 use super::{fold_guard, pinned_env, Builder, N};
-use crate::circuit::QubitId;
+use crate::circuit::{QubitId,BitId};
 fn cut_sqident() -> bool { super::env_flag("PP_CUT_SQIDENT") }
+/// The low-diagonal preload ([`diag_preload`]). Off by default: with this clear
+/// the file emits exactly the stream it did before the lever existed.
+fn diag_preload_on() -> bool { super::env_flag("SQ_DIAG_PRELOAD") }
+
+/// How many of the diagonal's bits ride in for free.
+///
+/// `diag_spread` adds `2*spread(x)`, whose bit `j` sits at product position
+/// `2j+1`. The row ladder leaves exactly `2^m - 1` of headroom below every
+/// row window's top (the rows sum to at most `2^(i+m+1) - 2^m` after row `i`,
+/// and the window reaches bit `i+m`), so any value under `2^m` may be sitting
+/// in the product BEFORE the first row without any row's truncated window
+/// losing a carry. The diagonal bits with `2j+1 < m` are exactly that value --
+/// their sum is under `2^(2*ceil((m-1)/2)) <= 2^m` -- so they are copied in
+/// with a CX apiece and the add that used to carry them shrinks from the full
+/// `2m-1` positions to the `2m-2j0-1` above them.
+///
+/// `j0 = ceil((m-1)/2) = m/2` in integer division. Zero when the knob is off,
+/// which is what makes every routine below fall back to its old shape.
+fn diag_split(m: usize) -> usize {
+    if diag_preload_on() { m / 2 } else { 0 }
+}
 
 /// `f = 2^256 - p` in non-adjacent form: the value is `sum (-1)^neg * 2^shift`,
 /// i.e. `1 + 2^4 - 2^6 + 2^10 + 2^32`. Five terms against the constant's six set
@@ -39,6 +60,8 @@ fn row_addsub(
     operand: &[QubitId],
     acc: &[QubitId],
     inverse: bool,
+    first_copies_operand: bool,
+    borrowed: Option<&[QubitId]>,
 ) {
     let k = operand.len();
     assert_eq!(acc.len(), k + 1);
@@ -47,7 +70,20 @@ fn row_addsub(
         circ.cx(ctrl, acc[k]);
     }
     circ.cx_all(ctrl, &acc[..k]);
-    addsub_wide(circ, operand, acc, inverse);
+    if let Some(qs)=borrowed {
+        let c0=if first_copies_operand {Carry0::IsAddend0}else{Carry0::Full};
+        let top=(inverse && super::env_flag("SQ_ROW_ALL_MEASURE_TOP")).then_some(false);
+        super::modular::addsub_wide_borrowed(circ,operand,acc,inverse,c0,Carry1::Full,top,qs);
+    } else if inverse && super::env_flag("SQ_ROW_ALL_MEASURE_TOP") {
+        // Before row i, previous rows touched only through product[m+i-1]
+        // and preload lies below m. Thus row i's top product[m+i] was zero.
+        // On inverse, after its leading top CX, the inner subtraction must
+        // restore that zero; the lower complement frame never touches it.
+        let c0=if first_copies_operand {Carry0::IsAddend0}else{Carry0::Full};
+        super::modular::addsub_wide_known_top(circ,operand,acc,true,c0,Carry1::Full,false);
+    } else if first_copies_operand {
+        addsub_wide_low(circ, operand, acc, inverse, Carry0::IsAddend0, Carry1::Full);
+    } else { addsub_wide(circ, operand, acc, inverse); }
     circ.cx_all(ctrl, &acc[..k]);
     if !inverse {
         circ.cx(ctrl, acc[k]);
@@ -61,16 +97,51 @@ fn tri_square(circ: &mut Builder, x: &[QubitId], product: &[QubitId], inverse: b
     assert_ne!(m, 0);
     if inverse {
         tri_corr(circ, x, product, true);
+    } else {
+        // Into the still-zeroed product, so this is a copy and not an add.
+        diag_preload(circ, x, product);
     }
     // Forward walks the rows low-to-high; the inverse undoes them high-to-low.
     // Row `i` lands `x[i+1..]` at offset `2i+1`, so it spans up to bit `i+m+1`.
     for r in 0..m - 1 {
         let i = if inverse { m - 2 - r } else { r };
         let row = &product[2 * i + 1..i + m + 1];
-        row_addsub(circ, x[i], &x[i + 1..], row, inverse);
+        // Before forward row i, higher product bits have never been touched.
+        // Before inverse row i, the higher rows are already undone. Preload
+        // occupies only bits below m. There are m-i-1 clean bits above the
+        // row, enough for all m-i-2 owned ripple carries. Return them to zero
+        // without releasing the product's ownership or extending its lifetime.
+        let borrowed=super::env_flag("SQ_BORROW_ROW_CARRIES")
+            .then(|| &product[m+i+1..2*m-1]);
+        if inverse && i==0 && diag_split(m)>0 && m>=4 && super::env_flag("SQ_ROW0_INVERSE_CARRIES") {
+            row0_inverse_known(circ,x,row,borrowed);
+            continue;
+        }
+        // With diagonal preload, row0 starts at product[1]=x[0]. The
+        // controlled complement therefore makes the forward low acc bit 1,
+        // so its first carry is x[1]. On reversal the row output low bit is
+        // x[0]^x[1]; the two complement frames make the adder's bit x[1],
+        // again giving carry x[1]&x[1]=x[1]. Keep the usual measured unwind:
+        // only the first carry's computation changes from CCX to CX.
+        let copy_first = super::env_flag("SQ_ROW0_CARRY") && i==0 && diag_split(m)>0 && row.len()>=4;
+        row_addsub(circ, x[i], &x[i + 1..], row, inverse, copy_first, borrowed);
     }
     if !inverse {
         tri_corr(circ, x, product, false);
+    } else {
+        diag_preload(circ, x, product);
+    }
+}
+
+/// The diagonal bits that fit under the row ladder's headroom, copied straight
+/// into the product. Self-inverse, and free -- a CX apiece, no Toffoli.
+///
+/// It must run while the product is still |0...0>, i.e. before the first row
+/// forward and after the last one on the way back. See [`diag_split`] for why
+/// the rows' truncated windows stay exact with it sitting there.
+fn diag_preload(circ: &mut Builder, x: &[QubitId], product: &[QubitId]) {
+    for j in 0..diag_split(x.len()) {
+        circ.cx(x[j], product[2 * j + 1]);
     }
 }
 
@@ -94,14 +165,29 @@ fn tri_corr(circ: &mut Builder, x: &[QubitId], product: &[QubitId], inverse: boo
 /// borrow from it. That drops the leading Toffoli and one pad per call.
 fn diag_spread(circ: &mut Builder, x: &[QubitId], product: &[QubitId], inverse: bool) {
     let m = x.len();
-    let pads = circ.alloc_qubits(m - 1);
-    let mut value = Vec::with_capacity(2 * m - 1);
-    value.push(x[0]);
-    for i in 1..m {
+    // Bits below `j0` are already in the product -- [`diag_preload`] put them
+    // there for free. With the knob off `j0` is 0 and this is the whole term.
+    let j0 = diag_split(m);
+    let k = m - j0;
+    if super::env_flag("SQ_SPARSE_SPREAD") {
+        let map: Vec<Vec<QubitId>> = (0..2*k-1).map(|i| {
+            if i % 2 == 0 { vec![x[j0+i/2]] } else { Vec::new() }
+        }).collect();
+        sparse_diag_add(circ, &map, &product[2*j0+1..], inverse, false);
+        return;
+    }
+    let pads = circ.alloc_qubits(k - 1);
+    let mut value = Vec::with_capacity(2 * k - 1);
+    value.push(x[j0]);
+    for i in 1..k {
         value.push(pads[i - 1]);
-        value.push(x[i]);
+        value.push(x[j0 + i]);
     }
-    addsub_full(circ, &value, &product[1..], inverse);
+    if inverse && super::env_flag("SQ_ZERO_TOP_SPREAD") {
+        // After removing the diagonal corrections only row outputs remain;
+        // no triangular row ever reached product[2m-1].
+        super::modular::addsub_wide_known_top(circ,&value,&product[2*j0+1..],true,Carry0::Full,Carry1::Full,false);
+    } else {addsub_full(circ, &value, &product[2 * j0 + 1..], inverse);}
     circ.free_vec(&pads);
 }
 
@@ -110,6 +196,15 @@ fn diag_spread(circ: &mut Builder, x: &[QubitId], product: &[QubitId], inverse:
 /// half is Clifford, which saves an (m-1)-Toffoli carry ladder per correction.
 fn diag_correction(circ: &mut Builder, x: &[QubitId], product: &[QubitId], inverse: bool) {
     let m = x.len();
+    if super::env_flag("SQ_SPARSE_CORRECTION") {
+        let one = circ.alloc_qubit(); circ.x(one);
+        let mut map: Vec<Vec<QubitId>> = x.iter().map(|&q| vec![q]).collect();
+        for &q in x.iter().take(m-1) { map.push(vec![q, one]); }
+        map.push(Vec::new());
+        sparse_diag_add(circ, &map, product, inverse, cut_sqident() && 2*m >= 4);
+        circ.x(one); circ.free(one);
+        return;
+    }
     let pads = circ.alloc_qubits(m);
     for i in 0..m - 1 {
         circ.cx(x[i], pads[i]);
@@ -127,6 +222,62 @@ fn diag_correction(circ: &mut Builder, x: &[QubitId], product: &[QubitId], inver
     circ.free_vec(&pads);
 }
 
+/// Undo the first row after all subsequent rows have been removed. Its output
+/// is the affine diagonal preload. Inside the subtraction/complement frame,
+/// output[j] = preload[j+1] XOR original_x0 for j<m-1, and output[m-1]=1.
+/// Those expressions recover every owned arithmetic carry without an AND.
+/// Keep the generic terminal CCX and measured carry unwind; scratch is unchanged.
+fn row0_inverse_known(circ:&mut Builder,x:&[QubitId],row:&[QubitId],borrowed:Option<&[QubitId]>) {
+    let m=x.len();let k=m-1;assert_eq!(row.len(),m);
+    circ.x(x[0]); // the ordinary row's complemented control
+    circ.cx(x[0],row[k]);
+    circ.cx_all(x[0],&row[..k]);
+    circ.x_all(row); // addsub_wide's subtraction frame
+    let mut output=Vec::with_capacity(m);
+    for j in 0..m {
+        // The preload's lowest bit is original_x0, hence this framed output
+        // bit is zero. x[0] itself is currently complemented.
+        if j==0 {output.push((false,Vec::new()));continue;}
+        let mut sources=Vec::new();
+        if j<k {
+            sources.push(x[0]);
+            if j%2==0 && j/2<diag_split(m) {sources.push(x[j/2]);}
+        }
+        output.push((true,sources));
+    }
+    super::modular::add_wide_known_output(circ,&x[1..],row,&output,borrowed);
+    circ.x_all(row);
+    circ.cx_all(x[0],&row[..k]);
+    circ.x(x[0]);
+}
+
+/// Exact full-width addition of the diagonal's XOR expressions, without an
+/// interleaved zero register or a copied complemented high half. The first
+/// carry stays separate from aliased source bits throughout the mapped add.
+fn sparse_diag_add(circ: &mut Builder, map: &[Vec<QubitId>], acc: &[QubitId],
+                   inverse: bool, first_copies_source: bool) {
+    assert_eq!(map.len(), acc.len()); assert!(!acc.is_empty());
+    assert_eq!(map[0].len(), 1);
+    if acc.len()==1 { circ.cx(map[0][0],acc[0]); return; }
+    if inverse { circ.x_all(acc); }
+    let source0=map[0][0]; let first=circ.alloc_qubit();
+    if first_copies_source { circ.cx(source0, first); }
+    else { circ.ccx(source0, acc[0], first); }
+    circ.cx(source0, acc[0]);
+    let n=acc.len()-1;
+    let room=super::pingpong::walk_max_qubits().saturating_sub(circ.active_qubits() as usize);
+    let plan=(room..=n.max(room)).find_map(|r|super::width_composition::direct_plan(n,r)).unwrap();
+    super::width_composition::direct_add(circ, &map[1..], &acc[1..], first, &plan);
+    if first_copies_source { circ.cx(source0, first); }
+    else {
+        circ.cx(source0, acc[0]);
+        let bit=circ.alloc_bit();circ.hmr(first,bit);circ.cz_if(source0,acc[0],bit);circ.free_bit(bit);
+        circ.cx(source0, acc[0]);
+    }
+    circ.free(first);
+    if inverse { circ.x_all(acc); }
+}
+
 /// Truncated fold of `value` at `shift`: carries past [`fold_guard`] bits of
 /// headroom above the operand are discarded. Same knob and same meaning as the
 /// headroom [`super::modular::f_slice`] leaves above `f`; this one just sits
@@ -199,6 +350,9 @@ struct K2Retained {
     cross: Vec<QubitId>,
     low: Option<Box<K2Retained>>,
     sum: Option<Box<K2Retained>>,
+    /// The high half's own retained scratch, when [`sq_split_b_min`] split it.
+    high: Option<Box<K2Retained>>,
+    cross_phase: Option<(super::width_composition::Plan,Vec<(usize,BitId)>)>,
 }
 
 /// Recursion policy: a sum half of at least this many bits is split again
@@ -211,6 +365,32 @@ pinned_env!(sq_split_sum_min, "SQ_SPLIT_SUM_MIN");
 /// until the inverse -- so `a` must be consumed (into `t = a + b`) before its
 /// split is built. Disabled by pinning it above any half width (>= 129).
 pinned_env!(sq_split_low_min, "SQ_SPLIT_LOW_MIN");
+/// Same policy for the HIGH half `b`, and the one that needs a restore.
+///
+/// `b` has to be pristine one line below its own square, where `t = a + b` is
+/// formed in its wires -- and a split leaves its input holding that same
+/// in-place sum until its inverse. So a split `b` is undone at once with one
+/// subtract and re-formed just before its own inverse: two adds of `|b|/2 + 1`
+/// bits against the level's saving. That restore is one subtract only while the
+/// split does not recurse, because a recursive split leaves two more in-place
+/// sums under it -- hence [`tri_square_k2r_flat`]. Unset means never, which is
+/// the shipped head.
+fn sq_split_b_min() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    *SLOT.get_or_init(|| super::optional_env("SQ_SPLIT_B_MIN").unwrap_or(usize::MAX))
+}
+
+// Public build-time policy context, restored by with_square. It changes only
+// exact integer producer trees; each inverse follows its retained tree.
+thread_local! { static OUTER_SQUARE_POLICY: std::cell::Cell<Option<usize>> = const { std::cell::Cell::new(None) }; }
+fn policy_min(bit: usize, default: usize) -> usize {
+    OUTER_SQUARE_POLICY.with(|p| match p.get() {
+        None => default,
+        Some(mask) => if mask & (1 << bit) != 0 {
+            if bit == 1 { 65 } else { 64 }
+        } else { usize::MAX },
+    })
+}
 
 fn square_half(circ: &mut Builder, x: &[QubitId], product: &[QubitId], min: usize) -> Option<Box<K2Retained>> {
     if x.len() >= min {
@@ -221,6 +401,38 @@ fn square_half(circ: &mut Builder, x: &[QubitId], product: &[QubitId], min: usiz
     }
 }
 
+/// `b^2` into the high half of the product, from the pristine `b`, restoring
+/// `b` before returning. See [`sq_split_b_min`] for why the restore is here and
+/// not in the inverse, and why the split underneath it does not recurse.
+fn square_b(circ: &mut Builder, bs: &[QubitId], b2: &[QubitId]) -> Option<Box<K2Retained>> {
+    if bs.len() < policy_min(2, sq_split_b_min()) {
+        tri_square(circ, bs, b2, false);
+        return None;
+    }
+    let r = tri_square_k2r_flat(circ, bs, b2);
+    let (a, inner) = bs.split_at(bs.len() / 2);
+    let mut t = inner.to_vec();
+    t.push(r.carry);
+    restore_square_sum(circ,a,&t);
+    Some(Box::new(r))
+}
+
+/// Inverse of [`square_b`]: put the in-place sum back, then run the split's own
+/// inverse, which is the ordinary one -- a flat node's `low`/`sum` are `None`,
+/// so it reduces to two triangular inverses.
+fn square_b_inv(circ: &mut Builder, bs: &[QubitId], b2: &[QubitId], retained: Option<Box<K2Retained>>) {
+    match retained {
+        None => tri_square(circ, bs, b2, true),
+        Some(r) => {
+            let (a, inner) = bs.split_at(bs.len() / 2);
+            let mut t = inner.to_vec();
+            t.push(r.carry);
+            add_wide(circ, a, &t);
+            tri_square_k2r_inv(circ, bs, b2, *r);
+        }
+    }
+}
+
 fn square_half_inv(circ: &mut Builder, x: &[QubitId], product: &[QubitId], retained: Option<Box<K2Retained>>) {
     match retained {
         Some(r) => tri_square_k2r_inv(circ, x, product, *r),
@@ -243,13 +455,81 @@ fn square_half_inv(circ: &mut Builder, x: &[QubitId], product: &[QubitId], retai
 /// truncated comparison, windowed fold or measured chunk boundary — the
 /// per-shot failure site count is unchanged in both channels by construction.
 fn tri_square_k2r(circ: &mut Builder, x: &[QubitId], product: &[QubitId]) -> K2Retained {
+    tri_square_k2r_inner(circ, x, product, false)
+}
+
+/// The same node with no recursion under it: `a`, `t` and `b` are all squared
+/// triangularly. [`square_b`] builds on this, because its restore is one
+/// subtract only while nothing below it has left an in-place sum of its own.
+fn tri_square_k2r_flat(circ: &mut Builder, x: &[QubitId], product: &[QubitId]) -> K2Retained {
+    tri_square_k2r_inner(circ, x, product, true)
+}
+
+/// The exact 2ab cross term has bit0=0. If its wide assembly ladder binds,
+/// reuse that zero source bit as the incoming carry to an exact chunk plan.
+/// Retain all internal boundary carries and pay their full phase cleanup.
+/// No fold/comparison truncation window is changed by this helper.
+fn add_cross(circ:&mut Builder,cross:&[QubitId],acc:&[QubitId],inverse:bool,
+    recover:Option<(super::width_composition::Plan,Vec<(usize,BitId)>)>)
+    ->Option<(super::width_composition::Plan,Vec<(usize,BitId)>)> {
+    let room=super::pingpong::walk_max_qubits().saturating_sub(circ.active_qubits()as usize);
+    if recover.is_some() || (super::env_flag("SQ_FIT_CROSS") && acc.len().saturating_sub(2)>room) {
+        if inverse {circ.x_all(acc);}
+        let n=acc.len()-1;
+        let(plan,fixes)=recover.unwrap_or_else(||((room..=room.max(n)).find_map(|r|super::width_composition::direct_plan(n,r)).unwrap(),Vec::new()));
+        let map:Vec<Vec<QubitId>>=(1..acc.len()).map(|i|cross.get(i).copied().into_iter().collect()).collect();
+        // bit0 of the source is zero, so acc[0] and the first carry stay put.
+        let defer=!inverse && super::env_flag("SQ_DEFER_CROSS_PHASE");
+        let pending=super::width_composition::direct_add_phase_transport(circ,&map,&acc[1..],cross[0],&plan,defer,&fixes);
+        if inverse {circ.x_all(acc);}
+        if super::env_flag("SQ_FIT_CROSS_TRACE") {eprintln!("FIT_CROSS {} {} {} {} {}",acc.len(),room,plan.peak,plan.extra2,inverse as u8);}
+        if defer{return Some((plan,pending));}
+    } else if cut_sqident() {
+        addsub_wide_low(circ,cross,acc,inverse,Carry0::Zero,Carry1::Full);
+    } else {addsub_wide(circ,cross,acc,inverse);}
+    None
+}
+
+/// The full sum is exactly a+b; removing a restores b and clears its extra
+/// top carry for every bitstring, independent of upstream field errors.
+fn restore_square_sum(circ:&mut Builder,a:&[QubitId],t:&[QubitId]) {
+    if super::env_flag("SQ_ZERO_TOP_SUM") {
+        super::modular::addsub_wide_known_top(circ,a,t,true,Carry0::Full,Carry1::Full,false);
+    } else {sub_wide(circ,a,t);}
+}
+
+/// Parent cross assembly does not read any child's retained cross scratch,
+/// or product bits below the assembly offset. Child low/top bits are zero;
+/// product[1] is zero for any square, and product[0] copies the stable x[0].
+/// Return the same identities before any child inverse or product consumer.
+fn assembly_loans(circ:&mut Builder,x:&[QubitId],product:&[QubitId],
+    low:Option<&K2Retained>,sum:Option<&K2Retained>,high:Option<&K2Retained>)->Vec<QubitId>{
+    if !super::env_flag("SQ_LEND_ASSEMBLY_ZEROS") || x.len()/2<2{return Vec::new();}
+    let lo=x.len()/2;let hi=x.len()-lo;let mut qs=vec![product[0],product[1]];
+    if let Some(r)=low{retained_zero_bits(r,lo,&mut qs);}
+    if let Some(r)=sum{retained_zero_bits(r,hi+1,&mut qs);}
+    if let Some(r)=high{retained_zero_bits(r,hi,&mut qs);}
+    circ.cx(x[0],product[0]);
+    for &q in &qs{circ.release_clean(q);}qs
+}
+fn assembly_repay(circ:&mut Builder,x:&[QubitId],product:&[QubitId],qs:Vec<QubitId>){
+    if qs.is_empty(){return;}
+    for q in qs{circ.reacquire(q);}circ.cx(x[0],product[0]);
+}
+
+fn tri_square_k2r_inner(circ: &mut Builder, x: &[QubitId], product: &[QubitId], flat: bool) -> K2Retained {
     let m = x.len();
     assert_eq!(product.len(), 2 * m);
     let lo = m / 2;
     let (a, bs) = x.split_at(lo);
     let (a2, b2) = product.split_at(2 * lo);
     // b^2 straight into the high half of the zeroed product, from the pristine b.
-    tri_square(circ, bs, b2, false);
+    let high = if flat {
+        tri_square(circ, bs, b2, false);
+        None
+    } else {
+        square_b(circ, bs, b2)
+    };
     // t = a + b, in place: b's own wires plus one carry.
     let carry = circ.alloc_qubit();
     let mut t = bs.to_vec();
@@ -257,25 +537,31 @@ fn tri_square_k2r(circ: &mut Builder, x: &[QubitId], product: &[QubitId]) -> K2R
     add_wide(circ, a, &t);
     // a^2 into the low half; a may now be split since nothing reads it again
     // before the inverse.
-    let low = square_half(circ, a, a2, sq_split_low_min());
+    let low = if flat { tri_square(circ, a, a2, false); None }
+              else { square_half(circ, a, a2, policy_min(0, sq_split_low_min())) };
     // cross = t^2, then subtract the still-pure halves to leave 2ab. Both
     // intermediates are nonnegative (t^2 - a^2 = 2ab + b^2 >= 0), so the
     // two's-complement frame never wraps at this width.
     let cross = circ.alloc_qubits(2 * t.len());
-    let sum = square_half(circ, &t, &cross, sq_split_sum_min());
+    let sum = if flat { tri_square(circ, &t, &cross, false); None }
+              else { square_half(circ, &t, &cross, policy_min(1, sq_split_sum_min())) };
     if cut_sqident() {
         addsub_wide_low(circ, a2, &cross, true, Carry0::Full, Carry1::CopiesCarry0);
-        addsub_wide_low(circ, b2, &cross, true, Carry0::Zero, Carry1::CopiesCarry0);
     } else {
         sub_wide(circ, a2, &cross);
-        sub_wide(circ, b2, &cross);
     }
+    if super::env_flag("SQ_ZERO_TOP_CROSS") {
+        // 2ab < 2^(lo+hi+1), while cross has 2*(hi+1) bits: its top is zero.
+        let (c0,c1)=if cut_sqident(){(Carry0::Zero,Carry1::CopiesCarry0)}else{(Carry0::Full,Carry1::Full)};
+        super::modular::addsub_wide_known_top(circ,b2,&cross,true,c0,c1,false);
+    } else if cut_sqident() {addsub_wide_low(circ,b2,&cross,true,Carry0::Zero,Carry1::CopiesCarry0);}
+    else {sub_wide(circ,b2,&cross);}
     // product += 2ab << lo, exact full ripple to the top (x^2 < 2^(2m), so the
     // top never overflows).
-    if cut_sqident() {
-        addsub_wide_low(circ, &cross, &product[lo..], false, Carry0::Zero, Carry1::Full);
-    } else { add_wide(circ, &cross, &product[lo..]); }
-    K2Retained { carry, cross, low, sum }
+    let loans=assembly_loans(circ,x,product,low.as_deref(),sum.as_deref(),high.as_deref());
+    let cross_phase=add_cross(circ,&cross,&product[lo..],false,None);
+    assembly_repay(circ,x,product,loans);
+    K2Retained { carry, cross, low, sum, high, cross_phase }
 }
 
 /// Inverse of `tri_square_k2r`, consuming its retained scratch. Requires
@@ -288,16 +574,16 @@ fn tri_square_k2r_inv(
 ) {
     let m = x.len();
     assert_eq!(product.len(), 2 * m);
-    let K2Retained { carry, cross, low, sum } = retained;
+    let K2Retained { carry, cross, low, sum, high, cross_phase } = retained;
     let lo = m / 2;
     let (a, bs) = x.split_at(lo);
     let (a2, b2) = product.split_at(2 * lo);
     let mut t = bs.to_vec();
     t.push(carry);
     // product -= 2ab << lo: the halves are pure a^2 / b^2 again.
-    if cut_sqident() {
-        addsub_wide_low(circ, &cross, &product[lo..], true, Carry0::Zero, Carry1::Full);
-    } else { sub_wide(circ, &cross, &product[lo..]); }
+    let loans=assembly_loans(circ,x,product,low.as_deref(),sum.as_deref(),high.as_deref());
+    assert!(add_cross(circ,&cross,&product[lo..],true,cross_phase).is_none());
+    assembly_repay(circ,x,product,loans);
     // cross: 2ab -> t^2, then clear it with the inverse square (which also
     // restores t if its own split modified it).
     if cut_sqident() {
@@ -312,9 +598,55 @@ fn tri_square_k2r_inv(
     // Clear a^2, restoring a first if it was split, then uncompute t = a + b:
     // t - a = b < 2^|b|, so the carry wire returns to |0>.
     square_half_inv(circ, a, a2, low);
-    sub_wide(circ, a, &t);
+    restore_square_sum(circ,a,&t);
     circ.free(carry);
-    tri_square(circ, bs, b2, true);
+    square_b_inv(circ, bs, b2, high);
+}
+
+/// Retained cross terms are exactly 2ab. Their low bit and unused high bit(s)
+/// are zero for every input. These wires are not product/consumer operands.
+fn retained_zero_bits(r:&K2Retained,m:usize,out:&mut Vec<QubitId>) {
+    let lo=m/2;let hi=m-lo;let n=r.cross.len();
+    out.push(r.cross[0]);out.push(r.cross[n-1]);
+    if lo<hi{out.push(r.cross[n-2]);}
+    if let Some(q)=r.low.as_ref(){retained_zero_bits(q,lo,out);}
+    if let Some(q)=r.sum.as_ref(){retained_zero_bits(q,hi+1,out);}
+    if let Some(q)=r.high.as_ref(){retained_zero_bits(q,hi,out);}
+}
+
+/// For a node retaining t=a+b in its high input half, bit1 of 2ab is
+/// a0*b0 = a0 AND NOT t0. Low/sum children retain this same source frame.
+/// A high child was restored and overwritten by its parent's sum; skip it.
+fn retained_and_bits(r:&K2Retained,x:&[QubitId],out:&mut Vec<(QubitId,QubitId,QubitId)>) {
+    let lo=x.len()/2;
+    out.push((r.cross[1],x[0],x[lo]));
+    if let Some(q)=r.low.as_ref(){retained_and_bits(q,&x[..lo],out);}
+    if let Some(q)=r.sum.as_ref(){let mut t=x[lo..].to_vec();t.push(r.carry);retained_and_bits(q,&t,out);}
+}
+
+/// Consumer-only W61 loan. No high edge: square_b restores that child's
+/// source frame, which its parent subsequently overwrites with a sum.
+#[derive(Clone,Copy,Debug)]
+struct Cross2Loan { q:QubitId, a0:QubitId, a1:QubitId, t0:QubitId, t1:QubitId }
+fn retained_cross2_bits(r:&K2Retained,x:&[QubitId],out:&mut Vec<Cross2Loan>) {
+    assert!(matches!(x.len(),64|65|66|128|129),"W61 only proves the production-sized retained frames");
+    let lo=x.len()/2;
+    // These allowed shapes and their actual retained children never modify
+    // either input half's first two bits. Recurse only through proved frames.
+    out.push(Cross2Loan{q:r.cross[2],a0:x[0],a1:x[1],t0:x[lo],t1:x[lo+1]});
+    if let Some(q)=r.low.as_ref(){retained_cross2_bits(q,&x[..lo],out);}
+    if let Some(q)=r.sum.as_ref(){let mut t=x[lo..].to_vec();t.push(r.carry);retained_cross2_bits(q,&t,out);}
+}
+fn cross2_erase(circ:&mut Builder,l:Cross2Loan) {
+    // cross[2] = a0*t1 ^ a1*t0 ^ a0*t0 ^ a0, for t=a+b.
+    let m=circ.alloc_bit();circ.hmr(l.q,m);
+    circ.cz_if(l.a0,l.t1,m);circ.cz_if(l.a1,l.t0,m);
+    circ.cz_if(l.a0,l.t0,m);circ.z_if(l.a0,m);circ.free_bit(m);
+}
+fn cross2_restore(circ:&mut Builder,l:Cross2Loan) {
+    // Two products after an exactly restored Clifford source-frame change.
+    circ.cx(l.t0,l.t1);circ.x(l.t1);circ.ccx(l.a0,l.t1,l.q);
+    circ.x(l.t1);circ.cx(l.t0,l.t1);circ.ccx(l.a1,l.t0,l.q);
 }
 
 /// Materialise `x^2` in a fresh register, run `folds` against it, then uncompute
@@ -324,12 +656,50 @@ fn tri_square_k2r_inv(
 /// folds that consume it, and `tri_square_k2r`'s retained scratch makes the
 /// uncompute exact rather than a second square. Having the three uses go through
 /// here means a fold cannot be added without its inverse, or a register leaked.
-fn with_square(circ: &mut Builder, x: &[QubitId], folds: impl FnOnce(&mut Builder, &[QubitId])) {
+fn with_square(circ: &mut Builder, x: &[QubitId], policy_name: &str, folds: impl FnOnce(&mut Builder, &[QubitId])) {
+    let price_branches=super::env_flag("SQ_MODEL_BRANCHES");
+    if price_branches {circ.set_phase(match policy_name{"SQ_A_POLICY"=>"square_a","SQ_B_POLICY"=>"square_b","SQ_C_POLICY"=>"square_c",_=>"square_test"});}
+    let old_policy = OUTER_SQUARE_POLICY.with(|p| p.replace(super::optional_env::<usize>(policy_name)));
     let product = circ.alloc_qubits(2 * x.len());
     let retained = tri_square_k2r(circ, x, &product);
-    folds(circ, &product);
+    let mut loans=Vec::new();
+    if super::env_flag("SQ_LEND_RETAINED_ZEROS"){retained_zero_bits(&retained,x.len(),&mut loans);}
+    let branch=match policy_name{"SQ_A_POLICY"=>1,"SQ_B_POLICY"=>2,"SQ_C_POLICY"=>4,_=>7};
+    let and_mask=super::optional_env::<usize>("SQ_LEND_RETAINED_ANDS").unwrap_or(0);
+    let mut and_loans=Vec::new();
+    if and_mask&branch!=0{retained_and_bits(&retained,x,&mut and_loans);}
+    let cross2_mask=super::optional_env::<usize>("SQ_LEND_RETAINED_CROSS2").unwrap_or(0);
+    assert!(cross2_mask<=7,"W61 branch mask must be in 0..=7");
+    let mut cross2_loans=Vec::new();
+    if cross2_mask&branch!=0{retained_cross2_bits(&retained,x,&mut cross2_loans);}
+    for &(q,a,t)in &and_loans{
+        let m=circ.alloc_bit();circ.hmr(q,m);circ.x(t);circ.cz_if(a,t,m);circ.x(t);circ.free_bit(m);loans.push(q);
+    }
+    // x[0] is unchanged by the in-place Karatsuba sums. Product bit0 equals
+    // that bit, so the consumer may read it directly through a source alias.
+    let alias=super::env_flag("SQ_ALIAS_PRODUCT_LSB");
+    let mut consumer_product=product.clone();
+    if alias{circ.cx(x[0],product[0]);loans.push(product[0]);consumer_product[0]=x[0];}
+    for &l in &cross2_loans{cross2_erase(circ,l);loans.push(l.q);}
+    if !cross2_loans.is_empty(){
+        let ids:std::collections::HashSet<_>=loans.iter().map(|q|q.0).collect();
+        assert_eq!(ids.len(),loans.len(),"W61 duplicate loan target");
+        for l in &cross2_loans {
+            for q in [l.a0,l.a1,l.t0,l.t1]{assert!(!ids.contains(&q.0),"W61 control is being loaned");}
+        }
+    }
+    for &q in &loans{circ.release_clean(q);}
+    folds(circ, &consumer_product);
+    // Every consumer restores its temporary work and source. Reclaim the same
+    // physical wire identities before the retained inverse consumes them.
+    for &q in &loans{circ.reacquire(q);}
+    for &(q,a,t)in &and_loans{circ.x(t);circ.ccx(a,t,q);circ.x(t);}
+    for &l in &cross2_loans{cross2_restore(circ,l);}
+    if alias{circ.cx(x[0],product[0]);}
     tri_square_k2r_inv(circ, x, &product, retained);
     circ.free_vec(&product);
+    OUTER_SQUARE_POLICY.with(|p| p.set(old_policy));
+    if price_branches {circ.set_phase("square_between");}
 }
 
 pub fn sub_square(circ: &mut Builder, out: &[QubitId], y: &[QubitId]) {
@@ -341,12 +711,12 @@ pub fn sub_square(circ: &mut Builder, out: &[QubitId], y: &[QubitId]) {
     // y = a + b*2^h, so y^2 = A + (C - A - B)*2^h + B*2^256 with A = a^2,
     // B = b^2, C = (a+b)^2. Five folds, and this routine subtracts, so every
     // sign below is the negation of that expansion.
-    with_square(circ, y_lo, |circ, a2| {
+    with_square(circ, y_lo, "SQ_A_POLICY", |circ, a2| {
         mod_addsub(circ, true, a2, out);
         fold_shifted(circ, false, a2, out, h);
     });
 
-    with_square(circ, y_hi, |circ, b2| {
+    with_square(circ, y_hi, "SQ_B_POLICY", |circ, b2| {
         fold_shifted(circ, false, b2, out, h);
         fold_times_f(circ, true, b2, out);
     });
@@ -361,15 +731,12 @@ pub fn sub_square(circ: &mut Builder, out: &[QubitId], y: &[QubitId]) {
 
     // C is 258 bits, so its high limb overhangs the rotate by two bits; those
     // ride in on a separate window add at the same shift.
-    with_square(circ, &sum, |circ, c2| {
+    with_square(circ, &sum, "SQ_C_POLICY", |circ, c2| {
         fold_rotated(circ, true, &c2[..h], &c2[h..], out);
         window_add(circ, true, &c2[2 * h..], out, h);
     });
 
-    sub_wide(circ, y_lo, &sum);
+    restore_square_sum(circ,y_lo,&sum);
     circ.free(sum_carry);
 }
 
-#[cfg(test)]
-#[path="a2_square_tests.rs"]
-mod a2_tests;
diff --git a/src/point_add/truth_simplify.rs b/src/point_add/truth_simplify.rs
index 0fd2a26..bd58430 100644
--- a/src/point_add/truth_simplify.rs
+++ b/src/point_add/truth_simplify.rs
@@ -355,6 +355,3 @@ fn simplify_with_products(ops: Vec<Op>, use_products: bool) -> Vec<Op> {
     result
 }
 
-#[cfg(test)]
-#[path = "truth_simplify_tests.rs"]
-mod tests;
diff --git a/src/point_add/width_composition.rs b/src/point_add/width_composition.rs
new file mode 100644
index 0000000..c499fcb
--- /dev/null
+++ b/src/point_add/width_composition.rs
@@ -0,0 +1,193 @@
+//! Exact low-workspace replacements. No finite-window policy is changed here.
+use super::{Builder, compare, modular};
+use crate::circuit::{QubitId,BitId};
+use std::collections::HashMap;
+use std::sync::{Mutex, OnceLock};
+
+#[derive(Clone,Debug)]
+pub(crate) struct Plan { pub sizes: Vec<usize>, pub slow: bool, pub extra2: usize, pub peak: usize }
+
+pub(crate) fn plan(n:usize, room:usize)->Option<Plan> {
+    static CACHE:OnceLock<Mutex<HashMap<(usize,usize),Option<Plan>>>>=OnceLock::new();
+    let cache=CACHE.get_or_init(||Mutex::new(HashMap::new()));
+    if let Some(p)=cache.lock().unwrap().get(&(n,room)){return p.clone();}
+    let mut best:Option<Plan>=None;
+    let mut offer=|sizes:Vec<usize>,slow:bool,extra2:usize,peak:usize|{
+        assert_eq!(sizes.iter().sum::<usize>(),n);assert!(peak<=room);
+        let key=(extra2,peak,sizes.len());
+        if best.as_ref().is_none_or(|p|key<(p.extra2,p.peak,p.sizes.len())) {best=Some(Plan{sizes,slow,extra2,peak});}
+    };
+    if room>=n {offer(vec![n],false,0,n);} else {
+        for k in 2..=n.min(room) {
+            let caps:Vec<_>=(0..k).map(|j|room-j).collect();
+            if caps.iter().sum::<usize>()<n {continue;}
+            let last=caps[k-1].min(n-k+1);
+            let mut sizes=vec![1;k];sizes[k-1]=last;
+            let mut left=n-sizes.iter().sum::<usize>();
+            for j in 0..k-1{let take=left.min(caps[j]-1);sizes[j]+=take;left-=take;}
+            if left>0{continue;}
+            let peak=sizes.iter().enumerate().map(|(j,w)|j+w).max().unwrap();
+            let extra2=sizes[..k-1].iter().map(|w|w-1).sum();offer(sizes,false,extra2,peak);
+        }
+        if room>=2 {
+            for k in 0..=(n-1).min(room-1) {
+                let caps:Vec<_>=(0..k).map(|j|room-j).collect();
+                let last=n.saturating_sub(caps.iter().sum()).max(1);
+                if last>n-k{continue;}
+                let mut sizes=vec![1;k+1];sizes[k]=last;
+                let mut left=n-sizes.iter().sum::<usize>();
+                for j in 0..k{let take=left.min(caps[j]-1);sizes[j]+=take;left-=take;}
+                if left>0{continue;}
+                let peak=sizes[..k].iter().enumerate().map(|(j,w)|j+w).chain(std::iter::once(if k==0{2}else{k+1})).max().unwrap();
+                let extra2=2*last+sizes[..k].iter().map(|w|w-1).sum::<usize>();offer(sizes,true,extra2,peak);
+            }
+        }
+    }
+    cache.lock().unwrap().insert((n,room),best.clone());best
+}
+
+fn erase_release(c:&mut Builder,q:QubitId,a:&[QubitId],b:&[QubitId],incoming:Option<QubitId>){
+    let m=c.alloc_bit();c.hmr(q,m);c.release_clean(q);
+    c.push_condition(m);
+    if b.len()>1 {compare::cmp_lt_phase(c,b,a,incoming);} else {
+        c.x(b[0]);c.cz(a[0],b[0]);
+        if let Some(p)=incoming{c.cz(a[0],p);c.cz(b[0],p);}
+        c.x(b[0]);
+    }
+    c.pop_condition();c.free_bit(m);
+}
+
+fn inplace(c:&mut Builder,a:&[QubitId],b:&[QubitId],incoming:Option<QubitId>,out:QubitId){
+    let seed=incoming.unwrap_or_else(||c.alloc_qubit());
+    for i in 0..a.len(){let p=if i==0{seed}else{a[i-1]};c.cx(a[i],b[i]);c.cx(a[i],p);c.ccx(p,b[i],a[i]);}
+    c.cx(a[a.len()-1],out);
+    for i in (0..a.len()).rev(){let p=if i==0{seed}else{a[i-1]};c.ccx(p,b[i],a[i]);c.cx(a[i],p);c.cx(p,b[i]);}
+    if incoming.is_none(){c.release_clean(seed);}
+}
+
+pub(crate) fn add(c:&mut Builder,a:&[QubitId],b:&[QubitId],p:&Plan)->QubitId{
+    add_with_carry(c,a,b,None,p)
+}
+
+/// Same exact adder with a live, preserved incoming carry. Its wire is part
+/// of the caller's base, so the existing workspace plan is unchanged.
+pub(crate) fn add_with_carry(c:&mut Builder,a:&[QubitId],b:&[QubitId],initial:Option<QubitId>,p:&Plan)->QubitId{
+    assert_eq!(a.len(),b.len());assert_eq!(p.sizes.iter().sum::<usize>(),a.len());
+    let base=c.active_qubits();let mut at=0;let mut incoming=initial;let mut flags=Vec::new();
+    for (j,&w) in p.sizes.iter().enumerate(){
+        let out=c.alloc_qubit();let end=at+w;
+        if p.slow && j+1==p.sizes.len(){inplace(c,&a[at..end],&b[at..end],incoming,out);}
+        else {modular::ripple_add(c,&a[at..end],&b[at..end],incoming,Some(out));}
+        if j+1<p.sizes.len(){flags.push((at,end,incoming,out));}
+        incoming=Some(out);at=end;
+    }
+    for (lo,hi,prev,q) in flags.into_iter().rev(){erase_release(c,q,&a[lo..hi],&b[lo..hi],prev);}
+    assert_eq!(c.active_qubits(),base+1);incoming.unwrap()
+}
+
+pub(crate) fn mapped_peak(n:usize,chunk:usize)->usize{
+    let buffer=n.min(chunk);let count=n.div_ceil(chunk);
+    (0..count).map(|j|{
+        let w=chunk.min(n-j*chunk);
+        // j incoming boundaries; nonfinal out and w-1 ladder, or wrapped w-2.
+        buffer+j+if j+1<count{w}else{w.saturating_sub(2)}
+    }).max().unwrap()
+}
+
+pub(crate) fn mapped_extra2(n:usize,chunk:usize)->usize{
+    let count=n.div_ceil(chunk);(0..count-1).map(|_|chunk-1).sum()
+}
+
+fn copy(c:&mut Builder,map:&[Vec<QubitId>],buf:&[QubitId]){
+    for (bits,&q) in map.iter().zip(buf){for &bit in bits{c.cx(bit,q);}}
+}
+
+/// b += XOR-mapped source + incoming, modulo 2^n. Source and incoming restored.
+pub(crate) fn mapped_add(c:&mut Builder,map:&[Vec<QubitId>],b:&[QubitId],incoming:QubitId,chunk:usize){
+    assert_eq!(map.len(),b.len());let base=c.active_qubits();
+    let buffer=c.alloc_qubits(chunk.min(b.len()));let mut stages=Vec::new();
+    let mut at=0;let mut prev=Some(incoming);
+    while at<b.len(){
+        let end=(at+chunk).min(b.len());let src=&map[at..end];let tmp=&buffer[..end-at];
+        copy(c,src,tmp);let out=if end<b.len(){Some(c.alloc_qubit())}else{None};
+        modular::ripple_add(c,tmp,&b[at..end],prev,out);copy(c,src,tmp);
+        if let Some(q)=out{stages.push((at,end,prev,q));}prev=out;at=end;
+    }
+    for (lo,hi,prev,q) in stages.into_iter().rev(){
+        let src=&map[lo..hi];let tmp=&buffer[..hi-lo];copy(c,src,tmp);
+        erase_release(c,q,tmp,&b[lo..hi],prev);copy(c,src,tmp);
+    }
+    for q in buffer{c.release_clean(q);}assert_eq!(c.active_qubits(),base);
+}
+
+pub(crate) fn direct_plan(n:usize,room:usize)->Option<Plan>{
+    let mut best:Option<Plan>=None;
+    for k in 1..=n.min(room+1){
+        let mut caps:Vec<_>=(0..k-1).map(|j|room-j).collect();caps.push(room-(k-1)+2);
+        if caps.contains(&0)||caps.iter().sum::<usize>()<n{continue;}
+        let mut sizes=vec![1;k];sizes[k-1]=caps[k-1].min(n-k+1);
+        let mut left=n-sizes.iter().sum::<usize>();
+        for j in 0..k-1{let d=left.min(caps[j]-1);sizes[j]+=d;left-=d;}
+        if left>0{continue;}
+        let extra2=sizes[..k-1].iter().map(|w|w-1).sum();
+        let peak=sizes.iter().enumerate().map(|(j,w)|j+if j+1<k{*w}else{w.saturating_sub(2)}).max().unwrap();
+        if best.as_ref().is_none_or(|p|(extra2,peak,k)<(p.extra2,p.peak,p.sizes.len())){best=Some(Plan{sizes,slow:false,extra2,peak});}
+    }best
+}
+
+fn mapped_compare(c:&mut Builder,map:&[Vec<QubitId>],b:&[QubitId],incoming:QubitId){
+    use super::pingpong::{fold_step,with_selector_xor};
+    let n=b.len();let carries=c.alloc_qubits(n-1);c.x_all(b);
+    for i in 0..n-1{let prev=if i==0{incoming}else{carries[i-1]};fold_step(c,b[i],prev,carries[i],&map[i],false);}
+    let prev=if n==1{incoming}else{carries[n-2]};
+    if map[n-1].is_empty(){c.cz(b[n-1],prev);}else{
+        with_selector_xor(c,&map[n-1],prev,|c,s|{c.cz(b[n-1],s);c.cz(b[n-1],prev);c.cz(s,prev);});
+    }
+    for i in (0..n-1).rev(){let prev=if i==0{incoming}else{carries[i-1]};
+        with_selector_xor(c,&map[i],prev,|c,s|{
+            c.cx(prev,carries[i]);if s!=prev{c.cx(prev,s);}
+            let m=c.alloc_bit();c.hmr(carries[i],m);c.cz_if(s,b[i],m);c.free_bit(m);
+            if s!=prev{c.cx(prev,s);}c.cx(prev,b[i]);
+        });
+    }
+    c.free_vec(&carries);c.x_all(b);
+}
+
+/// Exact wrapped source-selected add, without materializing a source word.
+pub(crate) fn direct_add(c:&mut Builder,map:&[Vec<QubitId>],b:&[QubitId],incoming:QubitId,p:&Plan){
+    assert!(direct_add_phase_transport(c,map,b,incoming,p,false,&[]).is_empty());
+}
+
+/// Optionally retain classical measurement outcomes instead of comparing to
+/// repair boundary phases. A matching inverse recreates the SAME carries and
+/// applies these deferred Z corrections before normal exact cleanup.
+pub(crate) fn direct_add_phase_transport(c:&mut Builder,map:&[Vec<QubitId>],b:&[QubitId],incoming:QubitId,p:&Plan,defer:bool,recover:&[(usize,BitId)])->Vec<(usize,BitId)>{
+    use super::pingpong::{fold_step,unwind_fold_step};
+    assert_eq!(p.sizes.iter().sum::<usize>(),b.len());let base=c.active_qubits();
+    let mut at=0;let mut prev=incoming;let mut stages=Vec::new();
+    for(j,&w)in p.sizes.iter().enumerate(){let last=j+1==p.sizes.len();let end=at+w;
+        let out=if last{None}else{Some(c.alloc_qubit())};
+        let work=c.alloc_qubits(if last{w.saturating_sub(2)}else{w-1});
+        for i in 0..work.len(){let carry=if i==0{prev}else{work[i-1]};fold_step(c,b[at+i],carry,work[i],&map[at+i],false);}
+        let carry=work.last().copied().unwrap_or(prev);
+        if let Some(q)=out{fold_step(c,b[end-1],carry,q,&map[end-1],true);}else if w==1{
+            c.cx(prev,b[at]);for &s in &map[at]{c.cx(s,b[at]);}
+        }else{
+            fold_step(c,b[end-2],carry,b[end-1],&map[end-2],true);
+            for &s in &map[end-1]{c.cx(s,b[end-1]);}
+        }
+        for i in(0..work.len()).rev(){let carry=if i==0{prev}else{work[i-1]};unwind_fold_step(c,b[at+i],carry,work[i],&map[at+i]);}
+        c.free_vec(&work);
+        if let Some(q)=out{
+            for &(boundary,bit)in recover{if boundary==end{c.z_if(q,bit);c.free_bit(bit);}}
+            stages.push((at,end,prev,q));prev=q;
+        }at=end;
+    }
+    assert!(recover.iter().all(|(hi,_)|stages.iter().any(|(_,end,_,_)|hi==end)));
+    let mut pending=Vec::new();
+    for(lo,hi,cin,q)in stages.into_iter().rev(){let m=c.alloc_bit();c.hmr(q,m);c.release_clean(q);
+        if defer{pending.push((hi,m));}else{c.push_condition(m);mapped_compare(c,&map[lo..hi],&b[lo..hi],cin);c.pop_condition();c.free_bit(m);}
+    }
+    assert_eq!(c.active_qubits(),base);
+    pending
+}
```

