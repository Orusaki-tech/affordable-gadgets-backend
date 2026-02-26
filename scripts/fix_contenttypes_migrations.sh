#!/usr/bin/env sh
# One-time fix when production DB has django_content_type already in modern
# schema (no "name" column) but migration history is out of sync.
# Run once: railway run sh scripts/fix_contenttypes_migrations.sh
set -eu
echo "Faking contenttypes.0002 (table already has no 'name' column)..."
python manage.py migrate contenttypes 0002_remove_content_type_name --fake --noinput
echo "Running remaining migrations..."
python manage.py migrate --noinput
echo "Done."
