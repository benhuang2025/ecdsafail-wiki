# Measurement-based uncomputation

> Every scratch qubit must end at |0⟩ with no leftover phase. The textbook way to clean a wire that holds a computed bit is to run the computation backwards, which costs as many Toffolis as computing it. Measurement-based uncomputation does it another way. You measure the wire in the X basis, which resets it to |0⟩ but leaves a known phase that depends on a random outcome bit `m`. Then you cancel that phase with gates conditioned on `m`. When the wire held an AND of two live bits, the fix-up is one classically controlled CZ, so the Toffoli cost of the uncompute drops to zero. This is the main tool of the *Uncompute Strategy* family in the census. Most of its variants differ only in how cheap the phase fix-up can be made.

## How it works in this circuit

**The `HMR` op.** In the competition's gate set (`src/circuit.rs`), `Hmr` is documented as "X-basis measurement combined with demolition into the 0 state". The paper's main text calls HMR "a demolition measurement in the X basis" (arXiv v2, §“Circuit Model and Cost Metric”), and Supplemental Note B (“Uncompute Strategy”, “Measurement-based uncompute”) calls it Hadamard-measure-reset. Both are the same thing. The trusted simulator (`src/sim.rs`) models it this way:

```
m      <- random bit from the Fiat–Shamir XOF stream
bit[c] <- m                           # outcome stored in a classical bit
phase  ^= q & m                       # the "kickback": (-1)^(m·q)
q      <- 0                           # wire is reset
```

`R` (reset) does the same thing but discards `m`. A reset of a wire that is not |0⟩ therefore leaves a random phase that nothing can cancel. `Builder::free(q)` emits an `R`, so freeing a dirty wire is never safe. `release_clean(q)` returns a wire to the pool without emitting any op. `Hmr`, `CZ` and `R` count as Clifford gates. Only `CCX`/`CCZ` count toward the score, and only on shots where their classical condition is true.

**The basic idiom** (Gidney's AND-uncompute) appears as `measured_and_clear` in `fd_coordinate.rs`, as `clear_and` in the older trailmix code, and inline in many adders:

```
w = x·y                    # built earlier by CCX(x, y -> w) from |0>
HMR(w -> m)                # w is |0> again; the state picked up (-1)^(m·x·y)
CZ(x, y) if m              # cz_if(x, y, m): applies (-1)^(m·x·y), cancelling it
```

This costs 0 Toffoli, where `CCX(x, y -> w)` would cost 1. One condition must hold: when the measurement happens, `w` must still equal the exact function that the fix-up assumes.

**What the fix-up costs.** The fix-up has to apply `(-1)^(m·f)`, where `f` is the function the wire held. The variants differ in how cheaply this can be done:

- *f is quadratic in live wires* (an AND, or a carry written in terms of sum bits). Then the fix-up is CZ/Z gates only, at 0 Toffoli. Examples:
  - The **from-zero adders** of [`5b834ba`](../commits/5b834ba.md). If a Cuccaro adder operand bit is provably |0⟩ on entry, the MAJ step leaves exactly `AND(x,y)` in it. `uma_from_zero` / `inv_maj_from_zero` then replace the UMA Toffoli with `hmr` + `cz_if` (`TLM_SQUARE_FROM_ZERO`, `TLM_KG_INC_VENT`).
  - **Known-output receivers** (`affine_constant::add_known`, `known_stream`, `stream_wide`, `round2_receiver`). These are used when the adder's final result is already known as an affine function of live wires, for example in a reverse pass that restores a value. Each carry is then rebuilt with CNOTs as `c_i = a_i ⊕ b_i ⊕ s_i`, without any Toffoli. Once the sum is finished, each carry is X-measured. Written in terms of the sum bit and the incoming carry, each carry is quadratic, so the repair is again CZ/Z. The comment in `add_known` gives the formulas: `a_i=0: c_i = p ⊕ p·s; a_i=1: c_i = 1 ⊕ s ⊕ p·s`. The result is an adder with zero Toffoli, valid only on the subspace where the output really is known.
- *f is a comparison* (for example the carry out of an adder chunk). The fix-up becomes a **phase oracle**: compute the comparison, apply a Z, uncompute, all inside `push_condition(m)`. `cmp_lt_phase_conditioned` in `compare.rs` and `erase_boundary_carry` in [`8910bd1`](../commits/8910bd1.md) work this way. Because the oracle runs only on shots where `m=1`, its executed Toffoli cost is about half its static cost. Usually the comparison is truncated to the top `k` bits (`ERASE_COMPARE`, `replay_chunk_compare()`), which makes it approximate.
- *Phase-only comparator tops.* The last stage of the oracle never needs its value, only its phase. A borrow is `maj(q,a,x) = q·a ⊕ q·x ⊕ a·x`, so its phase can be applied with three CZs instead of a Toffoli ([`51c6c31`](../commits/51c6c31.md)).

### Deferred coherent uncompute (the opposite choice)

[`b788efc`](../commits/b788efc.md) went the other way and coined the change-type **deferred coherent uncompute**. In the square's cross-assembly, each chunk carry-out used to be measured in the forward add (`hmr`, outcome kept) and erased in the inverse with an exact full-chunk compare (`mapped_compare`), run on about half of shots. Under `SQ_HOLD_BOUNDARY`, `direct_add_hold` instead keeps the carries live in `K2Retained.held`. Later the mirror-image inverse assembly runs high-to-low (`direct_add_unhold`) and recomputes the same carries into the held wires, which clears them with no extra gates. Compared with measuring:

| | measured erase | deferred coherent |
|---|---|---|
| wire lifetime | ends right away | lasts until the inverse pass, so peak qubits rise |
| Toffoli | conditioned compare on about half of shots | none beyond the inverse pass, which runs anyway |
| exactness | approximate if the compare is truncated (in b788efc's base it was exact) | exact |

The extra live wires had to be paid for with loans of provably-zero wires (`SQ_OWN_TOP_ZEROS`, `SQ_HIGH_CARRY_LOAN`); see [venting-and-wire-loans.md](venting-and-wire-loans.md).

## Why it is (or is not) exact

The idiom is exact whenever the measured wire holds exactly `f` and the fix-up applies exactly `(-1)^(m·f)`. Then the circuit computes the same function, with no residual phase, on every input. Two things break it. First, if a control changes after the AND was built, the wire no longer equals `x·y` of the current values and the CZ applies the wrong phase. Second, the fix-up may be approximate: a comparator truncated to `k` bits gets the carry wrong on roughly a 2^-k fraction of inputs. Wider settings such as `ERASE_COMPARE` 25→28 in [`454ff5a`](../commits/454ff5a.md) are bought as "protection" against this. That regime is island-exact, not value-exact (see [comparator-and-width-truncation.md](comparator-and-width-truncation.md)).

The evaluator (`src/bin/eval_circuit.rs`) runs 9,024 Fiat–Shamir shots and checks three channels: classical output, accumulated phase, and leftover ancilla values. A wrong fix-up flips the phase only on shots where both `m=1` and `f=1`. If the error is systematic, it shows up as `PHASE GARBAGE` with near certainty. If it is rare (a truncation), it adds hard inputs to the phase channel and raises λ (see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)). `hmr` always resets its wire, so it cannot leave ancilla garbage. Supplemental Note B (“Uncompute Strategy”, “Measurement-based uncompute”) also notes that `hmr` cannot be replayed by `emit_inverse`, so any backward pass that contains it has to be written by hand.

## Knobs and names you will see in commits

- `hmr(q, m)`, `cz_if(a, b, m)`, `z_if(q, m)` — measure into bit `m`; conditional CZ, which degenerates to Z when `a == b`.
- `free` / `release_clean` — reset-and-free a wire / free it with no op (the caller has restored |0⟩).
- `cuccaro_add_from_zero`, `uma_from_zero`, `TLM_SQUARE_FROM_ZERO`, `TLM_KG_INC_VENT` — from-zero adders (trailmix era).
- `cmp_lt_phase_conditioned`, `erase_boundary_carry`, `ERASE_COMPARE` — measured carry erase with a phase-oracle compare. `ERASE_COMPARE` is the compare width used by `mod_addsub`.
- `add_known`, `known_stream`, `stream_wide`, `round2_receiver`, `SQ_ROW1_STREAM` — known-output receivers.
- `terminal_top_copy`, `top_result_loan` (`I74_RESULT_TOP_LOAN`) — measuring a known top-bit copy instead of running the last CCX.
- "vent" (trailmix `*_vented` adders) — an extra ancilla that holds a carry so that the carry can be measured away.
- `SQ_HOLD_BOUNDARY`, `direct_add_hold` / `_unhold` — deferred coherent uncompute.

## How optimizations use it

The census change-type **measurement uncompute** (Uncompute Strategy family) covers commits whose main saving is turning Toffoli uncomputes into `hmr` + Clifford repairs. Many other commits use the idiom without it being their main lever.

- [`5b834ba`](../commits/5b834ba.md) — from-zero square-correction adders and the KG increment, about −1,720 T gross. The commit nets only −938 T, because it also drops the D2 strip.
- [`5a08ebd`](../commits/5a08ebd.md) — known-output receivers in the reverse rounds and square row 1.
- [`454ff5a`](../commits/454ff5a.md) — square B-merge inverse adds moved to `stream_wide::add`.
- [`8910bd1`](../commits/8910bd1.md) — measured boundary-carry erase rescheduled to lower peak. Its −1 qubit also needs the commit's exact dead-low change to `mod_halve_pm`, because the peak had two owners at 1317.
- [`b788efc`](../commits/b788efc.md) — the deferred coherent alternative.

## Related concepts

[venting-and-wire-loans.md](venting-and-wire-loans.md) (hmr as an early-erase tool), [adders-and-carries.md](adders-and-carries.md), [comparator-and-width-truncation.md](comparator-and-width-truncation.md), [scoring-and-validation.md](scoring-and-validation.md), [nonce-island-and-lambda.md](nonce-island-and-lambda.md), [dead-gate-strip.md](dead-gate-strip.md), [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md).
