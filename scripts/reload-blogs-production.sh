#!/usr/bin/env bash
set -eu

# reload-blogs-production.sh — Reload all 159 blog articles to production database.
#
# This script connects to the production Render database and reloads all blog batches.
# Must be run on a machine with access to production database credentials.
#
# Usage:
#   ./scripts/reload-blogs-production.sh
#
# The script:
# 1. Sets DATABASE_URL to production Render database
# 2. Runs load_blog_batch --force to reload all articles
# 3. Verifies the reload was successful

set -a
# Load production database credentials from .env
DB_USER="affordable_gadgets_user"
DB_PASSWORD="xwdwzdnCcVgdqxYYuk6XErBegYSGUneI"
DB_HOST="dpg-d5cfcf2li9vc73ceh8q0-a.oregon-postgres.render.com"
DB_NAME="affordable_gadgets"
DB_PORT="5432"

export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
set +a

echo "📚 Reloading all blog articles to production database..."
echo "   Database: ${DB_HOST}"
echo "   Database: ${DB_NAME}"
echo ""

python manage.py load_blog_batch --force

echo ""
echo "✅ Blog reload complete!"
echo "   Verify: curl https://api.affordable-gadgetske.com/api/v1/public/products/169/ | grep has_published_article"
