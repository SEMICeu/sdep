"""Alpha API versions are served up to PRE only (docs/API_TECH.md "Design").

Checked on what a client sees: the mounted routes and the docs landing page, per value of
API_ALPHA_ENABLED, plus the startup guard that refuses the flag in PRD.
"""

import pytest
from app.api.common_app import app_common
from app.api.domain_registry import API_DOMAINS, served_api_domains
from app.config import Settings, settings
from app.main import DOMAIN_APPS, mount_domain_apps
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

ALPHA = [domain for domain in API_DOMAINS if domain.status == "alpha"]
NON_ALPHA = [domain for domain in API_DOMAINS if domain.status != "alpha"]


def _mounted_app() -> FastAPI:
    root_app = FastAPI()
    mount_domain_apps(root_app)

    return root_app


async def _get(app: FastAPI, path: str) -> int:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return (await client.get(path)).status_code


async def _landing_page() -> str:
    async with AsyncClient(
        transport=ASGITransport(app=app_common), base_url="http://test"
    ) as client:
        return (await client.get("/docs")).text


def test_there_are_alpha_versions_to_guard() -> None:
    # Without alpha versions the tests below pass vacuously.
    assert ALPHA
    assert NON_ALPHA


def test_every_domain_version_has_a_sub_app() -> None:
    assert [domain for domain, _app in DOMAIN_APPS] == list(API_DOMAINS)


class TestAlphaDisabled:
    @pytest.fixture(autouse=True)
    def _alpha_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "API_ALPHA_ENABLED", False)

    def test_registry_leaves_out_alpha(self) -> None:
        assert list(served_api_domains()) == NON_ALPHA

    @pytest.mark.asyncio
    async def test_alpha_versions_are_not_mounted(self) -> None:
        app = _mounted_app()

        for domain in ALPHA:
            assert await _get(app, domain.openapi_path) == 404, domain.label
        for domain in NON_ALPHA:
            assert await _get(app, domain.openapi_path) == 200, domain.label

    @pytest.mark.asyncio
    async def test_alpha_write_endpoint_is_unreachable(self) -> None:
        """A 404, not a 401: the write path does not exist, so no data can reach the database."""
        async with AsyncClient(
            transport=ASGITransport(app=_mounted_app()), base_url="http://test"
        ) as client:
            response = await client.post("/api/str/v2/listings/bulk", json={})

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_landing_page_leaves_out_alpha(self) -> None:
        body = await _landing_page()

        for domain in ALPHA:
            assert f'href="{domain.docs_path}"' not in body, domain.label
        for domain in NON_ALPHA:
            assert f'href="{domain.docs_path}"' in body, domain.label
        # The listings group only holds alpha versions today, so its heading goes too.
        assert "v2 (listings)" not in body


class TestAlphaEnabled:
    @pytest.fixture(autouse=True)
    def _alpha_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "API_ALPHA_ENABLED", True)

    @pytest.mark.asyncio
    async def test_every_version_is_mounted(self) -> None:
        app = _mounted_app()

        for domain in API_DOMAINS:
            assert await _get(app, domain.openapi_path) == 200, domain.label

    @pytest.mark.asyncio
    async def test_landing_page_lists_alpha(self) -> None:
        body = await _landing_page()

        for domain in API_DOMAINS:
            assert f'href="{domain.docs_path}"' in body, domain.label


class TestProductionGuard:
    @pytest.mark.parametrize("dtap", ["PRD", "prd"])
    def test_alpha_in_prd_refuses_to_start(self, dtap: str) -> None:
        with pytest.raises(ValidationError, match="API_ALPHA_ENABLED"):
            Settings(DTAP=dtap, API_ALPHA_ENABLED=True)

    def test_prd_without_alpha_starts(self) -> None:
        assert Settings(DTAP="PRD", API_ALPHA_ENABLED=False).API_ALPHA_ENABLED is False

    def test_pre_with_alpha_starts(self) -> None:
        assert Settings(DTAP="PRE", API_ALPHA_ENABLED=True).API_ALPHA_ENABLED is True

    def test_alpha_is_off_by_default(self) -> None:
        assert Settings.model_fields["API_ALPHA_ENABLED"].default is False
