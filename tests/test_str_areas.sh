#!/bin/bash

# Test script for STR areas endpoints of the SDEP API
# Expects BACKEND_BASE_URL environment variable to be set
# Optionally accepts BEARER_TOKEN environment variable for authenticated requests
# Optionally accepts API_VERSION environment variable (defaults to v0)
# Tests:
#   - GET /str/areas/count (count areas)
#   - GET /str/areas (list areas with optional pagination)
#   - GET /str/areas/{areaId} (get specific area shapefile data)

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

echo "🔍 Testing STR areas endpoints"

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

##############################################################################
# Setup: Create fixture areas so tests work on empty DB
##############################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURE_COUNT=5
echo "📦 Creating $FIXTURE_COUNT fixture areas for STR tests..."
FIXTURE_IDS=$("$SCRIPT_DIR/lib/create_fixture_areas.sh" "$FIXTURE_COUNT" "sdep-test-str-areas" 2>&1 | tee /dev/stderr | grep "^sdep-test-")
FIXTURE_AREA_1=$(echo "$FIXTURE_IDS" | sed -n '1p')
FIXTURE_AREA_2=$(echo "$FIXTURE_IDS" | sed -n '2p')
FIXTURE_AREA_3=$(echo "$FIXTURE_IDS" | sed -n '3p')
echo "✅ Fixture areas created"
echo

##############################################################################
# GET /str/areas/count - Count areas test
##############################################################################

echo "════════════════════════════════════════════"
echo "Testing GET /str/areas/count (count areas)"
echo "════════════════════════════════════════════"
echo

# Test 1: Count areas
echo "Test 1: Count areas"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas/count")
else
    response=$(curl -s -w "\n%{http_code}" "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas/count")
fi

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

echo "Response: $body"
echo "HTTP Status: $http_code"
echo

# Expected count (at least the fixture areas we just created)
EXPECTED_COUNT=$FIXTURE_COUNT

if [ "$http_code" -eq 200 ]; then
    # Extract count from JSON response (handles both "count":10 and "count": 10)
    actual_count=$(echo "$body" | grep -o '"count"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*$')

    if [ -z "$actual_count" ]; then
        echo "❌ Test 1 failed: Could not extract count from response body"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    elif [ "$actual_count" -ge "$EXPECTED_COUNT" ]; then
        echo "✅ Test 1 passed: Areas count is correct (Expected minimal: $EXPECTED_COUNT, Got: $actual_count)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 1 failed: Unexpected count value (Expected minimal: $EXPECTED_COUNT, Got: $actual_count)"
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

##############################################################################
# GET /str/areas - List areas tests
##############################################################################

echo "════════════════════════════════════════════"
echo "Testing GET /str/areas (list areas)"
echo "════════════════════════════════════════════"
echo

# Test 2: GET all areas
echo "Test 2: GET all areas"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas")
else
    response=$(curl -s -w "\n%{http_code}" "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas")
fi

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

echo "Response (first 500 chars): ${body:0:500}..."
echo "HTTP Status: $http_code"
echo

if [ "$http_code" -eq 200 ]; then
    # Check if response contains areas array
    if echo "$body" | grep -q '"areas"'; then
        # Extract number of areas (count occurrences of "areaId")
        area_count=$(echo "$body" | grep -o '"areaId"' | wc -l)

        # Extract area IDs for later tests using jq
        FIRST_AREA_ID=$(echo "$body" | jq -r '.areas[0].areaId // empty' 2>/dev/null)
        SECOND_AREA_ID=$(echo "$body" | jq -r '.areas[1].areaId // empty' 2>/dev/null)
        THIRD_AREA_ID=$(echo "$body" | jq -r '.areas[2].areaId // empty' 2>/dev/null)

        # Fallback to fixture IDs if dynamic extraction failed
        FIRST_AREA_ID=${FIRST_AREA_ID:-$FIXTURE_AREA_1}
        SECOND_AREA_ID=${SECOND_AREA_ID:-$FIXTURE_AREA_2}
        THIRD_AREA_ID=${THIRD_AREA_ID:-$FIXTURE_AREA_3}

        if [ "$area_count" -ge 1 ]; then
            echo "✅ Test 2 passed: Retrieved $area_count area(s)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 2 failed: No areas found in response"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 2 failed: Response does not contain 'areas' field"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
elif [ "$http_code" -eq 401 ] && [ -z "$BEARER_TOKEN" ]; then
    echo "✅ Test 2 passed: Correctly rejected unauthenticated request (401)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "❌ Test 2 failed: Unexpected HTTP status $http_code"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo

# Test 3: GET areas with pagination (offset=0, limit=1)
echo "Test 3: GET areas with pagination (offset=0, limit=1)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Only run if authenticated
if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas?offset=0&limit=1")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 200 ]; then
        # Count number of areas in response
        area_count=$(echo "$body" | grep -o '"areaId"' | wc -l)

        if [ "$area_count" -eq 1 ]; then
            echo "✅ Test 3 passed: Retrieved exactly 1 area with limit=1"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 3 failed: Expected 1 area but got $area_count"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 3 failed: Unexpected HTTP status $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 3 (requires authentication)"
fi

echo

# Test 4: Verify response structure
echo "Test 4: Verify response structure (areaId, competentAuthorityId, competentAuthorityName, filename, created_at)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Only run if authenticated
if [ -n "$BEARER_TOKEN" ]; then
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas?limit=1")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 200 ]; then
        # Check for required fields
        has_area_id=$(echo "$body" | grep -q '"areaId"' && echo "yes" || echo "no")
        has_competent_authority_id=$(echo "$body" | grep -q '"competentAuthorityId"' && echo "yes" || echo "no")
        has_competent_authority_name=$(echo "$body" | grep -q '"competentAuthorityName"' && echo "yes" || echo "no")
        has_filename=$(echo "$body" | grep -q '"filename"' && echo "yes" || echo "no")
        has_created_at=$(echo "$body" | grep -q '"createdAt"' && echo "yes" || echo "no")

        if [ "$has_area_id" = "yes" ] && [ "$has_competent_authority_id" = "yes" ] && \
           [ "$has_competent_authority_name" = "yes" ] && [ "$has_filename" = "yes" ] && \
           [ "$has_created_at" = "yes" ]; then
            echo "✅ Test 4 passed: Response contains all required fields"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 4 failed: Missing required fields in response"
            echo "   - areaId: $has_area_id"
            echo "   - competentAuthorityId: $has_competent_authority_id"
            echo "   - competentAuthorityName: $has_competent_authority_name"
            echo "   - filename: $has_filename"
            echo "   - createdAt: $has_created_at"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 4 failed: Unexpected HTTP status $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 4 (requires authentication)"
fi

echo

##############################################################################
# GET /str/areas/{areaId} - Get specific area tests
##############################################################################

echo "════════════════════════════════════════════"
echo "Testing GET /str/areas/{areaId} (get area)"
echo "════════════════════════════════════════════"
echo

# Test 5: GET area with known areaId
echo "Test 5: GET area with known areaId"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

TARGET_AREA_ID=${FIRST_AREA_ID:-"99999999999999999999"}

if [ -n "$BEARER_TOKEN" ] && [ -n "$TARGET_AREA_ID" ]; then
    # Use -i to get headers and -s for silent mode, -w to get http code
    { response=$(curl -s -i -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas/${TARGET_AREA_ID}"); } 2>/dev/null
elif [ -z "$TARGET_AREA_ID" ]; then
    response=""
    http_code=""
    echo "⏭️  Skipping Test 5 (no areaId captured from list response)"
else
    { response=$(curl -s -i -w "\n%{http_code}" "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas/${TARGET_AREA_ID}"); } 2>/dev/null
fi

http_code=$(echo "$response" | tail -n1)
headers=$(echo "$response" | sed '$d')

echo "HTTP Status: $http_code"

if [ -z "$http_code" ]; then
    echo "⏭️  Skipping Test 5 (no response)"
elif [ "$http_code" -eq 200 ]; then
    # Check Content-Type header
    content_type=$(echo "$headers" | grep -i "content-type:" | head -n1 | cut -d' ' -f2- | tr -d '\r')

    # Check Content-Disposition header
    content_disposition=$(echo "$headers" | grep -i "content-disposition:" | head -n1)

    echo "Content-Type: $content_type"
    echo "Content-Disposition: ${content_disposition:0:100}..."

    if echo "$content_type" | grep -q "application/zip"; then
        if echo "$content_disposition" | grep -q "attachment"; then
            echo "✅ Test 5 passed: Retrieved area with correct headers"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 5 failed: Missing Content-Disposition attachment header"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 5 failed: Expected Content-Type application/zip"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
elif [ "$http_code" -eq 401 ] && [ -z "$BEARER_TOKEN" ]; then
    echo "✅ Test 5 passed: Correctly rejected unauthenticated request (401)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "❌ Test 5 failed: Unexpected HTTP status $http_code"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo

# Test 6: GET area with another known areaId
echo "Test 6: GET area with another known areaId"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Only run if authenticated and second area ID was captured
if [ -n "$BEARER_TOKEN" ] && [ -n "$SECOND_AREA_ID" ]; then
    { response=$(curl -s -i -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas/${SECOND_AREA_ID}"); } 2>/dev/null

    http_code=$(echo "$response" | tail -n1)
    headers=$(echo "$response" | sed '$d')

    echo "HTTP Status: $http_code"

    if [ "$http_code" -eq 200 ]; then
        # Check Content-Type header
        content_type=$(echo "$headers" | grep -i "content-type:" | head -n1 | cut -d' ' -f2- | tr -d '\r')

        if echo "$content_type" | grep -q "application/zip"; then
            echo "✅ Test 6 passed: Retrieved area"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 6 failed: Expected Content-Type application/zip"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 6 failed: Unexpected HTTP status $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 6 (no second area ID available)"
fi

echo

# Test 7: GET area with non-existent areaId (should return 404)
echo "Test 7: GET area with non-existent areaId (should return 404)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Only run if authenticated
if [ -n "$BEARER_TOKEN" ]; then
    NONEXISTENT_AREA_ID="99999999"

    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas/${NONEXISTENT_AREA_ID}")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 404 ]; then
        echo "✅ Test 7 passed: Correctly returned 404 for non-existent area"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 7 failed: Expected 404 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 7 (requires authentication)"
fi

echo

# Test 8: Verify Content-Disposition filename
echo "Test 8: Verify Content-Disposition contains filename"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Only run if authenticated and third area ID was captured
if [ -n "$BEARER_TOKEN" ] && [ -n "$THIRD_AREA_ID" ]; then
    { response=$(curl -s -i -w "\n%{http_code}" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        "${BACKEND_BASE_URL}/api/${API_VERSION}/str/areas/${THIRD_AREA_ID}"); } 2>/dev/null

    http_code=$(echo "$response" | tail -n1)
    headers=$(echo "$response" | sed '$d')

    echo "HTTP Status: $http_code"

    if [ "$http_code" -eq 200 ]; then
        # Check Content-Disposition header for filename
        content_disposition=$(echo "$headers" | grep -i "content-disposition:" | head -n1)

        echo "Content-Disposition: $content_disposition"

        if echo "$content_disposition" | grep -q "filename="; then
            echo "✅ Test 8 passed: Content-Disposition contains filename"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 8 failed: Content-Disposition does not contain filename"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 8 failed: Unexpected HTTP status $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 8 (no third area ID available)"
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
    echo "✅ All STR areas endpoint tests passed!"
    exit 0
else
    echo "❌ Some STR areas endpoint tests failed!"
    exit 1
fi
