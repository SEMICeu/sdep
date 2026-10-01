#!/usr/bin/env bash
# Print the API versions of one test, as listed in tests/suites.txt (all environments).
# Usage: scripts/api-versions.sh <test>   e.g. scripts/api-versions.sh test_ca_areas
# Exits 1 when the test has no versioned line, so a missing line fails instead of skipping.
# Kept for consuming repositories that predate scripts/suites.sh; new code uses suites.sh.
set -euo pipefail

test_name="${1:?Usage: $0 <test> (e.g. test_ca_areas)}"
suites_file="$(cd "$(dirname "$0")/.." && pwd)/tests/suites.txt"

versions=$(awk -v t="$test_name" '
  /^#/ || NF == 0 { next }
  $3 == t && $4 != "-" && !seen[$4]++ { printf "%s ", $4 }
' "$suites_file" | xargs -n1 | sort -V | xargs)
if [ -z "$versions" ]; then
  echo "❌ $test_name has no API versions in $suites_file" >&2
  exit 1
fi
echo "$versions"
