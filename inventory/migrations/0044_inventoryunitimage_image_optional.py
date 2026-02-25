# Generated for unit image upload: allow null/blank so serializer can create then set after Cloudinary upload.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0043_review_product_id_index'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inventoryunitimage',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='unit_photos/%Y/%m/'),
        ),
    ]
