#!/usr/bin/env python
"""
Script to fix product visibility by ensuring all inventory units are:
- sale_status = 'AV' (AVAILABLE)
- available_online = True

Run this from Django shell:
    python manage.py shell
    >>> exec(open('fix_product_visibility.py').read())
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
django.setup()

from inventory.models import Product, InventoryUnit

print("=" * 80)
print("FIXING PRODUCT VISIBILITY")
print("=" * 80)
print()

# 1. Fix all inventory units to be available and online
print("1. Fixing inventory units...")
print("-" * 80)

# Get all units that are not available or not online
units_to_fix = InventoryUnit.objects.filter(
    ~Q(sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE) | 
    ~Q(available_online=True)
)

print(f"Found {units_to_fix.count()} units that need fixing")

fixed_count = 0
for unit in units_to_fix:
    changed = False
    if unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
        print(f"  Unit {unit.id}: Changing sale_status from {unit.sale_status} to AVAILABLE")
        unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
        changed = True
    
    if not unit.available_online:
        print(f"  Unit {unit.id}: Setting available_online to True")
        unit.available_online = True
        changed = True
    
    if changed:
        unit.save()
        fixed_count += 1

print(f"✅ Fixed {fixed_count} units")
print()

# 2. Ensure all products are published
print("2. Ensuring products are published...")
print("-" * 80)

unpublished = Product.objects.filter(is_published=False, is_discontinued=False)
print(f"Found {unpublished.count()} unpublished products")

if unpublished.exists():
    unpublished.update(is_published=True)
    print(f"✅ Published {unpublished.count()} products")
else:
    print("✅ All products are already published")
print()

# 3. Verify fix
print("3. Verifying fix...")
print("-" * 80)

available_units = InventoryUnit.objects.filter(
    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
    available_online=True
)
print(f"✅ Available & online units: {available_units.count()}")

products = Product.objects.filter(is_published=True, is_discontinued=False)
print(f"✅ Published products: {products.count()}")

# Count products with available units
from django.db.models import Sum, Count, Q

products_with_units = 0
for product in products:
    units = product.inventory_units.filter(
        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
        available_online=True
    )
    if product.product_type == Product.ProductType.ACCESSORY:
        count = units.aggregate(total=Sum('quantity'))['total'] or 0
    else:
        count = units.count()
    if count > 0:
        products_with_units += 1

print(f"✅ Products with available units: {products_with_units}")
print()

print("=" * 80)
print("FIX COMPLETE!")
print("=" * 80)
print()
print("Your products should now appear in the frontend.")
print("Refresh your browser to see the changes.")
