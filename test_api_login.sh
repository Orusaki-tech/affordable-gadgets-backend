#!/bin/bash
# Test script to test Fabian's login via API
# Usage: ./test_api_login.sh [API_BASE_URL]

API_BASE_URL=${1:-"http://localhost:8000"}
EMAIL="fabian@shwariphones.com"
PASSWORD="00000000"

echo "=========================================="
echo "TESTING FABIAN'S LOGIN VIA API"
echo "=========================================="
echo "API Base URL: $API_BASE_URL"
echo "Email: $EMAIL"
echo ""

# Test login endpoint
echo "Testing login endpoint: $API_BASE_URL/api/auth/token/login/"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE_URL/api/auth/token/login/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMAIL&password=$PASSWORD")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP Status Code: $HTTP_CODE"
echo "Response Body:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
    TOKEN=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null)
    
    if [ -n "$TOKEN" ]; then
        echo "✅ LOGIN SUCCESS!"
        echo "Token received: ${TOKEN:0:20}..."
        echo ""
        
        # Test admin profile endpoint
        echo "Testing admin profile endpoint: $API_BASE_URL/api/inventory/profiles/admin/"
        echo ""
        
        PROFILE_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE_URL/api/inventory/profiles/admin/" \
          -H "Authorization: Token $TOKEN" \
          -H "Content-Type: application/json")
        
        PROFILE_HTTP_CODE=$(echo "$PROFILE_RESPONSE" | tail -n1)
        PROFILE_BODY=$(echo "$PROFILE_RESPONSE" | sed '$d')
        
        echo "Profile HTTP Status Code: $PROFILE_HTTP_CODE"
        echo "Profile Response Body:"
        echo "$PROFILE_BODY" | python3 -m json.tool 2>/dev/null || echo "$PROFILE_BODY"
        
        if [ "$PROFILE_HTTP_CODE" = "200" ]; then
            echo ""
            echo "✅ ADMIN PROFILE RETRIEVAL SUCCESS!"
            echo "✅ Full login flow works correctly!"
        else
            echo ""
            echo "⚠️  Login succeeded but admin profile retrieval failed"
            echo "   This might indicate a permission issue"
        fi
    else
        echo "⚠️  Login returned 200 but no token in response"
    fi
else
    echo "❌ LOGIN FAILED"
    echo ""
    echo "Possible reasons:"
    echo "  - Invalid credentials"
    echo "  - User does not have is_staff=True"
    echo "  - User account is inactive"
    echo "  - Server error"
fi
