from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0033_add_inventory_unit_quantities_to_reservation_request'),
    ]

    operations = [
        migrations.CreateModel(
            name='Bundle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('start_date', models.DateTimeField(blank=True, null=True)),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('pricing_mode', models.CharField(choices=[('FX', 'Fixed Bundle Price'), ('PC', 'Percentage Off Items Total'), ('AM', 'Fixed Amount Off Items Total')], default='FX', max_length=2)),
                ('bundle_price', models.DecimalField(blank=True, decimal_places=2, help_text='Total bundle price (required for Fixed pricing)', max_digits=10, null=True)),
                ('discount_percentage', models.DecimalField(blank=True, decimal_places=2, help_text='Percentage discount on items total (for Percentage pricing)', max_digits=5, null=True)),
                ('discount_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Fixed discount amount on items total (for Amount pricing)', max_digits=10, null=True)),
                ('show_in_listings', models.BooleanField(default=True, help_text='Show bundle badge in search/category lists')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bundles', to='inventory.brand')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_bundles', to='inventory.admin')),
                ('main_product', models.ForeignKey(help_text='Primary product this bundle is attached to', on_delete=django.db.models.deletion.PROTECT, related_name='bundles', to='inventory.product')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BundleItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('override_price', models.DecimalField(blank=True, decimal_places=2, help_text='Optional override price for this item in the bundle', max_digits=10, null=True)),
                ('display_order', models.IntegerField(default=0)),
                ('bundle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='inventory.bundle')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bundle_items', to='inventory.product')),
            ],
            options={
                'ordering': ['display_order', 'id'],
                'unique_together': {('bundle', 'product')},
            },
        ),
        migrations.AddField(
            model_name='cartitem',
            name='bundle',
            field=models.ForeignKey(blank=True, help_text='Bundle applied to this item (if any)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cart_items', to='inventory.bundle'),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='bundle_group_id',
            field=models.UUIDField(blank=True, db_index=True, help_text='Groups cart items added as a single bundle', null=True),
        ),
        migrations.AddIndex(
            model_name='bundle',
            index=models.Index(fields=['brand', 'is_active'], name='inventory_b_brand_i_4dd7a8_idx'),
        ),
        migrations.AddIndex(
            model_name='bundle',
            index=models.Index(fields=['main_product', 'is_active'], name='inventory_b_main_p_58d3be_idx'),
        ),
    ]
