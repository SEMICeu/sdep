#!/usr/bin/env bash
# Print the API versions of one test, as listed in tests/api-versions.txt.
# Usage: scripts/api-versions.sh <test>   e.g. scripts/api-versions.sh test_ca_areas
# Exits 1 when the test is not listed, so a missing line fails instead of skipping.
set -euo pipefail

test_name="${1:?Usage: $0 <test> (e.g. test_ca_areas)}"
versions_file="$(cd "$(dirname "$0")/.." && pwd)/tests/api-versions.txt"

versions=$(awk -v t="$test_name" '$1 == t { $1 = ""; print; exit }' "$versions_file" | xargs)
if [ -z "$versions" ]; then
  echo "❌ $test_name is not listed in $versions_file" >&2
  exit 1
fi
echo "$versions"
