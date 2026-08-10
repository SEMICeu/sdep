#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Utility script to authorize and save a bearer token, using client-secret
# authentication (client_secret_post). The client-signed-JWT equivalent is
# test_auth_client_jwt.py.
# Expects BACKEND_BASE_URL environment variable to be set.
# Expects CLIENT_ID and CLIENT_SECRET environment variables.
# Optionally accepts API_VERSION environment variable (defaults to v1).
# Saves the token to ./tmp/.bearer_token (TOKEN_FILE override) for use by other
# test scripts. This is the auth bootstrap, not a counted test suite, so it does
# not print a Total/Passed/Failed summary.

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx


# Token is written relative to the CURRENT working directory (./tmp/.bearer_token)
# so the readers (resolved the same way) find it whether run from sdep-app or from
# a consuming deployment repository.
BEARER_TOKEN_FILE = Path(os.getenv("TOKEN_FILE", "tmp/.bearer_token"))


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"❌ Error: {name} environment variable is not set")
        sys.exit(1)
    return value


def authorize(base_url: str, api_version: str, client_id: str, client_secret: str) -> int:
    print(f"🔐 Authorizing with client: {client_id}")

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{base_url}/api/auth/{api_version}/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code == 200:
        try:
            access_token = str(response.json().get("access_token", ""))
        except json.JSONDecodeError:
            access_token = ""

        if access_token:
            BEARER_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            BEARER_TOKEN_FILE.write_text(f"{access_token}\n", encoding="utf-8")
            print(f"✅ Token saved to {BEARER_TOKEN_FILE}")
            return 0
        print("❌ Failed to extract access token from response")
        return 1

    if response.status_code == 401:
        print("❌ Unauthorized - invalid credentials")
        return 1

    print(f"❌ Authorization failed with HTTP status {response.status_code}")
    print(f"Response: {response.text}")
    return 1


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    client_id = env("CLIENT_ID")
    client_secret = env("CLIENT_SECRET")
    api_version = os.getenv("API_VERSION", "v1")

    return authorize(base_url, api_version, client_id, client_secret)


if __name__ == "__main__":
    raise SystemExit(main())
