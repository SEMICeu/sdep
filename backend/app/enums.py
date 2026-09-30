"""Shared enumerations."""

from __future__ import annotations

from enum import StrEnum


class Regulation(StrEnum):
    """Regulation type for an area: 'listing', 'activity', or 'all' (covers both)."""

    listing = "listing"
    activity = "activity"
    all = "all"

    def covers(self, required: Regulation) -> bool:
        """True when this regulation asks for `required` data; `all` covers both."""
        return self in (required, Regulation.all)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema["title"] = "Common.Regulation"
        return json_schema


class ActivityStatus(StrEnum):
    """Lifecycle status for an activity record."""

    finished = "finished"
    cancelled = "cancelled"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema["title"] = "Activity.Status"
        return json_schema


class ListingStatus(StrEnum):
    """Lifecycle status for a listing (random check) record."""

    pending = "pending"
    clear = "clear"
    flagged = "flagged"
    acknowledged = "acknowledged"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema["title"] = "Listing.Status"
        return json_schema


class ListingFlag(StrEnum):
    """Flag code raised by listing screening, see docs/LISTING_FUNC.md."""

    ABS = "ABS"  # Absent registration number
    UNK = "UNK"  # Unknown registration number
    EXP = "EXP"  # Expired registration number
    MIS = "MIS"  # Mismatched address
    NPR = "NPR"  # Not a private residence
    UNX = "UNX"  # Unexpected registration number
    UDS = "UDS"  # Undeclared short-term rental

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema["title"] = "Listing.Flag"
        return json_schema
