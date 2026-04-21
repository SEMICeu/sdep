"""Shared enumerations."""

from enum import Enum


class Regulation(str, Enum):
    """Regulation type for an area: 'listing', 'activity', or 'all' (covers both)."""

    listing = "listing"
    activity = "activity"
    all = "all"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema["title"] = "Common.Regulation"
        return json_schema


class ActivityStatus(str, Enum):
    """Lifecycle status for an activity record."""

    finished = "finished"
    cancelled = "cancelled"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema["title"] = "Activity.Status"
        return json_schema
