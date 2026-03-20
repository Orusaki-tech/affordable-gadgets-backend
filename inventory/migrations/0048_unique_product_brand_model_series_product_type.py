from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0047_alter_promotion_carousel_position_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("brand", "model_series", "product_type"),
                name="uniq_product_brand_model_series_product_type",
            ),
        ),
    ]

