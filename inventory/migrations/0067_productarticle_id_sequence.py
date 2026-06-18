from django.db import migrations


def ensure_id_sequence(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS inventory_productarticle_id_seq
            OWNED BY inventory_productarticle.id;
            """
        )
        cursor.execute(
            """
            SELECT setval(
                'inventory_productarticle_id_seq',
                COALESCE((SELECT MAX(id) FROM inventory_productarticle), 1)
            );
            """
        )
        cursor.execute(
            """
            ALTER TABLE inventory_productarticle
            ALTER COLUMN id SET DEFAULT nextval('inventory_productarticle_id_seq');
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0066_productarticle_multi_article"),
    ]

    operations = [
        migrations.RunPython(ensure_id_sequence, migrations.RunPython.noop),
    ]
