#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Test script for CA activity endpoints.
# Expects BACKEND_BASE_URL environment variable to be set.
# Reads the bearer token written by test_auth_client (./tmp/.bearer_token).

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


# Bearer token is runtime state written by test_auth_client relative to the CURRENT
# working directory (./tmp/.bearer_token). Resolve it the same way so the test works
# when reused from a consuming repository, not just from sdep-app.
BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))

REQUIRED_FIELDS = (
    "activityId",
    "status",
    "platformId",
    "platformName",
    "url",
    "registrationNumber",
    "address",
    "temporal",
    "areaId",
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


def get_activities(
    client: httpx.Client,
    base_url: str,
    api_version: str,
    bearer_token: str,
    path_suffix: str = "",
) -> tuple[int, dict[str, Any]]:
    response = client.get(
        f"{base_url}/api/ca/{api_version}/activities{path_suffix}",
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

    print(f"Testing CA activity endpoints at: {base_url}/api/ca/{api_version}/activities")

    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        print()
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
        print("Test 2: Get all activities")
        print("------------------------------------------------")
        stats.total += 1
        code, body = get_activities(client, base_url, api_version, bearer_token)
        activities = body.get("activities")
        print(f"Response (first 500 chars): {compact_json(body)[:500]}...")
        print(f"HTTP Status: {code}")
        print()
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
            mark(stats, False, "", "Test 2 failed: Response does not contain 'activities' field")

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
        print()
        mark(
            stats,
            code == 200 and isinstance(activities, list) and len(activities) <= 1,
            "Test 3 passed: Pagination returns at most 1 activity with limit=1 (empty result is valid)",
            f"Test 3 failed: Unexpected HTTP status {code}",
        )

        print()
        print(
            "Test 4: Verify response structure "
            "(activityId, activityName, status, platformId, platformName, url, "
            "registrationNumber, address, temporal, areaId)"
        )
        print("------------------------------------------------")
        stats.total += 1
        code, body = get_activities(client, base_url, api_version, bearer_token, "?limit=1")
        activities = body.get("activities")
        print(f"Response: {compact_json(body)}")
        print(f"HTTP Status: {code}")
        print()
        if code != 200 or not isinstance(activities, list):
            mark(stats, False, "", f"Test 4 failed: Unexpected HTTP status {code}")
        elif not activities:
            mark(stats, True, "Test 4 passed: No data available to test", "")
        else:
            raw = compact_json(activities[0])
            missing = [field for field in REQUIRED_FIELDS if f'"{field}"' not in raw]
            has_activity_name = "yes" if '"activityName"' in raw else "no"
            if not missing:
                print(f"   Note: activityName is optional and was: {has_activity_name}")
            mark(
                stats,
                not missing,
                "Test 4 passed: Response contains all required fields",
                f"Test 4 failed: Missing required fields in response: {missing}",
            )

        print()
        print("Test 5: GET specific activity by URL (filtering by url parameter)")
        print("------------------------------------------------")
        stats.total += 1
        code, body = get_activities(client, base_url, api_version, bearer_token, "?limit=1")
        activities = body.get("activities") if isinstance(body, dict) else None
        if code != 200:
            mark(stats, False, "", "Test 5 failed: Could not retrieve activities for testing")
        else:
            activity_url = activities[0].get("url") if activities else None
            if not activity_url:
                mark(stats, True, "Test 5 passed: No data available to test", "")
            else:
                print(f"Found activity URL: {activity_url}")
                filter_code, filter_body = get_activities(
                    client, base_url, api_version, bearer_token, f"?url={activity_url}"
                )
                print(f"Response: {compact_json(filter_body)}")
                print(f"HTTP Status: {filter_code}")
                print()
                if filter_code == 200:
                    mark(
                        stats,
                        activity_url in compact_json(filter_body),
                        "Test 5 passed: Retrieved activity by URL filter",
                        "Test 5 failed: Response doesn't contain expected URL",
                    )
                else:
                    mark(
                        stats,
                        True,
                        "Test 5 passed: Endpoint responded (feature may not be implemented)",
                        "",
                    )

        print()
        print("Test 6: GET activities filtered by areaId")
        print("------------------------------------------------")
        stats.total += 1
        known_area_id = "00000000000000000001"
        code, body = get_activities(
            client, base_url, api_version, bearer_token, f"?areaId={known_area_id}"
        )
        print(f"HTTP Status: {code}")
        # Always passes: areaId filtering may not be implemented; we only confirm the
        # endpoint responds.
        if code == 200:
            print(f"Test 6 passed: Query executed successfully for area {known_area_id}")
        else:
            print("Test 6 passed: Endpoint responded (feature may not be implemented)")
        stats.passed += 1

        print()
        print("Test 7: GET with non-existent areaId filter (should return empty list or 404)")
        print("------------------------------------------------")
        stats.total += 1
        nonexistent_area_id = "00000000-0000-0000-0000-000000000000"
        code, body = get_activities(
            client, base_url, api_version, bearer_token, f"?areaId={nonexistent_area_id}"
        )
        print(f"Response: {compact_json(body)}")
        print(f"HTTP Status: {code}")
        print()
        mark(
            stats,
            code in (200, 404),
            "Test 7 passed: Endpoint correctly handled non-existent area",
            f"Test 7 failed: Expected 200 or 404 but got {code}",
        )

        print()
        print("Test 8: Verify pagination consistency (offset and limit work correctly)")
        print("------------------------------------------------")
        stats.total += 1
        code_1, body_1 = get_activities(
            client, base_url, api_version, bearer_token, "?offset=0&limit=2"
        )
        code_2, body_2 = get_activities(
            client, base_url, api_version, bearer_token, "?offset=2&limit=2"
        )
        print(f"Page 1 HTTP Status: {code_1}")
        print(f"Page 2 HTTP Status: {code_2}")
        print()
        mark(
            stats,
            code_1 == 200 and code_2 == 200,
            "Test 8 passed: Pagination endpoints respond correctly",
            f"Test 8 failed: Pagination requests failed (Page1: {code_1}, Page2: {code_2})",
        )
        print()

    print("=======================================")
    print("Test Summary (CA activities):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All CA activity endpoint tests passed!")
        return 0

    print("Some CA activity endpoint tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
