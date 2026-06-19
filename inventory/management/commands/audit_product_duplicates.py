import csv
import re

from django.core.management.base import BaseCommand

from inventory.models import Product


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


class Command(BaseCommand):
    help = "Audit products to find name-based duplicates (storage/RAM in name)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="CSV output file path (default: stdout)",
        )
        parser.add_argument(
            "--product-type",
            type=str,
            default="PH",
            help="Product type to audit (default: PH for Phone)",
        )

    def handle(self, *args, **options):
        output_path = options.get("output")
        product_type = options.get("product_type")

        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("PRODUCT DUPLICATE AUDIT"))
        self.stdout.write(self.style.SUCCESS("=" * 80))

        products = Product.objects.filter(product_type=product_type).order_by(
            "brand", "model_series"
        )

        if not products.exists():
            self.stdout.write(
                self.style.WARNING(f"No products found with type '{product_type}'")
            )
            return

        self.stdout.write(
            f"\nFound {products.count()} products of type '{product_type}'"
        )
        self.stdout.write(
            "Scanning for name-based variants (storage/RAM in name)...\n"
        )

        variant_products = [
            p for p in products if is_likely_variant_name(p.product_name)
        ]

        if not variant_products:
            self.stdout.write(
                self.style.SUCCESS(
                    "No name-based variant products found. Nothing to do."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(variant_products)} products with storage/RAM in name\n"
            )
        )

        base_map = {}
        for p in variant_products:
            base = strip_variant_suffix(p.product_name)
            if base not in base_map:
                base_map[base] = []
            base_map[base].append(p)

        clusters = []

        for base_name, dupes in sorted(base_map.items()):
            main_product = find_main_product(base_name, dupes, product_type)

            for dupe in dupes:
                storage = extract_storage_from_name(dupe.product_name)
                ram = extract_ram_from_name(dupe.product_name)
                has_units = dupe.inventory_units.exists()
                has_articles = dupe.articles.exists()
                unit_count = dupe.inventory_units.count()
                article_count = dupe.articles.count()
                has_price = (
                    dupe.default_selling_price is not None
                    and dupe.default_selling_price > 0
                )

                clusters.append(
                    {
                        "dupe_id": dupe.id,
                        "dupe_name": dupe.product_name,
                        "dupe_model": dupe.model_series,
                        "dupe_brand": dupe.brand,
                        "main_id": main_product.id if main_product else None,
                        "main_name": main_product.product_name if main_product else None,
                        "storage": storage,
                        "ram": ram,
                        "has_units": has_units,
                        "unit_count": unit_count,
                        "has_articles": has_articles,
                        "article_count": article_count,
                        "has_price": has_price,
                        "price": float(dupe.default_selling_price) if has_price else 0,
                        "is_orphan": not main_product,
                    }
                )

        self._report(clusters, output_path)

    def _report(self, clusters, output_path):
        matched = [c for c in clusters if not c["is_orphan"]]
        orphans = [c for c in clusters if c["is_orphan"]]

        self.stdout.write(f"\n{'=' * 80}")
        self.stdout.write("SUMMARY")
        self.stdout.write(f"{'=' * 80}")
        self.stdout.write(f"  Total variant-name products:    {len(clusters)}")
        self.stdout.write(f"  Matched to a main product:       {len(matched)}")
        self.stdout.write(f"  Orphans (no main found):         {len(orphans)}")
        self.stdout.write(
            f"  With selling price:              {sum(1 for c in clusters if c['has_price'])}"
        )
        self.stdout.write(
            f"  Without selling price:           {sum(1 for c in clusters if not c['has_price'])}"
        )
        self.stdout.write(
            f"  With units:                      {sum(1 for c in clusters if c['has_units'])}"
        )
        self.stdout.write(
            f"  With articles:                   {sum(1 for c in clusters if c['has_articles'])}"
        )

        if matched:
            self.stdout.write(f"\n{'=' * 80}")
            self.stdout.write(self.style.SUCCESS("MATCHED CLUSTERS"))
            self.stdout.write(f"{'=' * 80}")
            for c in matched:
                label = format_variant_label(c["storage"], c["ram"])
                self.stdout.write(
                    f"  DUP #{c['dupe_id']:>4} \"{c['dupe_name']:50}\" "
                    f"→ MAIN #{c['main_id']:>4} \"{c['main_name'] or '?'}\"  "
                    f"| {label:20} "
                    f"| KES {c['price']:>8,.0f} "
                    f"| units={c['unit_count']} arts={c['article_count']}"
                )

        if orphans:
            self.stdout.write(f"\n{'=' * 80}")
            self.stdout.write(
                self.style.ERROR("ORPHANS — no matching main product found")
            )
            self.stdout.write(f"{'=' * 80}")
            for c in orphans:
                label = format_variant_label(c["storage"], c["ram"])
                self.stdout.write(
                    f"  #{c['dupe_id']:>4} \"{c['dupe_name']:50}\" "
                    f"| {label:20} "
                    f"| KES {c['price']:>8,.0f} "
                    f"| units={c['unit_count']} arts={c['article_count']}"
                )

        no_price = [c for c in matched if not c["has_price"]]
        if no_price:
            self.stdout.write(f"\n{'=' * 80}")
            self.stdout.write(
                self.style.WARNING("MATCHED BUT NO PRICE — will be skipped")
            )
            self.stdout.write(f"{'=' * 80}")
            for c in no_price:
                self.stdout.write(f"  #{c['dupe_id']:>4} \"{c['dupe_name']}\"")

        if output_path:
            with open(output_path, "w", newline="") as f:
                fieldnames = [
                    "dupe_id",
                    "dupe_name",
                    "dupe_model",
                    "dupe_brand",
                    "main_id",
                    "main_name",
                    "storage",
                    "ram",
                    "has_units",
                    "unit_count",
                    "has_articles",
                    "article_count",
                    "has_price",
                    "price",
                    "is_orphan",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(clusters)
            self.stdout.write(
                self.style.SUCCESS(f"\nCSV written to {output_path}")
            )
