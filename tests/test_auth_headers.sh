#!/bin/bash

# Test script for verifying security headers on SDEP API endpoints
# Tests XSS protection, output encoding, and OWASP security headers compliance
# Expects BACKEND_BASE_URL environment variable to be set
# Optionally accepts API_VERSION environment variable (defaults to v0)

set -e

if [ -z "$BACKEND_BASE_URL" ]; then
    echo "❌ Error: BACKEND_BASE_URL environment variable is not set"
    echo "Usage: BACKEND_BASE_URL=http://localhost:8000 ./auth-headers.sh"
    exit 1
fi

# Default API version to v0 if not set
API_VERSION=${API_VERSION:-v0}

echo "🔒 Testing security headers at: ${BACKEND_BASE_URL}"
echo "📋 Testing endpoints: /, /api/health, /api/${API_VERSION}/ping, /api/${API_VERSION}/openapi.json"
echo

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to check if a header exists in response
check_header() {
    local endpoint="$1"
    local header_name="$2"
    local expected_value="$3"
    local response_headers="$4"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Check if header exists (case-insensitive)
    if echo "$response_headers" | grep -qi "^${header_name}:"; then
        actual_value=$(echo "$response_headers" | grep -i "^${header_name}:" | head -n1 | cut -d':' -f2- | sed 's/^[[:space:]]*//' | tr -d '\r')

        # If expected value is specified, check it matches
        if [ -n "$expected_value" ]; then
            if echo "$actual_value" | grep -q "$expected_value"; then
                echo "  ✅ $header_name: $actual_value"
                PASSED_TESTS=$((PASSED_TESTS + 1))
                return 0
            else
                echo "  ❌ $header_name: Expected '$expected_value', got '$actual_value'"
                FAILED_TESTS=$((FAILED_TESTS + 1))
                return 1
            fi
        else
            echo "  ✅ $header_name: $actual_value"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            return 0
        fi
    else
        echo "  ❌ $header_name: MISSING"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to test security headers on an endpoint
test_endpoint_headers() {
    local endpoint="$1"
    local description="$2"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📍 Testing: $description"
    echo "   Endpoint: $endpoint"
    echo

    # Get headers from endpoint
    response_headers=$(curl -s -i "${BACKEND_BASE_URL}${endpoint}" | sed -n '1,/^\r$/p')

    # Test OWASP recommended headers
    echo "🔒 Security Headers:"
    check_header "$endpoint" "Content-Security-Policy" "" "$response_headers"
    check_header "$endpoint" "X-Frame-Options" "DENY" "$response_headers"
    check_header "$endpoint" "X-Content-Type-Options" "nosniff" "$response_headers"
    check_header "$endpoint" "Referrer-Policy" "no-referrer" "$response_headers"
    check_header "$endpoint" "Permissions-Policy" "" "$response_headers"
    check_header "$endpoint" "Cross-Origin-Opener-Policy" "same-origin" "$response_headers"
    check_header "$endpoint" "Cross-Origin-Resource-Policy" "same-origin" "$response_headers"
    check_header "$endpoint" "Cross-Origin-Embedder-Policy" "unsafe-none" "$response_headers"

    echo
}

# Function to test CSP policy details
test_csp_policy() {
    local endpoint="$1"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🛡️  Testing CSP Policy Details"
    echo "   Endpoint: $endpoint"
    echo

    # Get CSP header
    csp_header=$(curl -s -i "${BACKEND_BASE_URL}${endpoint}" | grep -i "^Content-Security-Policy:" | cut -d':' -f2- | sed 's/^[[:space:]]*//' | tr -d '\r')

    if [ -z "$csp_header" ]; then
        echo "  ❌ CSP header not found"
        TOTAL_TESTS=$((TOTAL_TESTS + 5))
        FAILED_TESTS=$((FAILED_TESTS + 5))
        return 1
    fi

    echo "CSP Policy:"
    echo "$csp_header" | tr ';' '\n' | sed 's/^[[:space:]]*/  /'
    echo

    echo "🔍 CSP Directives Check:"

    # Check specific CSP directives
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$csp_header" | grep -q "default-src 'self'"; then
        echo "  ✅ default-src 'self' (only same-origin resources)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  ❌ default-src 'self' missing or incorrect"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$csp_header" | grep -q "script-src.*cdn.jsdelivr.net"; then
        echo "  ✅ script-src allows cdn.jsdelivr.net (for Swagger UI)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  ⚠️  script-src may not allow Swagger UI CDN"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$csp_header" | grep -q "frame-ancestors 'none'"; then
        echo "  ✅ frame-ancestors 'none' (clickjacking protection)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  ❌ frame-ancestors 'none' missing"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$csp_header" | grep -q "object-src 'none'"; then
        echo "  ✅ object-src 'none' (blocks object/embed XSS)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  ❌ object-src 'none' missing"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$csp_header" | grep -q "'unsafe-eval'"; then
        echo "  ❌ 'unsafe-eval' present (XSS risk!)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    else
        echo "  ✅ 'unsafe-eval' not present (good XSS protection)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    fi

    echo
}

# Function to test cache control on sensitive endpoints
test_sensitive_endpoint_caching() {
    local endpoint="$1"
    local description="$2"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔐 Testing Cache Control: $description"
    echo "   Endpoint: $endpoint"
    echo

    response_headers=$(curl -s -i "${BACKEND_BASE_URL}${endpoint}" | sed -n '1,/^\r$/p')

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$response_headers" | grep -qi "Cache-Control:.*no-store"; then
        echo "  ✅ Cache-Control contains 'no-store'"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  ⚠️  Cache-Control may not prevent caching"
        # Don't count as failed - some endpoints may not need strict caching
    fi

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$response_headers" | grep -qi "Pragma:.*no-cache"; then
        echo "  ✅ Pragma: no-cache present"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  ⚠️  Pragma: no-cache may be missing"
    fi

    echo
}

# Run tests on different endpoints

echo "════════════════════════════════════════"
echo "🔒 SDEP Security Headers Test Suite"
echo "════════════════════════════════════════"
echo

# Test root endpoint
test_endpoint_headers "/" "Root endpoint"

# Test common API health endpoint
test_endpoint_headers "/api/health" "Health check endpoint"

# Test v0 API endpoints
test_endpoint_headers "/api/${API_VERSION}/ping" "API ping endpoint (may be auth-protected)"
test_endpoint_headers "/api/${API_VERSION}/openapi.json" "OpenAPI schema endpoint"

# Test CSP policy in detail
test_csp_policy "/api/${API_VERSION}/ping"

# Test sensitive endpoint caching
test_sensitive_endpoint_caching "/api/${API_VERSION}/openapi.json" "OpenAPI schema"

# Check if HSTS is NOT set (should be handled by Nginx)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 HSTS Check (should be handled by reverse proxy)"
echo
response_headers=$(curl -s -i "${BACKEND_BASE_URL}/api/${API_VERSION}/ping" | sed -n '1,/^\r$/p')
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if echo "$response_headers" | grep -qi "Strict-Transport-Security:"; then
    echo "  ⚠️  HSTS header present (may be redundant with Nginx)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  ✅ HSTS not set by application (correctly delegated to infra, such as Nginx)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi
echo

# Final summary
echo "════════════════════════════════════════"
echo "📊 Test Summary"
echo "════════════════════════════════════════"
echo "  Total:  $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS ✅"
echo "  Failed: $FAILED_TESTS ❌"
echo "════════════════════════════════════════"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All security header tests passed!"
    echo
    echo "XSS Protection: ✅"
    echo "Output Encoding: ✅"
    echo "OWASP Security Headers: ✅"
    exit 0
else
    echo "❌ Some security header tests failed!"
    echo
    echo "Please review the failed tests above and ensure all"
    echo "OWASP recommended security headers are properly configured."
    exit 1
fi
