"""Address composite class."""


class Address:
    """Address composite representing physical addresses.

    This is a composite type (not a standalone entity) used inline in Activity.
    Represents a physical location with street, number, and other address components.
    """

    def __init__(
        self,
        street: str,
        number: int,
        letter: str | None,
        addition: str | None,
        postal_code: str,
        city: str,
    ):
        """Initialize Address composite.

        Args:
            street: Street name (max 64 chars, mandatory), for example "Turfmarkt"
            number: House number (mandatory), for example 147
            letter: House letter, for example "a"
            addition: House addition, for example "5h"
            postal_code: Postal code (max 8 chars, alfanumeric, no spaces, mandatory), for example "2500EA"
            city: City name (max 64 chars, mandatory), for example "Den Haag"
        """
        self.street = street
        self.number = number
        self.letter = letter
        self.addition = addition
        self.postal_code = postal_code
        self.city = city

    def __composite_values__(
        self,
    ) -> tuple[str, int, str | None, str | None, str, str]:
        """Return the composite values for SQLAlchemy."""
        return (
            self.street,
            self.number,
            self.letter,
            self.addition,
            self.postal_code,
            self.city,
        )

    def __repr__(self) -> str:
        """String representation of Address."""
        return f"<Address(street='{self.street}', number={self.number}, city='{self.city}')>"

    def __eq__(self, other: object) -> bool:
        """Compare two Address instances."""
        if not isinstance(other, Address):
            return False
        return (
            self.street == other.street
            and self.number == other.number
            and self.letter == other.letter
            and self.addition == other.addition
            and self.postal_code == other.postal_code
            and self.city == other.city
        )

    def __ne__(self, other: object) -> bool:
        """Compare two Address instances for inequality."""
        return not self.__eq__(other)
