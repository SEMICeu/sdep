#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


# Bearer token is runtime state written by test_auth_client.py relative to the
# CURRENT working directory (./tmp/.bearer_token). Resolve it the same way so the
# test works when reused from another repo (e.g. sdep-deployment), not just from
# sdep-app.
BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))

ACCEPTANCE_FIELDS = (
    "temporal",
    "startDatetime",
    "endDatetime",
    "numberOfGuests",
    "countryOfGuests",
    "registrationNumber",
    "competentAuthorityId",
)


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
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    return str(body.get("access_token", ""))


def get_activities(
    client: httpx.Client,
    base_url: str,
    api_version: str,
    bearer_token: str,
    path_suffix: str = "",
) -> tuple[int, dict[str, Any]]:
    response = client.get(
        f"{base_url}/api/rep/{api_version}/activities{path_suffix}",
        headers={"Authorization": f"Bearer {bearer_token}"},
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

    print(f"Testing REP activity endpoints at: {base_url}/api/rep/{api_version}/activities")
    print()

    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        print("Test 1: Count activities")
        print("------------------------------------------------")
        stats.total += 1
        code, body = get_activities(client, base_url, api_version, bearer_token, "/count")
        print(f"Response: {compact_json(body)}")
        print(f"HTTP Status: {code}")
        count = body.get("count")
        mark(
            stats,
            code == 200 and isinstance(count, int) and count >= 0,
            f"Test 1 passed: Activity count is valid (Got: {count})",
            f"Test 1 failed: Expected 200 with count >= 0, got HTTP {code}",
        )
        print()

        print("Test 2: Get all activities (across all competent authorities)")
        print("------------------------------------------------")
        stats.total += 1
        code, body = get_activities(client, base_url, api_version, bearer_token)
        activities = body.get("activities")
        print(f"Response (first 500 chars): {compact_json(body)[:500]}...")
        print(f"HTTP Status: {code}")
        if code == 200 and isinstance(activities, list):
            if not activities:
                print("Test 2: No activities found in database")
            mark(
                stats,
                True,
                f"Test 2 passed: Retrieved {len(activities)} activit(y/ies) (empty result is valid)",
                "",
            )
        else:
            mark(
                stats,
                False,
                "",
                f"Test 2 failed: Expected 200 with 'activities' field, got HTTP {code}",
            )
        print()

        print("Test 3: Get activities with pagination (offset=0, limit=1)")
        print("------------------------------------------------")
        stats.total += 1
        code, body = get_activities(
            client, base_url, api_version, bearer_token, "?offset=0&limit=1"
        )
        activities = body.get("activities")
        print(f"Response: {compact_json(body)}")
        print(f"HTTP Status: {code}")
        mark(
            stats,
            code == 200 and isinstance(activities, list) and len(activities) <= 1,
            "Test 3 passed: Pagination returns at most 1 activity with limit=1 (empty result is valid)",
            f"Test 3 failed: Expected 200 with at most 1 activity, got HTTP {code}",
        )
        print()

        print(
            "Test 4: Verify response structure "
            "(temporal, numberOfGuests, countryOfGuests, registrationNumber, competentAuthorityId)"
        )
        print("------------------------------------------------")
        stats.total += 1
        code, body = get_activities(client, base_url, api_version, bearer_token, "?limit=1")
        activities = body.get("activities")
        print(f"Response: {compact_json(body)}")
        print(f"HTTP Status: {code}")
        if code != 200 or not isinstance(activities, list):
            mark(stats, False, "", f"Test 4 failed: Expected HTTP 200, got {code}")
        elif not activities:
            mark(
                stats,
                True,
                "Test 4 passed: No data available to test response structure",
                "",
            )
        else:
            raw = compact_json(activities[0])
            missing = [field for field in ACCEPTANCE_FIELDS if f'"{field}"' not in raw]
            mark(
                stats,
                not missing,
                "Test 4 passed: Response contains all acceptance-criteria fields",
                f"Test 4 failed: Missing acceptance-criteria fields in response: {missing}",
            )
        print()

        print("Test 5: POST /activities returns 405 Method Not Allowed (read-only API)")
        print("------------------------------------------------")
        stats.total += 1
        response = client.post(
            f"{base_url}/api/rep/{api_version}/activities",
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            },
            json={},
        )
        print(f"HTTP Status: {response.status_code}")
        mark(
            stats,
            response.status_code == 405,
            "Test 5 passed: POST is rejected with 405 Method Not Allowed",
            f"Test 5 failed: Expected 405, got {response.status_code}",
        )
        print()

        print("Test 6: CA token gets 403 Forbidden on REP endpoint (role isolation)")
        print("------------------------------------------------")
        ca_client_id = os.getenv("CA1_CLIENT_ID")
        ca_client_secret = os.getenv("CA1_CLIENT_SECRET")
        if ca_client_id and ca_client_secret:
            stats.total += 1
            ca_token = auth_token(
                client, base_url, api_version, ca_client_id, ca_client_secret
            )
            if not ca_token:
                mark(stats, False, "", "Test 6 failed: Could not obtain CA token")
            else:
                code, _body = get_activities(client, base_url, api_version, ca_token)
                print(f"HTTP Status: {code}")
                mark(
                    stats,
                    code == 403,
                    "Test 6 passed: CA client is forbidden on the REP API",
                    f"Test 6 failed: Expected 403, got {code}",
                )
        else:
            print("Test 6 skipped: CA1_CLIENT_ID/CA1_CLIENT_SECRET not set")
        print()

    print("=======================================")
    print("Test Summary (rep activities):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All REP activity endpoint tests passed!")
        return 0

    print("Some REP activity endpoint tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
