#!/usr/bin/env bash
set -euo pipefail

# Initialize counters
CREATED_COUNT=0
UNMODIFIED_COUNT=0
CREATED_ITEMS=""
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
if [ -z "${KC_ADMIN_REALM_ADMIN_USERNAME:-}" ]; then
    echo "❌ Error: KC_ADMIN_REALM_ADMIN_USERNAME is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_ADMIN_REALM_ADMIN_PASSWORD:-}" ]; then
    echo "❌ Error: KC_ADMIN_REALM_ADMIN_PASSWORD is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_ADMIN_ID:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ADMIN_ID is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_ADMIN_NAME:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ADMIN_NAME is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_ADMIN_DESC:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ADMIN_DESC is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

# Check realm existence
REALM_CHECK=$(curl -s -o /dev/null -w "%{http_code}" \
    "${KC_BASE_URL}/realms/${REALM_NAME}/.well-known/openid-configuration")
if [ "$REALM_CHECK" != "200" ]; then
    echo "❌ Error: Realm '${REALM_NAME}' does not exist in Keycloak at ${KC_BASE_URL}" >&2
    echo "💡 Make sure this realm is added first" >&2
    exit 1
fi

# Client configuration from environment variables
CLIENT_ID="${KC_APP_REALM_ADMIN_ID}"
CLIENT_NAME="${KC_APP_REALM_ADMIN_NAME}"
CLIENT_DESC="${KC_APP_REALM_ADMIN_DESC}"

echo "📦 Creating CI/CD admin service account in ${REALM_NAME}..."
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
    echo "" >&2
    echo "💡 Suggestion: KC_ADMIN_REALM_ADMIN_USERNAME and KC_ADMIN_REALM_ADMIN_PASSWORD should be" >&2
    echo "   the username and password of a Keycloak admin user in the master realm." >&2
    exit 1
fi

echo "✅ Authentication successful"
echo "🔍 Checking if client $CLIENT_ID exists..."

CLIENT_CHECK=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients?clientId=$CLIENT_ID")

if [ "$(echo "$CLIENT_CHECK" | jq 'length')" -gt 0 ]; then
    echo "✅ Client $CLIENT_ID already exists"
    UNMODIFIED_COUNT=$((UNMODIFIED_COUNT + 1))
    UNMODIFIED_ITEMS="$CLIENT_ID"
    CLIENT_UUID=$(echo "$CLIENT_CHECK" | jq -r '.[0].id')

    # Get existing secret
    CLIENT_SECRET_OBJ=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID/client-secret")
    CLIENT_SECRET=$(echo "$CLIENT_SECRET_OBJ" | jq -r '.value')
else
    echo "📝 Creating client $CLIENT_ID..."

    # Generate a random secret
    CLIENT_SECRET=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

    CLIENT_DATA=$(jq -n \
        --arg clientId "$CLIENT_ID" \
        --arg name "$CLIENT_NAME" \
        --arg description "$CLIENT_DESC" \
        --arg secret "$CLIENT_SECRET" \
        '{
            clientId: $clientId,
            name: $name,
            description: $description,
            protocol: "openid-connect",
            publicClient: false,
            serviceAccountsEnabled: true,
            standardFlowEnabled: false,
            directAccessGrantsEnabled: false,
            enabled: true,
            secret: $secret
        }')

    CREATE_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$CLIENT_DATA" \
        -w "\n%{http_code}")

    HTTP_CODE=$(echo "$CREATE_RESPONSE" | tail -n1)

    if [ "$HTTP_CODE" = "201" ]; then
        echo "✅ Client $CLIENT_ID created successfully"
        CREATED_COUNT=$((CREATED_COUNT + 1))
        CREATED_ITEMS="$CLIENT_ID"
        CLIENT_CHECK=$(curl -s -H "Authorization: Bearer $TOKEN" \
            "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients?clientId=$CLIENT_ID")
        CLIENT_UUID=$(echo "$CLIENT_CHECK" | jq -r '.[0].id')
    else
        echo "❌ Failed to create client $CLIENT_ID" >&2
        echo "Response: $CREATE_RESPONSE" >&2
        exit 1
    fi
fi

# Get service account user
echo "🔍 Getting service account user..."
SA_USER=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID/service-account-user")
SA_USER_ID=$(echo "$SA_USER" | jq -r '.id')

# Get realm-management client UUID
echo "🔍 Getting realm-management client..."
REALM_MGMT_CLIENT=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients?clientId=realm-management")
REALM_MGMT_UUID=$(echo "$REALM_MGMT_CLIENT" | jq -r '.[0].id')

# Get available realm-management roles
echo "🔍 Getting available realm-management roles..."
AVAILABLE_ROLES=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$REALM_MGMT_UUID/roles")

# Get manage-realm, manage-clients, and manage-users roles
MANAGE_REALM_ROLE=$(echo "$AVAILABLE_ROLES" | jq '.[] | select(.name == "manage-realm")')
MANAGE_CLIENTS_ROLE=$(echo "$AVAILABLE_ROLES" | jq '.[] | select(.name == "manage-clients")')
MANAGE_USERS_ROLE=$(echo "$AVAILABLE_ROLES" | jq '.[] | select(.name == "manage-users")')

if [ -z "$MANAGE_REALM_ROLE" ] || [ "$MANAGE_REALM_ROLE" = "null" ]; then
    echo "❌ Error: manage-realm role not found" >&2
    exit 1
fi

if [ -z "$MANAGE_CLIENTS_ROLE" ] || [ "$MANAGE_CLIENTS_ROLE" = "null" ]; then
    echo "❌ Error: manage-clients role not found" >&2
    exit 1
fi

if [ -z "$MANAGE_USERS_ROLE" ] || [ "$MANAGE_USERS_ROLE" = "null" ]; then
    echo "❌ Error: manage-users role not found" >&2
    exit 1
fi

# Build roles array
ROLES_TO_ADD="[$MANAGE_REALM_ROLE,$MANAGE_CLIENTS_ROLE,$MANAGE_USERS_ROLE]"

# Get currently assigned client roles
CURRENT_CLIENT_ROLES=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${REALM_NAME}/users/$SA_USER_ID/role-mappings/clients/$REALM_MGMT_UUID")

# Check if roles are already assigned
CURRENT_ROLE_NAMES=$(echo "$CURRENT_CLIENT_ROLES" | jq -r '[.[].name] | sort | join(",")')
DESIRED_ROLE_NAMES=$(echo "$ROLES_TO_ADD" | jq -r '[.[].name] | sort | join(",")')

if [ "$CURRENT_ROLE_NAMES" = "$DESIRED_ROLE_NAMES" ]; then
    echo "✅ Roles already assigned: manage-realm, manage-clients, manage-users"
else
    echo "🔑 Assigning realm-management roles..."

    ASSIGN_RESPONSE=$(curl -s -X POST \
        "${KC_BASE_URL}/admin/realms/${REALM_NAME}/users/$SA_USER_ID/role-mappings/clients/$REALM_MGMT_UUID" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$ROLES_TO_ADD" \
        -w "\n%{http_code}")

    HTTP_CODE=$(echo "$ASSIGN_RESPONSE" | tail -n1)

    if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
        echo "✅ Roles assigned successfully: manage-realm, manage-clients, manage-users"
    else
        echo "❌ Failed to assign roles" >&2
        echo "Response: $ASSIGN_RESPONSE" >&2
        exit 1
    fi
fi

echo ""
echo "📊 Summary:"
if [ $CREATED_COUNT -gt 0 ]; then
    echo "  Created: $CREATED_COUNT client(s) - $CREATED_ITEMS"
else
    echo "  Created: 0 client(s)"
fi
if [ $UNMODIFIED_COUNT -gt 0 ]; then
    echo "  Unmodified: $UNMODIFIED_COUNT client(s) - $UNMODIFIED_ITEMS"
else
    echo "  Unmodified: 0 client(s)"
fi
echo ""
echo "✅ CI/CD admin service account setup completed"
echo ""
echo "Client ID: $CLIENT_ID"
echo "Client Secret: $CLIENT_SECRET"
echo ""
echo "To use this client for authentication, set:"
echo "  KC_ADMIN_CLIENT_ID=$CLIENT_ID"
echo "  KC_ADMIN_CLIENT_SECRET=$CLIENT_SECRET"
