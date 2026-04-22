"""Freeze the `/api/v0/openapi.json` contract for end users.

If the public API contract changes intentionally, refresh the committed snapshot
with `make openapi-snapshot-update` from `backend/Makefile` and review the diff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.api.v0.main import app_v0

SNAPSHOT_PATH = Path(__file__).with_name("fixtures") / "openapi_v0.snapshot.json"
PLACEHOLDER_VERSION = "<frozen-version>"
PLACEHOLDER_TOKEN_URL = "<token-url>"


def _normalized_openapi() -> dict[str, Any]:
    """Return the schema with environment-derived values normalized."""
    app_v0.openapi_schema = None
    schema = app_v0.openapi()

    schema["info"]["version"] = PLACEHOLDER_VERSION

    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    for scheme in security_schemes.values():
        client_credentials = scheme.get("flows", {}).get("clientCredentials", {})
        if "tokenUrl" in client_credentials:
            client_credentials["tokenUrl"] = PLACEHOLDER_TOKEN_URL

    return schema


def _serialize_openapi(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_openapi_snapshot() -> Path:
    """Write the normalized OpenAPI snapshot used by the contract test."""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(_serialize_openapi(_normalized_openapi()))
    return SNAPSHOT_PATH


def test_openapi_schema_is_frozen() -> None:
    """Detect unreviewed changes in the committed OpenAPI contract snapshot."""
    expected = SNAPSHOT_PATH.read_text()
    actual = _serialize_openapi(_normalized_openapi())

    assert actual == expected, (
        "OpenAPI schema changed. If this is intentional, refresh the snapshot "
        "with `make openapi-snapshot-update` from `backend/Makefile` and review "
        "the diff before committing."
    )
