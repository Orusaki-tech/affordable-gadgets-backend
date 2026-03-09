from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0045_alter_productaccessory_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="promotion",
            name="featured_product",
            field=models.ForeignKey(
                blank=True,
                help_text="Product showcased in storefront promo cards like the homepage hero.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="featured_promotions",
                to="inventory.product",
            ),
        ),
        migrations.AddField(
            model_name="promotion",
            name="featured_sale_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Explicit sale price to show and apply for the featured product.",
                max_digits=10,
                null=True,
            ),
        ),
    ]
