#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
#     "pyjwt[crypto]>=2.10.1",
# ]
# ///

# Test OAuth 2.0 token acquisition and role enforcement for the client-signed-JWT
# (private_key_jwt) machine clients. For each selected client (CA, STR, REP) it signs
# a short-lived assertion with the matching local private key, exchanges it for a
# bearer token via /api/auth/{API_VERSION}/token (client_signed_jwt), and then proves
# the token carries the right roles:
#
#   1. token acquisition                            -> 200 + access_token
#   2. call the client's own role endpoint          -> 200
#   3. call the two other roles' endpoints          -> 403
#
# Step 3 is what makes this more than a login test: a token that authenticates but
# grants the wrong roles would pass step 1 and 2 of its own role only. The role
# endpoints come from the full client registry below, not from the selected subset,
# so a run narrowed to a single client keeps its cross-role checks (see
# selected_clients).
#
# This is the end-to-end proof of the private_key_jwt authentication method against a
# real Keycloak: it depends on the sdep-test-*.jwt clients being provisioned with the
# matching public keys, and on the backend forwarding the assertion to Keycloak. It
# runs against the local docker-compose stack (all clients) and, through the CI/CD
# pipeline that reuses it, against deployed environments (the subset that environment
# provisions).
#
# Scope note: in this repository the suite is developer-local. It is not part of the
# CI gate and contributes nothing to the enforced 100% coverage target - the CI-gated
# proof of the same backend code path is backend/tests/api/test_auth.py, which mocks
# Keycloak.
#
# Only read-only "count" endpoints are used, so the test creates no data and stays
# idempotent.
#
# Expects BACKEND_BASE_URL. Optional:
# - CLIENT_SIGNED_JWT_AUDIENCE - the assertion "aud". Required for deployed
#   environments, where the public issuer URL differs from both the admin URL and the
#   in-cluster URL the backend forwards to. When unset it is derived from
#   BACKEND_KC_BASE_URL (falling back to KC_BASE_URL) plus the realm token path.
# - JWT_PROVISION_CLIENTS (default false) - run "make keycloak-configure" first. Only
#   ever true for the local stack: against a deployed environment it would re-provision
#   that Keycloak from locally generated key pairs.
# - JWT_KEY_DIR (default tmp) - directory holding "<client-id>.private.pem"
# - JWT_CLIENT_IDS - comma-separated subset of the clients below, default all
# - KC_REALM (default sdep), API_VERSION (default v1)
#
# Note: key paths are not configured per client anywhere - they follow from the
# client id by convention ("<JWT_KEY_DIR>/<client-id>.private.pem"), the same
# convention the generator writes them with.

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
import jwt


@dataclass(frozen=True)
class JwtTestClient:
    """A generated client-signed JWT client and the endpoint proving its role."""

    client_id: str
    role: str
    # Read-only endpoint requiring this client's role; "{version}" is substituted.
    role_endpoint: str


# Mirrors JWT_CLIENT_SPECS in scripts/generate-keycloak-machine-clients.py.
JWT_TEST_CLIENTS: tuple[JwtTestClient, ...] = (
    JwtTestClient(
        client_id="sdep-test-ca.jwt",
        role="CA",
        role_endpoint="/api/ca/{version}/areas/count",
    ),
    JwtTestClient(
        client_id="sdep-test-str.jwt",
        role="STR",
        role_endpoint="/api/str/{version}/areas/count",
    ),
    JwtTestClient(
        client_id="sdep-test-rep.jwt",
        role="REP",
        role_endpoint="/api/rep/{version}/activities/count",
    ),
)


@dataclass
class TestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0

    def record(self, ok: bool, message: str) -> None:
        self.total += 1
        if ok:
            self.passed += 1
            print(f"  OK   {message}")
        else:
            self.failed += 1
            print(f"  FAIL {message}")


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is not set")
        sys.exit(1)
    return value


def selected_clients() -> tuple[JwtTestClient, ...]:
    requested = os.getenv("JWT_CLIENT_IDS", "").strip()
    if not requested:
        return JWT_TEST_CLIENTS

    wanted = [
        client_id.strip() for client_id in requested.split(",") if client_id.strip()
    ]
    known = {client.client_id: client for client in JWT_TEST_CLIENTS}
    unknown = [client_id for client_id in wanted if client_id not in known]
    if unknown:
        print(f"Error: unknown JWT_CLIENT_IDS entries: {', '.join(unknown)}")
        sys.exit(1)
    return tuple(known[client_id] for client_id in wanted)


def build_client_signed_jwt(
    *, audience: str, client_id: str, private_key_pem: str, kid: str
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": client_id,
            "sub": client_id,
            "aud": audience,
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
        },
        private_key_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def provision_machine_clients(repo_dir: Path) -> None:
    print(
        "Provisioning Keycloak machine clients from generated local configuration",
        flush=True,
    )
    try:
        subprocess.run(
            ["make", "--no-print-directory", "keycloak-configure"],
            cwd=repo_dir,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Machine-client provisioning failed with exit code {exc.returncode}")
        raise


def acquire_token(
    *,
    http_client: httpx.Client,
    base_url: str,
    api_version: str,
    audience: str,
    client: JwtTestClient,
    key_file: Path,
) -> tuple[str | None, str]:
    """Return (access_token, message); access_token is None when acquisition failed."""

    if not key_file.is_file():
        return None, f"{client.client_id}: private key file not found: {key_file}"

    client_signed_jwt = build_client_signed_jwt(
        audience=audience,
        client_id=client.client_id,
        private_key_pem=key_file.read_text(encoding="utf-8"),
        kid=client.client_id,
    )

    response = http_client.post(
        f"{base_url}/api/auth/{api_version}/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client.client_id,
            "client_signed_jwt": client_signed_jwt,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code != 200:
        return None, (
            f"{client.client_id}: token acquisition returned HTTP "
            f"{response.status_code} (expected 200): {response.text}"
        )

    try:
        access_token = str(response.json().get("access_token", ""))
    except json.JSONDecodeError:
        access_token = ""

    if not access_token:
        return None, f"{client.client_id}: no access_token in token response"

    return access_token, f"{client.client_id}: token acquired"


def check_endpoint(
    *,
    http_client: httpx.Client,
    base_url: str,
    path: str,
    access_token: str,
    expected_status: int,
) -> tuple[bool, str]:
    response = http_client.get(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    ok = response.status_code == expected_status
    detail = f"GET {path} -> {response.status_code} (expected {expected_status})"
    return ok, detail


def main() -> int:
    repo_dir = Path(__file__).resolve().parents[1]
    base_url = env("BACKEND_BASE_URL").rstrip("/")
    api_version = os.getenv("API_VERSION", "v1")
    realm = os.getenv("KC_REALM", "sdep")
    key_dir = Path(os.getenv("JWT_KEY_DIR", "tmp"))
    clients = selected_clients()

    # Keycloak validates the assertion "aud" against its own token endpoint. Deployed
    # environments therefore have to state it: their public issuer URL is a third URL,
    # distinct from both the admin URL (KC_BASE_URL) and the in-cluster URL the backend
    # forwards to (BACKEND_KC_BASE_URL). Only the local stack can derive it, where the
    # URL the backend forwards to *is* the issuer (realm hardcoded to "sdep" in the
    # auth router).
    audience = os.getenv("CLIENT_SIGNED_JWT_AUDIENCE", "").strip()
    if not audience:
        kc_base_url = os.getenv("BACKEND_KC_BASE_URL") or env("KC_BASE_URL")
        audience = (
            f"{kc_base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token"
        )

    print("Testing client-signed-JWT (private_key_jwt) credentials")
    print("------------------------------------------------")
    print(f"Clients: {', '.join(client.client_id for client in clients)}")
    print(f"Key directory: {key_dir}")
    print(f"Assertion audience: {audience}")
    print(f"Endpoint: {base_url}/api/auth/{api_version}/token")
    print()
    sys.stdout.flush()

    stats = TestStats()

    # Opt-in, and default off: provisioning re-creates the machine clients from
    # locally generated key pairs, which is right for the local stack and destructive
    # against a deployed environment.
    if os.getenv("JWT_PROVISION_CLIENTS", "false").lower() == "true":
        try:
            provision_machine_clients(repo_dir)
        except subprocess.CalledProcessError:
            stats.record(False, "machine-client provisioning")
            return _summary(stats)

    with httpx.Client(timeout=30.0) as http_client:
        for client in clients:
            print()
            print(f"--- {client.client_id} ({client.role}) ---")

            access_token, message = acquire_token(
                http_client=http_client,
                base_url=base_url,
                api_version=api_version,
                audience=audience,
                client=client,
                key_file=key_dir / f"{client.client_id}.private.pem",
            )
            stats.record(access_token is not None, message)

            # Every client is checked against every *known* role endpoint: its own
            # must be granted, the other roles' must be refused. Iterating the full
            # registry rather than `clients` keeps the cross-role checks when a run is
            # narrowed with JWT_CLIENT_IDS - a 403 needs the other role's endpoint,
            # not the other role's client.
            for other in JWT_TEST_CLIENTS:
                path = other.role_endpoint.format(version=api_version)
                in_role = other.client_id == client.client_id
                expected_status = 200 if in_role else 403
                label = "own role" if in_role else f"{other.role} role (not granted)"

                if access_token is None:
                    stats.record(
                        False, f"{client.client_id}: {label} - skipped, no access token"
                    )
                    continue

                ok, detail = check_endpoint(
                    http_client=http_client,
                    base_url=base_url,
                    path=path,
                    access_token=access_token,
                    expected_status=expected_status,
                )
                stats.record(ok, f"{client.client_id}: {label} - {detail}")

    return _summary(stats)


def _summary(stats: TestStats) -> int:
    print()
    print("=======================================")
    print("Test Summary (auth client-signed JWT):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")

    if stats.failed == 0:
        print("All client-signed-JWT tests passed!")
        return 0

    print("Some client-signed-JWT tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
