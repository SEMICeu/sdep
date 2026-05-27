#!/usr/bin/env bash
set -euo pipefail

# Initialize counters
CREATED_COUNT=0
UPDATED_COUNT=0
UNMODIFIED_COUNT=0
CREATED_ITEMS=""
UPDATED_ITEMS=""
UNMODIFIED_ITEMS=""

# Check required variables
if [ -z "${KC_BASE_URL:-}" ]; then
    echo "❌ Error: KC_BASE_URL is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_CONFIG_YAML:-}" ]; then
    echo "❌ Error: KC_APP_REALM_CONFIG_YAML is not set" >&2; exit 1
fi
if [ ! -f "${KC_APP_REALM_CONFIG_YAML}" ]; then
    echo "❌ Error: KC_APP_REALM_CONFIG_YAML not found: ${KC_APP_REALM_CONFIG_YAML}" >&2; exit 1
fi
REALM_NAME=$(yq -r '.config.name' "$KC_APP_REALM_CONFIG_YAML")
REALM_DISPLAYNAME=$(yq -r '.config.display_name // ""' "$KC_APP_REALM_CONFIG_YAML")

if [ -z "${KC_ADMIN_REALM_ADMIN_USERNAME:-}" ]; then
    echo "❌ Error: KC_ADMIN_REALM_ADMIN_USERNAME is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_ADMIN_REALM_ADMIN_PASSWORD:-}" ]; then
    echo "❌ Error: KC_ADMIN_REALM_ADMIN_PASSWORD is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

echo "📦 Creating ${REALM_NAME} realm in Keycloak..."
echo "🔐 Authenticating with Keycloak admin..."

TOKEN_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${KC_ADMIN_REALM_ADMIN_USERNAME}" \
    -d "password=${KC_ADMIN_REALM_ADMIN_PASSWORD}" \
    -d "grant_type=password" \
    -d "client_id=admin-cli")

TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to authenticate with Keycloak admin" >&2
    echo "Response: $TOKEN_RESPONSE" >&2
    echo "" >&2
    echo "Configuration used:" >&2
    echo "  KC_BASE_URL: ${KC_BASE_URL}" >&2
    echo "  REALM_NAME: ${REALM_NAME}" >&2
    echo "  KC_ADMIN_REALM_ADMIN_USERNAME: ${KC_ADMIN_REALM_ADMIN_USERNAME}" >&2
    echo "  KC_ADMIN_REALM_ADMIN_PASSWORD: (${#KC_ADMIN_REALM_ADMIN_PASSWORD} characters)" >&2
    echo "  REALM_DISPLAYNAME: ${REALM_DISPLAYNAME}" >&2
    echo "" >&2
    echo "💡 Suggestion: KC_ADMIN_REALM_ADMIN_USERNAME and KC_ADMIN_REALM_ADMIN_PASSWORD should be" >&2
    echo "   the username and password of a Keycloak admin user in the master realm." >&2
    exit 1
fi

echo "✅ Authentication successful"
echo "🔍 Checking if ${REALM_NAME} realm already exists..."

REALM_EXISTS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${REALM_NAME}" \
    -o /dev/null -w "%{http_code}")

if [ "$REALM_EXISTS" = "200" ]; then
    # Fetch current display name and check if update needed
    CURRENT_REALM=$(curl -s -H "Authorization: Bearer $TOKEN" "${KC_BASE_URL}/admin/realms/${REALM_NAME}")
    CURRENT_DISPLAYNAME=$(echo "$CURRENT_REALM" | jq -r '.displayName // ""')

    if [ "$CURRENT_DISPLAYNAME" != "$REALM_DISPLAYNAME" ]; then
        echo "🔄 Updating display name for realm ${REALM_NAME}..."
        UPDATE_DATA=$(echo "$CURRENT_REALM" | jq --arg dn "$REALM_DISPLAYNAME" '.displayName = $dn')
        UPDATE_RESPONSE=$(curl -s -X PUT "${KC_BASE_URL}/admin/realms/${REALM_NAME}" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$UPDATE_DATA" \
            -w "\n%{http_code}")

        UPDATE_HTTP_CODE=$(echo "$UPDATE_RESPONSE" | tail -n1)

        if [ "$UPDATE_HTTP_CODE" = "204" ] || [ "$UPDATE_HTTP_CODE" = "200" ]; then
            echo "✅ Realm ${REALM_NAME} display name updated successfully"
            UPDATED_COUNT=$((UPDATED_COUNT + 1))
            UPDATED_ITEMS="${REALM_NAME}"
        else
            echo "❌ Failed to update realm ${REALM_NAME} display name" >&2
            echo "Response: $UPDATE_RESPONSE" >&2
            exit 1
        fi
    else
        echo "✅ Realm ${REALM_NAME} already exists, skipping creation"
        UNMODIFIED_COUNT=$((UNMODIFIED_COUNT + 1))
        UNMODIFIED_ITEMS="${REALM_NAME}"
    fi
else
    echo "📝 Creating realm ${REALM_NAME}..."
    RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"realm\":\"${REALM_NAME}\",\"enabled\":true,\"displayName\":\"${REALM_DISPLAYNAME}\"}" \
        -w "%{http_code}")

    if echo "$RESPONSE" | grep -q "201"; then
        echo "✅ Realm ${REALM_NAME} created successfully"
        CREATED_COUNT=$((CREATED_COUNT + 1))
        CREATED_ITEMS="${REALM_NAME}"
    else
        echo "❌ Failed to create realm ${REALM_NAME}" >&2
        echo "Response: $RESPONSE" >&2
        exit 1
    fi
fi

echo ""
echo "📊 Summary:"
if [ $CREATED_COUNT -gt 0 ]; then
    echo "  Created: $CREATED_COUNT realm(s) - $CREATED_ITEMS"
else
    echo "  Created: 0 realm(s)"
fi
if [ $UPDATED_COUNT -gt 0 ]; then
    echo "  Updated: $UPDATED_COUNT realm(s) - $UPDATED_ITEMS"
else
    echo "  Updated: 0 realm(s)"
fi
if [ $UNMODIFIED_COUNT -gt 0 ]; then
    echo "  Unmodified: $UNMODIFIED_COUNT realm(s) - $UNMODIFIED_ITEMS"
else
    echo "  Unmodified: 0 realm(s)"
fi
echo ""
echo "✅ Realm setup completed"
