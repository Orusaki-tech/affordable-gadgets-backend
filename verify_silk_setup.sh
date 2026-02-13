#!/bin/bash
# Verification script for Silk setup
# This script checks if all requirements for Silk UI are met

set -e

echo "🔍 Verifying Silk Setup..."
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if SILKY_ENABLED is set
echo "1. Checking SILKY_ENABLED environment variable..."
if [ -z "$SILKY_ENABLED" ]; then
    echo -e "${YELLOW}⚠️  SILKY_ENABLED is not set. Defaulting to 'false'${NC}"
    SILKY_ENABLED=false
else
    echo -e "${GREEN}✅ SILKY_ENABLED=$SILKY_ENABLED${NC}"
fi

if [ "$SILKY_ENABLED" != "true" ]; then
    echo -e "${YELLOW}⚠️  Silk is not enabled. Set SILKY_ENABLED=true to enable it.${NC}"
    echo ""
fi

# Check if django-silk is installed
echo "2. Checking if django-silk is installed..."
if python -c "import silk" 2>/dev/null; then
    echo -e "${GREEN}✅ django-silk is installed${NC}"
else
    echo -e "${RED}❌ django-silk is not installed. Run: pip install django-silk${NC}"
    exit 1
fi

# Check if static files are collected
echo "3. Checking if static files are collected..."
if [ -d "staticfiles" ] && [ "$(ls -A staticfiles 2>/dev/null)" ]; then
    echo -e "${GREEN}✅ Static files directory exists and is not empty${NC}"
    
    # Check if Silk static files are present
    if [ -d "staticfiles/silk" ]; then
        echo -e "${GREEN}✅ Silk static files are present in staticfiles/silk/${NC}"
    else
        echo -e "${YELLOW}⚠️  Silk static files not found. Run: python manage.py collectstatic --noinput${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Static files directory is empty or doesn't exist${NC}"
    echo -e "${YELLOW}   Run: python manage.py collectstatic --noinput${NC}"
fi

# Check Django settings
echo "4. Checking Django settings..."
if python manage.py check --deploy 2>&1 | grep -q "Silk"; then
    echo -e "${GREEN}✅ Silk is configured in Django settings${NC}"
else
    echo -e "${YELLOW}⚠️  Could not verify Silk configuration in settings${NC}"
fi

# Check if migrations are up to date
echo "5. Checking database migrations..."
if python manage.py showmigrations silk 2>/dev/null | grep -q "\[X\]"; then
    echo -e "${GREEN}✅ Silk migrations are applied${NC}"
else
    echo -e "${YELLOW}⚠️  Silk migrations may not be applied. Run: python manage.py migrate${NC}"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$SILKY_ENABLED" = "true" ]; then
    echo -e "${GREEN}✅ Silk Setup Verification Complete${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Ensure SILKY_ENABLED=true is set in your environment"
    echo "2. Run: python manage.py collectstatic --noinput"
    echo "3. Run: python manage.py migrate"
    echo "4. Access Silk UI at: https://your-domain.com/silk/"
    echo "5. Login with a staff user account"
else
    echo -e "${YELLOW}⚠️  Silk is not enabled${NC}"
    echo ""
    echo "To enable Silk:"
    echo "1. Set SILKY_ENABLED=true in your environment variables"
    echo "2. Restart your application"
    echo "3. Run this verification script again"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
