import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings")
django.setup()

from inventory.models import InventoryUnit, Brand
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from decimal import Decimal

bc = "AFFORDABLE_GADGETS"
print(f"Testing for brand code: {bc}")

# Using M2M field: Product.brands
# Note: Since 'brands' can be empty meaning "all brands", we also need to include units where product_template.brands is null
for status in ["AV", "SD", "RS", "RT", "PP"]:
    # Find units that either explicitly belong to this brand OR have no brands assigned (meaning all brands)
    val = InventoryUnit.objects.filter(
        Q(product_template__brands__code=bc) | Q(product_template__brands__isnull=True),
        sale_status=status
    ).aggregate(total=Coalesce(Sum("selling_price"), Decimal("0")))["total"]
    
    print(f"Status: {status}, Value: {val}")
