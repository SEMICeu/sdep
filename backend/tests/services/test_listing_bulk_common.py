"""Tests for the shared listing bulk helpers."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

from app.schemas.listing_bulk import ListingBulkResultItem
from app.services import listing_bulk_common as common


class _FakeValidationError(Exception):
    def errors(self):
        return []


class _FakeAdapter:
    def validate_python(self, raw: Any):
        raise _FakeValidationError("broken")


def test_validate_items_marks_non_dicts_and_empty_error_lists(monkeypatch):
    monkeypatch.setattr(common, "ValidationError", _FakeValidationError)
    results, valid, validated, ids = common.validate_items(
        cast("list[dict[str, Any]]", ["not-a-dict", {"listingId": "l-1"}]),
        _FakeAdapter(),  # type: ignore[arg-type]
        ListingBulkResultItem,
    )
    assert valid == [] and validated == {}
    assert ids == {0: None, 1: "l-1"}
    assert results[0] is not None and results[0].status == "NOK"
    assert results[1] is not None and results[1].errors is not None
    assert results[1].errors.detail[0].type == "validation_error"
    assert results[1].errors.detail[0].msg == "broken"


def test_last_wins_marks_earlier_duplicates():
    results: list[ListingBulkResultItem | None] = [None, None, None]
    keys = ["a", "b", "a"]
    valid = common.last_wins(
        [0, 1, 2],
        lambda i: keys[i],
        results,
        {0: "a", 1: "b", 2: "a"},
        ListingBulkResultItem,
    )
    assert valid == [1, 2]
    assert results[0] is not None
    assert results[0].errors is not None
    assert results[0].errors.detail[0].type == "duplicate_error"
    assert "index 2" in results[0].errors.detail[0].msg


def test_same_instant_normalizes_naive_and_offsets():
    aware = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)
    assert common.same_instant(datetime(2026, 9, 7, 8, 0), aware)
    assert common.same_instant(
        aware, datetime(2026, 9, 7, 10, 0, tzinfo=timezone(timedelta(hours=2)))
    )
    assert not common.same_instant(aware, aware + timedelta(microseconds=1))


def test_not_current_message_renders_utc_token():
    msg = common.not_current_message("abc-123", datetime(2026, 9, 7, 8, 0, tzinfo=UTC))
    assert (
        msg == "Listing 'abc-123' version '2026-09-07T08:00:00Z' is no longer current"
    )
