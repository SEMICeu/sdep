"""Verify OpenAPI example payloads resolve against seed SQL test data.

Every `areaId` / `competentAuthorityId` referenced in a "Try it out" example
(request body or response) must exist in `test-data/01-competent-authority.sql`
or `test-data/02-area-generated.sql`, except for the documented sentinel
`00000000-0000-0000-0000-000000000000` used to illustrate the area-not-found
NOK path.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.str.v1 import app_str_v1

REPO_ROOT = Path(__file__).resolve().parents[3]
CA_SQL = REPO_ROOT / "test-data" / "01-competent-authority.sql"
AREA_SQL = REPO_ROOT / "test-data" / "02-area-generated.sql"

SENTINEL_INVALID_AREA_ID = "00000000-0000-0000-0000-000000000000"

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
CA_ID_RE = re.compile(r"sdep-ca\d+")


def _load_valid_ca_ids() -> set[str]:
    return set(CA_ID_RE.findall(CA_SQL.read_text()))


def _load_valid_area_ids() -> set[str]:
    return set(UUID_RE.findall(AREA_SQL.read_text()))


def _walk(node, path: tuple[str, ...] = ()):
    """Yield (path, key, value) for every scalar leaf under an example tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                yield from _walk(v, (*path, str(k)))
            else:
                yield (*path, str(k)), k, v
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (dict, list)):
                yield from _walk(v, (*path, f"[{i}]"))
            else:
                yield (*path, f"[{i}]"), None, v


def _iter_examples(openapi: dict):
    """Yield (operation_id, location, example) for every example in the spec."""
    for path, methods in openapi.get("paths", {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            op_id = op.get("operationId", f"{method.upper()} {path}")

            rb = op.get("requestBody", {}) or {}
            for mt, mt_obj in (rb.get("content") or {}).items():
                if "example" in mt_obj:
                    yield op_id, f"requestBody[{mt}].example", mt_obj["example"]
                for name, ex in (mt_obj.get("examples") or {}).items():
                    if isinstance(ex, dict) and "value" in ex:
                        yield op_id, f"requestBody[{mt}].examples.{name}", ex["value"]

            for status_code, resp in (op.get("responses") or {}).items():
                for mt, mt_obj in (resp.get("content") or {}).items():
                    if "example" in mt_obj:
                        yield (
                            op_id,
                            f"responses.{status_code}[{mt}].example",
                            mt_obj["example"],
                        )
                    for name, ex in (mt_obj.get("examples") or {}).items():
                        if isinstance(ex, dict) and "value" in ex:
                            yield (
                                op_id,
                                f"responses.{status_code}[{mt}].examples.{name}",
                                ex["value"],
                            )


@pytest.fixture(scope="module")
def valid_area_ids() -> set[str]:
    ids = _load_valid_area_ids()
    assert ids, f"No area UUIDs parsed from {AREA_SQL}"
    return ids


@pytest.fixture(scope="module")
def valid_ca_ids() -> set[str]:
    ids = _load_valid_ca_ids()
    assert ids, f"No competent authority ids parsed from {CA_SQL}"
    return ids


@pytest.fixture(scope="module")
def openapi_specs() -> list[dict]:
    return [app_ca_v1.openapi(), app_str_v1.openapi()]


def test_openapi_area_ids_resolve_against_seed_sql(
    openapi_specs, valid_area_ids
) -> None:
    failures: list[str] = []
    for spec in openapi_specs:
        for op_id, location, example in _iter_examples(spec):
            for path, key, value in _walk(example):
                if key != "areaId" or not isinstance(value, str):
                    continue
                if value == SENTINEL_INVALID_AREA_ID:
                    continue
                if value not in valid_area_ids:
                    failures.append(
                        f"{op_id} @ {location} / {'.'.join(path)} = {value!r}"
                    )
    assert not failures, (
        "OpenAPI examples reference areaId values not in "
        "test-data/02-area-generated.sql:\n  " + "\n  ".join(failures)
    )


def test_openapi_competent_authority_ids_resolve_against_seed_sql(
    openapi_specs, valid_ca_ids
) -> None:
    failures: list[str] = []
    for spec in openapi_specs:
        for op_id, location, example in _iter_examples(spec):
            for path, key, value in _walk(example):
                if key != "competentAuthorityId" or not isinstance(value, str):
                    continue
                if value not in valid_ca_ids:
                    failures.append(
                        f"{op_id} @ {location} / {'.'.join(path)} = {value!r}"
                    )
    assert not failures, (
        "OpenAPI examples reference competentAuthorityId values not in "
        "test-data/01-competent-authority.sql:\n  " + "\n  ".join(failures)
    )
