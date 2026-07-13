# Generated manually: ProductArticleTombstone so deleted blogs stay deleted

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0074_productarticle_products_m2m"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductArticleTombstone",
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
                ("slug", models.SlugField(max_length=255)),
                ("headline", models.CharField(blank=True, max_length=255)),
                ("deleted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="article_tombstones",
                        to="inventory.product",
                    ),
                ),
            ],
            options={
                "ordering": ["-deleted_at"],
            },
        ),
        migrations.AddIndex(
            model_name="productarticletombstone",
            index=models.Index(fields=["slug"], name="inventory_p_slug_7f1c2a_idx"),
        ),
        migrations.AddConstraint(
            model_name="productarticletombstone",
            constraint=models.UniqueConstraint(
                condition=models.Q(("product__isnull", False)),
                fields=("product", "slug"),
                name="unique_product_article_tombstone",
            ),
        ),
        migrations.AddConstraint(
            model_name="productarticletombstone",
            constraint=models.UniqueConstraint(
                condition=models.Q(("product__isnull", True)),
                fields=("slug",),
                name="unique_standalone_article_tombstone",
            ),
        ),
    ]
