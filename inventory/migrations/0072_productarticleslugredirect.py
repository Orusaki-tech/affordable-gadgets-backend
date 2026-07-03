from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0071_productslugredirect"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductArticleSlugRedirect",
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
                ("old_slug", models.SlugField(db_index=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slug_redirects",
                        to="inventory.productarticle",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="article_slug_redirects",
                        to="inventory.product",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="productarticleslugredirect",
            index=models.Index(fields=["article", "created_at"], name="inventory_p_article_0c8f2d_idx"),
        ),
        migrations.AddConstraint(
            model_name="productarticleslugredirect",
            constraint=models.UniqueConstraint(
                fields=("product", "old_slug"),
                name="unique_product_article_slug_redirect",
            ),
        ),
    ]
