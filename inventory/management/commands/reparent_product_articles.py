"""Reassign blog articles to the product that matches their headline model.

Usage::

    python manage.py reparent_product_articles --dry-run
    python manage.py reparent_product_articles
    python manage.py reparent_product_articles --mapping article_reparent.csv
    python manage.py reparent_product_articles --no-auto-detect
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from inventory.seo_structural import reparent_product_articles


class Command(BaseCommand):
    help = "Move misassigned product articles to the correct parent product."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview reparenting without writing.",
        )
        parser.add_argument(
            "--mapping",
            default="",
            help="CSV mapping file (article_id,product_slug or article_slug,from_product_slug,to_product_slug).",
        )
        parser.add_argument(
            "--no-auto-detect",
            action="store_true",
            help="Only apply explicit --mapping rows; skip headline-based detection.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        mapping = (options.get("mapping") or "").strip()
        mapping_path = Path(mapping) if mapping else None

        stats = reparent_product_articles(
            dry_run=dry_run,
            mapping_path=mapping_path,
            auto_detect=not options["no_auto_detect"],
        )

        self.stdout.write(f"Articles scanned: {stats.scanned}")
        self.stdout.write(f"Reparented: {stats.updated}")
        self.stdout.write(f"Skipped: {stats.skipped}")

        for note in stats.notes[:40]:
            self.stdout.write(f"  {note}")
        if len(stats.notes) > 40:
            self.stdout.write(f"  ... and {len(stats.notes) - 40} more")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run only — no database changes made."))
        else:
            self.stdout.write(self.style.SUCCESS("\nArticle reparenting complete."))
