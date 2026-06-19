# Generated manually for ProductReleaseDate table + JSON seed

from django.db import migrations, models
import django.core.validators


def seed_product_release_dates(apps, schema_editor):
    ProductReleaseDate = apps.get_model("inventory", "ProductReleaseDate")
    from inventory.release_date_table import iter_release_date_rows

    for row in iter_release_date_rows():
        ProductReleaseDate.objects.update_or_create(
            family_key=row["family_key"],
            defaults={
                "product_label": row["product_label"],
                "release_month": row["release_month"],
                "release_year": row["release_year"],
                "source_url": row["source_url"],
                "notes": row["notes"],
            },
        )


def unseed_product_release_dates(apps, schema_editor):
    ProductReleaseDate = apps.get_model("inventory", "ProductReleaseDate")
    ProductReleaseDate.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0069_product_storage_ram_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductReleaseDate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "family_key",
                    models.CharField(
                        db_index=True,
                        help_text="Slug matched from product name inference (e.g. iphone-17-pro-max).",
                        max_length=120,
                        unique=True,
                    ),
                ),
                ("product_label", models.CharField(blank=True, max_length=255)),
                (
                    "release_month",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(12),
                        ]
                    ),
                ),
                ("release_year", models.PositiveSmallIntegerField()),
                (
                    "source_url",
                    models.URLField(
                        blank=True,
                        help_text="Manufacturer or newsroom URL confirming the release date.",
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Product release date",
                "verbose_name_plural": "Product release dates",
                "ordering": ["-release_year", "-release_month", "family_key"],
            },
        ),
        migrations.RunPython(seed_product_release_dates, unseed_product_release_dates),
    ]
