from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0079_promotion_watch_offers_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_out_of_stock",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Show an Out of stock label on the storefront and block online purchase.",
            ),
        ),
    ]
