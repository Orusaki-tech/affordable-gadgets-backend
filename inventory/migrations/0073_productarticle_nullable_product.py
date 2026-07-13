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
        migrations.RemoveConstraint(
            model_name="productarticle",
            name="unique_product_article_slug",
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
