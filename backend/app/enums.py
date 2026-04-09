"""Shared enumerations."""

from enum import Enum


class Regulation(str, Enum):
    """Regulation type for an area: 'listing', 'activity', or 'all' (covers both)."""

    listing = "listing"
    activity = "activity"
    all = "all"
