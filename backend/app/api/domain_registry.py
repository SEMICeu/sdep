"""API domain metadata registry."""

from dataclasses import dataclass
from html import escape
from typing import Literal

ApiStatus = Literal["stable", "beta"]
# EU-harmonized: common to every SDEP implementation. Country-specific: guidance only,
# may differ per Member State (this one is SDEP-NL).
ApiScope = Literal["eu-harmonized", "country-specific"]

# Landing page groups, in display order: (scope, heading, one-line note).
API_SCOPES: tuple[tuple[ApiScope, str, str], ...] = (
    (
        "eu-harmonized",
        "EU-harmonized",
        "Common to all SDEP implementations in EU Member States.",
    ),
    (
        "country-specific",
        "Country-specific",
        "Implemented for SDEP-NL. This may differ per Member State, but can be used "
        "for guidance and as a reference implementation.",
    ),
)

# OpenAPI specification version every sub-app emits, shown once as a badge in the docs
# landing page header. Bound to the served contract by the registry tests.
OAS_VERSION = "3.1"

# Published location of the generated version diff (see docs/API_DIFF.md).
VERSION_DIFF_URL = "https://github.com/SEMICeu/sdep/blob/main/docs/API_DIFF.md"


@dataclass(frozen=True)
class ApiDomain:
    label: str
    root_path: str
    title: str
    description: str
    status: ApiStatus
    scope: ApiScope
    # Cross-version links, given as root paths and resolved lazily against API_DOMAINS so a
    # sibling's label and status are never duplicated in this version's text.
    supersedes_path: str | None = None
    superseded_by_path: str | None = None
    # What this version changes relative to the version it supersedes. Single source for the
    # OpenAPI description, the docs landing page, and the narrative documentation.
    changes: str | None = None
    diff_url: str | None = None

    @property
    def docs_path(self) -> str:
        return f"{self.root_path}/docs"

    @property
    def openapi_path(self) -> str:
        return f"{self.root_path}/openapi.json"

    @property
    def supersedes(self) -> "ApiDomain | None":
        return _resolve(self.supersedes_path)

    @property
    def superseded_by(self) -> "ApiDomain | None":
        return _resolve(self.superseded_by_path)

    @property
    def version_note(self) -> str:
        """Cross-version pointer, shown at the top of Swagger UI via the OpenAPI description."""
        previous = self.supersedes
        if previous is not None and self.changes:
            return f"Changes from {previous.label}: {self.changes}"

        successor = self.superseded_by
        if successor is not None:
            return f"Superseded by {successor.label} ({successor.status})."

        return ""

    @property
    def description_with_status(self) -> str:
        parts = (self.description, f"Status: {self.status}.", self.version_note)
        return " ".join(part for part in parts if part)

    @property
    def html(self) -> str:
        status = escape(self.status)
        diff_link = (
            "\n      &nbsp;|&nbsp;\n"
            f'      <a href="{escape(self.diff_url)}">Version diff</a>'
            if self.diff_url
            else ""
        )

        return (
            '    <div class="version">\n'
            f'      <a href="{escape(self.docs_path)}">{escape(self.label)}</a>\n'
            f'      <span class="status status-{status}">{status}</span>\n'
            "      &nbsp;|&nbsp;\n"
            f'      <a href="{escape(self.openapi_path)}">OpenAPI JSON</a>'
            f"{diff_link}\n"
            "    </div>"
        )


AUTH_V1 = ApiDomain(
    label="Auth v1",
    root_path="/api/auth/v1",
    title="SDEP - Auth API",
    description=(
        "Authentication endpoints for machine-to-machine OAuth 2.0 Client Credentials flow "
        "via Keycloak."
    ),
    status="stable",
    scope="eu-harmonized",
)

CA_V1 = ApiDomain(
    label="CA v1",
    root_path="/api/ca/v1",
    title="SDEP - Competent Authority (CA) API",
    description=(
        "Endpoints for competent authorities to manage areas and to view activities."
    ),
    status="stable",
    scope="country-specific",
    superseded_by_path="/api/ca/v2",
)

CA_V2 = ApiDomain(
    label="CA v2",
    root_path="/api/ca/v2",
    title="SDEP - Competent Authority (CA) API",
    description=(
        "Endpoints for competent authorities to manage areas and to view activities."
    ),
    status="beta",
    scope="country-specific",
    supersedes_path="/api/ca/v1",
    changes=(
        "adds four optional activity filters (`createdAtFrom`, `createdAtTo`, "
        "`platformId`, `areaId`) on the activity list and count endpoints; "
        "no other changes."
    ),
    diff_url=VERSION_DIFF_URL,
)

STR_V1 = ApiDomain(
    label="STR v1",
    root_path="/api/str/v1",
    title="SDEP - Short-Term Rental Platform (STR) API",
    description=(
        "Endpoints for short-term rental platforms to view areas and to submit activities."
    ),
    status="stable",
    scope="eu-harmonized",
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
    scope="country-specific",
)

API_DOMAINS = (AUTH_V1, CA_V1, CA_V2, STR_V1, REP_V1)


def _resolve(root_path: str | None) -> ApiDomain | None:
    """Look up a sibling domain by root path (lazy - API_DOMAINS is defined above)."""
    if root_path is None:
        return None

    return next(
        (domain for domain in API_DOMAINS if domain.root_path == root_path), None
    )
