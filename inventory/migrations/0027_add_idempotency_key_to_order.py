# Generated manually for idempotency support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0026_make_return_request_salesperson_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='idempotency_key',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Idempotency key to prevent duplicate orders from retries or double-clicks',
                max_length=255,
                null=True,
                unique=True
            ),
        ),
    ]

