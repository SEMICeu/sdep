#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///
"""Listing lifecycle (random checks) through the LSA, STR, CA, LMA and STA APIs.

The LSA bearer token is loaded from ./tmp/.bearer_token; the other audiences
authenticate with their client credentials from the environment.
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
# API_VERSION selects the LSA version under test. The other audiences stay fixed.
LSA_API_VERSION = os.getenv("API_VERSION", "v2")
CA_API_VERSION = "v2"
STR_API_VERSION = "v2"
LMA_API_VERSION = "v2"
STA_API_VERSION = "v2"

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


def listing_ids(body: Any) -> list[str]:
    items = body.get("listings") if isinstance(body, dict) else None
    return [item.get("listingId") for item in items] if isinstance(items, list) else []


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    lsa_token = load_bearer_token()
    print(f"Testing the listing lifecycle at: {base_url}")
    print()
    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        ca_token = auth_token(client, base_url, env("CA1_CLIENT_ID"), env("CA1_CLIENT_SECRET"))
        str_token = auth_token(client, base_url, env("STR_CLIENT_ID"), env("STR_CLIENT_SECRET"))
        lma_token = auth_token(client, base_url, env("LMA_CLIENT_ID"), env("LMA_CLIENT_SECRET"))
        sta_token = auth_token(client, base_url, env("STA_CLIENT_ID"), env("STA_CLIENT_SECRET"))
        if not (ca_token and str_token and lma_token and sta_token):
            print("ERROR: Failed to get CA, STR, LMA or STA token", file=sys.stderr)
            return 1

        stamp = int(time.time() * 1000)
        area_id = f"sdep-test-lsa-area-{stamp}"
        create_fixture_area(client, base_url, ca_token, area_id, "listing")
        id_a = f"sdep-test-lsa-a-{stamp}"
        id_b = f"sdep-test-lsa-b-{stamp}"
        print(f"Fixture area: {area_id}; listings: {id_a}, {id_b}")
        print()

        lsa = f"{base_url}/api/lsa/{LSA_API_VERSION}"
        str_api = f"{base_url}/api/str/{STR_API_VERSION}"

        print("Test 1: STR submits two listings (POST /str/v2/listings/bulk -> 201)")
        print("------------------------------------------------")
        payload = {
            "listings": [
                {"listingId": id_a, "areaId": area_id, "url": f"http://example.com/{id_a}", "address": ADDRESS, "declaredAsShortTermRental": True, "registrationNumber": "REG-A"},
                {"listingId": id_b, "areaId": area_id, "url": f"http://example.com/{id_b}", "address": ADDRESS, "declaredAsShortTermRental": False},
            ]
        }
        code, body = call(client, "POST", f"{str_api}/listings/bulk", str_token, json=payload)
        print(f"HTTP Status: {code}: {brief(body)}")
        submitted = {r.get("listingId"): r.get("listing", {}) for r in body.get("results", [])} if isinstance(body, dict) else {}
        mark(stats, code == 201 and set(submitted) == {id_a, id_b}, "Test 1 passed: Both listings are pending", f"Test 1 failed: Expected 201, got {code}")
        platform_id = submitted.get(id_a, {}).get("platformId", "")
        print()

        print("Test 2: LSA sees the pending listings (GET /lsa/v2/listings?areaId, /count)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{lsa}/listings", lsa_token, params={"areaId": area_id})
        code_count, count_body = call(client, "GET", f"{lsa}/listings/count", lsa_token, params={"areaId": area_id, "platformId": platform_id})
        print(f"HTTP Status: list {code}, count {code_count} ({brief(count_body)})")
        mark(stats, code == 200 and set(listing_ids(body)) == {id_a, id_b} and count_body.get("count") == 2, "Test 2 passed: Two pending listings", f"Test 2 failed: {compact_json(body)[:200]}")
        print()

        print("Test 3: LSA screens them (POST /lsa/v2/listing-screenings/bulk -> 201)")
        print("------------------------------------------------")
        screenings = {
            "screenings": [
                {"platformId": platform_id, "listingId": id_a, "createdAt": submitted.get(id_a, {}).get("createdAt"), "flags": ["UNK"]},
                {"platformId": platform_id, "listingId": id_b, "createdAt": submitted.get(id_b, {}).get("createdAt"), "flags": []},
            ]
        }
        code, body = call(client, "POST", f"{lsa}/listing-screenings/bulk", lsa_token, json=screenings)
        print(f"HTTP Status: {code}: {brief(body)}")
        screened = {r.get("listingId"): r.get("listing", {}) for r in body.get("results", [])} if isinstance(body, dict) else {}
        mark(
            stats,
            code == 201 and screened.get(id_a, {}).get("status") == "flagged" and screened.get(id_b, {}).get("status") == "clear",
            "Test 3 passed: a is flagged, b is clear",
            f"Test 3 failed: Expected 201 with flagged/clear, got {code}",
        )
        print()

        print("Test 4: The LSA queue for the area is empty")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{lsa}/listings/count", lsa_token, params={"areaId": area_id})
        print(f"HTTP Status: {code}: {brief(body)}")
        mark(stats, code == 200 and body.get("count") == 0, "Test 4 passed: Nothing pending", f"Test 4 failed: {compact_json(body)}")
        print()

        print("Test 5: STR sees only the flagged listing (GET /str/v2/listings?areaId)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{str_api}/listings", str_token, params={"areaId": area_id})
        print(f"HTTP Status: {code}: {brief(body)}")
        mark(stats, code == 200 and listing_ids(body) == [id_a], "Test 5 passed: Only a is flagged", f"Test 5 failed: {listing_ids(body)}")
        print()

        print("Test 6: STR acknowledges a (POST /str/v2/listing-acknowledgements/bulk -> 201), retry -> 422 conflict_error")
        print("------------------------------------------------")
        acknowledgement = {"acknowledgements": [{"listingId": id_a, "createdAt": screened.get(id_a, {}).get("createdAt")}]}
        code, body = call(client, "POST", f"{str_api}/listing-acknowledgements/bulk", str_token, json=acknowledgement)
        acknowledged = (body.get("results") or [{}])[0].get("listing", {}) if isinstance(body, dict) else {}
        code_retry, retry_body = call(client, "POST", f"{str_api}/listing-acknowledgements/bulk", str_token, json=acknowledgement)
        retry_type = ((retry_body.get("results") or [{}])[0].get("errors", {}).get("detail") or [{}])[0].get("type") if isinstance(retry_body, dict) else None
        print(f"HTTP Status: {code} then {code_retry} ({retry_type})")
        mark(
            stats,
            code == 201 and acknowledged.get("status") == "acknowledged" and code_retry == 422 and retry_type == "conflict_error",
            "Test 6 passed: Acknowledged once, retry refused as no longer current",
            f"Test 6 failed: {code}/{code_retry}: {compact_json(retry_body)[:200]}",
        )
        print()

        print("Test 7: CA sees the acknowledged listing in its area (GET /ca/v2/listings?flags=UNK)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{base_url}/api/ca/{CA_API_VERSION}/listings", ca_token, params={"areaId": area_id, "flags": "UNK,EXP"})
        print(f"HTTP Status: {code}: {brief(body)}")
        mark(stats, code == 200 and listing_ids(body) == [id_a], "Test 7 passed: CA sees a", f"Test 7 failed: {listing_ids(body)}")
        print()

        print("Test 8: LMA and STA see both listings; status filter narrows (GET /lma/v2/listings, /sta/v2/listings)")
        print("------------------------------------------------")
        ok = True
        for label, version, token in (("lma", LMA_API_VERSION, lma_token), ("sta", STA_API_VERSION, sta_token)):
            code, body = call(client, "GET", f"{base_url}/api/{label}/{version}/listings", token, params={"areaId": area_id})
            code_clear, clear_body = call(client, "GET", f"{base_url}/api/{label}/{version}/listings", token, params={"areaId": area_id, "status": "clear"})
            print(f"{label}: HTTP {code} {sorted(listing_ids(body))}, status=clear HTTP {code_clear} {listing_ids(clear_body)}")
            ok = ok and code == 200 and set(listing_ids(body)) == {id_a, id_b} and code_clear == 200 and listing_ids(clear_body) == [id_b]
        mark(stats, ok, "Test 8 passed: LMA and STA see every status", "Test 8 failed: see above")
        print()

        print("Test 9: A stale version token is refused (422 conflict_error, loc createdAt)")
        print("------------------------------------------------")
        stale = {"screenings": [{"platformId": platform_id, "listingId": id_b, "createdAt": submitted.get(id_b, {}).get("createdAt"), "flags": ["EXP"]}]}
        code, body = call(client, "POST", f"{lsa}/listing-screenings/bulk", lsa_token, json=stale)
        detail = ((body.get("results") or [{}])[0].get("errors", {}).get("detail") or [{}])[0] if isinstance(body, dict) else {}
        print(f"HTTP Status: {code}: {brief(detail)}")
        mark(stats, code == 422 and detail.get("type") == "conflict_error" and detail.get("loc") == ["createdAt"], "Test 9 passed: Stale token refused", f"Test 9 failed: {code} {compact_json(detail)}")
        print()

        print("Test 10: STR token gets 403 Forbidden on the LSA API (role isolation)")
        print("------------------------------------------------")
        code, body = call(client, "GET", f"{lsa}/listings/count", str_token)
        print(f"HTTP Status: {code}")
        mark(stats, code == 403, "Test 10 passed: STR is not a listing screening authority", f"Test 10 failed: Expected 403, got {code}")
        print()

    print("=======================================")
    print("Test Summary (listing lifecycle):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")
    if stats.failed == 0:
        print("All listing lifecycle tests passed!")
        return 0
    print("Some listing lifecycle tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
