"""OpenAPI schema customization utilities for common APIs."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI


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
        "Body_post_auth_token": "auth.TokenRequest",
        "Body_postArea": "area.AreaRequest",
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


def sort_schemas_by_namespace(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    """Sort schemas by namespace (title prefix) first, then alphabetically.

    Schemas are sorted by their title attribute (e.g., 'area.AreaResponse', 'auth.TokenRequest').
    First by namespace (area, auth, health, validation), then alphabetically within each namespace.

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

        # Sort schemas by namespace first, then alphabetically
        openapi_schema = sort_schemas_by_namespace(openapi_schema)

        # Cache the schema
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return custom_openapi
