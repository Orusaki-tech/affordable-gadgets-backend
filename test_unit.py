import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings")
django.setup()

from inventory.models import InventoryUnit

unit = InventoryUnit.objects.first()
if unit:
    print(f"Unit ID: {unit.id}")
    print(f"Product Template Brand: {unit.product_template.brand}")
    print(f"Sale Status: {unit.sale_status}")
    print(f"Selling Price: {unit.selling_price}")
else:
    print("No units found.")
