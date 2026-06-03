from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.api.common import openapi as openapi_utils
from app.api.common import security as common_security
from app.api.common.exception_handlers import register_exception_handlers
from app.api.common.security import OAuth2ClientCredentials
from app.security.audit import _extract_jwt_roles
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.openapi.models import OAuthFlows
from fastapi.security import OAuth2
from httpx import ASGITransport, AsyncClient
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidTokenError,
    PyJWKClientError,
)
from starlette.requests import Request


def _request(path: str = "/api/test", auth: str | None = None) -> Request:
    headers = []
    if auth is not None:
        headers.append((b"authorization", auth.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": path,
            "headers": headers,
            "query_string": b"",
            "scheme": "http",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


def test_replace_auto_generated_body_schemas_returns_original_without_components():
    schema = {"paths": {}}

    result = openapi_utils.replace_auto_generated_body_schemas(schema)

    assert result is schema


def test_replace_auto_generated_body_schemas_renames_components_and_refs():
    schema = {
        "components": {
            "schemas": {
                "Body_post_auth_token": {"title": "old title", "type": "object"},
                "Body_postArea": {"title": "old area", "type": "object"},
            }
        },
        "paths": {
            "/auth/token": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "$ref": "#/components/schemas/Body_post_auth_token"
                                }
                            }
                        }
                    }
                }
            }
        },
    }

    result = openapi_utils.replace_auto_generated_body_schemas(schema)

    assert "Body_post_auth_token" not in result["components"]["schemas"]
    assert (
        result["components"]["schemas"]["Auth.TokenRequest"]["title"]
        == "Auth.TokenRequest"
    )
    assert result["components"]["schemas"]["Area.Request"]["title"] == "Area.Request"
    assert (
        result["paths"]["/auth/token"]["post"]["requestBody"]["content"][
            "application/x-www-form-urlencoded"
        ]["schema"]["$ref"]
        == "#/components/schemas/Auth.TokenRequest"
    )


def test_replace_auto_generated_body_schemas_handles_missing_items_and_existing_ref():
    no_items_schema = {
        "components": {"schemas": {"ActivityBulkRequest": {"properties": {}}}}
    }
    existing_ref_schema = {
        "components": {
            "schemas": {
                "ActivityBulkRequest": {
                    "properties": {
                        "activities": {
                            "items": {"$ref": "#/components/schemas/ActivityRequest"}
                        }
                    }
                }
            }
        }
    }

    assert (
        openapi_utils.replace_auto_generated_body_schemas(no_items_schema)
        is no_items_schema
    )
    assert (
        openapi_utils.replace_auto_generated_body_schemas(existing_ref_schema)
        is existing_ref_schema
    )


def test_replace_auto_generated_body_schemas_returns_original_when_items_use_ref():
    schema = {
        "components": {
            "schemas": {
                "ActivityBulkRequest": {
                    "properties": {
                        "activities": {
                            "items": {"$ref": "#/components/schemas/ActivityRequest"}
                        }
                    }
                }
            }
        }
    }

    result = openapi_utils.replace_auto_generated_body_schemas(schema)

    assert result is schema


def test_extract_bulk_activity_item_schema_returns_original_when_items_use_ref():
    schema = {
        "components": {
            "schemas": {
                "ActivityBulkRequest": {
                    "properties": {
                        "activities": {
                            "items": {"$ref": "#/components/schemas/ActivityRequest"}
                        }
                    }
                }
            }
        }
    }

    result = openapi_utils.extract_bulk_activity_item_schema(schema)

    assert result is schema


def test_remove_fastapi_validation_schemas_and_422_responses():
    schema = {
        "components": {
            "schemas": {
                "HTTPValidationError": {},
                "ValidationError": {},
                "KeepMe": {},
            }
        },
        "paths": {
            "/auth/token": {"post": {"responses": {"422": {}, "200": {}}}},
            "/areas": {"get": {"responses": {"422": {}, "200": {}}}},
        },
    }

    schema = openapi_utils.remove_fastapi_validation_schemas(schema)
    schema = openapi_utils.remove_inapplicable_422_responses(schema)

    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert "ValidationError" not in schema["components"]["schemas"]
    assert "KeepMe" in schema["components"]["schemas"]
    assert "422" in schema["paths"]["/auth/token"]["post"]["responses"]
    assert "422" not in schema["paths"]["/areas"]["get"]["responses"]


def test_sort_schemas_by_namespace_and_handle_missing_components():
    empty_schema = {"paths": {}}
    assert openapi_utils.sort_schemas_by_namespace(empty_schema) is empty_schema

    schema = {
        "components": {
            "schemas": {
                "Zed": {"title": "zzz"},
                "Area": {"title": "area.AreaResponse"},
                "Auth": {"title": "auth.TokenRequest"},
            }
        }
    }

    result = openapi_utils.sort_schemas_by_namespace(schema)

    assert list(result["components"]["schemas"].keys()) == ["Area", "Auth", "Zed"]


def test_create_custom_openapi_caches_and_reuses_generated_schema():
    app = FastAPI()
    calls = {"count": 0}

    def original_openapi():
        calls["count"] += 1
        return {
            "components": {"schemas": {"Body_post_auth_token": {"title": "x"}}},
            "paths": {"/auth/token": {"post": {"responses": {"422": {}}}}},
        }

    app.openapi = original_openapi
    custom = openapi_utils.create_custom_openapi(app)

    first = custom()
    second = custom()

    assert first is second
    assert calls["count"] == 1
    assert "Auth.TokenRequest" in first["components"]["schemas"]


def test_get_jwks_client_handles_configuration_errors(monkeypatch):
    monkeypatch.setattr(common_security, "_jwks_client", None)
    monkeypatch.setattr(common_security.settings, "KC_BASE_URL", "")
    with pytest.raises(common_security.AuthorizationServerOperationalError):
        common_security._get_jwks_client()


def test_get_jwks_client_creates_client_with_correct_url(monkeypatch):
    monkeypatch.setattr(common_security, "_jwks_client", None)
    monkeypatch.setattr(common_security.settings, "KC_BASE_URL", "https://kc.example")

    with patch("app.api.common.security.PyJWKClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        client = common_security._get_jwks_client()

        mock_cls.assert_called_once_with(
            "https://kc.example/realms/sdep/protocol/openid-connect/certs",
            cache_jwk_set=True,
            lifespan=common_security.JWKS_CACHE_TTL,
        )
        assert client is mock_cls.return_value

    monkeypatch.setattr(common_security, "_jwks_client", None)


def test_get_jwks_client_returns_cached_instance(monkeypatch):
    sentinel = MagicMock()
    monkeypatch.setattr(common_security, "_jwks_client", sentinel)
    assert common_security._get_jwks_client() is sentinel


def test_get_jwks_client_returns_cached_instance_inside_lock(monkeypatch):
    sentinel = MagicMock()
    real_lock = common_security._jwks_client_lock

    class _LockThatSimulatesRace:
        def __enter__(self):
            real_lock.__enter__()
            common_security._jwks_client = sentinel
            return self

        def __exit__(self, *args):
            return real_lock.__exit__(*args)

    monkeypatch.setattr(common_security, "_jwks_client", None)
    monkeypatch.setattr(common_security, "_jwks_client_lock", _LockThatSimulatesRace())
    assert common_security._get_jwks_client() is sentinel
    monkeypatch.setattr(common_security, "_jwks_client", None)


def test_get_jwks_client_wraps_constructor_exception(monkeypatch):
    monkeypatch.setattr(common_security, "_jwks_client", None)
    monkeypatch.setattr(common_security.settings, "KC_BASE_URL", "https://kc.example")

    with (
        patch(
            "app.api.common.security.PyJWKClient",
            side_effect=RuntimeError("connection refused"),
        ),
        pytest.raises(
            common_security.AuthorizationServerOperationalError,
            match="Failed to initialize",
        ),
    ):
        common_security._get_jwks_client()

    monkeypatch.setattr(common_security, "_jwks_client", None)


def test_validate_jwt_token_success_and_error_paths(monkeypatch):
    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = "test-key"
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    monkeypatch.setattr(common_security, "_get_jwks_client", lambda: mock_client)

    monkeypatch.setattr(
        common_security.jwt, "decode", lambda *args, **kwargs: {"sub": "ok"}
    )
    assert common_security.validate_jwt_token("token") == {"sub": "ok"}

    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(ExpiredSignatureError("expired")),
    )
    with pytest.raises(HTTPException, match="Token has expired"):
        common_security.validate_jwt_token("token")

    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            InvalidAudienceError("bad audience")
        ),
    )
    with pytest.raises(HTTPException, match="Invalid token claims"):
        common_security.validate_jwt_token("token")

    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(DecodeError("bad token")),
    )
    with pytest.raises(HTTPException, match="Invalid token: bad token"):
        common_security.validate_jwt_token("token")

    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(InvalidTokenError("invalid")),
    )
    with pytest.raises(HTTPException, match="Invalid token: invalid"):
        common_security.validate_jwt_token("token")

    # A JWKS fetch failure (network/HTTP error talking to Keycloak) is a dependency
    # outage, not a bad token: it must surface as AuthorizationServerOperationalError
    # (-> 503), never as a 401.
    mock_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("jwks down")
    with pytest.raises(
        common_security.AuthorizationServerOperationalError,
        match="Failed to fetch signing keys from Keycloak",
    ):
        common_security.validate_jwt_token("token")
    mock_client.get_signing_key_from_jwt.side_effect = None
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    # An operational error from the JWKS client setup propagates unchanged so the
    # registered handler can map it to 503.
    monkeypatch.setattr(
        common_security,
        "_get_jwks_client",
        lambda: (_ for _ in ()).throw(
            common_security.AuthorizationServerOperationalError("kc unconfigured")
        ),
    )
    with pytest.raises(
        common_security.AuthorizationServerOperationalError, match="kc unconfigured"
    ):
        common_security.validate_jwt_token("token")
    monkeypatch.setattr(common_security, "_get_jwks_client", lambda: mock_client)

    # Genuinely unexpected errors are no longer masked as 401: they propagate so the
    # registered general handler returns 500 with a full server-side traceback.
    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("oops")),
    )
    with pytest.raises(RuntimeError, match="oops"):
        common_security.validate_jwt_token("token")


@pytest.mark.asyncio
async def test_protected_endpoint_maps_jwt_errors_to_http_status_end_to_end(
    monkeypatch,
):
    """End-to-end wiring guard for issue #165.

    Drives a real request through an app wired with the standard exception
    handlers and the real ``verify_bearer_token`` dependency, and asserts the
    HTTP status a client actually receives when JWT validation fails:

    - Authorization server unreachable/misconfigured -> 503 (the fix)
    - JWKS fetch failure -> 503
    - Genuinely invalid token -> 401
    - Unexpected error -> 500 (never masked as 401, never mislabeled 503)
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected")
    async def _protected(_payload=Depends(common_security.verify_bearer_token)):
        return {"ok": True}

    async def _status() -> int:
        # raise_app_exceptions=False so the 500 case returns a response instead of
        # propagating (Starlette's ServerErrorMiddleware re-raises after responding).
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/protected", headers={"Authorization": "Bearer dummy-token"}
            )
        return response.status_code

    # Authorization server unreachable/misconfigured -> 503 (core of #165).
    monkeypatch.setattr(
        common_security,
        "_get_jwks_client",
        lambda: (_ for _ in ()).throw(
            common_security.AuthorizationServerOperationalError("kc down")
        ),
    )
    assert await _status() == status.HTTP_503_SERVICE_UNAVAILABLE

    # JWKS fetch failure (network/HTTP error) -> 503.
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = PyJWKClientError("jwks down")
    monkeypatch.setattr(common_security, "_get_jwks_client", lambda: mock_client)
    assert await _status() == status.HTTP_503_SERVICE_UNAVAILABLE

    # Genuinely invalid token -> 401.
    mock_client.get_signing_key_from_jwt.side_effect = None
    mock_client.get_signing_key_from_jwt.return_value = MagicMock(key="k")
    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(DecodeError("nope")),
    )
    assert await _status() == status.HTTP_401_UNAUTHORIZED

    # Unexpected error -> 500, never masked as 401 nor mislabeled as 503.
    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert await _status() == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
async def test_create_verify_bearer_token_dependency_and_oauth2_client_credentials(
    monkeypatch,
):
    oauth = OAuth2(flows=OAuthFlows())
    verify = common_security.create_verify_bearer_token(oauth)
    monkeypatch.setattr(
        common_security, "validate_jwt_token", lambda token: {"token": token}
    )

    # verify_bearer_token now stashes the verified payload on request.state so
    # the audit middleware can reuse it without re-decoding the token.
    request = _request()
    assert await verify(request, "abc") == {"token": "abc"}
    assert request.state.jwt_payload == {"token": "abc"}

    strict = OAuth2ClientCredentials(flows=OAuthFlows(), auto_error=True)
    with pytest.raises(HTTPException, match="Not authenticated"):
        await strict(_request())

    soft = OAuth2ClientCredentials(flows=OAuthFlows(), auto_error=False)
    assert await soft(_request()) is None
    assert await strict(_request(auth="Bearer hello")) == "hello"


def test_extract_jwt_roles_reads_from_request_state():
    """_extract_jwt_roles reads only from request.state.jwt_payload.

    The audit middleware never re-decodes the Authorization header: a request
    without a stashed payload yields None even if it carries a bearer token,
    and a request with a stashed payload yields the joined roles list.
    """
    # No payload on state → None, even when an Authorization header is present
    assert _extract_jwt_roles(_request()) is None
    assert _extract_jwt_roles(_request(auth="Bearer not-a-jwt")) is None

    # Empty / missing realm_access → None
    request_empty = _request()
    request_empty.state.jwt_payload = {}
    assert _extract_jwt_roles(request_empty) is None

    request_no_roles = _request()
    request_no_roles.state.jwt_payload = {"realm_access": {"roles": []}}
    assert _extract_jwt_roles(request_no_roles) is None

    # Verified payload → comma-joined roles
    request_with_roles = _request()
    request_with_roles.state.jwt_payload = {
        "realm_access": {"roles": ["role-a", "role-b"]}
    }
    assert _extract_jwt_roles(request_with_roles) == "role-a,role-b"
