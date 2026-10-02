# Kaliski almost-inverse (the May–June inversion)

> From the organisers' reference circuit (29–30 May) until pldallairedemers' [cddd5df](../commits/cddd5df.md) (2 June), every frontier commit computed λ = dy/dx with two runs of a reversible Kaliski binary almost-inverse, in the qrisp/Roetteler style. The state was `u, v_w` (the GCD pair), `r, s` (the Bézout pair), a termination flag `f` and one history qubit `m_hist[i]` per iteration. Each run had a fixed number of iterations, ran forwards and then backwards, and was followed by `iters` modular halvings or doublings to remove the 2^iters scale. Almost every saving in this era came from betting on how fast Kaliski converges: shorter loops, cheaper bodies in a long prefix, a free rotation for `r`, and widths fitted to 80k sample inputs. There was no tail nonce, so each bet only had to hold on the op stream's own draw. The score fell from 2715 × 3,942,753 to 2006 × 2,552,687 ([cef001a](../commits/cef001a.md)). Then the dialog GCD replaced the whole inverter at 1698 qubits.

## How it works in this circuit

**Files.** Until [c8e508f](../commits/c8e508f.md) (1 June) split it, everything is in `src/point_add/mod.rs`. After the split, the body is in `kaliski_walk.rs`, thresholds and knobs in `kaliski_state.rs`, the pair wrappers in `kaliski_inv.rs`, the driver in `point_add.rs`, and the constant adders in `cuccaro.rs` / `modular.rs` / `solinas.rs`.

**State and init** (`alloc_kaliski_state`). The registers are `u, v_w, r, s` (256 qubits each), `m_hist` (exactly `iters` qubits) and `f`. The run starts at `(u, v_w, r, s) = (p, dx, 0, 1)` with `f = 1`. The flags `a_f`, `b_f` and `add_f` are allocated fresh inside each iteration.

**One iteration** (`kaliski_iteration`, using qrisp's step numbers):

```
STEP 0   is_zero = (v_w == 0) via OR chain; m_i ^= f·is_zero; f ^= m_i
STEP 1-2 branch flags from u[0], v_w[0] and l = (u > v_w)   -> a_f, b_f, m_i
STEP 3   cswap(a_f): (u, v_w) and (r, s)
STEP 4   add_f = f·¬b_f;  v_w -= add_f·u;  s += add_f·r     (one shared tmp register, measured unload)
STEP 6   v_w >>= 1                                          (unconditional swap chain, 0 Toffoli)
STEP 7+8 r = 2r mod p
STEP 9   cswap(a_f) back;  STEP 10: a_f ^= ¬s[0]            (qrisp invariant)
```

The iteration's branch bit stays in `m_hist[i]`, so the backward run (`kaliski_backward_caps`) can be the exact mirror. Provable widths come from the invariant `bitlen(u) + bitlen(v_w) ≤ 2n − i`, which gives width `n` for `i < n` and `2n − i` after that. The `(r, s)` widths use `max(r, s) ≤ 2^i`.

**Pairs and the descale.** After the forward run, `u = 1`, `v_w = 0`, `f = 0` and (the comment claims, once iters ≥ ~407) `s = p`. These registers are freed by value and rebuilt before the backward run. `r` holds −dx⁻¹·2^iters mod p. The negation is never applied; callers swap `mul_add` for `mul_sub` instead. An input that terminates early only keeps doubling `r`, so a fixed `iters` gives a fixed scale. In `build_standard_point_add`:
- **Pair 1** computes `lam = ty·inv` (phase `pair1_mul1`), runs `iters` × `mod_halve_inplace_fast` (`pair1_halve`), then runs Kaliski backwards.
- **Pair 2** inverts the updated x-difference. It runs `iters` × `mod_double_inplace_fast` on λ (`pair2_double`), then `pair2_mul` and `pair2_cleanup`, which clear λ.

Pair 1's `m_hist` is live at the peak, so each pair-1 iteration cost a qubit as well as Toffoli.

**Bulk prefix.** For `i < BULK_PREFIX_SAFE_ITERS` the drivers call `kaliski_iteration_bulk_prefix3` and its mirror. This body assumes the run is still active. It drops STEP 0 (an OR chain of up to 255 Toffoli) and removes `f` from the STEP 1/2/4 controls.

**Free r rotation.** For `i < R_SMALL_THRESHOLD`, STEP 7+8 is `mod_double_no_corr`, a 0-Toffoli rotation that assumes `r`'s top bit is 0. From the threshold on it is a Solinas double of about 255 Toffoli, later the register-free `mod_double_inplace_direct` (`KAL_GZ_DOUBLE_DIRECT`, [d19dbb5](../commits/d19dbb5.md)).

**W-TRUNC** ([36e8578](../commits/36e8578.md)). `kal_wtrunc_width(it, n)` fits an envelope to 80k random inputs:

```
env(it) = n                                   for it < K0
env(it) = max(n − ⌊(it − K0)·num/den⌋, floor)  otherwise   (num/den = 2/3, floor = 3)
width   = min(provable, env(it) + margin)
```

36e8578 itself hard-codes the slope as 2/3 and has no floor: `env = n − ⌊(it − K0)·2/3⌋`, then `+ margin`, capped at `n`. The `num/den` and `floor` knobs first appear in [6e71096](../commits/6e71096.md) (2 June).

It clips the STEP 0 OR chain, the STEP 2 comparator and the STEP 4 load/subtract. From [404d630](../commits/404d630.md)/[a25248f](../commits/a25248f.md) it also clips the `(u, v_w)` cswaps (`KAL_CSWAP_WTRUNC`). A merged swap uses the wider iteration-(k−1) envelope. Each margin bit was worth about 4,200–4,400 Toffoli ([1e18b4d](../commits/1e18b4d.md)).

**Boundary cswap merges.** STEP 9 of iteration k and STEP 3 of k+1 swap the same pair, and `cswap(a)·cswap(b) = cswap(a⊕b)`.
- **`(r, s)` merge** ([9bcc27d](../commits/9bcc27d.md), −274,327 T). STEP 9 copies `a_k` into a one-qubit **frame**. The next STEP 3 swaps under `a_f ⊕ frame`, then resets the frame with `a_{k−1} = ¬(a_k ? r[0] : s[0])`. That reset took 2 CCX, then 1 after [d4959a1](../commits/d4959a1.md). The frame is allocated after STEP 8 and freed at STEP 3, so it is never live at the STEP 4 peak.
- **`(u, v_w)` merge** ([36a2989](../commits/36a2989.md), −260,517 T). This reuses the frame. The next iteration sees physically exchanged registers, so it needs fix-ups:
  - STEP 1 toggles `a_f` and `m_i` on `frame·(u0⊕v0)`. That is 2 CCX, or 1 CCX plus a fan-out after [ce60f0e](../commits/ce60f0e.md).
  - STEP 2 sets `l_gt ^= frame`. This is right only when `u ≠ v_w`.

**In-place v and borrowed carries** ([d19dbb5](../commits/d19dbb5.md), 2708 → 2310 q).
- `with_kal_inv_raw_borrow_v_w_pair` uses the live `tx` register itself as `v_w`. The forward run drives it to 0 and the backward run restores it.
- STEP 4's measured-carry Cuccaro adds take their 255-wire carry bank from `m_hist[i+1..]` (`KAL_GZ_STEP4_SLOW`). Those history bits are still |0⟩ forwards and already uncomputed backwards. Late iterations add `u`'s provably zero high bits (`KAL_GZ_LATE_RECOVER`). If more than `KAL_GZ_MAX_FRESH` = 131 carries would have to be fresh, the code falls back to a carry-free adder.
- [233a44c](../commits/233a44c.md) moved the carries to the clean high bits of `s`, `r` and `u` (`KAL_GZ_EARLY_RECOVER`). That unpinned the history slots, so the **dialog history-fold** (`KAL_DIALOG_FOLD`) could put about 196 `m_hist` bits on `v_w` bits above `env + slack`. The peak went 2309 → 2025. The slack later went 4 → 3 ([9899c06](../commits/9899c06.md)) and → 0 ([0435f04](../commits/0435f04.md), 2002 q).

**Constant adders and the shift-22 fold.** Reduction uses `2^256 ≡ c = 2^32 + 977 = 1 + 2^4 − 2^6 + 2^10 + 2^32`.
- A fold adds `hi` at weight 1, doubles it in place to weights 4, 6 and 10, then calls `mod_shift_left_by_k(hi, 22)` to reach 2^32 and halves 10 times back. The shift spills 22 bits and folds `spill·c` back with five Cuccaro ops at offsets 0/4/6/10/32.
  - [81ff75b](../commits/81ff75b.md) turned the offset-0 op into 22 CX.
  - [c8e508f](../commits/c8e508f.md) collapsed the five ops to two by computing `spill·977` into 32-bit scratch first.
  - [3f534f2](../commits/3f534f2.md) and [3ab1c72](../commits/3ab1c72.md) truncated the spill carries.
  - [d19dbb5](../commits/d19dbb5.md) and [ccd7530](../commits/ccd7530.md) ran it on dirty-borrowed `lo` with Gidney venting adders.
- The ±c steps of the modular helpers moved from a loaded 257-qubit constant register to register-free direct adders: [168048c](../commits/168048c.md) (+756 T, −2 q) and [bc9728a](../commits/bc9728a.md).
  - A known-1 control saves 13 T per call ([8631b04](../commits/8631b04.md)).
  - The MAJ fold takes 3 CCX → 1 per carry ([0be8d11](../commits/0be8d11.md) for subtract, [d4959a1](../commits/d4959a1.md) for add).
- **Carry-tail** ([1e18b4d](../commits/1e18b4d.md)). Above c's top set bit a carry can only propagate, so the chain is cut at `min(n−1, k0 + W)` with `k0 = max(33, c.bit_len())` (`kal_carrytail_count_c`, [d6551e8](../commits/d6551e8.md)). For the sparse c this is `cut = 33 + W`. The dense `p + 1` used by `mod_neg`/`mod_double` keeps its full chain. [ba05d3a](../commits/ba05d3a.md) routed `mod_double_inplace_fast` through this adder.

## Why it is (or is not) exact

**Exact:**
- the two swap merges, apart from the `u ≠ v_w` premise;
- the frame reset;
- in-place `v`;
- borrowed carries on bits that are zero by construction;
- register-free and dirty adders;
- the MAJ folds.

**Provable only in a range:**
- **Bulk prefix.** The comment above `BULK_PREFIX_SAFE_ITERS` proves the first 256 iterations are non-terminal, because `u + v_w ≥ (p + dx)/2^i`. Caps of 377 → 394 → 400/401 are empirical, though [1c400f2](../commits/1c400f2.md) argues they add no new failure mode.
- **R_SMALL.** The doc comment's `max(r, s) ≤ 2^i` covers only i < 256. [9bd0748](../commits/9bd0748.md) shows `u·s + v·r = p` keeps `r < 2^255` while the run is active. So the move 262 → 263 ([a16788e](../commits/a16788e.md)) → 326 ([9bd0748](../commits/9bd0748.md)) is a bet that every drawn input runs at least that long. Later comments reject 328 and 329.
- **`(u, v_w)` merge.** It is provable up to prefix 254 (`u = v_w` only at (1, 1)). The prefixes 255, 256, 329 and 331 ([a8688f8](../commits/a8688f8.md), [cd34b79](../commits/cd34b79.md), [908521d](../commits/908521d.md), [cef001a](../commits/cef001a.md)) are empirical.

**Empirical:**
- **Loop lengths.** An input needs 256–512 steps. An input that is unfinished at `iters` frees non-zero registers and gives a wrong λ. The code calls clean lengths a "non-monotonic single-input classical-mismatch cliff" found by grid search.
- **W-TRUNC.** It is a distribution fit; margin 0 has no slack.
- **Carry-tail.** A 3M-trial Monte Carlo put the longest run above bit 32 at 28 (add) and 19 (sub). Windows of 19–20 sit at that edge.

Failures show as classical mismatches, or as phase or ancilla garbage when the backward run stops mirroring the forward run. See [nonce-island-and-lambda.md](nonce-island-and-lambda.md) for why each value was tuned together with the draw.

## Knobs and names you will see in commits

- `KAL_PAIR1_ITERS`, `KAL_PAIR2_ITERS`, `pair1_default` / `pair2_default`: loop lengths (404/400 → 397/396 at [8eb6b5e](../commits/8eb6b5e.md)).
- `BULK_PREFIX_SAFE_ITERS`, `KAL_BULK3_*`, `bulk_prefix_caps`: the bulk prefix.
- `R_SMALL_THRESHOLD`, `KAL_R_SMALL_THRESHOLD`, per-pair `KAL_PAIR{1,2}_R_SMALL_THRESHOLD` ([a444668](../commits/a444668.md)).
- `KAL_WTRUNC`, `KAL_WTRUNC_K0` (27 → 20/21), `KAL_WTRUNC_MARGIN` (32 → 0), `KAL_WTRUNC_SLOPE_NUM/DEN`, `KAL_WTRUNC_FLOOR`, `KAL_CSWAP_WTRUNC`.
- `KAL_CSWAP_RS_MERGE`, `KAL_CSWAP_UV_MERGE`, `KAL_CSWAP_UV_MERGE_SAFE_ITERS`, `KAL_UV_STEP1_FANOUT`; *frame*.
- `KAL_PAIR1_BORROW_DX_DENOM`, `KAL_PAIR2_INPLACE_V`, `POINT_ADD_STACK_2565`, `KAL_GOUZIEN_9N` and `KAL_GZ_*` (STEP4_SLOW, LATE_RECOVER, EARLY_RECOVER, MAX_FRESH, DOUBLE_DIRECT, SOLINAS_LOWSCRATCH).
- `KAL_DIALOG_FOLD`, `KAL_DIALOG_FOLD_SLACK`: history-fold. This "dialog" is unrelated to the dialog GCD.
- `KAL_CARRYTAIL_TRUNC` (`both`/`add`/`sub`), `KAL_CARRYTAIL_W` (96 → 18), `KAL_CARRYTAIL_K0` = 33, `KAL_MAJFOLD_ADD/SUB`, `KAL_DIRECT_CONST_DOUBLE`.
- *shift22*, `mod_shift_left_by_k`, `LOWQ_SHIFT22`, `AUDIT_SHIFT22_POS0_CX`.
- `KAL_REROLL`, `KAL_SCREEN`: draw rerollers ([6e71096](../commits/6e71096.md)).
- `KAL_DOUBLE_CARRY_TRUNC_W` / `KAL_FOLD_CARRY_TRUNC_W` (from [f8a36ba](../commits/f8a36ba.md) and [ad02935](../commits/ad02935.md) respectively) are dialog-era fold windows that kept the prefix; see [modular-fold.md](modular-fold.md).

## How optimizations use it

- **Iteration/threshold tuning:** [a16788e](../commits/a16788e.md), [9bd0748](../commits/9bd0748.md), [1c400f2](../commits/1c400f2.md), [a3ee589](../commits/a3ee589.md), [77b87f1](../commits/77b87f1.md), [801b73e](../commits/801b73e.md), [13a7a53](../commits/13a7a53.md).
- **Boundary merges:** [9bcc27d](../commits/9bcc27d.md), [36a2989](../commits/36a2989.md), [f910ba3](../commits/f910ba3.md), [908521d](../commits/908521d.md).
- **Width truncation:** [36e8578](../commits/36e8578.md), [6da9882](../commits/6da9882.md), [13ac8da](../commits/13ac8da.md), [179ab10](../commits/179ab10.md), [404d630](../commits/404d630.md), [5136c0a](../commits/5136c0a.md), [700d5a7](../commits/700d5a7.md).
- **Carry-tail truncation:** [1e18b4d](../commits/1e18b4d.md), [2abe7f4](../commits/2abe7f4.md), [d6551e8](../commits/d6551e8.md), [ba05d3a](../commits/ba05d3a.md), [297f5e5](../commits/297f5e5.md), [1b913c5](../commits/1b913c5.md).
- **Peak work:** [168048c](../commits/168048c.md), [bc9728a](../commits/bc9728a.md), [d19dbb5](../commits/d19dbb5.md), [b60eec2](../commits/b60eec2.md), [233a44c](../commits/233a44c.md), [ccd7530](../commits/ccd7530.md), [0435f04](../commits/0435f04.md).

## Timeline

- [f43a73e](../commits/f43a73e.md) (30 May): unpadded reference, 2715 × 3,942,753. Loops 404/400, bulk 377, R_SMALL 262.
- [a16788e](../commits/a16788e.md) (30 May): 399/398, bulk 394, 2710 q. [bc9728a](../commits/bc9728a.md): 2708 q.
- [9bd0748](../commits/9bd0748.md) (31 May): R_SMALL 326, −64,260 T. [9bcc27d](../commits/9bcc27d.md): `(r, s)` merge, 2708 × 3,546,654.
- [d19dbb5](../commits/d19dbb5.md) (31 May): in-place v plus borrowed carries, 2310 × 3,656,039.
- [36a2989](../commits/36a2989.md) (1 Jun): `(u, v_w)` merge, 3,361,759 T. [36e8578](../commits/36e8578.md): W-TRUNC, 3,063,680 T. [1e18b4d](../commits/1e18b4d.md): carry-tail, 2309 × 2,870,041. [404d630](../commits/404d630.md): cswap W-TRUNC, 2,615,899 T. [ba05d3a](../commits/ba05d3a.md): 2,462,914 T.
- [6e71096](../commits/6e71096.md) (2 Jun): `KAL_REROLL`, 2309 × 2,408,761.
- [233a44c](../commits/233a44c.md) (2 Jun): history-fold, 2025 q. [ccd7530](../commits/ccd7530.md): 2006 q. [0435f04](../commits/0435f04.md): 2002 q.
- [908521d](../commits/908521d.md), [cef001a](../commits/cef001a.md) (2 Jun): merge prefix 331, 2006 × 2,552,687. This was the last Kaliski frontier.
- [cddd5df](../commits/cddd5df.md) (2 Jun, three minutes later): the dialog GCD replaces both inversions, 1698 × 2,447,846; Kaliski never returns to the frontier.

## Related concepts

[dialog-gcd-early.md](dialog-gcd-early.md) · [transcript-codecs.md](transcript-codecs.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md) · [adders-and-carries.md](adders-and-carries.md) · [modular-fold.md](modular-fold.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [measurement-uncompute.md](measurement-uncompute.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [squaring-and-karatsuba.md](squaring-and-karatsuba.md) · [scoring-and-validation.md](scoring-and-validation.md)
