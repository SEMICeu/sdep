#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = []
# ///
"""Behavioural tests for scripts/check_cve_allowlist.py (the CVE policy gate).

The gate must fail when an allowlisted CVE differs from Trivy's package or severity.
It must also fail on unallowed, stale, duplicate, and structurally invalid entries. The
gate reads a Trivy JSON report directly, so the tests feed it fixtures without requiring
a scanner or image.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "check_cve_allowlist.py"


def trivy_results(*vulns: tuple[str, str, str]) -> dict:
    """Build a Trivy-style report from (cve_id, package, severity) triples."""
    return {
        "Results": [
            {
                "Target": "image",
                "Vulnerabilities": [
                    {"VulnerabilityID": cve, "PkgName": pkg, "Severity": severity}
                    for cve, pkg, severity in vulns
                ],
            }
        ]
    }


def allowlist(*rows: tuple[str, str], severity: str = "High") -> str:
    """Render a CVE_EXPLAINS-style allowlist from (cve_id, pkg_name) pairs."""
    lines = [
        "<h1>Known CVEs</h1>",
        "",
        f"## {severity}",
        "",
        "| CVE ID | Package | Justification | Reviewed at |",
        "| :--- | :--- | :--- | :--- |",
    ]
    lines += [
        f"| {cve} | {pkg} | Justified for test. | 2026-01-01 |" for cve, pkg in rows
    ]
    return "\n".join(lines) + "\n"


def run_gate(allowlist_md: str, results: dict) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        allowlist_file = tmp_path / "CVE_EXPLAINS.md"
        allowlist_file.write_text(allowlist_md)
        results_json = tmp_path / "trivy-results.json"
        results_json.write_text(json.dumps(results, indent=2))
        # Run via uv so the gate's declared dependencies (pydantic) are resolved.
        return subprocess.run(
            [
                "uv",
                "run",
                "--script",
                str(GATE),
                str(results_json),
                "--allowlist",
                str(allowlist_file),
            ],
            capture_output=True,
            check=False,
            text=True,
        )


class Stats:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"  PASS: {name}")
        else:
            self.failed += 1
            print(f"  FAIL: {name}{(' - ' + detail) if detail else ''}")


def main() -> int:
    stats = Stats()

    print("Matching package passes:")
    res = run_gate(
        allowlist(("CVE-2024-0001", "libfoo")),
        trivy_results(("CVE-2024-0001", "libfoo", "HIGH")),
    )
    stats.check(
        "exit code 0", res.returncode == 0, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("reports OK", "OK:" in res.stdout)
    stats.check("no PACKAGE MISMATCH", "PACKAGE MISMATCH" not in res.stdout)

    print("Mismatched package fails:")
    res = run_gate(
        allowlist(("CVE-2024-0006", "libdocumented")),
        trivy_results(("CVE-2024-0006", "libreported", "HIGH")),
    )
    stats.check(
        "exit code 2", res.returncode == 2, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("reports PACKAGE MISMATCH", "PACKAGE MISMATCH" in res.stdout)
    stats.check("names the offending CVE", "CVE-2024-0006" in res.stdout)
    stats.check("shows Trivy's package", "libreported" in res.stdout)

    print("Package matching any of Trivy's PkgNames passes:")
    res = run_gate(
        allowlist(("CVE-2024-0002", "libb")),
        trivy_results(
            ("CVE-2024-0002", "liba", "HIGH"),
            ("CVE-2024-0002", "libb", "HIGH"),
        ),
    )
    stats.check(
        "exit code 0", res.returncode == 0, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("no PACKAGE MISMATCH", "PACKAGE MISMATCH" not in res.stdout)

    print("Unallowed CVE fails:")
    res = run_gate(
        allowlist(),
        trivy_results(("CVE-2024-0003", "libc", "HIGH")),
    )
    stats.check(
        "exit code 2", res.returncode == 2, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("reports NOT ALLOWED", "NOT ALLOWED" in res.stdout)
    stats.check("names the unallowed CVE", "CVE-2024-0003" in res.stdout)

    print("Stale allowlist entry fails:")
    res = run_gate(
        allowlist(("CVE-2024-0004", "libd")),
        trivy_results(),
    )
    stats.check(
        "exit code 2", res.returncode == 2, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("reports STALE", "STALE" in res.stdout)
    stats.check("names the stale CVE", "CVE-2024-0004" in res.stdout)

    print("Duplicate allowlist row fails (same CVE id in two rows):")
    # The CVE is found and its package matches, so only the duplicate guard can fail this -
    # exactly the excess-row clutter the id-keyed checks would otherwise collapse silently.
    res = run_gate(
        allowlist(("CVE-2024-0005", "libe"), ("CVE-2024-0005", "libe")),
        trivy_results(("CVE-2024-0005", "libe", "HIGH")),
    )
    stats.check(
        "exit code 2", res.returncode == 2, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("reports DUPLICATE", "DUPLICATE" in res.stdout)
    stats.check("names the duplicated CVE", "CVE-2024-0005" in res.stdout)
    stats.check("not reported as stale", "STALE" not in res.stdout)

    print("Mismatched severity fails:")
    res = run_gate(
        allowlist(("CVE-2024-0007", "libf"), severity="Low"),
        trivy_results(("CVE-2024-0007", "libf", "CRITICAL")),
    )
    stats.check(
        "exit code 2", res.returncode == 2, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("reports SEVERITY MISMATCH", "SEVERITY MISMATCH" in res.stdout)
    stats.check("names the severity-mismatched CVE", "CVE-2024-0007" in res.stdout)
    stats.check("shows Trivy's severity", "CRITICAL" in res.stdout)

    print("Package and severity must match the same Trivy finding:")
    res = run_gate(
        allowlist(("CVE-2024-0008", "libb"), severity="Low"),
        trivy_results(
            ("CVE-2024-0008", "liba", "LOW"),
            ("CVE-2024-0008", "libb", "HIGH"),
        ),
    )
    stats.check(
        "exit code 2", res.returncode == 2, f"rc={res.returncode}\n{res.stdout}"
    )
    stats.check("reports SEVERITY MISMATCH", "SEVERITY MISMATCH" in res.stdout)
    stats.check("names the cross-pair CVE", "CVE-2024-0008" in res.stdout)

    print("Structurally invalid Trivy report fails:")
    res = run_gate(allowlist(), {})
    stats.check("exit code 1", res.returncode == 1, f"rc={res.returncode}")
    stats.check("reports the missing Results field", "Results" in res.stderr)

    print("Trivy report without scan targets fails:")
    res = run_gate(allowlist(), {"Results": []})
    stats.check("exit code 1", res.returncode == 1, f"rc={res.returncode}")
    stats.check("reports the empty Results field", "Results" in res.stderr)

    print()
    print(f"Test results: {stats.passed}/{stats.passed + stats.failed} passed")
    return 1 if stats.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
