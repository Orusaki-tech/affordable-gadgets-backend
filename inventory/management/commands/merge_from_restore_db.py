"""
Selectively merge ProductArticle and InventoryUnit rows from RESTORE_DATABASE_URL
(Cloud SQL clone) into the default (current production) database.

Rules:
- Articles: copy when current product (by slug) has no article but restore does.
- Units: copy only when current has zero units for that slug and restore has >=1.
  Skips sold/reserved/returned unless --all-unit-statuses.
  Skips units whose serial_number or imei already exists on current.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from inventory.models import (
    ArticleImage,
    Brand,
    Color,
    InventoryUnit,
    InventoryUnitImage,
    Product,
    ProductArticle,
    UnitAcquisitionSource,
)

RESTORE = "restore"
AV_PP = (
    InventoryUnit.SaleStatusChoices.AVAILABLE,
    InventoryUnit.SaleStatusChoices.PENDING_PAYMENT,
)


class Command(BaseCommand):
    help = "Merge blogs and missing inventory units from RESTORE_DATABASE_URL into default DB."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--articles-only", action="store_true")
        parser.add_argument("--units-only", action="store_true")
        parser.add_argument(
            "--all-unit-statuses",
            action="store_true",
            help="Include SD/RS/RT units from restore (default: only AV and PP).",
        )

    def handle(self, *args, **options):
        if RESTORE not in settings.DATABASES:
            raise CommandError("Set RESTORE_DATABASE_URL to a Cloud SQL clone connection string.")

        dry_run = options["dry_run"]
        do_articles = not options["units_only"]
        do_units = not options["articles_only"]
        status_filter = None if options["all_unit_statuses"] else AV_PP

        articles_merged = 0
        units_merged = 0
        units_skipped = 0

        if do_articles:
            articles_merged = self._merge_articles(dry_run)

        if do_units:
            units_merged, units_skipped = self._merge_units(dry_run, status_filter)

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Merged articles: {articles_merged}, "
                f"units: {units_merged}, units skipped (conflict/filter): {units_skipped}"
            )
        )

    def _merge_articles(self, dry_run: bool) -> int:
        merged = 0
        restore_articles = (
            ProductArticle.objects.using(RESTORE).select_related("product").iterator()
        )
        for r_article in restore_articles:
            slug = r_article.product.slug
            try:
                product = Product.objects.get(slug=slug)
            except Product.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  Skip article — no product for slug={slug}"))
                continue

            if ProductArticle.objects.filter(product=product, slug=getattr(r_article, "slug", None) or r_article.headline).exists():
                continue

            self.stdout.write(f"  Article → {slug}")
            if dry_run:
                merged += 1
                continue

            with transaction.atomic():
                new_article = ProductArticle.objects.create(
                    product=product,
                    slug=getattr(r_article, "slug", None) or slug,
                    is_primary=getattr(r_article, "is_primary", True),
                    category=r_article.category,
                    thumbnail_image=r_article.thumbnail_image,
                    headline=r_article.headline,
                    seo_title=r_article.seo_title,
                    seo_description=r_article.seo_description,
                    body=r_article.body,
                    is_published=r_article.is_published,
                    published_at=r_article.published_at,
                    created_at=r_article.created_at,
                    updated_at=r_article.updated_at,
                )
                for r_img in ArticleImage.objects.using(RESTORE).filter(article=r_article):
                    ArticleImage.objects.create(
                        article=new_article,
                        image=r_img.image,
                        alt_text=r_img.alt_text,
                        caption=r_img.caption,
                        position=r_img.position,
                    )
            merged += 1
        return merged

    def _merge_units(self, dry_run: bool, status_filter):
        merged = 0
        skipped = 0

        restore_counts = {
            row["product__slug"]: row["c"]
            for row in (
                InventoryUnit.objects.using(RESTORE)
                .values("product__slug")
                .annotate(c=Count("id"))
            )
        }
        current_counts = {
            row["product__slug"]: row["c"]
            for row in InventoryUnit.objects.values("product__slug").annotate(c=Count("id"))
        }

        existing_serials = set(
            InventoryUnit.objects.exclude(serial_number__isnull=True)
            .exclude(serial_number="")
            .values_list("serial_number", flat=True)
        )
        existing_imeis = set(
            InventoryUnit.objects.exclude(imei__isnull=True)
            .exclude(imei="")
            .values_list("imei", flat=True)
        )

        for slug, r_count in restore_counts.items():
            if r_count == 0 or current_counts.get(slug, 0) > 0:
                continue
            try:
                product = Product.objects.get(slug=slug)
            except Product.DoesNotExist:
                continue

            qs = InventoryUnit.objects.using(RESTORE).filter(product_template__slug=slug)
            if status_filter:
                qs = qs.filter(sale_status__in=status_filter)

            for r_unit in qs.select_related(
                "product_color", "acquisition_source_details"
            ).prefetch_related("images", "brands"):
                if r_unit.serial_number and r_unit.serial_number in existing_serials:
                    skipped += 1
                    continue
                if r_unit.imei and r_unit.imei in existing_imeis:
                    skipped += 1
                    continue

                self.stdout.write(f"  Unit → {slug} (status={r_unit.sale_status})")
                if dry_run:
                    merged += 1
                    continue

                with transaction.atomic():
                    color = self._map_color(r_unit.product_color)
                    acq = self._map_acquisition(r_unit.acquisition_source_details)
                    new_unit = InventoryUnit.objects.create(
                        product_template=product,
                        product_color=color,
                        acquisition_source_details=acq,
                        quantity=r_unit.quantity,
                        condition=r_unit.condition,
                        source=r_unit.source,
                        sale_status=r_unit.sale_status,
                        grade=r_unit.grade,
                        cost_of_unit=r_unit.cost_of_unit,
                        selling_price=r_unit.selling_price,
                        compare_at_price=r_unit.compare_at_price,
                        serial_number=r_unit.serial_number,
                        imei=r_unit.imei,
                        storage_gb=r_unit.storage_gb,
                        ram_gb=r_unit.ram_gb,
                        battery_mah=r_unit.battery_mah,
                        is_sim_enabled=r_unit.is_sim_enabled,
                        processor_details=r_unit.processor_details,
                        date_sourced=r_unit.date_sourced,
                        reserved_by=None,
                        reserved_until=None,
                        available_online=r_unit.available_online,
                    )
                    brand_codes = list(r_unit.brands.values_list("code", flat=True))
                    brand_ids = list(
                        Brand.objects.filter(code__in=brand_codes).values_list("pk", flat=True)
                    )
                    if brand_ids:
                        new_unit.brands.set(brand_ids)

                    for r_img in r_unit.images.all():
                        img_color = self._map_color(r_img.color)
                        InventoryUnitImage.objects.create(
                            inventory_unit=new_unit,
                            image=r_img.image,
                            is_primary=r_img.is_primary,
                            color=img_color,
                        )

                    if r_unit.serial_number:
                        existing_serials.add(r_unit.serial_number)
                    if r_unit.imei:
                        existing_imeis.add(r_unit.imei)
                merged += 1

        return merged, skipped

    def _map_color(self, r_color):
        if not r_color:
            return None
        color, _ = Color.objects.get_or_create(
            name=r_color.name,
            defaults={"hex_code": r_color.hex_code},
        )
        return color

    def _map_acquisition(self, r_acq):
        if not r_acq:
            return None
        acq, _ = UnitAcquisitionSource.objects.get_or_create(
            source_type=r_acq.source_type,
            name=r_acq.name,
            defaults={"phone_number": r_acq.phone_number},
        )
        return acq
