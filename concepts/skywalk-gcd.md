# GCD Skywalk (HEO walk with trit-packed history)

> On 29 September mochimodev (Matt Zweil with MAI-A.A.E., Mochimo Foundation) replaced the ping-pong walk ([pingpong-division.md](pingpong-division.md)) with **GCD Skywalk** in 8ee337c. It follows Stein's binary GCD: at each step the even operand is halved, or, when both are odd, the larger is replaced by half the difference. A fixed alternation is no longer used. The circuit avoids a magnitude comparison by keeping the pair in a {u+v, u} form where exactly one rail is even. In that form halving is just relabelling wires. Each step records a three-valued symbol (a *trit*), and five trits pack into eight qubits. The walk needs about 390 steps where ping-pong needed about 700, and the total history is shorter. Peak width fell from 1250 to 1174 qubits while executed Toffoli rose about 6.4% (888,879 → 946,250). The score improved slightly: 1,111,098,750 → 1,110,897,500. Those figures are against the frontier at the time, its git parent 718a807. Against its actual base a231a39 (1250 × 889,202 = 1,111,502,500) the change is +57,048 T and −605,000 score. The sky5…sky12 follow-ups (30 Sep–1 Oct) tune its windows.

## How it works in this circuit

**Files.**

- `src/point_add/heo.rs` holds the rail tick, seeds, envelopes and configuration.
- `heo_carry.rs` holds the production "CARRY" schedule, the tape and the trit codec.
- `codec_synth.rs` and `codec_probe.rs` hold the synthesized packers.
- `fd_coordinate.rs` and `back_seam.rs` fuse the walk's seed and unseed with the coordinate arithmetic; `moddiv_adapter.rs` is a helper interface between the parked signed rails and a positive odd cofactor.

The module docs still describe HEO as an inert "research seam", but `build()` calls `install_skywalk_submission_recipe()`. That sets `HEO_WALK=1` and `HEO_SCHEDULE=carry`, so `build_point_add` routes phases `divide` and `multiply` through `heo::divide` / `heo::multiply`.

**The recurrence.** This is Stein's binary GCD, min-source form, as the submission note describes it. With v odd:

- if u is even, u ← u/2;
- if both are odd, the smaller becomes the retained odd operand and the larger becomes |u − v|/2.

Represent the state by the unordered magnitudes {u+v, u}. Exactly one of the two is even. Call it E and the other O. The next state is {E/2, |O − E/2|}. Example with u = 5, v = 13 (magnitudes):

```
{18, 5} -> E=18: {9,  |5-9|=4}
{9, 4}  -> E=4 : {2,  |9-2|=7}
{2, 7}  -> E=2 : {1,  |7-1|=6}
{1, 6}  -> E=6 : {3,  |1-3|=2}
{3, 2}  -> E=2 : {1,  |3-1|=2}
{1, 2}  -> E=2 : {1,  |1-1|=0}    # parked: gcd = 1
```

**One rail tick** (`heo::fwd_tick`, "ported gate for gate from heo_gates.py"). The rails start at `(R1, R2) = (d + p, d)` in two's complement, where d is the denominator.

1. `c = R1[0]`.
2. Fredkin-swap `R1[i] ↔ R2[i]` on `c` for i ≥ 1, then `R2[0] ^= c`. The even rail is now in R1.
3. `E/2 = R1[1..]`. This is a relabel: no gates are spent on the halving.
4. `R2 ← R2 ∓ E/2`, subtracting when the signs agree. The circuit keeps signs instead of taking absolute values.
5. The `c` wire leaves the rail and becomes the tape's orientation bit, `typ_t = typ_{t-1} ⊕ c_t`. The add's sign-flip wire becomes `s_t`.

The doc comment gives the cost per tick as exactly `(esw − 1) + (ead − 1)` CCX, where `esw` and `ead` are that tick's swap and add widths from the *envelope* file (`HEO_ENVELOPE`, `HEO_ENVELOPE_MUL`). The loaders only check that those variables are set; the table data is compiled in with `include_str!`. At 8ee337c each leg has 393 ticks (392 for multiply). The widths fall from 259 to 3 (swap) and 2 (add), roughly 0.65 bit per tick. Ping-pong's schedule falls from 259 to 8 over 700 rounds, about 0.36 bit per round. These rates are my reading of the two tables. The submission note gives typical convergence as "roughly 360 Skywalk steps versus 620 Pingpong rounds", and the fixed public lengths as about 390 and 700. The intuitive reason: ping-pong halves whichever register the round number picks, while Skywalk always halves the even rail and always subtracts from the larger one.

**Trit history.** The pair (typ, s) takes only three legal joint values on the walk (submission note), so each tick's record is a trit stored on two raw wires. `Tape` (heo_carry.rs) packs letters in groups of five:

- `pack3` folds three trits (6 wires) into 5. It uses `codec_synth::pack_compatible_shared`, which is 3 CCX plus a measured cleanup and is certified on all 27 valid states.
- `pack5` packs two more trits (4 wires) into 3 more. A group therefore occupies 8 qubits, since 3⁵ = 243 ≤ 256.

That is 1.6 qubits per tick, against 2 raw and against ping-pong's 1 qubit per round. Over about 393 ticks the history comes to roughly 630 qubits against ping-pong's roughly 700-bit tape. This is my estimate; the note says only "a shorter total history". Groups are unpacked in LIFO order as the walk-back or the batch replay consumes them (`HEO_DIV_LIFO_N`, `HEO_MULB_LIFO_N`).

**Payload, and the "FD" frame.** The two field payloads are carried as a sum/difference ("butterfly") pair `(Sig, Del)`. The division cell is

```
Sig <- (Sig - (-1)^g Del) / 2  (mod p),   g = typ_t
if s: swap(Sig, Del)
```

With the base seed, `(Sig, Del) = (2N, 0)`. At park `Sig == Del == N/d`, so the endpoint is `Del ^= Sig` at 0 CCX. The multiply leg reverses the order: exchange first, then double and add. The halving cell is ping-pong's own `pingpong::replay_add_halve`, run "at the proxy round of the rail width". This is why ping-pong knobs survive as `HEO_PIN_PP_*` pins. `HEO_CARRY_SEED=fd` selects a fused start frame (`fd_seed`, `fd_coordinate.rs`: "Coordinate subtraction / native FD seed fusion") that merges dx = x − ox with tick 0. The source never spells out what "FD" stands for.

**Schedule** (heo_carry.rs header). The divide leg runs:

1. seed;
2. fused forward ticks for t < `HEO_R2D`: tick → pack → cell → route;
3. rails-only forward ticks;
4. loan of the terminal wires;
5. a trailing batch of cells, unpacking and repacking groups;
6. endpoint;
7. unloan, the reverse walk, unseed.

The multiply leg mirrors this, with `HEO_R2M` and a head batch. Carry ladders are sized under `HEO_PIN_PP_WALK_MAX_QUBITS = 1174`.

**Why Q falls but T rises.** There are fewer ticks and the history is shorter, and that sets the replay peak. But every tick pays for a full-width Fredkin row on the rails plus the rail add. Every payload cell also carries a conditional 256-bit swap ("route") on top of ping-pong's cell. The note sums this up: "Skywalk pays additional routing per step, but performs many fewer steps".

## Why it is (or is not) exact

- **The tick itself is exact** as long as the envelope's promise holds. `resize` trims a wire by CXing it with the bit below and then freeing it, so the trimmed wire must be a sign copy.
- **Fixed depth.** A walk that has not parked by tick R gives a wrong result, so the tick count is a truncation, just like ping-pong rounds.
- **Inherited truncations.** The payload cells inherit ping-pong's chunk-boundary compares, flag compares and fold windows.
- **Windowed split repairs.** Split rail and fit adds can use windowed repairs: `HEO_SPLIT_K` (only on the multiply leg's fused walk-back ticks), and `HEO_FIT_MODE=win` / `HEO_FIT_K`.
- **Tie-safe zone.** Early cells run tie-safe (`HEO_ZONE` in the carry schedule). The comment on `tie_ticks` explains why: Del is seeded 0, so one early cell per walk has a zero target where seeded top-k compares tie. That remark is about the unused v0 (`fused`) schedule, where about 25% of shots failed phase.
- **Codecs.** These are exact on the valid trit support.
- **SAT-proved rewrites.** Rows in the `SKY_REWRITE` tables are exact on reachable states. They are keyed to op positions, though, so they must be re-proved whenever the stream shifts. 800ba12 dropped them for that reason.

8ee337c also carries a "limiting contract": any later work must keep the circuit's λ below 19.5 on 9,024 shots, and must not cut rounds. The follow-ups state that they spend λ up to that limit (bdff8c8, f260d33). See [nonce-island-and-lambda.md](nonce-island-and-lambda.md).

## Knobs and names you will see in commits

- `HEO_WALK`, `HEO_SCHEDULE=carry`, `HEO_SEED`, `HEO_CARRY_SEED=fd`: route selection and seed frame.
- `HEO_ENVELOPE`, `HEO_ENVELOPE_MUL` (`skywalk_data/*`, later `sky8_env_*_iA.*.100`): per-tick `esw ead` widths. The variables are only checked for presence; the data is compiled in via `include_str!`. A wider envelope is an error buy-back.
- `HEO_R2D` (375→382 in sky5), `HEO_R2M`: fused/batch checkpoints.
- `HEO_SPLIT_K` (default 24; 21 in 4ea960f/70148ce): the boundary-carry erase window of split rail adds (`rail_add_inner` / `fama_add` in `SplitMode::Approx`), applied only to the multiply leg's fused walk-back ticks. The code applies it as exact on a leading chunk ≤ K and top-K bits otherwise.
- `HEO_FIT_K` (24→23→22): window for the chunked adds fitted under the cap.
- `HEO_DB_SKIP2` / `HEO_MB_SKIP2`: skip the divide or multiply batch route (a controlled swap) at t = R−2. That route is the identity except on walks that park exactly at R. The cost is priced in λ.
- `GO_CELLB` / `GO_CELLF`: ±1 bit per (leg, tick band) on the cells' boundary compare and flag compare (`go_cell_delta`).
- `GO_CHUNK`: per-round chunk-compare shift (`go_slice` in pingpong's `chunk_compare`).
- `HEO_CELL_WINDOWS`: a tsv of per-tick (dB, dF, dX) shifts.
- `HEO_PIN_<NAME>`: overrides a ping-pong pin, e.g. `HEO_PIN_PP_CHUNK_SHAPE`, `HEO_PIN_ERASE_COMPARE`, `HEO_PIN_FOLD_GUARD`, `HEO_PIN_SQ_ASM_TAIL`.
- `SKY_REWRITE` / `skyN_*_rewrite.txt`: offline SAT-proved CCX → CX-chain rows.
- `HEO_CODEC_SYNTH`, `HEO_CARRY_CODEC`, `HEO_REVERSE_CARRY_CODEC`, `GO_*_SHARE`: synthesized packers and reuse of a product the walk has already computed.

## How optimizations use it

- **Comparator/width truncation** (4ea960f, 70148ce, bdff8c8, f260d33, 84e78ce). These buy back error with wider envelopes, then sell compare and window bits per tick band.
- **Dead-gate removal** (800ba12, `HEO_MB_SKIP2`).
- **Fusion** (82c849b, sky5). The FD payload doubling and negation are fused, and `coord_y_sub` / `coord_y_sub_final` are folded into the payload seed and its inverse.
- **Host-derived specialization** (0642f52). More SAT rewrite rows.

## Timeline

- [8ee337c](../commits/8ee337c.md) (29 Sep): GCD Skywalk lands, Q 1250→1174.
- [82c849b](../commits/82c849b.md) (30 Sep): sky5 fusions, codec shares, first 57 SAT rows.
- [0642f52](../commits/0642f52.md) (30 Sep): sky6, +11 SAT rows.
- [4ea960f](../commits/4ea960f.md) (30 Sep): sky8, iA.100 envelopes, `HEO_SPLIT_K` 21, `GO_CELLB/F`.
- [800ba12](../commits/800ba12.md) (30 Sep): `HEO_MB_SKIP2`.
- [70148ce](../commits/70148ce.md) (30 Sep): sky8 ported onto 800ba12.
- [bdff8c8](../commits/bdff8c8.md) (30 Sep): sky9, `GO_CHUNK` 0-399:−1.
- [f260d33](../commits/f260d33.md) (1 Oct): sky10, `HEO_FIT_K` 22, `ERASE_COMPARE` 22.
- [84e78ce](../commits/84e78ce.md) (1 Oct): sky12, more `GO_CELLB/F` bands; 1174 × 944,682.
- [86221ad](../commits/86221ad.md) (7 Oct): Skywalk is replaced by the route-free Leapfrog walk ([leapfrog.md](leapfrog.md)), 1243 × 804,160.

## Related concepts

[pingpong-division.md](pingpong-division.md) · [trailmix-jump-gcd.md](trailmix-jump-gcd.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [dead-gate-strip.md](dead-gate-strip.md) · [modular-fold.md](modular-fold.md) · [measurement-uncompute.md](measurement-uncompute.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md)
