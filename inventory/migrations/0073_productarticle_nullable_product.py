# Generated manually for nullable ProductArticle.product + standalone slug uniqueness

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0072_productarticleslugredirect"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productarticle",
            name="product",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional product association. Leave empty for a general blog post.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="articles",
                to="inventory.product",
            ),
        ),
        migrations.AlterField(
            model_name="productarticle",
            name="slug",
            field=models.SlugField(
                help_text="URL segment: /products/{product-slug}/blog/{slug}/ or /blog/{slug}/",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="productarticle",
            name="is_primary",
            field=models.BooleanField(
                default=False,
                help_text="Default article for legacy /products/{slug}/blog URLs (product-linked only)",
            ),
        ),
        # 0066 created this uniqueness as a UNIQUE INDEX via raw SQL on some DBs,
        # while Django state expects a constraint. Drop both forms safely.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="productarticle",
                    name="unique_product_article_slug",
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        "ALTER TABLE inventory_productarticle DROP CONSTRAINT IF EXISTS unique_product_article_slug;",
                        "DROP INDEX IF EXISTS unique_product_article_slug;",
                    ],
                    reverse_sql=[
                        "CREATE UNIQUE INDEX IF NOT EXISTS unique_product_article_slug "
                        "ON inventory_productarticle (product_id, slug);",
                    ],
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="productarticle",
            constraint=models.UniqueConstraint(
                condition=models.Q(("product__isnull", False)),
                fields=("product", "slug"),
                name="unique_product_article_slug",
            ),
        ),
        migrations.AddConstraint(
            model_name="productarticle",
            constraint=models.UniqueConstraint(
                condition=models.Q(("product__isnull", True)),
                fields=("slug",),
                name="unique_standalone_article_slug",
            ),
        ),
    ]
