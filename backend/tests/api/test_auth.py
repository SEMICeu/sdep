import base64

import httpx
import pytest
from app.api.common.routers import auth as auth_router
from app.api.domains.auth.v1 import app_auth_v1
from fastapi import status
from httpx import ASGITransport, AsyncClient


class _MockResponse:
    def __init__(
        self, status_code: int, payload=None, json_error: Exception | None = None
    ):
        self.status_code = status_code
        self._payload = payload or {}
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _MockAsyncClient:
    def __init__(
        self, response: _MockResponse | None = None, error: Exception | None = None
    ):
        self.response = response
        self.error = error
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, data=None, headers=None):
        self.calls.append({"url": url, "data": data, "headers": headers})
        if self.error is not None:
            raise self.error
        return self.response


@pytest.mark.asyncio
class TestAuthRouter:
    async def test_token_uses_basic_auth_credentials(self, monkeypatch):
        fake_client = _MockAsyncClient(
            response=_MockResponse(
                200,
                {
                    "access_token": "abc123",
                    "token_type": "Bearer",
                    "expires_in": 120,
                },
            )
        )
        monkeypatch.setattr(auth_router.settings, "KC_BASE_URL", "https://kc.example")
        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda **_: fake_client)

        credentials = base64.b64encode(b"client-a:secret-a").decode()
        async with AsyncClient(
            transport=ASGITransport(app=app_auth_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/token",
                headers={"Authorization": f"Basic {credentials}"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "access_token": "abc123",
            "token_type": "Bearer",
            "expires_in": 120,
        }
        assert fake_client.calls[0]["data"] == {
            "grant_type": "client_credentials",
            "client_id": "client-a",
            "client_secret": "secret-a",
        }
        assert (
            fake_client.calls[0]["url"]
            == "https://kc.example/realms/sdep/protocol/openid-connect/token"
        )

    async def test_token_prefers_form_credentials_over_basic_auth(self, monkeypatch):
        fake_client = _MockAsyncClient(
            response=_MockResponse(200, {"access_token": "abc"})
        )
        monkeypatch.setattr(auth_router.settings, "KC_BASE_URL", "https://kc.example/")
        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda **_: fake_client)

        credentials = base64.b64encode(b"basic-client:basic-secret").decode()
        async with AsyncClient(
            transport=ASGITransport(app=app_auth_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/token",
                data={"client_id": "form-client", "client_secret": "form-secret"},
                headers={"Authorization": f"Basic {credentials}"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["token_type"] == "bearer"
        assert response.json()["expires_in"] == 300
        assert fake_client.calls[0]["data"]["client_id"] == "form-client"
        assert fake_client.calls[0]["data"]["client_secret"] == "form-secret"

    async def test_token_rejects_missing_credentials_after_bad_basic_auth(
        self, monkeypatch
    ):
        monkeypatch.setattr(auth_router.settings, "KC_BASE_URL", "https://kc.example")

        async with AsyncClient(
            transport=ASGITransport(app=app_auth_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/token",
                headers={"Authorization": "Basic ###not-base64###"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "Client credentials must be provided" in response.json()["detail"][0]["msg"]
        )

    async def test_token_rejects_missing_keycloak_configuration(self, monkeypatch):
        monkeypatch.setattr(auth_router.settings, "KC_BASE_URL", "")

        async with AsyncClient(
            transport=ASGITransport(app=app_auth_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/token",
                data={"client_id": "client-a", "client_secret": "secret-a"},
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert (
            "Authorization server is temporarily unavailable"
            in response.json()["detail"][0]["msg"]
        )

    async def test_token_returns_keycloak_json_error_description(self, monkeypatch):
        fake_client = _MockAsyncClient(
            response=_MockResponse(401, {"error_description": "bad credentials"})
        )
        monkeypatch.setattr(auth_router.settings, "KC_BASE_URL", "https://kc.example")
        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda **_: fake_client)

        async with AsyncClient(
            transport=ASGITransport(app=app_auth_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/token",
                data={"client_id": "client-a", "client_secret": "secret-a"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["detail"][0]["msg"] == "bad credentials"

    async def test_token_returns_generic_error_when_keycloak_body_is_not_json(
        self, monkeypatch
    ):
        fake_client = _MockAsyncClient(
            response=_MockResponse(401, json_error=ValueError("not json"))
        )
        monkeypatch.setattr(auth_router.settings, "KC_BASE_URL", "https://kc.example")
        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda **_: fake_client)

        async with AsyncClient(
            transport=ASGITransport(app=app_auth_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/token",
                data={"client_id": "client-a", "client_secret": "secret-a"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"][0]["msg"] == "Authentication failed"

    async def test_token_wraps_request_errors_as_service_unavailable(self, monkeypatch):
        request = httpx.Request("POST", "https://kc.example/token")
        fake_client = _MockAsyncClient(
            error=httpx.RequestError("network down", request=request)
        )
        monkeypatch.setattr(auth_router.settings, "KC_BASE_URL", "https://kc.example")
        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda **_: fake_client)

        async with AsyncClient(
            transport=ASGITransport(app=app_auth_v1), base_url="http://test"
        ) as client:
            response = await client.post(
                "/token",
                data={"client_id": "client-a", "client_secret": "secret-a"},
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert (
            "Authorization server is temporarily unavailable"
            in response.json()["detail"][0]["msg"]
        )
