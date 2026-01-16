from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0008_review_video_file_alter_review_customer_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='review_image',
            field=models.ImageField(blank=True, help_text='Optional photo uploaded by the reviewer', null=True, upload_to='review_images/%Y/%m/', verbose_name='Review Photo'),
        ),
        migrations.AddField(
            model_name='review',
            name='product_condition',
            field=models.CharField(blank=True, help_text='Condition at time of purchase (e.g. New, Refurbished, Pre-owned)', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='review',
            name='purchase_date',
            field=models.DateField(blank=True, help_text='Date the item was purchased', null=True),
        ),
    ]
