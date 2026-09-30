"""Every route with a write session commits before its response is sent.

FastAPI runs the teardown of a `yield` dependency after the response by default,
so a client could get 201 before the commit and read back 404. See get_async_db.
"""

from collections.abc import Iterator

import pytest
from app.api.domain_registry import ApiDomain
from app.db.config import get_async_db
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from tests.api.test_openapi_schema_frozen import DOMAIN_STATUS_APPS


def _api_routes(app: FastAPI) -> Iterator[tuple[str, APIRoute]]:
    # app.routes holds included routers as wrappers, iter_route_contexts unfolds them
    for context in iter_route_contexts(app.routes):
        if isinstance(context.original_route, APIRoute):
            yield context.path or context.original_route.path, context.original_route


def _write_session_dependants(dependant: Dependant) -> Iterator[Dependant]:
    for sub in dependant.dependencies:
        if sub.call is get_async_db:
            yield sub
        yield from _write_session_dependants(sub)


@pytest.mark.parametrize(
    ("domain", "app"),
    DOMAIN_STATUS_APPS,
    ids=[domain.label for domain, _app in DOMAIN_STATUS_APPS],
)
def test_write_session_uses_function_scope(domain: ApiDomain, app: FastAPI) -> None:
    for path, route in _api_routes(app):
        for dependant in _write_session_dependants(route.dependant):
            assert dependant.scope == "function", (
                f'{domain.label} {path}: use Depends(get_async_db, scope="function")'
            )


def test_write_session_routes_are_found() -> None:
    # Guards the walk above: if it finds nothing, the scope test passes vacuously
    found = [
        path
        for _domain, app in DOMAIN_STATUS_APPS
        for path, route in _api_routes(app)
        if any(_write_session_dependants(route.dependant))
    ]
    assert len(found) >= 7
