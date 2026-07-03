"""Unpublish test/demo products so they drop out of the public API and sitemap.

Usage::

    python manage.py unpublish_test_products --dry-run
    python manage.py unpublish_test_products
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Product

TEST_SLUG_RE = re.compile(
    r"^(test-|test\d|demo-|sample-)|(?:^|-)test(?:-|$)|test-payment|test-2test",
    re.IGNORECASE,
)


def _is_test_product(product: Product) -> bool:
    slug = (product.slug or "").strip().lower()
    name = (product.product_name or "").strip().lower()
    if TEST_SLUG_RE.search(slug):
        return True
    if name in {"test", "test1", "test payment product"}:
        return True
    if slug in {"test-payment-product", "test-2test1-test1"}:
        return True
    return False


class Command(BaseCommand):
    help = "Unpublish test/demo products from the storefront catalog."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview products that would be unpublished.",
        )
        parser.add_argument(
            "--include-unpublished",
            action="store_true",
            help="Also list already-unpublished test products.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_unpublished = options["include_unpublished"]

        queryset = Product.objects.filter(is_discontinued=False).order_by("id")
        if not include_unpublished:
            queryset = queryset.filter(is_published=True)

        matches = [product for product in queryset if _is_test_product(product)]
        if not matches:
            self.stdout.write(self.style.SUCCESS("No test products matched."))
            return

        self.stdout.write(f"Matched {len(matches)} test product(s):")
        for product in matches:
            status = "published" if product.is_published else "unpublished"
            self.stdout.write(
                f"  id={product.id:>4} [{status}] {product.slug} — {product.product_name}"
            )

        to_unpublish = [product for product in matches if product.is_published]
        if not to_unpublish:
            self.stdout.write(self.style.SUCCESS("All matched test products are already unpublished."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\nDry run only — would unpublish {len(to_unpublish)} product(s).")
            )
            return

        with transaction.atomic():
            for product in to_unpublish:
                product.is_published = False
            Product.objects.bulk_update(to_unpublish, ["is_published"])

        self.stdout.write(self.style.SUCCESS(f"\nUnpublished {len(to_unpublish)} test product(s)."))
