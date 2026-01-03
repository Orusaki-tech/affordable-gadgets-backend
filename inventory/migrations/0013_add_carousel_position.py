# Generated manually for adding carousel_position field

from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0012_add_promotion_type_and_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='promotion',
            name='carousel_position',
            field=models.IntegerField(
                blank=True,
                help_text='Position in stories carousel (1-5). 1 = Large banner, 2-5 = Grid positions',
                null=True,
            ),
        ),
    ]

