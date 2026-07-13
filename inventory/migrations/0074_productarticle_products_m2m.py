# Generated manually: ProductArticle.products M2M + backfill from primary FK

import django.db.models.deletion
from django.db import migrations, models


def backfill_article_products(apps, schema_editor):
    ProductArticle = apps.get_model("inventory", "ProductArticle")
    through = ProductArticle.products.through
    rows = []
    for article_id, product_id in (
        ProductArticle.objects.exclude(product_id=None).values_list("id", "product_id")
    ):
        rows.append(through(productarticle_id=article_id, product_id=product_id))
    if rows:
        through.objects.bulk_create(rows, ignore_conflicts=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0073_productarticle_nullable_product"),
    ]

    operations = [
        migrations.AddField(
            model_name="productarticle",
            name="products",
            field=models.ManyToManyField(
                blank=True,
                help_text="All products associated with this blog (may include the primary product).",
                related_name="linked_articles",
                to="inventory.product",
            ),
        ),
        migrations.AlterField(
            model_name="productarticle",
            name="product",
            field=models.ForeignKey(
                blank=True,
                help_text="Primary product for URL /products/{slug}/blog/... Leave empty for a general blog.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="articles",
                to="inventory.product",
            ),
        ),
        migrations.RunPython(backfill_article_products, noop_reverse),
    ]
