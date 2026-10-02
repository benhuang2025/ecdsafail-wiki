# Venting, wire loans and recompute-later

> Peak qubits is decided by a single moment: the instant when the most wires are live at once. To lower it you do not have to remove gates. It is enough that fewer wires are *held* at that instant. This page covers the tricks contestants use for that. You can free a wire early (vent it) once its value is no longer needed or can be rebuilt. You can lend a wire whose value is known (a constant, a copy of another bit, or a provable zero) to the peak-binding code as scratch, and restore it afterwards. You can park a temporary inside a wire that is already live. You can also erase a bit now and recompute it later. Each of these trades a few cheap gates, and sometimes some Toffolis, for one fewer qubit at the peak.

## How it works in this circuit

**Why freeing helps.** The evaluator sets `Q` to one plus the largest qubit index referenced anywhere in the op stream (`analyze_ops` in `src/circuit.rs`). The builder (`src/point_add/builder.rs`) reuses freed indices: `alloc_qubit()` pops the free list before it creates a new index, and `note_peak()` tracks the running maximum of `active_qubits`. A wire freed before the widest region therefore gets handed out again inside that region, and the high-water mark drops by one. Builder primitives:

- `free(q)` emits an `R` (reset) and returns `q` to the pool. Safe only if `q` is already |0⟩, because resetting a 1 leaves a random phase (see [measurement-uncompute.md](measurement-uncompute.md)).
- `release_clean(q)` returns `q` to the pool without emitting anything. The caller has already restored |0⟩ with ordinary gates.
- `reacquire(q)` takes that specific index back out of the pool and may raise the peak.

**A loan, as written in `pingpong.rs`** (`with_sign_copy_loans`, added in [`cc7f10e`](../commits/cc7f10e.md), which lends a live walk register's top sign copy during a replay; the terminal loan `loan_terminal` / `restore_terminal`, which frees with `free` instead of `release_clean`, is the generalised form of [`adec6f4`](../commits/adec6f4.md)):

```
cx(sign, q)        # q was a copy of `sign`, so it is now |0>
release_clean(q)   # q goes back to the pool; active_qubits -= 1
  body(...)        # the peak-binding code allocates q as a carry, uses it,
                   # returns it to |0> and frees it again
reacquire(q)
cx(sign, q)        # q is a copy of `sign` again, as before
```

The loan costs two CNOTs and no Toffoli. The loaned wire can be any of these:

- **A duplicated bit.** After the fixed ping-pong walk, `u, v ∈ {±1}`, so bits 1..7 of each 9-wire register are copies of the sign. [`152fbe0`](../commits/152fbe0.md) lends all 16 known terminal wires (these sign copies plus each register's constant bit 0; the base already lent one) across the coefficient replay and, with two smaller changes, goes from 1317 to 1301 qubits.
- **A constant.** The walk operands are odd, so `u[0] = v[0] = 1`. That bit can be cleared with an X and lent (`loan_interleaved_odd_passengers`, [`522d002`](../commits/522d002.md); `LOW0` in [`c1adf3e`](../commits/c1adf3e.md)).
- **A provable zero.** Examples are the square's always-zero top cross bits and retained zero bits (`SQ_OWN_TOP_ZEROS`, `SQ_LEND_RETAINED_ZEROS`, `SQ_LEND_ASSEMBLY_ZEROS`).
- **A reconstructible value.** `SQ_LEND_RETAINED_ANDS` / `SQ_LEND_RETAINED_CROSS2` are branch bitmasks: 1=A, 2=B, 4=C. They erase a retained AND or cross value with `hmr`+CZ, lend the wire, and rebuild the value with a CCX afterwards. This one costs Toffoli, so it is worth it only when that wire really binds the peak. [`c8da745`](../commits/c8da745.md) and [`ea73b1a`](../commits/ea73b1a.md) set the B-branch loans to 0 for −4 T.

**Parking.** Instead of allocating a temporary, the code can host it in a wire that is already live and whose value can be restored. [`51c6c31`](../commits/51c6c31.md) computes an adder's final carry straight into the top output bit, holds the fold operand in `selectors[0]`, holds `plus_f` in the `parity` wire, and keeps the Karatsuba sum in the input's high half. That gives −6 qubits for +2,372 T. In-place Cuccaro "bridges" (`bridge.rs`, `I35_PROFILE`) do the same thing inside an adder: each bridge stage keeps its carry in the operand, which costs one extra CCX and saves one carry wire. The census calls this *in-place mutation* ([`8bba91b`](../commits/8bba91b.md), [`a4b4125`](../commits/a4b4125.md)).

**Recompute-later.** A bit that is needed now and again much later, but not across the peak, can be erased in the X basis and rebuilt when it is needed again:

```
free_sign_bit:  hmr(tape[k] -> m); free(tape[k])    # erase now, remember m
   ... peak-binding replay rounds ...
recompute:      rebuild tape[k] from live state      # CX/X if the relation is linear
                z_if(tape[k], m)                     # cancel the phase the hmr left
```

[`5526766`](../commits/5526766.md) does this for the first two tape bits, `tape[0]` and `tape[1]`, with three levers (`A0_FREE`, `SIGN1_FREE`, `BCHAIN_MUL`). Some of the rebuilds need a truncated carry chain, so it costs −2 Q for +112 T (vs its base `db7623e`). [`265a9e9`](../commits/265a9e9.md) (`PP_N_HOLE2`) frees the round-2 sign bit and rebuilds it with CX/X alone from a linear invariant of the walk, at 0 Toffoli.

**Rescheduling.** Lifetimes can also be shortened without any new identity. [`8910bd1`](../commits/8910bd1.md) erases each chunk-boundary carry as soon as the next chunk has used it, and allocates the carry-out only in the last chunk. That lowers only one of the two peak owners at 1317; the −1 qubit also needs the commit's exact dead-low change to the round-0 `mod_halve_pm` endpoint chain. [`cb56b71`](../commits/cb56b71.md) interleaves the walk with the replay, so early replay rounds run beside only part of the tape. The full tape and both coefficient registers still coexist in the late rounds, where the peak sits; those rounds fit by shrinking their own scratch.

**The second meaning of "vent".** In the trailmix-era adders (`*_vented`, `hybrid_add_plain`), a *vent* is an extra ancilla that holds a carry so it can be measured away instead of uncomputed with a CCX. More vents mean fewer Toffoli and more qubits. The caps `TLM_TARGET_Q` / `TLM_SQUARE_PEAK_CAP` set how many vents may be live. Commits that only move the cap ([`f5ff95b`](../commits/f5ff95b.md), [`d9ef3e9`](../commits/d9ef3e9.md) raise it, [`31f9c58`](../commits/31f9c58.md) lowers it) are also filed under *ancilla-lifetime / venting*, even though they trade in the opposite direction.

## Why it is (or is not) exact

A loan is exact when four things hold: the claimed value really holds on every input when the loan starts; its source (for example `sign`) is not changed inside the body; the body hands the wire back at |0⟩; and the repayment uses the same relation as the clearing. Supplemental Note B (“Register and Scratch Allocation”, “Ancilla-lifetime windowing”) states the same condition for ancilla-lifetime windowing. When these hold, no gate's function changes, only which index each allocation receives.

If the invariant fails on some input, the validator sees it in one of two ways. With `free`, the `R` scrambles the phase of that shot, which shows up as phase garbage. With `release_clean`, the body is handed a dirty "zero", which shows up as a classical mismatch or leftover ancilla garbage. Either is caught on any of the 9,024 Fiat–Shamir shots where it happens (see [scoring-and-validation.md](scoring-and-validation.md)). Recompute-later is exact only if the rebuilt bit equals the erased one and the `z_if` uses the same measurement bit. If the rebuild uses a truncated chain, as `recompute_a0` does, it can be wrong on rare inputs, which raises λ (see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)). One thing is not verified here: whether every invariant used (for example "the walk ends at ±1") holds for all inputs or only for inputs whose walk converges. The commit notes state them as facts.

A lifetime cut lowers `Q` only if it covers *every* phase that ties for the peak, because the peak is often a floor shared by several phases (see [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md)). In the late game one qubit is worth about one average-Toffoli count of score: about 0.89M of the 1.6M gain in [`265a9e9`](../commits/265a9e9.md) came from the single qubit.

## Knobs and names you will see in commits

- `free` / `release_clean` / `reacquire` — pool primitives; `set_avoid` keeps parked wires out of fresh allocations.
- `PP_REPLAY_SIGN_LOAN(_MUL)`, `PP_SOURCE_SIGN_LOAN` / `_GROW` — sign-copy loans across the replay.
- `loan_interleaved_odd_passengers`, `LOW0` — lend the odd constant bit 0.
- `SQ_LEND_RETAINED_ZEROS`, `SQ_LEND_ASSEMBLY_ZEROS`, `SQ_OWN_TOP_ZEROS`, `SQ_HIGH_CARRY_LOAN` — square-side zero and carry loans.
- `SQ_LEND_RETAINED_ANDS` / `_CROSS2` — erase-lend-rebuild loans (branch bitmasks).
- `top_result_loan` (`I74_RESULT_TOP_LOAN`, `I76_SOURCE_TOP_LOAN`) — measure a known top-bit copy early and borrow its wire.
- `free_sign_bit`, `SUB4_PP_SIGN1_FREE` / `A0_FREE` / `BCHAIN_MUL`, `PP_N_HOLE2` — recompute-later.
- `bridge.rs`, `I35_PROFILE` — in-place carry stages.
- `TLM_TARGET_Q`, `TLM_SQUARE_PEAK_CAP`, `PP_WALK_MAX_QUBITS` — caps that the allocators plan against.

## How optimizations use it

In the census these moves fall under **Register and Scratch Allocation**. *Ancilla-lifetime / venting* (22 commits in the extension) covers early frees, recompute-later, rescheduling and vent-cap retunes. *Scratch/ancilla reuse* (9) covers loans and parking. *In-place mutation* (2) covers bridges. Examples:

- [`adec6f4`](../commits/adec6f4.md) — frees one duplicated sign bit (1318→1317).
- [`152fbe0`](../commits/152fbe0.md) — lends all 16 constant and sign-copy wires (1317→1301).
- [`51c6c31`](../commits/51c6c31.md) — parking in output, selector and parity wires (Q−6).
- [`5526766`](../commits/5526766.md) — hmr-erase tape signs and recompute them at walk-back (Q−2).
- [`265a9e9`](../commits/265a9e9.md) — Clifford-only recompute via a walk invariant (Q−1).
- [`cc7f10e`](../commits/cc7f10e.md) — 62-knob composite of loans across the square, replay and walk (cap 1259→1251).

## Related concepts

[measurement-uncompute.md](measurement-uncompute.md) (the erase tool; deferred uncompute paid for by loans), [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) (co-binders and caps), [pingpong-division.md](pingpong-division.md) (walk, tape and replay), [squaring-and-karatsuba.md](squaring-and-karatsuba.md), [adders-and-carries.md](adders-and-carries.md), [scoring-and-validation.md](scoring-and-validation.md), [nonce-island-and-lambda.md](nonce-island-and-lambda.md).
