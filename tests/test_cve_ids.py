#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
# ///
"""Check CVE identifier years in the repository's authoritative CVE documents.

Repository history contains a targeted edit that changed CVE-2024-45409 into the
unassigned CVE-2026-45409. This offline guard catches identifiers with an
implausible year: earlier than the CVE program or later than the current year.

A plausible year and valid syntax do not prove that an identifier is assigned. The live
policy gate provides the stronger check for allowlist rows by comparing their identifiers,
packages, and severities with Trivy's report.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Authoritative documents that record CVE identifiers.
SCANNED_FILES = [
    REPO_ROOT / "docs" / "CVE_EXPLAINS.md",
    REPO_ROOT / "CHANGELOG.md",
]

CVE_FIRST_YEAR = 1999
CVE_RE = re.compile(r"CVE-(\d{4})-\d+")


def find_invalid_cve_ids(text: str, max_year: int) -> list[tuple[str, int]]:
    """Return (cve_id, line_number) for every implausibly-dated CVE id."""
    invalid: list[tuple[str, int]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in CVE_RE.finditer(line):
            year = int(match.group(1))
            if year < CVE_FIRST_YEAR or year > max_year:
                invalid.append((match.group(0), line_number))
    return invalid


def main() -> int:
    current_year = datetime.now(timezone.utc).year
    failures = 0

    for path in SCANNED_FILES:
        rel = path.relative_to(REPO_ROOT)
        if not path.is_file():
            print(f"  FAIL: {rel} not found")
            failures += 1
            continue
        invalid = find_invalid_cve_ids(path.read_text(), current_year)
        if invalid:
            failures += 1
            print(f"  FAIL: {rel} has implausibly-dated CVE id(s):")
            for cve, line_number in invalid:
                print(f"        {rel}:{line_number} {cve}")
        else:
            print(f"  PASS: {rel}")

    print()
    if failures:
        print(
            "Implausibly-dated CVE identifiers detected. A CVE year must be between "
            f"{CVE_FIRST_YEAR} and {current_year}; correct each reported identifier "
            "from its authoritative source."
        )
        return 1
    print("All CVE identifiers are plausibly dated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
