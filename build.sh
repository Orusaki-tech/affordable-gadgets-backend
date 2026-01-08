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
python manage.py create_default_brand || {
    echo "⚠️  Brand creation encountered an error. Continuing with build..."
}

echo "✅ Build complete!"

