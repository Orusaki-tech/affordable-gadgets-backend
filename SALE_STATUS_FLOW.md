# Sale Status Flow: How Products Appear in Frontend

## The Problem

Products are not showing in the frontend. This document explains how `sale_status` affects product visibility and how it changes throughout the product lifecycle.

---

## 1. Frontend Filtering Requirements

**File:** `inventory/views_public.py` (lines 348-352)

The backend **REQUIRES** both conditions for a product to appear:

```python
available_units_filter = Q(
    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,  # ✅ Must be AVAILABLE
    available_online=True                                    # ✅ Must be True
)
```

**Both conditions must be true:**
- ✅ `sale_status` must be `'AV'` (AVAILABLE)
- ✅ `available_online` must be `True`

If **either** condition fails, the product will **NOT** appear in the frontend.

---

## 2. Default Values When Creating InventoryUnit

**File:** `inventory/models.py` (lines 409, 463-466)

When you create a new `InventoryUnit`:

```python
sale_status = models.CharField(
    max_length=2, 
    choices=SaleStatusChoices.choices, 
    default=SaleStatusChoices.AVAILABLE  # ✅ Default: 'AV' (AVAILABLE)
)

available_online = models.BooleanField(
    default=True,  # ✅ Default: True
    help_text="Whether this unit can be purchased online"
)
```

**By default, new units SHOULD appear in frontend** because:
- `sale_status` defaults to `AVAILABLE` ✅
- `available_online` defaults to `True` ✅

---

## 3. Sale Status Choices

**File:** `inventory/models.py` (lines 380-385)

```python
class SaleStatusChoices(models.TextChoices):
    AVAILABLE = 'AV', _('Available')           # ✅ Shows in frontend
    SOLD = 'SD', _('Sold')                     # ❌ Hidden from frontend
    RESERVED = 'RS', _('Reserved')              # ❌ Hidden from frontend
    RETURNED = 'RT', _('Returned')              # ❌ Hidden from frontend
    PENDING_PAYMENT = 'PP', _('Pending Payment') # ❌ Hidden from frontend
```

**Only `AVAILABLE` status shows in frontend.**

---

## 4. How Sale Status Changes

### 4.1 Manual Changes (Admin Panel)

**File:** `inventory/admin.py` (lines 71-100)

Admins can manually change `sale_status` in Django Admin:
- Navigate to: `/admin/inventory/inventoryunit/`
- Edit any unit
- Change `sale_status` field
- Save

**Common scenarios:**
- Mark as `SOLD` when manually recording a sale
- Mark as `RESERVED` when holding for a customer
- Mark as `RETURNED` when processing a return

### 4.2 Programmatic Changes

Currently, **there are NO automatic signals or code that changes `sale_status`** when:
- Orders are created
- Payments are completed
- Reservations are approved

**This means:**
- ❌ Creating an order does NOT automatically set `sale_status = SOLD`
- ❌ Completing payment does NOT automatically set `sale_status = SOLD`
- ❌ Approving a reservation does NOT automatically set `sale_status = RESERVED`

**You must manually update `sale_status` in the admin panel or via API.**

---

## 5. Product Visibility Logic

**File:** `inventory/views_public.py` (lines 148-920)

### Step-by-Step Filtering:

1. **Base Product Filter:**
   ```python
   Product.objects.filter(is_discontinued=False, is_published=True)
   ```
   - Product must be published (`is_published=True`)
   - Product must not be discontinued (`is_discontinued=False`)

2. **Inventory Unit Filter:**
   ```python
   inventory_units.filter(
       sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
       available_online=True
   )
   ```
   - Only counts units with `sale_status='AV'`
   - Only counts units with `available_online=True`

3. **Brand Filtering:**
   ```python
   if brand:
       units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
   ```
   - If brand is specified, only show units for that brand or global units

4. **Count Calculation:**
   - **Accessories:** Sum of `quantity` field
   - **Phones/Laptops/Tablets:** Count of distinct units

5. **Final Filter:**
   ```python
   queryset = queryset.annotate(available_units_count=...)
   ```
   - Products with `available_units_count = 0` are effectively hidden
   - Even if product exists, if no available units → product doesn't show

---

## 6. Common Issues & Solutions

### Issue 1: Products Created But Not Showing

**Possible Causes:**
1. ❌ `sale_status` is not `AVAILABLE`
2. ❌ `available_online` is `False`
3. ❌ Product `is_published=False`
4. ❌ Product `is_discontinued=True`
5. ❌ No inventory units created for the product
6. ❌ Brand mismatch (unit not assigned to correct brand)

**Solution:**
```python
# Check in Django shell:
from inventory.models import Product, InventoryUnit

product = Product.objects.get(id=YOUR_PRODUCT_ID)
print(f"Product published: {product.is_published}")
print(f"Product discontinued: {product.is_discontinued}")

units = product.inventory_units.all()
for unit in units:
    print(f"Unit {unit.id}: sale_status={unit.sale_status}, available_online={unit.available_online}")
```

### Issue 2: Units Show as Available But Product Doesn't Appear

**Possible Causes:**
1. ❌ Brand filtering issue (unit not assigned to brand)
2. ❌ Product not published
3. ❌ All units have `available_online=False`

**Solution:**
```python
# Check brand assignment:
unit = InventoryUnit.objects.get(id=YOUR_UNIT_ID)
print(f"Unit brands: {unit.brands.all()}")
print(f"Request brand: {request.brand}")  # Check in viewset
```

### Issue 3: Products Disappear After Order

**Cause:**
- `sale_status` is NOT automatically changed to `SOLD` when order is created
- If you manually set it to `SOLD`, product disappears (expected behavior)

**Solution:**
- Keep `sale_status = AVAILABLE` until order is confirmed/paid
- Or implement automatic status change (see section 7)

---

## 7. Recommended: Automatic Status Updates

### Option 1: Signal to Update Status on Order Creation

**File:** `inventory/signals.py`

Add this signal:

```python
@receiver(post_save, sender=Order)
def update_inventory_status_on_order(sender, instance, created, **kwargs):
    """Update inventory unit sale_status when order is created."""
    if created:
        for order_item in instance.order_items.all():
            if order_item.inventory_unit:
                # Mark as PENDING_PAYMENT initially
                order_item.inventory_unit.sale_status = InventoryUnit.SaleStatusChoices.PENDING_PAYMENT
                order_item.inventory_unit.save()
```

### Option 2: Update Status When Payment Confirmed

```python
@receiver(post_save, sender=PesapalPayment)
def update_inventory_status_on_payment(sender, instance, created, **kwargs):
    """Update inventory unit sale_status when payment is confirmed."""
    if not created and instance.status == PesapalPayment.StatusChoices.COMPLETED:
        order = instance.order
        for order_item in order.order_items.all():
            if order_item.inventory_unit:
                order_item.inventory_unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
                order_item.inventory_unit.save()
```

### Option 3: Admin Action to Bulk Update

**File:** `inventory/admin.py`

```python
@admin.action(description='Mark selected units as SOLD')
def mark_as_sold(modeladmin, request, queryset):
    queryset.update(sale_status=InventoryUnit.SaleStatusChoices.SOLD)

@admin.register(InventoryUnit)
class InventoryUnitAdmin(admin.ModelAdmin):
    actions = [mark_as_sold]
    # ... rest of admin config
```

---

## 8. Debugging Checklist

### Check Product Visibility:

```python
# 1. Check product status
product = Product.objects.get(id=YOUR_PRODUCT_ID)
assert product.is_published == True, "Product not published"
assert product.is_discontinued == False, "Product is discontinued"

# 2. Check inventory units
units = product.inventory_units.all()
assert units.exists(), "No inventory units created"

# 3. Check unit statuses
available_units = units.filter(
    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
    available_online=True
)
assert available_units.exists(), f"No available units. Found {units.count()} total units"

# 4. Check brand assignment (if brand filtering is active)
if brand:
    brand_units = available_units.filter(
        Q(brands=brand) | Q(brands__isnull=True)
    )
    assert brand_units.exists(), f"Units not assigned to brand {brand.code}"

# 5. Check counts
from django.db.models import Sum, Count, Case, When, IntegerField, Value
from django.db.models.functions import Coalesce

if product.product_type == Product.ProductType.ACCESSORY:
    count = available_units.aggregate(total=Sum('quantity'))['total'] or 0
else:
    count = available_units.count()

print(f"Available units count: {count}")
assert count > 0, "Available units count is 0"
```

### Check Frontend API Call:

```bash
# Test API directly:
curl -H "X-Brand-Code: AFFORDABLE_GADGETS" \
     http://localhost:8000/api/v1/public/products/

# Check response:
# - Does it include your product?
# - What is available_units_count?
# - What is min_price/max_price?
```

---

## 9. Summary

### Why Products Might Not Show:

1. ✅ **Default values are correct** (`sale_status=AVAILABLE`, `available_online=True`)
2. ❌ **But if manually changed**, products disappear
3. ❌ **No automatic updates** when orders/payments happen
4. ❌ **Must manually manage** `sale_status` in admin

### Key Takeaways:

- **`sale_status` must be `AVAILABLE`** for frontend visibility
- **`available_online` must be `True`** for frontend visibility
- **Both conditions are required** (AND logic)
- **Status is NOT automatically updated** on order/payment
- **Check both product AND unit status** when debugging

### Quick Fix:

If products are not showing, check in Django Admin:
1. Go to `/admin/inventory/inventoryunit/`
2. Find your units
3. Ensure `sale_status = Available` and `available_online = True`
4. Save

---

## 10. Next Steps

1. **Check your existing units:**
   ```python
   from inventory.models import InventoryUnit
   InventoryUnit.objects.filter(sale_status='AV', available_online=True).count()
   ```

2. **Check products with no available units:**
   ```python
   from inventory.models import Product
   products = Product.objects.filter(is_published=True, is_discontinued=False)
   for p in products:
       available = p.inventory_units.filter(sale_status='AV', available_online=True)
       if not available.exists():
           print(f"Product {p.id} ({p.product_name}) has no available units")
   ```

3. **Consider implementing automatic status updates** (see section 7)
