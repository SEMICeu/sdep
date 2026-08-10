#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

# Regression test: the default client-ID regex must reject a literal backslash.
#
# The Keycloak machine-client script validates client IDs with bash `[[ =~ ]]`,
# which uses POSIX ERE. Inside a bracket expression bash treats a backslash as a
# *literal* character, so writing the pattern as `[A-Za-z0-9._\-]` accidentally
# allows a backslash in the allowed set. This test reads the default regex from the
# shell script and verifies it accepts valid IDs and rejects backslash IDs.
#
# IMPORTANT: this must reproduce bash's POSIX-ERE bracket semantics, NOT Python's.
# Python's `re` treats `\-` inside `[...]` as an escaped hyphen (backslash NOT in
# the set), so a naive `re.search` would *miss* the very bug this test guards
# against. `bash_ere_search` escapes backslashes inside bracket expressions so the
# Python engine agrees with bash: with the correct regex the backslash IDs are
# rejected; reintroducing the `\-` bug makes them accepted again (test goes red).

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


TARGET_SCRIPT = Path(__file__).resolve().parents[1] / "keycloak" / "add-realm-machine-clients.sh"

VALID_IDS = ("sdep.client_1", "abc-123", "a.b-c_d")
BAD_IDS = ("my\\client", "a\\b", "\\")


@dataclass
class TestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0


def extract_clientid_regex(text: str) -> str:
    # Mirror the shell extraction `.config.clientid_regex // "<regex>"`: grab the
    # first double-quoted default that follows the clientid_regex key.
    match = re.search(r'clientid_regex[^"]*"([^"]*)"', text)
    return match.group(1) if match else ""


def bash_ere_search(pattern: str, value: str) -> bool:
    # Translate a POSIX ERE to a Python regex preserving the one semantic that
    # matters here: a backslash inside a bracket expression is a literal character
    # in bash, but an escape in Python. Escaping it makes Python agree with bash.
    translated: list[str] = []
    in_bracket = False
    bracket_start = -1  # index in `translated` where the current class body begins
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if not in_bracket:
            translated.append(char)
            if char == "[":
                in_bracket = True
                bracket_start = len(translated)
                # A leading '^' negates; a ']' right after '[' or '[^' is literal.
                if pattern[i + 1 : i + 2] == "^":
                    translated.append("^")
                    i += 1
                    bracket_start = len(translated)
        else:
            if char == "\\":
                translated.append("\\\\")  # literal backslash for Python
            elif char == "]" and len(translated) > bracket_start:
                translated.append(char)
                in_bracket = False
            else:
                translated.append(char)
        i += 1
    return re.search("".join(translated), value) is not None


def main() -> int:
    if not TARGET_SCRIPT.is_file():
        print(f"Cannot find {TARGET_SCRIPT}")
        return 1

    clientid_regex = extract_clientid_regex(TARGET_SCRIPT.read_text(encoding="utf-8"))
    if not clientid_regex:
        print(f"Could not extract default clientid_regex from {TARGET_SCRIPT}")
        return 1

    print(f"Testing default clientid_regex: {clientid_regex}")

    stats = TestStats()

    for client_id in VALID_IDS:
        stats.total += 1
        if bash_ere_search(clientid_regex, client_id):
            print(f"accepted (expected): '{client_id}'")
            stats.passed += 1
        else:
            print(f"rejected but should be accepted: '{client_id}'")
            stats.failed += 1

    for client_id in BAD_IDS:
        stats.total += 1
        if bash_ere_search(clientid_regex, client_id):
            print(f"accepted but should be rejected (backslash): '{client_id}'")
            stats.failed += 1
        else:
            print(f"rejected (expected): '{client_id}'")
            stats.passed += 1

    print()
    print("=======================================")
    print("Test Summary (client-ID regex):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("client-ID regex test passed")
        return 0

    print("client-ID regex test FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
