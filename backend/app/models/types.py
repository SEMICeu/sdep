"""Shared SQLAlchemy custom types."""

from __future__ import annotations

import json

from sqlalchemy import ARRAY, String, Text, TypeDecorator


class StringArray(TypeDecorator):
    """Custom type for storing arrays as JSON in SQLite and ARRAY in PostgreSQL."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load the appropriate type based on dialect."""
        match dialect.name:
            case "postgresql":
                return dialect.type_descriptor(ARRAY(String(32)))
            case "sqlite":
                return dialect.type_descriptor(Text())
            case _:
                raise NotImplementedError(
                    f"StringArray not supported for dialect: {dialect.name}"
                )

    def process_bind_param(self, value, dialect):
        """Convert list to JSON string for SQLite."""
        if value is None:
            return None
        match dialect.name:
            case "postgresql":
                return value
            case "sqlite":
                return json.dumps(value)
            case _:
                raise NotImplementedError(
                    f"StringArray not supported for dialect: {dialect.name}"
                )

    def process_result_value(self, value, dialect):
        """Convert JSON string back to list for SQLite."""
        if value is None:
            return None
        match dialect.name:
            case "postgresql":
                return value
            case "sqlite":
                return json.loads(value)
            case _:
                raise NotImplementedError(
                    f"StringArray not supported for dialect: {dialect.name}"
                )
