"""Freeze the OpenAPI contract for each API domain.

If the public API contract changes intentionally, refresh the committed snapshots
with `make openapi-snapshot-update` from `backend/Makefile` and review the diff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from app.api.domains.auth.v1 import app_auth_v1
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.str.v1 import app_str_v1

if TYPE_CHECKING:
    from fastapi import FastAPI

FIXTURES_DIR = Path(__file__).with_name("fixtures")
PLACEHOLDER_VERSION = "<frozen-version>"
PLACEHOLDER_TOKEN_URL = "<token-url>"

DOMAIN_APPS: dict[str, FastAPI] = {
    "auth_v1": app_auth_v1,
    "ca_v1": app_ca_v1,
    "str_v1": app_str_v1,
}


def _snapshot_path(domain: str) -> Path:
    return FIXTURES_DIR / f"openapi_{domain}.snapshot.json"


def _normalized_openapi(app: FastAPI) -> dict[str, Any]:
    """Return the schema with environment-derived values normalized."""
    app.openapi_schema = None
    schema = app.openapi()

    schema["info"]["version"] = PLACEHOLDER_VERSION

    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    for scheme in security_schemes.values():
        client_credentials = scheme.get("flows", {}).get("clientCredentials", {})
        if "tokenUrl" in client_credentials:
            client_credentials["tokenUrl"] = PLACEHOLDER_TOKEN_URL

    return schema


def _serialize_openapi(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_openapi_snapshots() -> list[Path]:
    """Write normalized OpenAPI snapshots for all domains."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for domain, app in DOMAIN_APPS.items():
        path = _snapshot_path(domain)
        path.write_text(_serialize_openapi(_normalized_openapi(app)))
        paths.append(path)
    return paths


def write_openapi_snapshot() -> Path:
    """Legacy entry point for Makefile compatibility."""
    paths = write_openapi_snapshots()
    return paths[0].parent


@pytest.mark.parametrize("domain", list(DOMAIN_APPS.keys()))
def test_openapi_schema_is_frozen(domain: str) -> None:
    """Detect unreviewed changes in the committed OpenAPI contract snapshot."""
    path = _snapshot_path(domain)
    app = DOMAIN_APPS[domain]
    expected = path.read_text()
    actual = _serialize_openapi(_normalized_openapi(app))

    assert actual == expected, (
        f"OpenAPI schema for {domain} changed. If this is intentional, refresh "
        "the snapshots with `make openapi-snapshot-update` from `backend/Makefile` "
        "and review the diff before committing."
    )
