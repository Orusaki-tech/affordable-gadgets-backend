# Payment Initiation Failure - Troubleshooting Guide

## Current Issue
Order is created successfully, but payment initiation fails with:
- **Error:** "Failed to initiate payment"
- **Order ID:** `8c72b167-fdcc-4d04-8957-5030a3708c19`

## What's Happening

The error message "Failed to initiate payment" comes from the exception handler in `initiate_payment()` view method. This means an **exception is being raised** somewhere in the payment initiation flow.

## Step 1: Check Render Logs

The logs will show the **exact error**. Look for these log messages in Render:

### Expected Log Sequence (Success):
```
[PESAPAL] ========== VIEW: INITIATE PAYMENT START ==========
[PESAPAL] Order PK: 8c72b167-fdcc-4d04-8957-5030a3708c19
[PESAPAL] Getting order object...
[PESAPAL] Order retrieved - ID: 8c72b167-fdcc-4d04-8957-5030a3708c19
[PESAPAL] Calling service.initiate_payment...
[PESAPAL] ========== INITIATE PAYMENT START ==========
[PESAPAL] Order ID: 8c72b167-fdcc-4d04-8957-5030a3708c19
[PESAPAL] IPN URL: https://...
[PESAPAL] ========== INITIATE PAYMENT SUCCESS ==========
```

### Error Log Patterns to Look For:

#### 1. Order Not Found:
```
[PESAPAL] ========== VIEW: INITIATE PAYMENT EXCEPTION ==========
[PESAPAL] ERROR: Error initiating payment for order ...: Order matching query does not exist
Traceback (most recent call last):
  ...
```

#### 2. Configuration Missing:
```
[PESAPAL] ========== INITIATE PAYMENT FAILED ==========
[PESAPAL] ERROR: PESAPAL_IPN_URL not configured
```

#### 3. Authentication Error:
```
[PESAPAL] ========== API REQUEST FAILED ==========
[PESAPAL] ERROR: Authentication failed (401): ...
```

#### 4. TypeError (if code not deployed):
```
[PESAPAL] ========== VIEW: INITIATE PAYMENT EXCEPTION ==========
[PESAPAL] ERROR: ... got an unexpected keyword argument 'order_id'
Traceback (most recent call last):
  ...
```

## Step 2: Verify Configuration

Check Render Environment Variables:

### Required Variables:
```bash
PESAPAL_CONSUMER_KEY=your_consumer_key
PESAPAL_CONSUMER_SECRET=your_consumer_secret
PESAPAL_ENVIRONMENT=sandbox  # or 'live'
PESAPAL_CALLBACK_URL=https://your-frontend.vercel.app/payment/callback/
PESAPAL_IPN_URL=https://affordable-gadgets-backend.onrender.com/api/inventory/pesapal/ipn/
```

### How to Check:
1. Go to Render Dashboard
2. Select your backend service
3. Go to "Environment" tab
4. Verify all variables are set

## Step 3: Test Order Retrieval

Verify the order can be retrieved:

```bash
curl -X GET \
  https://affordable-gadgets-backend.onrender.com/api/inventory/orders/8c72b167-fdcc-4d04-8957-5030a3708c19/ \
  -H "Content-Type: application/json"
```

**Expected:** Order details returned (200 OK)
**If 404:** Order doesn't exist or lookup is failing

## Step 4: Test Payment Initiation Directly

Try calling the payment initiation endpoint directly:

```bash
curl -X POST \
  https://affordable-gadgets-backend.onrender.com/api/inventory/orders/8c72b167-fdcc-4d04-8957-5030a3708c19/initiate_payment/ \
  -H "Content-Type: application/json" \
  -d '{
    "callback_url": "https://your-frontend.vercel.app/payment/callback/"
  }'
```

**Expected:** 
```json
{
  "success": true,
  "redirect_url": "https://pay.pesapal.com/...",
  "order_tracking_id": "...",
  "payment_id": "..."
}
```

**If Error:** Check the response body for the specific error message.

## Common Issues & Solutions

### Issue 1: "PESAPAL_IPN_URL not configured"
**Solution:** Set `PESAPAL_IPN_URL` in Render environment variables

### Issue 2: "Order is already {status}"
**Solution:** Order must be in `PENDING` status. Check order status:
```bash
curl https://affordable-gadgets-backend.onrender.com/api/inventory/orders/8c72b167-fdcc-4d04-8957-5030a3708c19/
```

### Issue 3: "callback_url is required"
**Solution:** Frontend must send `callback_url` in request body

### Issue 4: "Authentication failed"
**Solution:** 
- Verify `PESAPAL_CONSUMER_KEY` and `PESAPAL_CONSUMER_SECRET` are correct
- Check if credentials are for the correct environment (sandbox vs live)

### Issue 5: "Order not found"
**Solution:**
- Verify order exists: `GET /api/inventory/orders/{order_id}/`
- Check if `get_object()` is working correctly
- Verify `lookup_field='order_id'` is set correctly

### Issue 6: TypeError (unexpected keyword argument)
**Solution:** Code fix is already applied (`**kwargs` in method signature). If still happening:
- Verify code is deployed to Render
- Check if Render is using cached code
- Force redeploy

## Code Status

✅ **Fixed Issues:**
- `**kwargs` added to `initiate_payment()` method signature
- `log_path` defined in `create()` method
- Error handling improved with detailed logging

## Next Steps

1. **Check Render Logs** - Find the exact error message
2. **Verify Configuration** - Ensure all Pesapal env vars are set
3. **Test Order Retrieval** - Verify order can be found
4. **Test Payment Initiation** - Try direct API call
5. **Share Error Details** - Once you have the exact error from logs, we can fix it

## How to Get Detailed Logs

1. Go to Render Dashboard
2. Select your backend service
3. Click "Logs" tab
4. Filter by `[PESAPAL]` to see payment-related logs
5. Look for the error message and traceback

The logs will show exactly where the failure is occurring and why.

