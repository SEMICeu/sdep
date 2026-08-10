#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "cryptography>=42.0.0",
#   "pyyaml>=6.0.0",
# ]
# ///
"""Validate that a private key matches the client public key declared in a YAML.

Shared: a consuming deployment repository reuses this script through SDEP_APP_DIR,
for both the local machine clients here and the per-environment clients it declares
in its own machine-clients-<env>.yaml. Keep the messages environment-neutral.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def load_clients(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as clients_file:
        data = yaml.safe_load(clients_file)
    clients = data.get("clients") if isinstance(data, dict) else None
    if not isinstance(clients, list):
        raise ValueError(f"clients file must contain a top-level clients list: {path}")
    return [client for client in clients if isinstance(client, dict)]


def find_client(clients: list[dict[str, Any]], client_id: str) -> dict[str, Any]:
    for client in clients:
        if client.get("id") == client_id:
            return client
    raise ValueError(f"client not found in clients file: {client_id}")


def load_private_key(path: Path) -> rsa.RSAPrivateKey:
    with path.open("rb") as key_file:
        private_key = serialization.load_pem_private_key(key_file.read(), password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("key file must contain an RSA private key")
    return private_key


def load_public_key(public_key_pem: str) -> rsa.RSAPublicKey:
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("public_key_pem must contain an RSA public key")
    return public_key


def validate_client_key_pair(
    *,
    clients_file: Path,
    client_id: str,
    key_file: Path,
    kid: str,
) -> None:
    client = find_client(load_clients(clients_file), client_id)

    auth_type = client.get("auth_type", "client-secret")
    if auth_type != "client-jwt":
        raise ValueError(f"client {client_id} must use auth_type: client-jwt")

    expected_kid = client.get("jwks_kid")
    if expected_kid != kid:
        raise ValueError(
            f"kid mismatch for {client_id}: got {kid!r}, expected {expected_kid!r}"
        )

    public_key_pem = client.get("public_key_pem")
    if not isinstance(public_key_pem, str) or not public_key_pem.strip():
        raise ValueError(f"client {client_id} must declare public_key_pem")

    if not key_file.is_file():
        raise ValueError(f"private key file not found: {key_file}")

    private_key = load_private_key(key_file)
    configured_public_key = load_public_key(public_key_pem)

    if private_key.public_key().public_numbers() != configured_public_key.public_numbers():
        raise ValueError(
            "private key does not match public_key_pem for "
            f"{client_id}; rotate the key pair, or update public_key_pem in "
            f"{clients_file}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clients-file", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--kid", required=True)
    args = parser.parse_args()

    try:
        validate_client_key_pair(
            clients_file=Path(args.clients_file),
            client_id=args.client_id,
            key_file=Path(args.key_file),
            kid=args.kid,
        )
    except Exception as exc:
        parser.exit(1, f"error: {exc}\n")

    print(f"OK: private key matches public_key_pem for {args.client_id}")


if __name__ == "__main__":
    main()
