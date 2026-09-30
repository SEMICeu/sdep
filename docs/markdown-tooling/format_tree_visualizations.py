#!/usr/bin/env python3
"""Align the `# comment` column in Markdown directory-tree code blocks.

House rule: within one tree block, every comment starts at the same column, the
one the longest commented line needs (longest content + 2 spaces). Lines without
a comment are left alone. Run by `make md-format` (align in place) and
`make md-lint` (--check: exit 1 and list the misaligned lines).

Usage:
    format_tree_visualizations.py [--check] FILE.md [FILE.md ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TREE_CHARS = frozenset("│├└─")
MIN_GAP = 2
# Non-greedy, so a comment that itself contains " # " is split at its first "#".
COMMENT = re.compile(r"^(.*?\S)\s+(# .*)$")


def tree_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """(start, end) line indexes of fenced blocks that hold a commented tree."""
    blocks: list[tuple[int, int]] = []
    start = -1
    for i, line in enumerate(lines):
        if not line.strip().startswith("```"):
            continue
        if start < 0:
            start = i
            continue
        body = lines[start + 1 : i]
        if any(is_tree_line(l) and COMMENT.match(l) for l in body):
            blocks.append((start + 1, i))
        start = -1
    return blocks


def is_tree_line(line: str) -> bool:
    return any(c in TREE_CHARS for c in line)


def align(block: list[str]) -> list[str]:
    """The block with every tree comment at the shared column."""
    parsed = [COMMENT.match(l) if is_tree_line(l) else None for l in block]
    column = max((len(m.group(1)) for m in parsed if m), default=0) + MIN_GAP
    out = []
    for line, m in zip(block, parsed):
        if m is None:
            out.append(line)
            continue
        content, comment = m.group(1), m.group(2)
        out.append(content + " " * max(MIN_GAP, column - len(content)) + comment)
    return out


def process(path: Path, check: bool) -> int:
    """Number of misaligned lines; rewrites the file unless check."""
    lines = path.read_text(encoding="utf-8").splitlines()
    original = list(lines)
    for start, end in tree_blocks(lines):
        lines[start:end] = align(lines[start:end])
    changed = [i for i, (a, b) in enumerate(zip(original, lines), 1) if a != b]
    if not changed:
        return 0
    if check:
        for i in changed:
            print(f"{path}:{i}: tree comment not at the shared column")
    else:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{path}: {len(changed)} tree comment line(s) aligned")
    return len(changed)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    files = [Path(a) for a in argv if a != "--check"]
    if not files:
        print(__doc__, file=sys.stderr)
        return 2
    misaligned = sum(process(f, check) for f in files if f.suffix == ".md")
    if check and misaligned:
        print(f"{misaligned} misaligned tree comment line(s): run `make md-format`")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
