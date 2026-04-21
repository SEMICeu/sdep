#!/usr/bin/env bash
# Run all test suites with isolation checks (local docker-compose stack).
# Usage: scripts/run-tests.sh
# Requires: .env sourced, tmp/.credentials present (from .get-client-credentials)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

set -a
# shellcheck source=/dev/null
source ./.env
# shellcheck source=/dev/null
source ./tmp/.credentials
set +a
set -o pipefail

RESULTS_FILE=$(mktemp)
FAILED_TESTS_FILE=$(mktemp)
OUTPUT_FILE=$(mktemp)
SUITE_RESULTS_FILE=$(mktemp)
PRE_RAW_COUNTS_FILE=$(mktemp)
PRE_COUNTS_FILE=$(mktemp)
POST_COUNTS_FILE=$(mktemp)
trap "rm -f $RESULTS_FILE $FAILED_TESTS_FILE $OUTPUT_FILE $SUITE_RESULTS_FILE $PRE_RAW_COUNTS_FILE $PRE_COUNTS_FILE $POST_COUNTS_FILE" EXIT

echo "🧪 Running all tests..."
echo ""

# --- Helper to run a make test target and collect results ---
run_suite() {
  local suite_name="$1"

  if make --no-print-directory "$suite_name" 2>&1 | tee "$OUTPUT_FILE"; then
    grep -E "^\s*(Total|Passed|Failed):" "$OUTPUT_FILE" >> "$RESULTS_FILE" || true
  else
    grep -E "^\s*(Total|Passed|Failed):" "$OUTPUT_FILE" >> "$RESULTS_FILE" || true
    echo "$suite_name" >> "$FAILED_TESTS_FILE"
  fi

  S_TOTAL=$(grep "Total:" "$OUTPUT_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
  S_PASSED=$(grep "Passed:" "$OUTPUT_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
  S_FAILED=$(grep "Failed:" "$OUTPUT_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')

  if [ "$S_FAILED" -gt 0 ] 2>/dev/null; then S_ICON="❌"; else S_ICON="✅"; fi
  printf "📋 %-18s %3d total, %3d passed, %d failed %s\n" "$suite_name:" "$S_TOTAL" "$S_PASSED" "$S_FAILED" "$S_ICON"
  printf "%s|%d|%d|%d\n" "$suite_name" "$S_TOTAL" "$S_PASSED" "$S_FAILED" >> "$SUITE_RESULTS_FILE"
  echo ""
}

# --- Capture PRE-test row counts (RAW, before any cleanup) ---
echo "📊 Capturing PRE-test row counts (includes any leftover sdep-test-* rows)..."
docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
  -t -A -F'|' < postgres/count-app.sql > "$PRE_COUNTS_FILE"

while IFS='|' read -r tname tcount; do
  printf "    %-25s %s\n" "$tname:" "$tcount"
done < "$PRE_COUNTS_FILE"
echo ""

# --- Pre-clean leftover sdep-test-* data (unless KEEP_TEST_DATA=true) ---
# Ensures the isolation baseline is a clean slate even if a prior `make test-keep`
# left sdep-test-* rows behind. Captured internally (not displayed).
if [ "${KEEP_TEST_DATA:-false}" != "true" ]; then
  echo "🧹 Pre-cleaning leftover sdep-test-* data..."
  docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
    -v ON_ERROR_STOP=1 < postgres/clean-testrun.sql > /dev/null
fi

# Internal baseline (post pre-clean) used for the isolation check.
docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
  -t -A -F'|' < postgres/count-app.sql > "$PRE_RAW_COUNTS_FILE"

# --- Run test suites ---
run_suite test-security
run_suite test-str
run_suite test-ca

# --- Clean test data (unless KEEP_TEST_DATA=true) ---
if [ "${KEEP_TEST_DATA:-false}" = "true" ]; then
  echo "🧷 KEEP_TEST_DATA=true — skipping sdep-test-* cleanup (isolation check will be skipped)"
else
  echo "🧹 Cleaning sdep-test-* data..."
  docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
    -v ON_ERROR_STOP=1 < postgres/clean-testrun.sql
fi

# --- Capture POST-test row counts ---
echo "📊 Capturing POST-test row counts..."
docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
  -t -A -F'|' < postgres/count-app.sql > "$POST_COUNTS_FILE"

while IFS='|' read -r tname tcount; do
  printf "    %-25s %s\n" "$tname:" "$tcount"
done < "$POST_COUNTS_FILE"
echo ""

# --- Results summary ---
SUITE_COUNT=$(grep -c "Total:" "$RESULTS_FILE" 2>/dev/null || echo 0)
GRAND_TOTAL=$(grep "Total:" "$RESULTS_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
GRAND_PASSED=$(grep "Passed:" "$RESULTS_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
GRAND_FAILED=$(grep "Failed:" "$RESULTS_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
SUITES_FAILED=$(if [ -s "$FAILED_TESTS_FILE" ]; then wc -l < "$FAILED_TESTS_FILE"; else echo 0; fi)
ISOLATION_OK=true

echo ""
echo "══ TEST RESULTS ══════════════════════════════"
echo ""
echo "  Suite Results:"
while IFS='|' read -r SNAME STOT SPAS SFAI; do
  SICO=$(if [ "$SFAI" -gt 0 ] 2>/dev/null; then echo "❌"; else echo "✅"; fi)
  printf "    %-18s %3d total, %3d passed, %d failed %s\n" "$SNAME:" "$STOT" "$SPAS" "$SFAI" "$SICO"
done < "$SUITE_RESULTS_FILE"

echo ""
echo "  Grand Total:"
echo "    Test suites:  $SUITE_COUNT"
echo "    Total tests:  $GRAND_TOTAL"
echo "    Tests passed: $GRAND_PASSED ✅"
echo "    Tests failed: $GRAND_FAILED ❌"
echo ""
if [ "${KEEP_TEST_DATA:-false}" = "true" ]; then
  echo "  Test Isolation: skipped (KEEP_TEST_DATA=true)"
else
  echo "  Test Isolation (PRE/POST row counts):"
  while IFS='|' read -r PRE_NAME PRE_COUNT; do
    BASELINE_COUNT=$(grep "^$PRE_NAME|" "$PRE_RAW_COUNTS_FILE" | cut -d'|' -f2)
    POST_COUNT=$(grep "^$PRE_NAME|" "$POST_COUNTS_FILE" | cut -d'|' -f2)
    if [ "$BASELINE_COUNT" = "$POST_COUNT" ]; then
      printf "    %-25s PRE=%-5s POST=%-5s ✅\n" "$PRE_NAME:" "$PRE_COUNT" "$POST_COUNT"
    else
      printf "    %-25s PRE=%-5s POST=%-5s ❌\n" "$PRE_NAME:" "$PRE_COUNT" "$POST_COUNT"
      ISOLATION_OK=false
    fi
  done < "$PRE_COUNTS_FILE"
fi

echo ""
if [ "$ISOLATION_OK" != "true" ]; then
  echo "test-isolation" >> "$FAILED_TESTS_FILE"
fi

if [ -s "$FAILED_TESTS_FILE" ] || [ "$GRAND_FAILED" -gt 0 ]; then
  if [ -s "$FAILED_TESTS_FILE" ]; then
    echo "  Failed test suites:"
    while read -r test; do echo "    ❌ $test"; done < "$FAILED_TESTS_FILE"
    echo ""
  fi
  echo "  ❌ Some test (suites) failed!"
  exit 1
else
  echo "  ✅ All tests passed!"
fi
