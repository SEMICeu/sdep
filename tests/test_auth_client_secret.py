#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Test OAuth 2.0 token acquisition for the STR and CA machine clients, using
# client-secret authentication (client_secret_post). Same Client Credentials flow as
# test_auth_client_jwt.py, different client authentication method: a shared secret
# instead of a signed assertion.
# Requires CLIENT_SECRET_AUTH_ENABLED=true on the backend under test.
# Expects BACKEND_BASE_URL environment variable to be set.
# Reads STR_CLIENT_ID/STR_CLIENT_SECRET and CA1_CLIENT_ID/CA1_CLIENT_SECRET from env.
# Optionally accepts API_VERSION environment variable (defaults to v1).

from __future__ import annotations

import base64
import binascii
import json
import os
import sys
from dataclasses import dataclass

import httpx


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


def decode_jwt_payload(access_token: str) -> str:
    # Best-effort, informational only: decode the JWT payload (second segment).
    parts = access_token.split(".")
    if len(parts) < 2:
        return "Could not decode JWT token"
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)  # restore base64 padding
    try:
        decoded = base64.urlsafe_b64decode(payload)
        return json.dumps(json.loads(decoded), indent=2, ensure_ascii=False)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        return "Could not decode JWT token"


def test_credentials(
    client: httpx.Client,
    stats: TestStats,
    base_url: str,
    api_version: str,
    client_id: str,
    client_secret: str,
    client_type: str,
) -> None:
    print(f"Testing {client_type} credentials")
    print("------------------------------------------------")
    print(f"CLIENT_ID: {client_id}")
    print(f"Endpoint: {base_url}/api/auth/{api_version}/token")
    print()

    stats.total += 1

    response = client.post(
        f"{base_url}/api/auth/{api_version}/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    print(f"HTTP Status: {response.status_code}")

    if response.status_code == 200:
        try:
            access_token = str(response.json().get("access_token", ""))
        except json.JSONDecodeError:
            access_token = ""

        if access_token:
            print(f"{client_type} token acquired successfully!")
            print()
            print("JWT Token Contents:")
            print("------------------------------------------------")
            print(decode_jwt_payload(access_token))
            print("------------------------------------------------")
            stats.passed += 1
        else:
            print("Failed to extract access token from response")
            stats.failed += 1
    elif response.status_code == 401:
        print(f"Unauthorized - invalid {client_type} credentials")
        stats.failed += 1
    else:
        print(f"Token acquisition failed with HTTP status {response.status_code}")
        stats.failed += 1


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v1")

    stats = TestStats()

    with httpx.Client(timeout=30.0) as client:
        test_credentials(
            client,
            stats,
            base_url,
            api_version,
            env("STR_CLIENT_ID"),
            env("STR_CLIENT_SECRET"),
            "STR",
        )
        print()
        test_credentials(
            client,
            stats,
            base_url,
            api_version,
            env("CA1_CLIENT_ID"),
            env("CA1_CLIENT_SECRET"),
            "CA",
        )

    print()
    print("=======================================")
    print("Test Summary (auth credentials):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All OAuth token acquisition tests passed!")
        return 0

    print("Some OAuth token acquisition tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
