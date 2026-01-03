# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0014_cartitem_promotion_cartitem_unit_price'),
    ]

    operations = [
        # Add new ManyToMany field
        migrations.AddField(
            model_name='reservationrequest',
            name='inventory_units',
            field=models.ManyToManyField(
                related_name='reservation_requests',
                to='inventory.inventoryunit',
                help_text='Inventory units in this reservation request'
            ),
        ),
        # Make old field nullable for migration compatibility
        migrations.AlterField(
            model_name='reservationrequest',
            name='inventory_unit',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='reservation_requests_old',
                to='inventory.inventoryunit',
                null=True,
                blank=True
            ),
        ),
        # Remove unique_together constraint
        migrations.AlterUniqueTogether(
            name='reservationrequest',
            unique_together=set(),
        ),
        # Data migration: Copy existing single units to ManyToMany
        migrations.RunPython(
            code=lambda apps, schema_editor: migrate_units_to_many_to_many(apps, schema_editor),
            reverse_code=lambda apps, schema_editor: reverse_migrate_units(apps, schema_editor),
        ),
    ]


def migrate_units_to_many_to_many(apps, schema_editor):
    """Copy existing inventory_unit to inventory_units ManyToMany field."""
    ReservationRequest = apps.get_model('inventory', 'ReservationRequest')
    for request in ReservationRequest.objects.all():
        if request.inventory_unit_id:
            request.inventory_units.add(request.inventory_unit_id)


def reverse_migrate_units(apps, schema_editor):
    """Reverse migration: set inventory_unit from first inventory_units item."""
    ReservationRequest = apps.get_model('inventory', 'ReservationRequest')
    for request in ReservationRequest.objects.all():
        first_unit = request.inventory_units.first()
        if first_unit:
            request.inventory_unit_id = first_unit.id
            request.save(update_fields=['inventory_unit'])

