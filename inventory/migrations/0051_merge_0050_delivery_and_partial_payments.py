from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration to resolve two parallel 0050 migrations:
    - 0050_deliveryrate_unique_active_county_no_ward
    - 0050_partial_payments_items_delivery
    """

    dependencies = [
        ("inventory", "0050_deliveryrate_unique_active_county_no_ward"),
        ("inventory", "0050_partial_payments_items_delivery"),
    ]

    operations = []

