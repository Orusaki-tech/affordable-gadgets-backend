import glob
import json
import os
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as django_timezone
from django.utils.text import slugify

from inventory.cloudinary_utils import get_optimized_image_url
from inventory.models import Product, ProductArticle, ProductImage


BATCHES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "blog_content",
    "batches",
)
STOCK_LIST_CSV = (
    Path(__file__).resolve().parents[2] / "data" / "stock_list_2026_06_19_products.csv"
)


def _blog_name_tokens(name: str) -> set[str]:
    text = name.lower().replace('"', " inch ").replace("'", "")
    text = re.sub(r"[^\w\s]", " ", text)
    stop = {"gb", "tb", "ram", "wifi", "cellular", "sim", "inch", "gen", "dubai", "official"}
    return {t for t in text.split() if t and t not in stop and not t.isdigit()}


def _blog_name_similarity(left: str, right: str) -> float:
    a, b = _blog_name_tokens(left), _blog_name_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Command(BaseCommand):
    help = "Load blog article JSON fixtures from blog_content/batches/ into ProductArticle records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            type=str,
            help="Load only a specific batch directory (e.g., '001'). If omitted, loads all unloaded batches.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-process already-loaded articles (replaces existing).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be loaded without writing to DB.",
        )

    def handle(self, *args, **options):
        batch_filter = options.get("batch")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)

        if not os.path.isdir(BATCHES_DIR):
            raise CommandError(f"Batches directory not found: {BATCHES_DIR}")

        # Discover batch directories
        if batch_filter:
            batch_dirs = [os.path.join(BATCHES_DIR, batch_filter)]
        else:
            batch_dirs = sorted(
                d
                for d in glob.glob(os.path.join(BATCHES_DIR, "*"))
                if os.path.isdir(d)
            )

        if not batch_dirs:
            self.stdout.write(self.style.WARNING("No batch directories found."))
            return

        total_created = 0
        total_skipped = 0
        total_errors = 0

        for batch_dir in batch_dirs:
            batch_name = os.path.basename(batch_dir)
            self.stdout.write(f"\nProcessing batch: {batch_name}")
            self.stdout.write(f"  ({batch_dir})")

            json_files = sorted(glob.glob(os.path.join(batch_dir, "*.json")))
            if not json_files:
                self.stdout.write(self.style.WARNING(f"  No JSON files in {batch_name}"))
                continue

            for json_path in json_files:
                basename = os.path.basename(json_path)
                result = self._load_single_article(
                    json_path, dry_run=dry_run, force=force
                )
                if result == "created":
                    total_created += 1
                    self.stdout.write(f"  ✓ {basename} — created")
                elif result == "skipped":
                    total_skipped += 1
                    self.stdout.write(f"  → {basename} — skipped (already exists)")
                elif result == "updated":
                    total_created += 1
                    self.stdout.write(f"  ↻ {basename} — updated")
                else:
                    total_errors += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ {basename} — {result}"))

        summary = (
            f"\nDone. Created/updated: {total_created}, "
            f"Skipped: {total_skipped}, Errors: {total_errors}"
        )
        if dry_run:
            summary = f"[DRY RUN] Would create/update: {total_created} (skipped {total_skipped})"
        self.stdout.write(self.style.SUCCESS(summary))

    def _stock_list_product_names(self) -> list[tuple[str, Product]]:
        """Published stock-list products for blog JSON matching."""
        if not STOCK_LIST_CSV.is_file():
            return []
        import csv

        names: list[str] = []
        with STOCK_LIST_CSV.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                names.append(row["product_name"])

        matches: list[tuple[str, Product]] = []
        for name in names:
            product = Product.objects.filter(product_name=name, is_published=True).first()
            if product is None:
                product = Product.objects.filter(
                    product_name__iexact=f"Samsung {name}", is_published=True
                ).first()
            if product is not None:
                matches.append((name, product))
        return matches

    def _resolve_product(self, data):
        """Find product by product_name (primary) or slug (fallback).

        Uses product_name when available for SEO-friendly matching.
        Falls back to slug lookup for backward compatibility.
        """
        product_name = data.get("product_name")
        if product_name:
            name = product_name.strip()

            # Exact published name always wins (e.g. iPhone 17e vs iPhone 17E SIM).
            exact = Product.objects.filter(product_name__iexact=name, is_published=True).first()
            if exact is None:
                exact = Product.objects.filter(product_name__iexact=name).first()
            if exact is not None:
                return exact

            product_slug = data.get("product_slug")
            if product_slug:
                by_slug = Product.objects.filter(slug=product_slug, is_published=True).first()
                if by_slug is not None:
                    return by_slug

            # Prefer stock-list catalog names (short template names over Dubai SKUs).
            stock_names = self._stock_list_product_names()
            stock_matches = [
                p
                for stock_name, p in stock_names
                if _blog_name_similarity(name, stock_name) >= 0.35
                or name.lower() in stock_name.lower()
                or stock_name.lower() in name.lower()
            ]
            # e-series blogs (iPhone 17e) must not attach to *E SIM* stock SKUs.
            if re.match(r"^iPhone \d+e$", name, re.I):
                stock_matches = [
                    p for p in stock_matches if " sim" not in p.product_name.lower()
                ]
            # iPhone Air blog must not attach to colour/warranty stock SKUs.
            if name.lower() == "iphone air":
                stock_matches = [
                    p
                    for p in stock_matches
                    if "air e-sim" not in p.product_name.lower()
                ]
            if stock_matches:
                stock_matches.sort(
                    key=lambda p: (
                        0 if p.product_name.lower() == name.lower() else 1,
                        len(p.product_name),
                    )
                )
                return stock_matches[0]

            # Try forward match (DB contains JSON name)
            candidates = list(
                Product.objects.filter(
                    product_name__icontains=name
                ).order_by("product_name")[:10]
            )
            if not candidates:
                # Try reverse match (JSON name contains DB product_name)
                for p in Product.objects.filter(is_published=True).only("product_name"):
                    if name.lower() in p.product_name.lower() or p.product_name.lower() in name.lower():
                        candidates.append(p)
                        if len(candidates) >= 5:
                            break
            if candidates:
                # Prefer exact match, then shortest name (base model, not variant)
                exact_candidates = [
                    p for p in candidates if p.product_name.strip().lower() == name.lower()
                ]
                if exact_candidates:
                    return exact_candidates[0]
                if re.match(r"^iPhone \d+e$", name, re.I):
                    candidates = [
                        p for p in candidates if " sim" not in p.product_name.lower()
                    ]
                if name.lower() == "iphone air":
                    candidates = [
                        p
                        for p in candidates
                        if "air e-sim" not in p.product_name.lower()
                    ]
                if candidates:
                    candidates.sort(key=lambda p: len(p.product_name))
                    return candidates[0]

        # Fallback to slug
        product_slug = data.get("product_slug")
        if product_slug:
            try:
                return Product.objects.get(slug=product_slug)
            except Product.DoesNotExist:
                pass

        return None

    def _load_single_article(self, json_path, dry_run=False, force=False):
        with open(json_path) as f:
            data = json.load(f)

        product = self._resolve_product(data)
        if not product:
            slug = data.get("product_slug", "?")
            return f"Product not found (slug={slug}, name={data.get('product_name', 'N/A')})"

        # Check if article already exists (same product + slug)
        article_slug = data.get("slug") or slugify(data.get("headline", "")) or f"article-{product.slug}"
        article_exists = ProductArticle.objects.filter(product=product, slug=article_slug).exists()
        if article_exists and not force:
            return "skipped"

        if dry_run:
            return "created"

        body_markdown = data.get("body_markdown", "")
        headline = data.get("headline", "")
        seo_title = data.get("seo_title", "")[:60]
        seo_description = data.get("seo_description", "")[:160]
        category = data.get("category", "buying_guide")
        is_published = data.get("is_published", True)

        # Check for product images to include as thumbnail
        thumbnail_image = None

        # Use the first product image as thumbnail and a single aside image in the body
        product_images = ProductImage.objects.filter(product=product).order_by(
            "display_order"
        )
        primary_image_url = None
        primary_image_alt = product.product_name
        if product_images.exists():
            first_image = product_images.first()
            try:
                primary_image_url = get_optimized_image_url(
                    first_image.image, width=800, crop="limit"
                )
                primary_image_alt = first_image.alt_text or product.product_name
            except Exception:
                primary_image_url = None

            if primary_image_url:
                try:
                    thumbnail_url = get_optimized_image_url(
                        first_image.image, width=1200, height=630
                    )
                    if thumbnail_url:
                        thumbnail_image = thumbnail_url
                except Exception:
                    pass

        gallery_markdown = ""
        if primary_image_url:
            gallery_markdown = f"\n\n![{primary_image_alt}]({primary_image_url})\n\n"

        # Inject the single image after the first heading
        lines = body_markdown.split("\n", 1)
        if len(lines) > 1:
            body_with_images = lines[0] + gallery_markdown + lines[1]
        else:
            body_with_images = lines[0] + gallery_markdown

        # Create or update the article
        defaults = {
            "headline": headline,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "body": body_with_images,
            "category": category,
            "is_published": is_published,
            "is_primary": data.get("is_primary", not ProductArticle.objects.filter(product=product).exists()),
        }
        if is_published:
            defaults["published_at"] = django_timezone.now()

        article, created = ProductArticle.objects.update_or_create(
            product=product,
            slug=article_slug,
            defaults=defaults,
        )

        # Save thumbnail note (ImageField not set here since we reference URLs directly in body)
        return "created" if created else "updated"
