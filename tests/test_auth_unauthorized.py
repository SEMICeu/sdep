#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Test that all secured endpoints return 401 Unauthorized without authentication.
# Expects BACKEND_BASE_URL environment variable to be set.
# Tests both version-independent (/api) and versioned domain endpoints.

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import httpx


# (method, path) pairs for secured endpoints; public endpoints like /api/health
# and /api/auth/v1/token are intentionally excluded.
SECURED_ENDPOINTS = (
    ("GET", "/api/ping"),
    ("GET", "/api/str/v1/areas"),
    ("GET", "/api/str/v1/areas/count"),
    ("GET", "/api/str/v1/areas/amsterdam-area0363"),
    ("POST", "/api/str/v1/activities/bulk"),
    ("POST", "/api/ca/v1/areas"),
    ("GET", "/api/ca/v1/areas"),
    ("GET", "/api/ca/v1/areas/count"),
    ("GET", "/api/ca/v1/areas/some-area-id"),
    ("DELETE", "/api/ca/v1/areas/some-area-id"),
    ("GET", "/api/ca/v1/activities"),
    ("GET", "/api/ca/v1/activities/count"),
    ("GET", "/api/rep/v1/activities"),
    ("GET", "/api/rep/v1/activities/count"),
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


def main() -> int:
    base_url = env("BACKEND_BASE_URL")

    print("Testing unauthorized access to secured endpoints")
    print(f"Backend: {base_url}")
    print()

    stats = TestStats()

    print("Testing secured endpoints without authentication...")
    print()
    with httpx.Client(timeout=30.0) as client:
        for method, path in SECURED_ENDPOINTS:
            stats.total += 1
            code = client.request(method, f"{base_url}{path}").status_code
            if code == 401:
                print(f"{method} {path} - Correctly returns 401 Unauthorized")
                stats.passed += 1
            else:
                print(f"{method} {path} - Expected 401 but got {code}")
                stats.failed += 1

    print()
    print("=======================================")
    print("Test Summary (unauthorized access):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All endpoints are properly secured!")
        return 0

    print("Some endpoints are not properly secured!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
