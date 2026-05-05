from __future__ import annotations

import httpx
import pytest
from app.api.common import openapi as openapi_utils
from app.api.common import security as common_security
from app.api.common.security import OAuth2ClientCredentials
from app.security.audit import _extract_jwt_roles
from fastapi import FastAPI, HTTPException
from fastapi.openapi.models import OAuthFlows
from fastapi.security import OAuth2
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
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


def test_get_keycloak_public_key_handles_configuration_and_http_errors(monkeypatch):
    common_security.get_keycloak_public_key.cache_clear()
    monkeypatch.setattr(common_security.settings, "KC_BASE_URL", "")
    with pytest.raises(common_security.AuthorizationServerOperationalError):
        common_security.get_keycloak_public_key()

    common_security.get_keycloak_public_key.cache_clear()
    monkeypatch.setattr(common_security.settings, "KC_BASE_URL", "https://kc.example")

    class SuccessfulResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"keys": [{"kid": "test-key"}]}

    def successful_get(url, **kwargs):
        assert url == "https://kc.example/realms/sdep/protocol/openid-connect/certs"
        assert kwargs == {"timeout": 10.0}
        return SuccessfulResponse()

    monkeypatch.setattr(common_security.httpx, "get", successful_get)
    assert common_security.get_keycloak_public_key() == {"keys": [{"kid": "test-key"}]}

    common_security.get_keycloak_public_key.cache_clear()

    def raise_error(*args, **kwargs):
        request = httpx.Request("GET", "https://kc.example")
        raise httpx.ConnectError("boom", request=request)

    monkeypatch.setattr(common_security.httpx, "get", raise_error)
    with pytest.raises(common_security.AuthorizationServerOperationalError):
        common_security.get_keycloak_public_key()


def test_validate_jwt_token_success_and_error_paths(monkeypatch):
    monkeypatch.setattr(
        common_security, "get_keycloak_public_key", lambda: {"keys": []}
    )
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
        lambda *args, **kwargs: (_ for _ in ()).throw(JWTClaimsError("bad claims")),
    )
    with pytest.raises(HTTPException, match="Invalid token claims"):
        common_security.validate_jwt_token("token")

    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(JWTError("bad token")),
    )
    with pytest.raises(HTTPException, match="Invalid token: bad token"):
        common_security.validate_jwt_token("token")

    monkeypatch.setattr(
        common_security.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("oops")),
    )
    with pytest.raises(HTTPException, match="Could not validate credentials"):
        common_security.validate_jwt_token("token")


@pytest.mark.asyncio
async def test_create_verify_bearer_token_dependency_and_oauth2_client_credentials(
    monkeypatch,
):
    oauth = OAuth2(flows=OAuthFlows())
    verify = common_security.create_verify_bearer_token(oauth)
    monkeypatch.setattr(
        common_security, "validate_jwt_token", lambda token: {"token": token}
    )

    assert await verify("abc") == {"token": "abc"}

    strict = OAuth2ClientCredentials(flows=OAuthFlows(), auto_error=True)
    with pytest.raises(HTTPException, match="Not authenticated"):
        await strict(_request())

    soft = OAuth2ClientCredentials(flows=OAuthFlows(), auto_error=False)
    assert await soft(_request()) is None
    assert await strict(_request(auth="Bearer hello")) == "hello"


def test_extract_jwt_roles_handles_missing_invalid_and_valid_tokens():
    assert _extract_jwt_roles(_request()) is None

    bad = _extract_jwt_roles(_request(auth="Bearer not-a-jwt"))
    assert bad is None

    token = jwt.encode(
        {"realm_access": {"roles": ["role-a", "role-b"]}},
        key="secret",
        algorithm="HS256",
    )
    assert _extract_jwt_roles(_request(auth=f"Bearer {token}")) == "role-a,role-b"
