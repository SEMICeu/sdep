#!/bin/bash
# Creates N fixture areas with sdep-test-* IDs using CA credentials.
# Usage: create_fixture_areas.sh [count] [prefix]
# Outputs area IDs to stdout (one per line). Errors to stderr.
# Requires env: BACKEND_BASE_URL, API_VERSION
# Uses ephemeral test CA client (sdep-test-ca01) so all created rows match sdep-test-* for cleanup

set -e
COUNT=${1:-3}
PREFIX=${2:-"sdep-test-fixture-area"}
API_VERSION=${API_VERSION:-v1}
TIMESTAMP=$(date +%s%N | cut -b1-13)

# Use ephemeral test CA client
FIXTURE_CA_CLIENT_ID="${CA1_CLIENT_ID}"
FIXTURE_CA_CLIENT_SECRET="${CA1_CLIENT_SECRET}"

# Get CA token (local variable only -does not modify ./tmp/.bearer_token)
CA_TOKEN=$(curl -s -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=${FIXTURE_CA_CLIENT_ID}" \
  --data-urlencode "client_secret=${FIXTURE_CA_CLIENT_SECRET}" \
  "${BACKEND_BASE_URL}/api/auth/${API_VERSION}/token" \
  | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"\([^"]*\)"/\1/')

if [ -z "$CA_TOKEN" ]; then
  echo "ERROR: Failed to get CA token for fixture creation" >&2
  exit 1
fi

# Read shapefile
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHAPEFILE_PATH="$SCRIPT_DIR/../../test-data/shapefiles/Amsterdam.zip"

# Create areas individually via single-item multipart/form-data endpoint
for i in $(seq 1 $COUNT); do
  AREA_ID="${PREFIX}-${TIMESTAMP}-${i}"

  response=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Authorization: Bearer ${CA_TOKEN}" \
    -F "file=@${SHAPEFILE_PATH}" \
    -F "areaId=${AREA_ID}" \
    "${BACKEND_BASE_URL}/api/ca/${API_VERSION}/areas")

  http_code=$(echo "$response" | tail -n1)
  if [ "$http_code" -ne 201 ]; then
    body=$(echo "$response" | sed '$d')
    echo "ERROR: Failed to create fixture area ${AREA_ID} (HTTP $http_code): $body" >&2
    exit 1
  fi
done

# Output area IDs to stdout
for i in $(seq 1 $COUNT); do
  echo "${PREFIX}-${TIMESTAMP}-${i}"
done
