# Comparator and width truncation

> Many operations in the circuit are done at more bits than a typical input needs. Two cases recur. A comparison that only has to recover one carry bit can usually be decided from the top few bits. A register in the GCD walk holds a value that shrinks round by round, so it can be made narrower as it goes. Truncation means doing the work on fewer bits. Each bit removed saves roughly one Toffoli per call site, every round, and sometimes a qubit. The cost is correctness on rare inputs: on a few inputs the narrowed operation gives the wrong answer. This is the most common change-type in the census: 149 of the original 404 commits and 33 of the 157 audited since, so 182 of 561.

## How it works in this circuit

### Truncated comparators

Many comparators in this circuit exist only to clean up. An adder leaves a carry or an overflow flag on a wire. Uncomputing that bit coherently would cost a full comparison, so the circuit measures it out instead and repairs the phase this leaves. `compare.rs::erase_with_compare(target, a, b, borrow_in)` does three things:

1. `hmr(target)` measures the wire in the X basis.
2. Only if the outcome is 1 (`push_condition`), it runs `cmp_lt_phase(a, b)`, which applies the phase `(-1)^[a < b]` and then unwinds its own carries for free.
3. Because the carry out of `sum = acc + addend` is exactly `[sum < addend]`, that phase cancels the one left by the measurement.

The slices `a` and `b` passed in are the window. The source puts it this way: "Comparing only the top `k` bits of each operand is the sole approximation: the predicate is wrong exactly when both agree across all `k`, i.e. with probability ~2^-k. Widening by one bit costs one Toffoli and halves that error." There is also a scoring detail. The comparator runs under a classical condition, so its Toffoli execute on only about half the shots. A comparator bit therefore costs about 0.5 *executed* Toffoli (see the comment above `ERASE_COMPARE` in `modular.rs`).

```
chunk boundary at bit 86, carry c0 to erase, window k = 4
  sum[82..86]    = 1 0 1 1
  addend[82..86] = 1 1 0 0   → sum < addend → c0 was 1 → phase cancels correctly
  if the 4 top bits tie, the truncated compare says "not less";
  that is wrong whenever the lower bits would have said "less"
```

Where the circuit uses this pattern:
- **Chunk-boundary carries** in the replay's chunked adder (`pingpong::chunked_add`): width `chunk_compare(round)`.
- **The replay cell's overflow flag** (`replay_add_halve`, `replay_double_add`): width `flag_compare(round)`.
- **The coordinate shell's modular add/sub carry** (`modular::mod_addsub`): width `ERASE_COMPARE`.
- **The mid-carry of `peak_fitted_add`**: optionally truncated to `PP_F_PEAKCMP` bits instead of being compared over the whole chunk.

A "seeded" compare passes one bit just below the window (`addend[phi-k-1]`) as a guessed borrow-in, which the code calls a *predictor*. This handles ties better at no Toffoli cost.

### Width schedules

The ping-pong divider (see [pingpong-division.md](pingpong-division.md)) runs a GCD-style walk on registers `u` and `v`. The values they hold shrink, so `pingpong::width_schedule()` narrows the registers round by round and "hands the freed wires back to the allocator". The schedule is the pinned string `PP_WIDTH_SCHEDULE = "259,258x19,257x5,…,8x9,8x2"`, a run-length list of per-round widths. It must be non-increasing (`shrink_to` cannot grow a register back) and may not go below 5. A narrower round makes every walk add, compare and conditional swap that touches `u` or `v` narrower in that round. The schedule is not a proof. It was fitted from sampled walks: in the `b5796ce` version, each round got the smallest width whose width-violation count stayed within a λ budget of about 1.5 per 9,024-shot draw. The code still records the exchange rate: going from 8 to 5 "saves 96 Toffoli for +2.7 lambda, ~130x off the exchange rate every other width knob trades at".

The schedule started as piecewise-linear `BREAK`/`SLOPE` constants in `value_width()`, became a baked 700-entry `WIDTH_SCHEDULE` table plus `WIDTH_REPAIR`, and is now the env string. In the earlier trailmix route, `SCHED_J2` (register width per divstep) and `GAP_J2` (comparator window per divstep) played the same role. *Guard bits* buy back safety on selected rounds: `PP_WALK_GUARD_BITS` / `PP_WALK_GUARD_MAX_WIDTH`, `PP_WALK_EXTRA_ROUNDS` (`start:len:delta`). `I45_NARROW_ROUNDS` does the opposite and removes one bit on chosen rounds.

### Per-round shapes

Failure rates are not flat across rounds, so the widths are shaped per round. The doc comment on `chunk_compare` records a measurement: a narrowed boundary compare fails at a relative rate of 1.00 when the walk width is 69–38, 0.33 at 37–25, and 0.04 at 25–8. "So the late boundaries are two to four bits over-provisioned." Minimising total bits at a fixed total error means equalising the per-site error. So each width is a pinned base plus a band offset keyed on the walk's current width: `PP_CHUNK_SHAPE = "64:0,38:1,25:-3,0:-4"` (718a807; the Skywalk route re-pins the same string as `HEO_PIN_PP_CHUNK_SHAPE`) and `PP_FLAG_SHAPE = "38:0,25:-1,0:-3"`. Round-range slices (`GO_CHUNK`, `GO_FLAG`) and, in the Skywalk route, per-cell deltas (`GO_CELLB`, `GO_CELLF`) are added on top.

## Why it is (or is not) exact

There are two kinds of truncation, and the census puts both under this change-type:

- **Exact truncation** drops bits that a proven invariant says are zero, i.e. narrows to a "proven-nonzero prefix" (Supplemental Note B, “Dead-Code and Redundancy Elimination”, “Comparator and register-width truncation”). Note B names the `COMPARE_BITS`, `WIDTH_MARGIN` and `KAL_*_TRUNC_W` levers as the source-record examples. That fits `KAL_*_TRUNC_W` poorly: those are carry-tail windows (e.g. `KAL_DOUBLE_CARRY_TRUNC_W`, added in the 2 June competition submission f8a36ba) whose own doc comment gives a dropped-carry probability of about 2^-(w+1) per call, so they are probabilistic.
- **Probabilistic truncation**, which covers almost all recent commits, is wrong on rare *hard inputs*. A comparator is wrong on a top-k tie (about 2^-k per call). A walk register overflows its scheduled width on an unusually slow input.

Validation runs 9,024 test inputs derived by Fiat–Shamir from the op stream and a nonce. Every truncation raises λ, the expected number of hard inputs among those 9,024. A submission is accepted only with a nonce whose island has zero failures, and the chance that a random nonce gives one is about e^-λ. Any change to the op stream re-rolls the island, so the nonce must be hunted again (see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)). Later routes work against explicit λ limits: 18 under the "PR 419 contract" of [`cc7f10e`](../commits/cc7f10e.md) (carried by later commits such as [`291d749`](../commits/291d749.md)) and 19.5 in the Skywalk packages. Commit notes call a narrowing a **sell** (saves Toffoli, spends λ) and a widening a **buy** (costs Toffoli, returns λ). Many commits are sell/buy packages.

## Knobs and names you will see in commits

- `PP_REPLAY_CHUNK_COMPARE` (older `SUB4_PP_REPLAY_CHUNK_COMPARE`, "chunk compare"), `PP_CHUNK_SHAPE`, `GO_CHUNK`, `PP_N_BADJ`: width of the chunk-boundary carry erase.
- `PP_REPLAY_FLAG_COMPARE`, `PP_FLAG_SHAPE`, `GO_FLAG`, `PP_FLAG_WIDEN_DIV`: width of the replay overflow-flag erase. `PP_FLAG_WIDEN_DIV` adds one bit on divide rounds whose walk width is at or above its value, so setting it to 696 turns the widening off.
- `ERASE_COMPARE` / `HEO_PIN_ERASE_COMPARE`: width of the coordinate-shell carry erase.
- `PP_F_PEAKCMP` ("PEAKCMP"): truncated mid-carry compare in `peak_fitted_add`.
- `GO_CELLB` / `GO_CELLF`, `HEO_FIT_K`, `HEO_SPLIT_K`: per-cell boundary (B) and flag (F) compare deltas, and fit/split windows, in the Skywalk route (see [skywalk-gcd.md](skywalk-gcd.md)).
- `PP_WIDTH_SCHEDULE`, `WIDTH_SCHEDULE`, `SLOPE_2`, `BREAK_1`, `WIDTH_REPAIR`, `PP_WALK_GUARD_BITS`, `PP_WALK_EXTRA_ROUNDS`, `I45_NARROW_ROUNDS`: walk register widths and guard bits.
- `SCHED_J2` / `GAP_J2`, `TLM_COORD_MSBS`, `TLM_COUT_ERASE_CAP` (trailmix era); `DIALOG_GCD_COMPARE_BITS`, `SQUARE_ROW_WINDOW_CLEAN_COMPARE_BITS` (dialog era): the same ideas in older routes (see [trailmix-jump-gcd.md](trailmix-jump-gcd.md)).

## How optimizations use it

The change-type is **Dead-Code and Redundancy Elimination → comparator/width truncation**. Typical moves:
- **Shave one compare by a bit or two**: [`6ee4d14`](../commits/6ee4d14.md) (chunk 24→23, flag 26→25, about −2.1k T); [`d631017`](../commits/d631017.md) (flag 24→20, about −2.8k T).
- **Re-fit the width schedule**: [`b5796ce`](../commits/b5796ce.md) replaces linear slopes with a fitted 700-round table (−1,378 bit-rounds, about −8k T before λ buy-backs).
- **Turn a narrower register into a lower peak**: [`2aedb45`](../commits/2aedb45.md) narrows `SCHED_J2`/`GAP_J2` by 1 bit over divsteps 101–260 and lowers the cap, so both factors of the score drop.
- **Extreme case**: [`716e359`](../commits/716e359.md) replaces a 55-CCX truncated constant compare with one CX of bit 255.
- **Sell/buy rebalance**: [`84e78ce`](../commits/84e78ce.md) shifts per-cell compare bands, removing more bits than it adds.

## Related concepts

[nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [adders-and-carries.md](adders-and-carries.md) · [modular-fold.md](modular-fold.md) · [pingpong-division.md](pingpong-division.md) · [skywalk-gcd.md](skywalk-gcd.md) · [trailmix-jump-gcd.md](trailmix-jump-gcd.md) · [measurement-uncompute.md](measurement-uncompute.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [scoring-and-validation.md](scoring-and-validation.md)
