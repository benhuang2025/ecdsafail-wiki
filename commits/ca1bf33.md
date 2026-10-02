# ca1bf33 — Bootstrap: after the organisers' reset, cut DUMMY_TOFFOLIS from 10,000 to 9,000 again (unscored)

| | |
| --- | --- |
| Contestant | unknown (bootstrap submission) |
| Date | 2026-05-30 |
| Submission | `90ea031` (not on the leaderboard) |
| Commit | `ca1bf336d447abfc9f7e581db7f4a938711e969d` |
| Result | unscored (bootstrap). The identical tree was scored later as [`6f7c159`](6f7c159.md): 2715 qubits × 3,960,753 Toffoli = 10,753,444,395 |
| Base | [`c55911f`](c55911f.md), an unscored bootstrap commit whose `src/point_add` is identical to this one. Its tree was scored as [`6f7c159`](6f7c159.md): 2715 × 3,960,753 = 10,753,444,395 |
| Change vs base | none (identical tree). Against the git parent `db48f66` (10,000 units): qubits ±0, Toffoli −2,000, score −5,430,000 by construction |
| Leaderboard Δ | none (unscored) |
| Family | Unscored bootstrap (DUMMY_TOFFOLIS) → unscored bootstrap |
| Concepts | [scoring-and-validation](../concepts/scoring-and-validation.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [kaliski-almost-inverse](../concepts/kaliski-almost-inverse.md) |
| Reproduce tier | **A**: no patch is needed; the base tree is already identical |

## Summary

The fourth and last bootstrap commit. After the three earlier bootstrap
commits had walked the `DUMMY_TOFFOLIS` padding down to 7,500, the organisers
put it back to 10,000 in `db48f66` ("reset dummy"). This commit lowers it
from 10,000 to 9,000 again, which reproduces [`c55911f`](c55911f.md)
exactly. Removing 1,000 self-cancelling Toffoli pairs removes 2,000 executed
Toffoli per shot and changes nothing else. It was accepted but not scored.

## What changed and why it saves Toffoli

- `src/point_add/mod.rs`, `build()`: against the git parent `db48f66`, the
  default of `DUMMY_TOFFOLIS` goes from `10_000` to `9_000`. Against the base
  `c55911f` nothing changes.
- The block runs `n` times `ccx(tx[0], ty[0], c); ccx(tx[0], ty[0], c)` on a
  fresh ancilla `c` after the point addition is finished. Each pair is the
  identity, because CCX is self-inverse, but the simulator charges both gates
  on every shot. One unit costs exactly 2 average Toffoli and no qubit. The
  code is quoted in [`c55911f`](c55911f.md). See
  [scoring-and-validation](../concepts/scoring-and-validation.md) and
  [dead-gate-strip](../concepts/dead-gate-strip.md).

## Why it is still correct, and what it risks

The change is exact: only the number of identity pairs differs from the
parent. The tree is byte-identical to `c55911f`, so the op stream and its
Fiat–Shamir test draw are the same as that commit's (and as
[`6f7c159`](6f7c159.md)'s, which was scored with 0 classical, 0 phase and
0 ancilla failures). There is no tail nonce in this era.

## Classification rationale

One of the four pre-leaderboard padding commits, filed in their own
"Unscored bootstrap" group. Scored, it would be a "DUMMY_TOFFOLIS padding
change" under Neutral / Mechanical, exactly like [`6f7c159`](6f7c159.md),
which made the same edit on top of the next organiser commit.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout c55911f -- src/point_add`.
   - `git diff --ignore-cr-at-eol c55911f ca1bf33 -- src/point_add` is empty,
     so no patch is needed.
   - Do not start from the git parent `db48f66`. That is the organisers'
     "reset dummy" commit, which put the padding back to 10,000. Against it
     the diff is the 2-line change `10_000` → `9_000`.
2. **No patch to apply.** The base tree is already the commit's tree.
3. **Check the tree.** `git diff --ignore-cr-at-eol ca1bf33 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DUMMY_TOFFOLIS` or other environment overrides set. The commit was never
   scored. The same tree, scored as [`6f7c159`](6f7c159.md), gives:
   - 2715 qubits
   - 3,960,753 average Toffoli (rounded)
   - score 10,753,444,395
   - 0 classical, 0 phase and 0 ancilla failures

There is no tail nonce in this era. The 9,024 test inputs are a hash of the
op stream, so the score only reproduces with an identical op stream.

### Patch

None. The diff against the base `c55911f` is empty.
