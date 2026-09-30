"""API domain metadata registry."""

from dataclasses import dataclass
from html import escape
from typing import Literal

from app.config import settings

# Lifecycle, see docs/API_TECH.md "Design": N goes alpha -> beta -> stable, N-1 goes
# stable -> deprecated. "deprecated" is added once the first version retires; the
# signals it drives are in docs/API_TECH.md "Implementation (deprecation)".
ApiStatus = Literal["stable", "beta", "alpha"]
# EU-harmonized: common to every SDEP implementation. Country-specific: guidance only,
# may differ per Member State (this one is SDEP-NL).
ApiScope = Literal["eu-harmonized", "country-specific"]
# Landing page section a domain version is listed in, see API_GROUPS.
ApiGroup = Literal["authentication", "activities", "listings"]

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

# Landing page sections, in display order: (group, heading). The heading starts with the
# major version of its domains (checked by the registry tests). The scope groups above
# repeat inside each section.
API_GROUPS: tuple[tuple[ApiGroup, str], ...] = (
    ("authentication", "v1 (authentication)"),
    ("activities", "v1 (activities)"),
    ("listings", "v2 (listings)"),
)

# OpenAPI specification version every sub-app emits, shown once as a badge in the docs
# landing page header. Bound to the served contract by the registry tests.
OAS_VERSION = "3.1"

# Published location of the generated version diff (see docs/API_DIFF_TECH.md).
VERSION_DIFF_URL = "https://github.com/SEMICeu/sdep/blob/main/docs/API_DIFF_TECH.md"


@dataclass(frozen=True)
class ApiDomain:
    label: str
    # The acronym spelled out, e.g. "Short-Term Rental Platform" for STR: the landing page
    # one-liner. Must equal the docs/DEFINITIONS.md heading when the acronym is defined
    # there, casing aside (checked by the docs-consistency gate).
    name: str
    root_path: str
    title: str
    description: str
    status: ApiStatus
    scope: ApiScope
    group: ApiGroup
    # Cross-version links, given as root paths and resolved lazily against API_DOMAINS so a
    # sibling's label and status are never duplicated in this version's text.
    supersedes_path: str | None = None
    superseded_by_path: str | None = None
    # What this version changes relative to the version it supersedes. Single source for the
    # OpenAPI description, the docs landing page, and the narrative documentation.
    changes: str | None = None
    diff_url: str | None = None
    # A trailing slash returns 404 (NLgov `/core/no-trailing-slash`, see docs/API_TECH.md).
    # Auth, CA and STR v1 were frozen with the redirect and keep it, so no client breaks.
    redirect_slashes: bool = False

    @property
    def acronym(self) -> str:
        """The domain acronym as used in the label, e.g. "STR" for "STR v1"."""
        return self.label.split()[0]

    @property
    def major(self) -> int:
        """The major version from the root path, e.g. 2 for "/api/str/v2"."""
        return int(self.root_path.rsplit("/v", 1)[1])

    @property
    def docs_path(self) -> str:
        return f"{self.root_path}/docs"

    @property
    def openapi_path(self) -> str:
        return f"{self.root_path}/openapi.json"

    @property
    def supersedes(self) -> ApiDomain | None:
        return _resolve(self.supersedes_path)

    @property
    def superseded_by(self) -> ApiDomain | None:
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
            f'      <span class="name">{escape(self.name)}</span>\n'
            "    </div>"
        )


AUTH_V1 = ApiDomain(
    label="Auth v1",
    name="Authentication",
    root_path="/api/auth/v1",
    title="SDEP - Auth API",
    description=(
        "Authentication endpoints for machine-to-machine OAuth 2.0 Client Credentials flow "
        "via Keycloak."
    ),
    status="stable",
    redirect_slashes=True,
    scope="eu-harmonized",
    group="authentication",
)

CA_V1 = ApiDomain(
    label="CA v1",
    name="Competent Authority",
    root_path="/api/ca/v1",
    title="SDEP - Competent Authority (CA) API",
    description=(
        "Endpoints for competent authorities to manage areas and to view activities."
    ),
    status="stable",
    redirect_slashes=True,
    scope="country-specific",
    group="activities",
    superseded_by_path="/api/ca/v2",
)

CA_V2 = ApiDomain(
    label="CA v2",
    name="Competent Authority",
    root_path="/api/ca/v2",
    title="SDEP - Competent Authority (CA) API",
    description=(
        "Endpoints for competent authorities to manage areas, to view activities and "
        "platforms, and to view acknowledged listings (random checks)."
    ),
    status="alpha",
    scope="country-specific",
    group="listings",
    supersedes_path="/api/ca/v1",
    changes=(
        "the activity response documents the field "
        "maximums (e.g. `url` 2048, `fullAddress` 328); adds `GET /listings` and "
        "`GET /listings/count` (acknowledged listings in own areas, random checks); "
        "adds `GET /platforms` and `GET /platforms/count`; "
        "no other changes."
    ),
    diff_url=VERSION_DIFF_URL,
)

STR_V1 = ApiDomain(
    label="STR v1",
    name="Short-Term Rental Platform",
    root_path="/api/str/v1",
    title="SDEP - Short-Term Rental Platform (STR) API",
    description=(
        "Endpoints for short-term rental platforms to view areas and to submit activities."
    ),
    status="stable",
    redirect_slashes=True,
    scope="eu-harmonized",
    group="activities",
    superseded_by_path="/api/str/v2",
)

STR_V2 = ApiDomain(
    label="STR v2",
    name="Short-Term Rental Platform",
    root_path="/api/str/v2",
    title="SDEP - Short-Term Rental Platform (STR) API",
    description=(
        "Endpoints for short-term rental platforms to view areas, to submit and "
        "acknowledge listings (random checks), and to submit activities."
    ),
    status="alpha",
    scope="eu-harmonized",
    group="listings",
    supersedes_path="/api/str/v1",
    changes=(
        "activity timestamps must be UTC (offset `Z` or `+00:00`; no other offsets, no date-only values); "
        "activity `url` and `fullAddress` allow 2048 and 328 characters (v1: 128 and 318); "
        "activities are rejected per item (`regulation_error`) for areas that are "
        "regulated for listing only; `GET /areas` returns at most 1000 areas per call "
        "(`limit` defaults to 1000); adds the listing endpoints for random checks "
        "(`POST /listings/bulk`, `GET /listings`, `GET /listings/count`, "
        "`POST /listing-acknowledgements/bulk`); no other changes."
    ),
    diff_url=VERSION_DIFF_URL,
)

LSA_V2 = ApiDomain(
    label="LSA v2",
    name="Listing Screening Authority",
    root_path="/api/lsa/v2",
    title="SDEP - Listing Screening Authority (LSA) API",
    description=(
        "Endpoints for the listing screening authority to retrieve submitted listings and to "
        "submit screening results (random checks), and to view platforms, competent "
        "authorities and areas."
    ),
    status="alpha",
    scope="country-specific",
    group="listings",
)

LMA_V2 = ApiDomain(
    label="LMA v2",
    name="Listing Monitoring Authority",
    root_path="/api/lma/v2",
    title="SDEP - Listing Monitoring Authority (LMA) API",
    description=(
        "Read-only endpoints for the listing monitoring authority to view all "
        "listings (random checks) in every lifecycle status, and to view platforms, "
        "competent authorities and areas."
    ),
    status="alpha",
    scope="country-specific",
    group="listings",
)

AMA_V1 = ApiDomain(
    label="AMA v1",
    name="Activity Monitoring Authority",
    root_path="/api/ama/v1",
    title="SDEP - Activity Monitoring Authority (AMA) API",
    description=(
        "Read-only endpoints for the activity monitoring authority to view all "
        "registered activity data, platforms, competent authorities and areas."
    ),
    status="stable",
    scope="country-specific",
    group="activities",
)

STA_V1 = ApiDomain(
    label="STA v1",
    name="Statistics Authority",
    root_path="/api/sta/v1",
    title="SDEP - Statistics Authority (STA) API",
    description=(
        "Read-only endpoints for the statistics authority to view all "
        "registered activity data, platforms, competent authorities and areas."
    ),
    status="stable",
    scope="country-specific",
    group="activities",
    superseded_by_path="/api/sta/v2",
)

STA_V2 = ApiDomain(
    label="STA v2",
    name="Statistics Authority",
    root_path="/api/sta/v2",
    title="SDEP - Statistics Authority (STA) API",
    description=(
        "Read-only endpoints for the statistics authority to view all "
        "registered activity data, all listings (random checks), platforms, "
        "competent authorities and areas."
    ),
    status="alpha",
    scope="country-specific",
    group="listings",
    supersedes_path="/api/sta/v1",
    changes=(
        "adds `GET /listings` and `GET /listings/count` (all listings in every "
        "lifecycle status, random checks); no other changes."
    ),
    diff_url=VERSION_DIFF_URL,
)

API_DOMAINS = (
    AUTH_V1,
    CA_V1,
    CA_V2,
    STR_V1,
    STR_V2,
    LSA_V2,
    LMA_V2,
    AMA_V1,
    STA_V1,
    STA_V2,
)


def is_served(domain: ApiDomain) -> bool:
    """Whether this deployment serves the version: alpha only with API_ALPHA_ENABLED.

    Read at call time, so the mounts (app/main.py) and the landing page agree.
    """
    return domain.status != "alpha" or settings.API_ALPHA_ENABLED


def served_api_domains() -> tuple[ApiDomain, ...]:
    return tuple(domain for domain in API_DOMAINS if is_served(domain))


def _resolve(root_path: str | None) -> ApiDomain | None:
    """Look up a sibling domain by root path (lazy - API_DOMAINS is defined above)."""
    if root_path is None:
        return None

    return next(
        (domain for domain in API_DOMAINS if domain.root_path == root_path), None
    )
