#!/usr/bin/env python3
"""Build accepted-commit-census.tex from the frozen census plus new rows.

Inputs
  data/census.tsv                  frozen 404 rows (from parse_census.py)
  data/new-classification.tsv      commit, family, change_type, summary
  data/leaderboard-<latest>.tsv    official scores (snapshot_leaderboard.py)
  the competition clone            dates and commit indices from git

Ordering follows the original census: families by descending size, with the
residual buckets (Verifier Search, Neutral / Mechanical, Unscored bootstrap)
last; change-types by descending size; rows by score, best first.
"""
import os
import csv
import datetime
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = Path(os.environ.get("ECDSAFAIL_CHALLENGE_REPO", Path(__file__).resolve().parents[2] / "ecdsafail-challenge"))
DATA = ROOT / "data"
OUT = ROOT / "accepted-commit-census.tex"
RESIDUAL = ["Verifier Search", "Neutral / Mechanical",
            "Unscored bootstrap (DUMMY_TOFFOLIS)"]
FIRST_INDEX = 883


def read_tsv(path):
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def tex(s):
    return s.replace("_", "\\_")


def num(s):
    return f"${int(s):,}$".replace(",", "{,}")


def strip_new(s):
    for p in ("NEW FAMILY: ", "NEW: "):
        if s.startswith(p):
            return s[len(p):]
    return s


def main():
    board_path = max(DATA.glob("leaderboard-*.tsv"))
    board = {r["commit"]: r for r in read_tsv(board_path)
             if r["commit"] and r["status"] == "promoted"}

    rows = read_tsv(DATA / "census.tsv")
    for r in rows:
        if r["contestant"] == "unknown" and r["commit"] in board:
            r["contestant"] = board[r["commit"]]["solver"]

    for c in read_tsv(DATA / "new-classification.tsv"):
        b = board[c["commit"]]
        rows.append(dict(commit=c["commit"], contestant=b["solver"],
                         date=git("log", "-1", "--format=%ad", "--date=short", c["commit"]),
                         score=b["score"], delta=b["delta"],
                         family=strip_new(c["family"]),
                         change_type=strip_new(c["change_type"]),
                         source="extension"))

    commits = [r["commit"] for r in rows]
    assert len(commits) == len(set(commits)), "duplicate commit rows"
    # Several commits can share the last date, so pick the latest by index.
    last_index, last = max((int(git("rev-list", "--count", r["commit"])), r)
                           for r in rows if r["source"] == "extension")
    n_total = len(rows)
    n_unscored = sum(1 for r in rows if not r["score"])
    n_new = sum(1 for r in rows if r["source"] == "extension")
    cutoff = datetime.date.fromisoformat(last["date"])
    cutoff_txt = f"{cutoff.day} {cutoff:%B}"

    fam_size = Counter(r["family"] for r in rows)
    by_change = defaultdict(list)
    for r in rows:
        by_change[(r["family"], r["change_type"])].append(r)
    families = sorted((f for f in fam_size if f not in RESIDUAL),
                      key=lambda f: -fam_size[f])
    families += [f for f in RESIDUAL if f in fam_size]

    out = [f"""\\section{{Optimization Census of Accepted Competition Source Commits}}
\\label{{sec:supp-census}}

This note lists every accepted source commit of the public competition
(Supplemental Note~B), assigned to its primary transformation family or
residual bucket---the census summarized in \\Cref{{M:fig:family-census-tree}}, here
expanded to one row per commit and extended past its 18 July interval.
Official operating points---\\emph{{Score}}~$=$
average executed Toffoli $\\times$ peak qubits (lower is better) and $\\Delta$, the
score change versus the prior public frontier---are joined from the ecdsafail
leaderboard; they are not in the git history itself. The ledger covers ${n_total}$
accepted commits through {cutoff_txt}. The first ${n_total - n_new}$, through 18 July,
are the census of \\Cref{{M:fig:family-census-tree}}, with labels and scores as
published (reconciled against the 2 July ledger snapshot). The ${n_new}$ later commits
are scored from the {board_path.stem.removeprefix('leaderboard-')} leaderboard snapshot
and lie outside the interval of \\Cref{{M:fig:family-census-tree}}. From 6 August the
contest records an accepted solution as a ``Validate submission'' commit instead of
``Accept submission''; both count as accepted here. ${n_unscored}$ commits are the
contest's \\texttt{{DUMMY\\_TOFFOLIS}} bootstrap commits, which went through the
acceptance plumbing but were never scored and are marked \\emph{{(unscored)}}. Each
row's assignment is made by an audit of its actual \\texttt{{git show}} diff (not its
commit subject or lever name, which are frequently unreliable). Rows are grouped by
family in descending order of frequency---with the two residual buckets (verifier
search, neutral) and the unscored bootstrap group placed last---then by change-type,
and within a change-type by score (best first).

Within the 18 July interval, the largest recorded frontier delta belongs to
\\texttt{{d19dbb5}} (Register and Scratch Allocation), and the second largest to the
two-jump inversion base (\\texttt{{cddd5df}}, under Windowing), the landed
\\texttt{{DIALOG\\_GCD}} reimplementation of the modular inverse, whose $\\Delta$ is
nearly one billion. After the interval, the largest delta belongs to the ping-pong
division of \\texttt{{897dda2}} (submission \\texttt{{3616dbf}}, under Algorithmic
Substitution).

{{\\small
\\setlength{{\\tabcolsep}}{{4pt}}
\\begin{{longtable}}{{@{{}}lllrr@{{}}}}
\\caption{{Competition optimization census: all ${n_total}$ accepted source commits
(\\#{FIRST_INDEX}--{last_index}) through {cutoff_txt}, classified by primary family,
with official leaderboard score and frontier delta where available. ${n_total - n_unscored}$
scored; ${n_unscored}$ unscored bootstrap commits.}}\\label{{tab:supp-census}}\\\\
\\toprule
\\textbf{{Commit}} & \\textbf{{Contestant}} & \\textbf{{Date}} & \\textbf{{Score}} & \\textbf{{$\\Delta$}}\\\\
\\midrule
\\endfirsthead
\\multicolumn{{5}}{{@{{}}l}}{{\\small\\itshape \\Cref{{tab:supp-census}}, continued}}\\\\[2pt]
\\toprule
\\textbf{{Commit}} & \\textbf{{Contestant}} & \\textbf{{Date}} & \\textbf{{Score}} & \\textbf{{$\\Delta$}}\\\\
\\midrule
\\endhead
\\midrule
\\multicolumn{{5}}{{r@{{}}}}{{\\small\\itshape continued on next page}}\\\\
\\endfoot
\\bottomrule
\\endlastfoot"""]

    for fam in families:
        changes = [k for k in by_change if k[0] == fam]
        changes.sort(key=lambda k: -len(by_change[k]))
        title = tex(fam).replace("DUMMY\\_TOFFOLIS", "\\texttt{DUMMY\\_TOFFOLIS}")
        out.append("\\addlinespace[2pt]")
        out.append(f"\\multicolumn{{5}}{{@{{}}l}}{{\\rule{{0pt}}{{2.6ex}}\\textbf{{{title}}}~\\small({fam_size[fam]})}}\\\\[1pt]")
        for key in changes:
            group = sorted(by_change[key],
                           key=lambda r: (not r["score"], int(r["score"] or 0), r["commit"]))
            if not fam.startswith("Unscored"):
                out.append(f"\\multicolumn{{5}}{{@{{}}l}}{{\\quad\\itshape {tex(key[1])} \\small({len(group)})}}\\\\")
            for r in group:
                score = num(r["score"]) if r["score"] else "\\emph{(unscored)}"
                delta = num(r["delta"]) if r["delta"] else "---"
                out.append(f"\\texttt{{{r['commit']}}} & {tex(r['contestant'])} & {r['date']} & {score} & {delta}\\\\")
    out.append("\\end{longtable}\n}\n")
    OUT.write_text("\n".join(out))
    print(f"{n_total} rows ({n_new} new) -> {OUT}")


if __name__ == "__main__":
    main()
