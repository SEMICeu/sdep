#!/usr/bin/env bash
# Run performance tests with Locust (local docker-compose stack).
# Usage: scripts/run-tests-perf.sh
# Requires: .env sourced, tmp/.credentials present (from .get-client-credentials)
# All PERF_* variables can be set via environment.
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

# --- Defaults ---
P_ACTIVITIES_PER_DAY="${PERF_ACTIVITIES_TARGET:-5000}"
P_USERS="${PERF_USERS:-10}"
P_RAMP_UP="${PERF_RAMP_UP:-1}"
P_DURATION_SECONDS="${PERF_MAX_DURATION_SECONDS:-300}"
P_BATCH_SIZE="${PERF_BATCH_SIZE:-1000}"
P_KEEP_DATA="${PERF_KEEP_DATA:-false}"
P_STOP_ON_TARGET="${PERF_STOP_ON_TARGET:-true}"
P_YES="${PERF_YES:-false}"

# --- Show configuration ---
echo "🚀 Bulk performance test"
echo ""
printf "   %-27s = %-10s (%s)\n" "PERF_ACTIVITIES_TARGET" "$P_ACTIVITIES_PER_DAY" "target volume"
printf "   %-27s = %-10s (%s)\n" "PERF_USERS" "$P_USERS" "concurrent users to reach the target volume"
printf "   %-27s = %-10s (%s)\n" "PERF_RAMP_UP" "$P_RAMP_UP" "users spawned per second"
printf "   %-27s = %-10s (%s)\n" "PERF_MAX_DURATION_SECONDS" "$P_DURATION_SECONDS" "max. test duration in seconds"
printf "   %-27s = %-10s (%s)\n" "PERF_BATCH_SIZE" "$P_BATCH_SIZE" "activities per HTTP request"
printf "   %-27s = %-10s (%s)\n" "PERF_KEEP_DATA" "$P_KEEP_DATA" "keep data in database"
printf "   %-27s = %-10s (%s)\n" "PERF_STOP_ON_TARGET" "$P_STOP_ON_TARGET" "stop early when target reached"
echo ""
echo "   Override: make test-perf PERF_ACTIVITIES_TARGET=4000000 PERF_USERS=10 PERF_RAMP_UP=2 PERF_MAX_DURATION_SECONDS=600 PERF_BATCH_SIZE=1000 PERF_STOP_ON_TARGET=true PERF_YES=true"
echo ""

# --- Interactive confirmation ---
if [ "$P_YES" != "true" ]; then
  read -p "   Continue with these settings? [Y/n] " answer
  case "$answer" in
    [nN]*)
      echo ""
      read -p "   PERF_ACTIVITIES_TARGET    [$P_ACTIVITIES_PER_DAY]: " val && [ -n "$val" ] && P_ACTIVITIES_PER_DAY=$val
      read -p "   PERF_USERS                [$P_USERS]: " val && [ -n "$val" ] && P_USERS=$val
      read -p "   PERF_RAMP_UP              [$P_RAMP_UP]: " val && [ -n "$val" ] && P_RAMP_UP=$val
      read -p "   PERF_MAX_DURATION_SECONDS [$P_DURATION_SECONDS]: " val && [ -n "$val" ] && P_DURATION_SECONDS=$val
      read -p "   PERF_BATCH_SIZE           [$P_BATCH_SIZE]: " val && [ -n "$val" ] && P_BATCH_SIZE=$val
      read -p "   PERF_KEEP_DATA            [$P_KEEP_DATA]: " val && [ -n "$val" ] && P_KEEP_DATA=$val
      read -p "   PERF_STOP_ON_TARGET       [$P_STOP_ON_TARGET]: " val && [ -n "$val" ] && P_STOP_ON_TARGET=$val
      echo ""
      ;;
  esac
fi

echo ""

# --- Create fixture areas ---
echo "📦 Creating fixture areas for performance test..."
PERF_AREA_IDS=$(./tests/lib/create_fixture_areas.sh 5 "sdep-test-perf-areas" 2>/dev/null | tr '\n' ',' | sed 's/,$//')
echo "✅ Areas created"
echo ""

# --- Verify STR client authorization ---
echo "   Concurrent users: $P_USERS"
echo ""
if CLIENT_ID=$STR_CLIENT_ID CLIENT_SECRET=$STR_CLIENT_SECRET ./tests/test_auth_client.sh > /dev/null 2>&1; then
  echo "✅ STR client authorized"
else
  echo "❌ STR client authorization failed"
  exit 1
fi
echo ""

# --- Run Locust ---
export PERF_BATCH_SIZE=$P_BATCH_SIZE
export PERF_ACTIVITIES_TARGET=$P_ACTIVITIES_PER_DAY
export PERF_KEEP_DATA=$P_KEEP_DATA
export PERF_STOP_ON_TARGET=$P_STOP_ON_TARGET
export PERF_USERS=$P_USERS
export STR_CLIENT_ID=$STR_CLIENT_ID
export STR_CLIENT_SECRET=$STR_CLIENT_SECRET
export PERF_AREA_IDS=$PERF_AREA_IDS

echo "⏳ Spawning users and running tests (please be patient)..."
echo ""

P_VERBOSE="${PERF_VERBOSE:-false}"
LOCUST_EXTRA_ARGS=()
if [ "$P_VERBOSE" != "true" ]; then
  LOCUST_EXTRA_ARGS+=(--only-summary)
fi

EXIT_CODE=0
uvx --from 'locust>=2.20' locust -f tests/perf/locustfile.py \
  --headless \
  --host "$BACKEND_BASE_URL" \
  -u "$P_USERS" \
  -r "$P_RAMP_UP" \
  --run-time "${P_DURATION_SECONDS}s" \
  "${LOCUST_EXTRA_ARGS[@]}" \
  </dev/null || EXIT_CODE=$?

# --- Cleanup ---
if [ "$P_KEEP_DATA" != "true" ]; then
  echo "🧹 Cleaning up test data (PERF_KEEP_DATA=false)..."
  docker exec -i sdep-postgres psql -U "$POSTGRES_SUPER_USER" -d "$POSTGRES_DB_NAME" \
    -v ON_ERROR_STOP=1 < postgres/clean-testrun.sql > /dev/null 2>&1
  echo "✅ Test data cleaned"
fi

exit $EXIT_CODE
