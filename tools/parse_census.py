#!/usr/bin/env python3
"""Parse the original 404-row census longtable into data/census.tsv.

One row per accepted commit: commit, contestant, date, score, delta, family,
change_type, source. Score/delta are plain integers ("" when unscored).
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources" / "supplemental-note-C-2026-08-28.tex"
OUT = ROOT / "data" / "census.tsv"

FAMILY = re.compile(r"\\textbf\{(.+?)\}~\\small\((\d+)\)")
CHANGE = re.compile(r"\\quad\\itshape (.+?) \\small\((\d+)\)")
ROW = re.compile(r"^\\texttt\{([0-9a-f]{7})\} & (.*?) & (\d{4}-\d{2}-\d{2}) & (.*?) & (.*?)\\\\$")


def unlatex(s):
    s = s.replace("\\_", "_").replace("{,}", ",")
    s = re.sub(r"\\texttt\{(.*?)\}", r"\1", s)
    return s.strip()


def number(s):
    s = s.strip().strip("$").replace("{,}", "").replace(",", "")
    return s if re.fullmatch(r"-?\d+", s) else ""


def main():
    rows, family, change = [], None, None
    for line in SRC.read_text().splitlines():
        if m := FAMILY.search(line):
            family, change = unlatex(m.group(1)), None
            # The bootstrap group has no change-type sub-heading.
            if family.startswith("Unscored bootstrap"):
                change = "unscored bootstrap"
        elif m := CHANGE.search(line):
            change = unlatex(m.group(1))
        elif m := ROW.match(line):
            commit, who, date, score, delta = m.groups()
            rows.append(dict(commit=commit, contestant=who, date=date,
                             score=number(score), delta=number(delta),
                             family=family, change_type=change,
                             source="census-2026-07-18"))
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
