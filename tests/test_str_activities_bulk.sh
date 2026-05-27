#!/bin/bash

# Test script for bulk activity submission endpoint of the SDEP API
# Expects BACKEND_BASE_URL environment variable to be set
# Optionally accepts BEARER_TOKEN environment variable for authenticated requests
# Optionally accepts API_VERSION environment variable (defaults to v1)
# Tests POST /str/activities/bulk endpoint

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

# Default API version to v1 if not set
API_VERSION=${API_VERSION:-v1}

# STR endpoint requires authorized client
# Load token from ./tmp/.bearer_token file
if [ -f ./tmp/.bearer_token ]; then
    BEARER_TOKEN=$(cat ./tmp/.bearer_token)
    echo "🔑 Loaded BEARER_TOKEN from ./tmp/.bearer_token"
else
    echo "⚠️  No ./tmp/.bearer_token file found"
fi

echo "🔍 Testing STR bulk activity endpoints at: ${BACKEND_BASE_URL}/api/str/${API_VERSION}/activities/bulk"

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

# Setup: Create fixture areas so tests work on empty DB
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📦 Creating fixture areas for bulk activity tests..."
FIXTURE_IDS=$("$SCRIPT_DIR/lib/create_fixture_areas.sh" 3 "sdep-test-bulk-areas" 2>&1 | tee /dev/stderr | grep "^sdep-test-")
AREA_ID_1=$(echo "$FIXTURE_IDS" | sed -n '1p')
AREA_ID_2=$(echo "$FIXTURE_IDS" | sed -n '2p')
AREA_ID_3=$(echo "$FIXTURE_IDS" | sed -n '3p')

if [ -z "$AREA_ID_1" ] || [ -z "$AREA_ID_2" ] || [ -z "$AREA_ID_3" ]; then
    echo "❌ Error: Failed to create fixture areas"
    exit 1
fi
echo "✅ Using fixture area IDs: $AREA_ID_1, $AREA_ID_2, $AREA_ID_3"
echo

# Generate dynamic timestamps
TIMESTAMP=$(date +%s)
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
END_TIME=$(date -u -d "+1 hour" +"%Y-%m-%dT%H:%M:%SZ")

# Test 1: POST bulk activities (all valid)
echo "Test 1: POST bulk activities (all valid → 201)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    read -r -d '' PAYLOAD <<EOF || true
{
  "activities": [
    {
      "activityId": "sdep-test-bulk-ok1-$TIMESTAMP",
      "url": "http://sdep-test.example.com/bulk-ok1",
      "registrationNumber": "REGBULK001",
      "address": {"thoroughfare": "Prinsengracht", "locatorDesignatorNumber": 265, "postCode": "1016HV", "postName": "Amsterdam", "fullAddress": "Prinsengracht 265, 1016HV Amsterdam"},
      "temporal": {"startDatetime": "$START_TIME", "endDatetime": "$END_TIME"},
      "areaId": "$AREA_ID_1",
      "numberOfGuests": 4,
      "countryOfGuests": ["NLD", "NLD", "DEU", "BEL"]
    },
    {
      "activityId": "sdep-test-bulk-ok2-$TIMESTAMP",
      "url": "http://sdep-test.example.com/bulk-ok2",
      "registrationNumber": "REGBULK002",
      "address": {"thoroughfare": "Keizersgracht", "postCode": "1015AA", "postName": "Amsterdam", "fullAddress": "Keizersgracht, 1015AA Amsterdam"},
      "temporal": {"startDatetime": "$START_TIME", "endDatetime": "$END_TIME"},
      "areaId": "$AREA_ID_2",
      "numberOfGuests": 2,
      "countryOfGuests": ["FRA", "N/A"]
    }
  ]
}
EOF

    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -d "$PAYLOAD" \
        "${BACKEND_BASE_URL}/api/str/${API_VERSION}/activities/bulk")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 201 ]; then
        if echo "$body" | grep -q '"succeeded":2' && echo "$body" | grep -q '"failed":0'; then
            echo "✅ Test 1 passed: All activities created (201)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 1 failed: Expected succeeded=2, failed=0"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 1 failed: Expected 201 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 1 (requires authentication)"
fi

echo

# Test 2: POST bulk activities (partial success)
echo "Test 2: POST bulk activities (partial success → 200)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    START_TIME_2=$(date -u -d "+2 hours" +"%Y-%m-%dT%H:%M:%SZ")
    END_TIME_2=$(date -u -d "+3 hours" +"%Y-%m-%dT%H:%M:%SZ")

    read -r -d '' PAYLOAD_PARTIAL <<EOF || true
{
  "activities": [
    {
      "activityId": "sdep-test-bulk-partial1-$TIMESTAMP",
      "url": "http://sdep-test.example.com/bulk-partial1",
      "registrationNumber": "REGPART001",
      "address": {"thoroughfare": "Prinsengracht", "locatorDesignatorNumber": 265, "postCode": "1016HV", "postName": "Amsterdam", "fullAddress": "Prinsengracht 265, 1016HV Amsterdam"},
      "temporal": {"startDatetime": "$START_TIME_2", "endDatetime": "$END_TIME_2"},
      "areaId": "$AREA_ID_1",
      "numberOfGuests": 4,
      "countryOfGuests": ["NLD", "NLD", "DEU", "BEL"]
    },
    {
      "activityId": "sdep-test-bulk-partial2-$TIMESTAMP",
      "url": "http://sdep-test.example.com/bulk-partial2",
      "registrationNumber": "REGPART002",
      "address": {"thoroughfare": "Bad Street", "locatorDesignatorNumber": 1, "postCode": "0000AA", "postName": "Nowhere", "fullAddress": "Bad Street 1, 0000AA Nowhere"},
      "temporal": {"startDatetime": "$START_TIME_2", "endDatetime": "$END_TIME_2"},
      "areaId": "nonexistent-area-id",
      "numberOfGuests": 2,
      "countryOfGuests": ["NLD", "N/A"]
    }
  ]
}
EOF

    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -d "$PAYLOAD_PARTIAL" \
        "${BACKEND_BASE_URL}/api/str/${API_VERSION}/activities/bulk")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 200 ]; then
        if echo "$body" | grep -q '"succeeded":1' && echo "$body" | grep -q '"failed":1'; then
            echo "✅ Test 2 passed: Partial success (200)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 2 failed: Expected succeeded=1, failed=1"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 2 failed: Expected 200 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 2 (requires authentication)"
fi

echo

# Test 3: POST bulk activities (all invalid → 422)
echo "Test 3: POST bulk activities (all invalid → 422)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    START_TIME_3=$(date -u -d "+4 hours" +"%Y-%m-%dT%H:%M:%SZ")
    END_TIME_3=$(date -u -d "+5 hours" +"%Y-%m-%dT%H:%M:%SZ")

    read -r -d '' PAYLOAD_FAIL <<EOF || true
{
  "activities": [
    {
      "activityId": "sdep-test-bulk-fail1-$TIMESTAMP",
      "url": "http://sdep-test.example.com/bulk-fail1",
      "registrationNumber": "REGFAIL001",
      "address": {"thoroughfare": "Bad Street", "locatorDesignatorNumber": 1, "postCode": "0000AA", "postName": "Nowhere", "fullAddress": "Bad Street 1, 0000AA Nowhere"},
      "temporal": {"startDatetime": "$START_TIME_3", "endDatetime": "$END_TIME_3"},
      "areaId": "nonexistent-area-1",
      "numberOfGuests": 1,
      "countryOfGuests": ["N/A"]
    },
    {
      "activityId": "sdep-test-bulk-fail2-$TIMESTAMP",
      "url": "http://sdep-test.example.com/bulk-fail2",
      "registrationNumber": "REGFAIL002",
      "address": {"thoroughfare": "Bad Street", "locatorDesignatorNumber": 2, "postCode": "0000BB", "postName": "Nowhere", "fullAddress": "Bad Street 2, 0000BB Nowhere"},
      "temporal": {"startDatetime": "$START_TIME_3", "endDatetime": "$END_TIME_3"},
      "areaId": "nonexistent-area-2",
      "numberOfGuests": 2,
      "countryOfGuests": ["N/A", "N/A"]
    }
  ]
}
EOF

    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -d "$PAYLOAD_FAIL" \
        "${BACKEND_BASE_URL}/api/str/${API_VERSION}/activities/bulk")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "HTTP Status: $http_code"
    echo

    if [ "$http_code" -eq 422 ]; then
        if echo "$body" | grep -q '"succeeded":0' && echo "$body" | grep -q '"failed":2'; then
            echo "✅ Test 3 passed: All failed (422)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "❌ Test 3 failed: Expected succeeded=0, failed=2"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo "❌ Test 3 failed: Expected 422 but got $http_code"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo "⏭️  Skipping Test 3 (requires authentication)"
fi

echo

# Test 4: POST bulk without auth (→ 401)
echo "Test 4: POST bulk activities without authentication (→ 401)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"activities": [{"areaId": "test"}]}' \
    "${BACKEND_BASE_URL}/api/str/${API_VERSION}/activities/bulk")

http_code=$(echo "$response" | tail -n1)

echo "HTTP Status: $http_code"
echo

if [ "$http_code" -eq 401 ]; then
    echo "✅ Test 4 passed: Correctly rejected unauthenticated request (401)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "❌ Test 4 failed: Expected 401 but got $http_code"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo

# Test 5: Stacked insert + cancel (CA count unchanged)
# Step A: POST activityId=X with default status=finished     → CA count = N+1
# Step B: POST activityId=X with status=cancelled            → CA count still N+1
#         (cancellation is a new version of the same functional activityId,
#          not an additional current activity)
echo "Test 5: Stacked insert + cancel (CA count stays the same)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_TESTS=$((TOTAL_TESTS + 1))

if [ -n "$BEARER_TOKEN" ]; then
    STACKED_ID="sdep-test-bulk-stacked-$TIMESTAMP"
    START_TIME_5=$(date -u -d "+4 hours" +"%Y-%m-%dT%H:%M:%SZ")
    END_TIME_5=$(date -u -d "+5 hours" +"%Y-%m-%dT%H:%M:%SZ")

    CA_TOKEN_RESPONSE=$(curl -s -X POST \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "grant_type=client_credentials" \
        --data-urlencode "client_id=${CA1_CLIENT_ID}" \
        --data-urlencode "client_secret=${CA1_CLIENT_SECRET}" \
        "${BACKEND_BASE_URL}/api/auth/${API_VERSION}/token")
    CA_BEARER=$(echo "$CA_TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"\([^"]*\)"/\1/')
    if [ -z "$CA_BEARER" ]; then
        echo "❌ Test 5 failed: could not authenticate as CA (${CA1_CLIENT_ID})"
        echo "   Response: $CA_TOKEN_RESPONSE"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo
        # Skip rest of Test 5 but keep running remaining suites/summary
        : # no-op; drop into summary via the outer fi below
    else

    ca_count() {
        curl -s -H "Authorization: Bearer ${CA_BEARER}" \
            "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/activities/count" \
            | grep -o '"count"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*$'
    }

    COUNT_BEFORE=$(ca_count)
    if [ -z "$COUNT_BEFORE" ]; then
        echo "❌ Test 5 failed: could not fetch CA activity count (empty response)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo
    else
    echo "CA activity count BEFORE insert:  $COUNT_BEFORE"

    # Step A: insert (default status=finished)
    read -r -d '' PAYLOAD_INSERT <<EOF || true
{"activities":[{
  "activityId": "$STACKED_ID",
  "url": "http://sdep-test.example.com/bulk-stacked",
  "registrationNumber": "REGSTACK001",
  "address": {"thoroughfare": "Prinsengracht", "locatorDesignatorNumber": 265, "postCode": "1016HV", "postName": "Amsterdam", "fullAddress": "Prinsengracht 265, 1016HV Amsterdam"},
  "temporal": {"startDatetime": "$START_TIME_5", "endDatetime": "$END_TIME_5"},
  "areaId": "$AREA_ID_1",
  "numberOfGuests": 2,
  "countryOfGuests": ["NLD", "NLD"]
}]}
EOF

    insert_response=$(curl -s -w "\n%{http_code}" \
        -X POST -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -d "$PAYLOAD_INSERT" \
        "${BACKEND_BASE_URL}/api/str/${API_VERSION}/activities/bulk")
    insert_code=$(echo "$insert_response" | tail -n1)
    insert_body=$(echo "$insert_response" | sed '$d')
    echo "Step A (insert finished)  HTTP=$insert_code  body=$insert_body"

    COUNT_AFTER_INSERT=$(ca_count)
    echo "CA activity count AFTER  insert:  $COUNT_AFTER_INSERT"

    # Step B: cancel (same activityId, status=cancelled)
    read -r -d '' PAYLOAD_CANCEL <<EOF || true
{"activities":[{
  "activityId": "$STACKED_ID",
  "status": "cancelled",
  "url": "http://sdep-test.example.com/bulk-stacked",
  "registrationNumber": "REGSTACK001",
  "address": {"thoroughfare": "Prinsengracht", "locatorDesignatorNumber": 265, "postCode": "1016HV", "postName": "Amsterdam", "fullAddress": "Prinsengracht 265, 1016HV Amsterdam"},
  "temporal": {"startDatetime": "$START_TIME_5", "endDatetime": "$END_TIME_5"},
  "areaId": "$AREA_ID_1",
  "numberOfGuests": 2,
  "countryOfGuests": ["NLD", "NLD"]
}]}
EOF

    cancel_response=$(curl -s -w "\n%{http_code}" \
        -X POST -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        -d "$PAYLOAD_CANCEL" \
        "${BACKEND_BASE_URL}/api/str/${API_VERSION}/activities/bulk")
    cancel_code=$(echo "$cancel_response" | tail -n1)
    cancel_body=$(echo "$cancel_response" | sed '$d')
    echo "Step B (cancel)           HTTP=$cancel_code  body=$cancel_body"

    COUNT_AFTER_CANCEL=$(ca_count)
    echo "CA activity count AFTER  cancel:  $COUNT_AFTER_CANCEL"
    echo

    ASSERTIONS_OK=true
    if [ "$insert_code" != "201" ] || ! echo "$insert_body" | grep -q '"succeeded":1'; then
        ASSERTIONS_OK=false
    fi
    if [ "$cancel_code" != "201" ] || ! echo "$cancel_body" | grep -q '"succeeded":1' \
       || ! echo "$cancel_body" | grep -q '"status":"cancelled"'; then
        ASSERTIONS_OK=false
    fi
    if [ -z "$COUNT_AFTER_INSERT" ] || [ -z "$COUNT_AFTER_CANCEL" ] \
       || [ "$COUNT_AFTER_INSERT" != "$COUNT_AFTER_CANCEL" ] \
       || [ "$((COUNT_AFTER_INSERT - COUNT_BEFORE))" != "1" ]; then
        ASSERTIONS_OK=false
    fi

    if [ "$ASSERTIONS_OK" = "true" ]; then
        echo "✅ Test 5 passed: insert+cancel OK; CA count unchanged ($COUNT_AFTER_INSERT == $COUNT_AFTER_CANCEL)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ Test 5 failed: expected insert=201/succeeded=1, cancel=201/succeeded=1/status=cancelled,"
        echo "   and CA count to go BEFORE→AFTER_INSERT (+1) then stay equal after cancel."
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    fi  # end COUNT_BEFORE non-empty
    fi  # end CA_BEARER non-empty
else
    echo "⏭️  Skipping Test 5 (requires STR BEARER_TOKEN)"
fi

echo

# Summary
echo "═══════════════════════════════════════"
echo "Test Summary (bulk activities):"
echo "  Total:  $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS ✅"
echo "  Failed: $FAILED_TESTS ❌"
echo "═══════════════════════════════════════"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All bulk activity endpoint tests passed!"
    exit 0
else
    echo "❌ Some bulk activity endpoint tests failed!"
    exit 1
fi
