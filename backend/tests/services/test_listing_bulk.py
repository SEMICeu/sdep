"""Tests for the three listing bulk services, through the database."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.enums import ListingStatus
from app.schemas.listing import ListingScope
from app.services import listing as listing_service
from app.services.listing_acknowledgement_bulk import acknowledge_listings_bulk
from app.services.listing_bulk import create_listings_bulk
from app.services.listing_screening_bulk import screen_listings_bulk
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import (
    AreaFactory,
    CompetentAuthorityFactory,
    ListingFactory,
    PlatformFactory,
)

ADDRESS = {
    "thoroughfare": "Turfmarkt",
    "locatorDesignatorNumber": 147,
    "postCode": "2500EA",
    "postName": "Den Haag",
    "fullAddress": "Turfmarkt 147, 2500EA Den Haag",
}


def _listing(area_id: str, **overrides):
    base = {
        "areaId": area_id,
        "url": "http://example.com/x",
        "address": ADDRESS,
        "declaredAsShortTermRental": True,
    }
    base.update(overrides)
    return base


def _token(listing) -> str:
    return listing.created_at.isoformat()


@pytest.mark.database
class TestListingBulkServices:
    @pytest.fixture
    async def areas(self, async_session: AsyncSession) -> dict[str, str]:
        ca = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_id="ca-1"
        )
        ids = {}
        for regulation in ("listing", "activity", "all"):
            area = await AreaFactory.create_async(
                async_session,
                area_id=f"area-{regulation}",
                regulation=regulation,
                competent_authority_id=ca.id,
            )
            ids[regulation] = area.area_id
        return ids

    async def test_submit_covers_every_nok_branch(self, async_session, areas):
        response = await create_listings_bulk(
            async_session,
            [
                _listing(areas["all"], listingId="l-ok"),
                {"areaId": areas["all"]},
                _listing("missing-area"),
                _listing(areas["activity"]),
                _listing(areas["all"], listingId="dup"),
                _listing(areas["all"], listingId="dup"),
                _listing(areas["listing"], listingId=""),
            ],
            client_id="str-1",
            platform_name="STR 1",
        )
        assert (response.total_received, response.succeeded, response.failed) == (
            7,
            3,
            4,
        )
        types = [
            r.errors.detail[0].type if r.errors else None for r in response.results
        ]
        assert types == [
            None,
            "missing",
            "not_found_error",
            "regulation_error",
            "duplicate_error",
            None,
            None,
        ]
        assert response.results[3].errors is not None
        assert response.results[3].errors.detail[0].loc == ["areaId"]
        ok = response.results[0].listing
        assert ok is not None and ok.status == ListingStatus.pending
        assert ok.created_at.tzinfo is not None
        assert response.results[6].listing_id == ""  # echoed as supplied, id generated

    async def test_correction_only_while_pending(self, async_session, areas):
        first = await create_listings_bulk(
            async_session, [_listing(areas["all"], listingId="l-1")], "str-1", "STR 1"
        )
        listing = first.results[0].listing
        assert listing is not None
        corrected = await create_listings_bulk(
            async_session,
            [_listing(areas["all"], listingId="l-1", listingName="Corrected")],
            "str-1",
            "STR 1",
        )
        assert corrected.results[0].status == "OK"
        assert corrected.results[0].listing is not None
        assert corrected.results[0].listing.listing_name == "Corrected"
        current = await listing_service.get_listing_list(
            async_session, scope=ListingScope(platform_client_id="str-1")
        )
        assert [row.listing_name for row in current] == ["Corrected"]
        assert (
            await listing_service.count_current_listings(
                async_session, scope=ListingScope(platform_client_id="str-1")
            )
            == 1
        )

        screened = await screen_listings_bulk(
            async_session,
            [
                {
                    "platformId": listing.platform_id,
                    "listingId": "l-1",
                    "createdAt": _token(current[0]) + "Z",
                    "flags": ["UNK"],
                }
            ],
        )
        assert screened.results[0].status == "OK", screened.results[0]
        refused = await create_listings_bulk(
            async_session, [_listing(areas["all"], listingId="l-1")], "str-1", "STR 1"
        )
        assert refused.results[0].errors is not None
        detail = refused.results[0].errors.detail[0]
        assert (detail.type, detail.loc) == ("conflict_error", ["listingId"])
        assert "already screened (status 'flagged')" in detail.msg

    async def test_listing_id_of_another_platform_is_refused(
        self, async_session, areas
    ):
        """A listingId has one owner: another platform gets duplicate_error."""
        await create_listings_bulk(
            async_session, [_listing(areas["all"], listingId="l-own")], "str-1", "STR 1"
        )

        response = await create_listings_bulk(
            async_session,
            [_listing(areas["all"], listingId="l-own")],
            "str-2",
            "STR 2",
        )

        assert response.results[0].status == "NOK"
        assert response.results[0].errors is not None
        detail = response.results[0].errors.detail[0]
        assert (detail.type, detail.loc) == ("duplicate_error", ["listingId"])
        assert "another platform" in detail.msg
        current = await listing_service.get_listing_list(
            async_session, scope=ListingScope(platform_client_id="str-1")
        )
        assert [row.listing_id for row in current] == ["l-own"]

    async def test_listing_id_is_case_sensitive(self, async_session, areas):
        """`L-Case` and `l-case` are two listingIds, so two owners can each have one."""
        first = await create_listings_bulk(
            async_session,
            [_listing(areas["all"], listingId="L-Case")],
            "str-1",
            "STR 1",
        )
        second = await create_listings_bulk(
            async_session,
            [_listing(areas["all"], listingId="l-case")],
            "str-2",
            "STR 2",
        )

        assert [r.status for r in (*first.results, *second.results)] == ["OK", "OK"]
        assert [r.listing_id for r in (*first.results, *second.results)] == [
            "L-Case",
            "l-case",
        ]

    async def test_non_string_listing_id_is_nok_not_500(self, async_session, areas):
        """All three listing services echo a non-string listingId as null."""
        items = [{"listingId": 123}, {"listingId": ["x"]}, {"listingId": "bad/id"}]
        responses = [
            await create_listings_bulk(async_session, items, "str-1", "STR 1"),
            await screen_listings_bulk(async_session, items),
            await acknowledge_listings_bulk(async_session, items, "str-1"),
        ]
        for response in responses:
            assert response.failed == 3
            assert [r.listing_id for r in response.results] == [None, None, "bad/id"]

    async def test_resent_listing_without_id_is_a_retry(self, async_session, areas):
        """A generated listingId is deterministic: a resend returns the stored listing."""
        scope = ListingScope(platform_client_id="str-1")
        first = await create_listings_bulk(
            async_session, [_listing(areas["all"])], "str-1", "STR 1"
        )
        stored = first.results[0].listing
        assert stored is not None
        assert uuid.UUID(stored.listing_id).version == 8

        resent = await create_listings_bulk(
            async_session, [_listing(areas["all"])], "str-1", "STR 1"
        )
        assert resent.results[0].listing is not None
        assert resent.results[0].listing.listing_id == stored.listing_id
        assert (
            await listing_service.count_current_listings(async_session, scope=scope)
            == 1
        )

        # Also once screened: OK with the stored (flagged) version, no conflict_error
        current = await listing_service.get_listing_list(async_session, scope=scope)
        await screen_listings_bulk(
            async_session,
            [
                {
                    "platformId": stored.platform_id,
                    "listingId": stored.listing_id,
                    "createdAt": _token(current[0]) + "Z",
                    "flags": ["UNK"],
                }
            ],
        )
        screened = await create_listings_bulk(
            async_session, [_listing(areas["all"])], "str-1", "STR 1"
        )
        assert screened.results[0].status == "OK", screened.results[0]
        assert screened.results[0].listing is not None
        assert screened.results[0].listing.status == ListingStatus.flagged

    async def test_identical_listing_with_its_id_is_a_resend(
        self, async_session, areas
    ):
        """Same listingId and content: the stored listing, also once screened."""
        scope = ListingScope(platform_client_id="str-1")
        first = await create_listings_bulk(
            async_session, [_listing(areas["all"], listingId="l-r")], "str-1", "STR 1"
        )
        stored = first.results[0].listing
        assert stored is not None
        resent = await create_listings_bulk(
            async_session, [_listing(areas["all"], listingId="l-r")], "str-1", "STR 1"
        )
        again = resent.results[0].listing
        assert again is not None
        assert again.created_at.replace(tzinfo=None) == stored.created_at.replace(
            tzinfo=None
        )

        current = await listing_service.get_listing_list(async_session, scope=scope)
        await screen_listings_bulk(
            async_session,
            [
                {
                    "platformId": stored.platform_id,
                    "listingId": "l-r",
                    "createdAt": _token(current[0]) + "Z",
                    "flags": [],
                }
            ],
        )
        screened = await create_listings_bulk(
            async_session, [_listing(areas["all"], listingId="l-r")], "str-1", "STR 1"
        )
        assert screened.results[0].status == "OK", screened.results[0]
        assert screened.results[0].listing is not None
        assert screened.results[0].listing.status == ListingStatus.clear

        # Changed content of a screened listing is still refused
        changed = await create_listings_bulk(
            async_session,
            [_listing(areas["all"], listingId="l-r", listingName="Changed")],
            "str-1",
            "STR 1",
        )
        assert changed.results[0].errors is not None
        assert changed.results[0].errors.detail[0].type == "conflict_error"

    @pytest.mark.parametrize(
        "empty", [None, "", "    "], ids=["null", "empty", "spaces"]
    )
    @pytest.mark.parametrize("listing_id", [None, "l-null"], ids=["generated", "own"])
    async def test_null_or_empty_equals_an_omitted_field(
        self, async_session, areas, listing_id, empty
    ):
        """An optional field sent as null, "" or spaces is the same content as omitted."""
        first = _listing(areas["all"])
        resent = _listing(
            areas["all"],
            listingName=empty,
            registrationNumber=empty,
            address=ADDRESS
            | {"locatorDesignatorLetter": empty, "locatorDesignatorAddition": empty},
        )
        if listing_id is not None:
            first["listingId"] = resent["listingId"] = listing_id
        stored = (
            (await create_listings_bulk(async_session, [first], "str-1", "STR 1"))
            .results[0]
            .listing
        )
        again = (
            (await create_listings_bulk(async_session, [resent], "str-1", "STR 1"))
            .results[0]
            .listing
        )
        assert stored is not None and again is not None
        assert again.listing_id == stored.listing_id
        assert again.created_at.replace(tzinfo=None) == stored.created_at.replace(
            tzinfo=None
        )

    @pytest.mark.parametrize("listing_id", [None, "l-trim"], ids=["generated", "own"])
    async def test_surrounding_spaces_are_trimmed(
        self, async_session, areas, listing_id
    ):
        """ " Name " is the same content as "Name", and is stored as "Name"."""
        first = _listing(areas["all"], listingName="Name", registrationNumber="REG1")
        resent = _listing(
            areas["all"], listingName=" Name ", registrationNumber="  REG1 "
        )
        if listing_id is not None:
            first["listingId"] = resent["listingId"] = listing_id
        stored = (
            (await create_listings_bulk(async_session, [first], "str-1", "STR 1"))
            .results[0]
            .listing
        )
        again = (
            (await create_listings_bulk(async_session, [resent], "str-1", "STR 1"))
            .results[0]
            .listing
        )
        assert stored is not None and again is not None
        assert again.listing_id == stored.listing_id
        assert again.created_at.replace(tzinfo=None) == stored.created_at.replace(
            tzinfo=None
        )
        assert (again.listing_name, again.registration_number) == ("Name", "REG1")

    async def test_other_content_or_platform_gives_another_listing(
        self, async_session, areas
    ):
        """Other content or another platform: another generated listingId."""
        posts = [
            (_listing(areas["all"]), "str-1"),
            (_listing(areas["all"], url="http://example.com/y"), "str-1"),
            (_listing(areas["all"]), "str-2"),
        ]
        ids = set()
        for item, client in posts:
            response = await create_listings_bulk(
                async_session, [item], client, client.upper()
            )
            assert response.results[0].listing is not None
            ids.add(response.results[0].listing.listing_id)
        assert len(ids) == 3

    async def test_platform_rename_keeps_listing_findable(self, async_session, areas):
        """A client_name change versions the platform; its listings stay one current row."""
        # Backdated, so the rename's new platform version gets another created_at
        await PlatformFactory.create_async(
            async_session,
            client_id="str-1",
            platform_name="STR 1",
            created_at=datetime(2026, 1, 1),
        )
        scope = ListingScope(platform_client_id="str-1")
        await create_listings_bulk(
            async_session,
            [_listing(areas["all"], listingId=i) for i in ("l-1", "l-2")],
            "str-1",
            "STR 1",
        )

        # Resubmitting l-2 under the new name versions it, no second current row
        resubmitted = await create_listings_bulk(
            async_session,
            [_listing(areas["all"], listingId="l-2", listingName="After rename")],
            "str-1",
            "STR 1 renamed",
        )
        assert resubmitted.results[0].status == "OK", resubmitted.results[0]
        assert (
            await listing_service.count_current_listings(async_session, scope=scope)
            == 2
        )

        # l-1 still points at the previous platform version: screen and acknowledge it
        [current] = [
            row
            for row in await listing_service.get_listing_list(
                async_session, scope=scope
            )
            if row.listing_id == "l-1"
        ]
        screened = await screen_listings_bulk(
            async_session,
            [
                {
                    "platformId": current.platform.platform_id,
                    "listingId": "l-1",
                    "createdAt": _token(current) + "Z",
                    "flags": ["UNK"],
                }
            ],
        )
        assert screened.results[0].status == "OK", screened.results[0]
        flagged = screened.results[0].listing
        assert flagged is not None
        acknowledged = await acknowledge_listings_bulk(
            async_session,
            [{"listingId": "l-1", "createdAt": flagged.created_at.isoformat()}],
            "str-1",
        )
        assert acknowledged.results[0].status == "OK", acknowledged.results[0]
        assert (
            await listing_service.count_current_listings(async_session, scope=scope)
            == 2
        )

    async def test_screening_covers_every_nok_branch(self, async_session, areas):
        platform = await PlatformFactory.create_async(
            async_session, platform_id="p-1", client_id="str-1"
        )
        pending = await ListingFactory.create_async(
            async_session,
            listing_id="l-pending",
            platform_id=platform.id,
            area_id=areas["all"],
        )
        acknowledged = await ListingFactory.create_async(
            async_session,
            listing_id="l-ack",
            platform_id=platform.id,
            area_id=areas["all"],
            status=ListingStatus.acknowledged,
            flags=["UNK"],
        )
        stale_listing = await ListingFactory.create_async(
            async_session,
            listing_id="l-stale",
            platform_id=platform.id,
            area_id=areas["all"],
        )
        stale = (stale_listing.created_at - timedelta(minutes=1)).isoformat() + "Z"
        base = {"platformId": "p-1", "createdAt": _token(pending) + "Z"}
        response = await screen_listings_bulk(
            async_session,
            [
                {**base, "listingId": "l-pending", "flags": ["UNK", "UNK"]},
                {**base, "listingId": "l-pending", "flags": ["NOPE"]},
                {
                    **base,
                    "platformId": "p-missing",
                    "listingId": "l-pending",
                    "flags": [],
                },
                {**base, "listingId": "l-missing", "flags": []},
                {**base, "listingId": "l-stale", "createdAt": stale, "flags": []},
                {
                    **base,
                    "listingId": "l-ack",
                    "createdAt": _token(acknowledged) + "Z",
                    "flags": ["UNK"],
                },
                {**base, "listingId": "l-pending", "flags": ["UDS"]},
                {**base, "listingId": "l-pending", "flags": ["EXP"]},
            ],
        )
        assert (response.total_received, response.succeeded, response.failed) == (
            8,
            1,
            7,
        )
        detail = [r.errors.detail[0] if r.errors else None for r in response.results]
        assert [d.type if d else None for d in detail] == [
            "value_error",
            "enum",
            "not_found_error",
            "not_found_error",
            "conflict_error",
            "conflict_error",
            "duplicate_error",
            None,
        ]
        assert detail[2] is not None and detail[2].loc == ["platformId"]
        assert detail[3] is not None and detail[3].loc == ["listingId"]
        assert detail[4] is not None and detail[4].loc == ["createdAt"]
        assert detail[4].msg.endswith("is no longer current")
        assert detail[5] is not None and "already acknowledged" in detail[5].msg
        flagged = response.results[7].listing
        assert flagged is not None
        assert flagged.status == ListingStatus.flagged
        assert [f.value for f in flagged.flags] == ["EXP"]
        assert flagged.screened_at is not None
        assert flagged.submitted_at == pending.submitted_at.replace(tzinfo=UTC)

        clear = await screen_listings_bulk(
            async_session,
            [
                {
                    "platformId": "p-1",
                    "listingId": "l-pending",
                    "createdAt": flagged.created_at.isoformat(),
                    "flags": [],
                }
            ],
        )
        assert clear.results[0].listing is not None
        assert clear.results[0].listing.status == ListingStatus.clear

    async def test_acknowledgement_covers_every_branch(self, async_session, areas):
        no_platform = await acknowledge_listings_bulk(
            async_session,
            [{"listingId": "l-1", "createdAt": "2026-09-07T08:00:00Z"}],
            "unknown",
        )
        assert no_platform.failed == 1
        assert no_platform.results[0].errors is not None
        assert no_platform.results[0].errors.detail[0].type == "not_found_error"

        platform = await PlatformFactory.create_async(
            async_session, platform_id="p-1", client_id="str-1"
        )
        flagged = await ListingFactory.create_async(
            async_session,
            listing_id="l-flagged",
            platform_id=platform.id,
            area_id=areas["all"],
            status=ListingStatus.flagged,
            flags=["UNK"],
            screened_at=datetime(2026, 9, 8, 6, 0),
        )
        pending = await ListingFactory.create_async(
            async_session,
            listing_id="l-pending",
            platform_id=platform.id,
            area_id=areas["all"],
        )
        await ListingFactory.create_async(
            async_session,
            listing_id="l-stale",
            platform_id=platform.id,
            area_id=areas["all"],
            status=ListingStatus.flagged,
            flags=["UNK"],
        )
        token = _token(flagged) + "Z"
        response = await acknowledge_listings_bulk(
            async_session,
            [
                {"listingId": "l-missing", "createdAt": token},
                {"listingId": "l-stale", "createdAt": "2020-01-01T00:00:00Z"},
                {"listingId": "l-pending", "createdAt": _token(pending) + "Z"},
                {"listingId": "l-flagged", "createdAt": token},
                {"listingId": "l-flagged", "createdAt": token},
            ],
            "str-1",
        )
        assert (response.succeeded, response.failed) == (1, 4)
        detail = [r.errors.detail[0] if r.errors else None for r in response.results]
        assert [d.type if d else None for d in detail] == [
            "not_found_error",
            "conflict_error",
            "conflict_error",
            "duplicate_error",
            None,
        ]
        assert (
            detail[2] is not None
            and "is not flagged (status 'pending')" in detail[2].msg
        )
        acknowledged = response.results[4].listing
        assert acknowledged is not None
        assert acknowledged.status == ListingStatus.acknowledged
        assert [f.value for f in acknowledged.flags] == ["UNK"]
        assert acknowledged.acknowledged_at is not None
        assert acknowledged.screened_at == datetime(2026, 9, 8, 6, 0, tzinfo=UTC)

        retried = await acknowledge_listings_bulk(
            async_session, [{"listingId": "l-flagged", "createdAt": token}], "str-1"
        )
        assert retried.results[0].errors is not None
        assert retried.results[0].errors.detail[0].loc == ["createdAt"]
