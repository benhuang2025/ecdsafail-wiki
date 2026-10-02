# Dialog GCD, the June route (record the walk, apply it in a separate pass)

> From pldallairedemers' [cddd5df](../commits/cddd5df.md) (2 June) until the trailmix swap [bdb1d22](../commits/bdb1d22.md) (19 June), every frontier commit divided with a *dialog GCD*. A fixed-length binary GCD walk on `(u, v) = (p, a)` writes its branch decisions into a compressed transcript. A separate *apply* pass replays the decisions mod p on a 256-bit pair, which divides by `a` or multiplies by it. A reverse walk then restores `a` and erases the transcript. Each step first halved `v` once. From [0780f67](../commits/0780f67.md) (5 June) it may halve twice (K=2), which cut the walk from 393 to 259 steps. The route started at 1698 × 2,447,846 and ended at 1168 × 1,431,621 ([ba3efc1](../commits/ba3efc1.md)). Nearly every commit in between tunes one of its truncations: step count, width envelope, branch-compare widths, body trims, apply clean compares, fold windows. The later jump-2 port, which applies each step while walking and uses baked per-call tables, is [trailmix-jump-gcd.md](trailmix-jump-gcd.md).

## How it works in this circuit

**Files and shell.** Until [69bd3d7](../commits/69bd3d7.md) (6 June) the route was `emit_dialog_gcd_raw_pa` inside a 30,000–36,000-line `src/point_add/mod.rs`; 69bd3d7 moved it to `rounds/dialog/{mod,compressed,config}.rs` and `arith/`. `emit_dialog_gcd_raw_pa` forms `dx`, `dy`, runs the *quotient* (`ty ← dy/dx = λ`), the x-tail square and `c = ox − x₃`, then the *ipmul* (`ty ← λ·c`). Each GCD use is a forward walk, an apply pass and a reverse walk, so one point addition has **four walks and two apply passes**.

**One walk step** (`…_tobitvector_steps_block_lifecycle`). `u` is loaded with p by X gates. `v` is the caller's factor register. Step `s` touches only the low `w = active_width(s)` bits:

```
b0  ^= v[0]                                    # v odd -> subtract
b01 ^= b0 AND [u > v on the top k(s) bits]     # swap so that u <= v
cswap(b01, u[1..w], v[1..w])                   # lane 0 skipped: u is always odd
if b0: v -= u                                  # v becomes even
v >>= 1                                        # free relabel
K=2:  s2 = NOT v[0];  if s2: v >>= 1           # cswap cascade, about w Toffoli
```

This is Stein's binary GCD; with `gcd = 1` it reaches `(1, 0)` and then idles. Lane 0 is skipped since [0261289](../commits/0261289.md), and bit 0 of the subtract is a CNOT since [ba3efc1](../commits/ba3efc1.md). The compare (2 T/bit, run twice at cddd5df) became measured ([7e660f9](../commits/7e660f9.md)) and fused with the `b01` write ([9b6b9d6](../commits/9b6b9d6.md)): once, 1 T/bit. The subtract body went from a gated load `b0·u` plus measured subtract (cddd5df), to `gated` hosted on the log ([68e3653](../commits/68e3653.md)), to a Gidney-vented controlled Cuccaro ([7689eac](../commits/7689eac.md)).

**K=2 bounded second shift** ([0780f67](../commits/0780f67.md)). It is exact: `s2` is uncomputed by the reverse cascade, and the apply pairs every halving of `v` with one doubling (or halving) of `y`. `v` now shrinks about 0.95 bits per step instead of 0.71, so the slope was refitted (0.95 at first, 1.015–1.017 by mid-June). The transcript gains one bit per step. See [transcript-codecs.md](transcript-codecs.md).

**Width envelope.** `active_width(s) = ceil_even(256 − s·WIDTH_SLOPE_X1000/1000 + WIDTH_MARGIN)`, clamped to 256, plus `WIDTH_STEP_BUMPS`. It began at slope 0.7075, margin 37, and was then cut repeatedly: margin 28 in [8cb350c](../commits/8cb350c.md), 10 at the end, with slopes up to 1.017. Bits above `w` are never touched. That only works if `u` and `v` really are shorter than `w`.

**Branch compare width.** `dialog_gcd_compare_bits_for_step` returns:

- the `COMPARE_STEP_BITS[step]` override, if one is set;
- otherwise `min(PA9024_COMPARE_SCHEDULE[step] + MARGIN, COMPARE_BITS, w)` when the schedule is on;
- otherwise `min(COMPARE_BITS, w)`.

A 399-entry table was turned on by [f8a36ba](../commits/f8a36ba.md) (margin 8, later 5) and off by 0780f67. [69bd3d7](../commits/69bd3d7.md) baked a 258-entry K2 table whose entries are the *observed maximum* of `w − msb(u⊕v)` over 8 M sampled factors; at margin 0 its comment expects about 0.3 compare hazards per draw, left to the nonce. The global cap fell from 75 to 46.

**Body trims and binder notches** (`dialog_gcd_body_carry_trunc_width`). The subtract/add body may run narrower than `w` (cswap and compare keep `w`). `BODY_CARRY_BAND_TRIMS` gives one trim per equal band of steps: 1 bit on steps 200–392 at [cc5584e](../commits/cc5584e.md), finally 26 bands with 3 bits on steps 10–59 and 230–257 and 1 between ([bde4caa](../commits/bde4caa.md)). The early full-width steps bind the walk peak because the body's composite scratch asks for `2·body_len − 1` lanes, so a notched bit there frees 2 wires. The notch knobs are `BINDER_NOTCH_STEPS/EXTRA/MAP` ([a5a590a](../commits/a5a590a.md), [73f4f48](../commits/73f4f48.md)), the step-11 `TRIO_WIDTH_NOTCH` ([3409fbd](../commits/3409fbd.md)), the 8–17 list of [94927be](../commits/94927be.md), and `BODY_STEP_GIVEBACKS`.

**Borrowed scratch.** `dialog_gcd_build_composite_scratch` fills the body's lanes in this order, and allocates fresh wires only for the remainder:

1. the not-yet-written future log (`BORROW_FUTURE_LOG_CARRIES`, `HOST_GATED`);
2. the current block's own empty cells (`BORROW_CURRENT_BLOCK`, 69bd3d7);
3. `v` and `u` above `w`;
4. the current step's `s2` cell (`BORROW_CURRENT_S2`);
5. later raw slots (`BORROW_ZERO_RAW_FUTURE`, [8983da8](../commits/8983da8.md)).

[transcript-codecs.md](transcript-codecs.md) explains why these cells are |0⟩.

**Apply phase.** The transcript fixes a linear map `M` with `M(p, a) = (1, ·)`. Mod p, `p ≡ 0`, so replaying `M` on `(0, y)` puts `y/a` in the first lane, and replaying `M⁻¹` multiplies instead. The quotient's apply step is `cswap(b01, x, y)`, then `y −= b0·x mod p`, then a halving of y (twice if `s2`). The ipmul runs the inverse step in reverse order. After the forward walk, `X(u[0])` frees `u` (terminal reuse), and the factor register serves as the second lane. The step has four parts:

- **Chunked controlled add.** `f = ctrl·x` is loaded one chunk at a time ([550895c](../commits/550895c.md)). Each chunk runs a measured-carry Cuccaro. The carry between chunks sits on a boundary wire, and an exact prefix compare clears it: `cout = [acc[..cut] < a[..cut]]`, since the carry out of a p-bit add is 1 exactly when the sum's low bits are below the addend's. One sweep can clear several boundaries ([e4edca0](../commits/e4edca0.md)). Inside a split final chunk `cmp_lt_into_fast_with_cin` takes the carry-in (correct for two windows only, per the [21fbfc7](../commits/21fbfc7.md) note). Cuts come from `APPLY_CHUNKED_F_CUT`…`CUT4`, later `F_BLOCKS` or an explicit `F_CUTS` list; raising a cut one bit shrinks the top chunk by 2 wires for about 1 T per apply call ([a772a45](../commits/a772a45.md)). [bfd3fa6](../commits/bfd3fa6.md) replaced the sweep by `hmr` plus an exact recompute run only on outcome 1.
- **Overflow handling.** The overflow adds `c = 2³² + 977` to the low 73 bits. The overflow flag is cleared by a compare of the top `APPLY_CLEAN_COMPARE_BITS` bits (`acc < f`; 20 at cddd5df, 18–24 later, 19 at the end), with per-step overrides `SPECIAL_{OVER,UNDER}FLOW_CLEAN_STEP_BITS`.
- **Fused double/halve.** From [8a47cf5](../commits/8a47cf5.md), `double_y` / `halve_y` do both shifts, then one fold of `c·e + 2c·d` with per-position controls `e`, `d`, `h = e∧d` and CX combinations; its majority went to 2 CCX ([94535d1](../commits/94535d1.md)) and 1 CCX ([2a87f33](../commits/2a87f33.md)), and `h`, `d`, `e` are cleared by measurement ([a88c9a1](../commits/a88c9a1.md)).
- **Carry windows.** `KAL_DOUBLE_CARRY_TRUNC_W` caps the double/halve fold at bit 32 + W (introduced 24 in [f8a36ba](../commits/f8a36ba.md), 19 at the end). `KAL_FOLD_CARRY_TRUNC_W` caps the apply add/sub fold (18). `DIALOG_GCD_FOLD_CARRY_TRUNC_W` overrides the window of the fused cell only (18).

**Cost.** Per walk, one envelope bit-step costs about 3 T single-shift (swap, load, subtract) or 4 T with the K2 cascade, and a compare bit 1 T; [ec0fa98](../commits/ec0fa98.md) reproduces its saving as 4 × (4 × 124 + 36). A whole K=2 step, over walks and applies, costs about 2,850–2,870 T, mostly apply ([11ceae2](../commits/11ceae2.md), [f5f0f61](../commits/f5f0f61.md)); single-shift, about 2,000 ([dd103cd](../commits/dd103cd.md)).

**Classical pre-filter** (`dialog_gcd_classical_filter.rs`, not part of the circuit). Added in ec0fa98, dropped by the 69bd3d7 split, re-added in [88079e6](../commits/88079e6.md), later mirrored in CUDA (`ecdsafail-agent/gpu-nonce/src/gcd.cu`). It replays the truncated walk for both factors of all 9,024 shots. At ec0fa98 a factor was hard on `WidthOverflow` or `NonConvergence`; it already followed the truncated branch decision, and `ComparatorMismatch` was flagged only with `DIALOG_GCD_FILTER_STRICT_COMPARE=1`. By ba3efc1 the width check is opt-in too (`DIALOG_GCD_FILTER_STRICT_WIDTH`, from [cf310ec](../commits/cf310ec.md)), the filter needs only terminal `u = 1` (first the `ACCEPT_U1_TERMINAL` option of 2a87f33), and replays the apply values, fold-carry escapes and head/tail codec support; clean-compare disagreements are only soft risks.

**Relation to [trailmix-jump-gcd.md](trailmix-jump-gcd.md).** That page covers the jump-2 port that followed. Per the code, the June route lived in `mod.rs` until 69bd3d7 and in `rounds/dialog/` after it; `kaliski_jump.rs` was never on it. Trailmix reorders the step (shift first) and fuses the apply into the walks. The `DIALOG_GCD_*` defaults that later trees still set are left over from this route.

## Why it is (or is not) exact

**Exact:** replay algebra, K=2 shift, odd-u shortcuts, terminal reuse (given convergence), measured clears, the full-prefix boundary clear, conditional replay, and borrows of cells known to be |0⟩.

**Probabilistic** (priced as λ, see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)):

- **`ACTIVE_ITERATIONS`.** An input not yet at `u = 1` leaves garbage when `u` is freed; dd103cd's comment puts this at about 3×10⁻⁴ of inputs at 396 steps. The count went 399 → 393, then 259 under K=2, and was traded within 258–262 against other cuts ([11ceae2](../commits/11ceae2.md), [94535d1](../commits/94535d1.md)).
- **Width envelope, body trims and notches.** These drop bits that a slow input still needs. The comment in 69bd3d7 says the late 1-bit trims "mis-drop" a bit on a handful of inputs.
- **Branch compare.** A tie on the top `k` bits picks the wrong branch.
- **Clean compares.** These fail with probability about 2⁻ᵏ per add, which shows up as phase or ancilla garbage.
- **Fold windows.** A run of W+1 ones above bit 32 is dropped. That is about 2⁻²⁵ per call at W = 24 (f8a36ba), and the result is a wrong value.
- **Tail codec support.** See [transcript-codecs.md](transcript-codecs.md).

Before [39134ec](../commits/39134ec.md) added `DIALOG_TAIL_NONCE` (4 June), identity `X;X` pads rerolled the draw (`DIALOG_GCD_REROLL`, then `DIALOG_REROLL`/`DIALOG_POST_SUB_REROLL`, from [541bd85](../commits/541bd85.md)). Per-step "repairs" widen only the sites where hard inputs failed ([674d0d8](../commits/674d0d8.md), [7bab51f](../commits/7bab51f.md)).

## Knobs and names you will see in commits

- **Walk:** `DIALOG_GCD_ACTIVE_ITERATIONS` (max 402), `DIALOG_GCD_K2`, `WIDTH_SLOPE_X1000`, `WIDTH_MARGIN`, `WIDTH_STEP_BUMPS`, `ODD_U_LOWBIT_FASTPATH`.
- **Compare:** `COMPARE_BITS`, `PA9024_COMPARE_SCHEDULE` (+`_MARGIN`, `_FLOOR`), `COMPARE_STEP_BITS`, `FUSED_BRANCH_BITS`.
- **Body and scratch:** the trim, notch and borrow names above, plus `CTRL_BODY_VENTED`, `RAW_TOBITVECTOR_MATERIALIZED_SUB`, `COMPOSITE_SCRATCH`.
- **Apply:** the chunk, clean-compare and window names above, plus `APPLY_FINAL_WINDOWED_FAST_BLOCKS`, `APPLY_BOUNDARY_SPLIT`, `APPLY_BOUNDARY_CONDITIONAL_REPLAY`, `APPLY_FUSED_FOLD`, `FOLD_PARK_LOW_CARRIES`.
- **Nonce:** `DIALOG_REROLL`, `DIALOG_POST_SUB_REROLL`, `DIALOG_TAIL_NONCE`. Trailmix kept that last name until [3f8ce09](../commits/3f8ce09.md) (20 July).
- **Pitfall:** `set_default_env` is first-wins. A later line in `configure_ecdsafail_submission_route()` is dead ([1caf521](../commits/1caf521.md) was undone this way by [ba3efc1](../commits/ba3efc1.md)).

## How optimizations use it

- **Iteration and threshold tuning:** [dd103cd](../commits/dd103cd.md), [339fe8d](../commits/339fe8d.md), [39134ec](../commits/39134ec.md), [fec6d25](../commits/fec6d25.md), [f5f0f61](../commits/f5f0f61.md).
- **Envelope and compare truncation:** [8cb350c](../commits/8cb350c.md), [412312f](../commits/412312f.md), [8316db1](../commits/8316db1.md), [353ac6d](../commits/353ac6d.md), [5ad23b1](../commits/5ad23b1.md), [69bd3d7](../commits/69bd3d7.md).
- **Body trims and notches (peak):** [cc5584e](../commits/cc5584e.md), [ace6347](../commits/ace6347.md), [94927be](../commits/94927be.md), [a4db9a5](../commits/a4db9a5.md).
- **Apply chunking and boundary clears:** [68e3653](../commits/68e3653.md), [550895c](../commits/550895c.md), [e4edca0](../commits/e4edca0.md), [2eab923](../commits/2eab923.md), [bfd3fa6](../commits/bfd3fa6.md).
- **Fold windows and fusion:** [f8a36ba](../commits/f8a36ba.md), [0aa33ed](../commits/0aa33ed.md), [8a47cf5](../commits/8a47cf5.md), [980ed3a](../commits/980ed3a.md).
- **Clean compares:** [006e38b](../commits/006e38b.md), [4b9cfbb](../commits/4b9cfbb.md), [88079e6](../commits/88079e6.md), [a5a590a](../commits/a5a590a.md).
- **Scratch borrowing:** [92a247e](../commits/92a247e.md), [13a01b8](../commits/13a01b8.md), [8983da8](../commits/8983da8.md).

## Timeline

- [cddd5df](../commits/cddd5df.md) (2 Jun): dialog GCD replaces Kaliski, 399 steps, 1698 × 2,447,846.
- [7e660f9](../commits/7e660f9.md), [9b6b9d6](../commits/9b6b9d6.md), [f8a36ba](../commits/f8a36ba.md) (2 Jun): measured and fused compares, truncated double/halve, first compare table.
- [68e3653](../commits/68e3653.md) → [92a247e](../commits/92a247e.md) → [6189d5f](../commits/6189d5f.md) (2 Jun): hosted `gated`, windowed apply, 1698 → 1446 q.
- [13a01b8](../commits/13a01b8.md) (3 Jun): uncapped u-high runway, composite scratch, 1355 q. [39134ec](../commits/39134ec.md) (4 Jun): `DIALOG_TAIL_NONCE`.
- [0780f67](../commits/0780f67.md) (5 Jun): K=2, 259 steps, 1394 × 1,629,451. [ec0fa98](../commits/ec0fa98.md): classical filter. [9a81017](../commits/9a81017.md): pair codec, 1313 q.
- [8a47cf5](../commits/8a47cf5.md) (6 Jun): fused fold, first score under 2.0 B. [69bd3d7](../commits/69bd3d7.md): module split, K2 compare table, 1309 q.
- [94927be](../commits/94927be.md) (7 Jun), [bfd3fa6](../commits/bfd3fa6.md) (8 Jun): notches to 1297 q; conditional replay, −50,826 T.
- [7689eac](../commits/7689eac.md) (10 Jun): vented body, 1226 q. [6953d1b](../commits/6953d1b.md), [cf310ec](../commits/cf310ec.md), [674d0d8](../commits/674d0d8.md) (12–14 Jun): K5/head-11/tail-3 codecs, 1203 → 1170 q.
- [35ceb01](../commits/35ceb01.md) (15 Jun) and [ba3efc1](../commits/ba3efc1.md) (18 Jun): last dialog frontier, 1168 × 1,431,621.
- [bdb1d22](../commits/bdb1d22.md) (19 Jun): trailmix replaces the route, 1167 × 1,422,591. The dialog code stays in the tree, uncalled.

## Related concepts

[transcript-codecs.md](transcript-codecs.md) · [trailmix-jump-gcd.md](trailmix-jump-gcd.md) · [kaliski-almost-inverse.md](kaliski-almost-inverse.md) · [trailmix-schedules-and-reserves.md](trailmix-schedules-and-reserves.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [modular-fold.md](modular-fold.md) · [adders-and-carries.md](adders-and-carries.md) · [measurement-uncompute.md](measurement-uncompute.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [squaring-and-karatsuba.md](squaring-and-karatsuba.md)
