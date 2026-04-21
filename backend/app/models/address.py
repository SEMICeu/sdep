"""Address composite class."""


class Address:
    """Address composite representing physical addresses.

    This is a composite type (not a standalone entity) used inline in Activity.
    Represents a physical location using INSPIRE/STR-AP field names for EU
    interoperability, with granular locatorDesignator sub-fields for national
    registry compatibility (e.g., Dutch BAG).
    """

    def __init__(
        self,
        thoroughfare: str,
        locator_designator_number: int | None,
        locator_designator_letter: str | None,
        locator_designator_addition: str | None,
        post_code: str,
        post_name: str,
        full_address: str,
    ):
        """Initialize Address composite.

        Args:
            thoroughfare: Street / public space name (max 80 chars, required), e.g. "Prinsengracht"
            locator_designator_number: Numeric house number component (optional, >= 0 when provided), e.g. 263
            locator_designator_letter: Letter/character suffix (max 10 chars, optional), e.g. "a", "bis"
            locator_designator_addition: Additional qualifier (max 128 chars, optional), e.g. "II", "Apt 3"
            post_code: Postal code (max 10 chars, alphanumeric, no spaces, required), e.g. "1016GV"
            post_name: City / town / village (max 80 chars, required), e.g. "Amsterdam"
            full_address: Full address as a single string (max 318 chars, required), e.g. "Turfmarkt 147a-5h, 2500EA Den Haag"
        """
        self.thoroughfare = thoroughfare
        self.locator_designator_number = locator_designator_number
        self.locator_designator_letter = locator_designator_letter
        self.locator_designator_addition = locator_designator_addition
        self.post_code = post_code
        self.post_name = post_name
        self.full_address = full_address

    def __composite_values__(
        self,
    ) -> tuple[str, int | None, str | None, str | None, str, str, str]:
        """Return the composite values for SQLAlchemy."""
        return (
            self.thoroughfare,
            self.locator_designator_number,
            self.locator_designator_letter,
            self.locator_designator_addition,
            self.post_code,
            self.post_name,
            self.full_address,
        )

    def __repr__(self) -> str:
        """String representation of Address."""
        return f"<Address(thoroughfare='{self.thoroughfare}', locator_designator_number={self.locator_designator_number}, post_name='{self.post_name}')>"

    def __eq__(self, other: object) -> bool:
        """Compare two Address instances."""
        if not isinstance(other, Address):
            return False
        return (
            self.thoroughfare == other.thoroughfare
            and self.locator_designator_number == other.locator_designator_number
            and self.locator_designator_letter == other.locator_designator_letter
            and self.locator_designator_addition == other.locator_designator_addition
            and self.post_code == other.post_code
            and self.post_name == other.post_name
            and self.full_address == other.full_address
        )

    def __ne__(self, other: object) -> bool:
        """Compare two Address instances for inequality."""
        return not self.__eq__(other)
