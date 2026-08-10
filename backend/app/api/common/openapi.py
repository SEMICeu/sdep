"""OpenAPI schema customization utilities for common APIs."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from app.config import settings


def replace_auto_generated_body_schemas(
    openapi_schema: dict[str, Any],
) -> dict[str, Any]:
    """Replace auto-generated Body_* schemas with proper namespaced schemas.

    FastAPI auto-generates schemas like 'Body_post_auth_token' for Form parameters.
    This function renames these schemas and their references to use proper namespaces.

    Args:
        openapi_schema: The generated OpenAPI schema dictionary

    Returns:
        Modified OpenAPI schema with renamed schemas
    """
    if (
        "components" not in openapi_schema
        or "schemas" not in openapi_schema["components"]
    ):
        return openapi_schema

    # Map of auto-generated schema names to their replacements
    replacements = {
        "Body_post_auth_token": "Auth.TokenRequest",
        "Body_postArea": "Area.Request",
    }

    schemas = openapi_schema["components"]["schemas"]

    # Rename schemas in components and update their title
    for old_name, new_name in replacements.items():
        if old_name in schemas:
            # Copy the schema with the new name
            schemas[new_name] = schemas[old_name].copy()
            # Update the title to match the new name
            schemas[new_name]["title"] = new_name
            # Remove the old schema
            del schemas[old_name]

    # Replace references in paths
    for _path, path_item in openapi_schema.get("paths", {}).items():
        for _method, operation in path_item.items():
            if "requestBody" in operation:
                for _content_type, content in (
                    operation["requestBody"].get("content", {}).items()
                ):
                    if "schema" in content and "$ref" in content["schema"]:
                        ref = content["schema"]["$ref"]
                        schema_name = ref.split("/")[-1]
                        if schema_name in replacements:
                            content["schema"]["$ref"] = (
                                f"#/components/schemas/{replacements[schema_name]}"
                            )

    return openapi_schema


def remove_fastapi_validation_schemas(
    openapi_schema: dict[str, Any],
) -> dict[str, Any]:
    """Remove FastAPI's built-in validation error schemas.

    FastAPI auto-registers HTTPValidationError and ValidationError in components/schemas.
    Since all validation errors are handled by custom exception handlers returning
    ErrorResponse, these schemas are unused and misleading.

    Args:
        openapi_schema: The generated OpenAPI schema dictionary

    Returns:
        Modified OpenAPI schema with FastAPI validation schemas removed
    """
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    return openapi_schema


def remove_inapplicable_422_responses(
    openapi_schema: dict[str, Any],
) -> dict[str, Any]:
    """Remove auto-generated 422 responses from endpoints that never emit them.

    FastAPI automatically adds a 422 response to any endpoint with parameters or
    request bodies. This function removes default 422 responses from:
    - GET endpoints whose validation errors return 400, not 422
    - Specific POST endpoints where 422 is never emitted (e.g. /auth/token)

    Args:
        openapi_schema: The generated OpenAPI schema dictionary

    Returns:
        Modified OpenAPI schema with 422 removed from inapplicable endpoints
    """
    # Specific (method, path) combinations where 422 is never emitted
    inapplicable: list[tuple[str, str]] = [
        ("post", "/token"),
    ]

    for path, path_item in openapi_schema.get("paths", {}).items():
        get_responses = path_item.get("get", {}).get("responses", {})
        if get_responses.get("422", {}).get("description") == "Validation Error":
            get_responses.pop("422", None)

        # Remove 422 from specific non-GET endpoints
        for method, specific_path in inapplicable:
            if path == specific_path:
                path_item.get(method, {}).get("responses", {}).pop("422", None)

    return openapi_schema


def extract_bulk_activity_item_schema(
    openapi_schema: dict[str, Any],
) -> dict[str, Any]:
    """Extract the inlined ActivityRequest item schema into components.

    `ActivityBulkRequest.activities` uses `SkipValidation[ActivityRequest]` so that
    items pass through without Pydantic validation at request-parse time. A
    side-effect is that FastAPI inlines the item schema instead of registering
    `ActivityRequest` as a separate component. This hook moves the inlined schema
    to `components.schemas["ActivityRequest"]` and replaces the inline with a
    `$ref`, giving the common API contract a reusable, concretely-typed item
    schema.

    Args:
        openapi_schema: The generated OpenAPI schema dictionary

    Returns:
        Modified OpenAPI schema with ActivityRequest extracted and referenced
    """
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    bulk = schemas.get("ActivityBulkRequest")
    if not bulk:
        return openapi_schema

    activities = bulk.get("properties", {}).get("activities", {})
    items = activities.get("items")
    if not items or "$ref" in items:
        return openapi_schema

    schemas["ActivityRequest"] = items
    activities["items"] = {"$ref": "#/components/schemas/ActivityRequest"}
    return openapi_schema


def sort_schemas_by_namespace(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    """Sort schemas by namespace (title prefix) first, then alphabetically.

    Schemas are sorted by their title attribute (e.g., 'Area.Response', 'Auth.TokenRequest').
    First by namespace (Activity, Area, Auth, Common, Error, Health), then alphabetically within each namespace.

    Args:
        openapi_schema: The generated OpenAPI schema dictionary

    Returns:
        Modified OpenAPI schema with sorted schemas
    """
    if (
        "components" not in openapi_schema
        or "schemas" not in openapi_schema["components"]
    ):
        return openapi_schema

    schemas = openapi_schema["components"]["schemas"]

    # Create a sorting key function that extracts namespace from title
    def get_sort_key(item: tuple[str, dict]) -> tuple[str, str]:
        """Return (namespace, name) sort key extracted from a schema's title."""
        schema_name, schema_def = item
        title = schema_def.get("title", schema_name)
        # Split by '.' to get namespace and name
        if "." in title:
            namespace, name = title.split(".", 1)
            return (namespace, name)
        # If no namespace, sort after all namespaced schemas
        return ("zzz_no_namespace", title)

    # Sort schemas by namespace first, then by name
    sorted_schemas = dict(sorted(schemas.items(), key=get_sort_key))

    # Replace with sorted schemas
    openapi_schema["components"]["schemas"] = sorted_schemas

    return openapi_schema


def use_bearer_scheme_when_client_credentials_disabled(
    openapi_schema: dict[str, Any],
) -> dict[str, Any]:
    """Swap the OAuth 2.0 Client Credentials scheme for an HTTP Bearer scheme when the
    client-credentials (client_secret) token flow is disabled.

    Swagger UI's "Authorize" button for the OAuth 2.0 Client Credentials flow performs a
    client_id/client_secret exchange against ``/token``. When
    ``CLIENT_SECRET_AUTH_ENABLED`` is false that exchange is rejected, so the
    button cannot obtain a token. Swagger cannot sign a client JWT itself, so rather
    than drop authentication from the docs entirely we expose a plain Bearer scheme:
    the operator obtains a token out of band (client-signed JWT) and pastes it into
    Authorize to exercise protected endpoints.

    This only rewrites the OpenAPI document the docs are rendered from; runtime
    bearer-token verification is unchanged. When the flow is enabled the schema is
    returned untouched.
    """
    if settings.CLIENT_SECRET_AUTH_ENABLED:
        return openapi_schema

    components = openapi_schema.get("components", {})
    security_schemes = components.get("securitySchemes", {})

    oauth2_names = {
        name
        for name, scheme in security_schemes.items()
        if scheme.get("type") == "oauth2"
        and "clientCredentials" in scheme.get("flows", {})
    }
    if not oauth2_names:
        return openapi_schema

    bearer_name = "BearerAuth"
    for name in oauth2_names:
        del security_schemes[name]
    security_schemes[bearer_name] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    components["securitySchemes"] = security_schemes
    openapi_schema["components"] = components

    # Repoint every operation's security requirement at the Bearer scheme.
    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            security = operation.get("security")
            if security:
                operation["security"] = [
                    {bearer_name: []}
                    if any(scheme_name in oauth2_names for scheme_name in requirement)
                    else requirement
                    for requirement in security
                ]

    return openapi_schema


def create_custom_openapi(app: FastAPI) -> Callable:
    """Factory function to create a custom OpenAPI schema generator.

    This factory creates a closure that:
    1. Caches the generated OpenAPI schema
    2. Sorts schemas by namespace first, then alphabetically

    Args:
        app: FastAPI application instance

    Returns:
        Custom OpenAPI schema generator function
    """
    # Store reference to original openapi method
    _original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        """Generate and cache custom OpenAPI schema."""
        if app.openapi_schema:
            return app.openapi_schema

        # Generate base schema
        openapi_schema = _original_openapi()

        # Replace auto-generated Body_* schemas with proper namespaced schemas
        openapi_schema = replace_auto_generated_body_schemas(openapi_schema)

        # Remove FastAPI's built-in validation schemas (replaced by ErrorResponse)
        openapi_schema = remove_fastapi_validation_schemas(openapi_schema)

        # Remove 422 from endpoints that never emit it
        openapi_schema = remove_inapplicable_422_responses(openapi_schema)

        # Extract inlined ActivityRequest item schema into components
        openapi_schema = extract_bulk_activity_item_schema(openapi_schema)

        # Sort schemas by namespace first, then alphabetically
        openapi_schema = sort_schemas_by_namespace(openapi_schema)

        # When client-secret authentication is disabled, present a Bearer scheme in
        # the docs instead of the (non-functional) OAuth 2.0 Authorize flow.
        openapi_schema = use_bearer_scheme_when_client_credentials_disabled(
            openapi_schema
        )

        # Cache the schema
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return custom_openapi
