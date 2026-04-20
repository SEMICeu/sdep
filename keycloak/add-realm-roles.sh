#!/usr/bin/env bash
set -euo pipefail

# Initialize counters
CREATED_COUNT=0
UPDATED_COUNT=0
UNMODIFIED_COUNT=0
DELETED_COUNT=0
REJECTED_COUNT=0
CREATED_ITEMS=""
UPDATED_ITEMS=""
UNMODIFIED_ITEMS=""
DELETED_ITEMS=""
REJECTED_ITEMS=""

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
REALM_SHORTNAME=$(yq -r '.config.shortname // ""' "$KC_APP_REALM_CONFIG_YAML")

if [ -z "${KC_APP_REALM_ADMIN_ID:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ADMIN_ID is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_ADMIN_SECRET:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ADMIN_SECRET is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_ROLE_YAML:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ROLE_YAML is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ ! -f "${KC_APP_REALM_ROLE_YAML}" ]; then
    echo "❌ Error: KC_APP_REALM_ROLE_YAML file not found: ${KC_APP_REALM_ROLE_YAML}" >&2
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

echo ""
echo "📦 Creating realm roles in ${REALM_NAME} from ${KC_APP_REALM_ROLE_YAML}..."
echo "🔐 Authenticating with ${KC_APP_REALM_ADMIN_ID}..."

TOKEN_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/realms/${REALM_NAME}/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=${KC_APP_REALM_ADMIN_ID}" \
    -d "client_secret=${KC_APP_REALM_ADMIN_SECRET}" \
    -d "grant_type=client_credentials")

TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to authenticate" >&2
    echo "Response: $TOKEN_RESPONSE" >&2
    echo "" >&2
    echo "Configuration used:" >&2
    echo "  KC_BASE_URL: ${KC_BASE_URL}" >&2
    echo "  REALM_NAME: ${REALM_NAME}" >&2
    echo "  KC_APP_REALM_ADMIN_ID: ${KC_APP_REALM_ADMIN_ID}" >&2
    echo "  KC_APP_REALM_ADMIN_SECRET: (${#KC_APP_REALM_ADMIN_SECRET} characters)" >&2
    echo "  KC_APP_REALM_ROLE_YAML: ${KC_APP_REALM_ROLE_YAML}" >&2
    echo "" >&2
    echo "💡 Suggestion: KC_APP_REALM_ADMIN_ID and KC_APP_REALM_ADMIN_SECRET should be" >&2
    echo "   the client_id and client_secret of a service account client (cicd_admin) in realm '${REALM_NAME}'" >&2
    exit 1
fi

echo "✅ Authentication successful"
echo "📄 Managing roles in ${REALM_NAME} from ${KC_APP_REALM_ROLE_YAML}..."

# Get all existing roles in the realm
EXISTING_ROLES=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "${KC_BASE_URL}/admin/realms/${REALM_NAME}/roles")

# Build desired roles array from YAML and validate prefix
ROLE_COUNT=$(yq '.roles | length' "$KC_APP_REALM_ROLE_YAML")
REALM_PREFIX="${REALM_NAME}_"
SHORTNAME_PREFIX="${REALM_SHORTNAME:+${REALM_SHORTNAME}_}"
DESIRED_ROLE_NAMES="["
VALID_INDICES=()

for i in $(seq 0 $((ROLE_COUNT - 1))); do
    ROLE_NAME=$(yq -r ".roles[$i].name" "$KC_APP_REALM_ROLE_YAML")

    # Validate that role has REALM prefix or shortname prefix
    if [[ "$ROLE_NAME" =~ ^${REALM_PREFIX} ]] || { [ -n "$SHORTNAME_PREFIX" ] && [[ "$ROLE_NAME" =~ ^${SHORTNAME_PREFIX} ]]; }; then
        VALID_INDICES+=("$i")
        if [ "$DESIRED_ROLE_NAMES" != "[" ]; then
            DESIRED_ROLE_NAMES="$DESIRED_ROLE_NAMES,"
        fi
        DESIRED_ROLE_NAMES="$DESIRED_ROLE_NAMES\"$ROLE_NAME\""
    else
        echo "⚠️  Rejected: '$ROLE_NAME' - missing required prefix '${REALM_PREFIX}' or '${SHORTNAME_PREFIX}'"
        REJECTED_COUNT=$((REJECTED_COUNT + 1))
        REJECTED_ITEMS="${REJECTED_ITEMS:+$REJECTED_ITEMS, }$ROLE_NAME"
    fi
done
DESIRED_ROLE_NAMES="$DESIRED_ROLE_NAMES]"

# Process valid roles from YAML (create or update)
for i in "${VALID_INDICES[@]+"${VALID_INDICES[@]}"}"; do
    ROLE_NAME=$(yq -r ".roles[$i].name" "$KC_APP_REALM_ROLE_YAML")
    ROLE_DESC=$(yq -r ".roles[$i].description" "$KC_APP_REALM_ROLE_YAML")

    ROLE_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${REALM_NAME}/roles/$ROLE_NAME" \
        -w "\n%{http_code}")

    ROLE_HTTP_CODE=$(echo "$ROLE_RESPONSE" | tail -n1)
    ROLE_BODY=$(echo "$ROLE_RESPONSE" | sed '$d')

    if [ "$ROLE_HTTP_CODE" = "200" ]; then
        CURRENT_DESC=$(echo "$ROLE_BODY" | jq -r '.description // ""')

        if [ "$CURRENT_DESC" != "$ROLE_DESC" ]; then
            echo "🔄 Updating role $ROLE_NAME..."
            UPDATE_DATA=$(jq -n \
                --arg name "$ROLE_NAME" \
                --arg description "$ROLE_DESC" \
                '{name: $name, description: $description}')

            UPDATE_RESPONSE=$(curl -s -X PUT "${KC_BASE_URL}/admin/realms/${REALM_NAME}/roles/$ROLE_NAME" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "$UPDATE_DATA" \
                -w "\n%{http_code}")

            UPDATE_HTTP_CODE=$(echo "$UPDATE_RESPONSE" | tail -n1)

            if [ "$UPDATE_HTTP_CODE" = "204" ] || [ "$UPDATE_HTTP_CODE" = "200" ]; then
                echo "✅ Role $ROLE_NAME updated successfully"
                UPDATED_COUNT=$((UPDATED_COUNT + 1))
                if [ -z "$UPDATED_ITEMS" ]; then
                    UPDATED_ITEMS="$ROLE_NAME"
                else
                    UPDATED_ITEMS="$UPDATED_ITEMS, $ROLE_NAME"
                fi
            else
                echo "❌ Failed to update role $ROLE_NAME" >&2
                echo "Response: $UPDATE_RESPONSE" >&2
                exit 1
            fi
        else
            echo "✅ Role $ROLE_NAME already exists (no changes)"
            UNMODIFIED_COUNT=$((UNMODIFIED_COUNT + 1))
            if [ -z "$UNMODIFIED_ITEMS" ]; then
                UNMODIFIED_ITEMS="$ROLE_NAME"
            else
                UNMODIFIED_ITEMS="$UNMODIFIED_ITEMS, $ROLE_NAME"
            fi
        fi
    else
        echo ""
        echo "🔍 Creating role $ROLE_NAME..."
        ROLE_DATA=$(jq -n \
            --arg name "$ROLE_NAME" \
            --arg description "$ROLE_DESC" \
            '{name: $name, description: $description}')

        RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms/${REALM_NAME}/roles" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$ROLE_DATA" \
            -w "%{http_code}")

        if echo "$RESPONSE" | grep -q "201"; then
            echo "✅ Role $ROLE_NAME created successfully"
            CREATED_COUNT=$((CREATED_COUNT + 1))
            if [ -z "$CREATED_ITEMS" ]; then
                CREATED_ITEMS="$ROLE_NAME"
            else
                CREATED_ITEMS="$CREATED_ITEMS, $ROLE_NAME"
            fi
        else
            echo "❌ Failed to create role $ROLE_NAME" >&2
            echo "Response: $RESPONSE" >&2
            exit 1
        fi
    fi
done

# Remove roles that exist in realm but not in YAML (only those with REALM prefix or shortname prefix)
# Skip deletion when there are no valid entries (e.g. NOK test files) to avoid wiping existing roles
if [ ${#VALID_INDICES[@]} -eq 0 ]; then
    echo "⏭️  Skipping deletion check (no valid entries in YAML)"
else
    echo "🔍 Checking for roles to remove..."
    if [ -n "$SHORTNAME_PREFIX" ]; then
        ROLES_TO_REMOVE=$(echo "$EXISTING_ROLES" | jq -r --argjson desired "$DESIRED_ROLE_NAMES" --arg prefix "${REALM_PREFIX}" --arg shortnamePrefix "${SHORTNAME_PREFIX}" \
            '[.[] | select(.composite == false and .clientRole == false and ((.name | startswith($prefix)) or (.name | startswith($shortnamePrefix))) and ([.name] | inside($desired) | not)) | .name] | .[]')
    else
        ROLES_TO_REMOVE=$(echo "$EXISTING_ROLES" | jq -r --argjson desired "$DESIRED_ROLE_NAMES" --arg prefix "${REALM_PREFIX}" \
            '[.[] | select(.composite == false and .clientRole == false and (.name | startswith($prefix)) and ([.name] | inside($desired) | not)) | .name] | .[]')
    fi

    if [ -n "$ROLES_TO_REMOVE" ]; then
        while IFS= read -r ROLE_NAME; do
            echo "🗑️  Removing role $ROLE_NAME (not in YAML)..."
            DELETE_RESPONSE=$(curl -s -X DELETE "${KC_BASE_URL}/admin/realms/${REALM_NAME}/roles/$ROLE_NAME" \
                -H "Authorization: Bearer $TOKEN" \
                -w "%{http_code}")

            if [ "$DELETE_RESPONSE" = "204" ] || [ "$DELETE_RESPONSE" = "200" ]; then
                echo "✅ Role $ROLE_NAME removed successfully"
                DELETED_COUNT=$((DELETED_COUNT + 1))
                if [ -z "$DELETED_ITEMS" ]; then
                    DELETED_ITEMS="$ROLE_NAME"
                else
                    DELETED_ITEMS="$DELETED_ITEMS, $ROLE_NAME"
                fi
            else
                echo "❌ Failed to remove role $ROLE_NAME" >&2
                echo "Response: $DELETE_RESPONSE" >&2
                exit 1
            fi
        done <<< "$ROLES_TO_REMOVE"
    else
        echo "✅ No roles to remove"
    fi
fi

echo ""
echo "📊 Summary:"
if [ $CREATED_COUNT -gt 0 ]; then
    echo "  Created: $CREATED_COUNT role(s) - $CREATED_ITEMS"
else
    echo "  Created: 0 role(s)"
fi
if [ $UPDATED_COUNT -gt 0 ]; then
    echo "  Updated: $UPDATED_COUNT role(s) - $UPDATED_ITEMS"
else
    echo "  Updated: 0 role(s)"
fi
if [ $DELETED_COUNT -gt 0 ]; then
    echo "  Deleted: $DELETED_COUNT role(s) - $DELETED_ITEMS"
else
    echo "  Deleted: 0 role(s)"
fi
if [ $UNMODIFIED_COUNT -gt 0 ]; then
    echo "  Unmodified: $UNMODIFIED_COUNT role(s) - $UNMODIFIED_ITEMS"
else
    echo "  Unmodified: 0 role(s)"
fi
if [ $REJECTED_COUNT -gt 0 ]; then
    echo "  Rejected: $REJECTED_COUNT role(s) - $REJECTED_ITEMS"
else
    echo "  Rejected: 0 role(s)"
fi
echo ""
echo "✅ Realm roles setup completed"
