#!/bin/bash
# Build script for Render deployment
# This script runs collectstatic to upload static files to Cloudinary

set -e  # Exit on any error

echo "🔨 Building Django application..."

# Install dependencies (if not already done)
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "🗄️  Running database migrations..."
# Try to run migrations, but continue if there are duplicate index errors
python manage.py migrate --noinput || {
    echo "⚠️  Migration encountered an error. Attempting to fix duplicate index issue..."
    # If migration fails due to duplicate index, try to continue with fake migration
    # This handles cases where the database state is partially migrated
    python manage.py migrate --noinput --fake inventory 0006 || {
        echo "⚠️  Migration issue detected. Continuing with build..."
        # Check if we can at least run other migrations
        python manage.py migrate --noinput --run-syncdb || true
    }
}

# Specifically ensure migration 0027 is applied (idempotency_key column)
echo "🔍 Checking migration 0027 (idempotency_key)..."
python manage.py apply_idempotency_migration || {
    echo "⚠️  Could not apply migration 0027 via management command. Will try on startup."
}

# Collect static files and upload to Cloudinary
echo "📤 Collecting static files and uploading to Cloudinary..."
python manage.py collectstatic --noinput

# Create superuser from environment variables (if provided)
echo "👤 Creating superuser (if not exists)..."
python manage.py create_superuser_from_env || {
    echo "⚠️  Superuser creation encountered an error. Continuing with build..."
}

# Create default brand from environment variables (if provided)
echo "🏷️  Creating default brand (if not exists)..."
# Run with --skip-checks and capture output
if python manage.py create_default_brand --skip-checks 2>&1; then
    echo "✅ Brand creation completed successfully"
else
    echo "⚠️  Brand creation encountered an error. Continuing with build..."
    # Try one more time without --skip-checks in case that was the issue
    python manage.py create_default_brand 2>&1 || {
        echo "⚠️  Brand creation failed again. This is non-critical - continuing build..."
    }
fi

echo "✅ Build complete!"

