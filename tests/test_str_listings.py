#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///
"""STR listing endpoints (random checks): submit, read flagged, acknowledge.

The STR bearer token is loaded from ./tmp/.bearer_token; fixture areas are
created with the CA1 client credentials from the environment.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SHAPEFILE_PATH = REPO_ROOT / "test-data" / "shapefiles" / "Amsterdam.zip"
BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))
AUTH_API_VERSION = "v1"
CA_API_VERSION = "v2"

ADDRESS = {
    "thoroughfare": "Prinsengracht",
    "locatorDesignatorNumber": 263,
    "postCode": "1016GV",
    "postName": "Amsterdam",
    "fullAddress": "Prinsengracht 263, 1016GV Amsterdam",
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


def create_fixture_area(client: httpx.Client, base_url: str, ca_token: str, area_id: str, regulation: str) -> None:
    with SHAPEFILE_PATH.open("rb") as shapefile:
        response = client.post(
            f"{base_url}/api/ca/{CA_API_VERSION}/areas",
            headers={"Authorization": f"Bearer {ca_token}"},
            data={"areaId": area_id, "regulation": regulation},
            files={"file": ("Amsterdam.zip", shapefile, "application/zip")},
        )
    if response.status_code != 201:
        print(f"ERROR: Failed to create fixture area {area_id} (HTTP {response.status_code}): {response.text}", file=sys.stderr)
        sys.exit(1)


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


def error_types(body: Any) -> list[str | None]:
    results = body.get("results", []) if isinstance(body, dict) else []
    return [((r.get("errors") or {}).get("detail") or [{}])[0].get("type") for r in results]


def listing(listing_id: str, area_id: str, **overrides: Any) -> dict[str, Any]:
    item = {"listingId": listing_id, "areaId": area_id, "url": f"http://example.com/{listing_id}", "address": ADDRESS, "declaredAsShortTermRental": True}
    item.update(overrides)
    return item


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v2")
    bearer_token = load_bearer_token()
    api = f"{base_url}/api/str/{api_version}"
    print(f"Testing STR listing endpoints at: {api}/listings")
    print()
    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        ca_token = auth_token(client, base_url, env("CA1_CLIENT_ID"), env("CA1_CLIENT_SECRET"))
        if not ca_token:
            print("ERROR: Failed to get CA token for fixture creation", file=sys.stderr)
            return 1
        stamp = int(time.time() * 1000)
        listing_area = f"sdep-test-str-listing-area-{stamp}"
        activity_area = f"sdep-test-str-activity-area-{stamp}"
        create_fixture_area(client, base_url, ca_token, listing_area, "listing")
        create_fixture_area(client, base_url, ca_token, activity_area, "activity")
        print(f"Fixture areas: {listing_area} (listing), {activity_area} (activity)")
        print()

        print("Test 1: POST listings/bulk with a valid, an activity-only and an unknown area (200 partial)")
        print("------------------------------------------------")
        ok_id = f"sdep-test-str-listing-{stamp}"
        payload = {
            "listings": [
                listing(ok_id, listing_area, registrationNumber="REG-1"),
                listing(f"sdep-test-str-listing-reg-{stamp}", activity_area),
                listing(f"sdep-test-str-listing-nf-{stamp}", "00000000-0000-0000-0000-000000000000"),
            ]
        }
        code, body = call(client, "POST", f"{api}/listings/bulk", bearer_token, json=payload)
        print(f"HTTP Status: {code}: {brief(body)}")
        mark(
            stats,
            code == 200 and error_types(body) == [None, "regulation_error", "not_found_error"],
            "Test 1 passed: OK, regulation_error, not_found_error",
            f"Test 1 failed: Expected 200 with [OK, regulation_error, not_found_error], got {code} {error_types(body)}",
        )
        first_created = ((body.get("results") or [{}])[0].get("listing") or {}).get("createdAt") if isinstance(body, dict) else None
        print()

        print("Test 2: Resubmitting a pending listing is a correction (201, new createdAt)")
        print("------------------------------------------------")
        code, body = call(client, "POST", f"{api}/listings/bulk", bearer_token, json={"listings": [listing(ok_id, listing_area, listingName="Corrected")]})
        item = ((body.get("results") or [{}])[0].get("listing") or {}) if isinstance(body, dict) else {}
        print(f"HTTP Status: {code}: {brief(item)}")
        mark(
            stats,
            code == 201 and item.get("status") == "pending" and item.get("listingName") == "Corrected" and item.get("createdAt") != first_created,
            "Test 2 passed: New pending version",
            f"Test 2 failed: Expected 201 with a new pending version, got {code}",
        )
        print()

        print("Test 3: GET listings and listings/count (flagged scope, empty result is valid)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{api}/listings", bearer_token, params={"areaId": listing_area})
        code_count, count_body = call(client, "GET", f"{api}/listings/count", bearer_token, params={"areaId": listing_area})
        items = body.get("listings") if isinstance(body, dict) else None
        print(f"HTTP Status: list {code}, count {code_count} ({brief(count_body)})")
        mark(
            stats,
            code == 200 and isinstance(items, list) and all(i.get("status") == "flagged" for i in items) and isinstance(count_body.get("count"), int) and len(items) == min(count_body["count"], PAGE_LIMIT),
            "Test 3 passed: Only flagged listings, count matches",
            f"Test 3 failed: {code}/{code_count} {compact_json(body)[:200]}",
        )
        print()

        print("Test 4: Acknowledging an unknown listing is refused (422 not_found_error)")
        print("------------------------------------------------")
        code, body = call(client, "POST", f"{api}/listing-acknowledgements/bulk", bearer_token, json={"acknowledgements": [{"listingId": f"sdep-test-unknown-{stamp}", "createdAt": "2026-09-07T08:00:00Z"}]})
        print(f"HTTP Status: {code}: {error_types(body)}")
        mark(stats, code == 422 and error_types(body) == ["not_found_error"], "Test 4 passed: not_found_error", f"Test 4 failed: Expected 422 not_found_error, got {code} {error_types(body)}")
        print()

        print("Test 5: An empty batch is rejected (422)")
        print("------------------------------------------------")
        code, body = call(client, "POST", f"{api}/listings/bulk", bearer_token, json={"listings": []})
        print(f"HTTP Status: {code}")
        mark(stats, code == 422, "Test 5 passed: Empty batch rejected", f"Test 5 failed: Expected 422, got {code}")
        print()

        print("Test 6: A non-UTC createdAtFrom filter is rejected (400)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{api}/listings", bearer_token, params={"createdAtFrom": "2026-09-01T00:00:00+02:00"})
        print(f"HTTP Status: {code}")
        mark(stats, code == 400, "Test 6 passed: 400 for a non-UTC filter", f"Test 6 failed: Expected 400, got {code}")
        print()

    print("=======================================")
    print("Test Summary (STR listings):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")
    if stats.failed == 0:
        print("All STR listing tests passed!")
        return 0
    print("Some STR listing tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
