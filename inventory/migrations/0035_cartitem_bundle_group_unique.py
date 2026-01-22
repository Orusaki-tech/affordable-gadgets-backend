from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0034_bundle_models_and_cartitem_bundle'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='cartitem',
            unique_together={('cart', 'inventory_unit', 'bundle_group_id')},
        ),
    ]
