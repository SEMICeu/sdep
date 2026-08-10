#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyjwt[crypto]>=2.10.1",
# ]
# ///
"""Create a client-signed JWT.

This script is portable: it can run outside this repository as long as `uv` is
installed.
"""

from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path

import jwt


def build_client_signed_jwt(
    *,
    token_url: str,
    client_id: str,
    private_key_pem: str,
    kid: str,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": client_id,
            "sub": client_id,
            "aud": token_url,
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        },
        private_key_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-url", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--kid", required=True)
    args = parser.parse_args()

    key_path = Path(args.key_file)
    if not key_path.is_file():
        parser.error(f"private key file not found: {key_path}")

    with key_path.open(encoding="utf-8") as key_file:
        private_key_pem = key_file.read()

    print(
        build_client_signed_jwt(
            token_url=args.token_url,
            client_id=args.client_id,
            private_key_pem=private_key_pem,
            kid=args.kid,
        )
    )


if __name__ == "__main__":
    main()
