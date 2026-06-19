import glob
import json
import os

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

    def _resolve_product(self, data):
        """Find product by product_name (primary) or slug (fallback).

        Uses product_name when available for SEO-friendly matching.
        Falls back to slug lookup for backward compatibility.
        """
        product_name = data.get("product_name")
        if product_name:
            name = product_name.strip()
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
                exact = [p for p in candidates if p.product_name.strip().lower() == name.lower()]
                if exact:
                    return exact[0]
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
        body_with_images = body_markdown

        # Generate image gallery from existing ProductImage records
        product_images = ProductImage.objects.filter(product=product).order_by(
            "display_order"
        )
        image_section = ""
        image_urls = []
        if product_images.exists():
            for pi in product_images:
                try:
                    url = get_optimized_image_url(pi.image, width=800, crop="limit")
                    if url:
                        image_urls.append(url)
                except Exception:
                    pass

            if image_urls:
                image_section = "\n\n<div class=\"product-gallery\">\n"
                for i, url in enumerate(image_urls):
                    alt = product_images[i].alt_text or f"{product.product_name} - Image {i + 1}"
                    image_section += f'<img src="{url}" alt="{alt}" loading="lazy" />\n'
                image_section += "</div>\n"

                # Set first image as article thumbnail
                try:
                    thumbnail_url = get_optimized_image_url(
                        product_images.first().image, width=1200, height=630
                    )
                    if thumbnail_url:
                        thumbnail_image = thumbnail_url
                except Exception:
                    pass

        # Insert gallery after the H1/headline
        body_lines = body_with_images.split("\n", 1)
        if len(body_lines) > 1:
            body_with_images = body_lines[0] + image_section + "\n" + body_lines[1]
        else:
            body_with_images = body_with_images + image_section

        # Build image markdown references for the body (if images exist)
        # The body already includes markdown image refs; we also add the gallery div above
        # For Markdown rendering, convert gallery div images to markdown too
        gallery_markdown = ""
        if image_urls:
            gallery_markdown = "\n\n"
            for i, url in enumerate(image_urls):
                alt = product_images[i].alt_text or f"{product.product_name} - Image {i + 1}"
                gallery_markdown += f"![{alt}]({url})\n\n"

        # Inject gallery markdown after first heading
        body_with_images = body_markdown
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
