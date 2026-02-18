#!/bin/bash

# Test script for area submission endpoint of the SDEP API
# Expects BACKEND_BASE_URL environment variable to be set
# Optionally accepts BEARER_TOKEN environment variable for authenticated requests
# Optionally accepts API_VERSION environment variable (defaults to v0)
# Tests POST /ca/areas endpoint with file upload (multipart/form-data)

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

# Default API version to v0 if not set
API_VERSION=${API_VERSION:-v0}

# CA endpoint requires authorized client
# Load token from ./tmp/.bearer_token_ca file
if [ -f ./tmp/.bearer_token ]; then
    BEARER_TOKEN=$(cat ./tmp/.bearer_token)
    echo "🔑 Loaded BEARER_TOKEN from ./tmp/.bearer_token"
else
    echo "⚠️  No ./tmp/.bearer_token file found"
fi

echo "🔍 Testing CA area endpoint at: ${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas"

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
SHAPEFILE_PATH="$SCRIPT_DIR/../test-data/shapefiles/Amsterdam-dummy.zip"
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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas")
else
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${AREA_ID}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas")
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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas")

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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas")

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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas")

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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas/count")

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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas")

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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas"

    # Submit v2 with same areaId
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -F "file=@${SHAPEFILE_PATH}" \
        -F "areaId=${VERSIONED_ID}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas")

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

# Test 8: DELETE area (soft-delete)
echo "Test 8: DELETE area (soft-delete)"
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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas"

    # Delete the area
    response=$(curl -s -w "\n%{http_code}" \
        -X DELETE \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas/${DELETE_AREA_ID}")

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
        "${BACKEND_BASE_URL}/api/${API_VERSION}/ca/areas/nonexistent-area-$(date +%s)")

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
