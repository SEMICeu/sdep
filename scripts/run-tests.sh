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
BASELINE_COUNTS_FILE=$(mktemp)
RAW_COUNTS_FILE=$(mktemp)
AFTER_COUNTS_FILE=$(mktemp)
trap "rm -f $RESULTS_FILE $FAILED_TESTS_FILE $OUTPUT_FILE $SUITE_RESULTS_FILE $BASELINE_COUNTS_FILE $RAW_COUNTS_FILE $AFTER_COUNTS_FILE" EXIT

echo "🧪 Running all tests..."
echo ""

# --- Helper to run a make test target and collect results ---
run_suite() {
  local suite_name="$1"

  if make --no-print-directory "$suite_name" 2>&1 | tee "$OUTPUT_FILE"; then
    grep -E "^\s*(Total|Passed|Failed|Skipped):" "$OUTPUT_FILE" >> "$RESULTS_FILE" || true
  else
    grep -E "^\s*(Total|Passed|Failed|Skipped):" "$OUTPUT_FILE" >> "$RESULTS_FILE" || true
    echo "$suite_name" >> "$FAILED_TESTS_FILE"
  fi

  S_TOTAL=$(grep "Total:" "$OUTPUT_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
  S_PASSED=$(grep "Passed:" "$OUTPUT_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
  S_FAILED=$(grep "Failed:" "$OUTPUT_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
  S_SKIPPED=$(awk '/Skipped:/ {sum += $2} END {print sum+0}' "$OUTPUT_FILE" 2>/dev/null)

  if [ "$S_FAILED" -gt 0 ] 2>/dev/null; then S_ICON="❌"; elif [ "$S_SKIPPED" -gt 0 ]; then S_ICON="⚠️"; else S_ICON="✅"; fi
  printf "📋 %-18s %3d total, %3d passed, %d failed, %d skipped %s\n" "$suite_name:" "$S_TOTAL" "$S_PASSED" "$S_FAILED" "$S_SKIPPED" "$S_ICON"
  printf "%s|%d|%d|%d|%d\n" "$suite_name" "$S_TOTAL" "$S_PASSED" "$S_FAILED" "$S_SKIPPED" >> "$SUITE_RESULTS_FILE"
  echo ""
}

# --- Capture PRE-test row counts (RAW, before any cleanup) ---
echo "📊 Capturing BEFORE-test row counts (includes any leftover sdep-test-* rows)..."
docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
  -t -A -F'|' < postgres/count-app.sql > "$RAW_COUNTS_FILE"

while IFS='|' read -r tname tcount; do
  printf "    %-25s %s\n" "$tname:" "$tcount"
done < "$RAW_COUNTS_FILE"
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
  -t -A -F'|' < postgres/count-app.sql > "$BASELINE_COUNTS_FILE"

# --- Run test suites ---
# One make target per suite in tests/suites.txt (DEV column), in file order.
for suite in $(scripts/suites.sh dev | awk '{ print $1 }' | uniq); do
  run_suite "test-$suite"
done

# --- Clean test data (unless KEEP_TEST_DATA=true) ---
if [ "${KEEP_TEST_DATA:-false}" = "true" ]; then
  echo "🧷 KEEP_TEST_DATA=true — skipping sdep-test-* cleanup (isolation check will be skipped)"
else
  echo "🧹 Cleaning sdep-test-* data..."
  docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
    -v ON_ERROR_STOP=1 < postgres/clean-testrun.sql
fi

# --- Capture POST-test row counts ---
echo "📊 Capturing AFTER-test row counts..."
docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
  -t -A -F'|' < postgres/count-app.sql > "$AFTER_COUNTS_FILE"

while IFS='|' read -r tname tcount; do
  printf "    %-25s %s\n" "$tname:" "$tcount"
done < "$AFTER_COUNTS_FILE"
echo ""

# --- Results summary ---
SUITE_COUNT=$(grep -c "Total:" "$RESULTS_FILE" 2>/dev/null || echo 0)
GRAND_TOTAL=$(grep "Total:" "$RESULTS_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
GRAND_PASSED=$(grep "Passed:" "$RESULTS_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
GRAND_FAILED=$(grep "Failed:" "$RESULTS_FILE" 2>/dev/null | awk '{sum += $2} END {print sum+0}')
GRAND_SKIPPED=$(awk '/Skipped:/ {sum += $2} END {print sum+0}' "$RESULTS_FILE" 2>/dev/null)
SUITES_FAILED=$(if [ -s "$FAILED_TESTS_FILE" ]; then wc -l < "$FAILED_TESTS_FILE"; else echo 0; fi)
ISOLATION_OK=true

echo ""
echo "══ TEST RESULTS ══════════════════════════════"
echo ""
echo "  Suite Results:"
while IFS='|' read -r SNAME STOT SPAS SFAI SSKI; do
  SICO=$(if [ "$SFAI" -gt 0 ] 2>/dev/null; then echo "❌"; elif [ "$SSKI" -gt 0 ]; then echo "⚠️"; else echo "✅"; fi)
  printf "    %-18s %3d total, %3d passed, %d failed, %d skipped %s\n" "$SNAME:" "$STOT" "$SPAS" "$SFAI" "$SSKI" "$SICO"
done < "$SUITE_RESULTS_FILE"

echo ""
echo "  Grand Total:"
echo "    Test suites:  $SUITE_COUNT"
echo "    Total tests:  $GRAND_TOTAL"
echo "    Tests passed: $GRAND_PASSED ✅"
echo "    Tests failed: $GRAND_FAILED ❌"
# A skip (no sample data, no credentials) is not a failure, but is shown so it is noticed
echo "    Tests skipped: $GRAND_SKIPPED ⚠️"
echo ""
if [ "${KEEP_TEST_DATA:-false}" = "true" ]; then
  echo "  Test Isolation: skipped (KEEP_TEST_DATA=true)"
else
  # BEFORE is the baseline after the pre-clean, the number that AFTER is compared with.
  # The raw count (leftovers of an earlier keep run included) is shown only when it differs.
  echo "  Test Isolation (BEFORE/AFTER row counts):"
  while IFS='|' read -r TABLE_NAME BASELINE_COUNT; do
    RAW_COUNT=$(grep "^$TABLE_NAME|" "$RAW_COUNTS_FILE" | cut -d'|' -f2)
    AFTER_COUNT=$(grep "^$TABLE_NAME|" "$AFTER_COUNTS_FILE" | cut -d'|' -f2)
    RAW_NOTE=""
    if [ "$RAW_COUNT" != "$BASELINE_COUNT" ]; then RAW_NOTE=" (before pre-clean: $RAW_COUNT)"; fi
    if [ "$BASELINE_COUNT" = "$AFTER_COUNT" ]; then
      printf "    %-25s BEFORE=%-5s AFTER=%-5s ✅%s\n" "$TABLE_NAME:" "$BASELINE_COUNT" "$AFTER_COUNT" "$RAW_NOTE"
    else
      printf "    %-25s BEFORE=%-5s AFTER=%-5s ❌%s\n" "$TABLE_NAME:" "$BASELINE_COUNT" "$AFTER_COUNT" "$RAW_NOTE"
      ISOLATION_OK=false
    fi
  done < "$BASELINE_COUNTS_FILE"
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
