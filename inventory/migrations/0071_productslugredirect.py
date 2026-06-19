from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0070_productreleasedate"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductSlugRedirect",
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
                ("old_slug", models.SlugField(db_index=True, max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slug_redirects",
                        to="inventory.product",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["product", "created_at"],
                        name="inventory_p_product_4d2f0a_idx",
                    )
                ],
            },
        ),
    ]
