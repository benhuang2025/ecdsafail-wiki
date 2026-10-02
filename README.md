# EcdsafailWiki

Per-commit analysis of every accepted source commit in the ECDSA.Fail
competition, the concept pages that explain the recurring mechanisms, and the
census table built from them.

Snapshot: **561 accepted commits (#883–1459), 29 May – 2 October 2026. Every
commit has a note**, written from its diff on 2026-10-01/02 and checked with
`check_reproduce.py`.
- The family labels of the first 404 commits, through 18 July, come from the
  paper's census and are kept as published. Where a note's diff audit
  disagrees with the published label, the note's "Classification rationale"
  says so.
- The 157 commits after 18 July were classified during this audit.

## Start here

- To understand one commit, open `commits/<hash>.md`. Each note explains what
  the optimization is and why it still works. It ends with a Reproduce
  appendix: the base to start from and the exact patch. The 35 nonce-only
  commits make no optimization, so their notes use a short format (see
  [NOTE_FORMAT.md](NOTE_FORMAT.md)): one paragraph and the patch.
- For background, read `concepts/`. There are 17 pages, listed below.
- To write or check a note, read [NOTE_FORMAT.md](NOTE_FORMAT.md).
- **Fact-checked 2026-10-02.** Header numbers, dates, contestants, bases and hashes
  were machine-checked against the leaderboard and git. Every full-format note's
  prose was re-read against its patch and the code, which corrected about 150
  notes. Every concept page was checked the same way, which corrected about 45
  claims. Claims that only a submission note supports are labelled as the
  author's.

## Layout

| Path | What it is |
| --- | --- |
| `commits/<hash>.md` | One note per accepted commit, 561 in all. Format: [NOTE_FORMAT.md](NOTE_FORMAT.md). |
| `concepts/*.md` | 17 concept pages. Commit notes link to them. |
| `accepted-commit-census.tex` | **Generated.** The extended census ledger, 561 rows. It follows Supplemental Note C (`ecdsafail-supplemental-materials/appendices/tex/appendix-C-content.tex`), the ledger that arXiv v2 cites, and keeps its cross-references (`M:fig:family-census-tree`, Supplemental Note B). |
| `sources/supplemental-note-C-2026-08-28.tex` | Frozen copy of Supplemental Note C as of supplemental-materials commit `945c2d2` (28 Aug). Its 404 rows are identical to the census in arXiv v2 (`arXiv-2609.09582v2/unused/09-appendix-census-of-source-commits.tex`) and in the older `ecdsafail2` draft. |
| `data/census.tsv` | The 404 original rows, parsed from the frozen tex. |
| `data/new-classification.tsv` | Family, change-type and a one-line summary for each of the 157 commits after 18 July. |
| `data/bases.tsv` | The base each note rebuilds from. It is often not the git parent. |
| `data/leaderboard-<date>.tsv` | Snapshot of `ecdsafail submissions --all`, all statuses. |
| `tools/` | Scripts, listed below. |

### Concept pages

| Group | Pages |
| --- | --- |
| Basics | [scoring-and-validation](concepts/scoring-and-validation.md), [nonce-island-and-lambda](concepts/nonce-island-and-lambda.md), [peak-qubits-and-budgets](concepts/peak-qubits-and-budgets.md) |
| Inversion architectures | [kaliski-almost-inverse](concepts/kaliski-almost-inverse.md) (29 May – 2 Jun), [dialog-gcd-early](concepts/dialog-gcd-early.md) (2 – 19 Jun), [trailmix-jump-gcd](concepts/trailmix-jump-gcd.md) (19 Jun – 21 Aug), [pingpong-division](concepts/pingpong-division.md) (21 Aug – 29 Sep), [skywalk-gcd](concepts/skywalk-gcd.md) (from 29 Sep) |
| Era machinery | [transcript-codecs](concepts/transcript-codecs.md) (June transcript packing), [trailmix-schedules-and-reserves](concepts/trailmix-schedules-and-reserves.md) (trailmix tables and qubit reserves) |
| Arithmetic | [adders-and-carries](concepts/adders-and-carries.md), [comparator-and-width-truncation](concepts/comparator-and-width-truncation.md), [modular-fold](concepts/modular-fold.md), [squaring-and-karatsuba](concepts/squaring-and-karatsuba.md) |
| Qubits and gates | [measurement-uncompute](concepts/measurement-uncompute.md), [venting-and-wire-loans](concepts/venting-and-wire-loans.md), [dead-gate-strip](concepts/dead-gate-strip.md) |

### Tools

| Script | Does |
| --- | --- |
| `insert_patch.py <hash> <base> [paths]` | Writes the exact git diff into a note's `### Patch`. Patches are never typed by hand. |
| `render_patch.py` | Prints that diff; used by `insert_patch.py`. |
| `check_reproduce.py <hash>…` or `--all` | Exports the base without git history, follows the note's steps, and compares the result with the commit's `src/point_add`. Prints PASS or the differing files. |
| `parse_census.py`, `snapshot_leaderboard.py`, `build_census.py` | Rebuild the census table, below. |

## Setup

The tools read diffs from a clone of the competition repository. By default
they look for `../ecdsafail-challenge` next to this wiki. Set
`ECDSAFAIL_CHALLENGE_REPO` to use another path:

```sh
git clone https://github.com/ecdsafail/ecdsafail-challenge ../ecdsafail-challenge
python3 tools/check_reproduce.py --all   # every note should print PASS
```

`snapshot_leaderboard.py` also needs the `ecdsafail` CLI
(https://www.ecdsa.fail).

## Rebuilding the table

```sh
python3 tools/parse_census.py         # sources/supplemental-note-C-2026-08-28.tex -> data/census.tsv
python3 tools/snapshot_leaderboard.py # ecdsafail CLI -> data/leaderboard-<today>.tsv
python3 tools/build_census.py         # -> accepted-commit-census.tex
```

`build_census.py` reads the newest leaderboard snapshot. Dates and commit
indices come from git in the competition clone. Run `git fetch origin main`
there first.

## Extending to a later date

1. Run `git -C ../ecdsafail-challenge fetch origin main`, then list the
   accepted commits that are not yet in the table. Their subjects are
   `Accept submission …` up to 3 August and `Validate submission …` from
   6 August.
2. Take a fresh leaderboard snapshot. Every accepted commit should match one
   `promoted` row by its 7-character `commit`.
3. For each new commit:
   - Pick its base: the earlier accepted commit whose `src/point_add` differs
     least. Add it to `data/bases.tsv`.
   - Write `commits/<hash>.md` following [NOTE_FORMAT.md](NOTE_FORMAT.md). Use
     the short format if the commit only re-rolls the nonce.
   - Run `check_reproduce.py` until it prints PASS.
   - Add a row to `data/new-classification.tsv`.
4. Rebuild the table.

## Classification rules

- The family is decided by the actual diff against the commit's real base,
  not by the commit subject or the submission note. Both are often wrong:
  several notes say "nonce only" for diffs that change the circuit (e.g.
  `330d42d`, `2dabd9d`).
- **The git parent is often not the author's base.** Many submissions were
  cut from an older tree, so a diff against the parent also reverts a rival's
  change. Many errors in the first draft of the notes came from exactly this.
- Some trees use CRLF line endings. Read diffs with `--ignore-cr-at-eol`, and
  apply patches with `git apply --ignore-whitespace`.
- The primary family is the lever that produces most of the score change.
  For bundled commits, see the "Classification rationale" in each note.

### Taxonomy changes made in the extension

- New change-type **Algorithmic Substitution → inversion/division algorithm
  swap**:
  - `897dda2`: ping-pong fixed-depth division replaces the GCD inverse,
    Δ −218,966,453, the largest delta in the extension.
  - `8ee337c`: GCD Skywalk, 1250 → 1174 qubits.
- New change-type **Uncompute Strategy → deferred coherent uncompute**:
  `b788efc` keeps the carries alive until the inverse pass.
- Peak-budget or vent-cap retunes, which trade qubits against Toffoli, are
  filed under **ancilla-lifetime / venting**. Examples are `f5ff95b`,
  `d9ef3e9` and `79e7afa`. `79e7afa` was moved there from iteration/threshold
  tuning after the re-audit.

### Borderline calls worth a second look

- `787eaa8`: fold window vs chunk compare.
- `9805dee` / `33e2b34`: dead-low carry elision, Dead-Code vs Constant
  Propagation.
- `0642f52`: SAT-proven CCX→CX rows.
- `800ba12`.
- `cc7f10e`, `d919bc6`, `5a08ebd`, `82c849b`, `a231a39`: multi-lever bundles.
- `16351d8` and `8e62c01`: merges whose family depends on which base they are
  measured against.

## Differences from the original census

- 10 rows that said `unknown` now carry the contestant's name from the
  leaderboard. The 4 unscored bootstrap rows stay `unknown`.
- Scores and Δ for the original 404 rows are kept as published, from the
  2 July ledger. The 2 October leaderboard snapshot differs on four Δ values:
  - `6bf73fe` is now 0 instead of −17,461,520.
  - `422f21d` is now 0 instead of −50,073,984.
  - `6f7c159` is now −5,430,000 instead of 0.
  - `f37a0bc` is now +3,724,105 instead of −3,734,577, measured against
    `a6a92a4`, which was promoted a minute later.
- The generated intro follows Note C's wording, including its corrected
  paragraph on the largest deltas (`d19dbb5`, then `cddd5df`). It adds the
  largest delta after the census interval (`897dda2`). Note C's draft
  comments (`\benhuang{}`, `\jieyi{}`) are left out.
