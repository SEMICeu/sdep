#!/bin/sh
set -eu

# Scan a container image with Trivy and write the raw JSON report.
#
# This script does ONE thing: run the scanner. Reconciling the report against the CVE
# "explain" allowlist (docs/CVE_EXPLAINS.md) is a separate concern handled by
# scripts/check_cve_allowlist.py, which runs in a general-purpose Python runtime.
# Keeping the two apart means this step only needs the minimal Trivy image, while the
# policy gate is free to use richer tooling (json, dict comparisons) instead of awk.

case "$0" in
  */*) ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd) ;;
  *) ROOT_DIR=$(pwd) ;;
esac
cd "$ROOT_DIR"

SEVERITY=${SEVERITY:-CRITICAL,HIGH,MEDIUM,LOW,UNKNOWN}
OUTPUT_DIR=${OUTPUT_DIR:-tmp/trivy-scan}

case "$OUTPUT_DIR" in
  /*)
    echo "ERROR: OUTPUT_DIR must be relative to the repository root."
    exit 1
    ;;
esac

mkdir -p "$OUTPUT_DIR"

# When this runs in a container as root against a bind-mounted repo (local
# `make test-cve`), any file written under $OUTPUT_DIR is created root-owned on the
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

echo "Wrote Trivy report to $RESULTS_JSON"
echo "Reconcile it against the allowlist with: scripts/check_cve_allowlist.py $RESULTS_JSON"
