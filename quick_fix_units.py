"""
Quick fix script to make all inventory units available and online.
Run this on production via Django shell or as a one-liner.

Usage on production:
    python manage.py shell
    >>> exec(open('quick_fix_units.py').read())

Or as one-liner:
    python manage.py shell -c "from inventory.models import InventoryUnit; InventoryUnit.objects.update(sale_status='AV', available_online=True); print(f'Fixed {InventoryUnit.objects.filter(sale_status=\"AV\", available_online=True).count()} units')"
"""
from inventory.models import InventoryUnit

# Count before
before_count = InventoryUnit.objects.filter(
    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
    available_online=True
).count()

# Fix all units
updated = InventoryUnit.objects.update(
    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
    available_online=True
)

# Count after
after_count = InventoryUnit.objects.filter(
    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
    available_online=True
).count()

print(f"✅ Updated {updated} inventory units")
print(f"   Before: {before_count} available units")
print(f"   After: {after_count} available units")
print()
print("Your products should now appear in the frontend!")
