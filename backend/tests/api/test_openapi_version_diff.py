"""Freeze the generated diff between consecutive API versions.

The diff is derived from the committed OpenAPI snapshots (see
``test_openapi_schema_frozen.py``), never from a live app, so it cannot describe a
contract the code no longer serves. When the contract changes intentionally, refresh the
snapshots with `make api-snapshot-update` and this document with `make api-diff-update`.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import pytest
from app.api.domain_registry import API_DOMAINS, ApiDomain

from tests.api.test_openapi_schema_frozen import snapshot_path

DIFF_PATH = Path(__file__).resolve().parents[3] / "docs" / "API_DIFF.md"

# Consecutive version pairs to document. One line per additional pair (e.g. a future str_v2).
VERSION_PAIRS: tuple[tuple[str, str], ...] = (("ca_v1", "ca_v2"),)

HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)


def _domain(snapshot_name: str) -> ApiDomain:
    """Resolve a snapshot name ("ca_v2") to its registry entry, for labels."""
    domain, _, version = snapshot_name.rpartition("_")
    root_path = f"/api/{domain}/{version}"

    return next(entry for entry in API_DOMAINS if entry.root_path == root_path)


def _load(snapshot_name: str) -> dict[str, Any]:
    return json.loads(snapshot_path(snapshot_name).read_text())


def _operations(schema: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Flatten paths into {(METHOD, path): operation}."""
    operations = {}
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS:
                operations[(method.upper(), path)] = operation

    return operations


def _type_label(schema: dict[str, Any]) -> str:
    """Short type name for a parameter schema.

    Optional query parameters are generated as ``anyOf: [T, null]``, so the null branch is
    dropped to keep the rendered type readable.
    """
    if not schema:
        return "unknown"

    variants = [
        variant for variant in schema.get("anyOf", []) if variant.get("type") != "null"
    ]
    if variants:
        return " or ".join(_type_label(variant) for variant in variants)

    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]

    type_name = schema.get("type", "object")
    if type_name == "array":
        return f"array of {_type_label(schema.get('items', {}))}"

    output_format = schema.get("format")

    return f"{type_name}, {output_format}" if output_format else type_name


def _parameter_label(parameter: dict[str, Any]) -> str:
    requirement = "required" if parameter.get("required") else "optional"
    location = parameter.get("in", "query")
    type_label = _type_label(parameter.get("schema", {}))

    return f"{requirement} {location} parameter `{parameter['name']}` ({type_label})"


def _by_name(operation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        parameter["name"]: parameter for parameter in operation.get("parameters", [])
    }


def _diff_operation(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Return one sentence per difference between two versions of the same operation."""
    changes: list[str] = []

    if old.get("operationId") != new.get("operationId"):
        changes.append(
            f"Renamed `operationId` from `{old.get('operationId')}` "
            f"to `{new.get('operationId')}`"
        )

    if bool(old.get("deprecated")) != bool(new.get("deprecated")):
        state = "deprecated" if new.get("deprecated") else "no longer deprecated"
        changes.append(f"Marked {state}")

    old_parameters, new_parameters = _by_name(old), _by_name(new)

    for name in sorted(set(new_parameters) - set(old_parameters)):
        changes.append(f"Added {_parameter_label(new_parameters[name])}")

    for name in sorted(set(old_parameters) - set(new_parameters)):
        changes.append(f"Removed {_parameter_label(old_parameters[name])}")

    for name in sorted(set(old_parameters) & set(new_parameters)):
        old_parameter, new_parameter = old_parameters[name], new_parameters[name]
        if bool(old_parameter.get("required")) != bool(new_parameter.get("required")):
            state = "required" if new_parameter.get("required") else "optional"
            changes.append(f"Made parameter `{name}` {state}")
        if old_parameter.get("schema") != new_parameter.get("schema"):
            changes.append(
                f"Changed the type of parameter `{name}` from "
                f"`{_type_label(old_parameter.get('schema', {}))}` to "
                f"`{_type_label(new_parameter.get('schema', {}))}`"
            )

    if old.get("requestBody") != new.get("requestBody"):
        changes.append("Changed the request body")

    old_responses, new_responses = old.get("responses", {}), new.get("responses", {})

    for code in sorted(set(new_responses) - set(old_responses)):
        changes.append(f"Added the `{code}` response")

    for code in sorted(set(old_responses) - set(new_responses)):
        changes.append(f"Removed the `{code}` response")

    for code in sorted(set(old_responses) & set(new_responses)):
        if old_responses[code] != new_responses[code]:
            changes.append(f"Changed the `{code}` response")

    if old.get("security") != new.get("security"):
        changes.append("Changed the security requirements")

    if old.get("summary") != new.get("summary"):
        changes.append("Updated the endpoint summary")

    if old.get("description") != new.get("description"):
        changes.append("Updated the endpoint description")

    return changes


def _changed_schemas(old: dict[str, Any], new: dict[str, Any]) -> dict[str, list[str]]:
    old_schemas = old.get("components", {}).get("schemas", {})
    new_schemas = new.get("components", {}).get("schemas", {})

    return {
        "added": sorted(set(new_schemas) - set(old_schemas)),
        "removed": sorted(set(old_schemas) - set(new_schemas)),
        "modified": sorted(
            name
            for name in set(old_schemas) & set(new_schemas)
            if old_schemas[name] != new_schemas[name]
        ),
        "unchanged": sorted(
            name
            for name in set(old_schemas) & set(new_schemas)
            if old_schemas[name] == new_schemas[name]
        ),
    }


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    """Render a GitHub table padded the way mdformat would leave it."""
    widths = [
        max(len(row[column]) for row in [header, *rows])
        for column in range(len(header))
    ]
    separator = ["-" * width for width in widths]

    return [
        "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) + " |"
        for row in [header, separator, *rows]
    ]


def _render_pair(old_name: str, new_name: str) -> list[str]:
    return _render_body(
        _load(old_name),
        _load(new_name),
        _domain(old_name).label,
        _domain(new_name).label,
    )


def _render_body(
    old: dict[str, Any], new: dict[str, Any], old_label: str, new_label: str
) -> list[str]:
    """Render one version pair. Takes loaded documents so it is testable in isolation."""
    old_operations, new_operations = _operations(old), _operations(new)
    added = sorted(set(new_operations) - set(old_operations))
    removed = sorted(set(old_operations) - set(new_operations))

    modified: list[tuple[tuple[str, str], list[str]]] = []
    unchanged = 0
    for key in sorted(set(old_operations) & set(new_operations)):
        changes = _diff_operation(old_operations[key], new_operations[key])
        if changes:
            modified.append((key, changes))
        else:
            unchanged += 1

    schemas = _changed_schemas(old, new)
    old_security = old.get("components", {}).get("securitySchemes", {})
    new_security = new.get("components", {}).get("securitySchemes", {})

    lines = [f"## {old_label} to {new_label}", ""]
    lines += _table(
        ["Category", "Added", "Removed", "Modified", "Unchanged"],
        [
            [
                "Operations",
                str(len(added)),
                str(len(removed)),
                str(len(modified)),
                str(unchanged),
            ],
            [
                "Component schemas",
                str(len(schemas["added"])),
                str(len(schemas["removed"])),
                str(len(schemas["modified"])),
                str(len(schemas["unchanged"])),
            ],
            [
                "Security schemes",
                str(len(set(new_security) - set(old_security))),
                str(len(set(old_security) - set(new_security))),
                str(
                    sum(
                        1
                        for name in set(old_security) & set(new_security)
                        if old_security[name] != new_security[name]
                    )
                ),
                str(
                    sum(
                        1
                        for name in set(old_security) & set(new_security)
                        if old_security[name] == new_security[name]
                    )
                ),
            ],
        ],
    )
    lines.append("")

    if added or removed:
        lines += ["---", "", "### Added and Removed Operations", ""]
        for method, path in added:
            lines.append(f"- Added `{method} {path}`")
        for method, path in removed:
            lines.append(f"- Removed `{method} {path}`")
        lines.append("")

    if modified:
        lines += ["---", "", "### Modified Operations", ""]
        for (method, path), changes in modified:
            lines += ["---", "", f"**`{method} {path}`**", ""]
            lines += [f"- {change}" for change in changes]
            lines.append("")

    if schemas["added"] or schemas["removed"] or schemas["modified"]:
        lines += ["---", "", "### Component Schemas", ""]
        for name in schemas["added"]:
            lines.append(f"- Added `{name}`")
        for name in schemas["removed"]:
            lines.append(f"- Removed `{name}`")
        for name in schemas["modified"]:
            lines.append(f"- Changed `{name}`")
        lines.append("")

    old_description = old.get("info", {}).get("description", "")
    new_description = new.get("info", {}).get("description", "")
    if old_description != new_description:
        lines += ["---", "", "### API Description", ""]
        lines.append(f"- {old_label}: {old_description}")
        lines.append(f"- {new_label}: {new_description}")
        lines.append("")

    return lines


def render_version_diff() -> str:
    """Render the full diff document for every configured version pair."""
    lines = [
        "<h1>API Version Diff</h1>",
        "",
        "Differences between consecutive API versions, generated from the committed OpenAPI",
        "snapshots in `backend/tests/api/fixtures/`. Refresh with `make api-diff-update` from",
        "`backend/`. Do not edit by hand.",
        "",
        "For the versioning rules behind these differences, see [API](API.md).",
        "",
    ]

    for old_name, new_name in VERSION_PAIRS:
        lines += _render_pair(old_name, new_name)

    return "\n".join(lines).rstrip("\n") + "\n"


def write_version_diff() -> Path | None:
    """Write the generated diff document when it changed. Returns the path if rewritten."""
    content = render_version_diff()
    if DIFF_PATH.exists() and DIFF_PATH.read_text() == content:
        return None

    DIFF_PATH.write_text(content)

    return DIFF_PATH


def report_version_diff() -> str:
    """Write the diff and describe what changed. Entry point for `make api-diff-update`."""
    written = write_version_diff()
    if written is None:
        return "✅ API version diff already up to date, no changes made"

    return f"✅ API version diff updated: {written}"


def test_version_diff_is_current() -> None:
    """Detect a generated version diff that no longer matches the frozen snapshots."""
    expected = DIFF_PATH.read_text()
    actual = render_version_diff()

    if actual != expected:
        diff = "\n".join(
            difflib.unified_diff(
                expected.splitlines(),
                actual.splitlines(),
                fromfile="docs/API_DIFF.md",
                tofile="generated",
                lineterm="",
            )
        )
        banner = "=" * 72
        # First line is visible in `make test` (--tb=line); full diff shows in `make test-verbose`
        pytest.fail(
            "docs/API_DIFF.md is out of date. "
            "Run `make api-diff-update` to refresh it."
            f"\n\n{banner}\n  API version diff\n{banner}\n\n{diff}\n\n{banner}"
        )


def _spec(
    paths: dict[str, Any], schemas: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Minimal OpenAPI document, enough to exercise the diff logic."""
    return {
        "info": {"description": "Test API."},
        "paths": paths,
        "components": {"schemas": schemas or {}},
    }


def _activities(parameters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "/activities": {
            "get": {
                "operationId": "getActivities",
                "parameters": parameters or [],
                "responses": {"200": {"description": "OK"}},
            }
        }
    }


OPTIONAL_FILTER = {
    "name": "areaId",
    "in": "query",
    "required": False,
    "schema": {"anyOf": [{"type": "string"}, {"type": "null"}]},
}


class TestDiffOperation:
    """Unit coverage for the per-operation comparison."""

    def test_identical_operations_report_no_changes(self) -> None:
        operation = _activities([OPTIONAL_FILTER])["/activities"]["get"]

        assert _diff_operation(operation, operation) == []

    def test_added_optional_parameter_is_reported_with_its_type(self) -> None:
        old = _activities()["/activities"]["get"]
        new = _activities([OPTIONAL_FILTER])["/activities"]["get"]

        assert _diff_operation(old, new) == [
            "Added optional query parameter `areaId` (string)"
        ]

    def test_removed_parameter_is_reported(self) -> None:
        old = _activities([OPTIONAL_FILTER])["/activities"]["get"]
        new = _activities()["/activities"]["get"]

        assert _diff_operation(old, new) == [
            "Removed optional query parameter `areaId` (string)"
        ]

    def test_parameter_becoming_required_is_reported(self) -> None:
        old = _activities([OPTIONAL_FILTER])["/activities"]["get"]
        new = _activities([{**OPTIONAL_FILTER, "required": True}])["/activities"]["get"]

        assert _diff_operation(old, new) == ["Made parameter `areaId` required"]

    def test_changed_response_is_reported(self) -> None:
        old = _activities()["/activities"]["get"]
        new = _activities()["/activities"]["get"] | {
            "responses": {"200": {"description": "Changed"}, "404": {}}
        }

        assert _diff_operation(old, new) == [
            "Added the `404` response",
            "Changed the `200` response",
        ]

    def test_renamed_operation_id_is_reported(self) -> None:
        old = _activities()["/activities"]["get"]
        new = _activities()["/activities"]["get"] | {"operationId": "getActivitiesV2"}

        assert _diff_operation(old, new) == [
            "Renamed `operationId` from `getActivities` to `getActivitiesV2`"
        ]


class TestDiffDocument:
    """Unit coverage for the rendered document."""

    def test_added_and_removed_paths_are_listed(self) -> None:
        old = _spec(_activities())
        new = _spec({"/areas": {"get": {"operationId": "getAreas", "responses": {}}}})

        rendered = "\n".join(_render_body(old, new, "v1", "v2"))

        assert "- Added `GET /areas`" in rendered
        assert "- Removed `GET /activities`" in rendered

    def test_changed_component_schema_is_listed(self) -> None:
        old = _spec(_activities(), {"Activity": {"type": "object"}})
        new = _spec(
            _activities(), {"Activity": {"type": "object", "title": "Activity"}}
        )

        rendered = "\n".join(_render_body(old, new, "v1", "v2"))

        assert "- Changed `Activity`" in rendered

    def test_identical_specs_render_only_the_summary(self) -> None:
        spec = _spec(_activities([OPTIONAL_FILTER]), {"Activity": {"type": "object"}})

        rendered = "\n".join(_render_body(spec, spec, "v1", "v2"))

        assert "###" not in rendered
        assert (
            "| Operations        | 0     | 0       | 0        | 1         |" in rendered
        )
