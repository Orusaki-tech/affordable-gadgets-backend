import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings")
django.setup()

from inventory.models import Product

p = Product.objects.first()
if p:
    print(f"Product ID: {p.id}, Name: {p.product_name}")
    print(f"Brands M2M: {list(p.brands.values_list('code', flat=True))}")
    print(f"Brand Field: {p.brand}")
