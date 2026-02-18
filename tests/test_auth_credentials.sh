#!/bin/bash

# Test script for OAuth token acquisition
# Expects BACKEND_BASE_URL environment variable to be set
# Tests both STR and CA credentials
# Optionally accepts API_VERSION environment variable (defaults to v0)

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

# Default API version to v0 if not set
API_VERSION=${API_VERSION:-v0}

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Helper function to test client credentials
test_credentials() {
    local client_id="$1"
    local client_secret="$2"
    local client_type="$3"

    echo "🔐 Testing ${client_type} credentials"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "CLIENT_ID: ${client_id}"
    echo "Endpoint: ${BACKEND_BASE_URL}/api/${API_VERSION}/auth/token"
    echo

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Request token using client_credentials grant type
    response=$(curl -s -w "\n%{http_code}" -X POST \
      -H "Content-Type: application/x-www-form-urlencoded" \
      --data-urlencode "grant_type=client_credentials" \
      --data-urlencode "client_id=${client_id}" \
      --data-urlencode "client_secret=${client_secret}" \
      "${BACKEND_BASE_URL}/api/${API_VERSION}/auth/token")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "HTTP Status: $http_code"

    if [ "$http_code" -eq 200 ]; then
        access_token=$(echo "$body" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"\([^"]*\)"/\1/')

        if [ -n "$access_token" ]; then
            echo "✅ ${client_type} token acquired successfully!"

            # Decode and display JWT token contents
            echo ""
            echo "🔍 JWT Token Contents:"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            # JWT format: header.payload.signature
            # Decode the payload (second part)
            JWT_PAYLOAD=$(echo "$access_token" | cut -d'.' -f2)
            # Add padding if needed (base64 requires padding)
            case $((${#JWT_PAYLOAD} % 4)) in
                2) JWT_PAYLOAD="${JWT_PAYLOAD}==" ;;
                3) JWT_PAYLOAD="${JWT_PAYLOAD}=" ;;
            esac
            # Decode and pretty print
            echo "$JWT_PAYLOAD" | base64 -d 2>/dev/null | jq . 2>/dev/null || echo "⚠️  Could not decode JWT token"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

            PASSED_TESTS=$((PASSED_TESTS + 1))
            return 0
        else
            echo "❌ Failed to extract access token from response"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            return 1
        fi
    elif [ "$http_code" -eq 401 ]; then
        echo "❌ Unauthorized - invalid ${client_type} credentials"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    else
        echo "❌ Token acquisition failed with HTTP status $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Always test both credentials
test_credentials "${STR_CLIENT_ID}" "${STR_CLIENT_SECRET}" "STR"
echo
test_credentials "${CA_CLIENT_ID}" "${CA_CLIENT_SECRET}" "CA"

# Summary
echo
echo "═══════════════════════════════════════"
echo "Test Summary:"
echo "  Total:  $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS ✅"
echo "  Failed: $FAILED_TESTS ❌"
echo "═══════════════════════════════════════"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All OAuth token acquisition tests passed!"
    exit 0
else
    echo "❌ Some OAuth token acquisition tests failed!"
    exit 1
fi
