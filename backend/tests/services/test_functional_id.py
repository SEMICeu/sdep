"""Tests for the generated functional IDs and their secret (services/functional_id.py)."""

import uuid
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.config import FUNCTIONAL_ID_SECRET_DEV, Settings
from app.schemas.common import UtcDateTime
from app.services import functional_id
from app.services.functional_id import (
    content,
    generate_id,
    resolve_ids,
    stored_content,
)
from pydantic import BaseModel, SecretStr, ValidationError

FIELDS = {"areaId": "a-1", "numberOfGuests": 2}


class TestGenerateId:
    def test_same_input_same_uuidv8(self):
        first = generate_id("activity", "p-1", FIELDS)
        assert first == generate_id("activity", "p-1", dict(reversed(FIELDS.items())))
        assert uuid.UUID(first).version == 8
        assert first == first.lower()

    @pytest.mark.parametrize(
        "other",
        [
            ("listing", "p-1", FIELDS, 0),
            ("activity", "p-2", FIELDS, 0),
            ("activity", "p-1", {**FIELDS, "numberOfGuests": 3}, 0),
            ("activity", "p-1", FIELDS, 1),
        ],
        ids=["kind", "owner", "field", "generation"],
    )
    def test_any_input_change_gives_another_id(self, other):
        assert generate_id(*other) != generate_id("activity", "p-1", FIELDS)

    def test_another_secret_gives_another_id(self, monkeypatch):
        before = generate_id("activity", "p-1", FIELDS)
        settings = SimpleNamespace(FUNCTIONAL_ID_SECRET=SecretStr("o" * 32))
        monkeypatch.setattr(functional_id, "get_settings", lambda: settings)
        assert generate_id("activity", "p-1", FIELDS) != before


class _Request(BaseModel):
    item_id: str | None = None
    at: list[UtcDateTime]
    status: str = "finished"


class _Response(BaseModel):
    item_id: str
    at: list[datetime]
    status: str
    created_at: datetime


class TestStoredContent:
    def test_stored_version_compares_like_the_request(self):
        """Naive (SQLite) and other offsets are the same instant; extra fields drop."""
        instant = datetime(2025, 6, 1, 14, tzinfo=UTC)
        stored = _Response(
            item_id="x",
            at=[
                instant.replace(tzinfo=None),
                instant.astimezone(timezone(timedelta(hours=2))),
            ],
            status="finished",
            created_at=instant,
        )
        request = _Request.model_validate({"at": ["2025-06-01T14:00:00Z"] * 2})
        assert stored_content(_Request, stored, "item_id") == content(
            request, "item_id"
        )


@pytest.mark.asyncio
class TestResolveIds:
    async def test_deleted_ids_move_to_the_next_generation(self):
        gen = [generate_id("area", "ca-1", FIELDS, n) for n in range(3)]
        other = generate_id("area", "ca-1", {"x": 1})
        # Round 1: generation 0 is deleted, round 2: generation 1 as well
        deleted = AsyncMock(side_effect=[{gen[0]}, {gen[1]}, set()])

        ids = await resolve_ids("area", "ca-1", {"k": FIELDS, "o": {"x": 1}}, deleted)

        assert ids == {"k": gen[2], "o": other}
        assert [c.args[0] for c in deleted.await_args_list] == [
            [gen[0], other],
            [gen[1]],
            [gen[2]],
        ]

    async def test_empty_batch_queries_nothing(self):
        deleted = AsyncMock()
        assert await resolve_ids("listing", "p-1", {}, deleted) == {}
        deleted.assert_not_awaited()


class TestSecretGuard:
    @pytest.mark.parametrize(
        "secret", [FUNCTIONAL_ID_SECRET_DEV, "s" * 31], ids=["default", "short"]
    )
    def test_outside_dev_needs_its_own_secret(self, secret):
        with pytest.raises(ValidationError, match="FUNCTIONAL_ID_SECRET"):
            Settings(DTAP="TST", FUNCTIONAL_ID_SECRET=SecretStr(secret))

    def test_outside_dev_starts_with_a_secret(self):
        secret = SecretStr("s" * 32)
        assert Settings(DTAP="PRE", FUNCTIONAL_ID_SECRET=secret).DTAP == "PRE"

    def test_dev_starts_with_the_default(self):
        dev_default = SecretStr(FUNCTIONAL_ID_SECRET_DEV)
        assert Settings(DTAP="DEV", FUNCTIONAL_ID_SECRET=dev_default).DTAP == "DEV"
        default = Settings.model_fields["FUNCTIONAL_ID_SECRET"].default
        assert default.get_secret_value() == FUNCTIONAL_ID_SECRET_DEV
