from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration to resolve parallel leaves:
    - 0051_merge_0050_delivery_and_partial_payments
    - 0050_make_financing_payments_optional
    """

    dependencies = [
        ("inventory", "0051_merge_0050_delivery_and_partial_payments"),
        ("inventory", "0050_make_financing_payments_optional"),
    ]

    operations = []

