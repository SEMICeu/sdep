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
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
# Bearer token is runtime state written by test_auth_client_bootstrap.py relative to the
# CURRENT working directory (./tmp/.bearer_token). Resolve it the same way so the
# test works when reused from a consuming repository, not just from sdep-app. SHAPEFILE_PATH stays REPO_ROOT-anchored — it is a static sdep-app asset.
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


def iso_utc_in_hours(hours: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def create_fixture_areas(
    client: httpx.Client,
    base_url: str,
    api_version: str,
    count: int,
    prefix: str,
) -> list[str]:
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

    for area_id in area_ids:
        print(area_id)
    return area_ids


def post_bulk(
    client: httpx.Client,
    base_url: str,
    api_version: str,
    bearer_token: str,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    response = client.post(
        f"{base_url}/api/str/{api_version}/activities/bulk",
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"raw": response.text}
    return response.status_code, body


def ca_count(client: httpx.Client, base_url: str, api_version: str, ca_bearer: str) -> int | None:
    response = client.get(
        f"{base_url}/api/ca/{api_version}/activities/count",
        headers={"Authorization": f"Bearer {ca_bearer}"},
    )
    try:
        return int(response.json()["count"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def activity(
    activity_id: str,
    url_suffix: str,
    registration_number: str,
    area_id: str,
    start_time: str,
    end_time: str,
    *,
    status: str | None = None,
    thoroughfare: str = "Prinsengracht",
    locator: int = 265,
    post_code: str = "1016HV",
    post_name: str = "Amsterdam",
    number_of_guests: int = 2,
    countries: list[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "activityId": activity_id,
        "url": f"http://sdep-test.example.com/{url_suffix}",
        "registrationNumber": registration_number,
        "address": {
            "thoroughfare": thoroughfare,
            "locatorDesignatorNumber": locator,
            "postCode": post_code,
            "postName": post_name,
            "fullAddress": f"{thoroughfare} {locator}, {post_code} {post_name}",
        },
        "temporal": {"startDatetime": start_time, "endDatetime": end_time},
        "areaId": area_id,
        "numberOfGuests": number_of_guests,
        "countryOfGuests": countries or ["NLD", "NLD"],
    }
    if status is not None:
        data["status"] = status
    return data


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

    print(f"Testing STR bulk activity endpoints at: {base_url}/api/str/{api_version}/activities/bulk")
    if bearer_token:
        print("Using Bearer token for authentication")
    else:
        print("No BEARER_TOKEN set - making unauthenticated request (should fail)")
    print()

    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        print("Creating fixture areas for bulk activity tests...")
        area_id_1, area_id_2, area_id_3 = create_fixture_areas(
            client,
            base_url,
            api_version,
            3,
            "sdep-test-bulk-areas",
        )
        print(f"Using fixture area IDs: {area_id_1}, {area_id_2}, {area_id_3}")
        print()

        timestamp = int(time.time())
        start_time = iso_utc_in_hours(0)
        end_time = iso_utc_in_hours(1)

        print("Test 1: POST bulk activities (all valid -> 201)")
        print("------------------------------------------------")
        stats.total += 1
        if bearer_token:
            payload = {
                "activities": [
                    activity(
                        f"sdep-test-bulk-ok1-{timestamp}",
                        "bulk-ok1",
                        "REGBULK001",
                        area_id_1,
                        start_time,
                        end_time,
                        number_of_guests=4,
                        countries=["NLD", "NLD", "DEU", "BEL"],
                    ),
                    activity(
                        f"sdep-test-bulk-ok2-{timestamp}",
                        "bulk-ok2",
                        "REGBULK002",
                        area_id_2,
                        start_time,
                        end_time,
                        thoroughfare="Keizersgracht",
                        locator=0,
                        post_code="1015AA",
                        number_of_guests=2,
                        countries=["FRA", "N/A"],
                    ),
                ]
            }
            payload["activities"][1]["address"].pop("locatorDesignatorNumber")
            code, body = post_bulk(client, base_url, api_version, bearer_token, payload)
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {code}")
            print()
            mark(
                stats,
                code == 201 and body.get("succeeded") == 2 and body.get("failed") == 0,
                "Test 1 passed: All activities created (201)",
                "Test 1 failed: Expected 201 with succeeded=2, failed=0",
            )
        else:
            print("Skipping Test 1 (requires authentication)")
        print()

        print("Test 2: POST bulk activities (partial success -> 200)")
        print("------------------------------------------------------")
        stats.total += 1
        if bearer_token:
            start_time_2 = iso_utc_in_hours(2)
            end_time_2 = iso_utc_in_hours(3)
            payload = {
                "activities": [
                    activity(
                        f"sdep-test-bulk-partial1-{timestamp}",
                        "bulk-partial1",
                        "REGPART001",
                        area_id_1,
                        start_time_2,
                        end_time_2,
                        number_of_guests=4,
                        countries=["NLD", "NLD", "DEU", "BEL"],
                    ),
                    activity(
                        f"sdep-test-bulk-partial2-{timestamp}",
                        "bulk-partial2",
                        "REGPART002",
                        "nonexistent-area-id",
                        start_time_2,
                        end_time_2,
                        thoroughfare="Bad Street",
                        locator=1,
                        post_code="0000AA",
                        post_name="Nowhere",
                        number_of_guests=2,
                        countries=["NLD", "N/A"],
                    ),
                ]
            }
            code, body = post_bulk(client, base_url, api_version, bearer_token, payload)
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {code}")
            print()
            mark(
                stats,
                code == 200 and body.get("succeeded") == 1 and body.get("failed") == 1,
                "Test 2 passed: Partial success (200)",
                "Test 2 failed: Expected 200 with succeeded=1, failed=1",
            )
        else:
            print("Skipping Test 2 (requires authentication)")
        print()

        print("Test 3: POST bulk activities (all invalid -> 422)")
        print("--------------------------------------------------")
        stats.total += 1
        if bearer_token:
            start_time_3 = iso_utc_in_hours(4)
            end_time_3 = iso_utc_in_hours(5)
            payload = {
                "activities": [
                    activity(
                        f"sdep-test-bulk-fail1-{timestamp}",
                        "bulk-fail1",
                        "REGFAIL001",
                        "nonexistent-area-1",
                        start_time_3,
                        end_time_3,
                        thoroughfare="Bad Street",
                        locator=1,
                        post_code="0000AA",
                        post_name="Nowhere",
                        number_of_guests=1,
                        countries=["N/A"],
                    ),
                    activity(
                        f"sdep-test-bulk-fail2-{timestamp}",
                        "bulk-fail2",
                        "REGFAIL002",
                        "nonexistent-area-2",
                        start_time_3,
                        end_time_3,
                        thoroughfare="Bad Street",
                        locator=2,
                        post_code="0000BB",
                        post_name="Nowhere",
                        number_of_guests=2,
                        countries=["N/A", "N/A"],
                    ),
                ]
            }
            code, body = post_bulk(client, base_url, api_version, bearer_token, payload)
            print(f"Response: {compact_json(body)}")
            print(f"HTTP Status: {code}")
            print()
            mark(
                stats,
                code == 422 and body.get("succeeded") == 0 and body.get("failed") == 2,
                "Test 3 passed: All failed (422)",
                "Test 3 failed: Expected 422 with succeeded=0, failed=2",
            )
        else:
            print("Skipping Test 3 (requires authentication)")
        print()

        print("Test 4: POST bulk activities without authentication (-> 401)")
        print("------------------------------------------------------------")
        stats.total += 1
        response = client.post(
            f"{base_url}/api/str/{api_version}/activities/bulk",
            headers={"Content-Type": "application/json"},
            json={"activities": [{"areaId": "test"}]},
        )
        print(f"HTTP Status: {response.status_code}")
        print()
        mark(
            stats,
            response.status_code == 401,
            "Test 4 passed: Correctly rejected unauthenticated request (401)",
            f"Test 4 failed: Expected 401 but got {response.status_code}",
        )
        print()

        print("Test 5: Stacked insert + cancel (CA count stays the same)")
        print("---------------------------------------------------------")
        stats.total += 1
        if bearer_token:
            stacked_id = f"sdep-test-bulk-stacked-{timestamp}"
            start_time_5 = iso_utc_in_hours(4)
            end_time_5 = iso_utc_in_hours(5)

            ca_bearer = auth_token(
                client,
                base_url,
                api_version,
                env("CA1_CLIENT_ID"),
                env("CA1_CLIENT_SECRET"),
            )
            if not ca_bearer:
                print(f"Test 5 failed: could not authenticate as CA ({env('CA1_CLIENT_ID')})")
                stats.failed += 1
            else:
                count_before = ca_count(client, base_url, api_version, ca_bearer)
                if count_before is None:
                    print("Test 5 failed: could not fetch CA activity count (empty response)")
                    stats.failed += 1
                else:
                    print(f"CA activity count BEFORE insert:  {count_before}")

                    payload_insert = {
                        "activities": [
                            activity(
                                stacked_id,
                                "bulk-stacked",
                                "REGSTACK001",
                                area_id_1,
                                start_time_5,
                                end_time_5,
                                number_of_guests=2,
                                countries=["NLD", "NLD"],
                            )
                        ]
                    }
                    insert_code, insert_body = post_bulk(
                        client, base_url, api_version, bearer_token, payload_insert
                    )
                    print(
                        f"Step A (insert finished)  HTTP={insert_code}  "
                        f"body={compact_json(insert_body)}"
                    )

                    count_after_insert = ca_count(client, base_url, api_version, ca_bearer)
                    print(f"CA activity count AFTER  insert:  {count_after_insert}")

                    payload_cancel = {
                        "activities": [
                            activity(
                                stacked_id,
                                "bulk-stacked",
                                "REGSTACK001",
                                area_id_1,
                                start_time_5,
                                end_time_5,
                                status="cancelled",
                                number_of_guests=2,
                                countries=["NLD", "NLD"],
                            )
                        ]
                    }
                    cancel_code, cancel_body = post_bulk(
                        client, base_url, api_version, bearer_token, payload_cancel
                    )
                    print(
                        f"Step B (cancel)           HTTP={cancel_code}  "
                        f"body={compact_json(cancel_body)}"
                    )

                    count_after_cancel = ca_count(client, base_url, api_version, ca_bearer)
                    print(f"CA activity count AFTER  cancel:  {count_after_cancel}")
                    print()

                    cancel_results = cancel_body.get("results") or []
                    cancel_activity_status = None
                    if cancel_results:
                        cancel_activity_status = (
                            cancel_results[0].get("activity") or {}
                        ).get("status")

                    assertions_ok = (
                        insert_code == 201
                        and insert_body.get("succeeded") == 1
                        and cancel_code == 201
                        and cancel_body.get("succeeded") == 1
                        and cancel_activity_status == "cancelled"
                        and count_after_insert is not None
                        and count_after_cancel is not None
                        and count_after_insert == count_after_cancel
                        and count_after_insert - count_before == 1
                    )
                    mark(
                        stats,
                        assertions_ok,
                        (
                            "Test 5 passed: insert+cancel OK; CA count unchanged "
                            f"({count_after_insert} == {count_after_cancel})"
                        ),
                        (
                            "Test 5 failed: expected insert=201/succeeded=1, "
                            "cancel=201/succeeded=1/status=cancelled, and CA count "
                            "to go BEFORE->AFTER_INSERT (+1) then stay equal after cancel."
                        ),
                    )
        else:
            print("Skipping Test 5 (requires STR BEARER_TOKEN)")
        print()

    print("=======================================")
    print("Test Summary (bulk activities):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All bulk activity endpoint tests passed!")
        return 0

    print("Some bulk activity endpoint tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
