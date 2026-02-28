#!/bin/bash
# Script to check admin count via API
# Usage: ./check_admin_count.sh [API_BASE_URL] [AUTH_TOKEN]

API_BASE_URL=${1:-"https://affordable-gadgets-backend.onrender.com"}
AUTH_TOKEN=${2:-""}

echo "=========================================="
echo "CHECKING ADMIN COUNT"
echo "=========================================="
echo "API Base URL: $API_BASE_URL"
echo ""

if [ -z "$AUTH_TOKEN" ]; then
    echo "⚠️  No auth token provided. The /admins/ endpoint requires superuser authentication."
    echo ""
    echo "To get admin count via API, you need to:"
    echo "1. Login as superuser to get a token"
    echo "2. Call: ./check_admin_count.sh $API_BASE_URL YOUR_TOKEN"
    echo ""
    echo "Alternatively, use Django management command:"
    echo "  python manage.py list_admins"
    echo ""
    exit 1
fi

echo "Calling API endpoint: $API_BASE_URL/api/inventory/admins/"
echo ""

RESPONSE=$(curl -k -s -w "\n%{http_code}" -X GET "$API_BASE_URL/api/inventory/admins/" \
  -H "Authorization: Token $AUTH_TOKEN" \
  -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP Status Code: $HTTP_CODE"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
    echo "Response:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    echo ""
    
    # Extract count
    COUNT=$(echo "$BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('count', len(data.get('results', []))))" 2>/dev/null)
    
    if [ -n "$COUNT" ]; then
        echo "=========================================="
        echo "✅ Total Admins: $COUNT"
        echo "=========================================="
    fi
else
    echo "❌ Failed to retrieve admin list"
    echo "Response: $BODY"
    echo ""
    echo "Possible reasons:"
    echo "  - Invalid or expired token"
    echo "  - User is not a superuser"
    echo "  - Server error"
fi
