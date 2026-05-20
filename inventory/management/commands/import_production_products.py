import csv
import json

from django.core.management.base import BaseCommand
from django.db import transaction, connection

from inventory.models import Product, ProductImage


class Command(BaseCommand):
    help = "Import production product data from CSV exports (Cloud SQL export)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--products-csv",
            default="_data/products.csv",
        )
        parser.add_argument(
            "--images-csv",
            default="_data/product_images.csv",
        )

    def handle(self, *args, **options):
        products_path = options["products_csv"]
        images_path = options["images_csv"]

        cursor = connection.cursor()

        with transaction.atomic():
            self.stdout.write("Clearing existing product data...")
            for table in [
                "inventory_productimage",
                "inventory_productarticle",
                "inventory_product_tags",
                "inventory_product_brands",
                "inventory_product",
            ]:
                cursor.execute(f"DELETE FROM {table}")
                self.stdout.write(f"  Cleared {table}")

            cursor.execute("ALTER SEQUENCE inventory_product_id_seq RESTART WITH 1")
            cursor.execute("ALTER SEQUENCE inventory_productimage_id_seq RESTART WITH 1")

            imported = 0
            with open(products_path) as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or len(row) < 17:
                        continue

                    product_highlights_raw = row[12]
                    try:
                        product_highlights = (
                            json.loads(product_highlights_raw)
                            if product_highlights_raw
                            else []
                        )
                    except (json.JSONDecodeError, ValueError):
                        product_highlights = []

                    product = Product(
                        id=int(row[0]),
                        product_type=row[1],
                        product_name=row[2],
                        product_description=row[3],
                        brand=row[4],
                        model_series=row[5],
                        default_selling_price=row[6] if row[6] else None,
                        is_discontinued=row[7].lower() == "t",
                        slug=row[8],
                        meta_title=row[9],
                        meta_description=row[10],
                        keywords=row[11],
                        product_highlights=product_highlights,
                        long_description=row[13],
                        is_published=row[14].lower() == "t",
                    )
                    product.save()

                    created_at = row[15] if len(row) > 15 else None
                    updated_at = row[16] if len(row) > 16 else None
                    if created_at:
                        Product.objects.filter(id=product.id).update(
                            created_at=created_at,
                            updated_at=updated_at or created_at,
                        )

                    imported += 1
                    if imported % 50 == 0:
                        self.stdout.write(f"  Imported {imported} products...")

            cursor.execute(
                "SELECT setval('inventory_product_id_seq', COALESCE((SELECT MAX(id) FROM inventory_product), 1))"
            )
            self.stdout.write(self.style.SUCCESS(f"Imported {imported} products"))

            image_count = 0
            with open(images_path) as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or len(row) < 5:
                        continue

                    product_id = int(row[1])
                    if not Product.objects.filter(id=product_id).exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Skipping image {row[0]} — product {product_id} not found"
                            )
                        )
                        continue

                    ProductImage.objects.create(
                        id=int(row[0]),
                        product_id=product_id,
                        image=row[2],
                        is_primary=row[3].lower() == "t",
                        alt_text=row[4] or "",
                        image_caption=row[5] if len(row) > 5 and row[5] else "",
                        display_order=int(row[6]) if len(row) > 6 and row[6] else 0,
                    )
                    image_count += 1

            cursor.execute(
                "SELECT setval('inventory_productimage_id_seq', COALESCE((SELECT MAX(id) FROM inventory_productimage), 1))"
            )

            self.stdout.write(self.style.SUCCESS(f"Imported {image_count} product images"))
            self.stdout.write(self.style.SUCCESS("Done! Production product data loaded locally."))
