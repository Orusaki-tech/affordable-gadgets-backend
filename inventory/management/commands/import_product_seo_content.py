"""Import generated SEO content (meta fields, long_description, highlights) from JSON.

Usage::

    python manage.py import_product_seo_content --dry-run /path/to/products_seo_filled.json
    python manage.py import_product_seo_content /path/to/products_seo_filled.json
    python manage.py import_product_seo_content --skip-existing /path/to/products_seo_filled.json
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Product

SEO_FIELDS = (
    "meta_title",
    "meta_description",
    "keywords",
    "long_description",
    "product_highlights",
)


class Command(BaseCommand):
    help = "Bulk-import product SEO content from products_seo_filled.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="Path to products_seo_filled.json",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview updates without writing.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip products that already have meta_title and long_description.",
        )
        parser.add_argument(
            "--published-only",
            action="store_true",
            default=True,
            help="Only update published, non-discontinued products (default: true).",
        )

    def handle(self, *args, **options):
        json_path = Path(options["json_path"])
        if not json_path.is_file():
            raise CommandError(f"File not found: {json_path}")

        dry_run = options["dry_run"]
        skip_existing = options["skip_existing"]
        published_only = options["published_only"]

        with json_path.open(encoding="utf-8") as handle:
            rows = json.load(handle)
        if not isinstance(rows, list):
            raise CommandError("Expected a JSON array of product objects.")

        updated = 0
        skipped = 0
        missing = 0
        to_update: list[Product] = []

        for row in rows:
            product_id = row.get("id")
            if not product_id:
                skipped += 1
                continue

            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                missing += 1
                self.stdout.write(
                    self.style.WARNING(f"  missing product id={product_id} ({row.get('product_name', '')})")
                )
                continue

            if published_only and (not product.is_published or product.is_discontinued):
                skipped += 1
                continue

            if skip_existing and (product.meta_title or "").strip() and (product.long_description or "").strip():
                skipped += 1
                continue

            changes: dict[str, object] = {}
            for field in SEO_FIELDS:
                value = row.get(field)
                if value is None:
                    continue
                if field == "product_highlights":
                    if not isinstance(value, list):
                        continue
                    if value == (product.product_highlights or []):
                        continue
                    changes[field] = value
                else:
                    text = str(value).strip()
                    if not text:
                        continue
                    if text == (getattr(product, field) or "").strip():
                        continue
                    changes[field] = text

            if not changes:
                skipped += 1
                continue

            self.stdout.write(
                f"  id={product.id} {product.slug}: "
                + ", ".join(f"{k}={len(str(v))} chars" if k != "product_highlights" else f"{k}={len(v)} items" for k, v in changes.items())
            )
            for field, value in changes.items():
                setattr(product, field, value)
            to_update.append(product)
            updated += 1

        self.stdout.write(
            f"\nSummary: {updated} to update, {skipped} skipped, {missing} missing (of {len(rows)} rows)"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only — no database changes made."))
            return

        if not to_update:
            self.stdout.write(self.style.SUCCESS("Nothing to update."))
            return

        with transaction.atomic():
            for product in to_update:
                product.save(update_fields=list(SEO_FIELDS))

        self.stdout.write(self.style.SUCCESS(f"Updated {len(to_update)} product(s)."))
