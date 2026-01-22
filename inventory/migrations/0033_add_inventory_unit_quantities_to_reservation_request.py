from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0032_drop_not_null_returnrequest_salesperson"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservationrequest",
            name="inventory_unit_quantities",
            field=models.JSONField(blank=True, default=dict, help_text="Requested quantities by inventory unit id (for accessories)."),
        ),
    ]
