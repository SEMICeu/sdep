"""Temporal composite class."""

from datetime import datetime

# Minimum year constraint for start_date_time
MIN_START_YEAR = 2025


class Temporal:
    """Temporal composite representing a time period.

    This is a composite type (not a standalone entity) used inline in Activity.
    Represents a duration with start and end datetimes.
    Constraints:
    - start_date_time < end_date_time
    - start_date_time year must be >= 2025
    """

    def __init__(
        self,
        start_date_time: datetime,
        end_date_time: datetime,
    ):
        """Initialize Temporal composite.

        Args:
            start_date_time: Start datetime of the period (mandatory, year >= 2025)
            end_date_time: End datetime of the period (mandatory)

        Raises:
            ValueError: If start_date_time year is less than 2025
            ValueError: If start_date_time is not less than end_date_time
        """
        if start_date_time.year < MIN_START_YEAR:
            raise ValueError(f"start_date_time year must be >= {MIN_START_YEAR}")
        if start_date_time >= end_date_time:
            raise ValueError("start_date_time must be less than end_date_time")
        self.start_date_time = start_date_time
        self.end_date_time = end_date_time

    def __composite_values__(self) -> tuple[datetime, datetime]:
        """Return the composite values for SQLAlchemy."""
        return self.start_date_time, self.end_date_time

    def __repr__(self) -> str:
        """String representation of Temporal."""
        return f"<Temporal(start_date_time='{self.start_date_time}', end_date_time='{self.end_date_time}')>"

    def __eq__(self, other: object) -> bool:
        """Compare two Temporal instances."""
        if not isinstance(other, Temporal):
            return False
        return (
            self.start_date_time == other.start_date_time
            and self.end_date_time == other.end_date_time
        )

    @property
    def is_valid(self) -> bool:
        """Check if the temporal period is valid (start < end and year >= 2025)."""
        return (
            self.start_date_time.year >= MIN_START_YEAR
            and self.start_date_time < self.end_date_time
        )

    def __ne__(self, other: object) -> bool:
        """Compare two Temporal instances for inequality."""
        return not self.__eq__(other)
