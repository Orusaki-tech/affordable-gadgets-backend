# Payment Initiation Error Diagnosis

## Error Observed
Order created successfully, but payment initiation fails with:
- Error: "Failed to initiate payment"
- Order ID: `8c72b167-fdcc-4d04-8957-5030a3708c19`

## Root Causes Identified

### 1. TypeError: Unexpected Keyword Argument ✅ FIXED
**Issue:** `initiate_payment()` method was receiving `order_id` as kwarg but only accepted `pk`

**Fix Applied:**
- Changed method signature from `def initiate_payment(self, request, pk=None):`
- To: `def initiate_payment(self, request, pk=None, **kwargs):`
- This allows DRF to pass `order_id` when `lookup_field='order_id'`

**Status:** Fixed in code, needs deployment

### 2. Missing log_path Variable ✅ FIXED
**Issue:** `log_path` was used in `create()` method but not defined

**Fix Applied:**
- Added `log_path` definition at start of `create()` method

**Status:** Fixed in code, needs deployment

### 3. Possible Configuration Issues
Check if these environment variables are set in Render:
- `PESAPAL_CONSUMER_KEY`
- `PESAPAL_CONSUMER_SECRET`
- `PESAPAL_ENVIRONMENT` (sandbox or live)
- `PESAPAL_CALLBACK_URL`
- `PESAPAL_IPN_URL`

### 4. Possible Order Lookup Issues
The `get_object()` method might be failing to find the order, causing the exception.

## How to Diagnose

### Step 1: Check Render Logs
Look for these log messages when payment initiation is attempted:
- `[PESAPAL] ========== VIEW: INITIATE PAYMENT START ==========`
- `[PESAPAL] Getting order object...`
- `[PESAPAL] Order retrieved - ID: ...`
- `[PESAPAL] ========== INITIATE PAYMENT FAILED ==========`
- `[PESAPAL] ERROR: ...`
- `Traceback (most recent call last):`

### Step 2: Check Configuration
Verify in Render Environment Variables:
```bash
# Required
PESAPAL_CONSUMER_KEY=...
PESAPAL_CONSUMER_SECRET=...
PESAPAL_ENVIRONMENT=sandbox  # or live
PESAPAL_CALLBACK_URL=https://your-frontend.vercel.app/payment/callback/
PESAPAL_IPN_URL=https://affordable-gadgets-backend.onrender.com/api/inventory/pesapal/ipn/
```

### Step 3: Test Order Retrieval
Try accessing the order directly:
```
GET https://affordable-gadgets-backend.onrender.com/api/inventory/orders/8c72b167-fdcc-4d04-8957-5030a3708c19/
```

## Immediate Fixes Needed

### 1. Deploy the Code Fixes
The fixes I made need to be deployed:
```bash
git add inventory/views.py
git commit -m "Fix: Add **kwargs to initiate_payment and fix log_path in create method"
git push
```

### 2. Verify Configuration
Check Render environment variables are set correctly.

### 3. Check Backend Logs
After deployment, check Render logs for the exact error when payment initiation is attempted.

## Expected Behavior After Fix

When payment initiation is called:
1. Order is retrieved successfully
2. Payment service is initialized
3. Pesapal API is called
4. Redirect URL is returned
5. Frontend redirects user to Pesapal payment page

## Common Error Messages

### "PESAPAL_IPN_URL not configured"
- **Cause:** Missing `PESAPAL_IPN_URL` environment variable
- **Fix:** Set in Render environment variables

### "Order is already {status}"
- **Cause:** Order status is not PENDING
- **Fix:** Order should be in PENDING status for payment initiation

### "callback_url is required"
- **Cause:** No callback_url provided in request or settings
- **Fix:** Frontend should send `callback_url` in request body

### "Authentication failed"
- **Cause:** Invalid `PESAPAL_CONSUMER_KEY` or `PESAPAL_CONSUMER_SECRET`
- **Fix:** Verify credentials in Render environment variables

### "TypeError: unexpected keyword argument"
- **Cause:** Method signature issue (should be fixed with **kwargs)
- **Fix:** Deploy the code fix

## Next Steps

1. **Deploy the fixes** I made to `inventory/views.py`
2. **Check Render logs** for the specific error when payment initiation fails
3. **Verify configuration** - ensure all Pesapal environment variables are set
4. **Test again** with a new order after deployment

