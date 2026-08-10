#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0.0",
#   "typer>=0.12.0",
# ]
# ///
"""Show the JWKS public key stored for a Keycloak Signed JWT client."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import typer
import yaml


app = typer.Typer(add_completion=False)
# A tuple, not a set: error messages list the environments in this declared
# order rather than alphabetically.
VALID_ENVIRONMENTS = ("local", "acc", "tst", "pre", "prd")


def fail(message: str) -> None:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def load_realm_name(realm_config_yaml: Path) -> str:
    if not realm_config_yaml.is_file():
        fail(f"realm config not found: {realm_config_yaml}")

    with realm_config_yaml.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)

    realm_name = data.get("config", {}).get("name") if isinstance(data, dict) else None
    if not isinstance(realm_name, str) or not realm_name:
        fail(f"realm config must contain config.name: {realm_config_yaml}")
    return realm_name


def load_keycloak_env() -> str:
    keycloak_env = os.environ.get("KC_ENV", "").strip().lower()
    if not keycloak_env:
        fail(
            "KC_ENV must be set to one of: "
            f"{', '.join(VALID_ENVIRONMENTS)}"
        )
    if keycloak_env not in VALID_ENVIRONMENTS:
        fail(
            f"KC_ENV must be one of {', '.join(VALID_ENVIRONMENTS)}; "
            f"got {keycloak_env!r}"
        )
    return keycloak_env


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    form_data: dict[str, str] | None = None,
) -> Any:
    body = None
    request_headers = dict(headers or {})
    if form_data is not None:
        body = urlencode(form_data).encode()
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            response_body = response.read().decode()
    except HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        fail(f"HTTP {exc.code} from {url}: {error_body}")
    except URLError as exc:
        fail(f"could not reach {url}: {exc.reason}")

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON from {url}: {exc}")


def get_access_token(
    *,
    kc_base_url: str,
    realm_name: str,
    admin_client_id: str,
    admin_client_secret: str,
) -> str:
    token_response = request_json(
        f"{kc_base_url}/realms/{realm_name}/protocol/openid-connect/token",
        method="POST",
        form_data={
            "client_id": admin_client_id,
            "client_secret": admin_client_secret,
            "grant_type": "client_credentials",
        },
    )
    access_token = token_response.get("access_token") if isinstance(token_response, dict) else None
    if not isinstance(access_token, str) or not access_token:
        fail(f"Keycloak did not return an access token: {token_response}")
    return access_token


@app.command()
def main(
    client_id: Annotated[
        str,
        typer.Option("--client-id", envvar="KC_APP_REALM_CLIENT_ID", help="Keycloak client id to inspect."),
    ],
    kc_base_url: Annotated[
        str,
        typer.Option("--kc-base-url", envvar="KC_BASE_URL", help="Keycloak base URL."),
    ],
    realm_config_yaml: Annotated[
        Path,
        typer.Option(
            "--realm-config-yaml",
            envvar="KC_APP_REALM_CONFIG_YAML",
            help="Realm config YAML containing config.name.",
        ),
    ],
    admin_client_id: Annotated[
        str,
        typer.Option(
            "--admin-client-id",
            envvar="KC_APP_REALM_ADMIN_ID",
            help="Realm admin service-account client id.",
        ),
    ],
    admin_client_secret: Annotated[
        str,
        typer.Option(
            "--admin-client-secret",
            envvar="KC_APP_REALM_ADMIN_SECRET",
            help="Realm admin service-account client secret.",
        ),
    ],
) -> None:
    """Fetch a client through Keycloak's admin API and print its stored JWKS."""

    keycloak_env = load_keycloak_env()
    kc_base_url = kc_base_url.rstrip("/")
    realm_name = load_realm_name(realm_config_yaml)
    access_token = get_access_token(
        kc_base_url=kc_base_url,
        realm_name=realm_name,
        admin_client_id=admin_client_id,
        admin_client_secret=admin_client_secret,
    )

    clients = request_json(
        f"{kc_base_url}/admin/realms/{realm_name}/clients?{urlencode({'clientId': client_id})}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not isinstance(clients, list):
        fail(f"unexpected Keycloak client lookup response: {clients}")
    if not clients:
        fail(f"client not found: {client_id}")
    if len(clients) > 1:
        fail(f"multiple clients found for client id: {client_id}")

    client = clients[0]
    attributes = client.get("attributes") or {}
    auth_type = client.get("clientAuthenticatorType") or ""
    use_jwks_string = attributes.get("use.jwks.string") or ""
    jwks_string = attributes.get("jwks.string") or ""
    use_jwks_url = attributes.get("use.jwks.url") or ""
    jwks_url = attributes.get("jwks.url") or ""

    if auth_type != "client-jwt":
        fail(
            f"client {client_id} is not configured for Signed JWT authentication "
            f"(clientAuthenticatorType={auth_type or '<empty>'})"
        )
    if use_jwks_string != "true" or not jwks_string:
        fail(
            f"client {client_id} has no stored JWKS string "
            f"(use.jwks.string={use_jwks_string or '<empty>'})"
        )
    if use_jwks_url == "true" or jwks_url:
        fail(f"client {client_id} uses jwks.url; expected stored jwks.string only")

    try:
        jwks = json.loads(jwks_string)
    except json.JSONDecodeError as exc:
        fail(f"client {client_id} has invalid jwks.string JSON: {exc}")

    typer.echo(f"keycloakEnv: {keycloak_env}")
    typer.echo(f"clientId: {client_id}")
    typer.echo(f"clientAuthenticatorType: {auth_type}")
    typer.echo(f"use.jwks.string: {use_jwks_string}")
    typer.echo(f"use.jwks.url: {use_jwks_url or '<empty>'}")
    typer.echo(f"jwks.url: {jwks_url or '<empty>'}")
    typer.echo("jwks.string:")
    typer.echo(json.dumps(jwks, indent=2, sort_keys=True))


if __name__ == "__main__":
    app()
