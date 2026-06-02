# Generated manually for blog recovery — prevent accidental CASCADE delete of articles.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0060_add_whatsappclickevent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productarticle",
            name="product",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                primary_key=True,
                related_name="article",
                serialize=False,
                to="inventory.product",
            ),
        ),
    ]
