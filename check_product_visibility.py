#!/usr/bin/env python
"""
Diagnostic script to check why products are not showing in the frontend.

Run this from Django shell:
    python manage.py shell
    >>> exec(open('check_product_visibility.py').read())

Or run directly:
    python manage.py shell < check_product_visibility.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
django.setup()

from inventory.models import Product, InventoryUnit, Brand
from django.db.models import Q, Sum, Count, Case, When, IntegerField, Value
from django.db.models.functions import Coalesce

print("=" * 80)
print("PRODUCT VISIBILITY DIAGNOSTIC")
print("=" * 80)
print()

# 1. Check all products
print("1. CHECKING PRODUCT STATUS")
print("-" * 80)
products = Product.objects.filter(is_discontinued=False, is_published=True)
print(f"✅ Published, non-discontinued products: {products.count()}")

unpublished = Product.objects.filter(is_published=False)
print(f"❌ Unpublished products: {unpublished.count()}")

discontinued = Product.objects.filter(is_discontinued=True)
print(f"❌ Discontinued products: {discontinued.count()}")
print()

# 2. Check inventory units
print("2. CHECKING INVENTORY UNITS")
print("-" * 80)
all_units = InventoryUnit.objects.all()
print(f"Total inventory units: {all_units.count()}")

available_units = InventoryUnit.objects.filter(
    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
    available_online=True
)
print(f"✅ Available & online units: {available_units.count()}")

# Status breakdown
statuses = InventoryUnit.objects.values('sale_status').annotate(count=Count('id'))
print("\nStatus breakdown:")
for status in statuses:
    status_display = dict(InventoryUnit.SaleStatusChoices.choices).get(status['sale_status'], status['sale_status'])
    print(f"  - {status_display}: {status['count']}")

# Available online breakdown
online_status = InventoryUnit.objects.values('available_online').annotate(count=Count('id'))
print("\nAvailable online breakdown:")
for status in online_status:
    print(f"  - available_online={status['available_online']}: {status['count']}")
print()

# 3. Check products with available units
print("3. CHECKING PRODUCTS WITH AVAILABLE UNITS")
print("-" * 80)
products_with_units = []
products_without_units = []

for product in products:
    # Check available units
    units_filter = Q(
        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
        available_online=True
    )
    
    available = product.inventory_units.filter(units_filter)
    
    if product.product_type == Product.ProductType.ACCESSORY:
        count = available.aggregate(total=Sum('quantity'))['total'] or 0
    else:
        count = available.count()
    
    if count > 0:
        products_with_units.append({
            'product': product,
            'count': count,
            'units': available
        })
    else:
        total_units = product.inventory_units.count()
        products_without_units.append({
            'product': product,
            'total_units': total_units,
            'available_units': available.count()
        })

print(f"✅ Products WITH available units: {len(products_with_units)}")
print(f"❌ Products WITHOUT available units: {len(products_without_units)}")
print()

# 4. Show products that should appear
print("4. PRODUCTS THAT SHOULD APPEAR IN FRONTEND")
print("-" * 80)
if products_with_units:
    for item in products_with_units[:10]:  # Show first 10
        product = item['product']
        print(f"✅ {product.id}: {product.product_name}")
        print(f"   Type: {product.product_type}, Available units: {item['count']}")
        # Show price range
        prices = item['units'].values_list('selling_price', flat=True)
        if prices:
            print(f"   Price range: KES {min(prices):,.0f} - KES {max(prices):,.0f}")
        print()
else:
    print("❌ NO PRODUCTS WILL APPEAR IN FRONTEND!")
    print()

# 5. Show products that won't appear (with reasons)
print("5. PRODUCTS THAT WON'T APPEAR (WITH REASONS)")
print("-" * 80)
if products_without_units:
    for item in products_without_units[:10]:  # Show first 10
        product = item['product']
        print(f"❌ {product.id}: {product.product_name}")
        print(f"   Total units: {item['total_units']}")
        print(f"   Available units: {item['available_units']}")
        
        # Check why units are not available
        all_product_units = product.inventory_units.all()
        if all_product_units.exists():
            statuses = all_product_units.values('sale_status', 'available_online').annotate(count=Count('id'))
            print("   Unit statuses:")
            for status in statuses:
                status_display = dict(InventoryUnit.SaleStatusChoices.choices).get(status['sale_status'], status['sale_status'])
                print(f"     - {status_display}, online={status['available_online']}: {status['count']}")
        else:
            print("   ⚠️  NO INVENTORY UNITS CREATED FOR THIS PRODUCT")
        print()
else:
    print("✅ All published products have available units!")
    print()

# 6. Brand filtering check
print("6. BRAND FILTERING CHECK")
print("-" * 80)
brands = Brand.objects.filter(is_active=True)
print(f"Active brands: {brands.count()}")

for brand in brands:
    print(f"\nBrand: {brand.name} ({brand.code})")
    
    # Check products for this brand
    brand_products = products.filter(
        Q(brands=brand) | Q(is_global=True) | Q(brands__isnull=True)
    ).distinct()
    
    print(f"  Products visible for this brand: {brand_products.count()}")
    
    # Check units for this brand
    brand_units = available_units.filter(
        Q(brands=brand) | Q(brands__isnull=True)
    )
    print(f"  Available units for this brand: {brand_units.count()}")
    
    # Count products with available units for this brand
    count = 0
    for product in brand_products:
        units_filter = Q(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        ) & (Q(brands=brand) | Q(brands__isnull=True))
        
        available = product.inventory_units.filter(units_filter)
        if product.product_type == Product.ProductType.ACCESSORY:
            unit_count = available.aggregate(total=Sum('quantity'))['total'] or 0
        else:
            unit_count = available.count()
        
        if unit_count > 0:
            count += 1
    
    print(f"  Products with available units: {count}")
print()

# 7. Recommendations
print("7. RECOMMENDATIONS")
print("-" * 80)
if len(products_without_units) > 0:
    print("⚠️  ISSUES FOUND:")
    print()
    print("Products without available units:")
    print("  1. Check if inventory units are created for these products")
    print("  2. Check if sale_status = 'AV' (AVAILABLE)")
    print("  3. Check if available_online = True")
    print()
    print("To fix:")
    print("  1. Go to Django Admin: /admin/inventory/inventoryunit/")
    print("  2. Find units for these products")
    print("  3. Set sale_status = 'Available'")
    print("  4. Set available_online = True")
    print("  5. Save")
else:
    print("✅ All published products have available units!")
    print("   If products still don't show in frontend:")
    print("   1. Check brand code in frontend (X-Brand-Code header)")
    print("   2. Check API endpoint: /api/v1/public/products/")
    print("   3. Check browser console for errors")
print()

print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
