#!/usr/bin/env bash
set -euo pipefail

# Initialize counters
CREATED_COUNT=0
UNMODIFIED_COUNT=0
CREATED_ITEMS=""
UNMODIFIED_ITEMS=""

# Check required variables
if [ -z "${KC_BASE_URL:-}" ]; then
    echo "❌ Error: KC_BASE_URL is not set" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM:-}" ]; then
    echo "❌ Error: REALM is not set" >&2
    exit 1
fi

if [ -z "${KC_ADMIN_REALM_ADMIN_USERNAME:-}" ]; then
    echo "❌ Error: KC_ADMIN_REALM_ADMIN_USERNAME is not set" >&2
    exit 1
fi

if [ -z "${KC_ADMIN_REALM_ADMIN_PASSWORD:-}" ]; then
    echo "❌ Error: KC_ADMIN_REALM_ADMIN_PASSWORD is not set" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_DISPLAYNAME:-}" ]; then
    echo "❌ Error: KC_APP_REALM_DISPLAYNAME is not set" >&2
    exit 1
fi

echo "📦 Creating ${KC_APP_REALM} realm in Keycloak..."
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
    echo "  KC_APP_REALM: ${KC_APP_REALM}" >&2
    echo "  KC_ADMIN_REALM_ADMIN_USERNAME: ${KC_ADMIN_REALM_ADMIN_USERNAME}" >&2
    echo "  KC_ADMIN_REALM_ADMIN_PASSWORD: (${#KC_ADMIN_REALM_ADMIN_PASSWORD} characters)" >&2
    echo "  KC_APP_REALM_DISPLAYNAME: ${KC_APP_REALM_DISPLAYNAME}" >&2
    echo "" >&2
    echo "💡 Suggestion: KC_ADMIN_REALM_ADMIN_USERNAME and KC_ADMIN_REALM_ADMIN_PASSWORD should be" >&2
    echo "   the username and password of a Keycloak admin user in the master realm." >&2
    exit 1
fi

echo "✅ Authentication successful"
echo "🔍 Checking if ${KC_APP_REALM} realm already exists..."

REALM_EXISTS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${KC_APP_REALM}" \
    -o /dev/null -w "%{http_code}")

if [ "$REALM_EXISTS" = "200" ]; then
    echo "✅ Realm ${KC_APP_REALM} already exists, skipping creation"
    UNMODIFIED_COUNT=$((UNMODIFIED_COUNT + 1))
    UNMODIFIED_ITEMS="${KC_APP_REALM}"
else
    echo "📝 Creating realm ${KC_APP_REALM}..."
    RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"realm\":\"${KC_APP_REALM}\",\"enabled\":true,\"displayName\":\"${KC_APP_REALM_DISPLAYNAME}\"}" \
        -w "%{http_code}")

    if echo "$RESPONSE" | grep -q "201"; then
        echo "✅ Realm ${KC_APP_REALM} created successfully"
        CREATED_COUNT=$((CREATED_COUNT + 1))
        CREATED_ITEMS="${KC_APP_REALM}"
    else
        echo "❌ Failed to create realm ${KC_APP_REALM}" >&2
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
if [ $UNMODIFIED_COUNT -gt 0 ]; then
    echo "  Unmodified: $UNMODIFIED_COUNT realm(s) - $UNMODIFIED_ITEMS"
else
    echo "  Unmodified: 0 realm(s)"
fi
echo ""
echo "✅ Realm setup completed"
