#!/bin/bash

# Smoke test for audit-excluded endpoints (SKIP_PATHS).
# These endpoints are safe for production: read-only, no authentication, no test data.
# Expects BACKEND_BASE_URL environment variable to be set.
# Keep in sync with SKIP_PATHS in backend/app/security/audit.py
# (guarded by test_skip_paths_are_complete in backend/tests/security/test_audit.py).

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

echo "🔍 Smoke testing audit-excluded endpoints at: ${BACKEND_BASE_URL}"
echo

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

ENDPOINTS=(
    "/"
    "/api/docs"
    "/api/health"
    "/api/auth/v1/openapi.json"
    "/api/auth/v1/docs"
    "/api/ca/v1/openapi.json"
    "/api/ca/v1/docs"
    "/api/str/v1/openapi.json"
    "/api/str/v1/docs"
)

for endpoint in "${ENDPOINTS[@]}"; do
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_BASE_URL}${endpoint}")

    if [ "$http_code" -eq 200 ]; then
        echo "✅ GET $endpoint — $http_code"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ GET $endpoint — $http_code (expected 200)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
done

echo
echo "═══════════════════════════════════════"
echo "Test Summary:"
echo "  Total:  $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS ✅"
echo "  Failed: $FAILED_TESTS ❌"
echo "═══════════════════════════════════════"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All smoke test endpoints passed!"
    exit 0
else
    echo "❌ Some smoke test endpoints failed!"
    exit 1
fi
