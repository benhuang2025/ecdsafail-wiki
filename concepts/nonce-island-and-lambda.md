# Tail nonce, island and λ

> The 9,024 test inputs are a hash of the op stream, so changing *any* gate draws a new test set. Every op stream ends with an identity tail of `X;X` pairs. This tail is a free knob: it changes the hash, but not the circuit, its Toffoli count or its width. The tail encodes a number, the *tail nonce*. The test set a given stream plus nonce draws is called its *island*. Approximate circuits are wrong on rare *hard inputs*. **λ** is the expected number of failing shots in one draw, and a random nonce gives a clean island with probability of roughly e^(−λ). Contestants therefore *hunt* for a nonce whose island happens to be clean. Every circuit change forces a new hunt, and pushing truncation further makes the hunt exponentially longer.

## How it works in this circuit

**The tail.** At the end of `build()` in `src/point_add/mod.rs`, 96 `X` ops are appended, and then `apply_tail_nonce` rewrites them:

```
for b in 0..48:  target = qubit((nonce >> b) & 1)    // qubit 0 or qubit 1
                 ops[start+2b]   = X(target)
                 ops[start+2b+1] = X(target)          // X·X = I
```

That gives 48 bits of nonce for zero Toffoli, zero Clifford (X is not counted) and zero new qubits. Changing only `q_target` changes the SHAKE256 seed, so it changes both the test inputs and the `R`/`Hmr` outcomes; see [scoring-and-validation.md](scoring-and-validation.md). The tail goes on after the exact post-pass simplifiers, "so the 96-X identity tail and the nonce it encodes are never reinterpreted by a proof". The code calls the baked value the *ground nonce* (as in ground by search). Its name has changed with each route:

- `DIALOG_TAIL_NONCE` — dialog-GCD era.
- `SUB4_TAIL_NONCE` / `SUB4_PINGPONG_TAIL_NONCE` — an `.unwrap_or(<literal>)`.
- `TAIL_NONCE` — today, pinned in `env_raw` (`"16000761750475"` at `799153a`).

One submission, [`9b2ce61`](../commits/9b2ce61.md), briefly packed the nonce into a 14-op base-1024 tail.

**Hard inputs and λ.** Many levers are approximate:

- A truncated carry or fold window of w guard bits drops a carry only when all w+1 relevant accumulator bits are 1 (add) or 0 (subtract), about 2^−(w+1) per call. `modular.rs` rounds this to "the error is `~2^-fold_guard()` per call".
- A comparator that looks only at the top bits misjudges ties.
- A fixed-depth GCD walk or a narrowed per-round width schedule fails to converge on some inputs.

Each such site adds (calls × 9,024 × per-call error) to λ. Sources define λ as *expected failing shots per draw*: the `b5796ce` memory note and the clean-nonce skill both say this. The task framing here says "failing batches". `eval_circuit` counts classical failures per shot but phase and ancilla failures per 64-shot batch. While λ is small next to the 141 batches, the two counts nearly coincide.

**Why e^(−λ) is only a sketch.** If failures were independent Poisson events, P(clean) = e^(−λ). They are not:

- A shot whose GCD walk fails classically usually also flips phase.
- `Hmr` erasures fail as a phase kick "half the time".

The `b5796ce` note measured λ ≈ 15.7 on random draws (9.5 classical, 6.2 phase). The naive estimate is one clean draw in 6.8 M. The real figure was P(clean) ≈ e^(−λ_walk) × 0.06 with λ_walk = 7.46, about 1 in 29,000. The practitioner rule (`ecdsafail-nonce-time`) is to measure P(cls=0) and P(pha=0 | cls=0) empirically on the current stream, and never to multiply the channels as if independent.

**The truncation cliff.** Hunt cost grows like e^λ, so each extra bit of truncation multiplies the expected number of nonces to try. Around λ ≈ 8 a hunt is routine: minutes to hours on GPUs. At λ ≈ 15–20 it needs a prefilter and many GPU-hours. Beyond that it becomes infeasible, even though the Toffoli count looks better. Practitioners price levers in **T per λ**. `b5796ce`'s table runs from about 1,100 T/λ (extra multiply rounds) to about 9,000 T/λ (a wider chunk compare). In `pingpong.rs`, a width floor of 8 → 5 "saves 96 Toffoli for +2.7 lambda, ~130x off the exchange rate".

**Hunting.** Running the full simulator costs seconds per nonce, which is too slow at high λ. So hunts are two-stage:

1. **Classical prefilter.** For each candidate nonce, re-derive the 9,024 inputs from SHAKE256 (the fixed prefix of the stream is shared), do the scalar multiplications, and replay the circuit's *classical* failure predicate exactly. For the GCD walk, that means the same widths and convergence test. Survivors are nonces whose island has no predicted walk failure. Implementations include CUDA kernels (`ecdsafail-agent/gpu-nonce`, 23–47k nonce/s per RTX 5090), a Metal kernel on a laptop (`b5796ce`), and an analysis-only Rust filter, `dialog_gcd_classical_filter.rs`. It first appeared in [`ec0fa98`](../commits/ec0fa98.md) (5 June), declared as `pub mod` in `mod.rs` and so compiled. It was later removed and re-added several times. The copy re-added in [`f735fd7`](../commits/f735fd7.md) (16 August) has no module declaration and is not compiled, and [`1196b9f`](../commits/1196b9f.md) (5 September) removed it.
2. **Full verify.** Run survivors through a bit-exact simulator at 9,024 shots. The first one with 0/0/0 is baked into `mod.rs`, and the official `build_circuit` + `eval_circuit` must agree.

The prefilter must be re-aligned whenever the circuit's approximation changes. If it is not, it silently passes nonces that are "clean" under the wrong comparator.

## Why it is (or is not) exact

The tail itself is exact (X·X = I). What the nonce buys is a **selected** validation set. A circuit with λ > 0 is wrong on about λ/9,024 of inputs in general, yet it validates because its island avoids them. The paper flags this as an integrity issue (arXiv v2, §“Limitations, Safety, and Responsible Framing”, “Approximate circuits can pass finite validation”). It re-evaluates a longitudinal sample of 42 accepted submissions on a common corpus of 50,000 pseudorandom inputs and reports Q·T/p̂, where p̂ is the measured success rate (arXiv v2, §“Approximation and nonce hunting” and §“Raw and Retry-Adjusted Q×T Scores Across Submissions”). p̂ stays near 1, so the adjusted point-addition trajectory follows the raw one. v2 adds that a full-Shor proxy (28 additions, union bound) shows some nominal improvements shrinking or reversing. A fully value-exact circuit (λ = 0) passes under any nonce.

**Why every change forces a re-hunt.** The hash covers every op. Even a value-exact reordering draws a new island, and the old nonce's island is gone. If λ > 0, the new island is clean only with probability of about e^(−λ). Nearly every circuit commit therefore also changes the nonce literal (look for `nonce → …` in the commit notes).

**Rerolls that change the score.** The Toffoli average depends on the sampled inputs and measurement outcomes. So a nonce-only change can move the score by a few Toffoli × Q without touching the circuit. That is the census's *Verifier Search → nonce/island reroll* family (17 commits in the extension).

## Knobs and names you will see in commits

- `TAIL_NONCE`, `DIALOG_TAIL_NONCE`, `SUB4_TAIL_NONCE`, `SUB4_PINGPONG_TAIL_NONCE` — the baked nonce.
- *island* — the 9,024-shot draw (inputs plus measurement outcomes) of one stream + nonce.
- *clean nonce* / *winner* — a nonce whose island validates 0/0/0.
- *λ*, *Lambda limit*, *λ budget* — expected failing shots per draw. The current recipe's packages are tuned to a "19.5 Lambda limit".
- *hard input*, *GCD-hard*, *carry escape* — inputs that make an approximate site fail.
- *risk budget* — the strip's λ-style allowance. `deep_strip_keys.rs` headers record e.g. "Risk 1.239700 (budget 1.24)". The unit is not stated in the file.
- *displacement* — mean failures a change adds to a random nonce's island.
- `NS_EARLY_EXIT` — in hunts, stop at the first failing batch. Counts become 0/1 flags, so they are not λ estimates.
- *re-ground / re-hunted* — a fresh nonce was searched for.

## How optimizations use it

- **Truncation priced in λ.** [`b5796ce`](../commits/b5796ce.md) fits a per-round `WIDTH_SCHEDULE` to a λ budget of about 1.5 per draw and spends λ to keep the stream huntable. [`f735fd7`](../commits/f735fd7.md) takes −308 T for about +0.49 λ.
- **Risk-budgeted dead-gate strips.** The budget is stepped up: [`7726431`](../commits/7726431.md) (2.5), [`5265674`](../commits/5265674.md) (3.0). [`ed4b529`](../commits/ed4b529.md) prices candidates by the union of failing shots, not their sum.
- **λ as an externality.** [`64f9aaa`](../commits/64f9aaa.md) cut two divide walk rounds (696 → 694), which through `width_round_index` also narrows the width schedule of both traversals (−2,339 T together). That raised λ for whoever builds next. The next frontier commit, [`1f99759`](../commits/1f99759.md), was built on `522d002` instead and kept 696 rounds.
- **Pure rerolls.** [`cf5aa02`](../commits/cf5aa02.md), [`ffc4e07`](../commits/ffc4e07.md) and [`11f5d9a`](../commits/11f5d9a.md) each gain 5–24 T against their bases by drawing a luckier island.

## Before the tail nonce

From 29 May to 4 June, there was no fixed nonce block. `fiat_shamir_seed` in `src/bin/eval_circuit.rs` absorbs a domain tag, then the op count, then every op's fields, Cliffords included. So the only way to draw a different test set was to change the op stream. It went through four stages.

**1. The island lottery (29 May – 2 June).** In the Kaliski era ([kaliski-almost-inverse.md](kaliski-almost-inverse.md)), each empirical knob was both a truncation and a reroller: loop lengths, bulk-prefix cap, `R_SMALL_THRESHOLD`, W-TRUNC `K0`/margin, carry-tail `W`, shift22 window. Contestants grid-searched knob values together, running the full 9,024-shot evaluator on each candidate, and shipped the cheapest combination that happened to draw clean. Results were non-monotone, because each value is a different draw:
- [`a3ee589`](../commits/a3ee589.md): pair 1 = 398 failed and 399 was clean. For pair 2, 400 and 402 failed and 401 was clean.
- [`d19dbb5`](../commits/d19dbb5.md) calls this a "non-monotonic single-input classical-mismatch cliff".
- [`297f5e5`](../commits/297f5e5.md) swept R_SMALL × W in 2-D. At R = 325 no window below 36 was clean. At R = 319, W = 23 was clean.
- Some knobs were moved only for the draw:
  - [`85ee8e7`](../commits/85ee8e7.md) moved the shift22 window 37 → 33, which saved about 48 T.
  - [`6eba4e3`](../commits/6eba4e3.md) gave back one free `r` doubling.
  - [`36a2989`](../commits/36a2989.md) and [`c8e508f`](../commits/c8e508f.md) re-picked pair 2's loop length.

**2. `KAL_REROLL` and `KAL_SCREEN` ([`6e71096`](../commits/6e71096.md), 2 June).** This was the first accepted identity reroller. `build()` appends `rr` pairs of `X(tx[0]); X(tx[0])` after the point addition. It changes no Toffoli, qubit or unitary. The default `rr = 35` was "CO-TUNED" to carry-tail W = 19. The dev-only `screen.rs`, gated by `KAL_SCREEN`, builds the circuit once and simulates candidate `rr` values in parallel with a replica of `eval_circuit`'s derivation. The op count is hashed first and `rr` changes it, so every candidate still re-hashes the whole stream. Typical values:
- 35 → 43 ([`233a44c`](../commits/233a44c.md));
- 254, from a 0–255 sweep ([`13a7a53`](../commits/13a7a53.md));
- 3 → 5 ([`908521d`](../commits/908521d.md));
- 47 ([`0435f04`](../commits/0435f04.md), [`cef001a`](../commits/cef001a.md)).

**3. Dialog-era pads (2–4 June).** [`cddd5df`](../commits/cddd5df.md) had no reroller and drew clean by luck. The rerollers that followed:
- **`DIALOG_GCD_REROLL`** ([`541bd85`](../commits/541bd85.md)). X;X pairs on `tx[0]` appended after the route, default 2.
- **`DIALOG_REROLL`** ([`8cb350c`](../commits/8cb350c.md), default 8). Pairs on `tx[0]` emitted at the start of the stream, before the first subtraction. That tree dropped `DIALOG_GCD_REROLL`.
- **`DIALOG_POST_SUB_REROLL`** ([`36dcf6b`](../commits/36dcf6b.md), default 10, next to `DIALOG_REROLL` = 9). A second pad of pairs on `tx[1]` right after `Px −= Qx, Py −= Qy`.
  - With two independent counts, the search became a 2-D grid. Memory notes describe a "parallel 2-D `DIALOG_REROLL × DIALOG_POST_SUB_REROLL` search". [`ecbf87b`](../commits/ecbf87b.md) moved (6, 28) → (0, 10).
  - As small grids ran out, the counts grew huge: [`311d6c3`](../commits/311d6c3.md) went from (164, 100) to (647,840, 443,672).
  - These pads sit near the start of a 12.7 M-op stream, so every candidate re-hashed essentially everything.

**4. The fixed-length tail ([`39134ec`](../commits/39134ec.md), 4 June).** `DIALOG_TAIL_NONCE` emits exactly 48 pairs at the very end of `build_builder()`. Each pair targets `tx[1]` when bit i of the nonce is 1 and `tx[0]` otherwise, under phase `dialog_tail_nonce`. The default was 296434. Because the length is fixed, the sponge state after the prefix is the same for every nonce. A search absorbs the prefix once and then only the 96-op tail per candidate. The old pads stayed baked in (4269, 503292) as part of that fixed prefix. `git log -S` on `origin/main` confirms where each name first appears: `KAL_REROLL`/`KAL_SCREEN` in 6e71096, `DIALOG_GCD_REROLL` in 541bd85, `DIALOG_REROLL` in 8cb350c, `DIALOG_POST_SUB_REROLL` in 36dcf6b, `DIALOG_TAIL_NONCE` in 39134ec. The classical prefilter followed a day later ([`ec0fa98`](../commits/ec0fa98.md)). Every later `TAIL_NONCE` is this mechanism.

## Related concepts

- [scoring-and-validation.md](scoring-and-validation.md) — the Fiat–Shamir seed and the 0/0/0 channels
- [comparator-and-width-truncation.md](comparator-and-width-truncation.md), [modular-fold.md](modular-fold.md), [adders-and-carries.md](adders-and-carries.md) — where λ comes from
- [dead-gate-strip.md](dead-gate-strip.md) — risk-budgeted gate deletion
- [pingpong-division.md](pingpong-division.md), [skywalk-gcd.md](skywalk-gcd.md), [trailmix-jump-gcd.md](trailmix-jump-gcd.md) — the GCD walks whose convergence the prefilter models
- [measurement-uncompute.md](measurement-uncompute.md) — why phase failures track classical ones
- [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md)
