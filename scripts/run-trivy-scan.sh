#!/bin/sh
set -eu

case "$0" in
  */*) ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd) ;;
  *) ROOT_DIR=$(pwd) ;;
esac
cd "$ROOT_DIR"

SEVERITY=${SEVERITY:-CRITICAL,HIGH,MEDIUM,LOW,UNKNOWN}
OUTPUT_DIR=${OUTPUT_DIR:-tmp/trivy-scan}
PYTHON_IMAGE=${PYTHON_IMAGE:-python:3.13-slim}
IMAGE_TAG=${IMAGE_TAG:-trivy-local}

case "$OUTPUT_DIR" in
  /*)
    echo "ERROR: OUTPUT_DIR must be relative to the repository root."
    exit 1
    ;;
esac

mkdir -p "$OUTPUT_DIR"

# When this runs in a container as root against a bind-mounted repo (local
# `make trivy`), any file written under $OUTPUT_DIR is created root-owned on the
# host. That later breaks non-root writes elsewhere under tmp/ (e.g.
# tmp/KC_APP_REALM_ADMIN_SECRET.txt during `make up`). If the caller passes its
# host UID/GID, hand ownership of the output back on exit. No-op in CI, where the
# job runs directly (not root over a bind mount) and HOST_UID is unset.
restore_output_ownership() {
  if [ -n "${HOST_UID:-}" ] && [ "$(id -u)" = "0" ]; then
    chown -R "${HOST_UID}:${HOST_GID:-$HOST_UID}" "$OUTPUT_DIR" 2>/dev/null || true
  fi
}
trap restore_output_ownership EXIT

RESULTS_JSON="$OUTPUT_DIR/trivy-results.json"
FOUND_CVES="$OUTPUT_DIR/found-cves.txt"
ALLOWED_CVES="$OUTPUT_DIR/allowed-cves.txt"
MATCHED_CVES="$OUTPUT_DIR/matched-cves.txt"
STALE_CVES="$OUTPUT_DIR/stale-cves.txt"
UNALLOWED_CVES="$OUTPUT_DIR/unallowed-cves.txt"
CVE_PKG_MAP="$OUTPUT_DIR/cve-pkg-map.txt"
UNALLOWED_DETAILS="$OUTPUT_DIR/unallowed-cves-details.txt"

require_command() {
  command_name=$1
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR: '$command_name' is required."
    exit 1
  fi
}

if [ -z "${TRIVY_INPUT:-}" ] && [ -z "${IMAGE:-}" ]; then
  echo "ERROR: Either IMAGE or TRIVY_INPUT must be set."
  exit 1
fi

if [ -n "${DOCKER_AUTH_CONFIG:-}" ]; then
  mkdir -p "$HOME/.docker"
  printf '%s' "$DOCKER_AUTH_CONFIG" > "$HOME/.docker/config.json"
fi

require_command trivy

echo "=== Trivy CVE scan ($SEVERITY) ==="
rm -f "$RESULTS_JSON"

if [ -n "${TRIVY_INPUT:-}" ]; then
  echo "Scanning image archive $TRIVY_INPUT"
  trivy image --input "$TRIVY_INPUT" \
    --severity "$SEVERITY" \
    --format json \
    --output "$RESULTS_JSON"
else
  echo "Scanning image $IMAGE"
  trivy image "$IMAGE" \
    --severity "$SEVERITY" \
    --format json \
    --output "$RESULTS_JSON"
fi

if [ ! -s "$RESULTS_JSON" ]; then
  echo "ERROR: Trivy did not write results to $RESULTS_JSON."
  exit 1
fi

awk '
  /"VulnerabilityID"[[:space:]]*:/ {
    line=$0
    sub(/.*"VulnerabilityID"[[:space:]]*:[[:space:]]*"/, "", line)
    sub(/".*/, "", line)
    if (line ~ /^CVE-[0-9][0-9][0-9][0-9]-[0-9][0-9]*$/) {
      found[line]=1
    }
  }
  END {
    for (cve in found) {
      print cve
    }
  }
' "$RESULTS_JSON" | sort -u > "$FOUND_CVES"

awk '
  /"VulnerabilityID"[[:space:]]*:/ {
    line=$0
    sub(/.*"VulnerabilityID"[[:space:]]*:[[:space:]]*"/, "", line)
    sub(/".*/, "", line)
    if (line ~ /^CVE-[0-9][0-9][0-9][0-9]-[0-9][0-9]*$/) {
      cve=line
    } else {
      cve=""
    }
  }
  /"PkgName"[[:space:]]*:/ && cve != "" {
    line=$0
    sub(/.*"PkgName"[[:space:]]*:[[:space:]]*"/, "", line)
    sub(/".*/, "", line)
    key=cve "\t" line
    if (!seen[key]++) {
      print key
    }
    cve=""
  }
' "$RESULTS_JSON" | sort -u > "$CVE_PKG_MAP"

grep -Eo 'CVE-[0-9]{4}-[0-9]+' docs/CVE_EXPLAINS.md 2>/dev/null | sort -u > "$ALLOWED_CVES" || touch "$ALLOWED_CVES"

comm -23 "$FOUND_CVES" "$ALLOWED_CVES" > "$UNALLOWED_CVES"
comm -12 "$FOUND_CVES" "$ALLOWED_CVES" > "$MATCHED_CVES"
comm -23 "$ALLOWED_CVES" "$FOUND_CVES" > "$STALE_CVES"

grep -Ff "$UNALLOWED_CVES" "$CVE_PKG_MAP" > "$UNALLOWED_DETAILS" || true

echo ""
echo "=== Current docs/CVE_EXPLAINS.md ==="
cat docs/CVE_EXPLAINS.md
echo ""
echo "=== Trivy results summary ==="
printf 'Total CVEs found: '
wc -l < "$FOUND_CVES" | tr -d ' '
echo ""

if [ -s "$MATCHED_CVES" ]; then
  echo "--- ALLOWED (on allowlist) ---"
  cat "$MATCHED_CVES"
fi

BUILD_FAILED=0

if [ -s "$UNALLOWED_CVES" ]; then
  echo "--- NOT ALLOWED (must fix or add to allowlist with justification) ---"
  cat "$UNALLOWED_CVES"
  echo ""
  echo "=== Copy-paste rows for docs/CVE_EXPLAINS.md ==="
  echo ""
  echo "| CVE ID | Package | Justification | Review by |"
  echo "| :--- | :--- | :--- | :--- |"
  while IFS="$(printf '\t')" read -r cve pkg; do
    echo "| $cve | $pkg | TODO | YYYY-MM-DD |"
  done < "$UNALLOWED_DETAILS"
  echo ""
  echo "ERROR: Unallowed CVEs detected. Fix them or add to docs/CVE_EXPLAINS.md with justification."
  BUILD_FAILED=1
fi

if [ -s "$STALE_CVES" ]; then
  echo ""
  echo "--- STALE (on allowlist but no longer reported by Trivy) ---"
  cat "$STALE_CVES"
  echo ""
  echo "ERROR: Stale CVEs found in docs/CVE_EXPLAINS.md. Remove the above CVEs from the allowlist; they are no longer reported by Trivy."
  BUILD_FAILED=1
fi

if [ "$BUILD_FAILED" -eq 1 ]; then
  exit 1
fi

echo "All found CVEs are on the allowlist and no stale entries. Build OK."
