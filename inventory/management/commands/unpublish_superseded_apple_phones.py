"""Unpublish generic Apple phone products superseded by E-SIM / SIM stock-list names.

Apple phones in the supplier list are separate products per SIM type because
E-SIM and physical SIM units have different prices, e.g. ``iPhone 17 E-SIM`` vs
``iPhone 17 SIM``. Legacy catalog entries like plain ``iPhone 17`` (no SIM type)
should not stay published once stock-list replacements exist.

For each superseded product this command:
1. Repoints articles and images to the canonical E-SIM product (SIM fallback)
2. Sets ``is_published=False`` on the legacy row

Usage::

    python manage.py unpublish_superseded_apple_phones --dry-run
    python manage.py unpublish_superseded_apple_phones
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Product, ProductArticle, ProductImage

# Legacy supplier / Dubai naming — already explicit about SIM type or region.
_LEGACY_MARKERS = ("(dubai)", "(official)", " e-sim", " sim")


def _normalize_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _is_legacy_generic_apple_phone(name: str) -> bool:
    if not name.startswith("iPhone"):
        return False
    lower = name.lower()
    if re.match(r"^iphone \d+e$", lower):
        # e-series models (17e, 16e) are canonical product names — not superseded by *E SIM SKUs.
        return False
    return not any(marker in lower for marker in _LEGACY_MARKERS)


def _replacement_names(generic_name: str) -> list[str]:
    """Candidate stock-list product names that replace a generic iPhone row."""
    base = generic_name.strip()
    return [f"{base} E-SIM", f"{base} SIM"]


def _is_direct_sim_variant(key: str, base_key: str) -> tuple[bool, bool]:
    """True when ``key`` is ``base_key`` plus an E-SIM or SIM suffix only."""
    if not key.startswith(base_key + " "):
        return False, False
    suffix = key[len(base_key) + 1 :]
    if suffix.startswith("e-sim"):
        return True, True
    if suffix == "sim" or suffix.endswith(" sim"):
        return True, False
    return False, False


def _find_replacement_product(
    generic: Product, published_by_name: dict[str, Product]
) -> Product | None:
    for candidate in _replacement_names(generic.product_name):
        product = published_by_name.get(_normalize_key(candidate))
        if product is not None:
            return product

    base_key = _normalize_key(generic.product_name)
    esim = None
    sim = None
    for key, product in published_by_name.items():
        is_match, is_esim = _is_direct_sim_variant(key, base_key)
        if not is_match:
            continue
        if is_esim:
            esim = product
        else:
            sim = product
    return esim or sim


def unpublish_superseded_apple_phones(*, dry_run: bool = False) -> dict[str, int]:
    published = list(
        Product.objects.filter(
            brand__iexact="Apple",
            product_type="PH",
            is_published=True,
            is_discontinued=False,
        ).order_by("product_name")
    )
    published_by_name = {_normalize_key(p.product_name): p for p in published}

    stats = {
        "candidates": 0,
        "unpublished": 0,
        "articles_moved": 0,
        "images_moved": 0,
        "skipped_no_replacement": 0,
    }

    for product in published:
        if not _is_legacy_generic_apple_phone(product.product_name):
            continue
        stats["candidates"] += 1
        replacement = _find_replacement_product(product, published_by_name)
        if replacement is None:
            stats["skipped_no_replacement"] += 1
            continue

        stats["articles_moved"] += ProductArticle.objects.filter(product=product).count()
        stats["images_moved"] += ProductImage.objects.filter(product=product).count()

        if dry_run:
            stats["unpublished"] += 1
            continue

        with transaction.atomic():
            ProductArticle.objects.filter(product=product).update(product=replacement)
            ProductImage.objects.filter(product=product).update(product=replacement)
            Product.objects.filter(pk=product.pk).update(is_published=False)
        stats["unpublished"] += 1

    return stats


class Command(BaseCommand):
    help = (
        "Unpublish generic Apple iPhone products when E-SIM / SIM stock-list "
        "replacements exist (different prices require separate product names)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes."))

        stats = unpublish_superseded_apple_phones(dry_run=dry_run)

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=== Unpublish superseded Apple phones ==="))
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value}")

        if dry_run and stats["unpublished"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nRe-run without --dry-run to unpublish legacy generic iPhone products."
                )
            )
