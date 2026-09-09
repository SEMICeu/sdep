"""Tests for the cross-version metadata in the API domain registry."""

from app.api.domain_registry import (
    API_DOMAINS,
    API_SCOPES,
    CA_V1,
    CA_V2,
    OAS_VERSION,
    REP_V1,
    ApiDomain,
)
from app.api.domains.ca.v1 import app_ca_v1
from app.api.domains.ca.v2 import app_ca_v2
from app.config import settings


class TestCrossVersionLinks:
    """Version links resolve to the sibling entry, so labels are never duplicated."""

    def test_successor_and_predecessor_resolve_to_each_other(self) -> None:
        assert CA_V1.superseded_by is CA_V2
        assert CA_V2.supersedes is CA_V1

    def test_unlinked_domain_has_no_version_note(self) -> None:
        assert REP_V1.superseded_by is None
        assert REP_V1.version_note == ""

    def test_successor_status_is_read_from_the_successor(self) -> None:
        """Promoting v2 to stable must update v1's note without editing v1."""
        assert CA_V1.version_note == f"Superseded by CA v2 ({CA_V2.status})."

    def test_missing_link_target_degrades_to_no_note(self) -> None:
        orphan = ApiDomain(
            label="X v9",
            root_path="/api/x/v9",
            title="X",
            description="X.",
            status="beta",
            scope="country-specific",
            superseded_by_path="/api/x/v10",
        )

        assert orphan.superseded_by is None
        assert orphan.version_note == ""


class TestServedDescriptions:
    """The note reaches the served contract, which is what Swagger UI renders."""

    def test_superseded_version_points_at_its_successor(self) -> None:
        description = app_ca_v1.openapi()["info"]["description"]

        assert description.endswith("Status: stable. Superseded by CA v2 (beta).")

    def test_new_version_summarizes_what_it_changes(self) -> None:
        description = app_ca_v2.openapi()["info"]["description"]

        assert (
            "Status: beta. Changes from CA v1: adds four optional activity filters"
            in description
        )
        assert "`createdAtFrom`" in description
        assert description.endswith("no other changes.")


class TestVersionDiffLink:
    """The diff describes what the newer version changes, so only that version links it."""

    def test_only_the_superseding_version_links_the_diff(self) -> None:
        linked = [domain.label for domain in API_DOMAINS if domain.diff_url]

        assert linked == [CA_V2.label]

    def test_superseded_version_does_not_link_the_diff(self) -> None:
        assert CA_V1.diff_url is None
        assert "Version diff" not in CA_V1.html


class TestBadgeConstants:
    """The badge values shown on the landing page must match what the sub-apps serve."""

    def test_version_label_matches_the_served_contract(self) -> None:
        assert app_ca_v2.openapi()["info"]["version"] == settings.api_version_label

    def test_oas_version_matches_the_served_specification_version(self) -> None:
        assert app_ca_v1.openapi()["openapi"].startswith(f"{OAS_VERSION}.")

    def test_domain_rows_carry_no_badges(self) -> None:
        """Both values are the same for every domain, so they are shown once in the header."""
        for domain in API_DOMAINS:
            assert "badge" not in domain.html


class TestScopes:
    """Auth and STR are EU-harmonized; CA and REP are national guidance (SDEP-NL)."""

    def test_domains_are_assigned_to_the_expected_scope(self) -> None:
        by_scope = {
            scope: {d.label for d in API_DOMAINS if d.scope == scope}
            for scope, _, _ in API_SCOPES
        }

        assert by_scope == {
            "eu-harmonized": {"Auth v1", "STR v1"},
            "country-specific": {"CA v1", "CA v2", "REP v1"},
        }

    def test_every_domain_scope_has_a_landing_page_group(self) -> None:
        known = {scope for scope, _, _ in API_SCOPES}

        assert {domain.scope for domain in API_DOMAINS} <= known
