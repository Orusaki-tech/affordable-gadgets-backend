"""Copy images and blog articles onto stock-list products from similar catalog rows.

Stock-list imports create correctly priced products but many lack photos and
articles because legacy rows used different names (Dubai variants, storage in
the title, etc.). This command:

1. Finds the best donor product (name similarity + existing images/articles)
2. Copies ``ProductImage`` rows (same Cloudinary asset, new FK)
3. Copies ``ProductArticle`` rows when the slug is not already on the target
4. Applies Apple marketing CDN fallback images for Apple rows still missing photos
5. Runs ``load_blog_batch --force`` to attach batch JSON articles

Usage::

    python manage.py sync_stock_list_media --dry-run
    python manage.py sync_stock_list_media
    python manage.py sync_stock_list_media --skip-blog-reload
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import requests
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from inventory.catalog_matching import (
    name_similarity,
    normalize_product_key,
    should_skip_article_copy,
)
from inventory.cloudinary_utils import upload_image_to_cloudinary
from inventory.models import Product, ProductArticle, ProductImage

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_PRODUCTS_CSV = DATA_DIR / "stock_list_2026_06_19_products.csv"

APPLE_CDN = "https://store.storeimages.cdn-apple.com/1/as-images.apple.com/is"
APPLE_FALLBACKS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"iphone 17 pro max|iphone 17 pro\b", re.I), "iphone-get-ready-iphone-17-pro-hero-202509", "wid=664&hei=840&fmt=png-alpha"),
    (re.compile(r"iphone 17|iphone 16|iphone 15|iphone 1[0-4]", re.I), "store-card-40-iphone-17-202509", "wid=1200&hei=1500&fmt=png-alpha"),
    (re.compile(r"ipad", re.I), "store-card-40-ipad-air-202603", "wid=1200&hei=1500&fmt=jpeg&qlt=90"),
    (re.compile(r"macbook|mac mini", re.I), "store-card-40-macbook-air-202603", "wid=1200&hei=1500&fmt=jpeg&qlt=90"),
    (re.compile(r"watch", re.I), "store-card-40-watch-s11-202509", "wid=1200&hei=1500&fmt=jpeg&qlt=90"),
    (re.compile(r"airpods max", re.I), "store-card-40-airpods-max-202409_GEO_US", "wid=1200&hei=1500&fmt=jpeg&qlt=90"),
    (re.compile(r"airpods", re.I), "airpods-pro-3-hero-select-202509", "wid=800&hei=800&fmt=png-alpha"),
    (re.compile(r"pencil|magic mouse|adapter", re.I), "store-card-13-airpods-nav-202509", "wid=400&hei=520&fmt=png-alpha"),
]


def resolve_stock_product(name: str) -> Product | None:
    product = Product.objects.filter(product_name=name).first()
    if product:
        return product
    product = Product.objects.filter(product_name__iexact=f"Samsung {name}").first()
    if product:
        return product
    return Product.objects.filter(model_series=name).first()


def _donor_score(
    target: Product,
    candidate: Product,
    *,
    stock_names: set[str],
) -> float:
    score = name_similarity(target.product_name, candidate.product_name)
    if candidate.brand == "Samsung" and not candidate.product_name.startswith("Samsung"):
        score = max(
            score,
            name_similarity(f"Samsung {target.product_name}", candidate.product_name),
        )
    if target.brand == "Samsung" and candidate.brand == "Samsung":
        score = max(
            score,
            name_similarity(
                target.product_name.removeprefix("Samsung ").strip(),
                candidate.product_name.removeprefix("Samsung ").strip(),
            ),
        )

    image_count = getattr(candidate, "image_count", 0) or 0
    article_count = getattr(candidate, "article_count", 0) or 0
    score += min(0.12, (image_count + article_count) * 0.015)

    if len(candidate.product_name) < len(target.product_name):
        score += 0.04

    if normalize_product_key(candidate.product_name) in stock_names:
        score -= 0.08

    return score


def find_donor(
    target: Product,
    *,
    min_score: float = 0.35,
    stock_names: set[str] | None = None,
) -> Product | None:
    stock_names = stock_names or set()
    donors = (
        Product.objects.exclude(pk=target.pk)
        .annotate(
            image_count=Count("images", distinct=True),
            article_count=Count("articles", distinct=True),
        )
        .filter(Q(image_count__gt=0) | Q(article_count__gt=0))
    )

    best: Product | None = None
    best_score = min_score
    for candidate in donors:
        if target.brand and candidate.brand and target.brand.lower() != candidate.brand.lower():
            continue
        score = _donor_score(target, candidate, stock_names=stock_names)
        if score > best_score:
            best_score = score
            best = candidate
    return best


def copy_images(source: Product, target: Product, *, dry_run: bool) -> int:
    if target.images.exists():
        return 0
    source_images = list(source.images.order_by("display_order", "id"))
    if not source_images:
        return 0
    if dry_run:
        return len(source_images)

    created = 0
    has_primary = False
    for img in source_images:
        is_primary = img.is_primary and not has_primary
        ProductImage.objects.create(
            product=target,
            image=img.image.name,
            is_primary=is_primary,
            alt_text=img.alt_text or target.product_name,
            image_caption=img.image_caption,
            display_order=img.display_order,
        )
        if is_primary:
            has_primary = True
        created += 1
    if not has_primary and created:
        first = target.images.order_by("display_order", "id").first()
        if first:
            ProductImage.objects.filter(product=target).update(is_primary=False)
            ProductImage.objects.filter(pk=first.pk).update(is_primary=True)
    return created


def copy_articles(source: Product, target: Product, *, dry_run: bool) -> int:
    if target.articles.filter(is_published=True).exists():
        return 0
    if should_skip_article_copy(source.product_name, target.product_name):
        return 0
    source_articles = list(source.articles.order_by("-is_primary", "-published_at", "id"))
    if not source_articles:
        return 0
    if dry_run:
        return len(source_articles)

    copied = 0
    has_primary = target.articles.filter(is_primary=True).exists()
    for article in source_articles:
        if ProductArticle.objects.filter(product=target, slug=article.slug).exists():
            continue
        ProductArticle.objects.create(
            product=target,
            slug=article.slug,
            is_primary=article.is_primary and not has_primary,
            category=article.category,
            thumbnail_image=article.thumbnail_image,
            headline=article.headline,
            seo_title=article.seo_title,
            seo_description=article.seo_description,
            body=article.body,
            is_published=article.is_published,
            published_at=article.published_at,
        )
        if article.is_primary:
            has_primary = True
        copied += 1
    return copied


def apple_fallback_image(product: Product, *, dry_run: bool) -> bool:
    if product.images.exists() or product.brand.lower() != "apple":
        return False
    label = product.product_name
    for pattern, path, query in APPLE_FALLBACKS:
        if not pattern.search(label):
            continue
        url = f"{APPLE_CDN}/{path}?{query}"
        if dry_run:
            return True
        try:
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            content = io.BytesIO(response.content)
            content.name = "product.jpg"
            saved_name, _ = upload_image_to_cloudinary(content, "product_photos")
            if not saved_name:
                return False
            ProductImage.objects.create(
                product=product,
                image=saved_name,
                is_primary=True,
                alt_text=product.product_name,
                display_order=0,
            )
            return True
        except Exception:
            return False
    return False


def sync_stock_list_media(
    *,
    products_csv: Path | None = None,
    dry_run: bool = False,
    skip_blog_reload: bool = False,
    min_score: float = 0.35,
    stdout=None,
    style=None,
) -> dict[str, int]:
    """Copy images/articles from similar catalog rows onto stock-list products."""
    csv_path = products_csv or DEFAULT_PRODUCTS_CSV
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        stock_rows = list(csv.DictReader(fh))

    stock_names = {normalize_product_key(row["product_name"]) for row in stock_rows}

    stats = {
        "products": len(stock_rows),
        "images_copied": 0,
        "articles_copied": 0,
        "apple_fallbacks": 0,
        "donors_used": 0,
        "already_complete": 0,
        "missing_product": 0,
    }

    write = stdout.write if stdout is not None else print

    for row in stock_rows:
        name = row["product_name"]
        target = resolve_stock_product(name)
        if target is None:
            stats["missing_product"] += 1
            if stdout and style:
                write(style.WARNING(f"  SKIP missing product: {name}"))
            continue

        has_image = target.images.exists()
        has_blog = target.articles.filter(is_published=True).exists()
        if has_image and has_blog:
            stats["already_complete"] += 1
            continue

        donor = find_donor(target, min_score=min_score, stock_names=stock_names)
        if donor is not None:
            stats["donors_used"] += 1
            with transaction.atomic():
                stats["images_copied"] += copy_images(donor, target, dry_run=dry_run)
                stats["articles_copied"] += copy_articles(donor, target, dry_run=dry_run)
            write(f"  donor {donor.product_name!r} -> {target.product_name!r}")

        if not dry_run:
            target.refresh_from_db()
        if not target.images.exists():
            if apple_fallback_image(target, dry_run=dry_run):
                stats["apple_fallbacks"] += 1
                write(f"  apple CDN image -> {target.product_name!r}")

    if skip_blog_reload or dry_run:
        return stats

    call_command("load_blog_batch", force=True)

    from django.core.cache import cache

    cache.clear()
    if stdout and style:
        write(style.SUCCESS("Cache cleared."))
    return stats


class Command(BaseCommand):
    help = "Copy images and blog articles onto stock-list products from similar catalog rows."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--products-csv",
            type=str,
            default=str(DEFAULT_PRODUCTS_CSV),
            help=f"Stock-list products CSV (default: {DEFAULT_PRODUCTS_CSV})",
        )
        parser.add_argument(
            "--skip-blog-reload",
            action="store_true",
            help="Skip load_blog_batch --force at the end",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=0.35,
            help="Minimum name similarity for donor matching (default: 0.35)",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        skip_blog = bool(options["skip_blog_reload"])
        min_score = float(options["min_score"])
        products_csv = Path(options["products_csv"]).expanduser()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes."))

        stats = sync_stock_list_media(
            products_csv=products_csv,
            dry_run=dry_run,
            skip_blog_reload=skip_blog,
            min_score=min_score,
            stdout=self.stdout,
            style=self.style,
        )

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=== Sync summary ==="))
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value}")

        if skip_blog:
            return

        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=== Reloading blog batches ==="))
        if dry_run:
            self.stdout.write("  (skipped in dry-run)")
