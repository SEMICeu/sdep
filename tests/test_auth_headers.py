#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///

# Test security headers on SDEP API endpoints (XSS protection, output encoding,
# OWASP security headers compliance).
# Expects BACKEND_BASE_URL environment variable to be set.
# Optionally accepts API_VERSION environment variable (defaults to v1).

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

import httpx


# OWASP headers checked on every endpoint: (name, expected substring or "" for
# presence-only).
OWASP_HEADERS = (
    ("Content-Security-Policy", ""),
    ("X-Frame-Options", "DENY"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", ""),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Cross-Origin-Embedder-Policy", "require-corp"),
)


@dataclass
class TestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is not set")
        sys.exit(1)
    return value


def get_headers(client: httpx.Client, base_url: str, endpoint: str) -> httpx.Headers:
    return client.get(f"{base_url}{endpoint}").headers


def check_header(
    stats: TestStats,
    headers: httpx.Headers,
    header_name: str,
    expected_value: str,
) -> None:
    stats.total += 1
    if header_name in headers:
        actual_value = headers[header_name]
        # Value match is case-sensitive, mirroring the original `grep -q`.
        if expected_value and expected_value not in actual_value:
            print(f"  {header_name}: Expected '{expected_value}', got '{actual_value}' FAIL")
            stats.failed += 1
        else:
            print(f"  {header_name}: {actual_value} OK")
            stats.passed += 1
    else:
        print(f"  {header_name}: MISSING FAIL")
        stats.failed += 1


def test_endpoint_headers(
    client: httpx.Client,
    stats: TestStats,
    base_url: str,
    endpoint: str,
    description: str,
) -> None:
    print("------------------------------------------------")
    print(f"Testing: {description}")
    print(f"   Endpoint: {endpoint}")
    print()
    print("Security Headers:")
    headers = get_headers(client, base_url, endpoint)
    for name, expected in OWASP_HEADERS:
        check_header(stats, headers, name, expected)
    print()


def test_csp_policy(client: httpx.Client, stats: TestStats, base_url: str, endpoint: str) -> None:
    print("------------------------------------------------")
    print("Testing CSP Policy Details")
    print(f"   Endpoint: {endpoint}")
    print()

    csp = get_headers(client, base_url, endpoint).get("Content-Security-Policy", "")

    if not csp:
        print("  CSP header not found")
        stats.total += 5
        stats.failed += 5
        return

    print("CSP Policy:")
    for directive in csp.split(";"):
        print(f"  {directive.strip()}")
    print()

    print("CSP Directives Check:")

    checks = (
        ("default-src 'self'", "default-src 'self' (only same-origin resources)", "default-src 'self' missing or incorrect"),
        (None, "script-src allows cdn.jsdelivr.net (for Swagger UI)", "script-src may not allow Swagger UI CDN"),
        ("frame-ancestors 'none'", "frame-ancestors 'none' (clickjacking protection)", "frame-ancestors 'none' missing"),
        ("object-src 'none'", "object-src 'none' (blocks object/embed XSS)", "object-src 'none' missing"),
    )

    # default-src
    needle, ok_msg, fail_msg = checks[0]
    stats.total += 1
    if needle in csp:
        print(f"  {ok_msg} OK")
        stats.passed += 1
    else:
        print(f"  {fail_msg} FAIL")
        stats.failed += 1

    # script-src CDN (regex, like the original `grep "script-src.*cdn.jsdelivr.net"`)
    _needle, ok_msg, fail_msg = checks[1]
    stats.total += 1
    if re.search(r"script-src.*cdn\.jsdelivr\.net", csp):
        print(f"  {ok_msg} OK")
        stats.passed += 1
    else:
        print(f"  {fail_msg} FAIL")
        stats.failed += 1

    # frame-ancestors and object-src
    for needle, ok_msg, fail_msg in checks[2:]:
        stats.total += 1
        if needle in csp:
            print(f"  {ok_msg} OK")
            stats.passed += 1
        else:
            print(f"  {fail_msg} FAIL")
            stats.failed += 1

    # unsafe-eval must be ABSENT
    stats.total += 1
    if "'unsafe-eval'" in csp:
        print("  'unsafe-eval' present (XSS risk!) FAIL")
        stats.failed += 1
    else:
        print("  'unsafe-eval' not present (good XSS protection) OK")
        stats.passed += 1

    print()


def test_sensitive_endpoint_caching(
    client: httpx.Client,
    stats: TestStats,
    base_url: str,
    endpoint: str,
    description: str,
) -> None:
    print("------------------------------------------------")
    print(f"Testing Cache Control: {description}")
    print(f"   Endpoint: {endpoint}")
    print()

    headers = get_headers(client, base_url, endpoint)

    # Soft checks: they count toward the total and may pass, but a miss is NOT a
    # failure (some endpoints may not need strict caching). Preserves the original
    # behaviour where total can exceed passed+failed.
    stats.total += 1
    if "no-store" in headers.get("Cache-Control", "").lower():
        print("  Cache-Control contains 'no-store' OK")
        stats.passed += 1
    else:
        print("  Cache-Control may not prevent caching")

    stats.total += 1
    if "no-cache" in headers.get("Pragma", "").lower():
        print("  Pragma: no-cache present OK")
        stats.passed += 1
    else:
        print("  Pragma: no-cache may be missing")

    print()


def main() -> int:
    base_url = env("BACKEND_BASE_URL")
    api_version = os.getenv("API_VERSION", "v1")

    print(f"Testing security headers at: {base_url}")
    print(
        f"Testing endpoints: /, /api/health, /api/ping, /api/ca/{api_version}/openapi.json"
    )
    print()

    stats = TestStats()

    print("========================================")
    print("SDEP Security Headers Test Suite")
    print("========================================")
    print()

    with httpx.Client(timeout=30.0) as client:
        test_endpoint_headers(client, stats, base_url, "/", "Root endpoint")
        test_endpoint_headers(client, stats, base_url, "/api/health", "Health check endpoint")
        test_endpoint_headers(
            client, stats, base_url, "/api/ping", "API ping endpoint (may be auth-protected)"
        )
        test_endpoint_headers(
            client,
            stats,
            base_url,
            f"/api/ca/{api_version}/openapi.json",
            "OpenAPI schema endpoint",
        )

        test_csp_policy(client, stats, base_url, f"/api/ca/{api_version}/docs")

        test_sensitive_endpoint_caching(
            client, stats, base_url, f"/api/ca/{api_version}/openapi.json", "OpenAPI schema"
        )

        # HSTS is set by the application itself (main.py enables it on
        # SecurityHeadersMiddleware), as defense in depth next to any header the
        # reverse proxy sets. A missing header is therefore a failure.
        print("------------------------------------------------")
        print("HSTS Check (set by the application as defense in depth)")
        print()
        ping_headers = get_headers(client, base_url, "/api/ping")
        check_header(stats, ping_headers, "Strict-Transport-Security", "max-age=")
        check_header(stats, ping_headers, "Strict-Transport-Security", "includeSubDomains")
        print()

    print("========================================")
    print("Test Summary (security headers):")
    print(f"  Total:  {stats.total}")
    print(f"  Passed: {stats.passed} OK")
    print(f"  Failed: {stats.failed} FAIL")
    print("========================================")

    if stats.failed == 0:
        print("All security header tests passed!")
        return 0

    print("Some security header tests failed!")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
