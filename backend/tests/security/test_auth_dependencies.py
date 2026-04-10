"""Unit tests for common auth dependencies."""

from typing import Any

import pytest
from app.api.common.auth_dependencies import (
    Client,
    NamedClient,
    ParsedToken,
    RequireRoles,
    get_client,
    get_named_client,
    get_parsed_token,
)
from app.api.common.security import Role
from fastapi import HTTPException, status


def _raw_token(
    *,
    roles: list[str] | None = None,
    client_id: str | None = "str01",
    client_name: str | None = "Platform 01",
) -> dict[str, Any]:
    token: dict[str, Any] = {}
    if roles is not None:
        token["realm_access"] = {"roles": roles}
    if client_id is not None:
        token["client_id"] = client_id
    if client_name is not None:
        token["client_name"] = client_name
    return token


def _parsed_token(
    *,
    roles: list[str] | None = None,
    client_id: str | None = "str01",
    client_name: str | None = "Platform 01",
) -> ParsedToken:
    return ParsedToken(
        roles=roles or [],
        client_id=client_id,
        client_name=client_name,
    )


@pytest.mark.asyncio
class TestGetParsedToken:
    async def test_get_parsed_token_parses_full_payload(self):
        """Parse a complete JWT payload into a structured token."""
        parsed_token = await get_parsed_token(
            _raw_token(
                roles=[Role.STR, Role.WRITE],
                client_id="str01",
                client_name="Platform 01",
            )
        )

        assert parsed_token == ParsedToken(
            roles=[Role.STR, Role.WRITE],
            client_id="str01",
            client_name="Platform 01",
        )

    async def test_get_parsed_token_defaults_missing_fields(self):
        """Default missing JWT fields to empty roles and null claims."""
        parsed_token = await get_parsed_token(
            _raw_token(client_id=None, client_name=None)
        )

        assert parsed_token.roles == []
        assert parsed_token.client_id is None
        assert parsed_token.client_name is None


@pytest.mark.asyncio
class TestRequireRoles:
    async def test_require_roles_allows_single_required_role(self):
        """Allow access when the single required role is present."""
        parsed_token = _parsed_token(roles=[Role.CA])

        dependency = RequireRoles(Role.CA)

        assert await dependency(parsed_token) is parsed_token

    async def test_require_roles_allows_multiple_required_roles(self):
        """Allow access when all required roles are present."""
        parsed_token = _parsed_token(roles=[Role.CA, Role.READ, Role.WRITE])

        dependency = RequireRoles(Role.CA, Role.READ)

        assert await dependency(parsed_token) is parsed_token

    async def test_require_roles_raises_403_when_role_missing(self):
        """Reject access when a required role is missing."""
        parsed_token = _parsed_token(roles=[Role.READ])

        dependency = RequireRoles(Role.CA)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(parsed_token)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "Access forbidden: 'sdep_ca' role required"

    async def test_require_roles_raises_403_when_one_of_multiple_roles_missing(self):
        """Reject access when one role in a multi-role check is missing."""
        parsed_token = _parsed_token(roles=[Role.CA])

        dependency = RequireRoles(Role.CA, Role.READ)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(parsed_token)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "Access forbidden: 'sdep_read' role required"


@pytest.mark.asyncio
class TestGetClient:
    async def test_get_client_returns_client_with_name(self):
        """Return a client when id and name are both available."""
        client = await get_client(
            _parsed_token(client_id="str01", client_name="Platform 01")
        )

        assert client == Client(id="str01", name="Platform 01")

    async def test_get_client_returns_client_without_name(self):
        """Return a client when only a valid client id is available."""
        client = await get_client(_parsed_token(client_id="str01", client_name=None))

        assert client == Client(id="str01", name=None)

    async def test_get_client_raises_401_when_client_id_missing(self):
        """Reject tokens that do not include a client id claim."""
        with pytest.raises(HTTPException) as exc_info:
            await get_client(_parsed_token(client_id=None))

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid token: missing 'client_id' claim"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    async def test_get_client_raises_422_when_client_id_invalid(self):
        """Reject tokens whose client id is not a valid functional ID."""
        with pytest.raises(HTTPException) as exc_info:
            await get_client(_parsed_token(client_id="invalid id"))

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in exc_info.value.detail


@pytest.mark.asyncio
class TestGetNamedClient:
    async def test_get_named_client_returns_client(self):
        """Return a named client when id and name are both present."""
        client = await get_named_client(
            _parsed_token(client_id="str01", client_name="Platform 01")
        )

        assert client == NamedClient(id="str01", name="Platform 01")

    async def test_get_named_client_raises_401_when_client_id_missing(self):
        """Reject named-client access when the client id claim is missing."""
        with pytest.raises(HTTPException) as exc_info:
            await get_named_client(_parsed_token(client_id=None))

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid token: missing 'client_id' claim"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    async def test_get_named_client_raises_401_when_client_name_missing(self):
        """Reject named-client access when the client name claim is missing."""
        with pytest.raises(HTTPException) as exc_info:
            await get_named_client(_parsed_token(client_name=None))

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid token: missing 'client_name' claim"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    async def test_get_named_client_raises_422_when_client_id_invalid(self):
        """Reject named-client access when the client id is invalid."""
        with pytest.raises(HTTPException) as exc_info:
            await get_named_client(
                _parsed_token(client_id="invalid id", client_name="Platform 01")
            )

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "client_id" in exc_info.value.detail
