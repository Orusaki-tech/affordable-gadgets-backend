# Generated manually for review prefetch performance (public products list).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0042_alter_product_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='product',
            field=models.ForeignKey(
                db_index=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='reviews',
                to='inventory.product',
                verbose_name='Reviewed Product Template',
            ),
        ),
    ]
