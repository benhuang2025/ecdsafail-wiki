# Ping-pong division (fixed-depth signed binary division)

> On 21 August teddyjfpender's 897dda2 replaced the GCD inverse ([trailmix-jump-gcd.md](trailmix-jump-gcd.md)) with a direct divider: `numerator *= denominator^{-1} (mod p)`, and the same machinery run backwards for `numerator *= denominator`. Two odd signed registers take turns being halved ("ping-pong"), in a fixed order and for a fixed number of rounds. No comparison is needed. Each round stores exactly one sign qubit on a *tape*. A *replay* then applies the same rounds, mod p, to a coefficient pair, and the result is the quotient. A *walk-back* restores the denominator and erases the tape. Compared with the trailmix route it cost 171 more qubits but saved about 332k Toffoli: 1321 q × 952,707 T against 1150 × 1,284,776. Until 29 September every frontier commit tuned this structure.

## How it works in this circuit

**Files.** `src/point_add/pingpong_div.rs` held the code from 897dda2 until nipzu's clean-room rewrite 1196b9f (5 Sep). After that it lives in `src/point_add/pingpong.rs`, and the knob prefix changes from `SUB4_PP_*` to `PP_*`. The affine shell is unchanged: phase `divide` computes y ← y/x and phase `multiply` computes y ← y·x.

**The value walk** (`value_walk`, later `walk_round`). It starts with `u = p` and `v = denominator`, both in a signed envelope of `VALUE_WIDTH = N + 3` bits. Round 0 makes an even denominator odd by lifting it to a − p, and keeps one lift bit. Every later round alternates roles: source and target are (u, v) on even rounds and (v, u) on odd rounds.

```
sign   = target[1] XOR source[1]                 # the one tape bit
target = (target + (-1)^sign * source) / 2       # sum is 2 mod 4, so the result is odd again
```

Toy run, using the general rule from the first round (the real rounds 0 and 1 are special lift/seed cases), with u = 13, v = 5:

```
round  target  source  sign  new value
  0    v=5     u=13     0    v = (5+13)/2  = 9
  1    u=13    v=9      0    u = (13+9)/2  = 11
  2    v=9     u=11     1    v = (9-11)/2  = -1
  3    u=11    v=-1     0    u = (11-1)/2  = 5
  4    v=-1    u=5      1    v = (-1-5)/2  = -3
  5    u=5     v=-3     0    u = (5-3)/2   = 1
  6    v=-3    u=1      0    v = (-3+1)/2  = -1
  7    u=1     v=-1     1    u = (1+1)/2   = 1     -> fixed point (+1, -1)
tape = 0 0 1 0 1 0 0 1
```

The magnitudes shrink, so a per-round width table narrows u and v. At first this was the linear `value_width()`. From b5796ce it is a 700-entry `WIDTH_SCHEDULE`, later `PP_WIDTH_SCHEDULE`. Trimming a top wire is a CX from the wire below it followed by `free`, which is only valid if the top bit was a sign copy. The walk add uses only Clifford gates for its first two carries (`signed_add_wrapping_sigma`). Because bit 0 is always 1, later versions keep it off any wire (`park_odd_bits`).

**The coefficient replay** (`replay_halving`). The same signed halvings run mod p on the pair (`coefficient`, `numerator`), seeded with (0, c). The map is linear and (p, a) ≡ (0, a), so the end state is (±c/a, ±c/a), with the signs of the terminal u and v. In the toy run mod 13 with c = 1, the pair ends at (8, 5) = (1/5, −1/5). `conditional_mod_negate` by each terminal sign makes the two registers equal, and a row of CXs clears one of them. Multiply runs the time-reverse. It seeds the terminal pair and runs `replay_doubling_inverse`, whose round is `T = 2T′ ± S`, back to (0, a·c).

Each replay round is one fused cell (`signed_mod_add_pm_halve_fused`, later `replay_add_halve`) made of three parts:

- **Chunked add** (`add_chunked_measured`). A 256-bit add is split into chunks. At first `REPLAY_CHUNK = 96` is only a size limit: `chunk_bounds` splits evenly, so 256 bits become chunks of 86, 85 and 85. From the ladder-budget commits on, the chunk layout is sized per round from the live-ladder budget (`chunk_layout`), with the 96-bit limit kept only as the no-budget fallback. Inside a chunk, Gidney carries are uncomputed exactly by measurement. Each carry at a chunk boundary is measured out (`hmr`), and its phase is repaired with a truncated compare (`cmp_lt_phase_conditioned`) of the top `REPLAY_CHUNK_COMPARE` bits of sum and addend.
- **Fold.** The overflow is corrected by adding one of {−f, 0, +f, +2f} with f = 2³² + 977, using a mask-free ripple restricted to the low `REPLAY_FOLD_WINDOW` bits (see [modular-fold.md](modular-fold.md)).
- **Flag compare.** The overflow flag is measured out and repaired by comparing the top `REPLAY_FLAG_COMPARE` bits.

**Walk-back and endpoint.** `value_walk_back` runs the walk in reverse. It consumes and frees each tape sign and restores the denominator, plus the lift bit. 897dda2's *sparse endpoint recovery* reconstructs the canonical denominator from the signed round-0 half-state. It uses one short carry chain, because 2w = a + k·p with k = a₀ − 2·¬a₁, so only k·f needs adding to the low word. The terminal `conditional_mod_negate` and the endpoint corrections are truncated pseudo-Mersenne chains of length about `hsb(f) + ENDPOINT_FOLD_WINDOW` (8cdc0e6). This is the **endpoint fold**.

**Depth.** The depth started as `ROUNDS = 704`, later `rounds()` / `SUB4_PP_ROUNDS`. Two parallel commits cut it: 704 → 703 (850db0c) and, on the eb187a4 line, 704 → 700 (be0c8bc). After that the two directions get separate depths. The divide keeps `rounds()`. The multiply uses `SUB4_PP_ROUNDS_MUL`, which was `rounds()−1` in 9652eec and later anything from −7 to +2 (b5796ce). In `pingpong.rs` the divide depth is simply the length of the width schedule (`rounds_div()`), and `PP_ROUNDS_MUL` is separate (698 at 718a807). The reasons for the asymmetry: the multiply cell keeps one extra wire, the shifted-out top bit `doubled_out`, and the multiply walk "converges in slightly fewer rounds" (pingpong.rs comment).

**The peak and why ladders matter.** The tape is fully live while it is replayed, so tape length sets the peak. The 08-pingpong-1300 memory note gives the flat batch-replay plateau:

```
700 tape + 256 coefficient + 256 numerator + 2 terminal signs + 86-wide chunk carry ladder = 1,300
```

Later commits shrink this in three ways:

- **Loaning provably-known wires** for the length of the replay: 152fbe0, 522d002 (see [venting-and-wire-loans.md](venting-and-wire-loans.md)).
- **Interleaving the replay with the walk.** Rounds below `r1` are replayed in one batch, rounds in `r1..r2` beside their own walk round, and rounds above `r2` at the loaned terminal state (cb56b71, f3b2f1f `plan()`). Early replay rounds then share the machine with only part of the tape. The late rounds, where the peak sits, still have the full tape and both coefficient registers live; they fit by shrinking their own scratch.
- **Sizing each chunked add's carry ladder** to the space left under a target peak: `SUB4_PP_PEAK`, `LADDER_TARGET` / `chunk_layout` (e928607), and finally `PP_WALK_MAX_QUBITS`, which reads the builder's live count.

Fewer, wider chunks need fewer approximate boundary repairs, so they cost fewer Toffoli but more qubits. The ladder budget is therefore the Q-versus-T dial. The product-register square has its own ladder budget (`SQUARE_LADDER`, `SQUARE_CHUNK_MIN`) so that it stays under the same cap. See [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md).

## Why it is (or is not) exact

The arithmetic inside each chunk is exact. Five things can make a shot fail:

1. **Depth is a truncation.** The walk is accepted only if it reaches (±1, ±1) by the last round, which is a fixed point. An input that needs more rounds yields a wrong quotient and dirty wires. The memory note gives the per-walk failure as about 2.5–4×10⁻⁴ at 700 rounds. Each round cut saves a walk add, a walk-back add and a replay cell (about 365 T in 9652eec), plus one tape qubit, but raises λ.
2. **Width schedule.** A trimmed top bit that was not a sign copy leaves garbage.
3. **Compare windows.** A chunk or flag repair is wrong when the compared top bits of sum and addend agree. The value is still right, but the phase is not. The failure rate depends on the walk's remaining width, which is why the late band tables `PP_CHUNK_SHAPE` and `PP_FLAG_SHAPE` are keyed on width.
4. **Fold windows.** If a carry runs past the window it is dropped, which gives a wrong value. The 09 memory note calls the endpoint window "λ-free down to ~25".
5. **Measured early erasure of tape bits.** Commits such as 5526766 recompute these bits later from linear walk invariants.

All of these are priced as λ, the expected number of failing shots per 9,024-shot draw. Validation demands 0/0/0 on the circuit's own draw, so every edit needs a new nonce. See [nonce-island-and-lambda.md](nonce-island-and-lambda.md).

## Knobs and names you will see in commits

- `ROUNDS`, `ROUNDS_DEFAULT`, `rounds()`, `SUB4_PP_ROUNDS`, `rounds_div()`: divide depth.
- `SUB4_PP_ROUNDS_MUL` / `PP_ROUNDS_MUL`: multiply depth, often written `rounds()−k`.
- `value_width`, `SLOPE_*`/`BREAK_*`, `WIDTH_SCHEDULE`, `PP_WIDTH_SCHEDULE`: walk width per round.
- `REPLAY_CHUNK_COMPARE`, `REPLAY_FLAG_COMPARE`: repair compare widths. Chunk went from 26 at 897dda2 to 21 at 718a807 (20 on some branches). Flag went from 28 to 20.
- `PP_FLAG_WIDEN_DIV`: walk-width threshold. Divide rounds whose walk is at least this wide get +1 flag-compare bit. Walk widths never exceed 259, so 696 turns the widening off (718a807).
- `REPLAY_FOLD_WINDOW` (`_MUL`): replay fold window (56→53).
- `ENDPOINT_FOLD_WINDOW`: terminal and endpoint fold (55→18 at the narrowest).
- `PP_FOLD_PROFILE`, `PP_CHUNK_SHAPE`, `PP_FLAG_SHAPE`, `PP_FOLD_WIDEN`: per-band offsets on the windows above.
- `plan()`, `SUB4_PP_R1`/`R2`, `PP_R2`, `SUB4_PP_PEAK`, `SUB4_PP_QSTAR`, `PP_WALK_MAX_QUBITS`: interleave checkpoints and the peak cap.
- `LADDER_TARGET`, `chunk_layout`, `SQUARE_LADDER`, `SQUARE_CHUNK_MIN`: carry-ladder budgets.
- Tape-bit lifetime tricks: `SIGN1_FREE`, `A0_FREE`, `BCHAIN_MUL` (5526766) and `PP_N_HOLE2` (265a9e9).

## How optimizations use it

- **Iteration/threshold tuning** cuts rounds: 850db0c, be0c8bc, 9652eec, 99d85b5, 1f6b836, 6b5c82c, 64f9aaa.
- **Comparator/width truncation** narrows compares and widths: cae8c82, 920c5bb, 6ee4d14, d631017, b5796ce (fitted width table), 718a807.
- **Fold/carry truncation** narrows fold windows: 8cdc0e6, 37b0c9f, 8e8f047, d1bb787, edeed3f, 1196b9f (band profiles).
- **Ancilla-lifetime / venting** reshapes live ranges and budgets: 152fbe0, cb56b71, f3b2f1f, e928607, 0b82781, 5526766, 265a9e9.
- **Scratch reuse** parks derived temporaries in live wires (51c6c31) and lends wires known to hold constants (c1adf3e, cc7f10e).

## Timeline

- [897dda2](../commits/897dda2.md) (21 Aug): introduced; 704 rounds, 1321 q.
- [8cdc0e6](../commits/8cdc0e6.md), [6ee4d14](../commits/6ee4d14.md), [850db0c](../commits/850db0c.md), [be0c8bc](../commits/be0c8bc.md) (21 Aug): first window and depth cuts; 703 rounds and 1319 q on 850db0c's line, 700 rounds and 1318 q on be0c8bc's.
- [152fbe0](../commits/152fbe0.md) (21 Aug): terminal wire loans, 1301 q. [9652eec](../commits/9652eec.md): `ROUNDS_MUL = rounds()−1`, 1300 q.
- [cb56b71](../commits/cb56b71.md), [f3b2f1f](../commits/f3b2f1f.md), [e928607](../commits/e928607.md) (21 Aug): walk/replay interleave and ladder budgets, 1281→1278 q.
- [b5796ce](../commits/b5796ce.md) (22 Aug): data-fitted `WIDTH_SCHEDULE`.
- [d919bc6](../commits/d919bc6.md), [6752417](../commits/6752417.md) (23 Aug): Karatsuba square plus round fusions at 1273 q (d919bc6), then 51c6c31's wire parking merged in at 1267 q (6752417).
- [5526766](../commits/5526766.md) (28 Aug): early erasure and recompute of tape sign bits.
- [1196b9f](../commits/1196b9f.md) (5 Sep): clean rewrite into `pingpong.rs`, per-band window profiles.
- [cc7f10e](../commits/cc7f10e.md) (25 Sep): 1259→1251 q. [265a9e9](../commits/265a9e9.md) (27 Sep): 1251→1250 q.
- [718a807](../commits/718a807.md) (29 Sep): last ping-pong frontier, 1250 × 888,879. Replaced by [8ee337c](../commits/8ee337c.md).

## Related concepts

[trailmix-jump-gcd.md](trailmix-jump-gcd.md) · [skywalk-gcd.md](skywalk-gcd.md) · [adders-and-carries.md](adders-and-carries.md) · [modular-fold.md](modular-fold.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [measurement-uncompute.md](measurement-uncompute.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [squaring-and-karatsuba.md](squaring-and-karatsuba.md)
