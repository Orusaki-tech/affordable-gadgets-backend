import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0052_merge_0051_and_make_financing_payments_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="financingoffer",
            name="term_count",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="financingoffer",
            name="term_unit",
            field=models.CharField(
                blank=True,
                choices=[("day", "Day"), ("week", "Week"), ("month", "Month")],
                db_index=True,
                max_length=10,
                null=True,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="financingoffer",
            name="uniq_financing_offer_provider_product_ram_rom",
        ),
        migrations.AddConstraint(
            model_name="financingoffer",
            constraint=models.UniqueConstraint(
                fields=("provider", "product", "term_unit", "term_count", "ram_gb", "rom_gb"),
                name="uniq_financing_offer_provider_product_term_unit_count_ram_rom",
            ),
        ),
    ]

