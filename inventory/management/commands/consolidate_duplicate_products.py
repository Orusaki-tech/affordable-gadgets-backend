"""Consolidate near-duplicate product URLs into one canonical slug per product.

Usage::

    python manage.py consolidate_duplicate_products --dry-run
    python manage.py consolidate_duplicate_products
    python manage.py consolidate_duplicate_products --slug samsung-galaxy-s25-2=samsung-galaxy-s25
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from inventory.management.commands.backfill_slug_redirects import _parse_slug_pairs
from inventory.seo_structural import consolidate_duplicate_products


class Command(BaseCommand):
    help = "Unpublish duplicate products and 301-redirect their slugs to the canonical product."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing.",
        )
        parser.add_argument(
            "--slug",
            action="append",
            dest="slug_pairs",
            metavar="DUPLICATE=CANONICAL",
            help="Explicit duplicate=canonical slug pair (repeatable).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        explicit_pairs = _parse_slug_pairs(options.get("slug_pairs"))

        stats = consolidate_duplicate_products(
            dry_run=dry_run,
            explicit_pairs=explicit_pairs,
        )

        self.stdout.write(f"Published products scanned: {stats.scanned}")
        self.stdout.write(f"Redirects to create: {stats.created}")
        self.stdout.write(f"Products to unpublish: {stats.updated}")
        self.stdout.write(f"Skipped: {stats.skipped}")

        for note in stats.notes[:40]:
            self.stdout.write(f"  {note}")
        if len(stats.notes) > 40:
            self.stdout.write(f"  ... and {len(stats.notes) - 40} more")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run only — no database changes made."))
        else:
            self.stdout.write(self.style.SUCCESS("\nDuplicate product consolidation complete."))
