#!/usr/bin/env bash
set -euo pipefail

get_client_secret() {
    # Check required variables
    if [ -z "${KC_BASE_URL:-}" ]; then
        echo "❌ Error: KC_BASE_URL is not set (commandline .env* or in pipeline)" >&2
        return 1
    fi

    if [ -z "${KC_APP_REALM_CONFIG_YAML:-}" ]; then
        echo "❌ Error: KC_APP_REALM_CONFIG_YAML is not set" >&2; return 1
    fi
    if [ ! -f "${KC_APP_REALM_CONFIG_YAML}" ]; then
        echo "❌ Error: KC_APP_REALM_CONFIG_YAML not found: ${KC_APP_REALM_CONFIG_YAML}" >&2; return 1
    fi
    local REALM_NAME
    REALM_NAME=$(yq -r '.config.name' "$KC_APP_REALM_CONFIG_YAML")

    if [ -z "${KC_APP_REALM_ADMIN_ID:-}" ]; then
        echo "❌ Error: KC_APP_REALM_ADMIN_ID is not set (commandline .env* or in pipeline)" >&2
        return 1
    fi

    if [ -z "${KC_APP_REALM_ADMIN_SECRET:-}" ]; then
        echo "❌ Error: KC_APP_REALM_ADMIN_SECRET is not set (commandline .env* or in pipeline)" >&2
        return 1
    fi

    if [ -z "${KC_APP_REALM_CLIENT_ID:-}" ]; then
        echo "❌ Error: KC_APP_REALM_CLIENT_ID is not set (commandline .env* or in pipeline)" >&2
        return 1
    fi

    # Fail fast when Keycloak is unreachable (curl waits 300s by default) and retry short outages.
    local CURL_OPTS=(--connect-timeout 10 --max-time 30 --retry 3 --retry-delay 5)

    echo "🔐 Authenticating with ${KC_APP_REALM_ADMIN_ID}..."

    local TOKEN_RESPONSE=$(curl -s "${CURL_OPTS[@]}" -X POST "${KC_BASE_URL}/realms/${REALM_NAME}/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "client_id=${KC_APP_REALM_ADMIN_ID}" \
        -d "client_secret=${KC_APP_REALM_ADMIN_SECRET}" \
        -d "grant_type=client_credentials")

    local TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$TOKEN" ]; then
        echo "❌ Failed to authenticate" >&2
        echo "Response: $TOKEN_RESPONSE" >&2
        if [ -z "$TOKEN_RESPONSE" ]; then
            echo "   Empty response: Keycloak did not answer (network, DNS or timeout)" >&2
        fi
        echo "" >&2
        echo "Configuration used:" >&2
        echo "  KC_BASE_URL: ${KC_BASE_URL}" >&2
        echo "  REALM_NAME: ${REALM_NAME}" >&2
        echo "  KC_APP_REALM_ADMIN_ID: ${KC_APP_REALM_ADMIN_ID}" >&2
        echo "  KC_APP_REALM_ADMIN_SECRET: (${#KC_APP_REALM_ADMIN_SECRET} characters)" >&2
        echo "  KC_APP_REALM_CLIENT_ID: ${KC_APP_REALM_CLIENT_ID}" >&2
        echo "" >&2
        echo "💡 Suggestion: KC_APP_REALM_ADMIN_ID and KC_APP_REALM_ADMIN_SECRET should be" >&2
        echo "   the client_id and client_secret of a service account client (cicd_admin) in realm '${REALM_NAME}'" >&2
        return 1
    fi

    echo "✅ Authentication successful"
    echo "🔍 Looking up client ${KC_APP_REALM_CLIENT_ID}..."

    # Get the client UUID
    local CLIENT_CHECK=$(curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients?clientId=${KC_APP_REALM_CLIENT_ID}")

    if [ "$(echo "$CLIENT_CHECK" | jq 'length')" -eq 0 ]; then
        echo "❌ Client ${KC_APP_REALM_CLIENT_ID} not found" >&2
        return 1
    fi

    local CLIENT_UUID=$(echo "$CLIENT_CHECK" | jq -r '.[0].id')
    echo "✅ Client found (UUID: ${CLIENT_UUID})"

    # Retrieve the client secret
    echo "🔑 Retrieving client secret for ${KC_APP_REALM_CLIENT_ID}..."
    local CLIENT_SECRET_RESPONSE=$(curl -s "${CURL_OPTS[@]}" -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/${CLIENT_UUID}/client-secret")

    KC_APP_REALM_CLIENT_SECRET=$(echo "$CLIENT_SECRET_RESPONSE" | jq -r '.value')

    if [ -z "$KC_APP_REALM_CLIENT_SECRET" ] || [ "$KC_APP_REALM_CLIENT_SECRET" = "null" ]; then
        echo "❌ Failed to retrieve client secret" >&2
        echo "Response: $CLIENT_SECRET_RESPONSE" >&2
        return 1
    fi

    echo "✅ Client secret retrieved successfully"

    # Write export to file if SECRET_OUTPUT_FILE is set (avoids logging secret to stdout)
    if [ -n "${SECRET_OUTPUT_FILE:-}" ]; then
        echo "export KC_APP_REALM_CLIENT_SECRET=\"${KC_APP_REALM_CLIENT_SECRET}\"" >> "${SECRET_OUTPUT_FILE}"
    fi

    # Export the credentials
    export KC_APP_REALM_CLIENT_SECRET
}
