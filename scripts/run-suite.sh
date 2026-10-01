#!/usr/bin/env bash
# Run one suite of tests/suites.txt against the local stack (DEV), stop at the first failure.
# Usage: scripts/run-suite.sh <suite>   e.g. scripts/run-suite.sh ca
# Requires: .env sourced, and tmp/.credentials for a suite with a client (see make test-<suite>).
set -euo pipefail

suite="${1:?Usage: $0 <suite> (e.g. ca)}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

runs=$(scripts/suites.sh dev "$suite")
client=$(echo "$runs" | awk '{ print $2; exit }')

echo "🧪 Testing suite ${suite}..."
echo "BACKEND_BASE_URL: $BACKEND_BASE_URL"
echo ""

if [ "$client" != "-" ]; then
  id_var="${client}_CLIENT_ID"
  secret_var="${client}_CLIENT_SECRET"
  if CLIENT_ID="${!id_var:-}" CLIENT_SECRET="${!secret_var:-}" uv run --script tests/test_auth_client_bootstrap.py; then
    echo "✅ ${client} client authorized"
  else
    echo "❌ ${client} client authorization failed"
    exit 1
  fi
fi

# The loop reads the runs from stdin, so the tests get /dev/null instead.
while read -r _ _ test version; do
  if [ "$version" = "-" ]; then
    uv run --script "tests/${test}.py" < /dev/null
  else
    API_VERSION="$version" uv run --script "tests/${test}.py" < /dev/null
  fi
done <<< "$runs"

echo "✅ Suite ${suite} tested!"
