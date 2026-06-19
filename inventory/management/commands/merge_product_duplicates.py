import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import (
    Bundle,
    BundleItem,
    FinancingOffer,
    InventoryUnit,
    ObservabilityEvent,
    Product,
    ProductAccessory,
    ProductArticle,
    ProductImage,
    ProductVariant,
    Review,
    WhatsAppClickEvent,
    WishlistItem,
)


def extract_storage_from_name(name):
    match = re.search(r"(\d+)\s*T\s*(?:B|b)(?!\s*(?:RAM|Ram|ram))", name)
    if match:
        return int(match.group(1)) * 1024
    match = re.search(r"(\d+)\s*G\s*(?:B|b)(?!\s*(?:RAM|Ram|ram))", name)
    if match:
        return int(match.group(1))
    return None


def extract_ram_from_name(name):
    match = re.search(r"(\d+)\s*G\s*(?:B|b)?\s*(?:RAM|Ram|ram)", name)
    if match:
        return int(match.group(1))
    return None


def strip_variant_suffix(name):
    result = re.sub(r"\s+\d+\s*[GT]\s*B.*$", "", name, flags=re.IGNORECASE)
    result = result.strip()
    return result if result else name


def is_likely_variant_name(name):
    return bool(re.search(r"\d+\s*[GT]\s*B", name, re.IGNORECASE))


def find_main_product(base_name, dupes, product_type):
    dupe_ids = [d.id for d in dupes]
    main = Product.objects.filter(
        product_type=product_type,
        product_name__iexact=base_name,
    ).exclude(id__in=dupe_ids).first()
    if main:
        return main
    best = None
    best_len = 0
    for p in Product.objects.filter(product_type=product_type).exclude(id__in=dupe_ids):
        name = p.product_name.strip()
        if base_name.lower().endswith(name.lower()) and len(name) > best_len:
            best = p
            best_len = len(name)
    return best


def format_variant_label(storage, ram):
    parts = []
    if storage:
        label = f"{storage}GB"
        if storage >= 1024 and storage % 1024 == 0:
            label = f"{storage // 1024}TB"
        parts.append(label)
    if ram:
        parts.append(f"{ram}GB RAM")
    return " / ".join(parts) if parts else "?"


class Command(BaseCommand):
    help = "Merge name-based duplicate products into their main product as variants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--product-type",
            type=str,
            default="PH",
            help="Product type to process (default: PH for Phone)",
        )
        parser.add_argument(
            "--dupe-id",
            type=int,
            nargs="*",
            help="Specific duplicate product IDs to process (default: all)",
        )

    def handle(self, *args, **options):
        is_dry_run = options.get("dry_run")
        product_type = options.get("product_type")
        specific_ids = options.get("dupe_id")

        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(
            self.style.SUCCESS(
                f"PRODUCT DUPLICATE MERGE {'[DRY RUN]' if is_dry_run else '[LIVE]'}"
            )
        )
        self.stdout.write(self.style.SUCCESS("=" * 80))

        if is_dry_run:
            self.stdout.write(
                self.style.WARNING("  DRY RUN — no changes will be made\n")
            )

        products = Product.objects.filter(product_type=product_type).order_by(
            "brand", "model_series"
        )

        if specific_ids:
            products = products.filter(id__in=specific_ids)

        variant_products = [
            p for p in products if is_likely_variant_name(p.product_name)
        ]
        self.stdout.write(
            f"Found {len(variant_products)} variant-name products to evaluate\n"
        )

        stats = {
            "processed": 0,
            "skipped_no_price": 0,
            "skipped_orphan": 0,
            "skipped_no_storage": 0,
            "variants_created": 0,
            "articles_reparented": 0,
            "images_reparented": 0,
            "reviews_reparented": 0,
            "others_reparented": 0,
            "deleted": 0,
        }

        base_map = {}
        for p in variant_products:
            base = strip_variant_suffix(p.product_name)
            if base not in base_map:
                base_map[base] = []
            base_map[base].append(p)

        for base_name, dupes in sorted(base_map.items()):
            main_product = find_main_product(base_name, dupes, product_type)

            for dupe in dupes:
                self._process_duplicate(
                    dupe, main_product, product_type, is_dry_run, stats
                )

        self.stdout.write(f"\n{'=' * 80}")
        self.stdout.write("RESULTS")
        self.stdout.write(f"{'=' * 80}")
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value}")

        if is_dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n  This was a DRY RUN. Re-run without --dry-run to apply."
                )
            )

    def _process_duplicate(self, dupe, main_product, product_type, is_dry_run, stats):
        has_price = (
            dupe.default_selling_price is not None
            and dupe.default_selling_price > 0
        )
        storage = extract_storage_from_name(dupe.product_name)
        ram = extract_ram_from_name(dupe.product_name)

        if not main_product:
            stats["skipped_orphan"] += 1
            self.stdout.write(
                self.style.WARNING(
                    f"  SKIP #{dupe.id:>4} \"{dupe.product_name:50}\" — orphan (no main product found)"
                )
            )
            return

        if not has_price:
            stats["skipped_no_price"] += 1
            self.stdout.write(
                self.style.WARNING(
                    f"  SKIP #{dupe.id:>4} \"{dupe.product_name:50}\" — no default_selling_price"
                )
            )
            return

        if not storage:
            stats["skipped_no_storage"] += 1
            self.stdout.write(
                self.style.WARNING(
                    f"  SKIP #{dupe.id:>4} \"{dupe.product_name:50}\" — couldn't parse storage from name"
                )
            )
            return

        if dupe.id == main_product.id:
            stats["skipped_no_price"] += 1
            self.stdout.write(
                self.style.WARNING(
                    f"  SKIP #{dupe.id:>4} \"{dupe.product_name:50}\" — is the main product itself"
                )
            )
            return

        ram_label = f"{ram}GB RAM" if ram else "No RAM"
        storage_label = format_variant_label(storage, ram)
        self.stdout.write(
            f"  #{dupe.id:>4} \"{dupe.product_name:50}\" "
            f"→ #{main_product.id:>4} \"{main_product.product_name}\"  "
            f"| {storage_label} | price={dupe.default_selling_price:>8,.0f}"
        )

        with transaction.atomic():
            self._reparent_content(dupe, main_product, is_dry_run, stats)
            self._create_variant(dupe, main_product, storage, ram, is_dry_run, stats)
            self._delete_product(dupe, is_dry_run, stats)

        stats["processed"] += 1

    def _reparent_content(self, dupe, main_product, is_dry_run, stats):
        reparent_mappings = [
            (ProductArticle, "product", "articles_reparented"),
            (ProductImage, "product", "images_reparented"),
            (Review, "product", "reviews_reparented"),
            (FinancingOffer, "product", "others_reparented"),
            (WhatsAppClickEvent, "product", "others_reparented"),
            (WishlistItem, "product", "others_reparented"),
            (Bundle, "main_product", "others_reparented"),
            (BundleItem, "product", "others_reparented"),
            (ObservabilityEvent, "product", "others_reparented"),
        ]

        for model_cls, fk_name, stat_key in reparent_mappings:
            qs = model_cls.objects.filter(**{fk_name: dupe})
            count = qs.count()
            if count > 0:
                if not is_dry_run:
                    qs.update(**{fk_name: main_product})
                stats[stat_key] += count
                self.stdout.write(
                    f"    → reparented {count} {model_cls.__name__}(s) to main product"
                )

        accessory_as_main = ProductAccessory.objects.filter(main_product=dupe)
        count_am = accessory_as_main.count()
        if count_am > 0:
            if not is_dry_run:
                accessory_as_main.update(main_product=main_product)
            stats["others_reparented"] += count_am
            self.stdout.write(
                f"    → reparented {count_am} ProductAccessory(main_product) to main product"
            )

        accessory_as_acc = ProductAccessory.objects.filter(accessory=dupe)
        count_aa = accessory_as_acc.count()
        if count_aa > 0:
            if not is_dry_run:
                accessory_as_acc.update(accessory=main_product)
            stats["others_reparented"] += count_aa
            self.stdout.write(
                f"    → reparented {count_aa} ProductAccessory(accessory) to main product"
            )

    def _create_variant(self, dupe, main_product, storage, ram, is_dry_run, stats):
        exists = ProductVariant.objects.filter(
            product=main_product, storage_gb=storage, ram_gb=ram
        ).exists()

        if exists:
            ram_label = f"{ram}GB RAM" if ram else "No RAM"
            self.stdout.write(
                self.style.WARNING(
                    f"    → variant ({storage}GB / {ram_label}) already exists on main product — skipping"
                )
            )
            return

        if not is_dry_run:
            ProductVariant.objects.create(
                product=main_product,
                storage_gb=storage,
                ram_gb=ram,
                default_selling_price=dupe.default_selling_price,
                default_cost_of_unit=Decimal("0.00"),
                is_active=True,
            )

        stats["variants_created"] += 1
        ram_label = f"{ram}GB RAM" if ram else "No RAM"
        self.stdout.write(
            f"    → created variant: {storage}GB / {ram_label} @ {dupe.default_selling_price:>,.0f}"
        )

    def _delete_product(self, dupe, is_dry_run, stats):
        dupe_id = dupe.id
        if not is_dry_run:
            dupe.delete()
        stats["deleted"] += 1
        self.stdout.write(f"    → deleted duplicate product #{dupe_id}")
