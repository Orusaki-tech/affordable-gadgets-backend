# Fix Pending Payment Units Issue

## Problem
Inventory units remain in "PENDING_PAYMENT" status even after orders are paid online via Pesapal.

## Root Cause
When payment is completed via Pesapal IPN, the code:
- ✅ Updates order status to PAID
- ✅ Generates receipt
- ❌ **Does NOT update inventory unit status from PENDING_PAYMENT to SOLD**

## Fix Applied

### 1. Updated Payment Service
Modified `inventory/services/pesapal_payment_service.py` to update inventory units to SOLD when payment is completed.

**What it does:**
- When payment status becomes COMPLETED, it now:
  1. Updates order status to PAID (already done)
  2. **Updates all inventory units from PENDING_PAYMENT to SOLD** (NEW)
  3. Generates receipt (already done)

### 2. Management Command for Existing Orders
Created `fix_pending_payment_units.py` management command to fix existing orders.

## How to Fix Existing Orders

### Option 1: Run Management Command (Recommended)

**Dry run first (see what would be fixed):**
```bash
python manage.py fix_pending_payment_units --dry-run
```

**Actually fix the units:**
```bash
python manage.py fix_pending_payment_units
```

This will:
- Find all PAID orders
- Check their inventory units
- Update units in PENDING_PAYMENT status to SOLD

### Option 2: Manual Fix via Admin

1. Go to admin panel
2. Find orders with status "Paid"
3. Check their inventory units
4. Manually update units from PENDING_PAYMENT to SOLD

### Option 3: SQL Fix (Advanced)

```sql
UPDATE inventory_inventoryunit
SET sale_status = 'SO'
WHERE id IN (
    SELECT oi.inventory_unit_id
    FROM inventory_orderitem oi
    JOIN inventory_order o ON oi.order_id = o.order_id
    WHERE o.status = 'Paid'
    AND oi.inventory_unit_id IS NOT NULL
)
AND sale_status = 'PP';
```

## Verification

After running the fix:

1. **Check units in admin:**
   - Go to Products → Select product → View units
   - Units from paid orders should show "SOLD" status

2. **Check via API:**
   ```bash
   curl "https://affordable-gadgets-backend.onrender.com/api/inventory/units/{unit_id}/"
   ```
   - Should show `"sale_status": "SO"` (SOLD)

3. **Check orders:**
   - Paid orders should have all units in SOLD status

## Prevention

The fix ensures that:
- ✅ Future payments will automatically update units to SOLD
- ✅ No manual intervention needed for new orders
- ✅ Consistent status across orders and units

## Testing

After deploying the fix:

1. Create a test order
2. Complete payment via Pesapal
3. Verify:
   - Order status = PAID ✅
   - Inventory units status = SOLD ✅
   - Receipt generated ✅

## Files Changed

1. `inventory/services/pesapal_payment_service.py` - Added unit status update
2. `inventory/management/commands/fix_pending_payment_units.py` - New command to fix existing orders
