"""
One-time fix: ensure contenttypes.0001_initial and 0002_remove_content_type_name
are recorded in django_migrations when the DB table already exists in modern shape
(no "name" column). Run: railway run python manage.py ensure_contenttypes_migrations
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Ensure contenttypes 0001 and 0002 are in django_migrations (insert if missing)."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            for app, name in [
                ("contenttypes", "0001_initial"),
                ("contenttypes", "0002_remove_content_type_name"),
            ]:
                cursor.execute(
                    "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s",
                    [app, name],
                )
                if cursor.fetchone():
                    self.stdout.write(f"Already recorded: {app}.{name}")
                else:
                    cursor.execute(
                        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
                        [app, name],
                    )
                    self.stdout.write(self.style.SUCCESS(f"Inserted: {app}.{name}"))
        self.stdout.write(self.style.SUCCESS("Done. Run: python manage.py migrate --noinput"))
