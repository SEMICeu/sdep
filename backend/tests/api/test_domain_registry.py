"""Tests for the cross-version metadata in the API domain registry."""

import re

import pytest
from app.api.domain_registry import (
    AMA_V1,
    API_DOMAINS,
    API_GROUPS,
    API_SCOPES,
    CA_V1,
    CA_V2,
    OAS_VERSION,
    STA_V1,
    STA_V2,
    STR_V2,
    ApiDomain,
)
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.config import settings
from app.main import app
from httpx import ASGITransport, AsyncClient

from tests.api.test_openapi_schema_frozen import DOMAIN_STATUS_APPS


class TestUriVersion:
    """Dutch Government API Design Rules `/core/uri-version` (docs/API_TECH.md "Design"): the
    OpenAPI `servers[].url` carries the major version only, prefixed with `v`. FastAPI
    injects it from the sub-app root path at request time, so it is checked on the served
    document, not on the frozen snapshots."""

    @pytest.mark.asyncio
    async def test_every_version_serves_its_root_path_as_server_url(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for domain in API_DOMAINS:
                response = await client.get(domain.openapi_path)

                assert response.status_code == 200, domain.label
                servers = response.json()["servers"]
                assert servers == [{"url": domain.root_path}], domain.label
                assert re.fullmatch(r"/api/[a-z]+/v[1-9]\d*", servers[0]["url"]), (
                    domain.label
                )


class TestTrailingSlash:
    """NLgov `/core/no-trailing-slash`: a trailing slash is a 404, not a redirect. The
    frozen v1 contracts keep the redirect they were released with (registry flag)."""

    @pytest.mark.asyncio
    async def test_trailing_slash_is_404_except_on_frozen_v1(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for domain in API_DOMAINS:
                response = await client.get(f"{domain.openapi_path}/")

                expected = 307 if domain.redirect_slashes else 404
                assert response.status_code == expected, domain.label

    def test_only_the_frozen_v1_contracts_keep_the_redirect(self) -> None:
        keeping = {d.label for d in API_DOMAINS if d.redirect_slashes}

        assert keeping == {"Auth v1", "CA v1", "STR v1"}
        assert all(d.status == "stable" for d in API_DOMAINS if d.redirect_slashes)


class TestContact:
    """NLgov `/core/doc-openapi-contact`: name, url and email in every document."""

    def test_every_version_publishes_the_contact(self) -> None:
        for domain, domain_app in DOMAIN_STATUS_APPS:
            contact = domain_app.openapi()["info"]["contact"]

            assert contact == settings.api_contact, domain.label
            assert set(contact) == {"name", "url", "email"}


class TestCrossVersionLinks:
    """Version links resolve to the sibling entry, so labels are never duplicated."""

    def test_successor_and_predecessor_resolve_to_each_other(self) -> None:
        assert CA_V1.superseded_by is CA_V2
        assert CA_V2.supersedes is CA_V1
        assert STA_V1.superseded_by is STA_V2
        assert STA_V2.supersedes is STA_V1

    def test_unlinked_domain_has_no_version_note(self) -> None:
        assert AMA_V1.superseded_by is None
        assert AMA_V1.version_note == ""

    def test_successor_status_is_read_from_the_successor(self) -> None:
        """Promoting v2 to stable must update v1's note without editing v1."""
        assert CA_V1.version_note == f"Superseded by CA v2 ({CA_V2.status})."

    def test_missing_link_target_degrades_to_no_note(self) -> None:
        orphan = ApiDomain(
            label="X v9",
            name="X",
            root_path="/api/x/v9",
            title="X",
            description="X.",
            status="beta",
            scope="country-specific",
            group="listings",
            superseded_by_path="/api/x/v10",
        )

        assert orphan.superseded_by is None
        assert orphan.version_note == ""


class TestServedDescriptions:
    """The note reaches the served contract, which is what Swagger UI renders."""

    def test_superseded_version_points_at_its_successor(self) -> None:
        description = app_ca_v1.openapi()["info"]["description"]

        assert description.endswith("Status: stable. Superseded by CA v2 (alpha).")

    def test_new_version_summarizes_what_it_changes(self) -> None:
        description = app_ca_v2.openapi()["info"]["description"]

        assert (
            "Status: alpha. Changes from CA v1: the activity response documents "
            "the field maximums" in description
        )
        assert description.endswith("no other changes.")


class TestVersionDiffLink:
    """The diff describes what the newer version changes, so only that version links it."""

    def test_only_the_superseding_version_links_the_diff(self) -> None:
        linked = [domain.label for domain in API_DOMAINS if domain.diff_url]

        assert linked == [CA_V2.label, STR_V2.label, STA_V2.label]

    def test_superseded_version_does_not_link_the_diff(self) -> None:
        assert CA_V1.diff_url is None
        assert "Version diff" not in CA_V1.html


class TestBadgeConstants:
    """The badge values shown on the landing page must match what the sub-apps serve."""

    def test_version_label_matches_the_served_contract(self) -> None:
        assert app_ca_v2.openapi()["info"]["version"] == settings.api_version

    def test_oas_version_matches_the_served_specification_version(self) -> None:
        assert app_ca_v1.openapi()["openapi"].startswith(f"{OAS_VERSION}.")

    def test_domain_rows_carry_no_badges(self) -> None:
        """Both values are the same for every domain, so they are shown once in the header."""
        for domain in API_DOMAINS:
            assert "badge" not in domain.html


class TestNames:
    """The landing page one-liner is the acronym spelled out (see docs/DEFINITIONS.md)."""

    def test_acronym_is_the_first_word_of_the_label(self) -> None:
        assert STR_V2.acronym == "STR"
        assert {domain.acronym for domain in API_DOMAINS} == {
            "AMA",
            "Auth",
            "CA",
            "LMA",
            "LSA",
            "STA",
            "STR",
        }

    def test_versions_of_one_domain_share_the_name(self) -> None:
        by_acronym: dict[str, set[str]] = {}
        for domain in API_DOMAINS:
            by_acronym.setdefault(domain.acronym, set()).add(domain.name)

        assert all(len(names) == 1 for names in by_acronym.values()), by_acronym


class TestScopes:
    """Auth and STR are EU-harmonized; the other domains are national guidance (SDEP-NL)."""

    def test_domains_are_assigned_to_the_expected_scope(self) -> None:
        by_scope = {
            scope: {d.label for d in API_DOMAINS if d.scope == scope}
            for scope, _, _ in API_SCOPES
        }

        assert by_scope == {
            "eu-harmonized": {"Auth v1", "STR v1", "STR v2"},
            "country-specific": {
                "CA v1",
                "CA v2",
                "LSA v2",
                "LMA v2",
                "AMA v1",
                "STA v1",
                "STA v2",
            },
        }

    def test_every_domain_version_has_a_landing_page_group(self) -> None:
        known = {group for group, _ in API_GROUPS}

        assert {domain.group for domain in API_DOMAINS} == known

    def test_domains_are_assigned_to_the_expected_landing_page_group(self) -> None:
        by_group = {
            group: {d.label for d in API_DOMAINS if d.group == group}
            for group, _ in API_GROUPS
        }

        assert by_group == {
            "authentication": {"Auth v1"},
            "activities": {"CA v1", "STR v1", "AMA v1", "STA v1"},
            "listings": {"CA v2", "STR v2", "LSA v2", "LMA v2", "STA v2"},
        }

    def test_landing_page_group_heading_names_the_major_version(self) -> None:
        for group, heading in API_GROUPS:
            majors = {d.major for d in API_DOMAINS if d.group == group}

            assert {int(heading.split()[0].removeprefix("v"))} == majors, heading

    def test_every_domain_scope_has_a_landing_page_group(self) -> None:
        known = {scope for scope, _, _ in API_SCOPES}

        assert {domain.scope for domain in API_DOMAINS} <= known
