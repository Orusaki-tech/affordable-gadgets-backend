from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0040_rename_inventory_d_county_ward_idx_inventory_d_county_90ab50_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='customer',
            name='email_verification_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='email_verification_token',
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]
