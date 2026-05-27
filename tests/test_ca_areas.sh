#!/bin/bash

# Test script for area submission endpoint of the SDEP API
# Expects BACKEND_BASE_URL environment variable to be set
# Optionally accepts BEARER_TOKEN environment variable for authenticated requests
# Optionally accepts API_VERSION environment variable (defaults to v1)
# Tests POST /ca/areas endpoint with file upload (multipart/form-data)

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

# Default API version to v1 if not set
API_VERSION=${API_VERSION:-v1}

# CA endpoint requires authorized client
# Load token from ./tmp/.bearer_token_ca file
if [ -f ./tmp/.bearer_token ]; then
    BEARER_TOKEN=$(cat ./tmp/.bearer_token)
    echo "🔑 Loaded BEARER_TOKEN from ./tmp/.bearer_token"
else
    echo "⚠️  No ./tmp/.bearer_token file found"
fi

echo "🔍 Testing CA area endpoint at: ${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas"

# Check if BEARER_TOKEN is set
if [ -n "$BEARER_TOKEN" ]; then
    echo "🔑 Using Bearer token for authentication"
else
    echo "⚠️  No BEARER_TOKEN set - making unauthenticated request (should fail)"
fi
echo

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Check if test shapefile exists (resolve relative to script location)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHAPEFILE_PATH="$SCRIPT_DIR/../test-data/shapefiles/Amsterdam.zip"
if [ ! -f "$SHAPEFILE_PATH" ]; then
    echo "❌ Error: Test shapefile not found at $SHAPEFILE_PATH"
    exit 1
fi

echo "📂 Using test shapefile: $SHAPEFILE_PATH"
echo

# Test 1: POST single area with file upload
echo "Test 1: POST single area with file upload"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Generate unique area ID
TIMESTAMP=$(date +%s)
AREA_ID="sdep-test-area-single-${TIMESTAMP}"

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${AREA_ID}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")
else
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${AREA_ID}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")
fi

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

echo "Response: $body"
echo "HTTP Status: $http_code"
echo

if [ "$http_code" -eq 201 ]; then
    # Check for single-item response format with areaId and filename
    if echo "$body" | grep -q '"areaId"' && \
       echo "$body" | grep -q '"filename"' && \
       echo "$body" | grep -q '"createdAt"'; then
        echo "✅ Test 1 passed: Area successfully submitted"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 1 failed: Expected areaId, filename, createdAt in response"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
elif [ "$http_code" -eq 401 ] && [ -z "$BEARER_TOKEN" ]; then
    echo "✅ Test 1 passed: Correctly rejected unauthenticated request (401)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "❌ Test 1 failed: Unexpected HTTP status $http_code"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo

# Test 2: POST with optional areaId field
echo "Test 2: POST with custom areaId"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Only run if authenticated
if [ -n "$BEARER_TOKEN" ]; then
    # Generate unique ID using epoch timestamp to ensure test idempotence
    UNIQUE_ID=$(date +%s%N | cut -b1-13)

    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=sdep-test-area-custom-${UNIQUE_ID}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 201 ]; then
        if echo "$body" | grep -q '"areaId"' && \
           echo "$body" | grep -q '"createdAt"'; then
            echo "✅ Test 2 passed: Area with custom areaId successfully submitted"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 2 failed: Expected success response format"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 2 failed: Expected 201 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 2 (requires authentication)"
fi

echo

# Test 3: POST without areaId (auto-generated UUID)
echo "Test 3: POST without areaId (auto-generated UUID)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Only run if authenticated
if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 201 ]; then
        if echo "$body" | grep -q '"areaId"' && \
           echo "$body" | grep -q '"createdAt"'; then
            echo "✅ Test 3 passed: Area with auto-generated UUID successfully submitted"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 3 failed: Expected areaId in response"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 3 failed: Expected 201 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 3 (requires authentication)"
fi

echo

# Test 4: GET own areas
echo "Test 4: GET own areas"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -X GET \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 200 ]; then
        if echo "$body" | grep -q '"areas"'; then
            echo "✅ Test 4 passed: GET /ca/areas returned areas list"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 4 failed: Expected areas key in response"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 4 failed: Expected 200 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 4 (requires authentication)"
fi

echo

# Test 5: GET own areas count
echo "Test 5: GET own areas count"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -X GET \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas/count")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 200 ]; then
        if echo "$body" | grep -q '"count"'; then
            echo "✅ Test 5 passed: GET /ca/areas/count returned count"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 5 failed: Expected count key in response"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 5 failed: Expected 200 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 5 (requires authentication)"
fi

echo

# Test 6: GET own areas does not contain endedAt
echo "Test 6: GET own areas does not contain endedAt"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -X GET \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 200 ]; then
        if echo "$body" | grep -q '"endedAt"'; then
            echo "❌ Test 6 failed: Response contains endedAt (should be internal only)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        else
            echo "✅ Test 6 passed: Response does not contain endedAt"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        fi
    else
        echo "❌ Test 6 failed: Expected 200 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 6 (requires authentication)"
fi

echo

# Test 7: Versioning - submit same areaId twice, verify only latest returned
echo "Test 7: Versioning - submit same areaId twice"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    VERSIONED_ID="sdep-test-area-versioned-$(date +%s)"

    # Submit v1
    curl -s -o /dev/null -w "" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${VERSIONED_ID}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas"

    # Submit v2 with same areaId
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${VERSIONED_ID}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 201 ]; then
        if echo "$body" | grep -q "\"areaId\":\"${VERSIONED_ID}\""; then
            echo "✅ Test 7 passed: Versioned area submission returned latest"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 7 failed: Expected areaId to match versioned ID"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 7 failed: Expected 201 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 7 (requires authentication)"
fi

echo

# Test 8: DELETE area (deactivate)
echo "Test 8: DELETE area (deactivate)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    DELETE_AREA_ID="sdep-test-area-delete-$(date +%s)"

    # Create area first
    curl -s -o /dev/null -w "" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${DELETE_AREA_ID}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas"

    # Delete the area
    response=$(curl -s -w "\n%{http_code}" \
        -X DELETE \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas/${DELETE_AREA_ID}")

    http_code=$(echo "$response" | tail -n1)

    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 204 ]; then
        echo "✅ Test 8 passed: Area successfully deleted (204 No Content)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 8 failed: Expected 204 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 8 (requires authentication)"
fi

echo

# Test 9: DELETE nonexistent area returns 404
echo "Test 9: DELETE nonexistent area returns 404"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -X DELETE \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas/nonexistent-area-$(date +%s)")

    http_code=$(echo "$response" | tail -n1)

    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 404 ]; then
        echo "✅ Test 9 passed: Nonexistent area correctly returned 404"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 9 failed: Expected 404 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 9 (requires authentication)"
fi

echo

# Test 10: GET own area by ID (success)
echo "Test 10: GET own area by ID (success)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    GET_AREA_ID="sdep-test-area-get-$(date +%s)"

    # Create area first
    curl -s -o /dev/null -w "" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${GET_AREA_ID}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas"

    # GET area by ID
    response=$(curl -s -w "\n%{http_code}" \
        -X GET \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas/${GET_AREA_ID}")

    http_code=$(echo "$response" | tail -n1)

    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 200 ]; then
        echo "✅ Test 10 passed: GET /ca/areas/{areaId} returned area (200 OK)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 10 failed: Expected 200 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 10 (requires authentication)"
fi

echo

# Test 11: GET nonexistent own area returns 404
echo "Test 11: GET nonexistent own area returns 404"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -X GET \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas/nonexistent-area-$(date +%s)")

    http_code=$(echo "$response" | tail -n1)

    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 404 ]; then
        echo "✅ Test 11 passed: Nonexistent area correctly returned 404"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 11 failed: Expected 404 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 11 (requires authentication)"
fi

echo

# Test 12: Cross-CA isolation - two CAs sharing the same areaId keep their own
echo "Test 12: Cross-CA isolation - same areaId across two CAs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ] && [ -n "${CA2_CLIENT_ID:-}" ] && [ -n "${CA2_CLIENT_SECRET:-}" ]; then
    # CA1 reuses the ambient BEARER_TOKEN; alias it so CA1_/CA2_ are explicit throughout this test
    CA1_BEARER_TOKEN="$BEARER_TOKEN"

    # Obtain a token for CA2
    ca2_token_response=$(curl -s -X POST \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "grant_type=client_credentials" \
        --data-urlencode "client_id=${CA2_CLIENT_ID}" \
        --data-urlencode "client_secret=${CA2_CLIENT_SECRET}" \
        "${BACKEND_BASE_URL}/api/auth/${API_VERSION}/token")
    CA2_BEARER_TOKEN=$(echo "$ca2_token_response" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"\([^"]*\)"/\1/')

    if [ -z "$CA2_BEARER_TOKEN" ]; then
        echo "❌ Test 12 failed: Could not obtain CA2 access token"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    else
        SHARED_AREA_ID="sdep-test-area-shared-$(date +%s)"

        # CA1 POSTs the shared areaId
        ca1_post=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Authorization: Bearer ${CA1_BEARER_TOKEN}" \
            -F "file=@${SHAPEFILE_PATH}" \
            -F "areaId=${SHARED_AREA_ID}" \
            -F "areaName=CA1 area" \
            "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")
        ca1_post_code=$(echo "$ca1_post" | tail -n1)

        # CA2 POSTs the SAME areaId
        ca2_post=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Authorization: Bearer ${CA2_BEARER_TOKEN}" \
            -F "file=@${SHAPEFILE_PATH}" \
            -F "areaId=${SHARED_AREA_ID}" \
            -F "areaName=CA2 area" \
            "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")
        ca2_post_code=$(echo "$ca2_post" | tail -n1)

        # Each CA should still see their own area (GET /ca/areas/{id})
        ca1_get_code=$(curl -s -o /dev/null -w "%{http_code}" \
            -X GET \
            -H "Authorization: Bearer ${CA1_BEARER_TOKEN}" \
            "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas/${SHARED_AREA_ID}")
        ca2_get_code=$(curl -s -o /dev/null -w "%{http_code}" \
            -X GET \
            -H "Authorization: Bearer ${CA2_BEARER_TOKEN}" \
            "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas/${SHARED_AREA_ID}")

        echo "CA1 POST: $ca1_post_code  CA2 POST: $ca2_post_code  CA1 GET: $ca1_get_code  CA2 GET: $ca2_get_code"
        echo

        if [ "$ca1_post_code" -eq 201 ] && [ "$ca2_post_code" -eq 201 ] && \
           [ "$ca1_get_code" -eq 200 ] && [ "$ca2_get_code" -eq 200 ]; then
            echo "✅ Test 12 passed: Both CAs keep their own area despite shared areaId"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 12 failed: Expected both POSTs=201 and both GETs=200 (issue #141)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    fi
else
    echo "⏭️  Skipping Test 12 (requires BEARER_TOKEN, CA2_CLIENT_ID, CA2_CLIENT_SECRET)"
fi

echo

# Summary
echo "═══════════════════════════════════════"
echo "Test Summary:"
echo "  Total:  $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS ✅"
echo "  Failed: $FAILED_TESTS ❌"
echo "═══════════════════════════════════════"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All area endpoint tests passed!"
    exit 0
else
    echo "❌ Some area endpoint tests failed!"
    exit 1
fi
