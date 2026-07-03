"""Reparent misassigned articles using blog JSON fixtures as source of truth.

Each fixture already declares the correct ``product_name``. This command finds
articles by headline and moves them to the product with that exact name — no
fuzzy stock-list matching.

Usage::

    python manage.py reparent_articles_from_fixtures --dry-run
    python manage.py reparent_articles_from_fixtures
    python manage.py reparent_articles_from_fixtures --generate-csv data/article_reparent_mapping.csv
"""

from __future__ import annotations

import csv
import glob
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Product, ProductArticle

BATCHES_DIR = Path(__file__).resolve().parents[3] / "blog_content" / "batches"


def _load_fixture_rows() -> list[dict]:
    rows: list[dict] = []
    for json_path in sorted(glob.glob(str(BATCHES_DIR / "*" / "*.json"))):
        with open(json_path, encoding="utf-8") as handle:
            data = json.load(handle)
        headline = (data.get("headline") or "").strip()
        product_name = (data.get("product_name") or "").strip()
        product_slug = (data.get("product_slug") or "").strip()
        if not headline or not product_name:
            continue
        rows.append(
            {
                "headline": headline,
                "product_name": product_name,
                "product_slug": product_slug,
                "source_file": os.path.relpath(json_path, BATCHES_DIR.parent.parent),
            }
        )
    return rows


def _resolve_target_product(product_name: str, product_slug: str = "") -> Product | None:
    """Strict product lookup — exact name first, then slug hints. No fuzzy matching."""
    name = product_name.strip()
    if not name:
        return None

    exact = Product.objects.filter(product_name__iexact=name, is_published=True).order_by("id")
    if exact.count() == 1:
        return exact.first()
    if exact.exists():
        # Prefer SEO slug without SIM/E-SIM suffix noise when multiple rows share a marketing name.
        for product in exact:
            slug = (product.slug or "").lower()
            if product_slug and product_slug in slug:
                return product
        return exact.order_by("slug").first()

    if product_slug:
        by_slug = Product.objects.filter(slug=product_slug, is_published=True).first()
        if by_slug:
            return by_slug
        contains = Product.objects.filter(slug__icontains=product_slug, is_published=True).order_by("slug")
        if contains.count() == 1:
            return contains.first()

    return Product.objects.filter(product_name__iexact=name).order_by("id").first()


class Command(BaseCommand):
    help = "Reparent articles to the product named in each blog JSON fixture (fixes issue 5)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview reparenting without writing.",
        )
        parser.add_argument(
            "--generate-csv",
            metavar="PATH",
            help="Write headline,product_name mapping CSV and exit (no DB writes).",
        )

    def handle(self, *args, **options):
        rows = _load_fixture_rows()
        self.stdout.write(f"Loaded {len(rows)} blog fixtures")

        if options.get("generate_csv"):
            self._write_csv(Path(options["generate_csv"]), rows)
            return

        dry_run = options["dry_run"]
        proposals: list[tuple[ProductArticle, Product, str]] = []
        missing_article = 0
        missing_product = 0
        already_ok = 0

        for row in rows:
            article = ProductArticle.objects.filter(headline=row["headline"]).select_related("product").first()
            if not article:
                missing_article += 1
                continue

            target = _resolve_target_product(row["product_name"], row["product_slug"])
            if not target:
                missing_product += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  No product for {row['product_name']!r} ({row['source_file']})"
                    )
                )
                continue

            if article.product_id == target.id:
                already_ok += 1
                continue

            conflict = ProductArticle.objects.filter(product=target, slug=article.slug).exclude(
                pk=article.pk
            ).exists()
            if conflict:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Slug collision: {article.slug} already on {target.slug} "
                        f"(article id={article.id} on {article.product.slug})"
                    )
                )
                continue

            proposals.append((article, target, row["source_file"]))

        self.stdout.write(f"Already correct: {already_ok}")
        self.stdout.write(f"Missing article in DB: {missing_article}")
        self.stdout.write(f"Missing target product: {missing_product}")
        self.stdout.write(f"To reparent: {len(proposals)}")

        for article, target, source in proposals[:50]:
            self.stdout.write(
                f"  id={article.id} {article.slug}: {article.product.slug} -> {target.slug} "
                f"({target.product_name}) [{source}]"
            )
        if len(proposals) > 50:
            self.stdout.write(f"  ... and {len(proposals) - 50} more")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run only — no database changes made."))
            return

        if not proposals:
            self.stdout.write(self.style.SUCCESS("Nothing to reparent."))
            return

        with transaction.atomic():
            for article, target, _source in proposals:
                article.product = target
            ProductArticle.objects.bulk_update([a for a, _t, _s in proposals], ["product"])

        self.stdout.write(self.style.SUCCESS(f"\nReparented {len(proposals)} article(s)."))

    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["headline", "product_name", "product_slug", "source_file"],
            )
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} rows to {path}"))
