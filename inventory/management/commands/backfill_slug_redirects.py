"""Audit and backfill ProductSlugRedirect rows for legacy product URLs.

Finds old slugs from:
- products_final_schema.csv (historical catalog)
- slugify(product_name / brand+model_series) variants
- explicit --slug old=new pairs

Usage::

    python manage.py backfill_slug_redirects --audit
    python manage.py backfill_slug_redirects --dry-run
    python manage.py backfill_slug_redirects
    python manage.py backfill_slug_redirects --slug samsung-galaxy-a06=samsung-a-series-galaxy-a06
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Product, ProductSlugRedirect
from inventory.slug_utils import slugify_seo

GENERIC_TOKENS = frozenset(
    {
        "samsung",
        "apple",
        "google",
        "xiaomi",
        "vivo",
        "tecno",
        "infinix",
        "oppo",
        "oneplus",
        "realme",
        "huawei",
        "nokia",
        "galaxy",
        "iphone",
        "ipad",
        "macbook",
        "phone",
        "series",
        "pro",
        "max",
        "plus",
        "ultra",
        "lite",
        "mini",
        "lte",
        "5g",
        "4g",
        "gb",
        "ram",
        "the",
        "and",
        "for",
        "with",
        "new",
    }
)


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _meaningful_tokens(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in slugify_seo(part or "").split("-"):
            if token and token not in GENERIC_TOKENS:
                tokens.add(token)
    return tokens


def _names_compatible(csv_name: str, product: Product) -> bool:
    left = _normalize_name(csv_name)
    right = _normalize_name(product.product_name)
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    overlap = _meaningful_tokens(left) & _meaningful_tokens(right)
    return len(overlap) >= 2 or any(re.search(r"\d", token) for token in overlap)


def _slug_pair_compatible(old_slug: str, product: Product) -> bool:
    if not old_slug or old_slug == (product.slug or ""):
        return False
    old_tokens = _meaningful_tokens(old_slug)
    live_tokens = _meaningful_tokens(
        product.slug or "",
        product.product_name or "",
        product.model_series or "",
        product.brand or "",
    )
    if not old_tokens:
        return False
    overlap = old_tokens & live_tokens
    return len(overlap) >= 2 or (
        len(overlap) >= 1 and any(re.search(r"\d", token) for token in overlap)
    )


def _variant_slugs(product: Product) -> set[str]:
    brand = (product.brand or "").strip()
    name = (product.product_name or "").strip()
    series = (product.model_series or "").strip()
    variants = {
        slugify_seo(name),
        slugify_seo(f"{brand} {name}"),
        slugify_seo(f"{brand} {series}"),
        slugify_seo(series),
        slugify_seo(f"{brand}-{series}"),
    }
    return {slug for slug in variants if slug}


def _parse_slug_pairs(values: list[str] | None) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in values or []:
        if "=" not in raw:
            continue
        old_slug, new_slug = raw.split("=", 1)
        old_slug = old_slug.strip()
        new_slug = new_slug.strip()
        if old_slug and new_slug:
            pairs.append((old_slug, new_slug))
    return pairs


class Command(BaseCommand):
    help = "Audit and backfill ProductSlugRedirect rows for legacy storefront slugs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--audit",
            action="store_true",
            help="Report missing redirects without writing.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview redirects that would be created.",
        )
        parser.add_argument(
            "--csv",
            default="products_final_schema.csv",
            help="CSV file with historical slugs (default: products_final_schema.csv).",
        )
        parser.add_argument(
            "--slug",
            action="append",
            dest="slug_pairs",
            metavar="OLD=NEW",
            help="Explicit old=new slug mapping (repeatable).",
        )
        parser.add_argument(
            "--published-only",
            action="store_true",
            default=True,
            help="Only consider published products (default: true).",
        )

    def handle(self, *args, **options):
        audit = options["audit"]
        dry_run = options["dry_run"]
        csv_path = Path(options["csv"])
        slug_pairs = _parse_slug_pairs(options.get("slug_pairs"))
        published_only = options["published_only"]

        products_qs = Product.objects.filter(is_discontinued=False)
        if published_only:
            products_qs = products_qs.filter(is_published=True)
        products = list(
            products_qs.only("id", "slug", "product_name", "brand", "model_series", "is_published")
        )
        products_by_slug = {(p.slug or "").strip(): p for p in products if p.slug}
        products_by_id = {p.id: p for p in products}

        existing_redirects = {
            row.old_slug: row.product_id
            for row in ProductSlugRedirect.objects.values("old_slug", "product_id")
        }

        proposals: dict[str, int] = {}
        sources: dict[str, str] = {}

        def propose(old_slug: str, product: Product, source: str) -> None:
            old_slug = (old_slug or "").strip()
            if not old_slug:
                return
            current_slug = (product.slug or "").strip()
            if old_slug == current_slug:
                return
            if old_slug in products_by_slug and products_by_slug[old_slug].id != product.id:
                return
            if old_slug in existing_redirects and existing_redirects[old_slug] != product.id:
                return
            if old_slug in proposals and proposals[old_slug] != product.id:
                return
            proposals[old_slug] = product.id
            sources[old_slug] = source

        for product in products:
            for variant in _variant_slugs(product):
                if _slug_pair_compatible(variant, product):
                    propose(variant, product, "variant")

        if csv_path.is_file():
            with csv_path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row.get("is_published", "").lower() != "true":
                        continue
                    old_slug = (row.get("slug") or "").strip()
                    if not old_slug:
                        continue
                    brand = (row.get("brand") or "").strip()
                    for product in products:
                        if brand and product.brand and brand.lower() != product.brand.lower():
                            continue
                        if not _names_compatible(row.get("product_name", ""), product):
                            continue
                        if _slug_pair_compatible(old_slug, product):
                            propose(old_slug, product, "csv")
        elif csv_path != Path("products_final_schema.csv"):
            self.stdout.write(self.style.WARNING(f"CSV not found: {csv_path}"))

        for old_slug, new_slug in slug_pairs:
            product = products_by_slug.get(new_slug)
            if not product:
                self.stdout.write(
                    self.style.WARNING(f"Skipping explicit pair {old_slug}={new_slug}: target slug not found")
                )
                continue
            propose(old_slug, product, "explicit")

        missing = []
        for old_slug, product_id in sorted(proposals.items(), key=lambda item: item[0]):
            product = products_by_id[product_id]
            current_slug = (product.slug or "").strip()
            if old_slug in existing_redirects:
                if existing_redirects[old_slug] == product_id:
                    continue
                missing.append((old_slug, current_slug, product, sources[old_slug], "conflict"))
                continue
            missing.append((old_slug, current_slug, product, sources[old_slug], "create"))

        self.stdout.write(f"Published products scanned: {len(products)}")
        self.stdout.write(f"Existing redirects: {len(existing_redirects)}")
        self.stdout.write(f"Redirect candidates: {len(missing)}")

        preview = missing[:40]
        for old_slug, current_slug, product, source, action in preview:
            self.stdout.write(
                f"  [{action}/{source}] {old_slug} -> {current_slug} "
                f"(id={product.id}, {product.product_name[:60]})"
            )
        if len(missing) > len(preview):
            self.stdout.write(f"  ... and {len(missing) - len(preview)} more")

        conflicts = [row for row in missing if row[4] == "conflict"]
        if conflicts:
            self.stdout.write(self.style.ERROR(f"\nConflicting redirects: {len(conflicts)}"))
            for old_slug, current_slug, product, source, _action in conflicts[:10]:
                self.stdout.write(
                    f"  {old_slug} points to product_id={existing_redirects[old_slug]}, "
                    f"but candidate is id={product.id} ({current_slug})"
                )
            return

        creates = [row for row in missing if row[4] == "create"]
        if audit:
            self.stdout.write(self.style.SUCCESS(f"\nAudit complete — {len(creates)} redirects missing."))
            return

        if not creates:
            self.stdout.write(self.style.SUCCESS("No new redirects needed."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDry run only — would create {len(creates)} redirects."))
            return

        to_create = [
            ProductSlugRedirect(old_slug=old_slug, product_id=product.id)
            for old_slug, _current_slug, product, _source, action in creates
            if action == "create"
        ]
        with transaction.atomic():
            ProductSlugRedirect.objects.bulk_create(to_create, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"\nCreated {len(to_create)} slug redirects."))
