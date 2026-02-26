#!/usr/bin/env sh
# One-time fix when production DB has django_content_type already in modern
# schema (no "name" column) but migration history is out of sync.
# Run once: railway run sh scripts/fix_contenttypes_migrations.sh
set -eu
echo "Ensuring contenttypes.0001 and 0002 are in django_migrations..."
python manage.py ensure_contenttypes_migrations
echo "Running remaining migrations..."
python manage.py migrate --noinput
echo "Done."
