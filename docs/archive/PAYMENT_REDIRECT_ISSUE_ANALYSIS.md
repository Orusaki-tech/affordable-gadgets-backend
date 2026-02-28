# Payment Redirect Issue - Analysis & Solution

## Problem Identified

Based on the console logs showing payment stuck in "PENDING" status with continuous polling, the issue is:

**The frontend is NOT redirecting users to Pesapal's payment page after payment initiation.**

## Root Cause

1. ✅ Backend correctly returns `redirect_url` in the payment initiation response
2. ❌ Frontend is NOT using the `redirect_url` to redirect the user
3. ❌ Frontend is polling payment status without the user ever completing payment on Pesapal
4. ❌ Payment stays "PENDING" forever because user never visits Pesapal payment page

## Evidence from Console Logs

From the browser console:
- Payment status shows: `"status": "PENDING"`
- Frontend is polling: `"will poll again in 3 seconds"`
- `redirect_url` is present: `"redirect_url": "https://pay.pesapal.com/iframe/PesapalIframe3/Index?OrderTrackingId=..."`
- But user is on callback page, not on Pesapal payment page

## Solution Implemented

### Backend Changes (✅ Completed)

1. **Enhanced `get_payment_status` method** to query Pesapal API directly when status is PENDING
   - Now queries Pesapal API for real-time status
   - Updates local database with latest status
   - Prevents infinite "PENDING" loops

2. **Added logging** to track redirect_url in API responses

3. **Created documentation** (`FRONTEND_PAYMENT_INTEGRATION.md`) with:
   - Complete payment flow examples
   - Code samples for React/Next.js
   - Best practices
   - Common issues and solutions

### Frontend Changes Required (⚠️ Action Needed)

The frontend MUST be updated to:

1. **Redirect user immediately after payment initiation:**
   ```javascript
   // After calling initiate_payment API
   if (response.success && response.redirect_url) {
     window.location.href = response.redirect_url; // ⚠️ CRITICAL
   }
   ```

2. **Only poll status on callback page** (after user returns from Pesapal)

3. **Handle all payment statuses** (COMPLETED, FAILED, CANCELLED, PENDING)

## Current Payment Flow (Broken)

```
User clicks "Pay Now"
  ↓
Frontend calls initiate_payment API
  ↓
Backend returns redirect_url
  ↓
❌ Frontend DOES NOT redirect (BUG)
  ↓
Frontend shows "Processing Payment" page
  ↓
Frontend starts polling payment status
  ↓
Status stays "PENDING" forever (user never paid)
```

## Correct Payment Flow (Fixed)

```
User clicks "Pay Now"
  ↓
Frontend calls initiate_payment API
  ↓
Backend returns redirect_url
  ↓
✅ Frontend redirects to redirect_url (Pesapal payment page)
  ↓
User completes payment on Pesapal
  ↓
Pesapal redirects back to callback_url
  ↓
Frontend shows "Processing Payment" page
  ↓
Frontend polls payment status
  ↓
Status updates to "COMPLETED" (backend queries Pesapal API)
  ↓
Frontend shows success page
```

## Files to Check in Frontend

Look for these files in your frontend repository:

1. **Payment initiation component:**
   - `components/PaymentForm.jsx` or similar
   - `pages/checkout.jsx` or similar
   - Any file that calls `/api/inventory/orders/{id}/initiate_payment/`

2. **Payment callback page:**
   - `pages/payment/callback.jsx` or similar
   - Any file that handles the callback URL

3. **Payment status polling:**
   - Look for `setInterval` or polling logic
   - Should only run on callback page, not on checkout page

## Quick Fix for Frontend

Find where you call the `initiate_payment` endpoint and add:

```javascript
// BEFORE (WRONG):
const response = await initiatePayment(orderId);
// Shows "Processing Payment" page
// Starts polling
// ❌ User never goes to Pesapal

// AFTER (CORRECT):
const response = await initiatePayment(orderId);
if (response.success && response.redirect_url) {
  // ✅ Redirect immediately to Pesapal payment page
  window.location.href = response.redirect_url;
} else {
  // Handle error
  showError(response.error);
}
```

## Testing Checklist

After fixing the frontend:

- [ ] User clicks "Pay Now" → Redirects to Pesapal payment page
- [ ] User completes payment on Pesapal → Returns to callback page
- [ ] Callback page shows "Processing Payment" → Polls status
- [ ] Status updates to "COMPLETED" → Shows success page
- [ ] Order status updates to "PAID" in database
- [ ] Receipt is generated and sent

## Additional Notes

- The backend now queries Pesapal API directly, so status will update even if IPN is delayed
- Payment will complete as soon as user pays on Pesapal (no need to wait for IPN)
- Polling should stop after 5 minutes to avoid infinite loops
- Handle all statuses: COMPLETED, FAILED, CANCELLED, PENDING

## Related Files

- `FRONTEND_PAYMENT_INTEGRATION.md` - Complete integration guide
- `inventory/services/pesapal_payment_service.py` - Backend payment service (updated)
- `inventory/views.py` - API views (updated with logging)

