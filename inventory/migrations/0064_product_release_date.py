from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0063_observability_event_and_utm_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="release_date",
            field=models.DateField(
                blank=True,
                db_index=True,
                help_text="Device launch/release date used for storefront sorting (newest first).",
                null=True,
            ),
        ),
    ]
