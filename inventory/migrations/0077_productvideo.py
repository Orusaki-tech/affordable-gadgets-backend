# Generated manually for ProductVideo multi-link support

from django.db import migrations, models
import django.db.models.deletion


def backfill_product_videos(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    ProductVideo = apps.get_model("inventory", "ProductVideo")
    to_create = []
    for product in Product.objects.exclude(product_video_url__isnull=True).exclude(product_video_url=""):
        url = (product.product_video_url or "").strip()
        if not url:
            continue
        if ProductVideo.objects.filter(product_id=product.id).exists():
            continue
        to_create.append(
            ProductVideo(
                product_id=product.id,
                url=url,
                title="",
                display_order=0,
            )
        )
    if to_create:
        ProductVideo.objects.bulk_create(to_create)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0076_add_tags_to_productarticle"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductVideo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "url",
                    models.URLField(
                        help_text="Link to product video (YouTube, Shorts, youtu.be, Vimeo, etc.)",
                        max_length=500,
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        help_text="Optional label shown with the video",
                        max_length=255,
                    ),
                ),
                (
                    "display_order",
                    models.IntegerField(
                        default=0,
                        help_text="Order in which videos should be displayed (lower numbers first)",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="videos",
                        to="inventory.product",
                    ),
                ),
            ],
            options={
                "ordering": ["display_order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="productvideo",
            index=models.Index(fields=["product", "display_order"], name="inventory_p_product_08cf5e_idx"),
        ),
        migrations.RunPython(backfill_product_videos, noop_reverse),
    ]
