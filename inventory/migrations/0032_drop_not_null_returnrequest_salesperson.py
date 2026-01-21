from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0031_alter_returnrequest_requesting_salesperson_nullable'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE inventory_returnrequest "
                "ALTER COLUMN requesting_salesperson_id DROP NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE inventory_returnrequest "
                "ALTER COLUMN requesting_salesperson_id SET NOT NULL;"
            ),
        ),
    ]
