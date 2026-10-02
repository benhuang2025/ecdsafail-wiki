#!/usr/bin/env python3
"""Check that a commit note's Reproduce section really rebuilds the commit.

For each note: export the base's src/point_add (no git history), apply the
note's diff blocks, run its `git checkout <hash> -- <paths>` copy commands
(Tier B), and compare the result with the commit's src/point_add, ignoring
CRLF. Prints PASS or the files that differ.

    python3 tools/check_reproduce.py e5c53dc 8d7051b ...
    python3 tools/check_reproduce.py --all
"""
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = Path(os.environ.get("ECDSAFAIL_CHALLENGE_REPO", Path(__file__).resolve().parents[2] / "ecdsafail-challenge"))


def git(*args, **kw):
    return subprocess.run(["git", "-C", str(REPO), *args], check=True,
                          capture_output=True, **kw).stdout


def export(rev, dest, path="src/point_add"):
    """Write the blobs under `path` at `rev` into dest.

    Reads blobs straight from git instead of going through tar, because macOS
    tar folds AppleDouble `._*` files (which some commits contain) into
    extended attributes.
    """
    listing = git("ls-tree", "-r", "-z", rev, "--", path).split(b"\0")
    entries = []
    for item in filter(None, listing):
        meta, name = item.split(b"\t", 1)
        mode, kind, sha = meta.split()
        if kind == b"blob":
            entries.append((sha, name.decode()))
    if not entries:
        return
    batch = subprocess.run(["git", "-C", str(REPO), "cat-file", "--batch"],
                           input=b"".join(sha + b"\n" for sha, _ in entries),
                           check=True, capture_output=True).stdout
    pos = 0
    for sha, name in entries:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        body = batch[header_end + 1:header_end + 1 + size]
        pos = header_end + 1 + size + 1
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)


def section(text):
    m = re.search(r"^## Reproduce\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise ValueError("no ## Reproduce section")
    return m.group(1)


def normalize(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def check(commit):
    text = (ROOT / "commits" / f"{commit}.md").read_text()
    repro = section(text)
    base = re.search(r"git checkout ([0-9a-f]{7,40}) -- src/point_add", repro).group(1)
    blocks = re.findall(r"^([ \t]*)```diff\n(.*?)^\1```", repro, re.S | re.M)
    patches = [textwrap.dedent(body) for _, body in blocks]
    copies = re.findall(r"git checkout ([0-9a-f]{7,40}) -- ((?!src/point_add`)[^`\n]+)", repro)
    removes = [p for block in re.findall(r"^```sh\n(.*?)^```", repro, re.S | re.M)
               for cmd in block.replace("\\\n", " ").splitlines() if cmd.startswith("rm ")
               for p in cmd.split()[1:]]

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        want = Path(tmp) / "want"
        work.mkdir()
        want.mkdir()
        export(base, work)
        export(commit, want)
        for path in removes:
            (work / path).unlink()
        for p in patches:
            # Apply exactly as the note instructs, so a PASS means the note works.
            r = subprocess.run(["git", "apply", "--ignore-whitespace", "-"],
                               cwd=work, input=p.encode(), capture_output=True)
            if r.returncode:
                return f"FAIL patch does not apply: {r.stderr.decode().strip()[:300]}"
        for rev, paths in copies:
            for path in paths.split():
                export(rev, work, path.rstrip("/"))
        got = {p.relative_to(work) for p in work.rglob("*") if p.is_file()}
        exp = {p.relative_to(want) for p in want.rglob("*") if p.is_file()}
        bad = sorted(str(p) for p in got | exp
                     if p not in got or p not in exp or normalize(work / p) != normalize(want / p))
    if bad:
        return f"FAIL {len(bad)} file(s) differ: {', '.join(bad[:8])}"
    return f"PASS (base {base}, {len(patches)} patch block(s), {len(copies)} copy command(s))"


def main():
    args = sys.argv[1:]
    if args == ["--all"]:
        args = sorted(p.stem for p in (ROOT / "commits").glob("*.md")
                      if "## Reproduce" in p.read_text())
    fails = 0
    for c in args:
        try:
            res = check(c)
        except Exception as e:  # report and keep going
            res = f"FAIL {type(e).__name__}: {e}"
        fails += res.startswith("FAIL")
        print(f"{c}: {res}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
