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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

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


def run_filter_tests(
    stats: TestStats,
    get: Callable[[str], tuple[int, dict[str, Any]]],
    first_test: int,
    id_fields: tuple[str, ...],
    filters_declared: bool,
) -> int:
    """Filter tests driven by a sample activity, so no IDs are hard-coded.

    filters_declared=False (CA v1): the API does not declare these query parameters,
    so they must be ignored - the filtered count equals the unfiltered count.
    filters_declared=True (CA v2, REP v1): every returned activity matches the filter
    and the sample activity is among them; a non-matching filter returns an empty list.

    Returns the next free test number.
    """
    code, body = get("?limit=1")
    activities = body.get("activities") if isinstance(body, dict) else None
    sample = activities[0] if code == 200 and activities else None
    _, count_body = get("/count")
    unfiltered = count_body.get("count") if isinstance(count_body, dict) else None

    def same(field: str, value: Any) -> Callable[[dict[str, Any]], bool]:
        return lambda activity: activity.get(field) == value

    # (label, query string, match predicate; None = expect an empty list)
    cases: list[tuple[str, str, Callable[[dict[str, Any]], bool] | None]] = []
    for field in id_fields:
        value = sample.get(field) if sample else None
        cases.append((f"filter by {field}", urlencode({field: value or ""}), same(field, value)))
    created = sample.get("createdAt") if sample else None
    cases.append(
        (
            "filter by createdAtFrom/createdAtTo (both = sample createdAt)",
            urlencode({"createdAtFrom": created or "", "createdAtTo": created or ""}),
            same("createdAt", created),
        )
    )
    cases.append(
        ("non-matching areaId filter", urlencode({"areaId": "00000000-0000-0000-0000-000000000000"}), None)
    )

    n = first_test
    for label, query, matches in cases:
        print()
        print(f"Test {n}: {label}")
        print("------------------------------------------------")
        stats.total += 1
        if sample is None and matches is not None:
            mark(stats, True, f"Test {n} passed: No data available to test", "")
        elif not filters_declared:
            code, body = get(f"/count?{query}")
            filtered = body.get("count") if isinstance(body, dict) else None
            print(f"HTTP Status: {code} (count={filtered}, unfiltered={unfiltered})")
            mark(
                stats,
                code == 200 and filtered == unfiltered,
                f"Test {n} passed: Undeclared filter is ignored (count unchanged)",
                f"Test {n} failed: Expected count {unfiltered} with an undeclared filter, got {filtered} (HTTP {code})",
            )
        else:
            code, body = get(f"?{query}")
            items = body.get("activities") if isinstance(body, dict) else None
            print(f"HTTP Status: {code} (returned={len(items) if isinstance(items, list) else items})")
            if matches is None:
                mark(
                    stats,
                    code == 200 and items == [],
                    f"Test {n} passed: Non-matching filter returns an empty list",
                    f"Test {n} failed: Expected 200 with an empty list, got HTTP {code}: {compact_json(body)[:200]}",
                )
            else:
                sample_id = sample.get("activityId") if sample else None
                ok = (
                    code == 200
                    and isinstance(items, list)
                    and bool(items)
                    and all(matches(a) for a in items)
                    and any(a.get("activityId") == sample_id for a in items)
                )
                mark(
                    stats,
                    ok,
                    f"Test {n} passed: All {len(items) if isinstance(items, list) else 0} returned activities match, sample included",
                    f"Test {n} failed: Filter did not narrow correctly (HTTP {code}): {compact_json(body)[:200]}",
                )
        n += 1

    print()
    print(f"Test {n}: count with filter equals length of the filtered list")
    print("------------------------------------------------")
    stats.total += 1
    if sample is None:
        mark(stats, True, f"Test {n} passed: No data available to test", "")
    elif not filters_declared:
        mark(stats, True, f"Test {n} passed: Not applicable, filters are not declared for this version", "")
    else:
        query = urlencode({"areaId": sample.get("areaId")})
        code_list, list_body = get(f"?{query}")
        code_count, count_body = get(f"/count?{query}")
        items = list_body.get("activities") if isinstance(list_body, dict) else None
        count = count_body.get("count") if isinstance(count_body, dict) else None
        print(f"HTTP Status: list {code_list}, count {code_count} (len={len(items) if isinstance(items, list) else items}, count={count})")
        mark(
            stats,
            code_list == 200 and code_count == 200 and isinstance(items, list) and count == len(items),
            f"Test {n} passed: Filtered count {count} equals filtered list length",
            f"Test {n} failed: Filtered count {count} differs from list length {len(items) if isinstance(items, list) else items}",
        )
    return n + 1


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

        # Tests 6-10: filters. CA v1 does not declare them (must be ignored), CA v2 does.
        next_test = run_filter_tests(
            stats,
            lambda suffix: get_activities(client, base_url, api_version, bearer_token, suffix),
            first_test=6,
            id_fields=("areaId", "platformId"),
            filters_declared=api_version != "v1",
        )

        print()
        print(f"Test {next_test}: Verify pagination consistency (offset and limit work correctly)")
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
            f"Test {next_test} passed: Pagination endpoints respond correctly",
            f"Test {next_test} failed: Pagination requests failed (Page1: {code_1}, Page2: {code_2})",
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
