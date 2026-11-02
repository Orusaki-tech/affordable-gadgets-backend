from django.db import migrations, models
import django.db.models.deletion


def seed_seasonal_campaign(apps, schema_editor):
    HomepageCampaign = apps.get_model("inventory", "HomepageCampaign")
    HomepageCampaign.objects.get_or_create(
        key="seasonal",
        defaults={
            "title": "Black November",
            "is_active": True,
            "animation": "none",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0080_product_is_out_of_stock"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomepageCampaign",
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
                (
                    "key",
                    models.CharField(default="seasonal", max_length=40, unique=True),
                ),
                (
                    "title",
                    models.CharField(default="Black November", max_length=80),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                (
                    "animation",
                    models.CharField(
                        choices=[("none", "None"), ("title_shimmer", "Title shimmer")],
                        default="none",
                        max_length=32,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Homepage campaign",
                "verbose_name_plural": "Homepage campaigns",
            },
        ),
        migrations.CreateModel(
            name="HomepageCampaignProduct",
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
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="inventory.homepagecampaign",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="homepage_campaign_items",
                        to="inventory.product",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="homepagecampaignproduct",
            constraint=models.UniqueConstraint(
                fields=("campaign", "product"),
                name="unique_homepage_campaign_product",
            ),
        ),
        migrations.RunPython(seed_seasonal_campaign, migrations.RunPython.noop),
    ]
