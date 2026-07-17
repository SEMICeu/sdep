"""Tests for CompetentAuthority CRUD operations."""

from datetime import datetime

import pytest
from app.crud import competent_authority
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import CompetentAuthorityFactory


@pytest.mark.database
class TestCompetentAuthorityCRUD:
    """Test suite for CompetentAuthority CRUD operations."""

    async def test_create_competent_authority(self, async_session: AsyncSession):
        """Test creating a new competent authority."""
        # Arrange
        client_id = "sdep-ca.0363"
        competent_authority_name = "Gemeente Amsterdam"

        # Act
        result = await competent_authority.create(
            session=async_session,
            client_id=client_id,
            competent_authority_name=competent_authority_name,
        )

        # Assert
        assert result.id is not None
        assert result.client_id == client_id
        assert result.competent_authority_id != client_id
        assert result.competent_authority_name == competent_authority_name
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_create_competent_authority_allows_duplicate_competent_authority_id(
        self, async_session: AsyncSession
    ):
        """Test that duplicate public competent_authority_id values are allowed."""
        # Arrange
        duplicate_competent_authority_id = "duplicate-ca"

        await competent_authority.create(
            session=async_session,
            client_id="duplicate-ca-client-1",
            competent_authority_id=duplicate_competent_authority_id,
            competent_authority_name="First CA",
        )
        await async_session.flush()

        # Act
        second = await competent_authority.create(
            session=async_session,
            client_id="duplicate-ca-client-2",
            competent_authority_id=duplicate_competent_authority_id,
            competent_authority_name="Second CA",
        )
        await async_session.flush()

        # Assert
        assert second.competent_authority_id == duplicate_competent_authority_id

    async def test_create_competent_authority_with_duplicate_client_id_created_at(
        self, async_session: AsyncSession
    ):
        """Same client can hold versions with different public IDs at one created_at.

        The composite UNIQUE constraint permits this as long as only one row is
        current; the first version must be ended first so the partial unique
        index on the current row is not violated.
        """
        # Arrange
        created_at = datetime(2026, 1, 1)

        first = await competent_authority.create(
            session=async_session,
            client_id="duplicate-ca-client",
            competent_authority_id="duplicate-ca-1",
            competent_authority_name="First CA",
        )
        first.created_at = created_at
        await async_session.flush()

        # End the first version so a new current version can be created.
        await competent_authority.mark_as_ended_by_client_id(
            async_session, "duplicate-ca-client"
        )

        # Act
        second = await competent_authority.create(
            session=async_session,
            client_id="duplicate-ca-client",
            competent_authority_id="duplicate-ca-2",
            competent_authority_name="Second CA",
        )
        second.created_at = created_at
        await async_session.flush()

        # Assert
        assert second.client_id == first.client_id
        assert second.competent_authority_id != first.competent_authority_id

    async def test_create_competent_authority_with_duplicate_client_public_id_created_at(
        self, async_session: AsyncSession
    ):
        """Test duplicate public IDs within the same client/version raise IntegrityError."""
        # Arrange
        created_at = datetime(2026, 1, 1)

        first = await competent_authority.create(
            session=async_session,
            client_id="duplicate-ca-client",
            competent_authority_id="duplicate-ca",
            competent_authority_name="First CA",
        )
        first.created_at = created_at
        await async_session.flush()

        # Act & Assert
        with pytest.raises(IntegrityError):
            second = await competent_authority.create(
                session=async_session,
                client_id="duplicate-ca-client",
                competent_authority_id="duplicate-ca",
                competent_authority_name="Second CA",
            )
            second.created_at = created_at
            await async_session.flush()

    async def test_exists_competent_authority(self, async_session: AsyncSession):
        """Test checking if a competent authority exists."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)

        # Act
        exists = await competent_authority.exists(async_session, ca.id)
        not_exists = await competent_authority.exists(async_session, 99999)

        # Assert
        assert exists is True
        assert not_exists is False

    async def test_count_competent_authorities(self, async_session: AsyncSession):
        """Test counting competent authorities."""
        # Arrange
        initial_count = await competent_authority.count(async_session)
        await CompetentAuthorityFactory.create_async(async_session)
        await CompetentAuthorityFactory.create_async(async_session)

        # Act
        final_count = await competent_authority.count(async_session)

        # Assert
        assert final_count == initial_count + 2

    async def test_get_all_competent_authorities(self, async_session: AsyncSession):
        """Test getting all competent authorities."""
        # Arrange
        initial_count = await competent_authority.count(async_session)
        await CompetentAuthorityFactory.create_async(async_session)
        await CompetentAuthorityFactory.create_async(async_session)
        await CompetentAuthorityFactory.create_async(async_session)

        # Act
        results = await competent_authority.get_all(async_session)

        # Assert
        assert len(results) == initial_count + 3

    async def test_get_all_competent_authorities_with_pagination(
        self, async_session: AsyncSession
    ):
        """Test getting competent authorities with pagination."""
        # Arrange
        for _ in range(5):
            await CompetentAuthorityFactory.create_async(async_session)

        # Act
        page1 = await competent_authority.get_all(async_session, offset=0, limit=2)
        page2 = await competent_authority.get_all(async_session, offset=2, limit=2)

        # Assert
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    async def test_get_by_id(self, async_session: AsyncSession):
        """Test getting a competent authority by id."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)

        # Act
        result = await competent_authority.get_by_id(async_session, ca.id)

        # Assert
        assert result is not None
        assert result.id == ca.id
        assert result.competent_authority_id == ca.competent_authority_id

    async def test_get_by_id_not_found(self, async_session: AsyncSession):
        """Test getting a non-existent competent authority by id."""
        # Act
        result = await competent_authority.get_by_id(async_session, 99999)

        # Assert
        assert result is None

    async def test_get_by_competent_authority_name(self, async_session: AsyncSession):
        """Test getting competent authorities by name."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_name="Gemeente Amsterdam"
        )

        # Act
        results = await competent_authority.get_by_competent_authority_name(
            async_session, "Gemeente Amsterdam"
        )

        # Assert
        assert len(results) == 1
        assert results[0].id == ca.id

    async def test_get_by_competent_authority_name_not_found(
        self, async_session: AsyncSession
    ):
        """Test getting competent authorities by non-existent name."""
        # Act
        results = await competent_authority.get_by_competent_authority_name(
            async_session, "Non-existent Municipality"
        )

        # Assert
        assert len(results) == 0

    async def test_get_by_competent_authority_name_with_limit(
        self, async_session: AsyncSession
    ):
        for _ in range(3):
            await CompetentAuthorityFactory.create_async(
                async_session, competent_authority_name="Shared Name"
            )

        results = await competent_authority.get_by_competent_authority_name(
            async_session, "Shared Name", limit=2
        )

        assert len(results) == 2
