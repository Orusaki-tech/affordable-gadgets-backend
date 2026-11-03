"""Cross-reference GSC URL exports against storefront slug resolution.

Classifies each URL as indexable, legacy_redirect, or would_noindex (API miss).

Usage::

    python manage.py audit_gsc_noindex_urls --urls-csv /path/to/Table.csv
    python manage.py audit_gsc_noindex_urls --urls-csv /path/to/Table.csv --output report.csv
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from inventory.models import Product, ProductArticle, ProductSlugRedirect
from inventory.slug_utils import resolve_article_for_slug, resolve_product_for_slug

PRODUCT_RE = re.compile(r"^/products/(?P<slug>[^/]+)/?$")
ARTICLE_RE = re.compile(
    r"^/products/(?P<product_slug>[^/]+)/blog/(?P<article_slug>[^/]+)/?$"
)


def _path_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path or ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def _published_products_queryset():
    return Product.objects.filter(is_discontinued=False, is_published=True)


class Command(BaseCommand):
    help = "Audit GSC URL list for noindex risk (unresolved slugs) vs redirect coverage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--urls-csv",
            required=True,
            help="GSC drilldown CSV with URL column (and optional Last crawled).",
        )
        parser.add_argument(
            "--output",
            default="",
            help="Optional path to write classification CSV.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max URLs to process (0 = all).",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["urls_csv"])
        if not csv_path.is_file():
            raise CommandError(f"File not found: {csv_path}")

        limit = options["limit"]
        output_path = (options["output"] or "").strip()

        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "URL" not in reader.fieldnames:
                raise CommandError("CSV must have a URL column.")
            rows = list(reader)

        if limit > 0:
            rows = rows[:limit]

        counts: dict[str, int] = {}
        report_rows: list[dict[str, str]] = []

        for row in rows:
            url = (row.get("URL") or "").strip()
            if not url:
                continue
            path = _path_from_url(url)
            status, detail = self._classify(path)
            counts[status] = counts.get(status, 0) + 1
            report_rows.append(
                {
                    "url": url,
                    "path": path,
                    "status": status,
                    "detail": detail,
                    "last_crawled": row.get("Last crawled", ""),
                }
            )

        self.stdout.write(self.style.HTTP_INFO(f"\nAudited {len(report_rows)} URL(s) from {csv_path.name}:"))
        for status, count in sorted(counts.items(), key=lambda item: -item[1]):
            self.stdout.write(f"  {status}: {count}")

        would_noindex = [r for r in report_rows if r["status"] == "would_noindex"]
        if would_noindex:
            self.stdout.write(self.style.WARNING(f"\nSample would_noindex URLs (up to 20):"))
            for item in would_noindex[:20]:
                self.stdout.write(f"  {item['path']} — {item['detail']}")

        missing_redirects = [
            r
            for r in would_noindex
            if "no ProductSlugRedirect" in r["detail"] or "no redirect" in r["detail"]
        ]
        if missing_redirects:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(missing_redirects)} URL(s) likely need ProductSlugRedirect backfill."
                )
            )

        if output_path:
            out = Path(output_path)
            with out.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["url", "path", "status", "detail", "last_crawled"]
                )
                writer.writeheader()
                writer.writerows(report_rows)
            self.stdout.write(self.style.SUCCESS(f"\nWrote report to {out}"))

    def _classify(self, path: str) -> tuple[str, str]:
        if path in {"/budget-search", "/match-score"}:
            return "intentional_noindex", "frontend sets index: false"

        article_match = ARTICLE_RE.match(path)
        if article_match:
            product_slug = article_match.group("product_slug")
            article_slug = article_match.group("article_slug")
            product, legacy_product = resolve_product_for_slug(
                product_slug, queryset=_published_products_queryset()
            )
            if not product:
                has_redirect = ProductSlugRedirect.objects.filter(old_slug=product_slug).exists()
                detail = "product slug unresolved"
                if not has_redirect:
                    detail += "; no ProductSlugRedirect"
                return "would_noindex", detail

            article, legacy_article = resolve_article_for_slug(product, article_slug)
            if not article:
                return "would_noindex", f"article slug unresolved under {product.slug}"

            if legacy_product or legacy_article:
                canonical = f"/products/{product.slug}/blog/{article.slug}"
                return "legacy_redirect", f"308 → {canonical}"
            return "indexable", "published article"

        product_match = PRODUCT_RE.match(path)
        if product_match:
            slug = product_match.group("slug")
            product, legacy = resolve_product_for_slug(slug, queryset=_published_products_queryset())
            if not product:
                has_redirect = ProductSlugRedirect.objects.filter(old_slug=slug).exists()
                detail = "product slug unresolved"
                if not has_redirect:
                    detail += "; no ProductSlugRedirect"
                return "would_noindex", detail
            if legacy:
                return "legacy_redirect", f"308 → /products/{product.slug}"
            return "indexable", "published product"

        if path in {
            "/categories",
            "/articles/phones",
            "/articles/laptops",
            "/articles/tablets",
            "/articles/accessories",
        }:
            return "sitemap_redirect", "listed in sitemap but page redirects"

        return "other", "non-product URL"
