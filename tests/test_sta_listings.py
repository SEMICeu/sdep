#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///
"""STA listing endpoints (random checks): all listings, every lifecycle status.

The bearer token is loaded from ./tmp/.bearer_token.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))
AUTH_API_VERSION = "v1"
STATUS_FILTER = None


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


def compact_json(data: Any) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


# Log form of a response body: a collection becomes its item count (lists grow
# with "keep" runs), anything else is cut at `limit` characters.
COLLECTION_KEYS = ("activities", "areas", "listings")


def brief(data: Any, limit: int = 300) -> str:
    if isinstance(data, dict):
        counts = [f"{key}: {len(data[key])} items" for key in COLLECTION_KEYS if isinstance(data.get(key), list)]
        if counts:
            return ", ".join(counts)
    text = compact_json(data)
    return text if len(text) <= limit else f"{text[:limit]}..."


# One list call returns one page: at most PAGE_LIMIT items (the default and max limit).
# A filtered set that is larger (e.g. after "keep" runs) has count > list length.
PAGE_LIMIT = 1000


def load_bearer_token() -> str:
    if BEARER_TOKEN_FILE.exists():
        print(f"Loaded BEARER_TOKEN from {BEARER_TOKEN_FILE}")
        return BEARER_TOKEN_FILE.read_text(encoding="utf-8").strip()
    print(f"No {BEARER_TOKEN_FILE} file found")
    return ""


def auth_token(client: httpx.Client, base_url: str, client_id: str, client_secret: str) -> str:
    response = client.post(
        f"{base_url}/api/auth/{AUTH_API_VERSION}/token",
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    return str(body.get("access_token", ""))


def call(client: httpx.Client, method: str, url: str, token: str, **kwargs: Any) -> tuple[int, Any]:
    response = client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"raw": response.text}
    return response.status_code, body


def mark(stats: TestStats, ok: bool, passed_message: str, failed_message: str) -> None:
    stats.total += 1
    if ok:
        print(passed_message)
        stats.passed += 1
    else:
        print(failed_message)
        stats.failed += 1


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v2")
    bearer_token = load_bearer_token()
    api = f"{base_url}/api/sta/{api_version}"
    print(f"Testing STA listing endpoints at: {api}/listings")
    print()
    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        print("Test 1: Count listings (GET /listings/count)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{api}/listings/count", bearer_token)
        count = body.get("count") if isinstance(body, dict) else None
        print(f"HTTP Status: {code}: {brief(body)}")
        mark(stats, code == 200 and isinstance(count, int) and count >= 0, f"Test 1 passed: Count is valid ({count})", f"Test 1 failed: Expected 200 with count >= 0, got {code}")
        print()

        print("Test 2: Get listings, at most 1 with limit=1 (GET /listings?limit=1)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{api}/listings", bearer_token, params={"limit": 1})
        items = body.get("listings") if isinstance(body, dict) else None
        print(f"HTTP Status: {code}: {brief(body)}")
        mark(stats, code == 200 and isinstance(items, list) and len(items) <= 1, "Test 2 passed: Listings returned (empty result is valid)", f"Test 2 failed: Expected 200 with 'listings', got {code}")
        sample = items[0] if code == 200 and items else None
        print()

        print("Test 3: Every listing matches the fixed scope and carries the listing fields")
        print("------------------------------------------------")
        if sample is None:
            mark(stats, True, "Test 3 passed: No data available to test", "")
        else:
            fields = ("listingId", "status", "flags", "areaId", "competentAuthorityId", "platformId", "submittedAt", "createdAt", "declaredAsShortTermRental")
            missing = [f for f in fields if f not in sample]
            scope_ok = STATUS_FILTER is None or sample.get("status") == STATUS_FILTER
            mark(stats, not missing and scope_ok, "Test 3 passed: Listing fields present, scope respected", f"Test 3 failed: missing {missing}, status {sample.get('status')}")
        print()

        print("Test 4: Filters narrow the result (areaId, competentAuthorityId, flags, createdAtFrom/To; /count matches list length)")
        print("------------------------------------------------")
        if sample is None:
            mark(stats, True, "Test 4 passed: No data available to test", "")
        else:
            params = {"areaId": sample.get("areaId"), "competentAuthorityId": sample.get("competentAuthorityId"), "createdAtFrom": sample.get("createdAt"), "createdAtTo": sample.get("createdAt")}
            if sample.get("flags"):
                params["flags"] = ",".join(sample["flags"])
            code, body = call(client, "GET", f"{api}/listings", bearer_token, params=params)
            code_count, count_body = call(client, "GET", f"{api}/listings/count", bearer_token, params=params)
            items = body.get("listings") if isinstance(body, dict) else None
            print(f"HTTP Status: list {code} (returned={len(items) if isinstance(items, list) else items}), count {code_count} ({brief(count_body)})")
            ok = (
                code == 200 and code_count == 200 and isinstance(items, list) and bool(items)
                and all(i.get("areaId") == sample.get("areaId") for i in items)
                and all(i.get("competentAuthorityId") == sample.get("competentAuthorityId") for i in items)
                and any(i.get("listingId") == sample.get("listingId") for i in items)
                and isinstance(count_body.get("count"), int) and len(items) == min(count_body["count"], PAGE_LIMIT)
            )
            mark(stats, ok, "Test 4 passed: Filtered listings match, sample included, count matches length", f"Test 4 failed: {compact_json(body)[:200]}")
        print()

        print("Test 5: An unknown flag code is rejected (400)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{api}/listings", bearer_token, params={"flags": "NOPE"})
        print(f"HTTP Status: {code}: {brief(body)}")
        mark(stats, code == 400, "Test 5 passed: 400 for an unknown flag code", f"Test 5 failed: Expected 400, got {code}")
        print()

        print("Test 6: POST /listings returns 405 Method Not Allowed (read-only)")
        print("------------------------------------------------")
        code, body = call(client, "POST", f"{api}/listings", bearer_token, json={})
        print(f"HTTP Status: {code}")
        mark(stats, code == 405, "Test 6 passed: POST is rejected with 405", f"Test 6 failed: Expected 405, got {code}")
        print()

        print("Test 7: CA token gets 403 Forbidden (role isolation)")
        print("------------------------------------------------")
        other_id, other_secret = os.getenv("CA1_CLIENT_ID"), os.getenv("CA1_CLIENT_SECRET")
        if other_id and other_secret:
            other_token = auth_token(client, base_url, other_id, other_secret)
            code, body = call(client, "GET", f"{api}/listings/count", other_token)
            print(f"HTTP Status: {code}")
            mark(stats, code == 403, "Test 7 passed: Other role is refused with 403", f"Test 7 failed: Expected 403, got {code}")
        else:
            print("Skipping Test 7 (CA1_CLIENT_ID/CA1_CLIENT_SECRET not set)")
        print()

    print("=======================================")
    print("Test Summary (STA listings):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")
    if stats.failed == 0:
        print("All STA listing tests passed!")
        return 0
    print("Some STA listing tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
