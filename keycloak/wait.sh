#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

# Load environment variables if .env exists
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

echo "⏳ Waiting for Keycloak to be ready (may take some time to complete)..."

# Keep waits bounded so startup issues fail fast with clear diagnostics
POLL_SECONDS="${KC_WAIT_POLL_SECONDS:-2}"
HTTP_TIMEOUT_SECONDS="${KC_WAIT_HTTP_TIMEOUT_SECONDS:-180}"
OIDC_TIMEOUT_SECONDS="${KC_WAIT_OIDC_TIMEOUT_SECONDS:-120}"
AUTH_MAX_RETRIES="${KC_WAIT_AUTH_MAX_RETRIES:-30}"
KC_CONTAINER_NAME="${KC_CONTAINER_NAME:-sdep-keycloak}"
DIAG_INTERVAL=30  # print diagnostics every N seconds

_kc_diagnostics() {
    echo "" >&2
    echo "── Keycloak container state ──────────────────────────" >&2
    docker inspect --format='  Status:     {{.State.Status}}
  Running:    {{.State.Running}}
  ExitCode:   {{.State.ExitCode}}
  Error:      {{.State.Error}}
  StartedAt:  {{.State.StartedAt}}
  FinishedAt: {{.State.FinishedAt}}' "${KC_CONTAINER_NAME}" 2>&1 >&2 || echo "  (could not inspect container)" >&2
    echo "" >&2
    echo "── Last 50 Keycloak log lines ────────────────────────" >&2
    docker logs --tail 50 "${KC_CONTAINER_NAME}" 2>&1 >&2 || echo "  (could not retrieve logs)" >&2
    echo "──────────────────────────────────────────────────────" >&2
}

# First wait for HTTP endpoint
HTTP_WAIT_START=$(date +%s)
LAST_DIAG=$HTTP_WAIT_START
until curl -sf "${KC_BASE_URL}" > /dev/null 2>&1; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - HTTP_WAIT_START))
    if [ "$ELAPSED" -ge "$HTTP_TIMEOUT_SECONDS" ]; then
        echo "" >&2
        echo "❌ Timed out waiting for Keycloak HTTP endpoint" >&2
        echo "  URL: ${KC_BASE_URL}" >&2
        echo "  Timeout: ${HTTP_TIMEOUT_SECONDS}s" >&2
        _kc_diagnostics
        exit 1
    fi
    # Periodic progress report
    SINCE_DIAG=$((NOW - LAST_DIAG))
    if [ "$SINCE_DIAG" -ge "$DIAG_INTERVAL" ]; then
        echo "" >&2
        echo "  [${ELAPSED}s elapsed] Still waiting for ${KC_BASE_URL} ..." >&2
        CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' "${KC_CONTAINER_NAME}" 2>/dev/null || echo "unknown")
        echo "  Container status: ${CONTAINER_STATUS}" >&2
        LAST_DIAG=$NOW
    fi
    printf "."
    sleep "$POLL_SECONDS"
done

# Then wait for admin API to be ready by checking the master realm endpoint
OIDC_WAIT_START=$(date +%s)
until curl -sf "${KC_BASE_URL}/realms/master/.well-known/openid-configuration" > /dev/null 2>&1; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - OIDC_WAIT_START))
    if [ "$ELAPSED" -ge "$OIDC_TIMEOUT_SECONDS" ]; then
        echo "" >&2
        echo "❌ Timed out waiting for Keycloak OpenID configuration endpoint" >&2
        echo "  URL: ${KC_BASE_URL}/realms/master/.well-known/openid-configuration" >&2
        echo "  Timeout: ${OIDC_TIMEOUT_SECONDS}s" >&2
        exit 1
    fi
    printf "."
    sleep "$POLL_SECONDS"
done

# Finally, verify we can authenticate
MAX_RETRIES="$AUTH_MAX_RETRIES"
RETRY_COUNT=0
until [ $RETRY_COUNT -ge $MAX_RETRIES ]; do
    TOKEN_RESPONSE=$(curl -sf -X POST "${KC_BASE_URL}/realms/master/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=${KC_ADMIN_REALM_ADMIN_USERNAME}" \
        -d "password=${KC_ADMIN_REALM_ADMIN_PASSWORD}" \
        -d "grant_type=password" \
        -d "client_id=admin-cli" 2>&1 || echo "")

    if echo "$TOKEN_RESPONSE" | grep -q "access_token"; then
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        printf "."
        sleep "$POLL_SECONDS"
    fi
done

if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "" >&2
    echo "❌ Failed to authenticate with Keycloak after $MAX_RETRIES retries" >&2
    echo "" >&2
    echo "Configuration used:" >&2
    echo "  KC_BASE_URL: ${KC_BASE_URL}" >&2
    echo "  KC_ADMIN_REALM_ADMIN_USERNAME: ${KC_ADMIN_REALM_ADMIN_USERNAME}" >&2
    echo "  KC_ADMIN_REALM_ADMIN_PASSWORD: (${#KC_ADMIN_REALM_ADMIN_PASSWORD} characters)" >&2
    echo "" >&2
    echo "💡 Suggestion: KC_ADMIN_REALM_ADMIN_USERNAME and KC_ADMIN_REALM_ADMIN_PASSWORD should be" >&2
    echo "   the username and password of a Keycloak admin user in the master realm." >&2
    exit 1
fi

echo "✅ Keycloak is ready!"
