# Trailmix schedules and reserves (the tuning machinery, 19 June – 21 August)

> The trailmix circuit ([trailmix-jump-gcd.md](trailmix-jump-gcd.md)) arrived on 19 June (bdb1d22) with its scratch decisions frozen in baked tables. Every adder, comparator and `+f` fold reads its next entry from a per-call table, through a thread-local cursor. The entry sets how many carries get their own clean wire, and how the adder is chunked. Most of the trailmix commits that followed, until 21 August, change no algorithm. They shift those tables by env "deltas", clamp them under a live qubit target with per-call reserves, search cheaper chunk layouts, narrow the `+f` padding, skip work in the last GCD steps, lend wires whose value is known, or strip gates after the build. Nearly all budget moves are exact and trade Toffoli against peak qubits. The PAD cuts and most late-tail skips are probabilistic.

## How it works in this circuit

**Baked tables and cursors** (`trailmix_ludicrous/schedule.rs`, read by `mod.rs::load_schedule()`). The source comment says the tables "deterministically replace any live cost-model decision, so the emitted circuit is fixed per call". They were fitted "for the EC-add at ceiling 1167" (`arith::CEILING = 1167`).

| table | entries | read by | meaning |
|---|---|---|---|
| `GCD_SUB_K` | 1,032 (4 walks × 258) | `next_gcd_k()` | carry budget `k` of each GCD subtract |
| `GCD_BRANCH` | 1,032 | `next_gcd_branch()` | GCD adder type: 0 plain (640), 1 varchunk (344), 2 adaptive (48) |
| `APPLY_COUT_K` | 516 | `next_cout_k()` | budget of each apply cofactor add/sub |
| `FFG_G` | 516 | `next_ffg()` | clean-carry count `g` of that call's `+f` fold |
| `FOLD_SCHED` | 514 | `next_fold()` | fused-doubling fold: `nv ≥ 0` clean vents, or `−s` for a chunked fold with chunk `s` (all −5) |
| `CMP_K` | 1,028 | `next_cmp_k()` | held carries in each swap-decision compare |
| `HYB_V` | 1,558 | `next_hyb_v()` | vented carries of each plain Gidney add |
| `SQ_ROW_K` | 512 | `next_sqrow_k()` | headroom of each square row add |

`SCHED_J2` and `GAP_J2` are indexed by step, not by call. The trailmix GCD page covers them. A cursor past the end of its table returns a sentinel (`usize::MAX`) that means "no constraint".

**The ordinal problem.** Entries are matched to calls by emission order alone. An edit that adds or removes a call shifts every later read. Commits work around this by hand:
- [6c0769f](../commits/6c0769f.md) still advances the `next_cout_k()` and `next_ffg()` cursors when it skips an add.
- [27d4627](../commits/27d4627.md) calls `advance_ffg_call_index(3)` so later fold reserves stay aligned.
- [a254a8a](../commits/a254a8a.md) adds `BAKED_ITERS = 258`, pads each pass's block (`widen_sched_blocks`), and disables every census-keyed table once `ITERS ≠ BAKED_ITERS`.
- [bc2334a](../commits/bc2334a.md)'s note warns that calls leaving the plain path stop advancing `HYB_V`.

**Overlays.** These change the tables without editing them:
- `LUD_EXTRA_FOLD_VENTS` / `_MIN_G` / `_MAX_G` give every `FFG_G` entry within the bounds `min(g + V, 53)` ([a9ac507](../commits/a9ac507.md), [fd89e69](../commits/fd89e69.md), [764afda](../commits/764afda.md), [f265bb1](../commits/f265bb1.md)).
- `CMP_K` + 4 and then + 7 ([75851e6](../commits/75851e6.md), [b1dec1e](../commits/b1dec1e.md)).
- A side line's `TRAILMIX_*_DELTA` / `TRAILMIX_FOLD_LOW_BITS` ([c9c03de](../commits/c9c03de.md)).
- The `TLM_*_DELTA` family is the one that lasted ([b310de9](../commits/b310de9.md), [31421df](../commits/31421df.md)). `TLM_HYB_V_DELTA`, `TLM_COUT_K_DELTA`, `TLM_FFG_DELTA` and `TLM_FOLD_DELTA` subtract, saturating, from every entry except the sentinel. `next_fold()` leaves negative codes alone. `TLM_*_CALL_DELTAS` and `TLM_*_CALL_OVERRIDES` take `call:value` lists (`fit_schedule_value`). `TLM_GCD_K_ADJUST` over `[_AFTER, _BEFORE)` moves `GCD_SUB_K` by GCD step. It was −2 over steps 169–195 from [7b7bd12](../commits/7b7bd12.md) to the end.

Fewer budget wires mean more carries are computed in place or recomputed, so Toffoli go up and the peak goes down.

**The live target and per-call reserves** ([fed64cf](../commits/fed64cf.md), 20 June). `target_qubit_headroom()` returns `TLM_TARGET_Q − active_qubits`. Each budget becomes:
- `min(schedule, headroom)` for hybrid vents, cout and GCD `k`;
- `headroom − 1` for compare carries;
- `headroom − reserve` for `+f` windows and fused folds.

The cap therefore bites only where it binds. A window or fold allocates more than its `g` or `nv`, so it keeps a reserve: `TLM_TARGET_FFG_RESERVE` = 9 and `TLM_TARGET_FOLD_RESERVE` = 4 by default. Hand-fitted `call:reserve` maps keyed by call index override that for the calls near the peak (`TLM_TARGET_FFG_CALL_RESERVES`, later `_DELTAS` / `_OVERRIDES`, and `TLM_TARGET_FOLD_CALL_RESERVE(S|_OVERRIDES)`). The square got its own cap in [d44cad3](../commits/d44cad3.md): `TLM_SQUARE_PEAK_CAP` overrides `SQUARE_PEAK_HARD_CAP`, and `TLM_SQUARE_VENT_MARGIN` sets the margin. The realized peak can sit one above the cap: [31f9c58](../commits/31f9c58.md) set 1149 and measured 1150.

**Chunked-adder layout search** ([bc2334a](../commits/bc2334a.md)). `searched_cout_layout(n, k)` and `searched_gcd_adaptive_layout(n, k)` try every chunk width `c` and top-part length. A layout must satisfy `nchunks + plain_len + margin ≤ k` and `nchunks + min(c, chunked_len) + margin ≤ k`. Among those, the search keeps the one with the lowest `2n + chunked_len + nchunks (±1)`. Each chunked bit adds a compare Toffoli to the measured boundary erase, which runs on about half the shots. The margins are `TLM_COUT_LAYOUT_MARGIN` and `TLM_GCD_ADAPTIVE_LAYOUT_MARGIN`, both later 0 ([916c0e3](../commits/916c0e3.md), [ed2715f](../commits/ed2715f.md)). `TLM_COUT_LAYOUT_FORCE_M1_KS=129` kept margin 1 at the two calls that raised Q, until the live target made it unnecessary ([6ba606a](../commits/6ba606a.md)).

**`+f` windows and PAD.** In `arith.rs`, `LSBS = PAD + bitlen(f)` is the fold window and `MSBS = PAD` is the width of the top-bit overflow compare. `add_f_window` has three forms:
- **clean**: `g ≥ LSBS − 1`; every carry gets a wire and is erased by `hmr` plus `cz_if_bit`.
- **hybrid**: a clean prefix of `g` bits, then a graduated chunked suffix (`controlled_add_const_chunked_graduated_off`) whose boundary carries need conditional compares.
- **dirty-borrow**: `g = 0`, or a suffix shorter than 2 bits. It borrows register bits above the window (`dirty_carryin`) and discharges their phase with Z.

`schedule::PAD` is a separate constant. It is the `cap` of the GCD subtract's varchunk boundary erase. [b310de9](../commits/b310de9.md) and [31421df](../commits/31421df.md) cut `arith::PAD` from 21 to 19, so windows went from 54 to 52 bits and compares from 21 to 19. They also cut `schedule::PAD` from 21 to 20.

**Late-tail apply relaxations** (`gcd.rs`). Each helper tests `i + last_n ≥ ITERS`:
- `TLM_APPLY_FWD_CSWAP_SKIP_LAST`, with the legacy `TLM_APPLY_FWD_FIRST_CSWAP_SKIP`;
- `TLM_APPLY_INV_CSWAP_SKIP_LAST`, with the earlier `TLM_APPLY_CSWAP_SKIP_LASTK` / `TLM_APPLY_INV_FIRST_CSWAP_SKIP`;
- `TLM_APPLY_FWD_S2_ZERO_LAST` and `TLM_APPLY_INV_S2_ZERO_LAST`, which drop the `s2` second doubling;
- `TLM_APPLY_ADD_SKIP_LASTK`, which drops the apply add/sub.

Each skipped 256-wire cswap saves 256 Toffoli; each dropped `s2` doubling about 260.

**Known-value wire loans.** `BExt::loan_zero_qubit(q)` puts a wire that holds |0⟩ back on the LIFO free list without an `R`. `reclaim_zero_qubit(q)` takes that exact id back, and panics if it is still in use. The wires lent this way:
- `u[0]`, which is always 1 after the cswap, flipped to 0 (`TLM_PARK_ODD_U0`, `TLM_LOAN_ODD_U0`; [cea9f5f](../commits/cea9f5f.md), 1166→1165).
- `v[0]`, which is 0 after the subtract, and the GCD adder's known `y[0]` (`TLM_LOAN_EVEN_V0`, `TLM_LOAN_GCD_Y0`; [f8d23a9](../commits/f8d23a9.md), →1164).

[fed64cf](../commits/fed64cf.md) also lends each carry wire right after its `hmr`. See [venting-and-wire-loans.md](venting-and-wire-loans.md).

**Post-passes and strips.** `constprop.rs` ([497cc20](../commits/497cc20.md)) propagates {0, 1, ?} from the known initial states. It drops a CCX with a known-0 control and folds one with a known-1 control to CX. [b02b354](../commits/b02b354.md) adds a fixpoint loop (`CONSTPROP_MAX_ITERS`), self-inverse pair cancellation, and affine GF(2) equal/complementary-control detection. Positional strips came next. `drop_dead_*.idx` files list op indices that a census never saw fire, and `build()` deletes those ops. The lineage runs [4a90d04](../commits/4a90d04.md) → [20b9a1d](../commits/20b9a1d.md), then [6c0769f](../commits/6c0769f.md) → [27d4627](../commits/27d4627.md) → [985eaec](../commits/985eaec.md) → [da51a48](../commits/da51a48.md). Any upstream edit shifts the indices, so every list had to be re-mined. [6dafa07](../commits/6dafa07.md) replaced the lists with `(call, bit)` skip tables inside the primitives. See [dead-gate-strip.md](dead-gate-strip.md).

**Classical 3·ox** ([662e267](../commits/662e267.md)). `ox` is a classical `BitId` register, so `classical_times3_mod_q` computes `3·ox mod p` with `BitStore0`/`BitStore1`/`BitInvert` ops, which cost no Toffoli. The circuit then does one `mod_add_exact`, replacing two modular adds, a doubling and a halving. [6c0769f](../commits/6c0769f.md) reverted it and [27d4627](../commits/27d4627.md) restored it.

## Why it is (or is not) exact

- **Exact, at a peak risk.** Deltas, reserves, `TLM_TARGET_Q`, layout search and margins, `LUD_EXTRA_FOLD_*`, `CMP_K` shifts, loans, constprop and classical 3·ox are all exact. They only decide whether a carry is measured, recomputed or borrowed. A wrong budget raises Q but never fails validation ([6ba606a](../commits/6ba606a.md)). A wrong loan invariant would show up as ancilla or classical garbage.
- **Exact by argument.**
  - The first forward-apply cswap: `y = 0` there ([5c34dd1](../commits/5c34dd1.md)).
  - The graduated suffix's dropped carry-out (`TLM_GRAD_FINAL_NO_COUT`), because the window discards that carry anyway.
- **Exact except on inputs that already fail.** The inverse last-step cswap: `swp = 1` at `i = ITERS−1` only if the GCD has not converged ([9d524b7](../commits/9d524b7.md)).
- **Probabilistic.**
  - The forward cswap skip beyond the first step, `S2_ZERO_LAST`, and `ADD_SKIP_LASTK`. Each is wrong when the GCD's last subtract (or swap) falls inside the skipped steps. [9d524b7](../commits/9d524b7.md) measured `TLM_APPLY_CSWAP_SKIP_LASTK = 2` (both directions) at about 18 classical and 8 phase failures per random draw.
  - PAD: about 2^−(PAD+1) per fold (the dropped carry also needs a carry out of the low `bitlen(f)` bits; `schedule.rs` rounds it to ~2^−PAD) and about 2^−PAD per top-bit compare.
  - `.idx` strips: an empirical census.

Every op-stream change needs a new nonce ([nonce-island-and-lambda.md](nonce-island-and-lambda.md)).

## Knobs and names you will see in commits

- `GCD_SUB_K`, `GCD_BRANCH`, `APPLY_COUT_K`, `FFG_G`, `FOLD_SCHED`, `CMP_K`, `HYB_V`, `SQ_ROW_K`, `next_*()`, `load_schedule`, `BAKED_ITERS`, `baked_artifacts_valid()`, `widen_sched_blocks`
- `LUD_EXTRA_FOLD_VENTS` / `_MIN_G` / `_MAX_G`; `TRAILMIX_*_DELTA`, `TRAILMIX_FOLD_LOW_BITS`
- `TLM_{HYB_V,COUT_K,FFG,FOLD}_DELTA`, `TLM_*_CALL_DELTAS` / `_CALL_OVERRIDES`, `TLM_GCD_K_ADJUST(_AFTER/_BEFORE)`, `TLM_GCD_K_EXTRA_ADJUST`
- `TLM_TARGET_Q`, `target_qubit_headroom()`, `TLM_TARGET_{FFG,FOLD}_RESERVE`, `TLM_TARGET_{FFG,FOLD}_CALL_RESERVE*`, `TLM_SQUARE_PEAK_CAP`, `TLM_SQUARE_VENT_MARGIN`
- `TLM_COUT_LAYOUT_SEARCH` / `_MARGIN` / `_FORCE_M1_KS`, `TLM_GCD_ADAPTIVE_LAYOUT_*`, `TLM_GCD_RESELECT_LAYOUT`, `TLM_DIRECT_VARCHUNK`
- `arith::PAD`, `LSBS`, `MSBS`, `schedule::PAD`; `add_f_window(_clean|_hybrid)`, `dirty_carryin`
- `TLM_APPLY_{FWD,INV}_CSWAP_SKIP_LAST`, `*_FIRST_CSWAP_SKIP`, `TLM_APPLY_CSWAP_SKIP_LASTK`, `TLM_APPLY_{FWD,INV}_S2_ZERO_LAST`, `TLM_APPLY_ADD_SKIP_LASTK`
- `loan_zero_qubit`, `reclaim_zero_qubit`, `TLM_PARK_*`, `TLM_LOAN_*`
- `constprop.rs`, `CONSTPROP_MAX_ITERS`, `drop_dead_*.idx`, `dead_*.idx`, `DROP_DEAD_ROBUST_DISABLE`, `DROP_DEAD_IDX_FILE`
- `coord_add3x` / `coord_add3x_orig`, `classical_times3_mod_q`, `advance_ffg_call_index`

## How optimizations use it

- **Budget trims for qubits:** [b310de9](../commits/b310de9.md), [31421df](../commits/31421df.md), [7b7bd12](../commits/7b7bd12.md), [f861f87](../commits/f861f87.md) (+1 delta, within draw noise).
- **Target and reserve refits:** [fed64cf](../commits/fed64cf.md) (1162→1159), [6ba606a](../commits/6ba606a.md) (1157), [cde752d](../commits/cde752d.md) (1156), [da51a48](../commits/da51a48.md) (1153). Cap raises bought Toffoli in [f5ff95b](../commits/f5ff95b.md) and [d9ef3e9](../commits/d9ef3e9.md). [31f9c58](../commits/31f9c58.md) forced the caps down with `set_var`.
- **Spending headroom on exact layouts:** [bc2334a](../commits/bc2334a.md) (−6,460 T), [916c0e3](../commits/916c0e3.md), [ed2715f](../commits/ed2715f.md), [764afda](../commits/764afda.md), [75851e6](../commits/75851e6.md).
- **Late-tail skips:** [5c34dd1](../commits/5c34dd1.md), [9d524b7](../commits/9d524b7.md), [9af02f7](../commits/9af02f7.md), [cde752d](../commits/cde752d.md), [6c0769f](../commits/6c0769f.md), [474c29a](../commits/474c29a.md).
- **Constant propagation and strips:** [497cc20](../commits/497cc20.md), [b02b354](../commits/b02b354.md), [9798bc9](../commits/9798bc9.md), [fa7126d](../commits/fa7126d.md), [4a90d04](../commits/4a90d04.md) (−13,014 T), [6dafa07](../commits/6dafa07.md).

## Timeline

- [bdb1d22](../commits/bdb1d22.md) (19 Jun): module and tables, 1167 q × 1,422,591.
- 19 Jun:
  - first overlays: [a9ac507](../commits/a9ac507.md), [75851e6](../commits/75851e6.md), [c9c03de](../commits/c9c03de.md);
  - layout search: [bc2334a](../commits/bc2334a.md);
  - constprop: [497cc20](../commits/497cc20.md);
  - loans: [cea9f5f](../commits/cea9f5f.md) and [f8d23a9](../commits/f8d23a9.md), reaching 1164;
  - deltas and PAD: [b310de9](../commits/b310de9.md) (1163), then [31421df](../commits/31421df.md) (1162, 20 Jun).
- 20 Jun:
  - [fed64cf](../commits/fed64cf.md): `TLM_TARGET_Q` = 1159;
  - classical 3·ox: [662e267](../commits/662e267.md);
  - first skips: [5c34dd1](../commits/5c34dd1.md), [9d524b7](../commits/9d524b7.md).
- 20–21 Jun: [6ba606a](../commits/6ba606a.md) (1157); [cde752d](../commits/cde752d.md) (1156, s2 and forward-2 skips).
- 21–23 Jun: positional strips [4a90d04](../commits/4a90d04.md) to [985eaec](../commits/985eaec.md); [da51a48](../commits/da51a48.md) (1153).
- 26 Jun: [6dafa07](../commits/6dafa07.md) (in-primitive skip tables); [d44cad3](../commits/d44cad3.md) (`TLM_SQUARE_PEAK_CAP`, 1152).
- 26 Jul: [a254a8a](../commits/a254a8a.md) (`BAKED_ITERS`; tables padded for `ITERS` 261); cap re-sweeps in [f5ff95b](../commits/f5ff95b.md) and [d9ef3e9](../commits/d9ef3e9.md).
- 12 Aug: [474c29a](../commits/474c29a.md), cswap skip-last 3/3.
- 18–20 Aug: [afcc72e](../commits/afcc72e.md) and [0422437](../commits/0422437.md) (1153); [31f9c58](../commits/31f9c58.md) (caps forced to 1149, 1150 q × 1,284,776).
- 21 Aug: [897dda2](../commits/897dda2.md) replaces the route ([pingpong-division.md](pingpong-division.md)).

## Related concepts

[trailmix-jump-gcd.md](trailmix-jump-gcd.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [adders-and-carries.md](adders-and-carries.md) · [modular-fold.md](modular-fold.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [measurement-uncompute.md](measurement-uncompute.md) · [dead-gate-strip.md](dead-gate-strip.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [scoring-and-validation.md](scoring-and-validation.md) · [squaring-and-karatsuba.md](squaring-and-karatsuba.md)
