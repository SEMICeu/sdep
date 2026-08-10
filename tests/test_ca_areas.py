#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Test script for the CA area submission endpoint of the SDEP API.
# Expects BACKEND_BASE_URL environment variable to be set.
# Reads the bearer token written by test_auth_client (./tmp/.bearer_token).
# Optionally accepts API_VERSION environment variable (defaults to v1).
# Tests POST /ca/areas endpoint with file upload (multipart/form-data) and related
# read/delete/isolation behaviour.

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
    if BEARER_TOKEN_FILE.exists():
        print(f"Loaded BEARER_TOKEN from {BEARER_TOKEN_FILE}")
        return BEARER_TOKEN_FILE.read_text(encoding="utf-8").strip()
    print(f"No {BEARER_TOKEN_FILE} file found")
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


def post_area(
    client: httpx.Client,
    base_url: str,
    api_version: str,
    bearer_token: str,
    *,
    area_id: str | None = None,
    area_name: str | None = None,
) -> tuple[int, dict[str, Any]]:
    data: dict[str, str] = {}
    if area_id is not None:
        data["areaId"] = area_id
    if area_name is not None:
        data["areaName"] = area_name
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    with SHAPEFILE_PATH.open("rb") as shapefile:
        response = client.post(
            f"{base_url}/api/ca/{api_version}/areas",
            headers=headers,
            data=data,
            files={"file": ("Amsterdam.zip", shapefile, "application/zip")},
        )
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"raw": response.text}
    return response.status_code, body


def mark(stats: TestStats, ok: bool, passed_message: str, failed_message: str) -> None:
    if ok:
        print(passed_message)
        stats.passed += 1
    else:
        print(failed_message)
        stats.failed += 1


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v1")

    bearer_token = load_bearer_token()

    print(f"Testing CA area endpoint at: {base_url}/api/ca/{api_version}/areas")
    if bearer_token:
        print("Using Bearer token for authentication")
    else:
        print("No BEARER_TOKEN set - making unauthenticated request (should fail)")
    print()

    if not SHAPEFILE_PATH.is_file():
        print(f"Error: Test shapefile not found at {SHAPEFILE_PATH}")
        return 1
    print(f"Using test shapefile: {SHAPEFILE_PATH}")
    print()

    stats = TestStats()
    areas_url = f"{base_url}/api/ca/{api_version}/areas"

    with httpx.Client(timeout=30.0) as client:
        auth = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}

        print("Test 1: POST single area with file upload")
        print("------------------------------------------------")
        stats.total += 1
        area_id = f"sdep-test-area-single-{int(time.time())}"
        if bearer_token:
            code, body = post_area(client, base_url, api_version, bearer_token, area_id=area_id)
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {code}")
            print()
            raw = compact_json(body)
            ok = code == 201 and all(f'"{f}"' in raw for f in ("areaId", "filename", "createdAt"))
            mark(
                stats,
                ok,
                "Test 1 passed: Area successfully submitted",
                "Test 1 failed: Expected areaId, filename, createdAt in response"
                if code == 201
                else f"Test 1 failed: Unexpected HTTP status {code}",
            )
        else:
            code, _body = post_area(client, base_url, api_version, bearer_token, area_id=area_id)
            print(f"HTTP Status: {code}")
            print()
            mark(
                stats,
                code == 401,
                "Test 1 passed: Correctly rejected unauthenticated request (401)",
                f"Test 1 failed: Unexpected HTTP status {code}",
            )
        print()

        print("Test 2: POST with custom areaId")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            unique_id = int(time.time() * 1000)
            code, body = post_area(
                client, base_url, api_version, bearer_token, area_id=f"sdep-test-area-custom-{unique_id}"
            )
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {code}")
            print()
            raw = compact_json(body)
            ok = code == 201 and all(f'"{f}"' in raw for f in ("areaId", "createdAt"))
            mark(
                stats,
                ok,
                "Test 2 passed: Area with custom areaId successfully submitted",
                "Test 2 failed: Expected success response format"
                if code == 201
                else f"Test 2 failed: Expected 201 but got {code}",
            )
        else:
            print("Skipping Test 2 (requires authentication)")
        print()

        print("Test 3: POST without areaId (auto-generated UUID)")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            code, body = post_area(client, base_url, api_version, bearer_token)
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {code}")
            print()
            raw = compact_json(body)
            ok = code == 201 and all(f'"{f}"' in raw for f in ("areaId", "createdAt"))
            mark(
                stats,
                ok,
                "Test 3 passed: Area with auto-generated UUID successfully submitted",
                "Test 3 failed: Expected areaId in response"
                if code == 201
                else f"Test 3 failed: Expected 201 but got {code}",
            )
        else:
            print("Skipping Test 3 (requires authentication)")
        print()

        print("Test 4: GET own areas")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.get(areas_url, headers=auth)
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {"raw": response.text}
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {response.status_code}")
            print()
            if response.status_code == 200:
                mark(
                    stats,
                    "areas" in body,
                    "Test 4 passed: GET /ca/areas returned areas list",
                    "Test 4 failed: Expected areas key in response",
                )
            else:
                mark(stats, False, "", f"Test 4 failed: Expected 200 but got {response.status_code}")
        else:
            print("Skipping Test 4 (requires authentication)")
        print()

        print("Test 5: GET own areas count")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.get(f"{areas_url}/count", headers=auth)
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {"raw": response.text}
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {response.status_code}")
            print()
            if response.status_code == 200:
                mark(
                    stats,
                    "count" in body,
                    "Test 5 passed: GET /ca/areas/count returned count",
                    "Test 5 failed: Expected count key in response",
                )
            else:
                mark(stats, False, "", f"Test 5 failed: Expected 200 but got {response.status_code}")
        else:
            print("Skipping Test 5 (requires authentication)")
        print()

        print("Test 6: GET own areas does not contain endedAt")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.get(areas_url, headers=auth)
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = {"raw": response.text}
            print(f"HTTP Status: {response.status_code}")
            print()
            if response.status_code == 200:
                mark(
                    stats,
                    '"endedAt"' not in compact_json(body),
                    "Test 6 passed: Response does not contain endedAt",
                    "Test 6 failed: Response contains endedAt (should be internal only)",
                )
            else:
                mark(stats, False, "", f"Test 6 failed: Expected 200 but got {response.status_code}")
        else:
            print("Skipping Test 6 (requires authentication)")
        print()

        print("Test 7: Versioning - submit same areaId twice")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            versioned_id = f"sdep-test-area-versioned-{int(time.time())}"
            post_area(client, base_url, api_version, bearer_token, area_id=versioned_id)
            code, body = post_area(client, base_url, api_version, bearer_token, area_id=versioned_id)
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {code}")
            print()
            if code == 201:
                mark(
                    stats,
                    body.get("areaId") == versioned_id,
                    "Test 7 passed: Versioned area submission returned latest",
                    "Test 7 failed: Expected areaId to match versioned ID",
                )
            else:
                mark(stats, False, "", f"Test 7 failed: Expected 201 but got {code}")
        else:
            print("Skipping Test 7 (requires authentication)")
        print()

        print("Test 8: DELETE area (deactivate)")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            delete_area_id = f"sdep-test-area-delete-{int(time.time())}"
            post_area(client, base_url, api_version, bearer_token, area_id=delete_area_id)
            response = client.delete(f"{areas_url}/{delete_area_id}", headers=auth)
            print(f"HTTP Status: {response.status_code}")
            print()
            mark(
                stats,
                response.status_code == 204,
                "Test 8 passed: Area successfully deleted (204 No Content)",
                f"Test 8 failed: Expected 204 but got {response.status_code}",
            )
        else:
            print("Skipping Test 8 (requires authentication)")
        print()

        print("Test 9: DELETE nonexistent area returns 404")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.delete(f"{areas_url}/nonexistent-area-{int(time.time())}", headers=auth)
            print(f"HTTP Status: {response.status_code}")
            print()
            mark(
                stats,
                response.status_code == 404,
                "Test 9 passed: Nonexistent area correctly returned 404",
                f"Test 9 failed: Expected 404 but got {response.status_code}",
            )
        else:
            print("Skipping Test 9 (requires authentication)")
        print()

        print("Test 10: GET own area by ID (success)")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            get_area_id = f"sdep-test-area-get-{int(time.time())}"
            post_area(client, base_url, api_version, bearer_token, area_id=get_area_id)
            response = client.get(f"{areas_url}/{get_area_id}", headers=auth)
            print(f"HTTP Status: {response.status_code}")
            print()
            mark(
                stats,
                response.status_code == 200,
                "Test 10 passed: GET /ca/areas/{areaId} returned area (200 OK)",
                f"Test 10 failed: Expected 200 but got {response.status_code}",
            )
        else:
            print("Skipping Test 10 (requires authentication)")
        print()

        print("Test 11: GET nonexistent own area returns 404")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            response = client.get(f"{areas_url}/nonexistent-area-{int(time.time())}", headers=auth)
            print(f"HTTP Status: {response.status_code}")
            print()
            mark(
                stats,
                response.status_code == 404,
                "Test 11 passed: Nonexistent area correctly returned 404",
                f"Test 11 failed: Expected 404 but got {response.status_code}",
            )
        else:
            print("Skipping Test 11 (requires authentication)")
        print()

        print("Test 12: Cross-CA isolation - same areaId across two CAs")
        print("------------------------------------------------")
        stats.total += 1
        ca2_client_id = os.getenv("CA2_CLIENT_ID")
        ca2_client_secret = os.getenv("CA2_CLIENT_SECRET")
        if bearer_token and ca2_client_id and ca2_client_secret:
            ca2_token = auth_token(client, base_url, api_version, ca2_client_id, ca2_client_secret)
            if not ca2_token:
                mark(stats, False, "", "Test 12 failed: Could not obtain CA2 access token")
            else:
                shared_area_id = f"sdep-test-area-shared-{int(time.time())}"
                ca1_post_code, _ = post_area(
                    client, base_url, api_version, bearer_token, area_id=shared_area_id, area_name="CA1 area"
                )
                ca2_post_code, _ = post_area(
                    client, base_url, api_version, ca2_token, area_id=shared_area_id, area_name="CA2 area"
                )
                ca1_get_code = client.get(
                    f"{areas_url}/{shared_area_id}",
                    headers={"Authorization": f"Bearer {bearer_token}"},
                ).status_code
                ca2_get_code = client.get(
                    f"{areas_url}/{shared_area_id}",
                    headers={"Authorization": f"Bearer {ca2_token}"},
                ).status_code
                print(
                    f"CA1 POST: {ca1_post_code}  CA2 POST: {ca2_post_code}  "
                    f"CA1 GET: {ca1_get_code}  CA2 GET: {ca2_get_code}"
                )
                print()
                mark(
                    stats,
                    ca1_post_code == 201
                    and ca2_post_code == 201
                    and ca1_get_code == 200
                    and ca2_get_code == 200,
                    "Test 12 passed: Both CAs keep their own area despite shared areaId",
                    "Test 12 failed: Expected both POSTs=201 and both GETs=200 "
                    "(cross-CA area isolation)",
                )
        else:
            print("Skipping Test 12 (requires BEARER_TOKEN, CA2_CLIENT_ID, CA2_CLIENT_SECRET)")
        print()

    print("=======================================")
    print("Test Summary (CA areas):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All area endpoint tests passed!")
        return 0

    print("Some area endpoint tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
