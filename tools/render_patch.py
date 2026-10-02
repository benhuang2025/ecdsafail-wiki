#!/usr/bin/env python3
"""Print the exact diff between a base and a commit as a Markdown ```diff block.

Never retype a patch into a note: paste this output under "### Patch".

    python3 tools/render_patch.py [--no-deletes] <base> <commit> [path ...]

Paths default to src/point_add. The diff ignores CRLF-only changes, and the
`diff --git` / `index` headers are kept so `git apply` accepts it as is.

With --no-deletes, deleted files are left out of the diff (their whole old
content would otherwise be inlined) and listed in an `rm` command printed
above the block instead.
"""
import os
import subprocess
from pathlib import Path
import sys

REPO = Path(os.environ.get("ECDSAFAIL_CHALLENGE_REPO", Path(__file__).resolve().parents[2] / "ecdsafail-challenge"))


def git(*args):
    return subprocess.check_output(["git", "-C", REPO, *args], text=True)


def main():
    args = sys.argv[1:]
    no_deletes = "--no-deletes" in args
    args = [a for a in args if a != "--no-deletes"]
    base, commit, *paths = args
    paths = paths or ["src/point_add"]
    filt = ["--diff-filter=d"] if no_deletes else []
    diff = git("diff", "--ignore-cr-at-eol", "--no-color", "--binary", *filt, base, commit, "--", *paths)
    deleted = []
    if no_deletes:
        deleted = git("diff", "--name-only", "--diff-filter=D", base, commit, "--", *paths).split()
    if not diff and not deleted:
        sys.exit("empty diff")
    if deleted:
        print("Delete these files first:\n")
        print("```sh")
        print("rm " + " \\\n   ".join(deleted))
        print("```\n")
    if diff:
        print("```diff")
        print(diff, end="" if diff.endswith("\n") else "\n")
        print("```")


if __name__ == "__main__":
    main()
