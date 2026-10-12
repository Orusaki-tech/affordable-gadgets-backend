from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0078_promotion_listing_brand"),
    ]

    operations = [
        migrations.AlterField(
            model_name="promotion",
            name="display_locations",
            field=models.JSONField(
                default=list,
                help_text=(
                    "List of display locations: 'stories_carousel', 'special_offers', "
                    "'flash_sales', 'homepage_hero', 'cbd_ribbon', 'brand_banner', 'watch_offers'"
                ),
            ),
        ),
    ]
