from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import InventoryUnit, UnitAcquisitionSource, Product


class Command(BaseCommand):
    help = (
        "Update all Sony Xperia 5 IV inventory units to selling price 22,000 "
        "and set supplier to 'Iqrar Shah_Ahmed Electronics'."
    )

    PRODUCT_NAME = "Sony Xperia 5 IV"
    TARGET_PRICE = Decimal("22000")
    SUPPLIER_NAME = "Iqrar Shah_Ahmed Electronics"

    def handle(self, *args, **options):
        with transaction.atomic():
            # Find the product template(s)
            products = Product.objects.filter(product_name__iexact=self.PRODUCT_NAME)
            if not products.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"No Product found with name '{self.PRODUCT_NAME}'. Nothing to update."
                    )
                )
                return

            # Ensure supplier acquisition source exists
            supplier_source, created = UnitAcquisitionSource.objects.get_or_create(
                name=self.SUPPLIER_NAME,
                defaults={
                    "source_type": UnitAcquisitionSource.SourceType.SUPPLIER,
                },
            )
            if not created and supplier_source.source_type != UnitAcquisitionSource.SourceType.SUPPLIER:
                supplier_source.source_type = UnitAcquisitionSource.SourceType.SUPPLIER
                supplier_source.save(update_fields=["source_type"])

            # Update all matching inventory units
            units_qs = InventoryUnit.objects.filter(product_template__in=products)
            total_units = units_qs.count()

            if total_units == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"No InventoryUnit records found for product '{self.PRODUCT_NAME}'."
                    )
                )
                return

            updated_count = units_qs.update(
                selling_price=self.TARGET_PRICE,
                acquisition_source_details=supplier_source,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated {updated_count} InventoryUnit(s) for '{self.PRODUCT_NAME}' "
                    f"to selling_price={self.TARGET_PRICE} and supplier='{self.SUPPLIER_NAME}'."
                )
            )

