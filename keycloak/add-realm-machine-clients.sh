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
IDEMPOTENCY_KEY=$(yq -r '.config.idempotency_key // ""' "$KC_APP_REALM_CONFIG_YAML")
if [ -z "$IDEMPOTENCY_KEY" ]; then
    echo "❌ Error: config.idempotency_key is not defined in ${KC_APP_REALM_CONFIG_YAML}" >&2; exit 1
fi

if [ -z "${KC_APP_REALM_ADMIN_ID:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ADMIN_ID is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_ADMIN_SECRET:-}" ]; then
    echo "❌ Error: KC_APP_REALM_ADMIN_SECRET is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ -z "${KC_APP_REALM_MACHINE_CLIENT_YAML:-}" ]; then
    echo "❌ Error: KC_APP_REALM_MACHINE_CLIENT_YAML is not set (commandline .env* or in pipeline)" >&2
    exit 1
fi

if [ ! -f "${KC_APP_REALM_MACHINE_CLIENT_YAML}" ]; then
    echo "❌ Error: KC_APP_REALM_MACHINE_CLIENT_YAML file not found: ${KC_APP_REALM_MACHINE_CLIENT_YAML}" >&2
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
echo "📦 Creating machine clients in ${REALM_NAME} from ${KC_APP_REALM_MACHINE_CLIENT_YAML}..."
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
    echo "  KC_APP_REALM_MACHINE_CLIENT_YAML: ${KC_APP_REALM_MACHINE_CLIENT_YAML}" >&2
    echo "" >&2
    echo "💡 Suggestion: KC_APP_REALM_ADMIN_ID and KC_APP_REALM_ADMIN_SECRET should be" >&2
    echo "   the client_id and client_secret of a service account client (cicd_admin) in realm '${REALM_NAME}'" >&2
    exit 1
fi

echo "✅ Authentication successful"
echo "📄 Processing clients from ${KC_APP_REALM_MACHINE_CLIENT_YAML}..."

CLIENT_COUNT=$(yq '.clients | length' "$KC_APP_REALM_MACHINE_CLIENT_YAML")
IDEMPOTENCY_SUBSTR="${IDEMPOTENCY_KEY}"
CLIENTID_REGEX=$(yq -r '.config.clientid_regex // "^[A-Za-z0-9._\-]+$"' "$KC_APP_REALM_CONFIG_YAML")

# First pass: validate clients contain idempotency_key and match clientid_regex, collect valid indices
VALID_INDICES=()
for i in $(seq 0 $((CLIENT_COUNT - 1))); do
    CLIENT_ID=$(yq -r ".clients[$i].id" "$KC_APP_REALM_MACHINE_CLIENT_YAML")

    if ! [[ "$CLIENT_ID" == *"$IDEMPOTENCY_SUBSTR"* ]]; then
        echo "⚠️  Rejected: '$CLIENT_ID' — does not contain required idempotency_key substring '${IDEMPOTENCY_SUBSTR}'"
        REJECTED_COUNT=$((REJECTED_COUNT + 1))
        REJECTED_ITEMS="${REJECTED_ITEMS:+$REJECTED_ITEMS, }$CLIENT_ID"
    elif ! [[ "$CLIENT_ID" =~ $CLIENTID_REGEX ]]; then
        echo "⚠️  Rejected: '$CLIENT_ID' — does not match clientid_regex '${CLIENTID_REGEX}'"
        REJECTED_COUNT=$((REJECTED_COUNT + 1))
        REJECTED_ITEMS="${REJECTED_ITEMS:+$REJECTED_ITEMS, }$CLIENT_ID"
    else
        VALID_INDICES+=("$i")
    fi
done

# Build desired client IDs from valid entries only
DESIRED_CLIENT_IDS="["
for i in "${VALID_INDICES[@]+"${VALID_INDICES[@]}"}"; do
    CLIENT_ID=$(yq -r ".clients[$i].id" "$KC_APP_REALM_MACHINE_CLIENT_YAML")
    if [ "$DESIRED_CLIENT_IDS" != "[" ]; then
        DESIRED_CLIENT_IDS="$DESIRED_CLIENT_IDS,"
    fi
    DESIRED_CLIENT_IDS="$DESIRED_CLIENT_IDS\"$CLIENT_ID\""
done
DESIRED_CLIENT_IDS="$DESIRED_CLIENT_IDS]"

# Second pass: process valid clients
for i in "${VALID_INDICES[@]+"${VALID_INDICES[@]}"}"; do
    CLIENT_WAS_UNMODIFIED=false
    CLIENT_PROPS_UPDATED=false
    ROLES_CHANGED=false
    CLIENT_CHANGES=""
    CLIENT_ID=$(yq -r ".clients[$i].id" "$KC_APP_REALM_MACHINE_CLIENT_YAML")
    CLIENT_NAME=$(yq -r ".clients[$i].name" "$KC_APP_REALM_MACHINE_CLIENT_YAML")
    CLIENT_DESC=$(yq -r ".clients[$i].description" "$KC_APP_REALM_MACHINE_CLIENT_YAML")
    CLIENT_SECRET=$(yq -r ".clients[$i].secret" "$KC_APP_REALM_MACHINE_CLIENT_YAML")
    ACCESS_TOKEN_LIFESPAN=$(yq -r ".clients[$i].access_token_lifespan // \"\"" "$KC_APP_REALM_MACHINE_CLIENT_YAML")

    echo "🔍 Checking if client $CLIENT_ID exists..."
    CLIENT_CHECK=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients?clientId=$CLIENT_ID")

    if [ "$(echo "$CLIENT_CHECK" | jq 'length')" -gt 0 ]; then
        CLIENT_UUID=$(echo "$CLIENT_CHECK" | jq -r '.[0].id')

        # Compare YAML values with current Keycloak state
        CURRENT_NAME=$(echo "$CLIENT_CHECK" | jq -r '.[0].name // ""')
        CURRENT_DESC=$(echo "$CLIENT_CHECK" | jq -r '.[0].description // ""')
        CURRENT_LIFESPAN=$(echo "$CLIENT_CHECK" | jq -r '.[0].attributes["access.token.lifespan"] // ""')

        NEEDS_UPDATE=false
        if [ "$CURRENT_NAME" != "$CLIENT_NAME" ]; then
            NEEDS_UPDATE=true
            CLIENT_CHANGES="${CLIENT_CHANGES:+$CLIENT_CHANGES, }name changed"
        fi
        if [ "$CURRENT_DESC" != "$CLIENT_DESC" ]; then
            NEEDS_UPDATE=true
            CLIENT_CHANGES="${CLIENT_CHANGES:+$CLIENT_CHANGES, }description changed"
        fi
        if [ "$CURRENT_LIFESPAN" != "$ACCESS_TOKEN_LIFESPAN" ]; then
            NEEDS_UPDATE=true
            CLIENT_CHANGES="${CLIENT_CHANGES:+$CLIENT_CHANGES, }token lifespan changed"
        fi

        # Check secret if defined in YAML
        if [ "$CLIENT_SECRET" != "null" ] && [ -n "$CLIENT_SECRET" ]; then
            CURRENT_SECRET_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
                "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID/client-secret")
            CURRENT_SECRET=$(echo "$CURRENT_SECRET_RESPONSE" | jq -r '.value // ""')
            if [ "$CURRENT_SECRET" != "$CLIENT_SECRET" ]; then
                NEEDS_UPDATE=true
                CLIENT_CHANGES="${CLIENT_CHANGES:+$CLIENT_CHANGES, }secret changed"
            fi
        fi

        if [ "$NEEDS_UPDATE" = true ]; then
            echo "🔄 Updating client $CLIENT_ID..."
            UPDATE_DATA=$(echo "$CLIENT_CHECK" | jq \
                --arg name "$CLIENT_NAME" \
                --arg description "$CLIENT_DESC" \
                '.[0] | .name = $name | .description = $description')

            if [ "$CLIENT_SECRET" != "null" ] && [ -n "$CLIENT_SECRET" ]; then
                UPDATE_DATA=$(echo "$UPDATE_DATA" | jq --arg secret "$CLIENT_SECRET" '.secret = $secret')
            fi

            if [ -n "$ACCESS_TOKEN_LIFESPAN" ]; then
                UPDATE_DATA=$(echo "$UPDATE_DATA" | jq --arg lifespan "$ACCESS_TOKEN_LIFESPAN" '.attributes["access.token.lifespan"] = $lifespan')
            else
                UPDATE_DATA=$(echo "$UPDATE_DATA" | jq 'del(.attributes["access.token.lifespan"])')
            fi

            UPDATE_RESPONSE=$(curl -s -X PUT "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "$UPDATE_DATA" \
                -w "\n%{http_code}")

            UPDATE_HTTP_CODE=$(echo "$UPDATE_RESPONSE" | tail -n1)

            if [ "$UPDATE_HTTP_CODE" = "204" ] || [ "$UPDATE_HTTP_CODE" = "200" ]; then
                echo "✅ Client $CLIENT_ID updated successfully"
                UPDATED_COUNT=$((UPDATED_COUNT + 1))
                CLIENT_PROPS_UPDATED=true
            else
                echo "❌ Failed to update client $CLIENT_ID" >&2
                echo "Response: $UPDATE_RESPONSE" >&2
                exit 1
            fi
        else
            echo "✅ Client $CLIENT_ID already exists (no changes)"
            UNMODIFIED_COUNT=$((UNMODIFIED_COUNT + 1))
            CLIENT_WAS_UNMODIFIED=true
            if [ -z "$UNMODIFIED_ITEMS" ]; then
                UNMODIFIED_ITEMS="$CLIENT_ID"
            else
                UNMODIFIED_ITEMS="$UNMODIFIED_ITEMS, $CLIENT_ID"
            fi
        fi
    else
        echo ""
        echo "📝 Creating client $CLIENT_ID..."

        # Build CLIENT_DATA, conditionally adding secret and access_token_lifespan
        CLIENT_DATA=$(jq -n \
            --arg clientId "$CLIENT_ID" \
            --arg name "$CLIENT_NAME" \
            --arg description "$CLIENT_DESC" \
            '{clientId: $clientId, name: $name, description: $description, protocol: "openid-connect", publicClient: false, serviceAccountsEnabled: true, standardFlowEnabled: false, directAccessGrantsEnabled: false, enabled: true}')

        if [ "$CLIENT_SECRET" != "null" ] && [ -n "$CLIENT_SECRET" ]; then
            CLIENT_DATA=$(echo "$CLIENT_DATA" | jq --arg secret "$CLIENT_SECRET" '.secret = $secret')
        fi

        if [ -n "$ACCESS_TOKEN_LIFESPAN" ]; then
            CLIENT_DATA=$(echo "$CLIENT_DATA" | jq --arg lifespan "$ACCESS_TOKEN_LIFESPAN" '.attributes["access.token.lifespan"] = $lifespan')
        fi

        CREATE_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$CLIENT_DATA" \
            -w "\n%{http_code}")

        HTTP_CODE=$(echo "$CREATE_RESPONSE" | tail -n1)

        if [ "$HTTP_CODE" = "201" ]; then
            echo "✅ Client $CLIENT_ID created successfully"
            CREATED_COUNT=$((CREATED_COUNT + 1))
            if [ -z "$CREATED_ITEMS" ]; then
                CREATED_ITEMS="$CLIENT_ID"
            else
                CREATED_ITEMS="$CREATED_ITEMS, $CLIENT_ID"
            fi
            CLIENT_CHECK=$(curl -s -H "Authorization: Bearer $TOKEN" \
                "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients?clientId=$CLIENT_ID")
            CLIENT_UUID=$(echo "$CLIENT_CHECK" | jq -r '.[0].id')

            # Retrieve the generated secret from Keycloak
            CLIENT_SECRET_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
                "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID/client-secret")
            GENERATED_SECRET=$(echo "$CLIENT_SECRET_RESPONSE" | jq -r '.value')

            # echo "🔑 Secret for $CLIENT_ID: $GENERATED_SECRET"
        else
            echo "❌ Failed to create client $CLIENT_ID" >&2
            echo "Response: $CREATE_RESPONSE" >&2
            exit 1
        fi
    fi

    # Add protocol mappers for client_id and client_name (JWT claims)
    echo "🔧 Adding protocol mappers for client_id and client_name to $CLIENT_ID..."

    # Protocol mapper for client_id (maps from "id" field in clients.yaml)
    CLIENT_ID_MAPPER=$(jq -n \
        --arg clientId "$CLIENT_ID" \
        '{
            name: "client_id",
            protocol: "openid-connect",
            protocolMapper: "oidc-hardcoded-claim-mapper",
            consentRequired: false,
            config: {
                "claim.name": "client_id",
                "claim.value": $clientId,
                "jsonType.label": "String",
                "id.token.claim": "false",
                "access.token.claim": "true",
                "userinfo.token.claim": "false"
            }
        }')

    MAPPER_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID/protocol-mappers/models" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$CLIENT_ID_MAPPER" \
        -w "\n%{http_code}")

    HTTP_CODE=$(echo "$MAPPER_RESPONSE" | tail -n1)

    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "409" ]; then
        echo "✅ client_id mapper added/exists for $CLIENT_ID"
    else
        echo "⚠️  Failed to add client_id mapper (non-critical)"
        echo "Response: $MAPPER_RESPONSE"
    fi

    # Protocol mapper for client_name (maps from "name" field in clients.yaml)
    CLIENT_NAME_MAPPER=$(jq -n \
        --arg clientName "$CLIENT_NAME" \
        '{
            name: "client_name",
            protocol: "openid-connect",
            protocolMapper: "oidc-hardcoded-claim-mapper",
            consentRequired: false,
            config: {
                "claim.name": "client_name",
                "claim.value": $clientName,
                "jsonType.label": "String",
                "id.token.claim": "false",
                "access.token.claim": "true",
                "userinfo.token.claim": "false"
            }
        }')

    MAPPER_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID/protocol-mappers/models" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$CLIENT_NAME_MAPPER" \
        -w "\n%{http_code}")

    HTTP_CODE=$(echo "$MAPPER_RESPONSE" | tail -n1)

    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "409" ]; then
        echo "✅ client_name mapper added/exists for $CLIENT_ID"
    else
        echo "⚠️  Failed to add client_name mapper (non-critical)"
        echo "Response: $MAPPER_RESPONSE"
    fi

    # Manage service account roles (idempotent and declarative)
    ROLES_COUNT=$(yq ".clients[$i].service_account_roles | length" "$KC_APP_REALM_MACHINE_CLIENT_YAML")

    if [ "$ROLES_COUNT" != "null" ] && [ "$ROLES_COUNT" -gt 0 ]; then
        echo "🔑 Managing service account roles for $CLIENT_ID..."

        # Get service account user
        SA_USER=$(curl -s -H "Authorization: Bearer $TOKEN" \
            "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID/service-account-user")
        SA_USER_ID=$(echo "$SA_USER" | jq -r '.id')

        # Get available roles in realm
        AVAILABLE_ROLES=$(curl -s -H "Authorization: Bearer $TOKEN" \
            "${KC_BASE_URL}/admin/realms/${REALM_NAME}/roles")

        # Get currently assigned realm roles for service account
        CURRENT_ROLES=$(curl -s -H "Authorization: Bearer $TOKEN" \
            "${KC_BASE_URL}/admin/realms/${REALM_NAME}/users/$SA_USER_ID/role-mappings/realm")

        # Build desired roles array from YAML (validate all roles exist)
        DESIRED_ROLES="["
        for j in $(seq 0 $((ROLES_COUNT - 1))); do
            ROLE_NAME=$(yq -r ".clients[$i].service_account_roles[$j]" "$KC_APP_REALM_MACHINE_CLIENT_YAML")
            ROLE_OBJ=$(echo "$AVAILABLE_ROLES" | jq ".[] | select(.name == \"$ROLE_NAME\")")

            if [ -z "$ROLE_OBJ" ]; then
                echo "❌ Error: Role $ROLE_NAME not found for client $CLIENT_ID" >&2
                exit 1
            fi

            if [ "$DESIRED_ROLES" != "[" ]; then
                DESIRED_ROLES="$DESIRED_ROLES,"
            fi
            DESIRED_ROLES="$DESIRED_ROLES$ROLE_OBJ"
        done
        DESIRED_ROLES="$DESIRED_ROLES]"

        # Calculate roles to ADD (in desired but not in current)
        ROLES_TO_ADD=$(jq -n \
            --argjson desired "$DESIRED_ROLES" \
            --argjson current "$CURRENT_ROLES" \
            '$desired - ($desired - ($desired - $current))')

        # Calculate roles to REMOVE (in current but not in desired)
        ROLES_TO_REMOVE=$(jq -n \
            --argjson desired "$DESIRED_ROLES" \
            --argjson current "$CURRENT_ROLES" \
            '$current - ($current - ($current - $desired))')

        # Add missing roles
        if [ "$(echo "$ROLES_TO_ADD" | jq 'length')" -gt 0 ]; then
            ADD_RESPONSE=$(curl -s -X POST "${KC_BASE_URL}/admin/realms/${REALM_NAME}/users/$SA_USER_ID/role-mappings/realm" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "$ROLES_TO_ADD" \
                -w "\n%{http_code}")

            HTTP_CODE=$(echo "$ADD_RESPONSE" | tail -n1)

            if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
                ADDED_NAMES=$(echo "$ROLES_TO_ADD" | jq -r '[.[].name] | join(", ")')
                echo "✅ Added roles to $CLIENT_ID: $ADDED_NAMES"
                ROLES_CHANGED=true
                CLIENT_CHANGES="${CLIENT_CHANGES:+$CLIENT_CHANGES, }roles added: $ADDED_NAMES"
            else
                echo "❌ Failed to add roles to $CLIENT_ID" >&2
                echo "Response: $ADD_RESPONSE" >&2
                exit 1
            fi
        fi

        # Remove obsolete roles
        if [ "$(echo "$ROLES_TO_REMOVE" | jq 'length')" -gt 0 ]; then
            REMOVE_RESPONSE=$(curl -s -X DELETE "${KC_BASE_URL}/admin/realms/${REALM_NAME}/users/$SA_USER_ID/role-mappings/realm" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "$ROLES_TO_REMOVE" \
                -w "\n%{http_code}")

            HTTP_CODE=$(echo "$REMOVE_RESPONSE" | tail -n1)

            if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
                REMOVED_NAMES=$(echo "$ROLES_TO_REMOVE" | jq -r '[.[].name] | join(", ")')
                echo "✅ Removed roles from $CLIENT_ID: $REMOVED_NAMES"
                ROLES_CHANGED=true
                CLIENT_CHANGES="${CLIENT_CHANGES:+$CLIENT_CHANGES, }roles removed: $REMOVED_NAMES"
            else
                echo "❌ Failed to remove roles from $CLIENT_ID" >&2
                echo "Response: $REMOVE_RESPONSE" >&2
                exit 1
            fi
        fi

        # Report if no changes needed
        if [ "$(echo "$ROLES_TO_ADD" | jq 'length')" -eq 0 ] && [ "$(echo "$ROLES_TO_REMOVE" | jq 'length')" -eq 0 ]; then
            ROLE_NAMES=$(yq -r ".clients[$i].service_account_roles | join(\", \")" "$KC_APP_REALM_MACHINE_CLIENT_YAML")
            echo "✅ Roles already in sync for $CLIENT_ID: $ROLE_NAMES"
        fi
    fi

    # Reclassify from Unmodified to Updated if only roles changed
    if [ "$CLIENT_WAS_UNMODIFIED" = true ] && [ "$ROLES_CHANGED" = true ]; then
        UNMODIFIED_COUNT=$((UNMODIFIED_COUNT - 1))
        UPDATED_COUNT=$((UPDATED_COUNT + 1))
        NEW_UNMODIFIED=""
        IFS=',' read -ra _ITEMS <<< "$UNMODIFIED_ITEMS"
        for _item in "${_ITEMS[@]}"; do
            _item="${_item# }"
            if [ "$_item" != "$CLIENT_ID" ]; then
                NEW_UNMODIFIED="${NEW_UNMODIFIED:+$NEW_UNMODIFIED, }$_item"
            fi
        done
        UNMODIFIED_ITEMS="$NEW_UNMODIFIED"
    fi

    # Append to UPDATED_ITEMS with change details
    if [ "$CLIENT_PROPS_UPDATED" = true ] || { [ "$CLIENT_WAS_UNMODIFIED" = true ] && [ "$ROLES_CHANGED" = true ]; }; then
        UPDATED_ENTRY="$CLIENT_ID"
        if [ -n "$CLIENT_CHANGES" ]; then
            UPDATED_ENTRY="$CLIENT_ID ($CLIENT_CHANGES)"
        fi
        if [ -z "$UPDATED_ITEMS" ]; then
            UPDATED_ITEMS="$UPDATED_ENTRY"
        else
            UPDATED_ITEMS=$(printf '%s\n%s' "$UPDATED_ITEMS" "$UPDATED_ENTRY")
        fi
    fi
done

# Remove clients containing idempotency_key that are not in YAML
# Skip deletion when there are no valid entries (e.g. NOK test files) to avoid wiping existing clients
if [ ${#VALID_INDICES[@]} -eq 0 ]; then
    echo "⏭️  Skipping deletion check (no valid entries in YAML)"
else
    echo "🔍 Checking for clients to remove..."

    # Get all clients in realm
    ALL_CLIENTS=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients")

    # Find machine clients containing idempotency_key that are not in YAML
    # Only target clients with serviceAccountsEnabled=true and standardFlowEnabled=false (machine clients)
    CLIENTS_TO_REMOVE=$(echo "$ALL_CLIENTS" | jq -r --argjson desired "$DESIRED_CLIENT_IDS" --arg idempotencySubstr "${IDEMPOTENCY_SUBSTR}" \
        '[.[] | select(.clientId | contains($idempotencySubstr)) | select(.serviceAccountsEnabled == true and .standardFlowEnabled == false) | select([.clientId] | inside($desired) | not) | {id: .id, clientId: .clientId}] | .[]')

    if [ -n "$CLIENTS_TO_REMOVE" ]; then
        echo "$CLIENTS_TO_REMOVE" | jq -c '.' | while IFS= read -r CLIENT_OBJ; do
            CLIENT_UUID=$(echo "$CLIENT_OBJ" | jq -r '.id')
            CLIENT_ID=$(echo "$CLIENT_OBJ" | jq -r '.clientId')

            echo "🗑️  Removing client $CLIENT_ID (not in YAML)..."
            DELETE_RESPONSE=$(curl -s -X DELETE "${KC_BASE_URL}/admin/realms/${REALM_NAME}/clients/$CLIENT_UUID" \
                -H "Authorization: Bearer $TOKEN" \
                -w "%{http_code}")

            if [ "$DELETE_RESPONSE" = "204" ] || [ "$DELETE_RESPONSE" = "200" ]; then
                echo "✅ Client $CLIENT_ID removed successfully"
                DELETED_COUNT=$((DELETED_COUNT + 1))
                if [ -z "$DELETED_ITEMS" ]; then
                    DELETED_ITEMS="$CLIENT_ID"
                else
                    DELETED_ITEMS="$DELETED_ITEMS, $CLIENT_ID"
                fi
            else
                echo "❌ Failed to remove client $CLIENT_ID" >&2
                echo "Response: $DELETE_RESPONSE" >&2
                exit 1
            fi
        done
    else
        echo "✅ No clients to remove"
    fi
fi

echo ""
echo "📊 Summary:"
if [ $CREATED_COUNT -gt 0 ]; then
    echo "  Created: $CREATED_COUNT client(s) - $CREATED_ITEMS"
else
    echo "  Created: 0 client(s)"
fi
if [ $UPDATED_COUNT -gt 0 ]; then
    echo "  Updated: $UPDATED_COUNT client(s)"
    while IFS= read -r _line; do
        echo "    - $_line"
    done <<< "$UPDATED_ITEMS"
else
    echo "  Updated: 0 client(s)"
fi
if [ $DELETED_COUNT -gt 0 ]; then
    echo "  Deleted: $DELETED_COUNT client(s) - $DELETED_ITEMS"
else
    echo "  Deleted: 0 client(s)"
fi
if [ $UNMODIFIED_COUNT -gt 0 ]; then
    echo "  Unmodified: $UNMODIFIED_COUNT client(s) - $UNMODIFIED_ITEMS"
else
    echo "  Unmodified: 0 client(s)"
fi
if [ $REJECTED_COUNT -gt 0 ]; then
    echo "  Rejected: $REJECTED_COUNT client(s) - $REJECTED_ITEMS"
else
    echo "  Rejected: 0 client(s)"
fi
echo ""
echo "✅ Machine clients setup completed"
