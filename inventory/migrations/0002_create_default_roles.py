"""
Data migration to create default AdminRole entries.
Run this after creating the model migrations.
"""
from django.db import migrations


def create_default_roles(apps, schema_editor):
    """Create default admin roles."""
    AdminRole = apps.get_model('inventory', 'AdminRole')
    
    roles = [
        {'name': 'SP', 'display_name': 'Salesperson', 'description': 'Can view inventory and create orders'},
        {'name': 'IM', 'display_name': 'Inventory Manager', 'description': 'Full access to inventory management'},
        {'name': 'CC', 'display_name': 'Content Creator', 'description': 'Can create reviews and content'},
        {'name': 'OM', 'display_name': 'Order Manager', 'description': 'Manages orders (future role)'},
        {'name': 'MM', 'display_name': 'Marketing Manager', 'description': 'Can create and manage promotions'},
    ]
    
    for role_data in roles:
        AdminRole.objects.get_or_create(
            name=role_data['name'],
            defaults=role_data
        )


def reverse_create_default_roles(apps, schema_editor):
    """Reverse migration - remove default roles."""
    AdminRole = apps.get_model('inventory', 'AdminRole')
    AdminRole.objects.filter(name__in=['SP', 'IM', 'CC', 'OM', 'MM']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0009_adminrole_inventoryunit_reserved_by_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_roles, reverse_create_default_roles),
    ]

