#!/bin/bash

# Regression test: the default client-ID regex must reject a literal backslash.
#
# The Keycloak machine-client script validates client IDs with bash `[[ =~ ]]`,
# which uses POSIX ERE. Inside a bracket expression bash treats a backslash as a
# *literal* character, so writing the pattern as `[A-Za-z0-9._\-]` accidentally
# allows a backslash in the allowed set. This test reads the default regex from the
# shell script and verifies bash accepts valid IDs and rejects backslash IDs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_SCRIPT="${SCRIPT_DIR}/../keycloak/add-realm-machine-clients.sh"

if [ ! -f "$TARGET_SCRIPT" ]; then
    echo "❌ Cannot find ${TARGET_SCRIPT}"
    exit 1
fi

# Extract the default regex from:  .config.clientid_regex // "<regex>"
CLIENTID_REGEX=$(grep -oE 'clientid_regex[^"]*"[^"]*"' "$TARGET_SCRIPT" | grep -oE '"[^"]*"$' | tr -d '"')

if [ -z "$CLIENTID_REGEX" ]; then
    echo "❌ Could not extract default clientid_regex from ${TARGET_SCRIPT}"
    exit 1
fi

echo "🔎 Testing default clientid_regex: ${CLIENTID_REGEX}"

VALID_IDS=("sdep.client_1" "abc-123" "a.b-c_d")
BAD_IDS=("my\\client" "a\\b" "\\")

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

for id in "${VALID_IDS[@]}"; do
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [[ "$id" =~ $CLIENTID_REGEX ]]; then
        echo "✅ accepted (expected): '$id'"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ rejected but should be accepted: '$id'"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
done

for id in "${BAD_IDS[@]}"; do
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [[ "$id" =~ $CLIENTID_REGEX ]]; then
        echo "❌ accepted but should be rejected (backslash): '$id'"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    else
        echo "✅ rejected (expected): '$id'"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    fi
done

echo ""
echo "  Total:  $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS ✅"
echo "  Failed: $FAILED_TESTS ❌"

if [ "$FAILED_TESTS" -ne 0 ]; then
    echo "❌ client-ID regex test FAILED"
    exit 1
fi

echo "✅ client-ID regex test passed"
