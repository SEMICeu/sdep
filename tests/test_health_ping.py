#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Test the SDEP ping endpoint.
# Expects BACKEND_BASE_URL environment variable to be set.
# Optionally accepts BEARER_TOKEN environment variable for authenticated requests
# (falls back to the token file written by test_auth_client).
# Optionally accepts API_VERSION environment variable (defaults to v1).

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx


# Bearer token is runtime state written by test_auth_client relative to the CURRENT
# working directory (./tmp/.bearer_token). Resolve it the same way so the test works
# when reused from a consuming repository, not just from sdep-app.
BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))


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


def load_bearer_token() -> str:
    token = os.getenv("BEARER_TOKEN", "")
    if token:
        return token
    if BEARER_TOKEN_FILE.exists():
        print(f"Loaded BEARER_TOKEN from {BEARER_TOKEN_FILE}")
        return BEARER_TOKEN_FILE.read_text(encoding="utf-8").strip()
    return ""


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    bearer_token = load_bearer_token()

    print(f"Testing ping endpoint at: {base_url}/api/ping")
    if bearer_token:
        print("Using Bearer token for authentication")
    else:
        print("No BEARER_TOKEN set - making unauthenticated request")
    print()

    stats = TestStats()
    stats.total += 1

    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{base_url}/api/ping", headers=headers)

    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"raw": response.text}

    print(f"Response: {json.dumps(body, separators=(',', ':'), ensure_ascii=False)}")
    print(f"HTTP Status: {response.status_code}")
    print()

    if response.status_code == 200 and body.get("status") == "OK":
        print("Ping test passed!")
        stats.passed += 1
    elif response.status_code == 200:
        print("Unexpected response body")
        stats.failed += 1
    else:
        print(f"Ping test failed with HTTP status {response.status_code}")
        stats.failed += 1

    print()
    print("=======================================")
    print("Test Summary (health ping):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("Ping endpoint test successful!")
        return 0

    print("Ping endpoint test failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
