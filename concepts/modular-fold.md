# Modular fold (pseudo-Mersenne reduction)

> The secp256k1 prime is `p = 2^256 − f` with `f = 2^32 + 977`, a small 33-bit constant. So `2^256 ≡ f (mod p)`. Anything that spills past bit 256 can be reduced by adding back "the spill times `f`" into the low bits. This is the Solinas or pseudo-Mersenne fold, and it replaces a full 256-bit compare-and-subtract against `p`. The fold's carries usually die out within a few dozen bits of `f`'s top bit. The circuit therefore adds `f` only into a low *window* and drops whatever carry leaves the window. Narrowing that window is one of the most common Toffoli and qubit levers, and every narrowing adds a small chance of a wrong result.

## How it works in this circuit

**The constant.** `modular::f()` derives `f` from the modulus (`2^256 − p`). The source calls it "the only constant any modular fold in this tree folds by".

**Modular add/sub (`modular::mod_addsub`), used by the coordinate shell and the square.**
1. `acc += value` with the top carry vented onto an `overflow` wire.
2. `cadd_const_trunc(acc[..fs], f, overflow)`: if the add wrapped, add `f` into the low `fs` bits. After a wrap, adding `f` is the same as subtracting `p`, since `a + b − 2^256 + f = a + b − p`.
3. Erase `overflow` with a measured compare of the top `ERASE_COMPARE` bits (see [comparator-and-width-truncation.md](comparator-and-width-truncation.md)).

The fold window here is `fs = f_slice() = 33 + FOLD_GUARD`. In the source's words, "The dropped carry off the top of the slice is the whole approximation, so the error is ~2^-fold_guard() per call." That comment overstates the rate by about a factor of two: a carry escapes only through FOLD_GUARD + 1 consecutive 1 bits (see below), so the rate is about 2^-(FOLD_GUARD+1).

Toy example with an 8-bit "p" = 2^8 − 5:
```
200 + 100 = 300 = 256 + 44   → register holds 44, overflow = 1
44 + f(=5) = 49              → 49 = 300 − 251 ✓   (then erase overflow)
window = 4 bits: 44 = 0010_1100; low nibble 1100 + 0101 = 1_0001
→ carry out of the window is dropped → result 33 instead of 49 ✗
```
In the real circuit the window sits about 20–25 bits above `f`'s 33rd bit. A carry escapes only if all those guard bits of `acc` are 1, which for random data has probability about `f / 2^fs ≈ 2^-(fs−32)`, i.e. 2^-(FOLD_GUARD+1).

**The replay cell (`pingpong.rs::replay_add_halve` / `replay_double_add`).** Each replay round of the ping-pong divider (see [pingpong-division.md](pingpong-division.md)) computes `target ← (target ± source)/2 mod p`. The sign, the parity of the sum, and the 2^256 overflow together select exactly one of `{−f, 0, +f, +2f}` to add before halving. Making an odd sum even means adding `p ≡ −f`, and an overflow contributes `+f`. `fold_selected` adds the chosen value into `target[..fold_window]` without building an operand register. The window is set per round:

```
fold_window(round) = PP_REPLAY_FOLD_WINDOW (divide) or PP_REPLAY_FOLD_WINDOW_MUL (multiply)
                   + band_at(PP_FOLD_PROFILE, walk width at this round)
                   + 1 if round < PP_FOLD_WIDEN
                   + GO_FWIN slice delta
```

The profile is measured, not derived. The doc comment on `fold_shape` reports escape rates, relative to the flat region, from narrowing one block of rounds at a time: 0.88–1.06 at walk widths 253..73, then 0.70 at 41, 0.46 at 35, 0.14 at 28 and 0.049 at 8. The late rounds can take narrower windows (`"38:0,32:-1,19:-4,0:-4"`). The window of the trailing batch also *sets the peak*: "the cell's fold is the widest thing alive in the trailing batch". So narrowing it there can lower peak qubits, not just Toffoli.

**Endpoint folds.** `mod_halve_pm`, `mod_double_pm`, `seed_round_one` and the conditional negate fold `f` or `f − 1` over `f_slice() = 33 + FOLD_GUARD` bits in the 27–29 Sep ping-pong trees. From the Skywalk tree (8ee337c) on they use `go_fs("GO_FG_P")`, which is `33 + FOLD_GUARD` plus an offset. In the August `pingpong_div.rs` this was `SUB4_PP_ENDPOINT_FOLD_WINDOW`. That code describes the carry chain as `min(n−2, highest_set_bit(f) + window)` long, so one window bit is one carry ancilla.

**NAF folds in the square.** The square produces a high limb `H` of many bits, and `f·H` must be folded. The code writes `f` in non-adjacent form (NAF, a signed-digit form): `F_NAF = 1 + 2^4 − 2^6 + 2^10 + 2^32`, five signed terms. `fold_rotated` folds the unit term by rotating the wrapped limb into the vacated low positions, so it rides inside the main `mod_addsub`. The other four terms are each a shifted `window_add` of `H` with `FOLD_GUARD` bits of headroom, and carries past that headroom are dropped. The paper's main text writes `F = 2^32 + 2^10 − 2^5 − 2^4 + 1` instead (arXiv v2, §“Karatsuba Squaring with Pseudo-Mersenne Modulo”). That is also five terms and also equals 2^32 + 977, but it is a different signed form from the one in the code. The supplemental notes use the code's form: Supplemental Note D (“Stage 4 detail: symmetry-aware streamed Karatsuba squaring”) writes `F = 2^32 + 2^10 − 2^6 + 2^4 + 1`, and Supplemental Note B (“Strength Reduction”, “Signed-digit constant decomposition”) gives 977 = 2^10 − 2^6 + 2^4 + 2^0. Fusions merge these windows: `PP_J_BMERGE`, `PP_J_WCIN` and `PP_J_SFUSE_B` (see [squaring-and-karatsuba.md](squaring-and-karatsuba.md)).

## Why it is (or is not) exact

The identity `2^256 ≡ f` is exact. A fold with an untruncated carry chain is exact. Dead-low carry elision inside the fold adder is exact too (see [adders-and-carries.md](adders-and-carries.md)). The approximation is the dropped top carry. If a carry would have left the window, the register ends up `2^W` too small. That is a wrong field element, so the shot fails the classical-value check. Each window bit removed roughly doubles that site's failure rate. A fold runs once or more per replay round, over about 700 rounds in each direction, so these small rates add up to a real share of λ, the expected number of failing inputs per 9,024-shot test island. A narrower window therefore needs a fresh clean nonce (see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)).

Two balance rules in the source guide the tuning:
- One `FOLD_GUARD` serves every non-replay fold, because "the balance rule makes them all want the same per-call error whatever their call counts are".
- The replay profile equalises the per-round error ("Minimising total window bits at fixed total error equalises the PER-ROUND error").

`PP_SPLIT_FOLD` (off by default) splits `k·f` into `k·977` and `k·2^32` ripples and deliberately drops the wrap between them, which is another bounded approximation.

**Caveat on numbers:** what a window number means has changed between code generations. In the August `pingpong_div.rs`, the helper's window argument counted positions *above* `f`'s top bit (its source comment says so). In the current `pingpong.rs`, the replay window is the absolute slice length (`target[..fold_window]`). `FOLD_GUARD` counts bits above `f`'s 33. Compare window values only within one generation.

## Knobs and names you will see in commits

- `FOLD_GUARD` (`HEO_PIN_FOLD_GUARD`): headroom above `f` for coordinate-shell, endpoint and square folds; `f_slice() = 33 + FOLD_GUARD`.
- `PP_REPLAY_FOLD_WINDOW`, `PP_REPLAY_FOLD_WINDOW_MUL` (older `SUB4_PP_REPLAY_FOLD_WINDOW`, "replay fold window"): base replay window.
- `PP_FOLD_PROFILE`: per-walk-width band offsets for that window.
- `PP_FOLD_WIDEN` ("FOLD_WIDEN"): +1 window bit on the first N rounds.
- `PP_RETAIN_LATE_WIDEN`, `GO_FWIN`: other per-round widenings.
- `SUB4_PP_ENDPOINT_FOLD_WINDOW` ("endpoint fold window"), `GO_FG_P`, `GO_FG_M`: endpoint and modular-add fold offsets.
- `add_f_window`, `cadd_const_trunc`, `fold_selected`, `fold_rotated`, `window_add`, `F_NAF`, `PP_SPLIT_FOLD`: the code that does the folding.
- Older names: `KAL_FOLD_CARRY_TRUNC_W`, `DIALOG_GCD_FOLD_CARRY_TRUNC_W` (dialog era, per the toffoli-reduction skill), `R84_QPROD_NAF`.

## How optimizations use it

- **Dead-Code → fold/carry truncation** (53 census commits: 37 original, 16 since): narrow a window or carry tail. [`8cdc0e6`](../commits/8cdc0e6.md): endpoint window 55→54 drops one carry ancilla, peak 1321→1320. [`787eaa8`](../commits/787eaa8.md): replay window 54→53 (about 1,400 of the commit's −2,549 T, so roughly 1.8M of score, at a cost in classical λ only).
- **Per-round fold shaping that lowers the cap**: [`1196b9f`](../commits/1196b9f.md) introduces `PP_FOLD_PROFILE` bands and drops the cap 1263→1260. [`9700396`](../commits/9700396.md) narrows the profile one more bit, cap 1259→1258.
- **Sell/buy repackages**: [`03d9ecd`](../commits/03d9ecd.md) sells `FOLD_GUARD` 25→21 and buys back with `PP_FOLD_WIDEN` 64. [`291d749`](../commits/291d749.md) moves widening from late rounds to the first 76.
- **Strength Reduction → solinas / NAF fold** (5 commits, all in the original census, e.g. `ed94ad2` NAF recoding of a constant product): fewer add/sub passes per fold. Fold fusions such as [`a231a39`](../commits/a231a39.md) are filed under Fusion.

## Related concepts

[adders-and-carries.md](adders-and-carries.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [squaring-and-karatsuba.md](squaring-and-karatsuba.md) · [pingpong-division.md](pingpong-division.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [scoring-and-validation.md](scoring-and-validation.md)
