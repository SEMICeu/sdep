#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///
"""Reference data endpoints: platforms, competent authorities, areas.

Runs for the domain of the bearer token (its audience role, e.g. `sdep_ama`) and
for API_VERSION; a domain version that does not serve the reference data is
skipped. The token is loaded from ./tmp/.bearer_token.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))

# Which resources each domain version serves, see docs/API_TECH.md "Reference data"
ALL = ("platforms", "competent-authorities", "areas")
SERVED: dict[tuple[str, str], tuple[str, ...]] = {
    ("ama", "v1"): ALL,
    ("sta", "v1"): ALL,
    ("sta", "v2"): ALL,
    ("lma", "v2"): ALL,
    ("lsa", "v2"): ALL,
    ("ca", "v2"): ("platforms",),
}
# Collection key and ID field per resource
FIELDS = {
    "platforms": ("platforms", "platformId"),
    "competent-authorities": ("competentAuthorities", "competentAuthorityId"),
    "areas": ("areas", "areaId"),
}


@dataclass
class TestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is not set")
        sys.exit(1)
    return value


def load_bearer_token() -> str:
    if BEARER_TOKEN_FILE.exists():
        print(f"Loaded BEARER_TOKEN from {BEARER_TOKEN_FILE}")
        return BEARER_TOKEN_FILE.read_text(encoding="utf-8").strip()
    print(f"No {BEARER_TOKEN_FILE} file found")
    return ""


def token_domain(token: str) -> str | None:
    """The domain of the token's audience role; the payload is read, not verified."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        return None
    roles = claims.get("realm_access", {}).get("roles", [])
    domains = {domain for domain, _ in SERVED}
    return next((role.removeprefix("sdep_") for role in roles if role.removeprefix("sdep_") in domains), None)


def call(client: httpx.Client, url: str, token: str, **kwargs: Any) -> tuple[int, Any]:
    response = client.get(url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = None
    return response.status_code, body


def mark(stats: TestStats, ok: bool, passed_message: str, failed_message: str) -> None:
    stats.total += 1
    if ok:
        print(passed_message)
        stats.passed += 1
    else:
        print(failed_message)
        stats.failed += 1


def check_resource(client: httpx.Client, api: str, token: str, resource: str, stats: TestStats) -> None:
    key, id_field = FIELDS[resource]

    print(f"Test: GET /{resource}/count and GET /{resource}?limit=1")
    print("------------------------------------------------")
    code_count, count_body = call(client, f"{api}/{resource}/count", token)
    code, body = call(client, f"{api}/{resource}", token, params={"limit": 1})
    items = body.get(key) if isinstance(body, dict) else None
    count = count_body.get("count") if isinstance(count_body, dict) else None
    print(f"HTTP Status: count {code_count} ({count}), list {code}")
    ok = code_count == 200 and code == 200 and isinstance(count, int) and isinstance(items, list) and len(items) == min(count, 1)
    mark(stats, ok, f"Passed: /{resource} and /{resource}/count agree", f"Failed: {body}")
    print()

    print(f"Test: GET /{resource}/{{id}} is not served (404)")
    print("------------------------------------------------")
    # No read by ID: the list item carries every field
    code, _ = call(client, f"{api}/{resource}/{items[0][id_field] if items else 'sdep-test-unknown-id'}", token)
    print(f"HTTP Status: {code}")
    mark(stats, code == 404, f"Passed: /{resource}/{{id}} is not served", f"Failed: Expected 404, got {code}")
    print()


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v2")
    token = load_bearer_token()
    domain = token_domain(token)
    resources = SERVED.get((domain, api_version)) if domain else None
    if resources is None:
        print(f"Skipping reference data tests: {domain or 'this token'} {api_version} does not serve them")
        return 0

    api = f"{base_url}/api/{domain}/{api_version}"
    print(f"Testing reference data endpoints at: {api} ({', '.join(resources)})")
    print()

    stats = TestStats()
    with httpx.Client(timeout=30.0) as client:
        for resource in resources:
            check_resource(client, api, token, resource, stats)
        if "competent-authorities" not in resources:
            print("Test: GET /competent-authorities is not served (404)")
            print("------------------------------------------------")
            code, _ = call(client, f"{api}/competent-authorities", token)
            mark(stats, code == 404, "Passed: not served", f"Failed: Expected 404, got {code}")
            print()

    print("=======================================")
    print(f"Test Summary (reference data, {domain} {api_version}):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")
    if stats.failed == 0:
        print("All reference data tests passed!")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
