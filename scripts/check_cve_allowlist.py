#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "pydantic>=2.10.3",
# ]
# ///
"""Reconcile a Trivy JSON report against the CVE "explain" allowlist.

This is the policy gate, kept separate from the scan itself (scripts/run-trivy-scan.sh)
so it runs in a general-purpose Python runtime instead of the minimal Trivy image - the
logic is plain json + set comparisons rather than awk over JSON text.

Given a Trivy results file and docs/CVE_EXPLAINS.md, the gate fails when:

- a found CVE is not on the allowlist (triage it or justify it),
- an allowlist entry is stale (Trivy no longer reports it),
- an allowlisted CVE's package does not match the PkgName Trivy reports for it,
- an allowlisted CVE is filed under a section that differs from Trivy's severity, or
- the same CVE id appears in more than one allowlist row. Trivy reports each CVE at a
  single severity, so a repeated row (e.g. the same perl-base CVE copied into Medium and
  Low) is dead clutter. The id-keyed cross-checks above would silently collapse it, so it
  must be caught explicitly.
"""

from __future__ import annotations

import argparse
import re
import shutil
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

CVE_RE = re.compile(r"^CVE-\d{4}-\d+$")
POLICY_DRIFT_EXIT_CODE = 2
INDENT = "  "
COLUMN_GAP = "  "


def render_table(headers: list[str], rows: list[tuple[str, ...]]) -> str:
    """Render rows as aligned columns. Every column except the last is padded to a fixed
    width; the last column (a possibly long, comma-separated package list) wraps under its
    own column so the leading columns stay aligned."""
    fixed = [
        max(len(headers[col]), *(len(row[col]) for row in rows))
        for col in range(len(headers) - 1)
    ]
    # Column at which the wrapping last column starts.
    last_start = len(INDENT) + sum(w + len(COLUMN_GAP) for w in fixed)
    terminal_width = shutil.get_terminal_size((100, 24)).columns
    wrap_width = max(20, terminal_width - last_start)

    def line(cells: tuple[str, ...]) -> str:
        prefix = INDENT + "".join(
            cells[col].ljust(fixed[col]) + COLUMN_GAP for col in range(len(fixed))
        )
        wrapped = textwrap.wrap(
            cells[-1], width=wrap_width, break_long_words=False, break_on_hyphens=False
        ) or [""]
        first, *rest = wrapped
        out = prefix + first
        for continuation in rest:
            out += "\n" + " " * last_start + continuation
        return out

    separator = INDENT + "".join(
        "-" * fixed[col] + COLUMN_GAP for col in range(len(fixed))
    )
    separator += "-" * len(headers[-1])
    return "\n".join([line(tuple(headers)), separator, *(line(row) for row in rows)])


# Schema for the slice of Trivy's JSON report this gate needs. Field names match Trivy's
# keys so access reads `report.Results[i].Vulnerabilities[j].VulnerabilityID` - a declared,
# validated shape rather than dict.get() guessing. extra="ignore" lets Trivy's many other
# fields pass through untouched; the lists are Optional because Trivy emits `null` for a
# target with no vulnerabilities.
class TrivyVulnerability(BaseModel):
    model_config = ConfigDict(extra="ignore")

    VulnerabilityID: str
    PkgName: str
    Severity: str


class TrivyResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    Vulnerabilities: list[TrivyVulnerability] | None = None


class TrivyReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    Results: list[TrivyResult] = Field(min_length=1)


@dataclass
class FoundCVE:
    severities_by_package: dict[str, set[str]] = field(default_factory=dict)

    @property
    def packages(self) -> set[str]:
        return set(self.severities_by_package)


@dataclass(frozen=True)
class AllowlistRow:
    package: str
    severity: str


def parse_trivy_report(path: Path) -> dict[str, FoundCVE]:
    """Map each found CVE id to the packages and severities Trivy reports."""
    report = TrivyReport.model_validate_json(path.read_text())
    found: dict[str, FoundCVE] = {}
    for result in report.Results:
        for vuln in result.Vulnerabilities or []:
            if not CVE_RE.match(vuln.VulnerabilityID):
                continue
            finding = found.setdefault(vuln.VulnerabilityID, FoundCVE())
            finding.severities_by_package.setdefault(vuln.PkgName, set()).add(
                vuln.Severity.upper()
            )
    return found


def parse_allowlist(path: Path) -> dict[str, list[AllowlistRow]]:
    """Map each allowlisted CVE id to its package and severity section.

    Only "| CVE-... | package | ... |" rows are considered; CVE ids appearing in prose
    are ignored. The package column is what the gate cross-checks against Trivy. A CVE id
    should appear in exactly one row; a list with more than one entry is a duplicate row
    (caught as a DUPLICATE finding rather than silently overwritten).
    """
    allow: dict[str, list[AllowlistRow]] = {}
    severity = ""
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            severity = line.removeprefix("## ").strip().upper()
            continue
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        # cells[0] is empty (text before the leading pipe); cells[1] = CVE, cells[2] = package.
        if len(cells) >= 3 and CVE_RE.match(cells[1]):
            allow.setdefault(cells[1], []).append(AllowlistRow(cells[2], severity))
    return allow


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile a Trivy report against the CVE allowlist."
    )
    parser.add_argument("results", type=Path, help="Path to the Trivy JSON report")
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("docs/CVE_EXPLAINS.md"),
        help="Path to the CVE explain allowlist (default: docs/CVE_EXPLAINS.md)",
    )
    args = parser.parse_args()

    found = parse_trivy_report(args.results)
    allow_rows = parse_allowlist(args.allowlist)
    # The first row's package is the one cross-checked against Trivy; extra rows for the
    # same CVE id are duplicates reported below.
    allow = {cve: rows[0] for cve, rows in allow_rows.items()}
    duplicates = sorted(cve for cve, rows in allow_rows.items() if len(rows) > 1)

    found_ids = set(found)
    allow_ids = set(allow)
    unallowed = sorted(found_ids - allow_ids)
    stale = sorted(allow_ids - found_ids)
    matched = sorted(found_ids & allow_ids)

    mismatches = [
        (cve, allow[cve].package, sorted(found[cve].packages))
        for cve in matched
        if allow[cve].package not in found[cve].packages
    ]
    severity_mismatches = [
        (
            cve,
            allow[cve].severity,
            sorted(found[cve].severities_by_package[allow[cve].package]),
        )
        for cve in matched
        if allow[cve].package in found[cve].severities_by_package
        and allow[cve].severity
        not in found[cve].severities_by_package[allow[cve].package]
    ]

    print(f"Trivy results vs {args.allowlist}")
    print(
        f"{len(found_ids)} CVE(s) found | {len(matched)} allowed | "
        f"{len(unallowed)} not allowed | {len(stale)} stale | "
        f"{len(mismatches)} package mismatch | "
        f"{len(severity_mismatches)} severity mismatch | {len(duplicates)} duplicate"
    )

    failed = False

    if unallowed:
        rows = [
            (cve, ", ".join(sorted(found[cve].packages)) or "?") for cve in unallowed
        ]
        print(
            f"\nNOT ALLOWED ({len(unallowed)}) - fix, or justify in {args.allowlist}\n"
        )
        print(render_table(["CVE", "PACKAGE"], rows))
        failed = True

    if stale:
        rows = [(cve, allow[cve].package) for cve in stale]
        print(
            f"\nSTALE ({len(stale)}) - no longer reported by Trivy; remove from {args.allowlist}\n"
        )
        print(render_table(["CVE", "PACKAGE"], rows))
        failed = True

    if mismatches:
        rows = [
            (cve, allow_pkg, ", ".join(trivy_pkgs))
            for cve, allow_pkg, trivy_pkgs in mismatches
        ]
        print(
            f"\nPACKAGE MISMATCH ({len(mismatches)}) - allowlist package vs Trivy's PkgName; "
            f"correct the Package column in {args.allowlist}\n"
        )
        print(render_table(["CVE", "ALLOWLIST", "TRIVY REPORTS"], rows))
        failed = True

    if severity_mismatches:
        rows = [
            (cve, allowlist_severity, ", ".join(trivy_severities))
            for cve, allowlist_severity, trivy_severities in severity_mismatches
        ]
        print(
            f"\nSEVERITY MISMATCH ({len(severity_mismatches)}) - allowlist section vs "
            f"Trivy's Severity; move each row to the matching section in {args.allowlist}\n"
        )
        print(render_table(["CVE", "ALLOWLIST", "TRIVY REPORTS"], rows))
        failed = True

    if duplicates:
        rows = [
            (
                cve,
                str(len(allow_rows[cve])),
                ", ".join(row.package for row in allow_rows[cve]),
            )
            for cve in duplicates
        ]
        print(
            f"\nDUPLICATE ({len(duplicates)}) - CVE id appears in multiple rows; "
            f"keep a single row in {args.allowlist}\n"
        )
        print(render_table(["CVE", "ROWS", "PACKAGES"], rows))
        failed = True

    if failed:
        print("\nFAILED: allowlist is out of sync with the Trivy report (see above).")
        return POLICY_DRIFT_EXIT_CODE

    print(
        "\nOK: all found CVEs are allowlisted, packages and severities match, "
        "and no stale entries exist."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
