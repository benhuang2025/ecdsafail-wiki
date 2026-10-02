#!/usr/bin/env python3
"""Snapshot the official leaderboard (`ecdsafail submissions --all`) to TSV.

Run from anywhere; the CLI is invoked inside the competition clone because it
reads the benchmark from repo context. Writes data/leaderboard-<date>.tsv.
"""
import os
import csv
import datetime
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = Path(os.environ.get("ECDSAFAIL_CHALLENGE_REPO", Path(__file__).resolve().parents[2] / "ecdsafail-challenge"))
ANSI = re.compile(r"\x1b\[[0-9;]*m")
ROW = re.compile(
    r"^(?P<submission>\w{7})\s+(?P<solver>\S+)\s+(?P<status>.+?)\s{2,}"
    r"(?P<score>\d+|n/a)\s+(?P<metrics>\{[^}]*\}|n/a)\s+"
    r"(?P<delta>[-+]?\d+|n/a)(?: \([^)]*\))?\s+(?P<commit>[0-9a-f]{7}|-)\s+(?P<created>.+?)\s*$"
)


def main():
    out = subprocess.run(["ecdsafail", "submissions", "--all"], cwd=REPO,
                         check=True, capture_output=True, text=True).stdout
    rows = []
    for line in ANSI.sub("", out).splitlines()[3:]:
        m = ROW.match(line)
        if not m:
            continue
        d = m.groupdict()
        raw = d.pop("metrics")
        metrics = json.loads(raw) if raw != "n/a" else {}
        d["qubits"] = metrics.get("qubits", "")
        d["toffoli"] = metrics.get("toffoli", "")
        for k in ("score", "delta"):
            d[k] = "" if d[k] == "n/a" else d[k]
        d["commit"] = "" if d["commit"] == "-" else d["commit"]
        rows.append(d)
    path = ROOT / "data" / f"leaderboard-{datetime.date.today()}.tsv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, delimiter="\t", fieldnames=[
            "submission", "solver", "status", "score", "qubits", "toffoli",
            "delta", "commit", "created"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} submissions -> {path}")


if __name__ == "__main__":
    main()
