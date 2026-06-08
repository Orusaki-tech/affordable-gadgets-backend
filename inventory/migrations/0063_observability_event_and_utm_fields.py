import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0062_user_supabase_uid_whatsappclickevent_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='utm_campaign',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='utm_content',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='utm_medium',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='utm_source',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.CreateModel(
            name='ObservabilityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=40)),
                ('event_type', models.CharField(choices=[('search', 'Search Query'), ('product_view', 'Product Detail View'), ('page_view', 'Page View'), ('whatsapp_click', 'WhatsApp Click')], db_index=True, max_length=32)),
                ('metadata', models.JSONField(blank=True, default=dict, null=True)),
                ('brand_code', models.CharField(db_index=True, default='AFFORDABLE_GADGETS', max_length=50)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.product')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Observability Event',
                'verbose_name_plural': 'Observability Events',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['user', 'created_at'], name='inventory_o_user_id_687442_idx'), models.Index(fields=['event_type', 'created_at'], name='inventory_o_event_t_b98293_idx'), models.Index(fields=['session_key', 'created_at'], name='inventory_o_session_f2b3c4_idx')],
            },
        ),
    ]
