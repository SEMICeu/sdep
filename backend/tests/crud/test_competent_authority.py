"""Tests for CompetentAuthority CRUD operations."""

from datetime import datetime

import pytest
from app.crud import competent_authority
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.factories import CompetentAuthorityFactory


@pytest.mark.database
class TestCompetentAuthorityCRUD:
    """Test suite for CompetentAuthority CRUD operations."""

    async def test_create_competent_authority(self, async_session: AsyncSession):
        """Test creating a new competent authority."""
        # Arrange
        competent_authority_id = "0363"
        competent_authority_name = "Gemeente Amsterdam"

        # Act
        result = await competent_authority.create(
            session=async_session,
            competent_authority_id=competent_authority_id,
            competent_authority_name=competent_authority_name,
        )

        # Assert
        assert result.id is not None
        assert result.competent_authority_id == competent_authority_id
        assert result.competent_authority_name == competent_authority_name
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    async def test_delete_competent_authority(self, async_session: AsyncSession):
        """Test deleting an existing competent authority."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(async_session)

        # Act
        result = await competent_authority.delete(async_session, ca.id)

        # Assert
        assert result is True
        retrieved = await competent_authority.get_by_id(async_session, ca.id)
        assert retrieved is None

    async def test_delete_competent_authority_not_found(
        self, async_session: AsyncSession
    ):
        """Test deleting a non-existent competent authority."""
        # Act
        result = await competent_authority.delete(async_session, 99999)

        # Assert
        assert result is False

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

    async def test_get_by_competent_authority_id(self, async_session: AsyncSession):
        """Test getting competent authority by competent_authority_id."""
        # Arrange
        ca = await CompetentAuthorityFactory.create_async(
            async_session, competent_authority_id="0363"
        )

        # Act
        result = await competent_authority.get_by_competent_authority_id(
            async_session, "0363"
        )

        # Assert
        assert result is not None
        assert result.id == ca.id

    async def test_get_by_competent_authority_id_not_found(
        self, async_session: AsyncSession
    ):
        """Test getting competent authority by non-existent competent_authority_id."""
        # Act
        result = await competent_authority.get_by_competent_authority_id(
            async_session, "9999"
        )

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
