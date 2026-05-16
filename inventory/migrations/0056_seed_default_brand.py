from django.db import migrations


def seed_default_brand(apps, schema_editor):
    Brand = apps.get_model("inventory", "Brand")
    Brand.objects.get_or_create(
        code="AFFORDABLE_GADGETS",
        defaults={
            "name": "Affordable Gadgets KE",
            "description": "Default brand - Affordable Gadgets Kenya",
            "is_active": True,
        },
    )


def reverse_seed_default_brand(apps, schema_editor):
    Brand = apps.get_model("inventory", "Brand")
    Brand.objects.filter(code="AFFORDABLE_GADGETS").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0055_product_default_selling_price"),
    ]

    operations = [
        migrations.RunPython(seed_default_brand, reverse_seed_default_brand),
    ]
