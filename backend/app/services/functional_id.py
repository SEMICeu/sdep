"""Generated functional IDs and resend detection (idempotency).

A functional ID that the caller did not supply is a UUIDv8 (RFC 9562) made from
HMAC-SHA256(secret, canonical JSON of the record key). The same key of the same
owner therefore always gets the same ID. A record that is identical to the
current version of its ID, generated or supplied, is a resend: the services
return the stored version, no new one. See docs/ARCHITECTURE_TECH.md, "Idempotency".
Generation is deprecated, in favour of a UUID that the client supplies.

- The secret (FUNCTIONAL_ID_SECRET) keeps IDs unpredictable: nobody else can
  compute an ID and claim it first (models/identity.py)
- `owner` keeps two owners with the same record apart, `kind` the resources
- `generation` gives a deleted record a new ID when it is submitted again
- `fields` are the key of the validated record (see `key` and `content`): trimmed
  and normalized, so " Name " and "Name", or "" and null, give the same ID

A new functional ID that the caller supplies must be a lowercase UUID, see
`refused_ids` and docs/ARCHITECTURE_TECH.md, "ID management".
"""

import hashlib
import hmac
import json
import re
import uuid
from collections.abc import Awaitable, Callable, Hashable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud import identity as identity_crud
from app.models.identity import IdentityModel

Kind = Literal["area", "listing", "activity"]

# Version of the canonical input below, per kind: a change of the input needs a new
# value. Activity and listing moved from all fields to a key (version 2).
_INPUT_VERSION: dict[Kind, int] = {"area": 1, "activity": 2, "listing": 2}

# Key fields per kind, as paths in `content`. A key keeps the ID stable when other
# fields change or are added, see docs/ARCHITECTURE_TECH.md, "ID management".
# An area has no request model: its key is built in services/area.py.
KEY_FIELDS: dict[Kind, tuple[str, ...]] = {
    "activity": (
        "registrationNumber",
        "temporal.startDatetime",
        "temporal.endDatetime",
        "url",
    ),
    "listing": ("url",),
}

# Textual UUID format (RFC 9562, section 4), lowercase only: IDs are case-sensitive,
# so one spelling per UUID. Version and variant are left free (v4, v5, v8, ...).
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_UUID_RE = re.compile(UUID_PATTERN)


def is_uuid(value: str) -> bool:
    """Return whether the value is a UUID in lowercase text format."""
    return _UUID_RE.fullmatch(value) is not None


def uuid_required_message(field: str, value: str) -> str:
    """Return the error message for a supplied ID that `refused_ids` refuses."""
    return (
        f"{field} '{value}' must be a lowercase UUID (RFC 9562), "
        "e.g. '3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b'; "
        "an existing ID of your own may still be resubmitted"
    )


async def refused_ids(
    session: AsyncSession,
    model: IdentityModel,
    supplied_ids: Iterable[str],
) -> set[str]:
    """
    Return the supplied IDs that are refused, because a new ID must be a UUID.

    An ID that exists already stays accepted, so its owner can still version the
    record. Nothing is refused when FUNCTIONAL_ID_UUID_REQUIRED is off.

    Args:
        session: Async database session
        model: Identity model of the resource, e.g. AreaIdentity
        supplied_ids: IDs that the caller supplied (never the generated ones)

    Returns:
        The IDs that are no lowercase UUID and do not exist yet
    """
    if not get_settings().FUNCTIONAL_ID_UUID_REQUIRED:
        return set()
    candidates = {i for i in supplied_ids if not is_uuid(i)}
    return candidates - await identity_crud.existing(session, model, candidates)


def content(item: BaseModel, id_field: str) -> dict[str, Any]:
    """
    Return the fields of a request item that make up the record, without its ID.

    JSON mode, so equal values give equal output: the UTC offset `Z` equals `+00:00`, and an
    omitted field equals its default.
    """
    return item.model_dump(mode="json", by_alias=True, exclude={id_field})


def key(kind: Kind, fields: Mapping[str, Any]) -> dict[str, Any]:
    """Return the key fields of a record (see KEY_FIELDS), flat by path."""
    result: dict[str, Any] = {}
    for path in KEY_FIELDS[kind]:
        value: Any = fields
        for part in path.split("."):
            value = value[part]
        result[path] = value
    return result


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
        fields: JSON-serializable key fields of the record (see `key`)
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
            "v": _INPUT_VERSION[kind],
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
    closed: Callable[[Mapping[K, str]], Awaitable[set[K]]] | None = None,
) -> dict[K, str]:
    """
    Generate the IDs of a batch, skipping IDs whose record was deleted or closed.

    A deleted ID stays deleted, so the next generation is tried until the ID is
    free or current. A resend follows the same steps and lands on the same ID.

    Args:
        kind: Resource type
        owner_id: Public ID of the owner
        fields_by_key: Key fields per caller key (e.g. the item index)
        deleted: Returns which of the given IDs have versions, but none current
        closed: Returns which caller keys may not version their current ID,
            e.g. a screened listing with other content (see services/listing_bulk.py)

    Returns:
        Dictionary {caller key: generated ID}
    """
    generation = dict.fromkeys(fields_by_key, 0)
    ids = {k: generate_id(kind, owner_id, f) for k, f in fields_by_key.items()}
    pending = list(fields_by_key)
    while pending:
        gone = await deleted([ids[k] for k in pending])
        shut = await closed({k: ids[k] for k in pending}) if closed else set()
        pending = [k for k in pending if ids[k] in gone or k in shut]
        for k in pending:
            generation[k] += 1
            ids[k] = generate_id(kind, owner_id, fields_by_key[k], generation[k])
    return ids
