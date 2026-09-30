"""Tests for the listing (random check) endpoints across every audience.

The lifecycle runs through the real sub-apps: STR v2 submits, LSA screens,
STR v2 reads and acknowledges, CA v2 / LMA v2 / STA v2 read. Every audience only
sees its fixed scope (docs/LISTING_FUNC.md).
"""

from typing import Any

import pytest
import pytest_asyncio
from app.api.common.security import verify_bearer_token
from app.api.domains.ca.v2 import app_ca_v2
from app.api.domains.lma.v2 import app_lma_v2
from app.api.domains.lsa.v2 import app_lsa_v2
from app.api.domains.sta.v2 import app_sta_v2
from app.api.domains.str.v2 import app_str_v2
from app.crud import listing as listing_crud
from app.db.config import get_async_db, get_async_db_read_only
from app.models.listing import Listing
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import AreaFactory, CompetentAuthorityFactory

CA_ID = "0363"
OTHER_CA_ID = "0599"
STR_CLIENT = "str-listings-test"


def _token(roles: list[str], client_id: str, name: str):
    def mock() -> dict[str, Any]:
        return {
            "sub": client_id,
            "client_id": client_id,
            "client_name": name,
            "realm_access": {"roles": roles},
        }

    return mock


TOKENS = {
    app_str_v2: _token(["sdep_str", "sdep_write", "sdep_read"], STR_CLIENT, "Test STR"),
    app_lsa_v2: _token(
        ["sdep_lsa", "sdep_write", "sdep_read"], "lsa01", "Screening Authority"
    ),
    app_ca_v2: _token(["sdep_ca", "sdep_read"], CA_ID, "Gemeente Amsterdam"),
    app_lma_v2: _token(["sdep_lma", "sdep_read"], "lma01", "Monitor"),
    app_sta_v2: _token(["sdep_sta", "sdep_read"], "cbs01", "Statistics Authority"),
}

ADDRESS = {
    "thoroughfare": "Turfmarkt",
    "locatorDesignatorNumber": 147,
    "postCode": "2500EA",
    "postName": "Den Haag",
    "fullAddress": "Turfmarkt 147, 2500EA Den Haag",
}


def _listing(area_id: str, suffix: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "listingId": f"listing-{suffix}",
        "areaId": area_id,
        "url": f"http://example.com/{suffix}",
        "address": ADDRESS,
        "declaredAsShortTermRental": True,
        "registrationNumber": f"REG-{suffix}",
    }
    base.update(overrides)
    return base


async def _post(app, path: str, body: dict[str, Any]):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(path, json=body, headers={"Authorization": "Bearer t"})


async def _get(app, path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers={"Authorization": "Bearer t"})


def _ids(body: dict[str, Any]) -> list[str]:
    return [item["listingId"] for item in body["listings"]]


async def _acknowledged(area_id: str, suffix: str) -> None:
    """Submit, flag and acknowledge one listing: steps 3, 4 and 6."""
    submitted = await _post(
        app_str_v2, "/listings/bulk", {"listings": [_listing(area_id, suffix)]}
    )
    listing = submitted.json()["results"][0]["listing"]
    screened = await _post(
        app_lsa_v2,
        "/listing-screenings/bulk",
        {
            "screenings": [
                {
                    "platformId": listing["platformId"],
                    "listingId": listing["listingId"],
                    "createdAt": listing["createdAt"],
                    "flags": ["UNK"],
                }
            ]
        },
    )
    listing = screened.json()["results"][0]["listing"]
    response = await _post(
        app_str_v2,
        "/listing-acknowledgements/bulk",
        {
            "acknowledgements": [
                {"listingId": listing["listingId"], "createdAt": listing["createdAt"]}
            ]
        },
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text


@pytest.mark.database
class TestListingsLifecycle:
    @pytest.fixture
    def setup_overrides(self, async_session: AsyncSession):
        async def override_get_db():
            yield async_session

        for app, token in TOKENS.items():
            app.dependency_overrides[verify_bearer_token] = token
            app.dependency_overrides[get_async_db] = override_get_db
            app.dependency_overrides[get_async_db_read_only] = override_get_db
        yield
        for app in TOKENS:
            app.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def areas(self, async_session: AsyncSession) -> dict[str, str]:
        """Amsterdam owns a listing-regulated and an activity-only area; Rotterdam one more."""
        ca = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id=CA_ID,
            competent_authority_name="Gemeente Amsterdam",
        )
        other = await CompetentAuthorityFactory.create_async(
            async_session,
            competent_authority_id=OTHER_CA_ID,
            competent_authority_name="Gemeente Rotterdam",
        )
        ids: dict[str, str] = {}
        for name, regulation, owner in (
            ("listing", "listing", ca),
            ("activity", "activity", ca),
            ("other", "all", other),
        ):
            area = await AreaFactory.create_async(
                async_session,
                area_id=f"area-{name}",
                area_name=f"Area {name}",
                regulation=regulation,
                competent_authority_id=owner.id,
                filename=f"{name}.zip",
                filedata=b"zip",
            )
            ids[name] = area.area_id
        return ids

    async def test_full_lifecycle_and_audience_scopes(self, setup_overrides, areas):
        # 3. STR submits: two listings in Amsterdam, one in Rotterdam, one refused
        response = await _post(
            app_str_v2,
            "/listings/bulk",
            {
                "listings": [
                    _listing(areas["listing"], "a"),
                    _listing(areas["listing"], "b", registrationNumber=None),
                    _listing(areas["other"], "c"),
                    _listing(areas["activity"], "d"),
                ]
            },
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert (body["succeeded"], body["failed"]) == (3, 1)
        assert body["results"][3]["errors"]["detail"][0]["type"] == "regulation_error"
        submitted = {r["listingId"]: r["listing"] for r in body["results"][:3]}
        platform_id = submitted["listing-a"]["platformId"]
        assert submitted["listing-a"]["createdAt"].endswith("Z")
        assert submitted["listing-a"]["status"] == "pending"
        assert "registrationNumber" not in submitted["listing-b"] or (
            submitted["listing-b"]["registrationNumber"] is None
        )

        # STR sees nothing yet: nothing is flagged
        response = await _get(app_str_v2, "/listings")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"listings": []}
        assert (await _get(app_str_v2, "/listings/count")).json() == {"count": 0}

        # 4. LSA sees the pending listings, also per platform
        response = await _get(app_lsa_v2, "/listings")
        assert set(_ids(response.json())) == {"listing-a", "listing-b", "listing-c"}
        response = await _get(app_lsa_v2, f"/listings/count?platformId={platform_id}")
        assert response.json() == {"count": 3}
        response = await _get(app_lsa_v2, f"/listings?areaId={areas['other']}")
        assert _ids(response.json()) == ["listing-c"]

        # LSA screens: a flagged, b clear, c flagged
        response = await _post(
            app_lsa_v2,
            "/listing-screenings/bulk",
            {
                "screenings": [
                    {
                        "platformId": platform_id,
                        "listingId": "listing-a",
                        "createdAt": submitted["listing-a"]["createdAt"],
                        "flags": ["UNK"],
                    },
                    {
                        "platformId": platform_id,
                        "listingId": "listing-b",
                        "createdAt": submitted["listing-b"]["createdAt"],
                        "flags": [],
                    },
                    {
                        "platformId": platform_id,
                        "listingId": "listing-c",
                        "createdAt": submitted["listing-c"]["createdAt"],
                        "flags": ["UDS", "EXP"],
                    },
                ]
            },
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        screened = {r["listingId"]: r["listing"] for r in response.json()["results"]}
        assert screened["listing-a"]["status"] == "flagged"
        assert screened["listing-b"]["status"] == "clear"
        assert screened["listing-c"]["flags"] == ["UDS", "EXP"]
        assert screened["listing-a"]["screenedAt"] is not None
        assert (
            screened["listing-a"]["submittedAt"]
            == submitted["listing-a"]["submittedAt"]
        )

        # LSA queue is empty now
        assert (await _get(app_lsa_v2, "/listings/count")).json() == {"count": 0}

        # 5. STR sees its flagged listings (not the clear one), with filters
        response = await _get(app_str_v2, "/listings")
        assert set(_ids(response.json())) == {"listing-a", "listing-c"}
        response = await _get(app_str_v2, f"/listings?areaId={areas['other']}")
        assert _ids(response.json()) == ["listing-c"]
        token = screened["listing-a"]["createdAt"]
        response = await _get(
            app_str_v2, f"/listings/count?createdAtFrom={token}&createdAtTo={token}"
        )
        assert response.json() == {"count": 2}

        # Nobody sees anything acknowledged yet
        assert (await _get(app_ca_v2, "/listings/count")).json() == {"count": 0}

        # 6. STR acknowledges a; a retry and a stale token are refused
        acknowledgement = {"listingId": "listing-a", "createdAt": token}
        response = await _post(
            app_str_v2,
            "/listing-acknowledgements/bulk",
            {"acknowledgements": [acknowledgement]},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        acknowledged = response.json()["results"][0]["listing"]
        assert acknowledged["status"] == "acknowledged"
        assert acknowledged["flags"] == ["UNK"]
        assert acknowledged["acknowledgedAt"] is not None

        response = await _post(
            app_str_v2,
            "/listing-acknowledgements/bulk",
            {"acknowledgements": [acknowledgement]},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = response.json()["results"][0]["errors"]["detail"][0]
        assert (detail["type"], detail["loc"]) == ("conflict_error", ["createdAt"])

        # STR now only sees c as flagged
        assert _ids((await _get(app_str_v2, "/listings")).json()) == ["listing-c"]

        # 8. CA sees the acknowledged listing in its own areas only
        response = await _get(app_ca_v2, "/listings")
        assert _ids(response.json()) == ["listing-a"]
        assert (await _get(app_ca_v2, "/listings/count?flags=UNK,EXP")).json() == {
            "count": 1
        }
        assert (await _get(app_ca_v2, "/listings/count?flags=EXP")).json() == {
            "count": 0
        }
        response = await _get(app_ca_v2, "/listings?flags=NOPE")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"][0]["loc"][:2] == ["query", "flags"]

        # 10/12. LMA and STA see everything, in every status
        for app in (app_lma_v2, app_sta_v2):
            response = await _get(app, "/listings")
            assert set(_ids(response.json())) == {"listing-a", "listing-b", "listing-c"}
            assert (await _get(app, "/listings/count")).json() == {"count": 3}
            response = await _get(app, "/listings?status=flagged")
            assert _ids(response.json()) == ["listing-c"]
            response = await _get(app, f"/listings?flags=UDS&platformId={platform_id}")
            assert _ids(response.json()) == ["listing-c"]
            response = await _get(app, "/listings/count?status=clear")
            assert response.json() == {"count": 1}
            response = await _get(app, "/listings?createdAtFrom=2026-01-01T00:00:00")
            assert response.status_code == status.HTTP_400_BAD_REQUEST

        # A re-screen of the acknowledged listing is final: refused
        response = await _post(
            app_lsa_v2,
            "/listing-screenings/bulk",
            {
                "screenings": [
                    {
                        "platformId": platform_id,
                        "listingId": "listing-a",
                        "createdAt": acknowledged["createdAt"],
                        "flags": [],
                    }
                ]
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "already acknowledged" in response.text

    async def test_submit_correction_while_pending(self, setup_overrides, areas):
        first = await _post(
            app_str_v2,
            "/listings/bulk",
            {"listings": [_listing(areas["listing"], "x")]},
        )
        assert first.status_code == status.HTTP_201_CREATED
        second = await _post(
            app_str_v2,
            "/listings/bulk",
            {"listings": [_listing(areas["listing"], "x", listingName="Corrected")]},
        )
        assert second.status_code == status.HTTP_201_CREATED
        assert second.json()["results"][0]["listing"]["listingName"] == "Corrected"
        assert (await _get(app_lsa_v2, "/listings/count")).json() == {"count": 1}
        pending = (await _get(app_lsa_v2, "/listings")).json()["listings"][0]
        assert pending["listingName"] == "Corrected"
        assert (
            pending["createdAt"] != first.json()["results"][0]["listing"]["createdAt"]
        )

    async def test_str_reads_own_platform_only(self, setup_overrides, areas):
        posted = await _post(
            app_str_v2,
            "/listings/bulk",
            {"listings": [_listing(areas["listing"], "y")]},
        )
        listing = posted.json()["results"][0]["listing"]
        await _post(
            app_lsa_v2,
            "/listing-screenings/bulk",
            {
                "screenings": [
                    {
                        "platformId": listing["platformId"],
                        "listingId": "listing-y",
                        "createdAt": listing["createdAt"],
                        "flags": ["ABS"],
                    }
                ]
            },
        )
        assert (await _get(app_str_v2, "/listings/count")).json() == {"count": 1}
        app_str_v2.dependency_overrides[verify_bearer_token] = _token(
            ["sdep_str", "sdep_read", "sdep_write"], "another-platform", "Other"
        )
        assert (await _get(app_str_v2, "/listings/count")).json() == {"count": 0}
        # Another platform cannot acknowledge it either (no platform row yet)
        response = await _post(
            app_str_v2,
            "/listing-acknowledgements/bulk",
            {
                "acknowledgements": [
                    {"listingId": "listing-y", "createdAt": listing["createdAt"]}
                ]
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert (
            response.json()["results"][0]["errors"]["detail"][0]["type"]
            == "not_found_error"
        )

    async def test_ca_reads_own_areas_only(self, setup_overrides, areas):
        # One acknowledged listing per competent authority
        await _acknowledged(areas["listing"], "own")
        await _acknowledged(areas["other"], "foreign")

        assert _ids((await _get(app_ca_v2, "/listings")).json()) == ["listing-own"]
        assert (await _get(app_ca_v2, "/listings/count")).json() == {"count": 1}
        # A filter cannot widen the scope to another authority's area
        response = await _get(app_ca_v2, f"/listings?areaId={areas['other']}")
        assert response.json() == {"listings": []}

        app_ca_v2.dependency_overrides[verify_bearer_token] = _token(
            ["sdep_ca", "sdep_read"], OTHER_CA_ID, "Gemeente Rotterdam"
        )
        assert _ids((await _get(app_ca_v2, "/listings")).json()) == ["listing-foreign"]
        assert (await _get(app_ca_v2, "/listings/count")).json() == {"count": 1}

    async def test_competent_authority_filter(self, setup_overrides, areas):
        # One pending listing per competent authority
        response = await _post(
            app_str_v2,
            "/listings/bulk",
            {
                "listings": [
                    _listing(areas["listing"], "own"),
                    _listing(areas["other"], "foreign"),
                ]
            },
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        submitted = [r["listing"] for r in response.json()["results"]]

        for app in (app_lsa_v2, app_lma_v2, app_sta_v2):
            response = await _get(app, f"/listings?competentAuthorityId={CA_ID}")
            assert _ids(response.json()) == ["listing-own"], app
            response = await _get(
                app, f"/listings/count?competentAuthorityId={OTHER_CA_ID}"
            )
            assert response.json() == {"count": 1}, app
            response = await _get(app, "/listings/count?competentAuthorityId=none")
            assert response.json() == {"count": 0}, app

        # STR reads flagged listings only, so flag both first
        response = await _post(
            app_lsa_v2,
            "/listing-screenings/bulk",
            {
                "screenings": [
                    {
                        "platformId": listing["platformId"],
                        "listingId": listing["listingId"],
                        "createdAt": listing["createdAt"],
                        "flags": ["UNK"],
                    }
                    for listing in submitted
                ]
            },
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        response = await _get(
            app_str_v2, f"/listings?competentAuthorityId={OTHER_CA_ID}"
        )
        assert _ids(response.json()) == ["listing-foreign"]
        response = await _get(
            app_str_v2, f"/listings/count?competentAuthorityId={CA_ID}"
        )
        assert response.json() == {"count": 1}

    async def test_failed_batch_rolls_back(
        self, setup_overrides, write_transaction, areas, async_session, monkeypatch
    ):
        # A correction ends the pending version, then fails before the insert
        await _post(
            app_str_v2,
            "/listings/bulk",
            {"listings": [_listing(areas["listing"], "r")]},
        )
        app_str_v2.dependency_overrides.pop(get_async_db)

        async def _fail(session: AsyncSession, *args: Any) -> None:
            with session.no_autoflush:  # The new versions are not added yet
                ended_at = await session.scalar(
                    select(Listing.ended_at).where(Listing.listing_id == "listing-r")
                )
            assert ended_at is not None  # So there is something to roll back
            raise RuntimeError("insert failed")

        monkeypatch.setattr(listing_crud, "bulk_create", _fail)
        with pytest.raises(RuntimeError, match="insert failed"):
            await _post(
                app_str_v2,
                "/listings/bulk",
                {"listings": [_listing(areas["listing"], "r", listingName="New")]},
            )

        # The end mark is rolled back: the first version is still the current one
        async_session.expire_all()
        versions = (
            await async_session.scalars(
                select(Listing).where(Listing.listing_id == "listing-r")
            )
        ).all()
        assert [(v.listing_name, v.ended_at) for v in versions] == [(None, None)]

    @pytest.mark.parametrize(
        ("app", "method", "path", "body"),
        [
            (app_str_v2, "GET", "/listings", None),
            (app_str_v2, "GET", "/listings/count", None),
            (app_str_v2, "POST", "/listings/bulk", {"listings": [{}]}),
            (
                app_str_v2,
                "POST",
                "/listing-acknowledgements/bulk",
                {"acknowledgements": [{}]},
            ),
            (app_lsa_v2, "GET", "/listings", None),
            (app_lsa_v2, "GET", "/listings/count", None),
            (app_lsa_v2, "POST", "/listing-screenings/bulk", {"screenings": [{}]}),
            (app_ca_v2, "GET", "/listings", None),
            (app_ca_v2, "GET", "/listings/count", None),
            (app_lma_v2, "GET", "/listings", None),
            (app_lma_v2, "GET", "/listings/count", None),
            (app_sta_v2, "GET", "/listings", None),
            (app_sta_v2, "GET", "/listings/count", None),
        ],
    )
    async def test_requires_audience_role(
        self, setup_overrides, app, method, path, body
    ):
        app.dependency_overrides[verify_bearer_token] = _token(
            ["sdep_read", "sdep_write"], "no-audience", "No audience"
        )
        if method == "GET":
            response = await _get(app, path)
        else:
            response = await _post(app, path, body or {})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_read_only_audiences_reject_writes(self, setup_overrides):
        for app in (app_lma_v2, app_sta_v2, app_ca_v2):
            response = await _post(app, "/listings", {})
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_bulk_envelope_is_validated(self, setup_overrides):
        response = await _post(app_str_v2, "/listings/bulk", {"listings": []})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        response = await _post(
            app_lsa_v2, "/listing-screenings/bulk", {"screenings": ["x"]}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert (
            response.json()["results"][0]["errors"]["detail"][0]["type"] == "model_type"
        )
