# Peak qubits and qubit budgets

> The qubit factor Q in the score is the circuit's **high-water mark**: the most qubits ever live at the same moment. Making a phase cheaper does not lower Q unless that phase is where the maximum happens. Several phases often sit at the same maximum (*co-binders*), and then all of them must come down together. Most modern builders don't hard-code their scratch layout. They size it against a **qubit budget** knob: "you may use up to N live qubits here". This makes Q a dial. A lower cap saves qubits but forces narrower, Toffoli-costlier layouts. A higher cap spends qubits to buy Toffoli. Since score = Q × T, a trade pays exactly when the product drops.

## How it works in this circuit

**What is measured.** `eval_circuit` takes Q = 1 + the largest qubit id referenced in `ops.bin` (`analyze_ops` in `src/circuit.rs`). The contestant's `Builder` (`src/point_add/builder.rs`) hands out ids from a LIFO free list. It mints a fresh id (`next_qubit += 1`) only when that list is empty, which is exactly when every existing id is in use. So the largest id + 1 equals the maximum of `active_qubits` over the build: the high-water mark. The relevant `Builder` methods:

- `alloc_qubit` raises `active_qubits`.
- `free` emits an `R` and returns the id to the pool.
- `release_clean` returns an id with no reset.
- `reacquire` takes a parked id back.
- `note_peak` records each new maximum and the phase in which it happened.

**Which phase binds.** `build_point_add` runs eight `set_phase` blocks:

1. `coord_x_sub`
2. `coord_y_sub`
3. `divide` (y /= x, the modular division)
4. `coord_add3x`
5. `square`
6. `multiply`
7. `coord_y_sub_final`
8. `coord_rsub_final`

The two 256-qubit coordinates are live throughout. The division and multiplication need a GCD-style walk, and the walk's history (a sign tape, or a packed trit history on the Skywalk route) plus coefficient registers sit on top of that floor. So in recent routes the peak lives in `divide`/`multiply` (the walk and its replay) and in the `square`'s carry ladder. A rough picture from the ping-pong era:

```
live qubits
 1278 ┤        ┌──replay ladder──┐          ┌square ladder┐      ← both at the cap
      │   ┌────┘                 └──┐  ┌────┘             └─┐
      │───┘ walk: tape grows        └──┘                    └── coord tails
        divide                         square    multiply
```

**Co-binders.** If the replay and the square both reach 1,278, trimming only one leaves Q at 1,278. Commit notes call these *peak owners*. A one-qubit win means lowering every owner's budget in the same commit: [`087cafa`](../commits/087cafa.md), [`a8ab75a`](../commits/a8ab75a.md), [`0440b62`](../commits/0440b62.md). In [`4eb93cb`](../commits/4eb93cb.md) the governor and `SQUARE_LADDER` drop together, because lowering only one would leave Q at 1,274.

**Budgets.** The adders, comparators and fold windows in each route look at `cap − active_qubits` and pick the widest (cheapest) layout that fits. For example, `target_qubit_headroom()` in the trailmix route returns `TLM_TARGET_Q − active_qubits`, and the ping-pong carry ladders size themselves to land "on exactly this many qubits". The cap is a *target*, and the realized Q can be lower. In [`79e7afa`](../commits/79e7afa.md), raising the governor 1267 → 1268 left Q at 1,266 but let the ladders choose cheaper shapes, for −585 T at no qubit cost.

**The trade, as arithmetic.** Moving from (Q, T) to (Q+ΔQ, T+ΔT) pays exactly when

```
(Q+ΔQ)(T+ΔT) < Q·T    ⇔    ΔT < −ΔQ · T / (Q+ΔQ)
```

So one qubit is worth about T/Q Toffoli: roughly 1,130 T at Q ≈ 1,151 and T ≈ 1.30 M (late July), and about 805 T at today's frontier (944,682 / 1,174). Worked cases from the commit notes:

| commit | ΔQ | ΔT | break-even ΔT | Δscore |
|---|---|---|---|---|
| [`f5ff95b`](../commits/f5ff95b.md) cap 1150→1158 | +7 | −9,147 | −7,869 | −1,479,640 |
| [`d9ef3e9`](../commits/d9ef3e9.md) cap 1150→1154 | +3 | −5,166 | −3,378 | −2,063,205 |
| [`87a1c68`](../commits/87a1c68.md) 1250-q tree vs frontier `73894fc` (1249) | +1 | −715 | −712 | −4,146 |
| [`087cafa`](../commits/087cafa.md) owners 1278→1275 | −3 | +1,491 | +2,159 | −851,418 |
| [`8ee337c`](../commits/8ee337c.md) Skywalk GCD vs frontier `718a807` | −76 | +57,371 | +57,542 | −201,250 |

For example, `f5ff95b` gives back 1,151 × 9,147 Toffoli-units and spends 7 × 1,301,798 qubit-units. The net is (1,158 × 1,292,651) − (1,151 × 1,301,798) = −1,479,640. `87a1c68` clears break-even by only 3 Toffoli and `8ee337c` by about 170 (both against the frontier at the time, not the note's base): when a trade is this close, the island noise of a reroll (±5–15 T) matters. The `f5ff95b` note describes a U-shaped (Q, T) curve under these caps. Too tight a cap forces repair-heavy layouts, too loose wastes qubits, and the best cap moves whenever the schedule underneath changes. That shift is what `d9ef3e9` shows.

## Why it is (or is not) exact

Changing a budget changes *layout*, not *function*. Most budget-driven layouts are exact: chunked adders with exact boundary repair, wires lent and later restored. Two caveats apply:

- Some narrower layouts add truncated boundary compares, which raise λ.
- Any layout change rewrites the op stream, so the nonce must be re-hunted ([nonce-island-and-lambda.md](nonce-island-and-lambda.md)).

The reverse effect also occurs. The `b5796ce` note found that "several 'free' λ purchases silently cost a qubit": widening a compare pushed a ladder over the cap, and Q became 1,279. Validation checks the budgets only indirectly. If a "freed" wire was not really |0⟩, its `R` shows up as phase garbage, and a never-cleaned one as ancilla garbage. The peak itself is just reported.

## Knobs and names you will see in commits

- **high-water / peak / Q** — max live qubits; `eval_circuit`'s `qubits`.
- **binder, peak owner, co-binder** — the phase or phases that reach Q.
- `TLM_TARGET_Q`, `TLM_SQUARE_PEAK_CAP` — trailmix-era headroom caps for the vent/scratch pool and the square (`TLM_TARGET_Q` from [`fed64cf`](../commits/fed64cf.md), 20 June; `TLM_SQUARE_PEAK_CAP` from [`d44cad3`](../commits/d44cad3.md), 26 June; see [trailmix-schedules-and-reserves.md](trailmix-schedules-and-reserves.md)).
- `SUB4_PP_PEAK` (the *peak governor*), `SUB4_PP_QSTAR`, plan checkpoints `r1`/`r2` — ping-pong-era replay budget (August).
- `SQUARE_LADDER` — live carry-ladder budget of the product-register square, the usual co-binder.
- `PP_WALK_MAX_QUBITS` — current route: "the circuit's peak, and the only width knob there is" (`pingpong.rs`). The current recipe pins it through `HEO_PIN_PP_WALK_MAX_QUBITS = 1174`, which equals the frontier's Q. A plain `env_raw` entry still lists 1251; it appears to be overridden by the pin.
- `SQUARE_ROW_MAX_SEG`, `DIALOG_GCD_APPLY_CHUNKED_F_BLOCKS` — older dialog-era peak dials (agent skill docs).
- `TRACE_PEAK`, `HEO_PHASE … peak=` — instrumentation that names the binder. Skill notes warn `TRACE_PEAK` went stale on later routes.

## How optimizations use it

- **Budget retunes** spend or recover qubits for Toffoli. These are filed as *ancilla-lifetime / venting*: [`f5ff95b`](../commits/f5ff95b.md), [`d9ef3e9`](../commits/d9ef3e9.md), [`9700396`](../commits/9700396.md) (cap 1259 → 1258 for +674 T).
- **Co-binder cuts** lower every owner's ladder at once: [`087cafa`](../commits/087cafa.md), [`a8ab75a`](../commits/a8ab75a.md).
- **Lifetime moves** take a wire out of the binding window, so the cap can drop with no extra Toffoli. [`152fbe0`](../commits/152fbe0.md) lends all 16 known-value terminal wires across the replay (1317 → 1301). [`265a9e9`](../commits/265a9e9.md) frees a tape sign and recomputes it (1251 → 1250).
- **Rescheduling** changes which big registers are live together: [`cb56b71`](../commits/cb56b71.md) interleaves walk and replay (1316 → 1281 vs its base `8910bd1`, for +10,733 T).
- **Algorithm swaps** shift the whole curve: [`8ee337c`](../commits/8ee337c.md).

## Related concepts

- [venting-and-wire-loans.md](venting-and-wire-loans.md) — the main peak-cutting mechanisms
- [adders-and-carries.md](adders-and-carries.md), [squaring-and-karatsuba.md](squaring-and-karatsuba.md) — the ladders the budgets size
- [pingpong-division.md](pingpong-division.md), [skywalk-gcd.md](skywalk-gcd.md), [trailmix-jump-gcd.md](trailmix-jump-gcd.md) — where the binding tape lives
- [scoring-and-validation.md](scoring-and-validation.md), [nonce-island-and-lambda.md](nonce-island-and-lambda.md)
- [measurement-uncompute.md](measurement-uncompute.md), [comparator-and-width-truncation.md](comparator-and-width-truncation.md)
