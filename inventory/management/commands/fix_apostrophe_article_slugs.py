"""Fix apostrophe-bug article slugs and record legacy redirects.

Usage::

    python manage.py fix_apostrophe_article_slugs --dry-run
    python manage.py fix_apostrophe_article_slugs
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from inventory.seo_structural import fix_apostrophe_article_slugs


class Command(BaseCommand):
    help = "Normalize article slugs affected by apostrophe handling and create 301 redirect rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview slug fixes without writing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        stats = fix_apostrophe_article_slugs(dry_run=dry_run)

        self.stdout.write(f"Published articles scanned: {stats.scanned}")
        self.stdout.write(f"Redirects created: {stats.created}")
        self.stdout.write(f"Slugs updated: {stats.updated}")
        self.stdout.write(f"Skipped: {stats.skipped}")

        for note in stats.notes[:40]:
            self.stdout.write(f"  {note}")
        if len(stats.notes) > 40:
            self.stdout.write(f"  ... and {len(stats.notes) - 40} more")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run only — no database changes made."))
        else:
            self.stdout.write(self.style.SUCCESS("\nApostrophe article slug fix complete."))
