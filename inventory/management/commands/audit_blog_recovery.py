"""
Audit blog recovery readiness: JSON fixtures vs current DB, optional restore DB diff.

Usage:
  python manage.py audit_blog_recovery
  RESTORE_DATABASE_URL=postgresql://... python manage.py audit_blog_recovery --compare-restore
"""

from __future__ import annotations

import glob
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from inventory.models import InventoryUnit, Product, ProductArticle

BATCHES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "blog_content",
    "batches",
)


class Command(BaseCommand):
    help = "Audit product catalog and blog coverage (JSON fixtures vs DB, optional restore clone)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--compare-restore",
            action="store_true",
            help="Diff articles and unit gaps against RESTORE_DATABASE_URL (Cloud SQL clone).",
        )
        parser.add_argument(
            "--json-only",
            action="store_true",
            help="Only report JSON fixture stats (no database queries).",
        )

    def handle(self, *args, **options):
        json_slugs, json_names, json_count = self._load_json_fixtures()
        self.stdout.write(f"JSON fixtures: {json_count} files, {len(json_slugs)} unique slugs")

        if options["json_only"]:
            return

        if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
            self.stdout.write(
                self.style.WARNING("Default DB is SQLite — set DATABASE_URL for production audit.")
            )
            self._report_json_vs_slugs(json_slugs)
            return

        products = Product.objects.count()
        articles = ProductArticle.objects.count()
        published = ProductArticle.objects.filter(is_published=True).count()
        units = InventoryUnit.objects.count()

        self.stdout.write(f"Products: {products}")
        self.stdout.write(f"ProductArticles: {articles} (published: {published})")
        self.stdout.write(f"InventoryUnits: {units}")

        slugs_in_db = set(Product.objects.values_list("slug", flat=True))
        missing_slug_products = sorted(json_slugs - slugs_in_db)
        if missing_slug_products:
            self.stdout.write(
                self.style.WARNING(
                    f"JSON slugs with no Product ({len(missing_slug_products)}): "
                    f"{', '.join(missing_slug_products[:15])}"
                    + (" ..." if len(missing_slug_products) > 15 else "")
                )
            )

        products_without_article = (
            Product.objects.filter(article__isnull=True)
            .filter(slug__in=json_slugs)
            .count()
        )
        self.stdout.write(
            f"Products matching JSON slugs but missing article: {products_without_article}"
        )

        dummy_hint = Product.objects.filter(product_name__icontains="Dummy").count()
        if dummy_hint:
            self.stdout.write(
                self.style.WARNING(f"Possible dummy catalog rows: {dummy_hint} 'Dummy' in name")
            )

        if options["compare_restore"]:
            self._compare_restore(json_slugs)

    def _load_json_fixtures(self):
        slugs = set()
        names = set()
        count = 0
        for path in glob.glob(os.path.join(BATCHES_DIR, "*", "*.json")):
            count += 1
            with open(path) as f:
                data = json.load(f)
            if data.get("product_slug"):
                slugs.add(data["product_slug"])
            if data.get("product_name"):
                names.add(data["product_name"].strip())
        return slugs, names, count

    def _report_json_vs_slugs(self, json_slugs):
        self.stdout.write(f"Unique product_slug values in JSON: {len(json_slugs)}")

    def _compare_restore(self, json_slugs):
        if "restore" not in settings.DATABASES:
            self.stderr.write(
                self.style.ERROR("RESTORE_DATABASE_URL not set — cannot compare restore DB.")
            )
            return

        restore = "restore"
        r_products = Product.objects.using(restore).count()
        r_articles = ProductArticle.objects.using(restore).count()
        r_units = InventoryUnit.objects.using(restore).count()
        self.stdout.write("")
        self.stdout.write(f"Restore DB — products: {r_products}, articles: {r_articles}, units: {r_units}")

        restore_slugs_with_article = set(
            ProductArticle.objects.using(restore)
            .select_related("product")
            .values_list("product__slug", flat=True)
        )
        current_slugs_with_article = set(
            ProductArticle.objects.values_list("product__slug", flat=True)
        )
        missing_articles = sorted(restore_slugs_with_article - current_slugs_with_article)
        self.stdout.write(
            f"Articles on restore but missing on current: {len(missing_articles)}"
        )
        if missing_articles:
            self.stdout.write("  " + ", ".join(missing_articles[:20]))
            if len(missing_articles) > 20:
                self.stdout.write(f"  ... and {len(missing_articles) - 20} more")

        restore_unit_counts = {
            row["product__slug"]: row["c"]
            for row in (
                InventoryUnit.objects.using(restore)
                .values("product__slug")
                .annotate(c=Count("id"))
            )
        }
        current_unit_counts = {
            row["product__slug"]: row["c"]
            for row in InventoryUnit.objects.values("product__slug").annotate(c=Count("id"))
        }
        unit_gaps = []
        for slug, r_count in restore_unit_counts.items():
            if r_count > 0 and current_unit_counts.get(slug, 0) == 0:
                if Product.objects.filter(slug=slug).exists():
                    unit_gaps.append((slug, r_count))
        self.stdout.write(f"Products with units on restore, zero on current: {len(unit_gaps)}")
        for slug, c in unit_gaps[:20]:
            self.stdout.write(f"  {slug}: {c} units on restore")
        if len(unit_gaps) > 20:
            self.stdout.write(f"  ... and {len(unit_gaps) - 20} more")
