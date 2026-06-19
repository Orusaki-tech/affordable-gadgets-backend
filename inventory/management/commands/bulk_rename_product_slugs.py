from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Product, ProductSlugRedirect
from inventory.slug_utils import allocate_unique_slugs, build_seo_product_slug


class Command(BaseCommand):
    help = (
        "Bulk-rename product slugs to SEO-friendly canonical URLs. "
        "Creates ProductSlugRedirect rows for every changed slug."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview slug changes without writing to the database.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rename even when the computed slug matches the current slug.",
        )
        parser.add_argument(
            "--product-ids",
            nargs="*",
            type=int,
            help="Optional subset of product IDs to rename.",
        )
        parser.add_argument(
            "--published-only",
            action="store_true",
            help="Limit to published storefront products only.",
        )
        parser.add_argument(
            "--include-discontinued",
            action="store_true",
            help="Include discontinued products.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        product_ids = options.get("product_ids") or None
        published_only = options["published_only"]
        include_discontinued = options["include_discontinued"]

        queryset = Product.objects.all().order_by("id")
        if not include_discontinued:
            queryset = queryset.filter(is_discontinued=False)
        if published_only:
            queryset = queryset.filter(is_published=True)
        if product_ids:
            queryset = queryset.filter(id__in=product_ids)

        products = list(queryset.only("id", "slug", "brand", "model_series", "product_name", "product_type"))
        if not products:
            self.stdout.write(self.style.WARNING("No products matched the selection."))
            return

        proposals: list[tuple[int, str]] = []
        unchanged = 0
        for product in products:
            new_slug = build_seo_product_slug(
                brand=product.brand,
                model_series=product.model_series,
                product_name=product.product_name,
                product_type=product.product_type,
            )
            if not new_slug:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping id={product.id}: could not compute SEO slug ({product.product_name})"
                    )
                )
                continue
            if not force and (product.slug or "") == new_slug:
                unchanged += 1
                continue
            proposals.append((product.id, new_slug))

        assigned = allocate_unique_slugs(
            proposals,
            reserved=set(
                Product.objects.exclude(id__in=[product_id for product_id, _ in proposals])
                .exclude(slug="")
                .values_list("slug", flat=True)
            ),
        )
        changes = []
        for product in products:
            new_slug = assigned.get(product.id)
            if not new_slug:
                continue
            old_slug = (product.slug or "").strip()
            if old_slug == new_slug:
                continue
            changes.append((product, old_slug, new_slug))

        self.stdout.write(f"Products scanned: {len(products)}")
        self.stdout.write(f"Already optimal: {unchanged}")
        self.stdout.write(f"Planned renames: {len(changes)}")

        if not changes:
            self.stdout.write(self.style.SUCCESS("No slug changes needed."))
            return

        preview = changes[:25]
        self.stdout.write("\nSample changes:")
        for product, old_slug, new_slug in preview:
            self.stdout.write(
                f"  id={product.id:>4} | {old_slug or '(empty)'}\n"
                f"         -> {new_slug} | {product.product_name[:70]}"
            )
        if len(changes) > len(preview):
            self.stdout.write(f"  ... and {len(changes) - len(preview)} more")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run only — no database changes made."))
            return

        redirects_to_create: list[ProductSlugRedirect] = []
        products_to_update: list[Product] = []
        with transaction.atomic():
            for product, old_slug, new_slug in changes:
                if old_slug and old_slug != new_slug:
                    ProductSlugRedirect.objects.filter(old_slug=new_slug).delete()
                    redirect, _created = ProductSlugRedirect.objects.get_or_create(
                        old_slug=old_slug,
                        defaults={"product_id": product.id},
                    )
                    if redirect.product_id != product.id:
                        redirect.product_id = product.id
                        redirect.save(update_fields=["product_id"])
                product.slug = new_slug
                products_to_update.append(product)

            Product.objects.bulk_update(products_to_update, ["slug"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nRenamed {len(products_to_update)} product slugs and recorded legacy redirects."
            )
        )
