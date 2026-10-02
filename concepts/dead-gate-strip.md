# Dead-gate stripping and exact peepholes

> The scorer charges every Toffoli whose classical condition is true, even if its two quantum controls are never both 1. A gate like that is paid for but does nothing. A whole class of optimizations deletes such gates after the circuit has been built. Some look for exact facts: a gate followed by its own inverse, a control that is provably constant, or a product that equals a linear combination of other wires. Others run the circuit on hundreds of millions of random inputs and delete gates that were never seen to fire. The two kinds look the same in a diff, but they are not the same in correctness. Exact removals change nothing on any input. Empirical removals are bets, priced in extra hard inputs that the nonce hunt has to avoid.

## How it works in this circuit

**Why dead gates cost anything.** In `src/sim.rs`, a `CCX`/`CCZ` adds `cond.count_ones()` to the Toffoli tally before it looks at its controls. A CCX that never fires is therefore charged in full. The deletions below all run as post-passes over the finished op stream in `build()` (`src/point_add/mod.rs`), after the circuit is emitted and before the nonce tail is appended.

### Exact removals

- **Self-inverse pairs.** `CCX(a,b→t) … CCX(a,b→t)`, under the same classical condition, with nothing writing `a` or `b` and nothing reading or writing `t` in between, is the identity (`find_inverse_pairs` checks both the last write and the last read of `t`). The trailmix-era `constprop.rs::find_inverse_pairs`, `ccz_straddle_cancel` and `ccx_final_cancel` ([`3f8ce09`](../commits/3f8ce09.md); off by default, since nothing sets `TLM_CCX_FINAL_CANCEL`) cancel such pairs. `constprop.rs` also tracked each wire as {0, 1, unknown}, plus affine relations. With that it dropped a CCX that has a known-0 control or complementary controls, and turned a CCX into a CX when a control is known 1 or the two controls are equal.
- **Exact simplifier chain.** At the current frontier, `build()` runs `PP_SIMPLIFY = product,affine,quadratic,truth` and then `interned_witness::witnesses`. `simplify_products`, `affine_simplify`, `quadratic_simplify` and `truth_simplify` each re-derive Boolean support facts from the stream itself. Their headers describe them as "exact CCX support identities", using small truth tables or affine/quadratic forms over immutable atoms. They drop or weaken a CCX only when they can prove it redundant. Re-running passes after the witness pass exposes more of these. [`c8da745`](../commits/c8da745.md) (27 Sep) re-runs all four simplifier passes there; [`17bc487`](../commits/17bc487.md), on another line, re-runs only `simplify_products`.
- **Affine-bridge peepholes.** A hard-coded window such as `CCX(511,898→735); CX…; CCX(511,898→735)` is spliced into an equivalent 3-op form with one CCX. The splice is fail-closed: it asserts a unique match ([`9aceb7d`](../commits/9aceb7d.md), [`9b2ce61`](../commits/9b2ce61.md)).
- **Target-fanout closure.** `single_ccx_fanout::rewrite_first_target_fanout` uses the identity `CCX(a,b→t); CX(t→u); CCX(a,b→t) = CX(t→u); CCX(a,b→u)` and loops until no match is left. A strip exposes new matches, so the loop is re-run after it ("post-strip closure", [`7936360`](../commits/7936360.md), [`266b783`](../commits/266b783.md)). The census files it under **Fusion**, because two Toffolis merge into one.
- **SAT-proven CCX→CX rows.** An offline SAT solver proves that a specific CCX's product equals a fixed XOR of other wires, plus an optional constant, at that point in the stream. The row (`widx c1 c2 t cst w1,w2,…`) replaces that CCX with a CX chain. Rows are matched by a unique global shift, which is asserted ([`0642f52`](../commits/0642f52.md); the frontier ships `sky12_rewrite.txt`). The census files these under **Constant Propagation → host-derived**, since the fact is derived on the host. The build only checks that each row still names the same CCX. It does not re-check the proof.
- **Dead-low carries** ([`33e2b34`](../commits/33e2b34.md), [`9805dee`](../commits/9805dee.md)) and an unread carry-out ([`258b25f`](../commits/258b25f.md)) remove provably zero or unused carry work at the source level, not as a post-pass.

### Empirical (census) removals

A **fire census** simulates the composed stream on many random secp256k1 input pairs. Early strips used 1e8 inputs, and [`a254a8a`](../commits/a254a8a.md) re-mined at 1e9. From [`6e9f0af`](../commits/6e9f0af.md) on, each candidate is also priced on an independent 320M-input oracle census. For each CCX/CCZ the census records whether it ever fired, and whether one control was ever 0 while the other was 1. Gates that never fired go into `DEAD_KEYS` and are deleted. Gates whose second control looked implied by the first go into `DOWNGRADE_KEYS` (from [`a254a8a`](../commits/a254a8a.md)) and become CX/CZ (`act` 1 or 2 says which control survives).

- **Positional strips** (`M60`, `D2_DEEP_STRIP`, `dead_*.idx`, the `route_042_action_mask.tsv` of [`31f9c58`](../commits/31f9c58.md)) list op indices. Any upstream edit shifts the indices and the strip deletes live gates. The skill docs record a resulting "classical 9024" failure, and the advice to turn the strip off while experimenting.
- **Identity-keyed deep strip** ([`d484caa`](../commits/d484caa.md), `apply_deep_strip_identity`). Keys are `(kind, q_control2, q_control1, q_target, c_condition, ordinal)`, where the ordinal is the k-th occurrence of that operand tuple. From [`a254a8a`](../commits/a254a8a.md) on, each key also carries `tuple_occupancy`. A key whose tuple count has changed since the census is *discarded*, not applied. The code comment says the guard was added after a mis-addressed key once caused 7535/9024 classical mismatches. The same commit retires 19 census-keyed families at ITERS 261 through `drops_off_family`, because the extra divsteps renumber their keys.
- **Risk budget and admission rules.** The 6e9f0af note argues that census depth is the wrong dial. Its approach is to price each candidate on an independent oracle census and admit candidates in ascending risk until a budget is spent. The note measures Δλ ≈ 0.77 × budget, with budget 0.5 at +0.363 λ for 13,735 keys. Later re-mines change only the rule or the budget: union-of-failure-sets pricing ([`ed4b529`](../commits/ed4b529.md)), true greedy ([`258b25f`](../commits/258b25f.md)), `NO_EVENT_CAP` ([`3701581`](../commits/3701581.md)), joint classical+phase pricing ([`892b03b`](../commits/892b03b.md)), and risk steps to 2.5 and 3.0 ([`7726431`](../commits/7726431.md), [`5265674`](../commits/5265674.md)).
- **Cascade** ([`f735fd7`](../commits/f735fd7.md)). Some identical pairs are blocked: exactly one unconditional CCX writes a control between them. Cancelling such a pair leaves a residual `t ^= s·c·d`, which is accepted if the triple is on a measured allow-list (it almost never fires). Eleven such roots unblocked 144 more exact pairs, for −308 T at about +0.49 λ.
- **Hand-made reachability claims**, such as the codec normalizer CCX→CX ([`330d42d`](../commits/330d42d.md), "valid where w10=1 implies w6=1") or the near-identity route skip `HEO_MB_SKIP2` ([`800ba12`](../commits/800ba12.md)).

## Why it is (or is not) exact

An exact removal leaves the circuit's function unchanged on every input. It still changes the op stream, so the Fiat–Shamir seed changes and the island is re-rolled. The baked nonce has to be re-hunted, but at the base rate of hard inputs.

An empirical removal is only as good as the census. If a deleted gate would have fired on some input, the output on that input is wrong, or a phase is left behind. Each such input is a new *hard input*. The 9,024 validation inputs are drawn from a SHAKE256 hash of the op stream, so the submission passes only if the nonce picks an island that avoids every hard input (see [nonce-island-and-lambda.md](nonce-island-and-lambda.md)). The risk budget amounts to spending λ, the expected number of failing shots, on Toffoli savings. The return falls off: about 6.5M score per unit λ at first, below 1M later (6e9f0af note). A strip that passes validation is a "validator-clean" circuit in the paper's terms (Supplemental Note A, “Evidential status and selection scope”; the earlier draft said "evaluator-clean"), not proven, and the skill docs warn never to treat a sampled "never fires" result as value-exact. Census tables and SAT rows are also tied to one stream. Upstream edits make them stale ([`5b834ba`](../commits/5b834ba.md) switched D2 off; [`800ba12`](../commits/800ba12.md) dropped SAT rows that no longer matched), and their savings are lost until the table is mined again.

Status as of 1 October 2026: the frontier `build()` (84e78ce) has no census strip. It runs only the exact simplifier chain, the witness pass, the exact `mabsorb` measurement-absorption pass (`HEO_MABSORB=1`) and the SAT rows.

## Knobs and names you will see in commits

- `DEAD_KEYS` / `DOWNGRADE_KEYS`, `apply_deep_strip_identity`, `tuple_occupancy` — the identity-keyed strip.
- `D2_DEEP_STRIP`, `M60`, `dead_*.idx`, `SUB4_APPLY_STRIP`, `DROP_DEAD_ROBUST_DISABLE` — positional strips and their switches.
- "risk budget", "union / joint admission", "true greedy", `NO_EVENT_CAP` — admission rules for census keys.
- `find_inverse_pairs`, `DEFAULT_CASCADE_TRIPLES`, `CONSTPROP_VERIFY` — trailmix-era exact and cascade passes.
- `PP_SIMPLIFY`, `simplify_products`, `interned_witness` — the frontier's exact chain.
- `single_ccx_fanout` — the Fusion rewrite; `SKY_REWRITE` — SAT-proven rows.

## How optimizations use it

In the extension census, *dead-gate/self-inverse removal* (Dead-Code family) has 18 commits. Most are strip re-mines; the rest are a few exact peepholes. The fanout closure appears as *gate/op fusion*, and the SAT rows and dead-low carries as *host-derived / classical specialization*.

- [`d484caa`](../commits/d484caa.md) — first identity-keyed deep strip: 1,442 gates, −1,309 T.
- [`6e9f0af`](../commits/6e9f0af.md) — risk-ranked admission, 13,735 keys.
- [`f735fd7`](../commits/f735fd7.md) — cascade cancellation of blocked pairs.
- [`9aceb7d`](../commits/9aceb7d.md) — exact 7→3 affine bridge, −1 T per shot.
- [`7936360`](../commits/7936360.md) — post-strip fanout closure (Fusion).
- [`0642f52`](../commits/0642f52.md) — 11 more SAT CCX→CX rows.

## Related concepts

[nonce-island-and-lambda.md](nonce-island-and-lambda.md) (how empirical removals are paid for), [scoring-and-validation.md](scoring-and-validation.md) (executed vs. emitted Toffoli), [comparator-and-width-truncation.md](comparator-and-width-truncation.md) (the other big island-exact lever), [measurement-uncompute.md](measurement-uncompute.md), [adders-and-carries.md](adders-and-carries.md), [venting-and-wire-loans.md](venting-and-wire-loans.md).
