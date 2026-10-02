# Commit note format

Every file in `commits/<hash>.md` follows this format. The goal is that an AI
reading only the note, plus the concept pages it links, can understand what
the commit does and rebuild it exactly.

Reference examples:
- [`e5c53dc`](commits/e5c53dc.md): a one-knob change
- [`8d7051b`](commits/8d7051b.md): several knobs, and the base is not the git parent
- [`a9af194`](commits/a9af194.md): a nonce-only change (short format, below)
- [`5526766`](commits/5526766.md): a new mechanism, about 250 lines
- [`897dda2`](commits/897dda2.md): an architecture swap, Tier B

## Sections, in order

The core of every note is sections 4 and 5: what the optimization is and why
it still works. Reproduce and its patch are an appendix at the end.

1. **`# <hash> — <what the change really does>`**. Use the real change in the
   title, not the commit subject.
2. **Header table** with these rows:
   - Contestant, Date, Submission, Commit (full 40-character hash)
   - Result: `Q × T = score`
   - Base, with its own `Q × T = score`
   - Change vs base: ΔQ, ΔT, Δscore
   - Leaderboard Δ, noting when it is measured against a frontier that is not
     the base
   - Family → change-type
   - Concepts: links to `concepts/*.md`
   - Reproduce tier
3. **`## Summary`**: one or two plain paragraphs. Say what changed, why it
   saves Toffoli or qubits, and what it costs.
4. **`## What changed and why it saves …`**: every change, by file and symbol,
   with old → new values. Describe the mechanism in this circuit's own terms
   and link a concept page for the background.
5. **`## Why it is still correct, and what it risks`**:
   - Which parts are exact, and which are probabilistic and why.
   - Which validation channel (classical, phase or ancilla) would catch a
     failure.
   - That the shipped nonce draws a clean set.
6. **`## Classification rationale`**: why this family and change-type, and
   what the runner-up was if the call was close.
7. **`## Reproduce`** (appendix, always the last section), numbered steps:
   1. Start: `git checkout <base> -- src/point_add`. Explain why this base, and
      if the git parent differs, say what diffing against the parent would
      wrongly show.
   2. Tier B only: `git checkout <hash> -- <paths>` for files that are too
      large to inline or are generated, with what they are.
   3. Apply the patch with `git apply --ignore-whitespace`. Some trees use
      CRLF line endings, and the patch is LF.
   4. Check: `git diff --ignore-cr-at-eol <hash> -- src/point_add` prints nothing.
   5. Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`, `TLM_*`, `PP_*` or
      `HEO_*` overrides set. List the expected qubits, average Toffoli, score
      and 0 / 0 / 0 failures.
   6. Nonce caveat: the score only reproduces with an identical op stream.
8. **`### Patch`**, inside Reproduce at the very end: the exact diff from git.
   **Never type it by hand.** Insert it with
   `python3 tools/insert_patch.py <hash> <base> [paths…]`. Deleted files are
   not inlined. The tool writes an `rm` command above the diff instead.

## Short format for nonce-only commits

A commit whose diff against its base changes only the tail nonce, or in the
pre-tail-nonce era only a reroll count such as `DIALOG_REROLL` or `KAL_REROLL`,
makes no optimization. It gets a short note instead of the full format.
Comment-only edits, line-ending churn and uncompiled backup files do not count
as changes. Example: [`a9af194`](commits/a9af194.md).

1. **`# <hash> — Nonce re-roll only (no circuit change)`.** In the pre-nonce
   era, use "Reroll only" and name the knob.
2. **Header table**, six rows:
   - Contestant · Date (with the submission)
   - Commit (full hash)
   - Result (`Q × T = score`, with Δ)
   - Base (the same circuit)
   - Family
   - Concepts (link `nonce-island-and-lambda`)
3. **`## Summary`**, one paragraph:
   - Start with "This commit makes no optimization."
   - Give the file, symbol and old → new value.
   - Say how much the average Toffoli moved on the new clean draw.
   - Give the evidence that it is nonce-only: the diff touches only that
     literal, the op count is unchanged, any extra files are inert.
   - Link the concept page instead of re-explaining why a nonce moves the
     score.
4. **`## Reproduce`**: one or two sentences giving the base checkout, any copy
   step, `git apply --ignore-whitespace`, and the expected qubits, average
   Toffoli and 0 / 0 / 0. Then `### Patch` from `insert_patch.py`.

A commit labelled Verifier Search that also changes the circuit (e.g.
[`a4db9a5`](commits/a4db9a5.md)) keeps the full format.

## Tiers

- **A**: the patch is the complete change.
- **B**: some files are copied from the commit. Use this for generated data
  (key lists, masks, `.bin` and `.tsv` files, baked tables), or for
  hand-written new files too large to inline. Their contents must still be
  described in "What changed".

## Choosing the base

The base is the earlier accepted commit whose `src/point_add` differs least
from this one, ignoring CRLF. This is precomputed in `data/bases.tsv`. In
about 45% of commits the base is not the git parent, because the author built
on an older tree.

## Acceptance check

`python3 tools/check_reproduce.py <hash>` exports the base without git
history, follows the note's copy commands, applies its patch, and compares the
result with the commit's `src/point_add`, ignoring CRLF. A note is done only
when this prints `PASS`.

`python3 tools/check_reproduce.py --all` checks every note that has a
Reproduce section.
