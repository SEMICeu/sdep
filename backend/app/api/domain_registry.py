"""API domain metadata registry."""

from dataclasses import dataclass
from html import escape
from typing import Literal

ApiStatus = Literal["stable", "beta"]


@dataclass(frozen=True)
class ApiDomain:
    label: str
    root_path: str
    title: str
    description: str
    status: ApiStatus

    @property
    def docs_path(self) -> str:
        return f"{self.root_path}/docs"

    @property
    def openapi_path(self) -> str:
        return f"{self.root_path}/openapi.json"

    @property
    def description_with_status(self) -> str:
        return f"{self.description} Status: {self.status}."

    @property
    def html(self) -> str:
        status = escape(self.status)

        return (
            '    <div class="version">\n'
            f'      <a href="{escape(self.docs_path)}">{escape(self.label)}</a>\n'
            f'      <span class="status status-{status}">{status}</span>\n'
            "      &nbsp;|&nbsp;\n"
            f'      <a href="{escape(self.openapi_path)}">OpenAPI JSON</a>\n'
            "    </div>"
        )


AUTH_V1 = ApiDomain(
    label="Auth v1",
    root_path="/api/auth/v1",
    title="SDEP - Auth API",
    description=(
        "Authentication endpoints for machine-to-machine OAuth2 Client Credentials flow "
        "via Keycloak."
    ),
    status="stable",
)

CA_V1 = ApiDomain(
    label="CA v1",
    root_path="/api/ca/v1",
    title="SDEP - Competent Authority (CA) API",
    description=(
        "Endpoints for competent authorities to manage areas and to view activities."
    ),
    status="stable",
)

CA_V2 = ApiDomain(
    label="CA v2",
    root_path="/api/ca/v2",
    title="SDEP - Competent Authority (CA) API",
    description=(
        "Endpoints for competent authorities to manage areas and to view activities."
    ),
    status="beta",
)

STR_V1 = ApiDomain(
    label="STR v1",
    root_path="/api/str/v1",
    title="SDEP - Short-Term Rental Platform (STR) API",
    description=(
        "Endpoints for short-term rental platforms to view areas and to submit activities."
    ),
    status="stable",
)

REP_V1 = ApiDomain(
    label="REP v1",
    root_path="/api/rep/v1",
    title="SDEP - Reporting (REP) API",
    description=(
        "Read-only endpoints for the national statistics office to view all "
        "registered activity data."
    ),
    status="beta",
)

API_DOMAINS = (AUTH_V1, CA_V1, CA_V2, STR_V1, REP_V1)
