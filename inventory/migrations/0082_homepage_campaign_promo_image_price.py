from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0081_homepage_campaign"),
    ]

    operations = [
        migrations.AddField(
            model_name="homepagecampaignproduct",
            name="promo_image",
            field=models.ImageField(
                blank=True,
                help_text="Optional image shown on this campaign card instead of the catalog photo.",
                null=True,
                upload_to="campaigns/%Y/%m/",
            ),
        ),
        migrations.AddField(
            model_name="homepagecampaignproduct",
            name="promo_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Optional price shown on this campaign card instead of the catalog price.",
                max_digits=10,
                null=True,
            ),
        ),
    ]
