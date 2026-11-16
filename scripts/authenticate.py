#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6,<7",
# ]
# ///
"""Authenticate as a client-signed JWT machine client, step by step, as a real client does.

Steps (each prints the shell command it runs, for learning):
  client-signed-jwt  create a client-signed JWT          -> <key-dir>/<client>-<env>.client-signed-jwt
  bearer             exchange it at /token for a bearer  -> <key-dir>/<client>-<env>.bearer
  ping               call the authenticated ping endpoint with the bearer

Asks for the client name (default: CLIENT_NAME), finds the client in the clients YAML and its
private key in the key dir. Reads SDEP_BASE_URL, SDEP_TOKEN_URL and CLIENT_SIGNED_JWT_AUDIENCE
from the environment.

Usage: scripts/authenticate.py {client-signed-jwt|bearer|ping} --clients-file F --key-dir D --env-label L
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent
URL_VARS = ["SDEP_BASE_URL", "SDEP_TOKEN_URL", "CLIENT_SIGNED_JWT_AUDIENCE"]
# A token closer than this to its expiry counts as expired: it may expire on the way
MARGIN_SECONDS = 10
# A tuple, not "except A, B": that form needs Python 3.14, the script runs on 3.11+
MALFORMED_TOKEN = (IndexError, ValueError, KeyError)


def abort(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def rel(path: Path) -> str:
    """Path as typed on the command line: relative to the current directory when possible."""
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def run_shown(cmd: str) -> subprocess.CompletedProcess[str]:
    """Print the command, then run exactly that command with bash."""
    print(f"\n$ {cmd}\n")
    return subprocess.run(["bash", "-c", cmd], text=True, capture_output=True)


# -- Client and key lookup


def ask_client_name() -> str:
    default = os.environ.get("CLIENT_NAME", "")
    if not sys.stdin.isatty():
        return default
    value = input(f"Client name [{default}]: ").strip()
    return value or default


def find_client(clients_file: Path, name: str) -> dict:
    """Client-signed JWT client with this id, or with this text in its name (case-insensitive)."""
    clients = (yaml.safe_load(clients_file.read_text()) or {}).get("clients") or []
    jwt_clients = [c for c in clients if c.get("auth_type") == "client-jwt"]
    matches = [c for c in jwt_clients if c.get("id") == name]
    matches = matches or [
        c for c in jwt_clients if name.lower() in str(c.get("name", "")).lower()
    ]
    if not matches:
        print(f"Client-signed JWT clients in {rel(clients_file)}:")
        for c in jwt_clients:
            print(f"  - {c.get('name')}")
        abort(f"no client-signed JWT client matches '{name}'")
    if len(matches) == 1:
        return matches[0]
    print(f"Clients that match '{name}':")
    for i, c in enumerate(matches, 1):
        print(f"  {i}. {c.get('name')}")
    choice = input("Number: ").strip() if sys.stdin.isatty() else ""
    if not choice.isdigit() or not 1 <= int(choice) <= len(matches):
        abort("no client chosen")
    return matches[int(choice) - 1]


def public_key(pem_or_path: str | Path) -> str | None:
    """Public key in one canonical form (base64 body), from a public PEM or a private key file."""
    if isinstance(pem_or_path, Path):
        # -passin: an encrypted key fails at once, instead of prompting for a passphrase
        args = [
            "openssl",
            "pkey",
            "-in",
            str(pem_or_path),
            "-pubout",
            "-passin",
            "pass:",
        ]
        res = subprocess.run(args, capture_output=True, text=True)
    else:
        args = ["openssl", "pkey", "-pubin", "-pubout"]
        res = subprocess.run(args, input=pem_or_path, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    return "".join(
        line for line in res.stdout.splitlines() if not line.startswith("-----")
    )


def find_private_key(client: dict, key_dir: Path) -> Path:
    """The private key in key_dir whose public half equals the client's public key in the YAML.

    Matching by key, not by filename, so a key of another environment or client is never used.
    """
    wanted = public_key(client.get("public_key_pem", ""))
    if not wanted:
        abort(f"client '{client.get('name')}' has no readable public_key_pem")
    candidates = [
        p
        for p in sorted(key_dir.rglob("*"))
        if p.is_file()
        and p.stat().st_size < 20_000
        and "PRIVATE KEY-----" in p.read_text(errors="ignore")
    ]
    for p in candidates:
        if public_key(p) == wanted:
            return p
    print(
        f"Private keys in {rel(key_dir)}/ (none matches the public key of '{client.get('name')}'):"
    )
    for p in candidates:
        print(f"  - {rel(p)}")
    abort(f"place the private key of '{client.get('name')}' in {rel(key_dir)}/")
    return Path()


# -- Token files


def jwt_exp(token: str) -> int:
    """The exp claim of a JWT, read without checking the signature (only to see if it is stale)."""
    try:
        payload = token.split(".")[1]
        return int(
            json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))[
                "exp"
            ]
        )
    except MALFORMED_TOKEN:
        return 0


def seconds_left(path: Path) -> int:
    return jwt_exp(path.read_text().strip()) - int(time.time())


def fresh(path: Path) -> bool:
    return path.is_file() and seconds_left(path) > MARGIN_SECONDS


class Session:
    def __init__(self, args: argparse.Namespace):
        missing = [v for v in URL_VARS if not os.environ.get(v)]
        if missing:
            abort(f"not set: {', '.join(missing)} (load the env file first)")
        name = ask_client_name()
        if not name:
            abort("a client name is required")
        self.client = find_client(args.clients_file, name)
        # Keeps the chosen client as the default of the next step
        self.make_args = (
            "" if name == os.environ.get("CLIENT_NAME") else f' CLIENT_NAME="{name}"'
        )
        self.client_id = self.client["id"]
        self.kid = self.client.get("jwks_kid") or self.client_id
        # File prefix from the client's name without its "(...)" remark, plus the environment,
        # e.g. "ictu-devops-tst": the same files whatever part of the name was typed
        base = re.sub(r"\(.*?\)", "", self.client["name"])
        slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
        prefix = args.key_dir / f"{slug}-{args.env_label}"
        self.key_dir = args.key_dir
        self.jwt_file = prefix.with_name(prefix.name + ".client-signed-jwt")
        self.response_file = prefix.with_name(prefix.name + ".token-response.json")
        self.bearer_file = prefix.with_name(prefix.name + ".bearer")
        print(f"🔐 Client: {self.client['name']} ({self.client_id})")
        # The printed commands use these variables: export them to copy-paste a command
        for var in URL_VARS:
            print(f'   export {var}="{os.environ[var]}"')

    def suggest_next(self, step: str) -> None:
        """Printed once, after the step that was asked for, not after a step it ran on its own."""
        if step == "client-signed-jwt":
            print(f"\n👉 Next step, within 60 seconds: make bearer{self.make_args}")
            print(
                "   One-time use: /token accepts a client-signed JWT once, make bearer creates a new one when needed"
            )
        elif step == "bearer":
            print(f"\n👉 Next step: make ping{self.make_args}")
        else:
            print(
                f'\n👉 Next step: call any endpoint with -H "Authorization: Bearer $(cat {rel(self.bearer_file)})"'
            )

    def client_signed_jwt(self) -> None:
        key_file = find_private_key(self.client, self.key_dir)
        print(f"🔑 Private key: {rel(key_file)}")
        script = rel(SCRIPTS / "create-client-signed-jwt.py")
        q = shlex.quote
        res = run_shown(
            f'uv run --script {q(script)} --token-url "$CLIENT_SIGNED_JWT_AUDIENCE" '
            f"--client-id {q(self.client_id)} --key-file {q(rel(key_file))} --kid {q(self.kid)} "
            f"> {q(rel(self.jwt_file))}"
        )
        if res.returncode != 0:
            self.jwt_file.unlink(missing_ok=True)
            abort(f"creating the client-signed JWT failed:\n{res.stderr}")
        print(
            f"✅ Client-signed JWT in {rel(self.jwt_file)} (valid 60 seconds, usable once)"
        )

    def bearer(self) -> None:
        # /token accepts a client-signed JWT once: the file is removed after use, see below
        if fresh(self.jwt_file):
            print(
                f"♻️ Reusing {rel(self.jwt_file)}: unused, {seconds_left(self.jwt_file)} seconds left"
            )
        else:
            print("🔄 No unused, valid client-signed JWT: creating one first")
            self.client_signed_jwt()
        q = shlex.quote
        res = run_shown(
            f'curl -sS -X POST "$SDEP_TOKEN_URL" '
            f'-H "Content-Type: application/x-www-form-urlencoded" '
            f'--data-urlencode "grant_type=client_credentials" '
            f"--data-urlencode {q('client_id=' + self.client_id)} "
            f'--data-urlencode "client_signed_jwt=$(cat {q(rel(self.jwt_file))})" '
            f"> {q(rel(self.response_file))}"
        )
        self.jwt_file.unlink(missing_ok=True)
        if res.returncode != 0:
            abort(f"calling /token failed:\n{res.stderr}")
        res = run_shown(
            f"jq -er .access_token {q(rel(self.response_file))} > {q(rel(self.bearer_file))}"
        )
        if res.returncode != 0:
            self.bearer_file.unlink(missing_ok=True)
            abort(
                f"no access token in the token response:\n{self.response_file.read_text()}"
            )
        expires_in = json.loads(self.response_file.read_text()).get("expires_in", "?")
        print(f"✅ Bearer in {rel(self.bearer_file)} (valid {expires_in} seconds)")

    def ping(self) -> None:
        if fresh(self.bearer_file):
            print(
                f"♻️ Reusing {rel(self.bearer_file)}: {seconds_left(self.bearer_file)} seconds left, "
                "so no new client-signed JWT or bearer is needed"
            )
        else:
            print("🔄 No valid bearer: getting one first")
            self.bearer()
        q = shlex.quote
        res = run_shown(
            f"curl -sS -w '\\nHTTP %{{http_code}}\\n' \"$SDEP_BASE_URL/api/ping\" "
            f'-H "Authorization: Bearer $(cat {q(rel(self.bearer_file))})"'
        )
        print(res.stdout, end="")
        if res.returncode != 0 or not res.stdout.rstrip().endswith("HTTP 200"):
            abort(f"ping failed {res.stderr}")
        print("✅ Ping OK")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("step", choices=["client-signed-jwt", "bearer", "ping"])
    parser.add_argument(
        "--clients-file", type=Path, required=True, help="machine clients YAML"
    )
    parser.add_argument(
        "--key-dir",
        type=Path,
        required=True,
        help="directory with the private key, gets the output",
    )
    parser.add_argument(
        "--env-label",
        required=True,
        help="environment in the output filenames, e.g. tst",
    )
    args = parser.parse_args()
    if not args.clients_file.is_file():
        abort(f"clients file not found: {args.clients_file}")
    # Tokens and keys are secrets: files this script (and its commands) create are owner-only
    os.umask(0o077)
    session = Session(args)
    getattr(session, args.step.replace("-", "_"))()
    session.suggest_next(args.step)


if __name__ == "__main__":
    main()
