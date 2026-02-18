#!/usr/bin/env bash
set -euo pipefail

get_client_secret() {
    # Check required variables
    if [ -z "${KC_BASE_URL:-}" ]; then
        echo "❌ Error: KC_BASE_URL is not set" >&2
        return 1
    fi

    if [ -z "${KC_APP_REALM:-}" ]; then
        echo "❌ Error: KC_APP_REALM is not set" >&2
        return 1
    fi

    if [ -z "${KC_APP_REALM_ADMIN_ID:-}" ]; then
        echo "❌ Error: KC_APP_REALM_ADMIN_ID is not set" >&2
        return 1
    fi

    if [ -z "${KC_APP_REALM_ADMIN_SECRET:-}" ]; then
        echo "❌ Error: KC_APP_REALM_ADMIN_SECRET is not set" >&2
        return 1
    fi

    if [ -z "${KC_APP_REALM_CLIENT_ID:-}" ]; then
        echo "❌ Error: KC_APP_REALM_CLIENT_ID is not set" >&2
        return 1
    fi

    echo "🔐 Authenticating with ${KC_APP_REALM_ADMIN_ID}..."

    local TOKEN_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/realms/${KC_APP_REALM}/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "client_id=${KC_APP_REALM_ADMIN_ID}" \
        -d "client_secret=${KC_APP_REALM_ADMIN_SECRET}" \
        -d "grant_type=client_credentials")

    local TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$TOKEN" ]; then
        echo "❌ Failed to authenticate" >&2
        echo "Response: $TOKEN_RESPONSE" >&2
        echo "" >&2
        echo "Configuration used:" >&2
        echo "  KC_BASE_URL: ${KC_BASE_URL}" >&2
        echo "  KC_APP_REALM: ${KC_APP_REALM}" >&2
        echo "  KC_APP_REALM_ADMIN_ID: ${KC_APP_REALM_ADMIN_ID}" >&2
        echo "  KC_APP_REALM_ADMIN_SECRET: (${#KC_APP_REALM_ADMIN_SECRET} characters)" >&2
        echo "  KC_APP_REALM_CLIENT_ID: ${KC_APP_REALM_CLIENT_ID}" >&2
        echo "" >&2
        echo "💡 Suggestion: KC_APP_REALM_ADMIN_ID and KC_APP_REALM_ADMIN_SECRET should be" >&2
        echo "   the client_id and client_secret of a service account client (cicd_admin) in realm '${KC_APP_REALM}'" >&2
        return 1
    fi

    echo "✅ Authentication successful"
    echo "🔍 Looking up client ${KC_APP_REALM_CLIENT_ID}..."

    # Get the client UUID
    local CLIENT_CHECK=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${KC_APP_REALM}/clients?clientId=${KC_APP_REALM_CLIENT_ID}")

    if [ "$(echo "$CLIENT_CHECK" | jq 'length')" -eq 0 ]; then
        echo "❌ Client ${KC_APP_REALM_CLIENT_ID} not found" >&2
        return 1
    fi

    local CLIENT_UUID=$(echo "$CLIENT_CHECK" | jq -r '.[0].id')
    echo "✅ Client found (UUID: ${CLIENT_UUID})"

    # Retrieve the client secret
    echo "🔑 Retrieving client secret for ${KC_APP_REALM_CLIENT_ID}..."
    local CLIENT_SECRET_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${KC_APP_REALM}/clients/${CLIENT_UUID}/client-secret")

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
