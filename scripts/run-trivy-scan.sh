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

EXPLAINS_MD=docs/CVE_EXPLAINS.md

RESULTS_JSON="$OUTPUT_DIR/trivy-results.json"
FOUND_CVES="$OUTPUT_DIR/found-cves.txt"
ALLOWED_CVES="$OUTPUT_DIR/allowed-cves.txt"
MATCHED_CVES="$OUTPUT_DIR/matched-cves.txt"
STALE_CVES="$OUTPUT_DIR/stale-cves.txt"
UNALLOWED_CVES="$OUTPUT_DIR/unallowed-cves.txt"
CVE_PKG_SEV_RAW="$OUTPUT_DIR/cve-pkg-sev.raw"
CVE_PKG_SEV="$OUTPUT_DIR/cve-pkg-sev.txt"
CVE_PKG_MAP="$OUTPUT_DIR/cve-pkg-map.txt"
UNALLOWED_DETAILS="$OUTPUT_DIR/unallowed-cves-details.txt"
DOCUMENTED_CVES="$OUTPUT_DIR/documented-cves.txt"
DRIFT="$OUTPUT_DIR/allowlist-drift.txt"

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

# Flatten the report to "<cve> <pkg> <severity>" triples. Rendered by Trivy itself
# rather than scraped out of the JSON: package names never contain spaces, so the
# result stays trivially parseable, and the field semantics come from Trivy instead
# of from assumptions about key ordering in the JSON.
# Deliberately not piped: `set -e` only inspects the LAST command of a pipeline, so
# a failing trivy followed by a succeeding sort would be ignored, leaving an empty
# file that reads downstream as "no CVEs found".
trivy convert \
  --format template \
  --template '{{ range . }}{{ range .Vulnerabilities }}{{ .VulnerabilityID }} {{ .PkgName }} {{ .Severity }}{{ println }}{{ end }}{{ end }}' \
  "$RESULTS_JSON" > "$CVE_PKG_SEV_RAW"

# A report that contains findings must never flatten to nothing. Without this, any
# failure to read the report is indistinguishable from a clean image: every allowlist
# row is declared stale, and on an empty allowlist the scan passes having checked
# nothing at all.
if grep -q '"VulnerabilityID"' "$RESULTS_JSON" && [ ! -s "$CVE_PKG_SEV_RAW" ]; then
  echo "ERROR: Trivy reported vulnerabilities in $RESULTS_JSON, but converting them"
  echo "       produced no rows. Refusing to continue - an empty result here would be"
  echo "       reported as 'no CVEs found'."
  exit 1
fi

# grep exits 1 when nothing matches, which is legitimate: a report can hold only
# non-CVE identifiers (Trivy emits TEMP-* ids for some Debian issues). The assertion
# above is what separates that from a genuine failure.
grep -E '^CVE-[0-9]{4}-[0-9]+ ' "$CVE_PKG_SEV_RAW" | sort -u > "$CVE_PKG_SEV" || true

awk '{ print $1 }' "$CVE_PKG_SEV" | sort -u > "$FOUND_CVES"
awk '{ printf "%s\t%s\n", $1, $2 }' "$CVE_PKG_SEV" | sort -u > "$CVE_PKG_MAP"

# Parse the allowlist tables into "<cve> <pkg> <section>" triples. Only rows whose
# first cell is a CVE id count, so CVE ids mentioned inside prose or a justification
# never silently become allowlist entries.
awk '
  function trim(s) {
    gsub(/^[ \t]+/, "", s)
    gsub(/[ \t]+$/, "", s)
    return s
  }
  /^##[[:space:]]+/ {
    section = toupper(trim(substr($0, 4)))
    next
  }
  /^\|[[:space:]]*CVE-[0-9]+-[0-9]+[[:space:]]*\|/ {
    n = split($0, cell, "|")
    if (n < 4) next
    print trim(cell[2]), trim(cell[3]), section
  }
' "$EXPLAINS_MD" > "$DOCUMENTED_CVES" 2>/dev/null || : > "$DOCUMENTED_CVES"

awk '{ print $1 }' "$DOCUMENTED_CVES" | sort -u > "$ALLOWED_CVES"

comm -23 "$FOUND_CVES" "$ALLOWED_CVES" > "$UNALLOWED_CVES"
comm -12 "$FOUND_CVES" "$ALLOWED_CVES" > "$MATCHED_CVES"
comm -23 "$ALLOWED_CVES" "$FOUND_CVES" > "$STALE_CVES"

grep -Ff "$UNALLOWED_CVES" "$CVE_PKG_MAP" > "$UNALLOWED_DETAILS" || true

# Cross-check what the allowlist claims against what Trivy actually reported. A row
# naming the wrong package carries a justification for the wrong software (an entry
# reading "SDEP does not use GnuTLS" for what is really a glibc flaw explains
# nothing), and a row filed under the wrong severity misstates how urgent it is.
# Neither is visible to the id-only allow/stale comparison above.
awk '
  NR == FNR {
    pkgs[$1] = pkgs[$1] " " $2
    sevs[$1] = sevs[$1] " " $3
    next
  }
  {
    cve = $1; pkg = $2; section = $3
    if (++seen[cve] == 2) {
      printf "DUP %s is listed more than once; keep a single row\n", cve
    }
    if (!(cve in pkgs)) next
    if (index(pkgs[cve] " ", " " pkg " ") == 0) {
      printf "PKG %s documented as \"%s\" but Trivy reports it for:%s\n", cve, pkg, pkgs[cve]
    }
    if (index(sevs[cve] " ", " " section " ") == 0) {
      printf "SEV %s filed under \"%s\" but Trivy rates it:%s\n", cve, section, sevs[cve]
    }
  }
' "$CVE_PKG_SEV" "$DOCUMENTED_CVES" | sort -u > "$DRIFT"

echo ""
echo "=== Current $EXPLAINS_MD ==="
cat "$EXPLAINS_MD"
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
  echo "=== Copy-paste rows for $EXPLAINS_MD ==="
  echo ""
  echo "| CVE ID | Package | Justification | Review by |"
  echo "| :--- | :--- | :--- | :--- |"
  while IFS="$(printf '\t')" read -r cve pkg; do
    echo "| $cve | $pkg | TODO | YYYY-MM-DD |"
  done < "$UNALLOWED_DETAILS"
  echo ""
  echo "ERROR: Unallowed CVEs detected. Fix them or add to $EXPLAINS_MD with justification."
  BUILD_FAILED=1
fi

if [ -s "$STALE_CVES" ]; then
  echo ""
  echo "--- STALE (on allowlist but no longer reported by Trivy) ---"
  cat "$STALE_CVES"
  echo ""
  echo "ERROR: Stale CVEs found in $EXPLAINS_MD. Remove the above CVEs from the allowlist; they are no longer reported by Trivy."
  BUILD_FAILED=1
fi

if [ -s "$DRIFT" ]; then
  echo ""
  echo "--- DRIFT (allowlist rows that disagree with the scan) ---"
  sed 's/^PKG /wrong package:  /; s/^SEV /wrong severity: /; s/^DUP /duplicate row: /' "$DRIFT"
  echo ""
  echo "ERROR: Allowlist drift detected in $EXPLAINS_MD. Correct the Package column, move the row under the heading matching the reported severity, and keep one row per CVE."
  BUILD_FAILED=1
fi

if [ "$BUILD_FAILED" -eq 1 ]; then
  exit 1
fi

echo "All found CVEs are on the allowlist, with no stale entries and no drift. Build OK."
