#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///
"""Tenant isolation: two CAs and two platforms attack each other's records.

Each side gets real areas, activities and listings, then tries to read and change the
records of the other side. Read-only clients compare the victim's records before and
after. Also checks that every API refuses the other roles.

The suite has no client: this test logs in as all its parties by itself, with the
<CLIENT>_CLIENT_ID and _CLIENT_SECRET variables that both runners export.
"""

from __future__ import annotations

import collections
import datetime as dt
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SHAPEFILE_PATH = REPO_ROOT / "test-data" / "shapefiles" / "Amsterdam.zip"
AUTH_API_VERSION = "v1"
PAGE_LIMIT = 1000
# Bearer tokens live 300 seconds on the deployed environments: renew well before that.
TOKEN_MAX_AGE_SECONDS = 200

ADDRESS = {
    "thoroughfare": "Prinsengracht",
    "locatorDesignatorNumber": 263,
    "postCode": "1016GV",
    "postName": "Amsterdam",
    "fullAddress": "Prinsengracht 263, 1016GV Amsterdam",
}

# Audience -> a read that only this audience may call.
READS = {
    "ca": "/api/ca/v2/areas",
    "str": "/api/str/v2/listings",
    "sta": "/api/sta/v2/listings",
    "ama": "/api/ama/v1/activities",
    "lma": "/api/lma/v2/listings",
    "lsa": "/api/lsa/v2/listings",
}

# Audience -> writes that only this audience may call. The batches are empty: a request
# that wrongly passes the role check gets 422 and stores nothing, so the test still fails.
WRITES = {
    "str": [
        ("/api/str/v2/listings/bulk", {"listings": []}),
        ("/api/str/v2/activities/bulk", {"activities": []}),
        ("/api/str/v2/listing-acknowledgements/bulk", {"acknowledgements": []}),
    ],
    "lsa": [("/api/lsa/v2/listing-screenings/bulk", {"screenings": []})],
}


def as_uuid(name: str) -> str:
    """Return the UUIDv5 of a readable test name: a new functional ID must be a UUID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is not set")
        sys.exit(1)
    return value


class Party:
    """One logged-in client, renews its own bearer token."""

    def __init__(self, http: httpx.Client, base_url: str, client: str) -> None:
        self.http = http
        self.base_url = base_url
        self.client_id = env(f"{client}_CLIENT_ID")
        self.client_secret = env(f"{client}_CLIENT_SECRET")
        self.bearer = ""
        self.logged_in_at = 0.0

    def token(self) -> str:
        if time.time() - self.logged_in_at > TOKEN_MAX_AGE_SECONDS:
            response = self.http.post(
                f"{self.base_url}/api/auth/{AUTH_API_VERSION}/token",
                data={"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret},
            )
            if response.status_code != 200:
                print(f"ERROR: Login failed for {self.client_id} (HTTP {response.status_code})", file=sys.stderr)
                sys.exit(1)
            self.bearer = response.json()["access_token"]
            self.logged_in_at = time.time()
        return self.bearer

    def call(self, method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
        response = self.http.request(method, f"{self.base_url}{path}", headers={"Authorization": f"Bearer {self.token()}"}, **kwargs)
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, {}

    def records(self, path: str, key: str, **filters: Any) -> dict[str, dict[str, Any]]:
        """All pages of a list, by functional ID. Anything but 200 stops the test, so a refused read never counts as "no records"."""
        found: dict[str, dict[str, Any]] = {}
        while True:
            code, body = self.call("GET", path, params={**filters, "limit": PAGE_LIMIT, "offset": len(found)})
            if code != 200:
                print(f"ERROR: GET {path} returned HTTP {code}", file=sys.stderr)
                sys.exit(1)
            page = next((value for value in body.values() if isinstance(value, list)), [])
            found.update({item[key]: item for item in page})
            if len(page) < PAGE_LIMIT:
                return found


@dataclass
class Stats:
    total: int = 0
    passed: int = 0
    failed: int = 0

    def check(self, ok: bool, label: str, detail: Any = "") -> None:
        self.total += 1
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{'OK  ' if ok else 'FAIL'} {label} {detail}".rstrip())


@dataclass
class World:
    """The records of both sides, and their public IDs."""

    stamp: int
    area_1_listing: str
    area_1_activity: str
    area_2_listing: str
    area_2_activity: str
    ca_id_1: str
    ca_id_2: str
    platform_id_1: str
    platform_id_2: str
    activity_1: str
    activity_2: str
    flagged_1: str
    acknowledged_1: str
    pending_1: str
    flagged_2: str
    acknowledged_2: str
    batch_mate_2: str
    versions: dict[str, str]


def setup_failed(step: str, code: int, body: Any) -> None:
    print(f"ERROR: Setup failed at {step} (HTTP {code}): {str(body)[:300]}", file=sys.stderr)
    sys.exit(1)


def post_area(party: Party, area_id: str, regulation: str, **extra: str) -> tuple[int, Any]:
    with SHAPEFILE_PATH.open("rb") as shapefile:
        return party.call(
            "POST",
            "/api/ca/v2/areas",
            data={"areaId": area_id, "regulation": regulation, **extra},
            files={"file": ("Amsterdam.zip", shapefile, "application/zip")},
        )


def listing(listing_id: str, area_id: str, **overrides: Any) -> dict[str, Any]:
    item = {"listingId": listing_id, "areaId": area_id, "url": f"http://sdep-test.example.com/{listing_id}", "address": ADDRESS, "declaredAsShortTermRental": True}
    return {**item, **overrides}


def activity(activity_id: str, area_id: str, **overrides: Any) -> dict[str, Any]:
    start = dt.datetime.now(dt.UTC)
    end = start + dt.timedelta(hours=1)
    item = {
        "activityId": activity_id,
        "url": f"http://sdep-test.example.com/{activity_id}",
        "registrationNumber": "REGISO1",
        "address": ADDRESS,
        "temporal": {"startDatetime": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "endDatetime": end.strftime("%Y-%m-%dT%H:%M:%SZ")},
        "areaId": area_id,
        "numberOfGuests": 2,
        "countryOfGuests": ["NLD", "NLD"],
    }
    return {**item, **overrides}


def error_types(body: Any) -> list[str | None]:
    results = body.get("results", []) if isinstance(body, dict) else []
    return [((r.get("errors") or {}).get("detail") or [{}])[0].get("type") for r in results]


def build_world(ca1: Party, ca2: Party, str1: Party, str2: Party, lsa: Party) -> World:
    """Give both sides areas, an activity and listings in every status an attacker could target."""
    stamp = int(time.time() * 1000)

    def new_id(name: str) -> str:
        return as_uuid(f"sdep-test-iso-{name}-{stamp}")

    area_1_listing, area_1_activity = new_id("ca1-listing"), new_id("ca1-activity")
    area_2_listing, area_2_activity = new_id("ca2-listing"), new_id("ca2-activity")
    for party, area_id, regulation in (
        (ca1, area_1_listing, "listing"),
        (ca1, area_1_activity, "activity"),
        (ca2, area_2_listing, "listing"),
        (ca2, area_2_activity, "activity"),
    ):
        code, body = post_area(party, area_id, regulation)
        if code != 201:
            setup_failed(f"area {area_id}", code, body)

    activity_1, activity_2 = new_id("activity-1"), new_id("activity-2")
    for party, activity_id, area_id in ((str1, activity_1, area_1_activity), (str2, activity_2, area_2_activity)):
        code, body = party.call("POST", "/api/str/v2/activities/bulk", json={"activities": [activity(activity_id, area_id)]})
        if code != 201:
            setup_failed(f"activity {activity_id}", code, body)

    flagged_1, acknowledged_1, pending_1 = new_id("flagged-1"), new_id("acknowledged-1"), new_id("pending-1")
    flagged_2, acknowledged_2, batch_mate_2 = new_id("flagged-2"), new_id("acknowledged-2"), new_id("batch-mate-2")
    submitted: dict[str, dict[str, Any]] = {}
    for party, area_id, ids in (
        (str1, area_1_listing, [flagged_1, acknowledged_1, pending_1]),
        (str2, area_2_listing, [flagged_2, acknowledged_2, batch_mate_2]),
    ):
        code, body = party.call("POST", "/api/str/v2/listings/bulk", json={"listings": [listing(i, area_id) for i in ids]})
        if code != 201:
            setup_failed("listings", code, body)
        submitted |= {r["listingId"]: r["listing"] for r in body["results"]}
    platform_id_1, platform_id_2 = submitted[flagged_1]["platformId"], submitted[flagged_2]["platformId"]

    for platform_id, ids in ((platform_id_1, [flagged_1, acknowledged_1]), (platform_id_2, [flagged_2, acknowledged_2, batch_mate_2])):
        screenings = [{"platformId": platform_id, "listingId": i, "createdAt": submitted[i]["createdAt"], "flags": ["UNK"]} for i in ids]
        code, body = lsa.call("POST", "/api/lsa/v2/listing-screenings/bulk", json={"screenings": screenings})
        if code != 201:
            setup_failed("screenings", code, body)
        submitted |= {r["listingId"]: r["listing"] for r in body["results"]}

    for party, listing_id in ((str1, acknowledged_1), (str2, acknowledged_2)):
        acknowledgement = {"listingId": listing_id, "createdAt": submitted[listing_id]["createdAt"]}
        code, body = party.call("POST", "/api/str/v2/listing-acknowledgements/bulk", json={"acknowledgements": [acknowledgement]})
        if code != 201:
            setup_failed("acknowledgement", code, body)

    ca_id_1 = ca1.records("/api/ca/v2/areas", "areaId")[area_1_listing]["competentAuthorityId"]
    ca_id_2 = ca2.records("/api/ca/v2/areas", "areaId")[area_2_listing]["competentAuthorityId"]
    if ca_id_1 == ca_id_2 or platform_id_1 == platform_id_2:
        print("ERROR: Both sides are the same party, check the test clients", file=sys.stderr)
        sys.exit(1)
    return World(
        stamp, area_1_listing, area_1_activity, area_2_listing, area_2_activity, ca_id_1, ca_id_2, platform_id_1, platform_id_2,
        activity_1, activity_2, flagged_1, acknowledged_1, pending_1, flagged_2, acknowledged_2, batch_mate_2,
        {key: value["createdAt"] for key, value in submitted.items()},
    )  # fmt: skip


def test_owners_see_own_data(stats: Stats, w: World, ca1: Party, ca2: Party, str1: Party, str2: Party, lma: Party) -> None:
    """Control: without this, every "0 records" below could also mean a broken test."""
    print("Test 1: Owners see their own data")
    stats.check(w.flagged_1 in str1.records("/api/str/v2/listings", "listingId"), "STR1 reads its flagged listing")
    stats.check(w.flagged_2 in str2.records("/api/str/v2/listings", "listingId"), "STR2 reads its flagged listing")
    stats.check(w.activity_1 in ca1.records("/api/ca/v2/activities", "activityId", areaId=w.area_1_activity), "CA1 reads the activity in its area")
    stats.check(w.activity_2 in ca2.records("/api/ca/v2/activities", "activityId", areaId=w.area_2_activity), "CA2 reads the activity in its area")
    stats.check(w.acknowledged_1 in ca1.records("/api/ca/v2/listings", "listingId", areaId=w.area_1_listing), "CA1 reads the acknowledged listing")
    stats.check(len(lma.records("/api/lma/v2/listings", "listingId", areaId=w.area_1_listing)) == 3, "LMA reads all 3 listings of STR1")
    print()


def test_reads_across_parties(stats: Stats, w: World, ca1: Party, ca2: Party, str2: Party) -> None:
    print("Test 2: A party reads nothing of the other party")
    own = str2.records("/api/str/v2/listings", "listingId")
    stats.check(all(i["platformId"] == w.platform_id_2 for i in own.values()), "STR2 list holds its own platform only", f"({len(own)} items)")
    for name, filters in (("areaId", {"areaId": w.area_1_listing}), ("competentAuthorityId", {"competentAuthorityId": w.ca_id_1})):
        found = str2.records("/api/str/v2/listings", "listingId", **filters)
        code, count = str2.call("GET", "/api/str/v2/listings/count", params=filters)
        stats.check(not found and code == 200 and count.get("count") == 0, f"STR2 filter on {name} of the other side", f"({len(found)} items)")
    # platformId is not a filter on STR: a forged value must not widen the fixed scope.
    found = str2.records("/api/str/v2/listings", "listingId", platformId=w.platform_id_1)
    stats.check(all(i["platformId"] == w.platform_id_2 for i in found.values()), "STR2 forged platformId is ignored")

    for version in ("v1", "v2"):
        found = ca2.records(f"/api/ca/{version}/activities", "activityId")
        stats.check(all(i["competentAuthorityId"] == w.ca_id_2 for i in found.values()), f"CA2 {version} activities hold its own CA only", f"({len(found)} items)")
        code, _ = ca2.call("GET", f"/api/ca/{version}/areas/{w.area_1_listing}")
        stats.check(code == 404, f"CA2 {version} reads an area of CA1", f"(HTTP {code})")
    for path, key, record, area in (
        ("/api/ca/v2/activities", "activityId", w.activity_1, w.area_1_activity),
        ("/api/ca/v2/listings", "listingId", w.acknowledged_1, w.area_1_listing),
    ):
        for filters in ({"areaId": area}, {"platformId": w.platform_id_1}):
            found = ca2.records(path, key, **filters)
            stats.check(record not in found, f"CA2 filter on {path} {next(iter(filters))}", f"({len(found)} items)")
    found = ca2.records("/api/ca/v2/listings", "listingId")
    stats.check(all(i["competentAuthorityId"] == w.ca_id_2 for i in found.values()), "CA2 listings hold its own areas only", f"({len(found)} items)")
    found = ca2.records("/api/ca/v2/areas", "areaId")
    stats.check(all(i["competentAuthorityId"] == w.ca_id_2 for i in found.values()), "CA2 areas hold its own areas only", f"({len(found)} items)")
    found = ca1.records("/api/ca/v2/listings", "listingId", areaId=w.area_1_listing)
    stats.check(set(found) == {w.acknowledged_1}, "CA1 reads no pending or flagged listing", f"({len(found)} items)")
    print()


def test_writes_across_parties(stats: Stats, w: World, ca2: Party, str2: Party, lsa: Party) -> None:
    print("Test 3: A party changes nothing of the other party")
    code, _ = post_area(ca2, w.area_1_listing, "activity")
    stats.check(code == 409, "CA2 reuses an areaId of CA1", f"(HTTP {code})")
    for version in ("v1", "v2"):
        code, _ = ca2.call("DELETE", f"/api/ca/{version}/areas/{w.area_1_listing}")
        stats.check(code == 404, f"CA2 {version} deletes an area of CA1", f"(HTTP {code})")
        hijack = activity(w.activity_1, w.area_2_activity, url="http://sdep-test.example.com/hijack")
        code, body = str2.call("POST", f"/api/str/{version}/activities/bulk", json={"activities": [hijack]})
        stats.check(code == 422 and error_types(body) == ["duplicate_error"], f"STR2 {version} overwrites an activity of STR1", f"(HTTP {code})")
    for listing_id in (w.pending_1, w.flagged_1, w.acknowledged_1):
        hijack = listing(listing_id, w.area_2_listing, url="http://sdep-test.example.com/hijack")
        code, body = str2.call("POST", "/api/str/v2/listings/bulk", json={"listings": [hijack]})
        stats.check(code == 422 and error_types(body) == ["duplicate_error"], "STR2 overwrites a listing of STR1", f"(HTTP {code})")

    other = {"listingId": w.flagged_1, "createdAt": w.versions[w.flagged_1]}
    own = {"listingId": w.batch_mate_2, "createdAt": w.versions[w.batch_mate_2]}
    code, body = str2.call("POST", "/api/str/v2/listing-acknowledgements/bulk", json={"acknowledgements": [other]})
    stats.check(code == 422 and error_types(body) == ["not_found_error"], "STR2 acknowledges a listing of STR1", f"(HTTP {code})")
    code, body = str2.call("POST", "/api/str/v2/listing-acknowledgements/bulk", json={"acknowledgements": [own, other]})
    stats.check(error_types(body) == [None, "not_found_error"], "STR2 hides that listing in a batch with its own", f"(HTTP {code})")

    screening = {"platformId": w.platform_id_2, "listingId": w.pending_1, "createdAt": w.versions[w.pending_1], "flags": ["UNK"]}
    code, body = lsa.call("POST", "/api/lsa/v2/listing-screenings/bulk", json={"screenings": [screening]})
    stats.check(code == 422 and error_types(body) == ["not_found_error"], "LSA screens a listing of STR1 under STR2", f"(HTTP {code})")
    print()


def test_forged_owner(stats: Stats, w: World, ca1: Party, ca2: Party, str1: Party, str2: Party, sta: Party, lma: Party) -> None:
    """The owner comes from the token: owner fields in a request change nothing."""
    print("Test 4: Forged owner fields in the request")
    forged = {"platformId": w.platform_id_1, "platformName": "forged", "clientId": str1.client_id, "competentAuthorityId": w.ca_id_1}
    listing_id, activity_id, area_id = as_uuid(f"sdep-test-iso-forged-l-{w.stamp}"), as_uuid(f"sdep-test-iso-forged-a-{w.stamp}"), as_uuid(f"sdep-test-iso-forged-area-{w.stamp}")

    code, _ = str2.call("POST", "/api/str/v2/listings/bulk", json={"listings": [listing(listing_id, w.area_2_listing, **forged)]})
    found = lma.records("/api/lma/v2/listings", "listingId", areaId=w.area_2_listing).get(listing_id)
    stats.check(code == 422 or bool(found and found["platformId"] == w.platform_id_2), "Listing keeps the platform of the token", f"(HTTP {code})")

    code, _ = str2.call("POST", "/api/str/v2/activities/bulk", json={"activities": [activity(activity_id, w.area_2_activity, **forged)]})
    found = sta.records("/api/sta/v2/activities", "activityId", areaId=w.area_2_activity).get(activity_id)
    stats.check(code == 422 or bool(found and found["platformId"] == w.platform_id_2), "Activity keeps the platform of the token", f"(HTTP {code})")

    code, _ = post_area(ca2, area_id, "listing", competentAuthorityId=w.ca_id_1, clientId=ca1.client_id)
    in_ca2, in_ca1 = area_id in ca2.records("/api/ca/v2/areas", "areaId"), area_id in ca1.records("/api/ca/v2/areas", "areaId")
    stats.check(code >= 400 or (in_ca2 and not in_ca1), "Area keeps the authority of the token", f"(HTTP {code})")
    print()


def test_roles(stats: Stats, w: World, parties: dict[str, Party]) -> None:
    print("Test 5: Every API refuses the other roles")
    wrong: list[Any] = []
    codes: collections.Counter[int] = collections.Counter()
    for audience, party in parties.items():
        for api, path in READS.items():
            code, _ = party.call("GET", path, params={"limit": 1})
            codes[code] += 1
            if code != (200 if audience == api else 403):
                wrong.append((audience, path, code))
    stats.check(not wrong, "Reads: 200 for the own audience, otherwise 403", f"({dict(codes)}) {wrong or ''}")

    wrong = []
    codes = collections.Counter()
    for audience, party in parties.items():
        attempts = [(path, body) for api, writes in WRITES.items() if api != audience for path, body in writes]
        for path, body in attempts:
            code, _ = party.call("POST", path, json=body)
            codes[code] += 1
            if code != 403:
                wrong.append((audience, path, code))
        if audience != "ca":
            for label, (code, _) in (
                ("POST area", post_area(party, as_uuid(f"sdep-test-iso-role-{audience}-{w.stamp}"), "listing")),
                ("DELETE area", party.call("DELETE", f"/api/ca/v2/areas/{w.area_1_listing}")),
            ):
                codes[code] += 1
                if code != 403:
                    wrong.append((audience, label, code))
    stats.check(not wrong, "Writes: 403 for every other audience", f"({dict(codes)}) {wrong or ''}")
    print()


def main() -> int:
    base_url = env("BACKEND_BASE_URL").rstrip("/")
    print(f"Testing tenant isolation at: {base_url}")
    print()
    stats = Stats()

    with httpx.Client(timeout=60.0) as http:
        ca1, ca2, str1, str2, sta, ama, lsa, lma = (Party(http, base_url, c) for c in ("CA1", "CA2", "STR", "STR2", "STA", "AMA", "LSA", "LMA"))
        w = build_world(ca1, ca2, str1, str2, lsa)
        print("Setup: 2 CAs, 2 platforms, 4 areas, 2 activities, 6 listings")
        print()

        def victim() -> tuple[Any, ...]:
            areas = str1.records("/api/str/v1/areas", "areaId")
            return (
                lma.records("/api/lma/v2/listings", "listingId", areaId=w.area_1_listing),
                sta.records("/api/sta/v2/activities", "activityId", areaId=w.area_1_activity),
                areas[w.area_1_listing],
                areas[w.area_1_activity],
            )

        test_owners_see_own_data(stats, w, ca1, ca2, str1, str2, lma)
        test_reads_across_parties(stats, w, ca1, ca2, str2)
        before = victim()
        test_writes_across_parties(stats, w, ca2, str2, lsa)
        test_forged_owner(stats, w, ca1, ca2, str1, str2, sta, lma)
        test_roles(stats, w, {"ca": ca1, "str": str1, "sta": sta, "ama": ama, "lma": lma, "lsa": lsa})

        print("Test 6: The records of the victim are unchanged")
        stats.check(victim() == before, "Listings, activity and areas of the victim are identical")
        code, _ = ca1.call("GET", f"/api/ca/v2/areas/{w.area_1_listing}")
        stats.check(code == 200, "CA1 still reads its area", f"(HTTP {code})")
        print()

    print("=======================================")
    print("Test Summary (tenant isolation):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("=======================================")
    if stats.failed == 0:
        print("All tenant isolation tests passed!")
        return 0
    print("Some tenant isolation tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
