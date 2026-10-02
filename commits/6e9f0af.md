# 6e9f0af — Re-select the dead-gate strip by per-gate risk against a λ budget instead of by census depth (11,480 → 13,735 keys)

| | |
| --- | --- |
| Contestant | gopikannappan |
| Date | 2026-07-27 |
| Submission | `4c5a972` |
| Commit | `6e9f0af126557eb345fdbcc7ae733f71db5ba206` |
| Result | 1154 qubits × 1,292,286 Toffoli = **1,491,298,044** |
| Base | `d9ef3e9` (the author's previous submission `8233cd7`): 1154 qubits × 1,294,287 Toffoli = 1,493,607,198 |
| Change vs base | qubits ±0, Toffoli −2,001, score −2,309,154 |
| Leaderboard Δ | −1,702,020, measured against the frontier at the time, `b978905` (Gajesh2007, 1152 × 1,296,007), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [scoring-and-validation](../concepts/scoring-and-validation.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the regenerated key table `deep_strip_keys.rs` is copied from the commit; the patch covers `mod.rs` |

## Summary

The circuit is d9ef3e9's, unchanged. Only the dead-gate strip table and the
nonce are new. Until now, strip tables were chosen by census depth: run N
random inputs and strip every gate that never fired. A deeper census is safer
but strips less. The author shows that this is a smooth trade with no cliff.
The expected number of failing shots added by the strip (Δλ) falls as a power
of depth, from +20.6 at 2M inputs to +0.007 at 256M.

The new idea is to drop the single depth threshold. Each candidate gate is
priced by how often it misbehaved on an independent 320M-input "oracle"
census. Gates are then admitted from the safest up, until a risk budget is
spent. At the same measured residual this saves 30–35% more Toffoli than any
depth cut. The commit ships budget 0.5: 13,735 keys (10,684 deletions and 3,051
CX/CZ downgrades) for a measured Δλ of +0.363. That is −2,001 average Toffoli
at the same 1154 qubits.

## What changed and why it saves Toffoli

- **`src/point_add/deep_strip_keys.rs`, regenerated.**
  - The census is 320,000,000 input pairs on the pre-strip stream (9,073,163
    ops, 1,361,613 CCX+CCZ). It gives 10,684 `DEAD_KEYS` and 3,051
    `DOWNGRADE_KEYS`, against 9,324 + 2,156 in the base.
  - The key format is unchanged: `(kind, c2, c1, target, condition, ordinal,
    tuple_occupancy)`, plus `act` for downgrades. `apply_deep_strip_identity`
    is unchanged.
  - The build logs "removed 10684 / 10684 dead; downgraded 3051 / 3051 to
    CX/CZ; 0 stale keys skipped".
- **How the keys were chosen** (from the note):
  1. Deleting a gate and downgrading it to CX/CZ (either `act`) save the same
     Toffoli. Candidates differ only in how often they would have been wrong.
  2. The census counts, per gate, how many "wrong events" it saw (a fire for a
     deletion, a control disagreement for a downgrade), not just whether any
     happened.
  3. Each candidate is priced on an independent 320M-shot oracle, disjoint
     from the census.
  4. Candidates are admitted in ascending risk until the budget is spent.
     `budget → Δλ` held at a flat ratio of 0.77 ± 0.02 across two orders of
     magnitude.

  | budget | keys | avg T | Δλ |
  |---|---|---|---|
  | 0.05 | 12,245 | 1,293,600.5 | +0.058 |
  | 0.30 | 13,281 | 1,292,699.9 | +0.233 |
  | **0.50 (shipped)** | **13,735** | **1,292,278.9** | **+0.363** |
  | 1.0 | 14,553 | 1,291,528.9 | +0.885 |
  | 3.0 | 16,466 | 1,289,786.1 | +2.302 |

  The marginal return falls: about 6.5M score per unit of λ below Δλ 0.36,
  about 1.7M from 0.36 to 1.57, and under 1M beyond 2.7.
- **How Δλ was measured.** The stripped and unstripped streams are run on
  identical inputs and identical measurement randomness. The strip only
  removes CCX/CCZ or turns them into CX/CZ, and neither consumes random bytes.
  Every qubit, classical bit and the phase word are compared. Divergences per
  5.12M shots, divided out, give Δλ per 9,024-shot draw.
- **Why it saves Toffoli.** Every stripped or downgraded gate was charged in
  full on each shot whose condition held. See
  [dead-gate-strip](../concepts/dead-gate-strip.md) and
  [scoring-and-validation](../concepts/scoring-and-validation.md).
- **Tail nonce:** `SUB4_TAIL_NONCE` default 30008006160 → 990018471007 in
  `src/point_add/mod.rs`.

## Why it is still correct, and what it risks

- **Empirical, by design.** The admitted gates are not proven dead. At budget
  0.5 the strip adds about 0.36 expected failing shots per draw. A wrong
  deletion or downgrade shows up as a classical mismatch or phase garbage on
  the inputs where that gate matters.
- **A single eval cannot see this.** The note's example: a 4M-depth strip
  scores 19 classical / 9 phase on one eval, indistinguishable from a healthy
  control, while its differential says Δλ = +8.49. Use the differential to
  judge a strip.
- Measured clean density for the shipped stream is 2.54e-8. 90M nonces
  screened on 4 GPUs gave 584 screen survivors and 2 true winners, against
  2.29 expected. The other winner, `990017592439`, scores 1,491,302,660.
- The shipped nonce `990018471007` draws a clean set: 9,024 of 9,024 shots, 0
  classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only change is a larger empirical dead-gate strip, so dead-gate/self-inverse
removal. What is new is the admission rule (risk-ranked, budgeted), not the
mechanism.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout d9ef3e9 -- src/point_add`.
   - Do not start from the git parent `b978905`. That is Gajesh2007's
     staircase tree, and this commit was built on `d9ef3e9`, as the note says.
   - Against the parent, the diff is 15,229 lines. It would remove b978905's
     `tail_narrow_at` / `TLM_TN_SPEC` code, move the schedule tables down by 2
     at 101–260 and raise the caps 1152 → 1154. None of that is this commit's
     work.
   - Against `d9ef3e9`, `git diff --ignore-cr-at-eol d9ef3e9 6e9f0af -- src/point_add`
     is 2,640 lines in 2 files: the key table and the nonce.
2. **Copy the generated table from the commit:**
   `git checkout 6e9f0af -- src/point_add/deep_strip_keys.rs`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
4. **Check the tree.** `git diff --ignore-cr-at-eol 6e9f0af -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `TLM_*` or
   `SUB4_*` overrides set. Expect:
   - 1154 qubits
   - 1,292,286 average Toffoli (1,292,286.126 before rounding)
   - score 1,491,298,044
   - 0 classical, 0 phase and 0 ancilla failures
6. **Nonce caveat.** The score only reproduces with the nonce `990018471007` and an
   identical op stream. Any other change needs a new nonce hunt and a strip
   re-mine.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index b7f6c13..2c1460c 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2377,7 +2377,7 @@ pub fn build() -> Vec<Op> {
     };
     // The tail nonce ground for this composed stream (verified PASS 0/0/0, score 1,517,633,280).
     // SUB4_TAIL_NONCE overrides for re-grinding/seam-export.
-    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(30008006160);
+    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(990018471007);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
```

