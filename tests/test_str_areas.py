#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Test script for STR areas endpoints of the SDEP API.
# Expects BACKEND_BASE_URL environment variable to be set.
# Reads the bearer token written by test_auth_client (./tmp/.bearer_token), or the
# BEARER_TOKEN environment variable.
# Optionally accepts API_VERSION environment variable (defaults to v1).
# Tests:
#   - GET /str/areas/count (count areas)
#   - GET /str/areas (list areas with optional pagination)
#   - GET /str/areas/{areaId} (get specific area shapefile data)

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
# Bearer token is runtime state written by test_auth_client relative to the CURRENT
# working directory (./tmp/.bearer_token). Resolve it the same way so the test works
# when reused from a consuming repository, not just from sdep-app.
# SHAPEFILE_PATH stays REPO_ROOT-anchored - it is a static sdep-app asset.
BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))
SHAPEFILE_PATH = REPO_ROOT / "test-data" / "shapefiles" / "Amsterdam.zip"

FIXTURE_COUNT = 5


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


def load_bearer_token() -> str:
    token = os.getenv("BEARER_TOKEN", "")
    if token:
        return token
    if BEARER_TOKEN_FILE.exists():
        print(f"Loaded BEARER_TOKEN from {BEARER_TOKEN_FILE}")
        return BEARER_TOKEN_FILE.read_text(encoding="utf-8").strip()
    return ""


def auth_token(client: httpx.Client, base_url: str, api_version: str, client_id: str, client_secret: str) -> str:
    response = client.post(
        f"{base_url}/api/auth/{api_version}/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        return str(response.json().get("access_token", ""))
    except json.JSONDecodeError:
        return ""


def create_fixture_areas(
    client: httpx.Client,
    base_url: str,
    api_version: str,
    count: int,
    prefix: str,
) -> list[str]:
    # Uses the test CA client so created rows match sdep-test-* for cleanup. Mirrors
    # lib/create_fixture_areas.py; kept inline so this stays a standalone script.
    ca_token = auth_token(
        client,
        base_url,
        api_version,
        env("CA1_CLIENT_ID"),
        env("CA1_CLIENT_SECRET"),
    )
    if not ca_token:
        print("ERROR: Failed to get CA token for fixture creation", file=sys.stderr)
        sys.exit(1)

    timestamp = int(time.time() * 1000)
    area_ids = [f"{prefix}-{timestamp}-{index}" for index in range(1, count + 1)]

    for area_id in area_ids:
        with SHAPEFILE_PATH.open("rb") as shapefile:
            response = client.post(
                f"{base_url}/api/ca/{api_version}/areas",
                headers={"Authorization": f"Bearer {ca_token}"},
                data={"areaId": area_id},
                files={"file": ("Amsterdam.zip", shapefile, "application/zip")},
            )
        if response.status_code != 201:
            print(
                f"ERROR: Failed to create fixture area {area_id} "
                f"(HTTP {response.status_code}): {response.text}",
                file=sys.stderr,
            )
            sys.exit(1)

    return area_ids


def auth_headers(bearer_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v1")

    bearer_token = load_bearer_token()

    print("Testing STR areas endpoints")
    if bearer_token:
        print("Using Bearer token for authentication")
    else:
        print("No BEARER_TOKEN set - making unauthenticated request (should fail)")
    print()

    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        # --- Setup: create fixture areas so tests work on an empty DB ---
        print(f"Creating {FIXTURE_COUNT} fixture areas for STR tests...")
        fixture_ids = create_fixture_areas(
            client, base_url, api_version, FIXTURE_COUNT, "sdep-test-str-areas"
        )
        fixture_area_1 = fixture_ids[0]
        fixture_area_2 = fixture_ids[1]
        fixture_area_3 = fixture_ids[2]
        print("Fixture areas created")
        print()

        # --- GET /str/areas/count ---
        print("Test 1: Count areas")
        print("------------------------------------------------")
        stats.total += 1
        response = client.get(
            f"{base_url}/api/str/{api_version}/areas/count", headers=auth_headers(bearer_token)
        )
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = {"raw": response.text}
        print(f"Response: {compact_json(body)}")
        print(f"HTTP Status: {response.status_code}")
        print()
        if response.status_code == 200:
            actual_count = body.get("count")
            mark_ok = isinstance(actual_count, int) and actual_count >= FIXTURE_COUNT
            mark(
                stats,
                mark_ok,
                f"Test 1 passed: Areas count is correct (Expected minimal: {FIXTURE_COUNT}, Got: {actual_count})",
                f"Test 1 failed: Unexpected count value (Expected minimal: {FIXTURE_COUNT}, Got: {actual_count})",
            )
        elif response.status_code == 401 and not bearer_token:
            mark(stats, True, "Test 1 passed: Correctly rejected unauthenticated request (401)", "")
        else:
            mark(stats, False, "", f"Test 1 failed: Unexpected HTTP status {response.status_code}")
        print()

        # --- GET /str/areas ---
        first_area_id = fixture_area_1
        second_area_id = fixture_area_2
        third_area_id = fixture_area_3

        print("Test 2: GET all areas")
        print("------------------------------------------------")
        stats.total += 1
        response = client.get(
            f"{base_url}/api/str/{api_version}/areas", headers=auth_headers(bearer_token)
        )
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = {"raw": response.text}
        print(f"Response (first 500 chars): {compact_json(body)[:500]}...")
        print(f"HTTP Status: {response.status_code}")
        print()
        if response.status_code == 200:
            areas = body.get("areas")
            if isinstance(areas, list):
                # Capture IDs for the by-ID tests, falling back to fixture IDs.
                if len(areas) > 0 and areas[0].get("areaId"):
                    first_area_id = areas[0]["areaId"]
                if len(areas) > 1 and areas[1].get("areaId"):
                    second_area_id = areas[1]["areaId"]
                if len(areas) > 2 and areas[2].get("areaId"):
                    third_area_id = areas[2]["areaId"]
                mark(
                    stats,
                    len(areas) >= 1,
                    f"Test 2 passed: Retrieved {len(areas)} area(s)",
                    "Test 2 failed: No areas found in response",
                )
            else:
                mark(stats, False, "", "Test 2 failed: Response does not contain 'areas' field")
        elif response.status_code == 401 and not bearer_token:
            mark(stats, True, "Test 2 passed: Correctly rejected unauthenticated request (401)", "")
        else:
            mark(stats, False, "", f"Test 2 failed: Unexpected HTTP status {response.status_code}")
        print()

        print("Test 3: GET areas with pagination (offset=0, limit=1)")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.get(
                f"{base_url}/api/str/{api_version}/areas?offset=0&limit=1",
                headers=auth_headers(bearer_token),
            )
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {"raw": response.text}
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {response.status_code}")
            print()
            if response.status_code == 200:
                areas = body.get("areas") or []
                mark(
                    stats,
                    len(areas) == 1,
                    "Test 3 passed: Retrieved exactly 1 area with limit=1",
                    f"Test 3 failed: Expected 1 area but got {len(areas)}",
                )
            else:
                mark(stats, False, "", f"Test 3 failed: Unexpected HTTP status {response.status_code}")
        else:
            print("Skipping Test 3 (requires authentication)")
        print()

        print(
            "Test 4: Verify response structure "
            "(areaId, competentAuthorityId, competentAuthorityName, filename, createdAt)"
        )
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.get(
                f"{base_url}/api/str/{api_version}/areas?limit=1",
                headers=auth_headers(bearer_token),
            )
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {"raw": response.text}
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {response.status_code}")
            print()
            if response.status_code == 200:
                raw = compact_json(body)
                required = (
                    "areaId",
                    "competentAuthorityId",
                    "competentAuthorityName",
                    "filename",
                    "createdAt",
                )
                missing = [field for field in required if f'"{field}"' not in raw]
                mark(
                    stats,
                    not missing,
                    "Test 4 passed: Response contains all required fields",
                    f"Test 4 failed: Missing required fields in response: {missing}",
                )
            else:
                mark(stats, False, "", f"Test 4 failed: Unexpected HTTP status {response.status_code}")
        else:
            print("Skipping Test 4 (requires authentication)")
        print()

        # --- GET /str/areas/{areaId} ---
        print("Test 5: GET area with known areaId")
        print("------------------------------------------------")
        stats.total += 1
        target_area_id = first_area_id
        response = client.get(
            f"{base_url}/api/str/{api_version}/areas/{target_area_id}",
            headers=auth_headers(bearer_token),
        )
        print(f"HTTP Status: {response.status_code}")
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            content_disposition = response.headers.get("content-disposition", "")
            print(f"Content-Type: {content_type}")
            print(f"Content-Disposition: {content_disposition[:100]}...")
            if "application/zip" in content_type:
                mark(
                    stats,
                    "attachment" in content_disposition,
                    "Test 5 passed: Retrieved area with correct headers",
                    "Test 5 failed: Missing Content-Disposition attachment header",
                )
            else:
                mark(stats, False, "", "Test 5 failed: Expected Content-Type application/zip")
        elif response.status_code == 401 and not bearer_token:
            mark(stats, True, "Test 5 passed: Correctly rejected unauthenticated request (401)", "")
        else:
            mark(stats, False, "", f"Test 5 failed: Unexpected HTTP status {response.status_code}")
        print()

        print("Test 6: GET area with another known areaId")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token and second_area_id:
            response = client.get(
                f"{base_url}/api/str/{api_version}/areas/{second_area_id}",
                headers=auth_headers(bearer_token),
            )
            print(f"HTTP Status: {response.status_code}")
            if response.status_code == 200:
                mark(
                    stats,
                    "application/zip" in response.headers.get("content-type", ""),
                    "Test 6 passed: Retrieved area",
                    "Test 6 failed: Expected Content-Type application/zip",
                )
            else:
                mark(stats, False, "", f"Test 6 failed: Unexpected HTTP status {response.status_code}")
        else:
            print("Skipping Test 6 (no second area ID available)")
        print()

        print("Test 7: GET area with non-existent areaId (should return 404)")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.get(
                f"{base_url}/api/str/{api_version}/areas/99999999",
                headers=auth_headers(bearer_token),
            )
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {"raw": response.text}
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {response.status_code}")
            print()
            mark(
                stats,
                response.status_code == 404,
                "Test 7 passed: Correctly returned 404 for non-existent area",
                f"Test 7 failed: Expected 404 but got {response.status_code}",
            )
        else:
            print("Skipping Test 7 (requires authentication)")
        print()

        print("Test 8: Verify Content-Disposition contains filename")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token and third_area_id:
            response = client.get(
                f"{base_url}/api/str/{api_version}/areas/{third_area_id}",
                headers=auth_headers(bearer_token),
            )
            print(f"HTTP Status: {response.status_code}")
            if response.status_code == 200:
                content_disposition = response.headers.get("content-disposition", "")
                print(f"Content-Disposition: {content_disposition}")
                mark(
                    stats,
                    "filename=" in content_disposition,
                    "Test 8 passed: Content-Disposition contains filename",
                    "Test 8 failed: Content-Disposition does not contain filename",
                )
            else:
                mark(stats, False, "", f"Test 8 failed: Unexpected HTTP status {response.status_code}")
        else:
            print("Skipping Test 8 (no third area ID available)")
        print()

    print("=======================================")
    print("Test Summary (STR areas):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All STR areas endpoint tests passed!")
        return 0

    print("Some STR areas endpoint tests failed!")
    return 1


def mark(stats: TestStats, ok: bool, passed_message: str, failed_message: str) -> None:
    if ok:
        print(passed_message)
        stats.passed += 1
    else:
        print(failed_message)
        stats.failed += 1


if __name__ == "__main__":
    raise SystemExit(main())
