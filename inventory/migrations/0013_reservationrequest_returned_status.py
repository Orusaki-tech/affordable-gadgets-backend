from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0012_add_promotion_type_and_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reservationrequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('PE', 'Pending'),
                    ('AP', 'Approved'),
                    ('RE', 'Rejected'),
                    ('EX', 'Expired'),
                    ('RT', 'Returned'),
                ],
                default='PE',
                max_length=2,
            ),
        ),
    ]

