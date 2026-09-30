"""Tests for Listing CRUD operations."""

from datetime import UTC, datetime

import pytest
from app.crud import listing as listing_crud
from app.crud.listing import _flags_overlap
from app.enums import ListingFlag, ListingStatus
from app.schemas.listing import ListingBulkCreate, ListingFilters, ListingScope
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import (
    AreaFactory,
    CompetentAuthorityFactory,
    ListingFactory,
    PlatformFactory,
)


@pytest.mark.database
class TestListingCRUD:
    async def test_empty_inputs_short_circuit(self, async_session: AsyncSession):
        assert await listing_crud.get_current_by_listing_ids(async_session, [], 1) == {}
        assert await listing_crud.bulk_mark_as_ended(async_session, [], 1) is None
        assert await listing_crud.bulk_create(async_session, []) == []

    async def test_scope_and_filters(self, async_session: AsyncSession):
        ca_a = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_id="ca-a"
        )
        ca_b = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_id="ca-b"
        )
        area_a = await AreaFactory.create_async(
            async_session, area_id="area-a", competent_authority_id=ca_a.id
        )
        area_b = await AreaFactory.create_async(
            async_session, area_id="area-b", competent_authority_id=ca_b.id
        )
        platform_1 = await PlatformFactory.create_async(
            async_session, platform_id="p1", client_id="client-1"
        )
        platform_2 = await PlatformFactory.create_async(
            async_session, platform_id="p2", client_id="client-2"
        )
        flagged = await ListingFactory.create_async(
            async_session,
            listing_id="l-flagged",
            area_id=area_a.id,
            platform_id=platform_1.id,
            status=ListingStatus.flagged,
            flags=["UNK", "MIS"],
            created_at=datetime(2026, 9, 10, tzinfo=UTC),
        )
        await ListingFactory.create_async(
            async_session,
            listing_id="l-pending",
            area_id=area_b.id,
            platform_id=platform_2.id,
            created_at=datetime(2026, 9, 12, tzinfo=UTC),
        )
        await ListingFactory.create_async(
            async_session,
            listing_id="l-ended",
            area_id=area_a.id,
            platform_id=platform_1.id,
            ended_at=datetime(2026, 9, 13, tzinfo=UTC),
        )

        unscoped = ListingScope()
        rows = await listing_crud.get_current_listings(async_session, scope=unscoped)
        assert [r.listing_id for r in rows] == ["l-pending", "l-flagged"]
        assert (
            await listing_crud.count_current_listings(async_session, scope=unscoped)
            == 2
        )

        by_platform = ListingScope(
            platform_client_id="client-1", status=ListingStatus.flagged
        )
        rows = await listing_crud.get_current_listings(async_session, scope=by_platform)
        assert [r.listing_id for r in rows] == ["l-flagged"]

        by_ca = ListingScope(competent_authority_client_id="ca-b")
        assert (
            await listing_crud.count_current_listings(async_session, scope=by_ca) == 1
        )

        cases = [
            (
                ListingFilters(created_at_from=datetime(2026, 9, 11, tzinfo=UTC)),
                ["l-pending"],
            ),
            (
                ListingFilters(created_at_to=datetime(2026, 9, 11, tzinfo=UTC)),
                ["l-flagged"],
            ),
            (ListingFilters(platform_id="p2"), ["l-pending"]),
            (ListingFilters(area_id="area-a"), ["l-flagged"]),
            (ListingFilters(flags=(ListingFlag.MIS, ListingFlag.UDS)), ["l-flagged"]),
            (ListingFilters(flags=(ListingFlag.UDS,)), []),
            (ListingFilters(status=ListingStatus.pending), ["l-pending"]),
        ]
        for filters, expected in cases:
            rows = await listing_crud.get_current_listings(
                async_session, scope=unscoped, filters=filters
            )
            assert [r.listing_id for r in rows] == expected, filters
            assert await listing_crud.count_current_listings(
                async_session, scope=unscoped, filters=filters
            ) == len(expected)

        limited = await listing_crud.get_current_listings(
            async_session, scope=unscoped, offset=1, limit=1
        )
        assert [r.listing_id for r in limited] == ["l-flagged"]

        current = await listing_crud.get_current_by_listing_ids(
            async_session,
            ["l-flagged", "l-ended", "missing"],
            platform_1.id,
            for_update=True,
        )
        assert set(current) == {"l-flagged"}
        assert current["l-flagged"].id == flagged.id

    def test_flags_overlap_uses_array_overlap_on_postgresql(self):
        clause = _flags_overlap("postgresql", (ListingFlag.UDS, ListingFlag.EXP))
        assert "&&" in str(clause.compile(dialect=postgresql.dialect()))
        clause = _flags_overlap("sqlite", (ListingFlag.UDS,))
        assert "LIKE" in str(clause.compile(dialect=sqlite.dialect()))

    async def test_version_builders_and_bulk_create(self, async_session: AsyncSession):
        platform = await PlatformFactory.create_async(async_session)
        area = await AreaFactory.create_async(async_session)
        now = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)
        row = ListingBulkCreate.model_validate(
            {
                "listingId": "l-1",
                "areaId": area.area_id,
                "url": "http://example.com/l-1",
                "address": {
                    "thoroughfare": "Turfmarkt",
                    "locatorDesignatorNumber": 147,
                    "postCode": "2500EA",
                    "postName": "Den Haag",
                    "fullAddress": "Turfmarkt 147, 2500EA Den Haag",
                },
                "declaredAsShortTermRental": True,
                "platform_technical_id": platform.id,
                "area_technical_id": area.id,
                "created_at": now,
                "submitted_at": now,
            }
        )
        pending = listing_crud.build_from_request(row, platform, area)
        [created] = await listing_crud.bulk_create(async_session, [pending])
        assert created.id is not None
        assert created.status == ListingStatus.pending
        assert created.flags == []
        assert created.registration_number is None
        assert created.platform_id_functional == platform.platform_id
        assert created.area_id_functional == area.area_id
        assert "l-1" in repr(created)

        later = datetime(2026, 9, 8, 6, 0, tzinfo=UTC)
        await listing_crud.bulk_mark_as_ended(async_session, ["l-1"], platform.id)
        flagged = listing_crud.build_next_version(
            created,
            created_at=later,
            status=ListingStatus.flagged,
            flags=["UNK"],
            screened_at=later,
            acknowledged_at=None,
        )
        [flagged] = await listing_crud.bulk_create(async_session, [flagged])
        assert flagged.listing_id == "l-1"
        assert flagged.submitted_at.replace(tzinfo=UTC) == now
        assert flagged.address_thoroughfare == "Turfmarkt"
        current = await listing_crud.get_current_by_listing_ids(
            async_session, ["l-1"], platform.id
        )
        assert current["l-1"].id == flagged.id
