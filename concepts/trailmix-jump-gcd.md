# Trailmix jump-GCD inversion (the pre-21-August divider)

> Point addition needs the slope λ = (y₂ − y₁)/(x₂ − x₁) mod p. Until 21 August the frontier computed that division with a reversible **binary extended GCD**. A forward "walk" runs a fixed number of GCD steps on the pair (u, v) = (p, dx) and writes each step's branch decisions into a compressed quantum transcript (the *dialog* or *tape*). The same decisions, applied to a second pair of registers, turn dy into dy·dx⁻¹. A backward walk then restores dx and erases the transcript. The jump-2 variant does up to two halvings per step. A base-5 codec packs three steps into 7 qubits. Most July–August commits in this family tune its per-step width tables (`SCHED_J2`, `GAP_J2`), its step count (`ITERS`), or small gates inside the codec.

## How it works in this circuit

**Lineage.** Schrottenloher's *dialog GCD* (record the branch decisions, then replay them on the payload pair; no Bézout coefficients are kept) arrived as the `DIALOG_GCD` route in early June ([`cddd5df`](../commits/cddd5df.md), 2 June). Its code lived in `mod.rs` until the module split of [`69bd3d7`](../commits/69bd3d7.md) (6 June), which moved it to `rounds/dialog/`; `kaliski_jump.rs` was never on that route. See [dialog-gcd-early.md](dialog-gcd-early.md) for the June route itself. Trail of Bits' "trailmix ludicrous" port then landed as `src/point_add/trailmix_ludicrous/` (submission bdb1d22, 19 June). By late July `build()` calls `trailmix_ludicrous::build_trailmix_ludicrous_ops()`. `mod.rs` still sets many `DIALOG_GCD_*` defaults and `DIALOG_TAIL_NONCE`, but these are legacy names: `DIALOG_TAIL_NONCE` stopped being the live tail nonce at [`3f8ce09`](../commits/3f8ce09.md) (20 July, a literal), and [`5b834ba`](../commits/5b834ba.md) (23 July) moved it to `SUB4_TAIL_NONCE`. I did not check which of the old variables the trailmix path still reads.

**Shell** (`trailmix_ludicrous/ec_add.rs`). The phases are `tlm_coord_x_sub` and `tlm_coord_y_sub`, which form dx and dy. Then come `tlm_inverse`, `tlm_coord_add3x`, `tlm_square` and `tlm_forward_multiply`, and finally the two `*_final` coordinate fix-ups. Both GCD phases call `gcd.rs::mod_mul_inverse_in_place(x, y, dir)`:

- `Direction::Inverse` divides: y ← y·x⁻¹, which gives λ.
- `Direction::Forward` multiplies: y ← y·x. Here x already holds x_A − x_R′, so the product gives y_R′ + y_A.

**One divstep** (`forward_gcd_jump`; JUMP = 2). The register `u` is loaded with the constant p and `v` is the denominator. For step i:

```
v >>= 1                     # unconditional (at i = 0 it is controlled by t1 = [v even])
s2 = [v even];  if s2: v >>= 1          # the "jump": a second halving
b  = v[0]                               # odd -> a subtraction happens
s  = b AND (v < u)                      # truncated compare on the top cmp_window(i) bits
if s: swap(u, v)                        # cswap across the live width
if b: v -= u                            # controlled hybrid add on the complement
emit symbol (b, s, s2)                  # 3 raw bits; only 5 combinations reachable
```

The code calls each iteration a "divstep", a term borrowed from Bernstein–Yang's safegcd. The rule itself is the comparison-based binary GCD of Schrottenloher's record phase (arXiv v2, §“Dialog-GCD record and replay”, “Dialog-GCD record phase” algorithm), retimed by Jump-2 (arXiv v2, §“The Jump-2 Euclidean Algorithm”), not Bernstein–Yang's δ-counter rule. v2 cites Bernstein–Yang only in the introduction's list of reused primitives and never ties it to this route; Supplemental Note B (“Algorithmic Substitution”, after “Karatsuba multiplication”) loosely calls the route a “jump/safegcd reformulation”. The Jump-2 section also gives the invariant: every macro-step ends with v even, so the next unconditional halving is always valid.

**Applying the decisions to the payload** (`apply_step_forward` / `apply_step_reverse`). For a fixed transcript the walk is a linear map D with D(p, x) = (1, 0). Over F_p the constant p is 0, so D(0, y) = (y·x⁻¹, 0). Per step, the payload update is:

1. a controlled modular add, on b;
2. a full 256-bit controlled swap of the two payload registers, on s (this is the **apply-cswap**);
3. a fused doubling by 2^(1+s2), with one shared pseudo-Mersenne fold of both overflow bits (`fused_double_cdouble`).

**Why there are forward and inverse passes.** The transcript depends on dx, which is in superposition, so it cannot be measured or dropped. It has to be uncomputed by running the walk backwards (`reverse_gcd_jump`), which also restores dx. Each GCD phase is therefore two walks, and the payload update is fused into one of them:

| phase | walk 1 | walk 2 |
|---|---|---|
| `tlm_inverse` (λ) | forward walk, `apply_step_reverse` applied from the live symbols before they are encoded | reverse walk: restore dx, erase tape |
| `tlm_forward_multiply` | forward walk, record tape only | reverse walk, decode each symbol, `apply_step_forward`, erase |

A point addition therefore runs four GCD walks and two 256-bit apply passes.

**Transcript codec** (`codec.rs`, `DialogCodec`). The five reachable symbols are base-5 digits:

- `Step0` stores step 0 plus t1 in 2 qubits.
- `Triple` stores three symbols (9 raw bits) in 7 qubits, since 5³ = 125 < 128. It runs `compress_2sym_fast`, then the `NORMALIZER_OPS` table, then `MERGE25`.
- `Pair` stores two symbols in 5 qubits.
- `Raw` stores one symbol in 3 qubits.
- `Tail4Top32` is optional and gated by `TLM_TAIL4_TOP32`.

The paper gives the size for 261 steps as 2 + 86·7 + 5 = 609 qubits, against 261·3 = 783 raw (arXiv v2, §“Base-5 Codec for the Jump-2 Transcript”). The 258-step figure of 602 qubits (2 + 85·7 + 5) appears in the earlier draft only. Each window is encoded as soon as it is complete, and the code wires reuse wires that the shrinking u and v have freed. In the trailmix route, "K5" refers to this base-5 packing. In the June dialog route, `DIALOG_GCD_K5_*` instead names a block of five steps (15 raw bits → 12-bit code); see [transcript-codecs.md](transcript-codecs.md). The "E208"/"E209" edits are gate-level changes inside `MERGE25` (see 2dabd9d).

**Where the qubits go.** Two payload registers (y and its temporary partner) are live through each walk. Supplemental Note D (“Stage 2 detail: width scheduling and qubit reuse”, “Combined live-width model”) estimates the width at step i as

  Q_i ≈ 512 (Bézout/payload pair) + |τ_i| (compressed dialog) + 2·w_i (u_i, v_i) + q_work,i (comparison, carry and control),

with w_i = `SCHED_J2[i]`. The design goal it states is that the shrinking 2·w_i absorbs the growth of |τ_i|.

The u,v width follows `SCHED_J2`. The scratch budget is capped by `TLM_TARGET_Q` / `TLM_SQUARE_PEAK_CAP`, which set the headroom that the vented adders, comparators and folds may use. On this route the peak fell from 1167 ([`bdb1d22`](../commits/bdb1d22.md), June) to 1150 ([`31f9c58`](../commits/31f9c58.md)); from late July it stayed at 1150–1158.

**Where the Toffoli go.** An estimate of unverified origin (it was attributed to a `b87bdf7`, which is not a commit on `main`) puts each divstep at about 3,050 executed Toffoli, summed over all walks and apply passes. At 259 steps that is roughly 0.79M of the 1.28M total. That is my multiplication, not a measured phase profile. Per step, the walks pay for the compare (about `GAP_J2[i]` bits), the u/v cswap and controlled add (about `SCHED_J2[i]` bits each), and the Fredkin shift ladders. The apply passes pay full 256-bit width for the modular add, the apply-cswap (256 Toffoli) and the fused double.

## Why it is (or is not) exact

Jump-2 is an exact retiming of the binary GCD, and the codec is an exact permutation on the reachable symbols. The approximations come from elsewhere:

- **`ITERS`.** Inputs that need more steps than `ITERS` never converge. Over 10M inputs the paper measured non-convergence of 2.839×10⁻⁴ at 258 steps and 2.86×10⁻⁵ at 261 (arXiv v2, §“The Jump-2 Euclidean Algorithm”).
- **`SCHED_J2`.** Wires above the scheduled width are freed on the assumption that they are already |0⟩.
- **`GAP_J2` / `cmp_window`.** The comparator looks only at the top bits, so it picks the wrong swap when u and v agree on those bits.
- **Skip-last knobs.** The `*_CSWAP_SKIP_LAST` and `*_ADD_SKIP_*` knobs drop work in the last steps, where it almost never fires.
- **Census-mined strips.** These remove gates that were never seen to fire.

Every one of these is priced by its failure rate. A circuit is accepted only if its own 9,024-shot Fiat–Shamir draw has 0 classical mismatches, 0 phase-garbage batches and 0 ancilla-garbage batches, which is why a fresh tail nonce has to be found after each edit. See [scoring-and-validation.md](scoring-and-validation.md) and [nonce-island-and-lambda.md](nonce-island-and-lambda.md).

## Knobs and names you will see in commits

- `ITERS` / `BAKED_ITERS` (`schedule.rs`): the step count, and the count the baked tables were fitted at. When the two differ, ordinal-keyed drop tables retire (`baked_artifacts_valid()`).
- `SCHED_J2[i]`: live width of u and v at step i.
- `GAP_J2[i]` / `cmp_window()`: comparator window. `TLM_GAP_J2_DELTA`, `_LO`, `_HI` and `_TRUNC_ONLY` narrow it over a range of steps.
- `TLM_TN_SPEC`: runtime staircase that narrows both tables (b978905).
- `TLM_APPLY_FWD_CSWAP_SKIP_LAST` / `TLM_APPLY_INV_CSWAP_SKIP_LAST`: drop the apply-cswap in the last n steps.
- `TLM_APPLY_ADD_SKIP_LASTK`: drop the apply add in the last k steps.
- `TLM_TARGET_Q`, `TLM_SQUARE_PEAK_CAP`: qubit headroom caps.
- `NORMALIZER_OPS`, `MERGE25_OPS`, E208/E209: gate tables inside the Triple codec.
- `GCD_SUB_K`, `APPLY_COUT_K`, `CMP_K`, `FFG_G`, `HYB_V`: per-call carry and window tables in `schedule.rs`.
- `deep_strip_keys.rs`, `D2_DEEP_STRIP`, `route_042_action_mask.tsv`: census-mined dead-gate strips.

## How optimizations use it

- **Comparator/width truncation.** These trim the two tables, usually together so that the window stays the same distance below the register width: 3f8ce09, 2aedb45, 3222da6, 60d6185, b978905, afcc72e.
- **Iteration/threshold tuning.**
  - `ITERS` 258→261 for nonce-hunt headroom: a254a8a.
  - `ITERS` 261→259, paid for by widening 80 `SCHED_J2`/`GAP_J2` entries (+84 bits vs its base afcc72e, whose narrowing it first undoes; only 30 hot entries end wider than in f735fd7): 0422437.
  - More skip-last apply-cswaps: 474c29a.
- **Codec gate edits.**
  - A normalizer CCX→CX: 330d42d, reverted in 37ab267 and re-applied in 7726431.
  - E209 shared product: 2dabd9d, 8e62c01.
- **Ancilla-lifetime / venting.** These move the headroom caps: f5ff95b, d9ef3e9, 31f9c58.
- **Dead-gate strips.** These are re-mined after almost every geometry change: d484caa, ed4b529, 3701581 (see [dead-gate-strip.md](dead-gate-strip.md)).

## Timeline

- [3f8ce09](../commits/3f8ce09.md) (20 Jul): `cmp_window`, GAP_J2 −2 over steps 0–199.
- [a254a8a](../commits/a254a8a.md) (26 Jul): ITERS 258→261.
- [2aedb45](../commits/2aedb45.md), [3222da6](../commits/3222da6.md), [60d6185](../commits/60d6185.md) (26 Jul): tail narrowing of SCHED_J2/GAP_J2; 60d6185 is the paper's best-Q×T circuit, submission 8e9c9a2, whose promoted source commit v2 gives as `60d61859fa69` (arXiv v2, §“Best Q×T-Scoring Circuit”; anatomy in Supplemental Note D).
- [b978905](../commits/b978905.md) (26 Jul): `TLM_TN_SPEC` staircase.
- [330d42d](../commits/330d42d.md) (28 Jul), [2dabd9d](../commits/2dabd9d.md) (11 Aug), [8e62c01](../commits/8e62c01.md) (13 Aug): codec gate edits.
- [474c29a](../commits/474c29a.md) (12 Aug): apply-cswap skip-last 3/3.
- [afcc72e](../commits/afcc72e.md) (18 Aug), [0422437](../commits/0422437.md) (19 Aug): 1153 qubits; ITERS 259.
- [31f9c58](../commits/31f9c58.md) (20 Aug): last frontier on this route, 1150 q × 1,284,776 T.
- [897dda2](../commits/897dda2.md) (21 Aug): replaced by ping-pong division.

## Related concepts

[pingpong-division.md](pingpong-division.md) · [skywalk-gcd.md](skywalk-gcd.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [modular-fold.md](modular-fold.md) · [dead-gate-strip.md](dead-gate-strip.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [measurement-uncompute.md](measurement-uncompute.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md)
