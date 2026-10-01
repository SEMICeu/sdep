#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Check tests/suites.txt, the single list of integration test runs.

Every runner (local and deployment) reads this file, so a test that is missing from it
never runs anywhere. This offline guard makes sure every test script is either listed
or named in NOT_IN_SUITES with a reason, and that the file is well-formed.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITES_FILE = REPO_ROOT / "tests" / "suites.txt"
MAKEFILE = REPO_ROOT / "Makefile"

FIXED_COLUMNS = ["suite", "client", "test", "version"]

# Test scripts that are deliberately not in a suite, with the reason.
NOT_IN_SUITES = {
    "test_auth_client_bootstrap": "login helper, runs before every suite that has a client",
    "test_auth_client_jwt": "needs a per-environment client and key, the runners call it separately",
    "test_cve_ids": "repository check (make test-cve-offline)",
    "test_trivy_allowlist": "repository check (make test-cve-offline)",
    "test_postgres_check_constraints": "migration test (make test-migrations)",
    "test_suites": "this check (make test-suites)",
}

# Production has no test clients and takes no test data: public smoke checks only.
PRD_SUITES = {"smoke"}

VERSION_RE = re.compile(r"^(-|v\d+)$")
CLIENT_RE = re.compile(r"^(-|[A-Z][A-Z0-9]*)$")


def parse(text: str) -> tuple[list[str], list[tuple[int, list[str]]], list[str]]:
    """Return (header columns, [(line number, row)], errors)."""
    header: list[str] = []
    rows: list[tuple[int, list[str]]] = []
    errors: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("# suite "):
            header = line[1:].split()
        elif line.strip() and not line.startswith("#"):
            rows.append((number, line.split()))
    if header[: len(FIXED_COLUMNS)] != FIXED_COLUMNS or len(header) == len(FIXED_COLUMNS):
        errors.append(f"header must be '# {' '.join(FIXED_COLUMNS)} <ENV> ...', got {header}")
    return header, rows, errors


def check(text: str, test_names: set[str], make_targets: set[str]) -> list[str]:
    """Return the problems found in the suites file."""
    header, rows, errors = parse(text)
    if errors:
        return errors
    envs = header[len(FIXED_COLUMNS) :]
    listed: set[str] = set()
    seen_runs: set[tuple[str, str, str]] = set()
    suite_client: dict[str, str] = {}
    closed_suites: set[str] = set()
    current_suite = ""

    for number, row in rows:
        where = f"line {number}"
        if len(row) >= len(FIXED_COLUMNS):
            listed.add(row[2])
        if len(row) != len(header):
            errors.append(f"{where}: {len(row)} columns, expected {len(header)}")
            continue
        suite, client, test, version, *flags = row

        if not CLIENT_RE.match(client):
            errors.append(f"{where}: client '{client}' must be - or uppercase (e.g. CA1)")
        if not VERSION_RE.match(version):
            errors.append(f"{where}: version '{version}' must be - or v<number>")
        if any(flag not in ("x", "-") for flag in flags):
            errors.append(f"{where}: environment flags must be x or -, got {flags}")
        if test not in test_names:
            errors.append(f"{where}: tests/{test}.py does not exist")
        if (suite, test, version) in seen_runs:
            errors.append(f"{where}: duplicate run {suite} {test} {version}")
        seen_runs.add((suite, test, version))

        # A suite is one block with one client: the runners log in once per suite.
        if suite != current_suite:
            if suite in closed_suites:
                errors.append(f"{where}: suite '{suite}' is split, keep its lines together")
            closed_suites.add(current_suite)
            current_suite = suite
        if suite_client.setdefault(suite, client) != client:
            errors.append(f"{where}: suite '{suite}' has client {client}, earlier {suite_client[suite]}")

        if "PRD" in envs and flags[envs.index("PRD")] == "x" and suite not in PRD_SUITES:
            errors.append(f"{where}: PRD only runs suite(s) {sorted(PRD_SUITES)}, not '{suite}'")

    for suite in suite_client:
        if f"test-{suite}" not in make_targets:
            errors.append(f"suite '{suite}' has no 'make test-{suite}' target")
    for test in sorted(test_names - listed - NOT_IN_SUITES.keys()):
        errors.append(f"tests/{test}.py is in no suite: add it to tests/suites.txt, or to NOT_IN_SUITES")
    for test in sorted(listed & NOT_IN_SUITES.keys()):
        errors.append(f"{test} is in a suite and in NOT_IN_SUITES, pick one")
    return errors


def main() -> int:
    test_names = {path.stem for path in (REPO_ROOT / "tests").glob("test_*.py")}
    make_targets = set(re.findall(r"^(test-[a-z0-9-]+):", MAKEFILE.read_text(), re.MULTILINE))
    errors = check(SUITES_FILE.read_text(), test_names, make_targets)
    for error in errors:
        print(f"  FAIL: {error}")
    if errors:
        print()
        print(f"tests/suites.txt has {len(errors)} problem(s).")
        return 1
    print("  PASS: tests/suites.txt lists every test and is well-formed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
