#!/usr/bin/env python3
"""Check that the documentation still describes the code (make dod).

Run from backend/ with its virtual environment (`uv run python ../scripts/...`):

- every served API route is documented in docs/API_TECH.md, and vice versa
- every ORM column has its row in docs/DATAMODEL_TECH.md
- every Keycloak role is in the docs/SECURITY.md roles table
- every audit action rule has its row in the docs/SECURITY.md action-mapping table, and vice versa
- every API domain name (the landing page one-liner) matches its docs/DEFINITIONS.md heading
- every integration script and `test-*` make target is mentioned in the docs

Exit 1 with one line per finding, exit 0 when the docs are current.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi.routing import APIRoute, iter_route_contexts  # noqa: E402
from starlette.routing import Mount  # noqa: E402

from app.api.common.security import Role  # noqa: E402
from app.api.domain_registry import API_DOMAINS  # noqa: E402
from app.db.config import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.security.audit import _ACTION_RULES  # noqa: E402

DOCS = REPO_ROOT / "docs"
API_DOC = (DOCS / "API_TECH.md").read_text(encoding="utf-8")
DATAMODEL_DOC = (DOCS / "DATAMODEL_TECH.md").read_text(encoding="utf-8")
SECURITY_DOC = (DOCS / "SECURITY.md").read_text(encoding="utf-8")
DEFINITIONS_DOC = (DOCS / "DEFINITIONS.md").read_text(encoding="utf-8")
ALL_DOCS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in [*sorted(DOCS.glob("*.md")), REPO_ROOT / "README.md"]
)

UI_SUFFIXES = ("/docs", "/openapi.json", "/docs/oauth2-redirect", "/redoc")
# Composite columns are documented under their own composite section.
COMPOSITE_PREFIXES = ("address_", "temporal_")


def served_routes() -> set[str]:
    routes: set[str] = set()
    for mount in app.routes:
        if not isinstance(mount, Mount):
            continue
        # app.routes holds included routers as wrappers, iter_route_contexts unfolds them
        for context in iter_route_contexts(mount.app.routes):
            route = context.original_route
            path = context.path or route.path
            if not isinstance(route, APIRoute) or path.endswith(UI_SUFFIXES):
                continue
            for method in route.methods - {"HEAD", "OPTIONS"}:
                routes.add(f"{method} {mount.path}{path}")
    return routes


def check_api() -> list[str]:
    findings: list[str] = []
    routes = served_routes()
    documented = set(re.findall(r"`((?:GET|POST|PUT|PATCH|DELETE) /api/[^`\s]+)`", API_DOC))
    # `/api/ca/v2/areas...` documents every route under that prefix
    prefixes = re.findall(r"`(/api/[^`\s]+?)\.\.\.`", API_DOC)
    for route in sorted(routes):
        path = route.split(" ", 1)[1]
        if route not in documented and not any(path.startswith(p) for p in prefixes):
            findings.append(f"API_TECH.md: served but not documented: {route}")
    for entry in sorted(documented):
        if entry not in routes and not entry.endswith(UI_SUFFIXES):
            findings.append(f"API_TECH.md: documented but not served: {entry}")
    return findings


def camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(part.capitalize() for part in rest)


def doc_section(name: str) -> str | None:
    """Text of the DATAMODEL_TECH.md section for a model class, by class name or spaced name.

    Case-insensitive: headings are sentence case ("Competent authority"), class names are not.
    """
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    for heading in (name, spaced):
        match = re.search(
            rf"^#{{2,3}} {re.escape(heading)}\n(.*?)(?=^#{{2,3}} |\Z)", DATAMODEL_DOC, re.S | re.M | re.I
        )
        if match:
            return match.group(1)
    return None


def check_datamodel() -> list[str]:
    findings: list[str] = []
    for mapper in Base.registry.mappers:
        model = mapper.class_
        section = doc_section(model.__name__)
        if section is None:
            findings.append(f"DATAMODEL_TECH.md: no section for model {model.__name__}")
            continue
        for column in mapper.columns:
            if column.key.startswith(COMPOSITE_PREFIXES):
                continue
            name = column.key
            if column.foreign_keys and name.endswith("_id"):
                name = name[: -len("_id")]  # documented as a reference
            if f"**{camel(name)}**" not in section:
                findings.append(f"DATAMODEL_TECH.md: {model.__name__} has no row for {camel(name)}")
    return findings


def check_roles() -> list[str]:
    return [
        f"SECURITY.md: role {role.value} is not in the roles table"
        for role in Role
        if f"`{role.value}`" not in SECURITY_DOC
    ]


def doc_pattern(regex: str) -> str:
    """The SECURITY.md spelling of an audit path regex: `v*`, `{id}`, `{a,b}`."""
    pattern = regex.strip("^$").replace(r"v\d+", "v*").replace("([^/]+)", "{id}")
    return re.sub(r"\(([^()]+)\)", lambda m: "{" + m.group(1).replace("|", ",") + "}", pattern)


def check_audit_actions() -> list[str]:
    findings: list[str] = []
    coded = {
        (method, doc_pattern(pattern.pattern), resource, action)
        for method, pattern, action, resource in _ACTION_RULES
    }
    # Table cells are padded by md-format, so match on the cell content only
    documented = set(
        re.findall(
            r"^\| *(GET|POST|PUT|PATCH|DELETE) *\| *`(/api/[^`]+)` *\| *`(\w+)` *\| *`(\w+)` *\|$",
            SECURITY_DOC,
            re.M,
        )
    )
    for method, path, resource, action in sorted(coded - documented):
        findings.append(f"SECURITY.md: audit rule not in the action-mapping table: {method} {path} -> {resource} {action}")
    for method, path, resource, action in sorted(documented - coded):
        findings.append(f"SECURITY.md: action-mapping row not in the audit rules: {method} {path} -> {resource} {action}")
    return findings


def check_definitions() -> list[str]:
    """A domain acronym defined in DEFINITIONS.md ("## Name (ACRONYM)") must carry that name.

    Compared case-insensitively: the heading is sentence case (Markdown house rule), the
    landing-page label is Title Case. Acronyms without a definition (e.g. Auth, technical
    rather than functional) are skipped.
    """
    defined = {
        acronym: name
        for name, acronym in re.findall(r"^## (.+) \((\w+)\)$", DEFINITIONS_DOC, re.M)
    }
    return [
        f"DEFINITIONS.md: {domain.label} is named {domain.name!r}, "
        f"the definition heading says {defined[domain.acronym]!r}"
        for domain in API_DOMAINS
        if domain.acronym in defined and defined[domain.acronym].lower() != domain.name.lower()
    ]


def check_tests() -> list[str]:
    findings: list[str] = []
    for script in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        if script.name not in ALL_DOCS:
            findings.append(f"docs: integration script {script.name} is not mentioned")
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    for target in sorted(set(re.findall(r"^(test-[a-z-]+):", makefile, re.M))):
        if f"`{target}`" not in ALL_DOCS and f"make {target}" not in ALL_DOCS:
            findings.append(f"docs: make target {target} is not mentioned")
    return findings


def main() -> int:
    findings = [
        *check_api(),
        *check_datamodel(),
        *check_roles(),
        *check_audit_actions(),
        *check_definitions(),
        *check_tests(),
    ]
    for finding in findings:
        print(finding)
    print(f"Docs consistency: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
