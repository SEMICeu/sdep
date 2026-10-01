#!/usr/bin/env bash
# Print the test runs of one environment from tests/suites.txt, in file order.
# Usage: scripts/suites.sh <env> [<suite>]   e.g. scripts/suites.sh tst, scripts/suites.sh dev ca
# Output: one line per run, "<suite> <client> <test> <version>" (- = no login / unversioned).
# Exits 1 when the environment has no column, or when nothing matches.
set -euo pipefail

env_name="${1:?Usage: $0 <env> [<suite>] (e.g. tst)}"
suite="${2:-}"
suites_file="$(cd "$(dirname "$0")/.." && pwd)/tests/suites.txt"

# The header is the last comment line that starts with "# suite"; its column names
# locate the environment, so environments can be added or removed.
runs=$(awk -v env="${env_name^^}" -v suite="$suite" '
  /^# suite / { col = 0; for (i = 2; i <= NF; i++) if ($i == env) col = i - 1; next }
  /^#/ || NF == 0 { next }
  col == 0 { print "❌ No column " env " in the header of tests/suites.txt" > "/dev/stderr"; exit 1 }
  $col == "x" && (suite == "" || $1 == suite) { print $1, $2, $3, $4 }
' "$suites_file")

if [ -z "$runs" ]; then
  echo "❌ No test runs for env=${env_name}${suite:+ suite=$suite} in $suites_file" >&2
  exit 1
fi
echo "$runs"
