# Squaring and Karatsuba

> Each point addition needs one modular square: the `square` phase computes `X ← X − λ² (mod p)`, where λ is the chord slope. Squaring is cheaper than a general multiply because the cross products `y_i·y_j` are symmetric, so each is needed once rather than twice, and the diagonal terms `y_i² = y_i` cost nothing. The circuit splits λ into halves with Karatsuba, so three half-size squares replace four. It applies the same split again to the halves, folds each piece straight into `X`, and uncomputes it before building the next. This keeps a full 512-bit product register from ever being live. Commits in this area either swap in a deeper or better-laid-out Karatsuba (**Algorithmic Substitution → multiplier/squarer swap**) or trim and fuse the square's internal adds and folds.

## How it works in this circuit

**Top level (`square.rs::sub_square`).** Write `y = a + b·2^128`. Then

```
y² = A + (C − A − B)·2^128 + B·2^256,    A = a², B = b², C = (a+b)²
   ≡ A + (C − A − B)·2^128 + f·B  (mod p),   since 2^256 ≡ f = 2^32 + 977
```

The routine subtracts, so the folds into `out` are `out −= A` and `out += A·2^128` (branch A), `out −= C·2^128` (branch C), and `out += B·2^128` and `out −= f·B` (branch B). The `f·B` term is folded with the NAF terms of `f` (see [modular-fold.md](modular-fold.md)). The paper's §“Karatsuba Squaring with Pseudo-Mersenne Modulo” (arXiv v2) derives the same three updates. Each branch goes through `with_square(x, policy, folds)`, which does three things:
- materialises `x²` in a fresh `2·|x|` register;
- runs the folds that consume it;
- uncomputes it and releases it.

The doc comment explains the purpose: "a sub-square is live only for the folds that consume it". The sum `t = a + b` is not a separate register. It lives in `b`'s own wires plus one carry ([`51c6c31`](../commits/51c6c31.md), [`e50a36f`](../commits/e50a36f.md)), and `b` is restored afterwards.

**Leaf squares (`tri_square`, `tri_square_cin`).** A leaf square of an *m*-bit `x` is built as a triangle of rows:

```
product bit:  ...  2i+1 ............ i+m+1
row i:             ± x[i+1..]  (sign selected by x[i])   ← one add-or-subtract ripple
diagonal:     x_i lands at bit 2i   (x_i² = x_i)
```

Row *i* adds `x[i+1..]` at offset `2i+1`. That counts each off-diagonal product once, and the offset of 1 doubles it. Each row is a single add-or-subtract selected by `x[i]`, built from complement frames, rather than an AND row followed by an add. A fixed correction (`tri_corr` / `diag_correction`) removes the resulting offset. Several knobs make parts of this free:
- `SQ_DIAG_PRELOAD` copies the low diagonal bits in with CX gates, because the rows provably leave headroom below them.
- `SQ_CIN_SPREAD` feeds each diagonal bit in on the row ripple's carry-in, which "costs no Toffoli".
- `SQ_ROW0_COPY` turns row 0 into a Clifford copy and adds the resulting constant offset classically ([`902ec7b`](../commits/902ec7b.md)).

**Recursive in-place Karatsuba (`tri_square_k2r`).** For a materialised square, `a²` and `b²` are built into the two disjoint halves of the zeroed product register. The cross term `2ab = t² − a² − b²` is built in retained scratch (`K2Retained`), then rippled in at shift `lo` by `add_cross` with one exact full-width add. Keeping that scratch live until the inverse means "the inverse never recomputes a sub-square". The split recurses under a width policy: a sum half of at least `SQ_SPLIT_SUM_MIN` (65) bits, or a low half of at least `SQ_SPLIT_LOW_MIN` (64) bits, is split again. The source's cost model compares `B(m) = m(m−1)/2 + 4m − 3` for a triangular leaf with `K(m) = B(a) + B(b) + B(b+1) + a + 7b + 1` for one split. It "puts the break-even near 60 bits", and adds that the qubit peak, not the Toffoli count, is what limits the depth. `SQ_A_POLICY`, `SQ_B_POLICY` and `SQ_C_POLICY` choose the policy for each top-level branch.

**Why squaring wins.** The paper counts off-diagonal products (arXiv v2, §“Karatsuba Squaring with Pseudo-Mersenne Modulo”). A direct 256-bit symmetric square has `256·255/2 = 32,640`. Two 128-bit squares plus one 129-bit sum-square have `24,512`, about 24.9% fewer. A general 256×256 multiply has no symmetry to exploit at all. Supplemental Note B (“Algorithmic Substitution”, “Karatsuba multiplication”) also records the earlier history: a generic Karatsuba multiplier on all four multiply sites (`cc427db`), and a revert of the in-inverse sites to a scratch-lean schoolbook (`bc2f2a4`). Karatsuba's extra scratch can raise the peak, so its value has to be decided site by site.

## Why it is (or is not) exact

The Karatsuba identity and the triangular row construction are exact. `tri_square_k2r`'s comment says "every primitive here is an exact full-width add or subtract, so this adds no truncated comparison, windowed fold or measured chunk boundary". A squarer swap therefore adds no hard inputs. It still changes the op stream, so it needs a new nonce. The paper says the same (arXiv v2, §“Karatsuba Squaring with Pseudo-Mersenne Modulo”): any approximation "arises only from separately documented finite-width modular-correction subroutines, not from the Karatsuba decomposition itself". In this file, those subroutines are:
- the `+f` fold and erase compare inside `mod_addsub` (`FOLD_GUARD`, `ERASE_COMPARE`);
- `window_add`'s `FOLD_GUARD` headroom;
- `SQ_ASM_TAIL`, which ripples the cross-term carry only `E` bits past the cross word. The bits above are random `b²` data, "so a carry reaches E bits in with probability about 2^-E".

Each of these is a λ trade (see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)). The many `SQ_LEND_*` and `SQ_HOLD_*` knobs lend the square's provably zero scratch to other code or keep carries live. They are exact layout choices, aimed at the peak.

## Knobs and names you will see in commits

- `sub_square`, `with_square`, `tri_square(_cin)`, `tri_square_k2r(_inv)`, `K2Retained`, `add_cross`: the squarer's structure.
- Older names: `square/product_register.rs`, `karatsuba_branch`, `square_sub`, `bk2_min`, `SUB4_SQUARE_A_MAT` / `C_MAT` (trailmix-era squarer, August).
- `SQ_SPLIT_SUM_MIN`, `SQ_SPLIT_LOW_MIN`, `SQ_SPLIT_B_MIN`, `SQ_{A,B,C}_POLICY`: recursion depth.
- `SQ_DIAG_PRELOAD`, `SQ_CIN_SPREAD`, `SQ_ROW0_COPY`, `SQ_ROW0_CARRY`, `SQ_ROW_ALL_MEASURE_TOP`: free or cheaper diagonal and row-0 handling.
- `SQ_ASM_TAIL`: truncated cross-add carry tail. `GUARD` in the old `product_register.rs`: `window_add` headroom, now `FOLD_GUARD`.
- `SQ_FIT_CROSS`, `SQ_HOLD_BOUNDARY`, `SQ_LEND_RETAINED_*`, `SQ_HIGH_CARRY_LOAN`, `SQUARE_CHUNK_MIN`, `SQUARE_LADDER`: fitting the square's ladders under the peak cap (see [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md)).
- `PP_J_BMERGE`, `PP_J_WCIN`, `PP_J_SFUSE(_B)`: fuse branch B's NAF folds into each other or into the multiply walk's round-0 lift.

## How optimizations use it

- **Multiplier/squarer swap** (5 census commits). In the original census, [`28fe2f2`](../commits/28fe2f2.md) swaps the Karatsuba squarer backend and [`b6d6f41`](../commits/b6d6f41.md) swaps the x-tail square (see "Early squarers" below). [`d919bc6`](../commits/d919bc6.md) adds a second Karatsuba level (−2,682 T by its own comment). [`1f99759`](../commits/1f99759.md) adds the retained recursive in-place `tri_square_k2r`. [`e50a36f`](../commits/e50a36f.md) recurses deeper under `SQ_SPLIT_*_MIN` and keeps the sum in place (−1,211 T at an unchanged peak).
- **Fused square steps** (Fusion → gate/op fusion): [`f812a29`](../commits/f812a29.md) merges the diagonal spread into the row carry-ins (about −1,676 T). [`a231a39`](../commits/a231a39.md) merges branch B's NAF windows and hands its last borrow to the walk's round-0 lift (part of the commit's −859 T; the note says the code does not report the split between its three parts).
- **Square truncations** (Dead-Code): [`0a06121`](../commits/0a06121.md) sets `SQ_ASM_TAIL`=21. [`8d7051b`](../commits/8d7051b.md) cuts the square `GUARD` from 44 to 24.
- **Peak work in the square**: [`51c6c31`](../commits/51c6c31.md) puts the Karatsuba sum into the input's high half instead of a separate 129-qubit register. [`9652eec`](../commits/9652eec.md) chunks the wide `tri_corr` adds, lowering the square's local peak.

## Early squarers (May–July)

Before `square.rs`, λ² went through four designs. Their names fill the June notes.

**The dialog-route x-tail square (`round84_*`, June).** `round84_emit_fused_square_xtail` computes the affine `x3`. Its square, `squaring_sub_from_acc_*` in `arith/multiply.rs`, does `acc −= x² mod p`. It first builds the full 512-bit `S = lo + hi·2^256`, then reduces with `2^256 ≡ c = 2^32 + 977`. The "Solinas lanes" were modular steps on `hi` itself, followed by the reverse steps to restore `hi`:

```
acc −= lo
acc −= hi; 4× double; acc −= hi; 2× double; acc += hi; 4× double; acc −= hi   # weights 1+16−64+1024 = 977
×2^22 (shift-by-22, or 22 doublings); acc −= hi                               # weight 2^32
```

- [`b6d6f41`](../commits/b6d6f41.md) (2 Jun) turned on the one-level Karatsuba version, `ROUND84_XTAIL_KARATSUBA=1`. It builds `(lo+hi)²` in a 258-qubit `z1_reg`, and `lo²` and `hi²` in the 512-qubit `tmp_ext`. That saved 16,272 emitted T; the measured net change was −11,600 T.
- The x-tail then held the peak, and a series of edits lowered it:
  - The `·2^22` shift (`mod_shift_left_by_k_lowq`) kept a 22-bit spill and two flags live across the subtract. 22 modular doublings and halvings replaced it ([`287595e`](../commits/287595e.md), [`33c072d`](../commits/33c072d.md)). That cost about +4,800 T and saved 24 q.
  - The provably-zero top bit of `z1` was freed ([`7021abe`](../commits/7021abe.md)).
  - `lo²` borrowed its carry lane from the still-empty `hi²` half. `hi²` used the ancilla-free "lowq" Cuccaro adder. The constant corrections used dirty-ancilla vented adders (`KARA_SOL_MOD_VENT`; [`250774e`](../commits/250774e.md), [`571e67c`](../commits/571e67c.md)).
- **Self-hosted schoolbook.** [`fb83e6c`](../commits/fb83e6c.md) moved the `hi²` rows to the fast Cuccaro adder, with measured uncompute instead of the UMA Toffoli. Its carry lane sits on the product's own unwritten high zeros, plus 3 fresh wires (−16,800 T). [`13a01b8`](../commits/13a01b8.md) then set `ROUND84_XTAIL_KARATSUBA=0` and ran the whole square as this low-qubit schoolbook, trading Toffoli for qubits. A knob from [`e0cfe2b`](../commits/e0cfe2b.md) kept each row's top carry in place to save a wire. [`c8f4536`](../commits/c8f4536.md) gave that back (−510 T).
- **In-place Solinas fold** (`ROUND84_INPLACE_SOLINAS_FOLD`, [`6bf73fe`](../commits/6bf73fe.md), 7 Jun, −13,360 T).
  - It adds `hi·c` into `lo` with plain integer shifted adds. A 34-bit quotient register catches the overflow.
  - It applies `quotient·c` once, so a single modular subtract `acc −= lo` remains.
  - One carry chain is truncated (`ROUND84_INPLACE_QUOTIENT_CARRY_TRUNC_W`, about 2^−22 per call). Everything else is exact.
  - Follow-ups made the small adders measured ([`c27e8a5`](../commits/c27e8a5.md), [`b7515d5`](../commits/b7515d5.md)) and used signed `977 = 2^10 − 2^5 − 2^4 + 1` ([`ed94ad2`](../commits/ed94ad2.md)). They also kept the quotient product live across the subtract ([`997dbd6`](../commits/997dbd6.md)) and narrowed the wrap window ([`f4404de`](../commits/f4404de.md)).

**Row-windowed squares (`SQUARE_ROW_MAX_SEG`, from 10 June).** [`7689eac`](../commits/7689eac.md) adds every schoolbook row wider than `SQUARE_ROW_MAX_SEG` (199 at first) in two windows, so the full row register is never live. That is exact. The boundary carry left on `cout` has to be cleared:
- At first this was an exact recompute, costing about 25,000 T.
- [`1a5e620`](../commits/1a5e620.md) compared only the top 22 bits of the segment (−22,624 T, about 2^−22 per row).
- [`d636d62`](../commits/d636d62.md) measured `cout` and ran the compare only as a conditional phase fix (`SQUARE_ROW_WINDOW_MEASURED_CARRY_CLEAR`).
- The width knob `SQUARE_ROW_WINDOW_CLEAN_COMPARE_BITS` then went 22 → 21 ([`5a783e4`](../commits/5a783e4.md)), then 19 with a per-row map `SQUARE_ROW_WINDOW_CLEAN_ROW_BITS` ([`cf99209`](../commits/cf99209.md)), then 18 ([`6878ef8`](../commits/6878ef8.md)).

Lowering `MAX_SEG` was a peak lever: 194 ([`572bba4`](../commits/572bba4.md)), 191 ([`9191f81`](../commits/9191f81.md)), 185 ([`8cd8104`](../commits/8cd8104.md)), 165 ([`0fa5c6f`](../commits/0fa5c6f.md)), and 141 in the mid-June route settings.

**The trailmix square and its f-fold routes (19 June – July).** [`bdb1d22`](../commits/bdb1d22.md)'s `mod_square_sub_pm_secp256k1_symmetric` builds the 512-bit product with a symmetric AND-row schoolbook. The row adds are sized by `SQ_ROW_K`. It then subtracts `lo + f·hi` with an `F_BITS = [0,4,6,7,8,9,32]` ramp: `hi` is doubled mod p in place up to `2^32`, with a modular subtract at each set bit, and then halved back. That is 64 doubling/halving fold windows. The f-fold routes that followed:
- **NAF** ([`4ea8b74`](../commits/4ea8b74.md), −1,738 T). It uses `F_NAF_TERMS`, `f = 2^32 + 2^10 − 2^6 + 2^4 + 1`. Each `±hi·2^j` term is `mod_add/sub_shifted_low` of the low `256 − j` bits at offset `j`. Each of the `j` spilled top bits is folded back as a gated `±f·2^t` window.
- **One-level Karatsuba** ([`28fe2f2`](../commits/28fe2f2.md), −19,229 T). Each of `A`, `B`, `C` is built, folded and unbuilt in turn. Its `f`-folds are doubling ramps again.
- **Ramp to shift 10, then add `2^32` directly** (`TLM_SQUARE_F_RAMP10_DIRECT32(_TAGS)`). This works because a 128-bit limb times `2^32` cannot wrap ([`e25c7d8`](../commits/e25c7d8.md), [`aacf05c`](../commits/aacf05c.md)).
- **`TLM_SQUARE_F_SHIFTED_LOW=1`.** Every NAF term of the three `×2^128` limbs becomes a shifted-low add with no ramp. This is value-exact because the limbs are below `2^130` ([`3df690f`](../commits/3df690f.md), −7,676 T; on the 1159-qubit tree in [`d11bdbb`](../commits/d11bdbb.md)). The `f·B` term of `2^256` keeps its ramp.
- [`d44cad3`](../commits/d44cad3.md) vented the square's reduce adds up to `TLM_SQUARE_PEAK_CAP` (see [trailmix-schedules-and-reserves.md](trailmix-schedules-and-reserves.md)).

**Signed add/subtract rows** ([`422f21d`](../commits/422f21d.md), 7 Jul, −43,467 T at 1152 q). `square_addsub_vented` replaces the AND rows:
- Row `i` adds `+x[i+1..]` when `x_i = 1` and `−x[i+1..]` when `x_i = 0`. A complement frame does this: an X on `x_i`, CXs onto the operand and the carry-in. So the row needs no controlled gates.
- Its carries are borrowed from the product's still-zero top bits and erased by measurement.
- A fixed correction (`square_corr_forward`) turns the signed sum into `x²`.

This is the ancestor of the add-or-subtract rows in `tri_square` described above.

## Related concepts

[modular-fold.md](modular-fold.md) · [adders-and-carries.md](adders-and-carries.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [measurement-uncompute.md](measurement-uncompute.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md)
