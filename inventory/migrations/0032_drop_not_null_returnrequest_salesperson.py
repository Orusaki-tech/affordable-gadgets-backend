from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0031_alter_returnrequest_requesting_salesperson_nullable'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$\n"
                "BEGIN\n"
                "  IF EXISTS (\n"
                "    SELECT 1\n"
                "    FROM information_schema.columns\n"
                "    WHERE table_name = 'inventory_returnrequest'\n"
                "      AND column_name = 'requesting_salesperson_id'\n"
                "      AND is_nullable = 'NO'\n"
                "  ) THEN\n"
                "    ALTER TABLE inventory_returnrequest\n"
                "      ALTER COLUMN requesting_salesperson_id DROP NOT NULL;\n"
                "  END IF;\n"
                "END $$;"
            ),
            reverse_sql=(
                "DO $$\n"
                "BEGIN\n"
                "  IF EXISTS (\n"
                "    SELECT 1\n"
                "    FROM information_schema.columns\n"
                "    WHERE table_name = 'inventory_returnrequest'\n"
                "      AND column_name = 'requesting_salesperson_id'\n"
                "      AND is_nullable = 'YES'\n"
                "  ) THEN\n"
                "    ALTER TABLE inventory_returnrequest\n"
                "      ALTER COLUMN requesting_salesperson_id SET NOT NULL;\n"
                "  END IF;\n"
                "END $$;"
            ),
        ),
    ]
