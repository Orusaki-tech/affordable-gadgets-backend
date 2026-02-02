from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0037_leaditem_bundle_leaditem_bundle_group_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryunit',
            name='compare_at_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Original/list price used to show discounts (optional)',
                max_digits=10,
                null=True,
                verbose_name='Compare-at Price',
            ),
        ),
        migrations.CreateModel(
            name='WishlistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, db_index=True, help_text='Anonymous session key (used when customer is not identified).', max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('brand', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wishlist_items', to='inventory.brand')),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wishlist_items', to='inventory.customer')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wishlist_items', to='inventory.product')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='wishlistitem',
            constraint=models.UniqueConstraint(fields=('customer', 'product', 'brand'), name='uniq_wishlist_customer_product_brand'),
        ),
        migrations.AddConstraint(
            model_name='wishlistitem',
            constraint=models.UniqueConstraint(fields=('session_key', 'product', 'brand'), name='uniq_wishlist_session_product_brand'),
        ),
        migrations.AddIndex(
            model_name='wishlistitem',
            index=models.Index(fields=['session_key'], name='inventory_w_session__b3f1e6_idx'),
        ),
        migrations.AddIndex(
            model_name='wishlistitem',
            index=models.Index(fields=['customer', 'product'], name='inventory_w_customer_e9d9df_idx'),
        ),
        migrations.AddIndex(
            model_name='wishlistitem',
            index=models.Index(fields=['product'], name='inventory_w_product_5d2f2e_idx'),
        ),
    ]
