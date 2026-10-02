# Adders and carries

> Almost every Toffoli in the circuit sits inside a ripple-carry adder. A reversible adder computes one carry bit per position, and those carry bits must be erased before their wires can be reused. Two levers recur across the commits. One changes how carries are computed and erased: one Toffoli per carry with a measured erase, or two Toffoli per carry and no extra wire. The other changes how many carries exist at all: dead low carries, chunking, and truncated top carries. Every adder trades Toffoli against live carry wires, and the commits keep re-tuning that trade.

## How it works in this circuit

**The basic ripple (`modular.rs::ripple_add`).** At position *i* the carry is `MAJ(a_i, b_i, c_{i-1})`. `carry_step` folds the previous carry into both operands with two CX gates, writes the AND into a fresh wire with one CCX, and XORs the previous carry into that wire, which gives the majority. When the sum is done, `unwind_carry_step` erases each carry with `hmr` (Hadamard-measure-reset) and repairs the phase with a classically conditioned `cz_if` on the two operands. That erase costs no Toffoli (see [measurement-uncompute.md](measurement-uncompute.md)). This is Gidney's "temporary logical-AND" adder. The source calls it "the floor for exact ripple arithmetic" and "the only register-plus-register adder in the tree". The costs, from its doc comment:

```
ripple_add, n-bit                 Toffoli    owned carry wires
with carry_out (vented)           n          n-1
wrapped, mod 2^n (no carry_out)   n-1        n-2   (terminal_step writes the
                                                    last carry into the top sum bit)
textbook Cuccaro (MAJ/UMA)        ~2n        ~1    (carry kept in the operand,
                                                    erased by a second Toffoli)
```

The two adder styles sit at opposite ends of the same trade. The temporary-AND adder needs about half the Toffoli. The Cuccaro adder needs almost no ancilla.

**In-place bridges (`bridge.rs`).** A bridge is one Cuccaro stage placed inside the measured ripple. The carry is stored in the addend wire (`cx(a,b); cx(a,p); ccx(b,p,a)`) and must be undone with a second CCX. The file header states the trade: "each in-place stage trades one extra CCX for one fewer owned carry wire". `ripple_add` uses bridges automatically when the live qubit count plus the carries it needs would exceed the cap (`walk_max_qubits`). The number of bridges allowed in each replay cell comes from `I35_PROFILE`, a list of `round:direction:count` entries, with direction 0 = divide and 1 = multiply.

**Constant adders and dead low carries (`const_arith.rs`).** When the addend is a classical constant `c`, the carry out of position *i* is identically zero below the first position that can generate one. `dead_low_carry_run` counts those positions. The run starts when `c`'s bit 0 is clear, or when the caller passes `first_carry_is_zero` because it has proved the first carry is zero. The run then extends through `c`'s low zero bits. `add_const` therefore emits `n − 2 − ctz(c)` Toffoli, where `ctz` is the number of trailing zeros. Negating the constant preserves `ctz`, so subtraction costs the same. Example: for `c = 0b10100`, positions 0 and 1 can never carry, so the ladder starts at bit 2. The folding constant `f = 2^32 + 977` is odd, so its first carry is `ctrl AND acc[0]` unless the caller can prove otherwise. Two callers can. In `mod_double_pm`, the rotation leaves `target[0]` clear. In `mod_halve_pm`, `parity` is a copy of `target[0]`, which `csub_const_trunc_ctrl_low0` exploits. This elision is exact.

**Chunked adders and carry erase.** A full ladder keeps about *n* carry wires live at once. When those do not fit under the cap, the add is cut into chunks (`pingpong.rs::chunked_add`, `modular::peak_fitted_add`, `width_composition.rs`):

```
acc:   [ chunk 0 ][ chunk 1 ][ chunk 2 ]
       ripple ─► c0 ─► ripple ─► c1 ─► ripple ─► overflow
       once chunk 1 has consumed c0:  hmr(c0); if outcome=1, phase-compare
       top k bits of chunk 0 (sum < addend) to cancel the phase; free c0
```

Each chunk unwinds its own carries before the next chunk starts, so only one chunk's ladder is live at a time. The boundary carry left between chunks is cleaned up by a carry erase. The carry out of `sum = acc + addend` is exactly `sum < addend`, so the carry can be measured out and its phase repaired by re-deriving that comparison (`compare::erase_with_compare`). If the whole chunk is compared and its carry-in is known, the erase is exact. If only the top *k* bits are compared, it is a truncation (see [comparator-and-width-truncation.md](comparator-and-width-truncation.md)). Chunking saves qubits and costs Toffoli. The `head_boundary` comment notes that moving from two chunks to three is "a step worth hundreds of Toffoli".

**Truncated top carries.** The constant-add ladders drop "the carry off the top" of whatever slice they are given (`cadd_const_trunc`: "the slice *is* the window"). This is how modular folds are narrowed (see [modular-fold.md](modular-fold.md)). `SQ_ASM_TAIL` does the same for the square's cross-term add.

## Why it is (or is not) exact

The temporary-AND ripple, Cuccaro bridges, dead-low elision and whole-chunk exact compares compute the same sum on every input. They differ only in scratch use and gate count, so they add no hard inputs. The measured erases are value-exact but phase-sensitive. A wrong or missing `cz_if` leaves a residual phase, and the evaluator's phase channel catches that (see [scoring-and-validation.md](scoring-and-validation.md)). Approximation enters only where a carry is dropped (a truncated slice or carry tail) or erased with a truncated compare. Those approximations are probabilistic, cost λ (the expected number of failing inputs per test island), and need a fresh nonce (see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)). Any change to the gate stream, exact or not, still re-rolls the Fiat–Shamir island.

## Knobs and names you will see in commits

- `ripple_add`, `ripple_add_lent`, `carry_step`/`unwind_carry_step`, `terminal_step`: the measured temporary-AND ripple and its wrapped top.
- `bridge.rs`, `I35_PROFILE`, `I35_BUDGET`, `I50_SPLIT_BRIDGE`: in-place Cuccaro stages and their per-round budget.
- `dead_low_carry_run`, `first_carry_is_zero`, `*_dead_low` (older `cadd/csub_nbit_const_direct_trunc_fast_dead_low`): provably zero low carries.
- `chunked_add`, `chunk_layout`, `peak_fitted_add`, `width_composition::plan`, older `add_chunked_measured`: chunked adders sized against the cap.
- `erase_with_compare`, carry erase, `TLM_COUT_ERASE_CAP` (trailmix era): measured boundary-carry cleanup.
- `PP_WALK_MAX_QUBITS`, older `SUB4_PP_PEAK`/`SQUARE_LADDER`: the cap that every ladder sizes itself against (see [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md)).
- `add_f_window_clean` / `add_f_window_hybrid` / `dirty_carryin`, `TLM_FFG_MAX_G` (trailmix era): constant-fold adders using clean carries, a hybrid, or borrowed dirty wires.

## How optimizations use it

- **Strength Reduction → fast-adder reroute** (10 census commits). The same add is sent to a variant with fewer Toffoli and more carry wires, wherever there is local headroom. Supplemental Note B (“Strength Reduction”, “Fast-adder substitution”) cites `384ed8a` (a Cuccaro adder swapped for a carry-ancilla adder at five `mod_shift_left/right_by_k` call sites, −17.4k T for +21 qubits). [`cc409de`](../commits/cc409de.md) lifts the `TLM_FFG_MAX_G` clamp so all 14 constant folds use the clean carry ladder (−61 T, peak unchanged).
- **Dead-low elision**, filed as fold/carry truncation (9805dee), classical specialization (33e2b34) or, as a side change, ancilla-lifetime (8910bd1): [`8910bd1`](../commits/8910bd1.md), [`33e2b34`](../commits/33e2b34.md) and [`9805dee`](../commits/9805dee.md) remove low constant-add carries that are provably zero. Each is exact and saves tens of Toffoli.
- **In-place mutation** (bridges): [`8bba91b`](../commits/8bba91b.md) moves bridges to the multiply tail (−117 T at the same peak). [`a4b4125`](../commits/a4b4125.md) adds bridges to fit a 1250→1249 cap (+604 T for −1 qubit).
- **Carry-erase scheduling and truncation**: [`8910bd1`](../commits/8910bd1.md) erases each boundary carry as soon as it is consumed (peak −1). [`a254a8a`](../commits/a254a8a.md) caps the chunked-adder carry-erase compares to their top bits.
- **Terminal-carry hosting**: [`51c6c31`](../commits/51c6c31.md) writes final carries straight into output bits, one wire fewer per adder.

## Related concepts

[comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [modular-fold.md](modular-fold.md) · [squaring-and-karatsuba.md](squaring-and-karatsuba.md) · [measurement-uncompute.md](measurement-uncompute.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [scoring-and-validation.md](scoring-and-validation.md)
