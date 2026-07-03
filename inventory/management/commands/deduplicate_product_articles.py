"""Remove duplicate blog articles published under multiple product URLs.

Usage::

    python manage.py deduplicate_product_articles --dry-run
    python manage.py deduplicate_product_articles
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from inventory.seo_structural import deduplicate_product_articles


class Command(BaseCommand):
    help = "Delete cross-product duplicate articles, keeping the canonical copy."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview deletions without writing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        stats = deduplicate_product_articles(dry_run=dry_run)

        self.stdout.write(f"Published articles scanned: {stats.scanned}")
        self.stdout.write(f"Duplicates to remove: {stats.deleted}")
        self.stdout.write(f"Skipped: {stats.skipped}")

        for note in stats.notes[:40]:
            self.stdout.write(f"  {note}")
        if len(stats.notes) > 40:
            self.stdout.write(f"  ... and {len(stats.notes) - 40} more")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run only — no database changes made."))
        else:
            self.stdout.write(self.style.SUCCESS("\nArticle deduplication complete."))
