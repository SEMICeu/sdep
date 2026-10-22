"""Generated functional IDs and resend detection (idempotency).

A functional ID that the caller did not supply is a UUIDv8 (RFC 9562) made from
HMAC-SHA256(secret, canonical JSON of the record). The same record of the same
owner therefore always gets the same ID. A record that is identical to the
current version of its ID, generated or supplied, is a resend: the services
return the stored version, no new one. See docs/ARCHITECTURE_TECH.md, "Idempotency".

- The secret (FUNCTIONAL_ID_SECRET) keeps IDs unpredictable: nobody else can
  compute an ID and claim it first (models/identity.py)
- `owner` keeps two owners with the same record apart, `kind` the resources
- `generation` gives a deleted record a new ID when it is submitted again
- `fields` are the validated record (see `content`): trimmed and normalized, so
  " Name " and "Name", or "" and null, give the same ID
"""

import hashlib
import hmac
import json
import uuid
from collections.abc import Awaitable, Callable, Hashable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.config import get_settings

Kind = Literal["area", "listing", "activity"]

# Version of the canonical input below: a change of the input needs a new value.
_INPUT_VERSION = 1


def content(item: BaseModel, id_field: str) -> dict[str, Any]:
    """
    Return the fields of a request item that make up the record, without its ID.

    JSON mode, so equal values give equal output: the UTC offset `Z` equals `+00:00`, and an
    omitted field equals its default.
    """
    return item.model_dump(mode="json", by_alias=True, exclude={id_field})


def stored_content(
    request_cls: type[BaseModel], response: BaseModel, id_field: str
) -> dict[str, Any]:
    """
    Return the content of a stored version, in the shape of `content`.

    The response goes back through the request model, so both sides are
    normalized the same way. Its extra fields (e.g. `createdAt`) are ignored.
    """
    data = _as_utc(response.model_dump(by_alias=True))
    return content(request_cls.model_validate(data), id_field)


def _as_utc(value: Any) -> Any:
    # SQLite returns naive datetimes (stored as UTC), the request model wants UTC.
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
    if isinstance(value, dict):
        return {k: _as_utc(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_as_utc(v) for v in value]
    return value


def generate_id(
    kind: Kind,
    owner_id: str,
    fields: Mapping[str, Any],
    generation: int = 0,
) -> str:
    """
    Return the deterministic functional ID of a record, as a UUIDv8 string.

    Args:
        kind: Resource type
        owner_id: Public ID of the owner (competentAuthorityId or platformId)
        fields: JSON-serializable record fields, without the functional ID
        generation: 0, or n after n deleted records with the same content

    Returns:
        Lowercase UUID string
    """
    canonical = json.dumps(
        {
            "fields": fields,
            "generation": generation,
            "kind": kind,
            "owner": owner_id,
            "v": _INPUT_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    key = get_settings().FUNCTIONAL_ID_SECRET.get_secret_value().encode()
    digest = hmac.new(key, canonical, hashlib.sha256).digest()
    return str(uuid.UUID(bytes=digest[:16], version=8))


async def resolve_ids[K: Hashable](
    kind: Kind,
    owner_id: str,
    fields_by_key: Mapping[K, Mapping[str, Any]],
    deleted: Callable[[list[str]], Awaitable[set[str]]],
) -> dict[K, str]:
    """
    Generate the IDs of a batch, skipping IDs whose record was deleted.

    A deleted ID stays deleted, so the next generation is tried until the ID is
    free or current. A resend follows the same steps and lands on the same ID.

    Args:
        kind: Resource type
        owner_id: Public ID of the owner
        fields_by_key: Record fields per caller key (e.g. the item index)
        deleted: Returns which of the given IDs have versions, but none current

    Returns:
        Dictionary {caller key: generated ID}
    """
    generation = dict.fromkeys(fields_by_key, 0)
    ids = {k: generate_id(kind, owner_id, f) for k, f in fields_by_key.items()}
    pending = list(fields_by_key)
    while pending:
        gone = await deleted([ids[k] for k in pending])
        pending = [k for k in pending if ids[k] in gone]
        for k in pending:
            generation[k] += 1
            ids[k] = generate_id(kind, owner_id, fields_by_key[k], generation[k])
    return ids
