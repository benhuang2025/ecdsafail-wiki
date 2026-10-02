#!/usr/bin/env python3
"""Fill a note's "### Patch" subsection with the exact diff from git.

    python3 tools/insert_patch.py <commit> <base> [path ...]

Replaces everything between "### Patch" and the next "## " heading with the
output of render_patch.py, so patches in notes are never hand-copied. Deleted
files become an `rm` command instead of being inlined in the diff.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    commit, base, *paths = sys.argv[1:]
    note = ROOT / "commits" / f"{commit}.md"
    block = subprocess.check_output(
        [sys.executable, str(ROOT / "tools" / "render_patch.py"), "--no-deletes",
         base, commit, *paths], text=True)
    text = note.read_text()
    new, n = re.subn(r"(^### Patch\n\n).*?(?=^## |\Z)",
                     lambda m: m.group(1) + block + "\n", text, flags=re.S | re.M)
    if n != 1:
        sys.exit(f"{note.name}: expected one '### Patch' subsection, found {n}")
    note.write_text(new)
    print(f"{note.name}: patch {base}..{commit} inserted ({block.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
