# Leapfrog (route-free multi-step 2-adic walk)

> On 7 October BitWonka's 86221ad replaced both GCD Skywalk walks ([skywalk-gcd.md](skywalk-gcd.md)) with **Leapfrog**, a binary-GCD walk with much bigger steps. Each *tick* runs three add-halve steps and then strips up to three more trailing zeros. The updated rail alternates with the tick's parity, so the payload never needs Skywalk's data-dependent 256-bit route swap. A tick writes a 5-qubit letter, and 139 ticks suffice (Skywalk about 393, ping-pong about 700). The tape is a little longer than Skywalk's packed trits, so peak width rose 1172 → 1243, but executed Toffoli fell 945,335 → 804,160. Against its actual base 9db31da the score went 1,107,932,620 → **999,570,880**, the first score below 1 billion; against the leaderboard frontier 0c373cd (1170 × 946,553) the gain is −107,896,130. Three same-day follow-ups reached 1244 × 797,905.

## How it works in this circuit

**Files and routing.** The walk is `src/point_add/leapfrog.rs` (new, about 4,150 lines) plus `leapfrog_data/`. `build()` still installs the Skywalk recipe, which configures the shared replay cells, coordinate ops and square. It then calls `leapfrog::install_recipe()`, which sets `LEAPFROG=1`, so `build_point_add` sends `divide` and `multiply` to `leapfrog::divide_seamed` / `multiply_seamed`. `heo.rs` stays compiled but unused, and Skywalk's SAT rewrite rows are skipped.

**Rails and payload.** There are two *rails* R[0] and R[1], both odd integers in two's complement. The *payload* is two 256-bit registers P[i] = λ·R[i] mod p. Every rail step is repeated on the payload mod p. When the rails park at (±1, ±1), the payload therefore holds (±λ, ±λ).

**The tick** (`fwd_tick_fast`). Tick t updates the target T = R[t mod 2] from the source B = R[1 − t mod 2].

1. **Two forced add-halves**, letters s0 and s1: T ← (T + (−1)^s B)/2 with s = T[1] ⊕ B[1]. Both rails are odd, so this sign makes the sum ≡ 2 mod 4, and T stays odd. The sign costs two CX (`pp_sign_into1`).
2. **One choice add-halve**, letter s3. Both T + B and T − B are even. Exactly one of them is ≡ 0 mod 4 (the *deep* candidate D); the other is *flat*. `fast_choice` takes D when two conditions hold:
   - D is admissible, meaning D mod 32 ≠ 0, so its extra zeros e = v2(D) − 1 are at most 3;
   - the step is not "e = 1 with equal signs", which would add two equal-signed magnitudes and make the rail grow. This rule is called *sign2*.

   `LF_W1=1` reopens that excluded case: D is still taken if |T| > 4|B|, compared on a K-bit window (`w1_window`, `w1_chain`, K = `LF_W1K` = 24). The window covers bits [anchor − K, anchor + 2). The per-tick anchor comes from `anch_w1.txt`, which starts at 258 and falls by about 1.8 per tick. The compare is the carry-out of a + NOT(4b) on sign-XORed (ones' complement) windows. Apart from the window chain, all three letters s3, k1, k2 cost 5 Toffoli.
3. **Barrel**, letters k1 = e & 1 and k2 = e >> 1, for e ∈ [0, 3].
   - *On the rail* (`lin_rail_barrel`): an arithmetic right shift by e. The e known-zero low wires are rotated to the top and sign-filled, for 1.5w − 2 Toffoli.
   - *On the payload* (`cmod_barrel`): a controlled multiply by 2^−e mod p. Since p ≡ −1 and f − 1 ≡ 0 mod 16 (f = 2^32 + 977), setting m = P mod 2^e gives P·2^−e ≡ rotr_e(P − m(f − 1)). The subtraction is one fold ladder over bits [4, 4 + fs). Its addend bits are AND-monomials of m's three bits. The rotation by e is `rot4`, built from three controlled reflections ρ_1, ρ_0, ρ_−2 (i ↦ x − i); two reflections compose to a rotation. It costs 1.5n − 2 Fredkins, against 2n − 3 for two nested shift stages.

Each tick therefore removes 3 + e low bits from the target. The payload work per tick is three replay cells plus one barrel. These are ping-pong's `replay_add_halve` cells, run at the *proxy round* of the rail width (`proxy_fold`), as in Skywalk. With `LF_MERGED` the third cell and the barrel become a single op, `merged_fwd`: T ← (T ± S)·2^−(1+e). It is the production chunked add, one fold ladder over bits [0, MW), a free rotate-by-1 and `rot4`.

**Letter and tape.** Each tick's letter is (s0, s1, s3, k1, k2): five raw qubits, with no codec (`Walk.tape: Vec<Vec<QubitId>>`). The missing name s2 belongs to the three-forced-step variant (`LEAPFROG_M=3`), which the module doc still describes. 139 ticks × 5 qubits = 695 tape qubits. The author reports that all 32 letter values occur. On the reverse tick s0 and s1 are recomputed by CX and freed, while s3, k1 and k2 are erased by measurement (`fast_choice_erase`, `fast_k_erase`); the W1 compare in that phase fix runs only on shots whose outcome is 1.

**Why no routing.** Skywalk always halves the even rail, and that rail can be either one. So it needed a Fredkin row to bring the even rail into a fixed slot, and a controlled 256-bit swap in every payload cell to match. In Leapfrog the target is fixed by t's parity, which is known when the circuit is built, so each cell is wired directly.

**Seed** (`LF_SEED=half`, `seed_half_rails`, `seed_r1`). R0 = d if d is odd, else d − p (negative), on d's own wires plus an extension. R1 = (R0 ± p)/2, with + exactly when R0 ≡ 3 mod 4, so R1 is odd too. Only constant folds are used. The payload starts as (y, y/2). `LF_SEAMS=1` fuses `coord_x_sub`, `coord_add3x` and `coord_rsub_final` into the seed and unseed (`seed_r0_seam`, `seam_add_reduce`).

**Divide and multiply.** `divide_dbg` walks the rails forward with the payload fused in. Its endpoint negates P1 on s0 ⊕ s1, clears it with CX, and negates P0 on s0; then the rails walk back alone. `multiply` walks the rails forward alone, loads (±y, ±y) by the reversed endpoint, walks back with the payload fused in (`double_add` cells, `merged_rev`), and clears P1 = P0/2. That is 4 rail traversals and 2 payload passes per point addition.

**Early-tick reorder** (`LF_REORDER=76`). In the fused traversals the early ticks are qubit-bound: full-width rails sit beside both payload registers, so rail adds had to split their carry ladders under the cap. The divide now runs ticks 0..75 on the rails alone, before P1 exists, then a payload-only pass over those taped letters (`pay_fwd_tick`) while the rails wait at tick 76 (128 bits wide), then fused ticks 76..138. The multiply mirrors this (`pay_rev_tick`). No extra rail traversal is needed, because the letters are on the tape. The recipe comment prices it at −5.9k T.

**Width envelope.** Two files hold the widths, compiled in with `include_str!`:

- `env_w1_peel139.txt`: 139 per-tick rail widths, from 257 down to 7.
- `env_w1_peel139_steps.txt`: per-tick (W, n0, n1, n2, nb), the widths of the two forced adds, the choice add and the barrel.

That is about 1.8 bits per tick, against about 0.65 for Skywalk; this rate is my reading of the table. The file header says "joint fit over 1.92M walks, region-priced widths". The author describes the fit as a greedy *peeling*:

1. drop the walks that never park;
2. repeatedly lower whichever position saves the most priced Toffoli per walk sacrificed;
3. take the maxima over the surviving walks.

The author reports validating it on 1.28M fresh walks. Width failures cluster in a few "fat" walks (author: union bound 2.6e-2 against an actual 7e-4), so a uniform per-position quantile wastes width. The previous uniform envelope, `env_sign2_m2_w1.txt`, needs 140 ticks; its header gives a fresh-640k failure rate of 7.09e-4 per leg. The `lf_peel()` doc says the peeled fit reaches 139 ticks at the same failure rate.

**Room squeezes.** `LF_EARLY` holds odd rails without their constant bit-0 wire (+2 wires). `LF_TRIM` and `LF_SIGNWIRE` keep the rails at their already-implied widths during payload ops. The walk cap is `HEO_PIN_PP_WALK_MAX_QUBITS=1243`.

**Compared with the earlier walks** (per walk, at each architecture's last or first frontier):

| | Ping-pong (718a807) | Skywalk (9db31da) | Leapfrog (86221ad) |
|---|---|---|---|
| Steps | ~700 rounds | ~393 ticks | 139 ticks |
| Tape | 1 bit/round, ~700 | 5 trits in 8 qubits, ~630 | 5 raw qubits/tick, 695 |
| Payload updates per pass | ~700 cells | ~393 cells + ~393 controlled 256-bit route swaps | 139 × (3 cells + 1 barrel) ≈ 556, no routes |
| Q | 1250 | 1172 | 1243 |
| T | 888,879 | 945,335 | 804,160 |

## Why it is (or is not) exact

**Exact parts.**

- Every rail step: the forced and choice sums are even, and the barrel only shifts out known zeros. The letters are a deterministic function of the pre-step state, so whatever W1 decides the step is valid and reversible. A wrong window verdict only slows a walk; it never corrupts a value.
- Letter erasure: forced signs are recomputed; choice and barrel letters are erased by measurement ([measurement-uncompute.md](measurement-uncompute.md)).
- The barrel identity (only its fold window is truncated).
- No ties: every rail result is odd, so a payload target λ·odd is never 0, and the recipe turns the tie-safe cell mode off (`LF_TIE_FROM=999`).
- The merged op's overflow erase, where the fold fits beside the top ripple (`merged_split`, `add_consume_exact`).

**Probabilistic parts.**

1. **Depth.** A walk not parked by tick 139 gives a wrong result.
2. **Envelope.** A walk wider than its per-tick width leaves garbage.
3. **Payload-cell windows**, inherited from ping-pong: chunk-boundary and flag compares, fold windows, the retained prebias's 32-bit low cut. The recipe floors the fold window at `LF_CELL_FOLD_MIN=56` and widens the compares with `LF_CMP_SHIFT=2,3`.
4. **Barrel and merged-op fold windows** (`GO_FG_P`, `LF_MERGED_WIN` default 61, `LF_MERGED_LATE_WIN=58`), and the merged op's flag-compare fallback where the exact route does not fit.

The author reports λ = 14.4 ± 0.4, measured over 96 nonces, under the 19.5 cap inherited from Skywalk. About 12.8 of that comes from the walk (envelope tail plus no-park), which matches 7.09e-4 × 2 legs × 9,024 shots. The rest comes from payload windows. See [nonce-island-and-lambda.md](nonce-island-and-lambda.md).

## Knobs and names you will see in commits

- `LEAPFROG=1`, `LEAPFROG_M` (forced steps; code default 3, recipe 2), `LEAPFROG_RULE` (`v0` / `pp`; sign2 when unset).
- `LF_FAST`, `LF_SEED=half`, `LF_SEAMS`, `LF_TIE_SEED`, `LF_TIE_FROM`.
- `LF_W1`, `LF_W1K` (24), `anch_w1.txt`; `LF_PEEL`, `env_w1_peel139{,_steps}.txt`.
- `LF_MERGED`, `LF_MERGED_LATE`, `LF_MERGED_WIN`, `LF_MERGED_LATE_WIN` (capped at `LF_MERGED_WIN`).
- `LF_REORDER` (or `_DIV` / `_MUL`), `HEO_PIN_PP_WALK_MAX_QUBITS`.
- `LF_EARLY` (= `LF_LOWREL` + `LF_SPLIT_TIGHT`), `LF_TRIM`, `LF_SIGNWIRE`.
- `LF_CELL_FOLD_MIN`, `LF_CMP_SHIFT=dB,dF`, `LF_CMP_FROM`.

## How optimizations use it

- **Gate-level rewrite of the merged op** (9440086).
- **Fold and compare window truncation**, which spends λ margin: `LF_MERGED_LATE_WIN`, `LF_MERGED_WIN`, `LF_CELL_FOLD_MIN`, `LF_CMP_SHIFT` (58229f8, 308a6ea). See [comparator-and-width-truncation.md](comparator-and-width-truncation.md) and [modular-fold.md](modular-fold.md).
- **Choice-compare narrowing**, `LF_W1K`, and the Q-versus-T dial of reorder depth plus walk cap (both 308a6ea). See [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md).

## Timeline

- [86221ad](../commits/86221ad.md) (7 Oct, BitWonka): Leapfrog lands, 1243 × 804,160 = 999,570,880.
- [9440086](../commits/9440086.md) (7 Oct, mochimodev): `m_u_build` computes u = x + ov + 15·sg as (x + ov − sg) + 16·sg, a conditional 4-bit increment or decrement. This uses 4 ANDs instead of 8 in every merged op. 1243 × 803,254 (−906 T).
- [58229f8](../commits/58229f8.md) (7 Oct, jackylee0424): `LF_MERGED_LATE_WIN` 58 → 52. 1243 × 802,520 (−734 T).
- [308a6ea](../commits/308a6ea.md) (7 Oct, jackylee0424): built on 9440086 (against its git parent 58229f8 the diff also shows `LF_MERGED_LATE_WIN` 52 → 58). `LF_W1K` 24 → 18 with anchors 4 bits lower (`anch_w1_k18a4.txt`); `LF_MERGED_WIN` 61 → 56, which also caps the late window at 56; `LF_REORDER` 76 → 77; walk cap 1243 → 1244; `LF_CELL_FOLD_MIN` 56 → 54; `LF_CMP_SHIFT` 2,3 → 1,1. 1244 × 797,905 = 992,593,820.

## Related concepts

[skywalk-gcd.md](skywalk-gcd.md) · [pingpong-division.md](pingpong-division.md) · [transcript-codecs.md](transcript-codecs.md) · [adders-and-carries.md](adders-and-carries.md) · [modular-fold.md](modular-fold.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [measurement-uncompute.md](measurement-uncompute.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md)
