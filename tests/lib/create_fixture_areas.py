#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Creates N fixture areas with sdep-test-* IDs using CA credentials.
# Usage: create_fixture_areas.py [count] [prefix]
# Outputs area IDs to stdout (one per line). Errors to stderr.
# Requires env: BACKEND_BASE_URL, API_VERSION (defaults to v1), CA1_CLIENT_ID, CA1_CLIENT_SECRET
# Uses the ephemeral test CA client (sdep-test-ca.01) so all created rows match
# sdep-test-* for cleanup. Gets the CA token locally only - it does NOT touch
# ./tmp/.bearer_token. Both the stdout (area IDs) and stderr (errors) contracts
# are relied on by the performance path in the consuming deployment repository.

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx


# Shapefile is a static sdep-app asset anchored to the repo root (tests/lib -> repo).
SHAPEFILE_PATH = Path(__file__).resolve().parents[2] / "test-data" / "shapefiles" / "Amsterdam.zip"


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"ERROR: {name} environment variable is not set", file=sys.stderr)
        sys.exit(1)
    return value


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


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    prefix = sys.argv[2] if len(sys.argv) > 2 else "sdep-test-fixture-area"

    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v1")

    timestamp = int(time.time() * 1000)
    area_ids = [f"{prefix}-{timestamp}-{index}" for index in range(1, count + 1)]

    with httpx.Client(timeout=30.0) as client:
        ca_token = auth_token(
            client,
            base_url,
            api_version,
            env("CA1_CLIENT_ID"),
            env("CA1_CLIENT_SECRET"),
        )
        if not ca_token:
            print("ERROR: Failed to get CA token for fixture creation", file=sys.stderr)
            return 1

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
                return 1

    for area_id in area_ids:
        print(area_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
