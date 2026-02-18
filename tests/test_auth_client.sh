#!/bin/bash

# Utility script to authorize and save bearer token
# Expects BACKEND_BASE_URL environment variable to be set
# Expects CLIENT_ID and CLIENT_SECRET environment variables
# Optionally accepts API_VERSION environment variable (defaults to v0)
# Saves token to .bearer_token for use by other test scripts

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    exit 1
fi

if [ -z "$CLIENT_ID" ]; then
    echo "❌ Error: CLIENT_ID environment variable is not set"
    exit 1
fi

if [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Error: CLIENT_SECRET environment variable is not set"
    exit 1
fi

# Default API version to v0 if not set
API_VERSION=${API_VERSION:-v0}

# Function to authorize and save token
authorize() {
    local client_id="$1"
    local client_secret="$2"

    echo "🔐 Authorizing with client: ${client_id}"

    # Request token using client_credentials grant type
    response=$(curl -s -w "\n%{http_code}" -X POST \
      -H "Content-Type: application/x-www-form-urlencoded" \
      --data-urlencode "grant_type=client_credentials" \
      --data-urlencode "client_id=${client_id}" \
      --data-urlencode "client_secret=${client_secret}" \
      "${BACKEND_BASE_URL}/api/${API_VERSION}/auth/token")

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        access_token=$(echo "$body" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"\([^"]*\)"/\1/')

        if [ -n "$access_token" ]; then
            mkdir -p ./tmp
            echo "$access_token" > ./tmp/.bearer_token
            export BEARER_TOKEN="$access_token"
            echo "✅ Token saved to ./tmp/.bearer_token"
            return 0
        else
            echo "❌ Failed to extract access token from response"
            return 1
        fi
    elif [ "$http_code" -eq 401 ]; then
        echo "❌ Unauthorized - invalid credentials"
        return 1
    else
        echo "❌ Authorization failed with HTTP status $http_code"
        echo "Response: $body"
        return 1
    fi
}

# Call authorize function
authorize "$CLIENT_ID" "$CLIENT_SECRET"
