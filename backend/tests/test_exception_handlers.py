from app.api.common.exception_handlers import register_exception_handlers
from app.exceptions.auth import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
)
from app.exceptions.business import (
    ApplicationValidationError,
    DuplicateResourceError,
    ResourceNotFoundError,
)
from app.exceptions.handlers import (
    authentication_exception_handler,
    authorization_exception_handler,
    authorization_server_unavailable_exception_handler,
    business_logic_exception_handler,
    database_unavailable_exception_handler,
    general_exception_handler,
    http_exception_handler,
    resource_not_found_exception_handler,
    validation_exception_handler,
)
from app.exceptions.infrastructure import (
    AuthorizationServerOperationalError,
    DatabaseOperationalError,
)
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from starlette.requests import Request


def _request(path: str = "/test", method: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
    )


class _ValidationModel:
    def __init__(self, value: int):
        self.value = value


async def test_validation_exception_handler_get_uses_400_for_query_errors():
    exc = RequestValidationError(
        [
            {
                "type": "int_parsing",
                "loc": ("query", "limit"),
                "msg": "bad int",
                "input": "x",
            }
        ]
    )

    response = await validation_exception_handler(_request(method="GET"), exc)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.body
        == b'{"detail":[{"msg":"bad int","type":"int_parsing","loc":["query","limit"]}]}'
    )


async def test_validation_exception_handler_non_get_uses_422_and_json_invalid_message():
    exc = RequestValidationError(
        [{"type": "json_invalid", "loc": (), "msg": "JSON decode error", "input": "{"}]
    )

    response = await validation_exception_handler(_request(method="POST"), exc)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert (
        response.body
        == b'{"detail":[{"msg":"Request body contains invalid JSON syntax","type":"json_invalid"}]}'
    )


async def test_validation_exception_handler_supports_pydantic_validation_error():
    exc = ValidationError.from_exception_data(
        "TestModel",
        [
            {
                "type": "missing",
                "loc": ("field",),
                "input": None,
            }
        ],
    )
    response = await validation_exception_handler(_request(method="POST"), exc)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert b'"type":"missing"' in response.body


async def test_business_logic_exception_handler_uses_duplicate_status_code():
    response = await business_logic_exception_handler(
        _request(), DuplicateResourceError("already exists")
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.body
        == b'{"detail":[{"msg":"already exists","type":"duplicate_error"}]}'
    )


async def test_business_logic_exception_handler_uses_default_status_code():
    response = await business_logic_exception_handler(
        _request(), ApplicationValidationError("invalid state")
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert (
        response.body
        == b'{"detail":[{"msg":"invalid state","type":"business_logic_error"}]}'
    )


async def test_authentication_exception_handler_sets_bearer_header():
    response = await authentication_exception_handler(
        _request(), AuthenticationError("bad token")
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_authentication_exception_handler_supports_invalid_token_error():
    response = await authentication_exception_handler(
        _request(), InvalidTokenError("expired")
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert b"Token is invalid or expired" in response.body


async def test_authorization_exception_handler_returns_403():
    response = await authorization_exception_handler(
        _request(), AuthorizationError("missing role")
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert (
        response.body
        == b'{"detail":[{"msg":"missing role","type":"authorization_error"}]}'
    )


async def test_resource_not_found_exception_handler_returns_404():
    response = await resource_not_found_exception_handler(
        _request(), ResourceNotFoundError("missing")
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.body == b'{"detail":[{"msg":"missing","type":"not_found_error"}]}'


async def test_http_exception_handler_maps_status_families():
    unauthorized = await http_exception_handler(
        _request(), HTTPException(status_code=401, detail="bad auth")
    )
    forbidden = await http_exception_handler(
        _request(), HTTPException(status_code=403, detail="nope")
    )
    not_found = await http_exception_handler(
        _request(), HTTPException(status_code=404, detail="gone")
    )
    duplicate = await http_exception_handler(
        _request(), HTTPException(status_code=409, detail="duplicate")
    )
    validation = await http_exception_handler(
        _request(), HTTPException(status_code=418, detail="teapot")
    )
    server = await http_exception_handler(
        _request(), HTTPException(status_code=500, detail="boom")
    )

    assert unauthorized.headers["WWW-Authenticate"] == "Bearer"
    assert b'"authentication_error"' in unauthorized.body
    assert b'"authorization_error"' in forbidden.body
    assert b'"not_found_error"' in not_found.body
    assert b'"duplicate_error"' in duplicate.body
    assert b'"validation_error"' in validation.body
    assert b'"server_error"' in server.body


async def test_database_unavailable_exception_handler_supports_both_exception_types():
    custom_response = await database_unavailable_exception_handler(
        _request(), DatabaseOperationalError("db down")
    )
    sqlalchemy_response = await database_unavailable_exception_handler(
        _request(), OperationalError("SELECT 1", {}, Exception("db down"))
    )

    assert custom_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert sqlalchemy_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert b"Database is temporarily unavailable" in custom_response.body


async def test_authorization_server_unavailable_exception_handler_returns_503():
    response = await authorization_server_unavailable_exception_handler(
        _request(), AuthorizationServerOperationalError("kc down")
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert b"Authorization server is temporarily unavailable" in response.body


async def test_general_exception_handler_hides_internal_details():
    response = await general_exception_handler(
        _request(), RuntimeError("secret details")
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert b"An internal server error occurred" in response.body
    assert b"secret details" not in response.body


def test_register_exception_handlers_registers_expected_mappings():
    app = FastAPI()

    register_exception_handlers(app)

    assert app.exception_handlers[HTTPException] is http_exception_handler
    assert (
        app.exception_handlers[RequestValidationError] is validation_exception_handler
    )
    assert (
        app.exception_handlers[ApplicationValidationError]
        is business_logic_exception_handler
    )
    assert (
        app.exception_handlers[ResourceNotFoundError]
        is resource_not_found_exception_handler
    )
    assert (
        app.exception_handlers[AuthenticationError] is authentication_exception_handler
    )
    assert app.exception_handlers[AuthorizationError] is authorization_exception_handler
    assert app.exception_handlers[InvalidTokenError] is authentication_exception_handler
    assert (
        app.exception_handlers[DatabaseOperationalError]
        is database_unavailable_exception_handler
    )
    assert (
        app.exception_handlers[OperationalError]
        is database_unavailable_exception_handler
    )
    assert (
        app.exception_handlers[AuthorizationServerOperationalError]
        is authorization_server_unavailable_exception_handler
    )
    assert app.exception_handlers[Exception] is general_exception_handler
