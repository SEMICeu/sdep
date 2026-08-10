#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Smoke test for audit-excluded endpoints (SKIP_PATHS).
# These endpoints are safe for production: read-only, no authentication, no test data.
# Expects BACKEND_BASE_URL environment variable to be set.
# Keep in sync with SKIP_PATHS in backend/app/security/audit.py
# (guarded by test_skip_paths_are_complete in backend/tests/security/test_audit.py).

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import httpx


ENDPOINTS = (
    "/",
    "/api/docs",
    "/api/health",
    "/api/auth/v1/openapi.json",
    "/api/auth/v1/docs",
    "/api/ca/v1/openapi.json",
    "/api/ca/v1/docs",
    "/api/str/v1/openapi.json",
    "/api/str/v1/docs",
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

    print(f"Smoke testing audit-excluded endpoints at: {base_url}")
    print()

    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        for endpoint in ENDPOINTS:
            stats.total += 1
            code = client.get(f"{base_url}{endpoint}").status_code
            if code == 200:
                print(f"GET {endpoint} - {code} OK")
                stats.passed += 1
            else:
                print(f"GET {endpoint} - {code} FAIL (expected 200)")
                stats.failed += 1

    print()
    print("=======================================")
    print("Test Summary (smoke test):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All smoke test endpoints passed!")
        return 0

    print("Some smoke test endpoints failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
