#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "cryptography>=42.0.0",
#   "pyyaml>=6.0.0",
#   "typer>=0.12.0",
# ]
# ///
"""Generate the local Keycloak client-signed JWT test client files.

One client-signed JWT test client is generated per role (CA, STR, REP), so every
role can be exercised through the client_signed_jwt flow, not only STR. Each
client gets its own RSA key pair; the private key stays local (tmp/, gitignored)
and the derived public key is declared in the generated machine-client YAML.

Per client, using the client id as the file stem:

- ``<output-dir>/<client-id>.private.pem``: local private key, signs assertions
- ``<output-dir>/<client-id>.public.yaml``: single-client YAML fragment carrying
  the derived public key, for inspection and key-pair validation

The extended YAML (the file actually provisioned into Keycloak) is the tracked
static client-secret clients plus these generated client-signed JWT clients.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

app = typer.Typer(add_completion=False)


@dataclass(frozen=True)
class JwtClientSpec:
    """Declarative definition of a generated client-signed JWT test client."""

    client_id: str
    name: str
    description: str
    service_account_roles: tuple[str, ...]


# Roles mirror their client-secret counterparts in keycloak/machine-clients.yaml:
# CA and STR are read-write, REP is read-only.
JWT_CLIENT_SPECS: tuple[JwtClientSpec, ...] = (
    JwtClientSpec(
        client_id="sdep-test-ca.jwt",
        name="Test CA Signed JWT (test automation, ephemeral data)",
        description="CA client using client_signed_jwt authentication with a PEM public key",
        service_account_roles=("sdep_ca", "sdep_read", "sdep_write"),
    ),
    JwtClientSpec(
        client_id="sdep-test-str.jwt",
        name="Test STR Signed JWT (test automation, ephemeral data)",
        description="STR client using client_signed_jwt authentication with a PEM public key",
        service_account_roles=("sdep_str", "sdep_read", "sdep_write"),
    ),
    JwtClientSpec(
        client_id="sdep-test-rep.jwt",
        name="Test REP Signed JWT (test automation, ephemeral data)",
        description="REP client using client_signed_jwt authentication with a PEM public key",
        service_account_roles=("sdep_rep", "sdep_read"),
    ),
)


def fail(message: str) -> None:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


class LiteralString(str):
    """YAML string rendered as a block scalar."""


def literal_string_representer(
    dumper: yaml.SafeDumper, data: LiteralString
) -> yaml.nodes.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.SafeDumper.add_representer(LiteralString, literal_string_representer)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"YAML file not found: {path}")
    with path.open(encoding="utf-8") as yaml_file:
        data = yaml.safe_load(yaml_file)
    if not isinstance(data, dict):
        fail(f"YAML file must contain a mapping: {path}")
    clients = data.get("clients")
    if not isinstance(clients, list):
        fail(f"YAML file must contain a top-level clients list: {path}")
    return data


def private_key_file_for(output_dir: Path, client_id: str) -> Path:
    return output_dir / f"{client_id}.private.pem"


def public_clients_file_for(output_dir: Path, client_id: str) -> Path:
    return output_dir / f"{client_id}.public.yaml"


def generate_private_key(private_key_file: Path) -> None:
    if private_key_file.is_file():
        typer.echo(f"Reusing client-signed JWT private key: {private_key_file}")
        return

    typer.echo(f"Generating client-signed JWT private key: {private_key_file}")
    private_key_file.parent.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_file.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    os.chmod(private_key_file, 0o600)


def derive_public_key_pem(private_key_file: Path) -> str:
    if not private_key_file.is_file():
        fail(f"private key file not found: {private_key_file}")

    private_key = serialization.load_pem_private_key(
        private_key_file.read_bytes(), password=None
    )
    if not isinstance(private_key, rsa.RSAPrivateKey):
        fail(f"private key must contain an RSA private key: {private_key_file}")

    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return public_key_pem.decode("ascii")


def build_client(spec: JwtClientSpec, public_key_pem: str) -> dict[str, Any]:
    return {
        "id": spec.client_id,
        "auth_type": "client-jwt",
        "name": spec.name,
        "description": spec.description,
        "jwks_kid": spec.client_id,
        "public_key_pem": LiteralString(public_key_pem),
        "service_account_roles": list(spec.service_account_roles),
    }


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as yaml_file:
        yaml.safe_dump(data, yaml_file, sort_keys=False, allow_unicode=False)


@app.command()
def main(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            envvar="KEYCLOAK_JWT_CLIENT_DIR",
            help="Directory for the generated private keys and public-key YAML.",
        ),
    ] = Path("tmp"),
    static_clients_file: Annotated[
        Path,
        typer.Option(
            "--static-clients-file",
            help="Tracked static machine-client YAML.",
        ),
    ] = Path("keycloak/machine-clients.yaml"),
    extended_clients_file: Annotated[
        Path,
        typer.Option(
            "--extended-clients-file",
            envvar="MACHINE_CLIENTS_EXTENDED_YAML",
            help="Extended machine-client YAML used for provisioning.",
        ),
    ] = Path("tmp/machine-clients-extended.yaml"),
) -> None:
    """Generate the local JWT key pairs and extended machine-client YAML."""

    generated_clients: list[dict[str, Any]] = []

    for spec in JWT_CLIENT_SPECS:
        private_key_file = private_key_file_for(output_dir, spec.client_id)
        generate_private_key(private_key_file)
        client = build_client(spec, derive_public_key_pem(private_key_file))

        public_clients_file = public_clients_file_for(output_dir, spec.client_id)
        typer.echo(
            f"Writing local JWT machine-client configuration: {public_clients_file}"
        )
        write_yaml(public_clients_file, {"clients": [client]})
        generated_clients.append(client)

    static_data = load_yaml(static_clients_file)
    merged_data = {
        **static_data,
        "clients": list(static_data["clients"]) + generated_clients,
    }
    typer.echo(
        f"Writing extended machine-client configuration: {extended_clients_file}"
    )
    write_yaml(extended_clients_file, merged_data)
    typer.echo(f"Machine client configuration: {extended_clients_file}")


if __name__ == "__main__":
    app()
