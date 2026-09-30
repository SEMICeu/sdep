#!/usr/bin/env python3
"""Check the directory tree in docs/ARCHITECTURE_TECH.md against the filesystem.

Two directions:
- every listed path must exist (a deleted or renamed file leaves a stale entry)
- a directory whose files are listed must not hold unlisted source files

Private paths (export-ignore in .gitattributes) are never required and must not
be listed: the tree is read on the public mirror, where they do not exist.
Exit 1 with one line per finding, exit 0 when the tree is current.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "ARCHITECTURE_TECH.md"
HEADING = "## Repository and directory structure"
CONNECTOR = re.compile(r"(├──|└──) (.+)$")
SOURCE_SUFFIXES = {".py", ".sh", ".sql", ".md", ".yaml", ".yml", ".toml", ".ini", ".mako"}
IGNORED_NAMES = {"__init__.py", "__pycache__", ".gitkeep"}


def tree_lines() -> list[str]:
    """The lines of the fenced block that follows the tree heading."""
    text = DOC.read_text(encoding="utf-8")
    start = text.index(HEADING)
    fence_open = text.index("```", start) + 3
    fence_close = text.index("```", fence_open)
    return text[fence_open:fence_close].splitlines()


def listed_paths() -> list[Path]:
    """Relative paths in the tree, directories with a trailing slash kept as Path."""
    stack: list[str] = []
    paths: list[Path] = []
    for line in tree_lines():
        match = CONNECTOR.search(line.split("#", 1)[0].rstrip())
        if not match:
            continue
        depth = match.start(1) // 4
        name = match.group(2).strip()
        del stack[depth:]
        path = Path(*stack, name.rstrip("/"))
        paths.append(path)
        if name.endswith("/"):
            stack.append(name.rstrip("/"))
    return paths


def git_known_paths() -> set[Path]:
    """Tracked and untracked-but-not-ignored files, so build output never counts."""
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    ).stdout
    files = {Path(line) for line in output.splitlines() if line}
    return files | {parent for file in files for parent in file.parents}


def private_paths(paths: set[Path]) -> set[Path]:
    """The subset marked export-ignore in .gitattributes (never on the public mirror)."""
    output = subprocess.run(
        ["git", "check-attr", "--stdin", "export-ignore"],
        input="".join(f"{p}\n" for p in paths),
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    ).stdout
    return {
        Path(line.rsplit(": export-ignore: ", 1)[0])
        for line in output.splitlines()
        if line.endswith(": export-ignore: set")
    }


def main() -> int:
    findings: list[str] = []
    known = git_known_paths()
    paths = listed_paths()
    listed = {p for p in paths if "*" not in p.name}
    private = private_paths(known | listed)
    for path in sorted(listed):
        if not (REPO_ROOT / path).exists():
            findings.append(f"listed but missing: {path}")
        elif path in private:
            findings.append(f"listed but private (export-ignore): {path}")

    # Directories whose files are enumerated (no wildcard entry) must be complete.
    enumerated = {p.parent for p in listed if (REPO_ROOT / p).is_file()}
    wildcarded = {p.parent for p in paths if "*" in p.name}
    for directory in sorted(enumerated - wildcarded):
        for entry in sorted((REPO_ROOT / directory).iterdir()):
            relative = entry.relative_to(REPO_ROOT)
            if (
                entry.name in IGNORED_NAMES
                or entry.name.startswith(".")
                or relative not in known
                or relative in private
                or relative in listed
                or (entry.is_file() and entry.suffix not in SOURCE_SUFFIXES)
            ):
                continue
            findings.append(f"present but not listed: {relative}")

    for finding in findings:
        print(finding)
    print(f"Architecture tree: {len(listed)} listed paths, {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
