#!/bin/bash

# Test script to verify all secured endpoints return 401 Unauthorized without authentication
# Expects BACKEND_BASE_URL environment variable to be set
# Tests both version-independent (/api) and versioned domain endpoints

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

echo "🔒 Testing unauthorized access to secured endpoints"
echo "🔍 Backend: ${BACKEND_BASE_URL}"
echo

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to test an endpoint expects 401
test_endpoint() {
    local method=$1
    local path=$2
    local description=$3

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Make request without authentication
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "${BACKEND_BASE_URL}${path}")

    if [ "$http_code" -eq 401 ]; then
        echo "✅ $method $path - Correctly returns 401 Unauthorized"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo "❌ $method $path - Expected 401 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Test all secured endpoints (excluding public endpoints like /api/health and /api/auth/v1/token)
echo "Testing secured endpoints without authentication..."
echo

# Version-independent common endpoints - None currently require authentication
# /api/health is public health check

# Secured endpoints (domain-first versioning)
echo "Testing secured endpoints..."
test_endpoint "GET" "/api/ping" "Ping endpoint (requires authentication)"
test_endpoint "GET" "/api/str/v1/areas" "STR areas retrieval"
test_endpoint "GET" "/api/str/v1/areas/count" "STR areas count"
test_endpoint "GET" "/api/str/v1/areas/amsterdam-area0363" "STR area retrieval by ID"
test_endpoint "POST" "/api/str/v1/activities/bulk" "STR bulk activity submission"
test_endpoint "POST" "/api/ca/v1/areas" "CA area submission"
test_endpoint "GET" "/api/ca/v1/areas" "CA own areas retrieval"
test_endpoint "GET" "/api/ca/v1/areas/count" "CA own areas count"
test_endpoint "GET" "/api/ca/v1/areas/some-area-id" "CA area retrieval by ID"
test_endpoint "DELETE" "/api/ca/v1/areas/some-area-id" "CA area deletion"
test_endpoint "GET" "/api/ca/v1/activities" "CA activity retrieval"
test_endpoint "GET" "/api/ca/v1/activities/count" "CA activity count"

# Summary
echo
echo "═══════════════════════════════════════"
echo "Test Summary:"
echo "  Total:  $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS ✅"
echo "  Failed: $FAILED_TESTS ❌"
echo "═══════════════════════════════════════"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All endpoints are properly secured!"
    exit 0
else
    echo "❌ Some endpoints are not properly secured!"
    exit 1
fi
