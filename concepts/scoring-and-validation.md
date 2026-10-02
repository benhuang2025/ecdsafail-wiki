# Scoring and validation

> A submission is a program that emits a list of gates (the *op stream*) for one secp256k1 point addition. A trusted evaluator runs that stream on 9,024 test inputs and checks three things on every input: the output point is right, no stray phase is left behind, and every scratch qubit is back at |0⟩. If all checks pass, the score is **(average executed Toffoli per input, rounded) × (peak qubits)**. Lower is better. The test inputs come from a hash of the op stream itself, so the circuit cannot be tuned to a known test set. A submission that passes and beats the current best is *promoted* and becomes a commit on the competition's `main` branch.

## How it works in this circuit

**Two stages.** `benchmark.sh` first runs `build_circuit`. This is untrusted contestant code from `src/point_add/`, run in a sandbox, and it writes `ops.bin`. Then `src/bin/eval_circuit.rs` runs. It never imports contestant code. It loads `ops.bin`, bounds-checks it, and rejects aliased operands, for example `CCX q q q`.

**Test inputs.** `fiat_shamir_seed` absorbs the domain tag `quantum_ecc-fiat-shamir-v2`, the op count, and every field of every op into SHAKE256, an extendable-output hash. From that stream it draws scalar pairs (k1, k2), computes the points k1·G and k2·G, and gets the expected sum from a classical reference adder. Pairs that are degenerate (equal x, or the point at infinity) are skipped without replacement, so `n_shots` is "up to 9,024". In practice a skip essentially never happens. The **same** SHAKE stream then supplies the random outcomes of every `R` (reset) and `Hmr` (X-basis measure-and-reset). So a given op stream fixes both the inputs and the measurement outcomes.

**Batches.** The simulator packs 64 shots into the bits of one `u64`. 9,024 = 141 batches of 64.

**Executed, not static, Toffoli.** In `sim.rs`, each `CCX`/`CCZ` adds `cond.count_ones()` to the Toffoli count: the number of shots in the batch whose classical condition is true. A Toffoli inside a `PushCondition` block, or one with a `c_condition` bit, only counts on the shots where it fires. Such conditions usually come from measurement results. In *measured uncompute*, you `Hmr` a garbage qubit and then apply a phase fix-up only if the random outcome was 1. A Toffoli-class fix-up therefore runs on about half the shots. The source puts it this way: "a compare's Toffoli sit under a `push_condition` and execute half the time" (`modular.rs`). So the score uses the **average** over shots:

```
avg_tof = (sum over shots of executed CCX/CCZ) / n_shots
score   = round(avg_tof) × Q          (write_score in eval_circuit.rs)
Q       = 1 + largest qubit id referenced anywhere in ops.bin   (analyze_ops)
```

X, Z, CX, CZ, Swap, R and Hmr add nothing to the score (Cliffords are counted, but only for reporting). Worked example, the frontier at `84e78ce` (1 Oct): 944,682 × 1,174 = 1,109,056,668.

**The three failure channels.** Each one is reported on every run:

| channel | how it is checked | what a failure means |
|---|---|---|
| classical mismatches (`cls`) | the output `x`,`y` registers vs the reference sum, **per shot** | wrong answer |
| phase-garbage batches (`pha`) | the batch's accumulated global-phase bits must be 0, **per batch** | leftover phase kickback. One cause is a `CZ`/`CCZ` fix-up that doesn't match the measured garbage. Another is resetting (`R`/`Hmr`) a qubit that was not |0⟩: the simulator XORs a random bit into the phase in that case. |
| ancilla-garbage batches (`anc`) | after clearing the output registers, every other qubit must be 0, **per batch** | a scratch qubit was never uncomputed |

A valid run is **0 / 0 / 0** over all shots. Then `eval_circuit` writes `score.json` and an `OK` row in `results.tsv`. Otherwise it records `FAIL` with the first failure reason, such as `CLASSICAL MISMATCH shot …`, `PHASE GARBAGE …` or `ANCILLA GARBAGE: qubit …`.

**Promotion.** Submissions go through the `ecdsafail` CLI. Each one is benchmarked; the `.github/workflows/benchmark.yml` workflow also rejects edits outside `src/point_add/`. A valid run is promoted only if it beats the current best, and the promoted tree is committed to `main`. The 2 Oct leaderboard snapshot (`data/leaderboard-2026-10-02.tsv`) has 557 `promoted`, 558 `rejected`, 225 `failed`, 4 `promotion failed` and 3 `cancelled` rows. The commit subject is `Accept submission <uuid>` up to 3 August and `Validate submission <uuid>` from 6 August. The switch comes right after the benchmark moved to a GitHub Actions workflow (3 Aug). Both kinds are accepted, scored submissions.

**`DUMMY_TOFFOLIS` bootstrap.** Just before launch, the maintainers' `dummy` commit (`33aa00d`, 28 May) appended N pairs of identical `CCX(tx[0], ty[0], c)` gates on a fresh ancilla. Each pair cancels, so the function is unchanged, but each pair adds 2 executed Toffoli. The default was 10,000 pairs (+20,000 Toffoli). The first accepted submissions changed only this number, which exercised the submit/promote pipeline. `6f7c159` (10,000 → 9,000 pairs) scored −2,000 × 2,715 = −5,430,000. `ed34c00` (9,000 → 8,690) scored −1,683,300. The maintainers twice put it back to 10,000 before the first scored commit (`db48f66` "reset dummy", then `e8ce2c9`), and the knob was removed in `cddd5df` (2 Jun). This padding explains the anchor numbers. The challenge README quotes 3,942,753 Toffoli for the starting circuit, which is unpadded. The paper quotes 3,960,753 (arXiv v2, §“Correctness, Verification, and Scoring”, “Anchors”), which is the 9,000-pair point. The paper's audit counts three submissions that changed only the padding (Supplemental Note B, “Distinguishing gate removal from re-sampling”). Supplemental Note C lists them as `6f7c159`, `ed34c00` and `f43a73e` under “DUMMY_TOFFOLIS padding change”, with leaderboard Δ 0, −1,683,300 and −47,186,700. Its Δ for `6f7c159` is 0 because that was the first scored row, not the −5,430,000 computed above against the 10,000-pair default.

## Why it is (or is not) exact

Validation is a **fixed sample, not a proof**. Passing means the circuit is right on the 9,024 inputs (and measurement outcomes) its own hash selects. Many frontier circuits are approximate on purpose. Truncated comparators, fold windows and walk widths fail on rare inputs, so passing depends on the draw. See [nonce-island-and-lambda.md](nonce-island-and-lambda.md).

Two caveats where sources disagree:

- The challenge README says `sim.rs` asserts each freed qubit is |0⟩ and that a forward∘reverse identity is checked. The current `eval_circuit.rs` and `sim.rs` do neither. An earlier draft's methods section confirmed this: the ancilla test is a final-state check, and dirty resets are caught only *statistically*, through the randomized phase channel. arXiv v2 dropped that section. Its channel table (§“Correctness, Verification, and Scoring”) says only that `anc` checks that all scratch and non-output registers return to |0⟩. On a given shot, a dirty reset has a 50% chance of producing no phase signal.
- The ancilla channel is reported, but practitioner notes find it is essentially never the binding one on modern routes. The live constraints are `cls` and `pha`.

## Knobs and names you will see in commits

- `ops.bin` — the serialized op stream, zstd-compressed since 22 Jun (`c66c958`).
- `eval_circuit` / `build_circuit` — the trusted evaluator / the untrusted builder.
- `NUM_TESTS = 9024`, `BATCH = 64` — the size of the test set and of each simulator batch.
- `0/0/0` — clean on classical / phase / ancilla.
- `avg executed Toffoli`, `qubits` — the two factors printed by `eval_circuit`.
- `Hmr`, `R`, `PushCondition`/`PopCondition` — the ops that make Toffoli execution data- and measurement-dependent.
- `DUMMY_TOFFOLIS` — the bootstrap padding knob (May–June only).
- `promoted` / `rejected` / `failed` — leaderboard statuses. `rejected` is the CLI's term for a submission that did not beat the current best.
- `Accept submission` / `Validate submission` — the subjects of promoted commits before and after early August.

## How optimizations use it

- **Measured uncompute** lowers the *average* without changing static gate counts much. The Toffoli-class work moves under a measurement condition, so it runs on only part of the shots: [`5b834ba`](../commits/5b834ba.md).
- **Verifier Search / nonce rerolls** change only the identity tail. The score still moves a few Toffoli, because the average is over a different sample: [`cf5aa02`](../commits/cf5aa02.md) (−5 T), [`ffc4e07`](../commits/ffc4e07.md) (−9 T), [`11f5d9a`](../commits/11f5d9a.md) (−24 T vs `f3b2f1f`; −15 T vs the frontier at the time, the reroll `ffc4e07`).
- **Dead-gate strips** delete gates a census never saw fire. They are scored only because the validation sample happens to avoid the rare inputs where those gates matter: [`3701581`](../commits/3701581.md).
- **Budget retunes** buy fewer Toffoli with more qubits, and they pay whenever the product drops: [`d9ef3e9`](../commits/d9ef3e9.md).

## Config layering pitfall

The grader runs `build_circuit` with no environment variables. Every knob therefore has to be baked into `src/point_add/mod.rs`, and almost all of them are baked through one helper:

```rust
fn set_default_env(name: &str, value: &str) {
    if std::env::var_os(name).is_none() { std::env::set_var(name, value); }
}
```

This is **first-wins**. The first call for a name fixes its value, and every later `set_default_env` of the same name does nothing. `configure_ecdsafail_submission_route()` (the dialog route of June) and the trailmix `build()` accumulated stacked blocks of defaults, one per earlier operating point. The same knob therefore often appears two or three times. Editing a later copy has no effect. Adding a new line above the existing ones silently overrides them. A diff can look like a tightening while it does nothing, or look neutral while it reverts someone else's cut.

- [`1caf521`](../commits/1caf521.md) narrowed `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` from 19 to 18 and set `DIALOG_GCD_WIDTH_SLOPE_X1000` from 1015 to 1017. Both knobs are set twice, and it edited both copies each time, so both changes took effect.
- The next commit, [`ba3efc1`](../commits/ba3efc1.md), added `…=19` and `…=1015` as new first lines of `configure_ecdsafail_submission_route()`. The parent's 18 and 1017 lines are still in the file, now dead. This undid both of `1caf521`'s cuts. Its net is −711 T against the parent. Against [`35ceb01`](../commits/35ceb01.md), which has the same two settings, its own bit-0 change is worth −2,055 T.
- [`35ceb01`](../commits/35ceb01.md) added a first line `DIALOG_GCD_FOLD_CARRY_TRUNC_W = "18"` and changed the in-block copy to `"17"`. The effective window is 18.
- The trailmix era has the same pattern:
  - [`31421df`](../commits/31421df.md) calls `configure_q1162_rebased_ffg1_route()` at the top of `build()` so that its trims win.
  - At [`31f9c58`](../commits/31f9c58.md), `TLM_TARGET_Q` is set to 1153 and again to 1155 later in the code. Only the first is live, and the forced `set_var("TLM_TARGET_Q", "1149")` at the top of `build()` overrides both.
- **Dead functions.** From [`bdb1d22`](../commits/bdb1d22.md) on, `build()` never reaches `configure_ecdsafail_submission_route()`. Nonce and knob edits made there afterwards, as in [`bc2334a`](../commits/bc2334a.md) and [`764afda`](../commits/764afda.md), are dead.
- **The caller's shell wins over every default.** A stray `DIALOG_*`, `TLM_*` or `LUD_*` variable silently changes the circuit, and with it the Fiat–Shamir draw. [`c9c03de`](../commits/c9c03de.md) and `31f9c58` switch to `std::env::set_var` for exactly this reason.

**How to check.** Before you trust a knob's value, grep every `set_default_env`/`set_var` of that name. Work out the call order from `build()`, which is not the same as the line order in the file. Then reproduce in a clean environment.

## Related concepts

- [nonce-island-and-lambda.md](nonce-island-and-lambda.md) — how the 9,024-shot sample is chosen and what failing it costs
- [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) — the Q factor
- [measurement-uncompute.md](measurement-uncompute.md) — where measurement-conditioned Toffoli come from
- [dead-gate-strip.md](dead-gate-strip.md), [comparator-and-width-truncation.md](comparator-and-width-truncation.md) — the approximate levers validation has to tolerate
