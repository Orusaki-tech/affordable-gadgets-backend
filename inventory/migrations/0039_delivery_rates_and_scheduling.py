from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0038_add_compare_at_price_and_wishlist'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeliveryRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('county', models.CharField(max_length=100)),
                ('ward', models.CharField(blank=True, max_length=100, null=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['county', 'ward'],
                'indexes': [
                    models.Index(fields=['county', 'ward'], name='inventory_d_county_ward_idx'),
                    models.Index(fields=['is_active'], name='inventory_d_is_active_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('county', 'ward'), name='uniq_delivery_rate_county_ward'),
                ],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_county',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_ward',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_window_start',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_window_end',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='delivery_county',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='lead',
            name='delivery_ward',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='lead',
            name='delivery_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='lead',
            name='delivery_window_start',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='delivery_window_end',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='delivery_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='cart',
            name='delivery_county',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='cart',
            name='delivery_ward',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='cart',
            name='delivery_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='cart',
            name='delivery_window_start',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='cart',
            name='delivery_window_end',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='cart',
            name='delivery_notes',
            field=models.TextField(blank=True),
        ),
    ]
