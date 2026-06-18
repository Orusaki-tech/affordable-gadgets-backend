from django.db import migrations

from inventory.release_date_inference import infer_release_date


def backfill_release_dates(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    for product in Product.objects.all().iterator():
        if product.release_date:
            continue
        inferred = infer_release_date(product.product_name)
        if inferred is None:
            continue
        product.release_date = inferred
        product.save(update_fields=["release_date"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0064_product_release_date"),
    ]

    operations = [
        migrations.RunPython(backfill_release_dates, migrations.RunPython.noop),
    ]
