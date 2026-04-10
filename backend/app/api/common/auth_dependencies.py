"""FastAPI authentication dependencies shared by common API routers."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.api.common.security import Role
from app.api.v0.security import verify_bearer_token
from app.schemas.common import validate_functional_id


class ParsedToken(BaseModel):
    """Structured representation of a decoded JWT payload."""

    model_config = ConfigDict(frozen=True)

    roles: list[str]
    client_id: str | None
    client_name: str | None


class Client(BaseModel):
    """Authenticated client identity extracted from JWT."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str | None = None


class NamedClient(BaseModel):
    """Authenticated client identity with a required display name."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str


async def get_parsed_token(
    token_payload: dict[str, Any] = Depends(verify_bearer_token),
) -> ParsedToken:
    """Parse the raw JWT payload into a structured token object."""

    realm_access = token_payload.get("realm_access", {})
    return ParsedToken(
        roles=realm_access.get("roles", []),
        client_id=token_payload.get("client_id"),
        client_name=token_payload.get("client_name"),
    )


class RequireRoles:
    """Callable FastAPI dependency that enforces required JWT realm roles."""

    def __init__(self, *required_roles: Role) -> None:
        self.required_roles = required_roles

    async def __call__(
        self,
        parsed_token: ParsedToken = Depends(get_parsed_token),
    ) -> ParsedToken:
        for role in self.required_roles:
            if role not in parsed_token.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access forbidden: '{role}' role required",
                )
        return parsed_token


async def get_client(
    parsed_token: ParsedToken = Depends(get_parsed_token),
) -> Client:
    """Extract a validated client id; client_name may be absent."""

    if not parsed_token.client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_id' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        validate_functional_id(parsed_token.client_id, "client_id")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from e
    return Client(id=parsed_token.client_id, name=parsed_token.client_name)


async def get_named_client(
    parsed_token: ParsedToken = Depends(get_parsed_token),
) -> NamedClient:
    """Extract a validated client id and required client name."""

    client = await get_client(parsed_token)
    if not parsed_token.client_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing 'client_name' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return NamedClient(id=client.id, name=parsed_token.client_name)


ParsedTokenDependency = Annotated[ParsedToken, Depends(get_parsed_token)]
ClientDependency = Annotated[Client, Depends(get_client)]
NamedClientDependency = Annotated[NamedClient, Depends(get_named_client)]


__all__ = [
    "Client",
    "ClientDependency",
    "NamedClient",
    "NamedClientDependency",
    "ParsedToken",
    "ParsedTokenDependency",
    "RequireRoles",
    "get_client",
    "get_named_client",
    "get_parsed_token",
]
