#!/bin/bash

# Test script for pinging the SDEP API endpoint
# Expects BACKEND_BASE_URL environment variable to be set
# Optionally accepts BEARER_TOKEN environment variable for authenticated requests
# Optionally accepts API_VERSION environment variable (defaults to v0)

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

# Default API version to v0 if not set
API_VERSION=${API_VERSION:-v0}

# If BEARER_TOKEN is not set, try to read from token file
if [ -z "$BEARER_TOKEN" ]; then
    TOKEN_FILE="${TOKEN_FILE:-./tmp/.bearer_token}"
    if [ -f "$TOKEN_FILE" ]; then
        BEARER_TOKEN=$(cat "$TOKEN_FILE")
        echo "🔑 Loaded BEARER_TOKEN from $TOKEN_FILE"
    fi
fi

echo "🔍 Testing ping endpoint at: ${BACKEND_BASE_URL}/api/${API_VERSION}/ping"

# Check if BEARER_TOKEN is set
if [ -n "$BEARER_TOKEN" ]; then
    echo "🔑 Using Bearer token for authentication"
else
    echo "⚠️  No BEARER_TOKEN set - making unauthenticated request"
fi
echo

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test ping endpoint with optional authentication
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ping")
else
    response=$(curl -s -w "\n%{http_code}" "${BACKEND_BASE_URL}/api/${API_VERSION}/ping")
fi

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

echo "Response: $body"
echo "HTTP Status: $http_code"
echo

if [ "$http_code" -eq 200 ]; then
    if echo "$body" | grep -q '"status":"OK"' || echo "$body" | grep -q "'status':'OK'"; then
        echo "✅ Ping test passed!"
        PASSED_TESTS=$((PASSED_TESTS + 1))

        # Summary
        echo
        echo "═══════════════════════════════════════"
        echo "Test Summary:"
        echo "  Total:  $TOTAL_TESTS"
        echo "  Passed: $PASSED_TESTS ✅"
        echo "  Failed: $FAILED_TESTS ❌"
        echo "═══════════════════════════════════════"
        echo "✅ Ping endpoint test successful!"

        exit 0
    else
        echo "❌ Unexpected response body"
        FAILED_TESTS=$((FAILED_TESTS + 1))

        # Summary
        echo
        echo "═══════════════════════════════════════"
        echo "Test Summary:"
        echo "  Total:  $TOTAL_TESTS"
        echo "  Passed: $PASSED_TESTS ✅"
        echo "  Failed: $FAILED_TESTS ❌"
        echo "═══════════════════════════════════════"
        echo "❌ Ping endpoint test failed!"

        exit 1
    fi
else
    echo "❌ Ping test failed with HTTP status $http_code"
    FAILED_TESTS=$((FAILED_TESTS + 1))

    # Summary
    echo
    echo "═══════════════════════════════════════"
    echo "Test Summary:"
    echo "  Total:  $TOTAL_TESTS"
    echo "  Passed: $PASSED_TESTS ✅"
    echo "  Failed: $FAILED_TESTS ❌"
    echo "═══════════════════════════════════════"
    echo "❌ Ping endpoint test failed!"

    exit 1
fi
