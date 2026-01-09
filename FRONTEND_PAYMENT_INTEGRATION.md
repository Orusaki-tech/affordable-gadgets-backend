# Frontend Payment Integration Guide

## Pesapal Payment Flow

This guide explains how the frontend should handle Pesapal payment initiation and status polling.

## Payment Initiation Flow

### 1. Initiate Payment API Call

**Endpoint:** `POST /api/inventory/orders/{order_id}/initiate_payment/`

**Request Body:**
```json
{
  "callback_url": "https://your-frontend.com/payment/callback",
  "cancellation_url": "https://your-frontend.com/payment/cancelled",
  "customer": {
    "email": "customer@example.com",
    "phone_number": "+254712345678",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "redirect_url": "https://pay.pesapal.com/iframe/PesapalIframe3/Index?OrderTrackingId=...",
  "order_tracking_id": "9327d83d-05e5-4df2-bbe0-dae01e6fb6a4",
  "payment_id": "123"
}
```

### 2. ⚠️ CRITICAL: Redirect User to Pesapal Payment Page

**The frontend MUST immediately redirect the user to the `redirect_url` when payment is initiated.**

```javascript
// Example: React/Next.js
const initiatePayment = async (orderId, customerData) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/inventory/orders/${orderId}/initiate_payment/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          callback_url: `${window.location.origin}/payment/callback`,
          cancellation_url: `${window.location.origin}/payment/cancelled`,
          customer: customerData,
        }),
      }
    );

    const data = await response.json();

    if (data.success && data.redirect_url) {
      // ⚠️ CRITICAL: Redirect immediately to Pesapal payment page
      window.location.href = data.redirect_url;
      // OR for iframe integration:
      // setPaymentIframeUrl(data.redirect_url);
    } else {
      // Handle error
      console.error('Payment initiation failed:', data.error);
      alert('Failed to initiate payment. Please try again.');
    }
  } catch (error) {
    console.error('Error initiating payment:', error);
    alert('An error occurred. Please try again.');
  }
};
```

### 3. Payment Status Polling (After Redirect)

**Only poll if the user is on the callback page waiting for payment completion.**

**Endpoint:** `GET /api/inventory/orders/{order_id}/payment_status/`

**Response:**
```json
{
  "status": "PENDING" | "COMPLETED" | "FAILED" | "CANCELLED",
  "order_tracking_id": "9327d83d-05e5-4df2-bbe0-dae01e6fb6a4",
  "payment_id": "123",
  "payment_reference": "ABC123",
  "amount": "10.00",
  "currency": "KES",
  "payment_method": "MPESA",
  "redirect_url": "https://pay.pesapal.com/...",
  "initiated_at": "2026-01-08T19:14:36.398953Z",
  "completed_at": null,
  "is_verified": false,
  "ipn_received": false
}
```

**Polling Implementation:**

```javascript
// Example: React Hook for Payment Status Polling
const usePaymentStatus = (orderId, orderTrackingId) => {
  const [status, setStatus] = useState('PENDING');
  const [isPolling, setIsPolling] = useState(true);

  useEffect(() => {
    if (!isPolling || !orderId) return;

    const pollStatus = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/inventory/orders/${orderId}/payment_status/`
        );
        const data = await response.json();

        setStatus(data.status);

        // Stop polling if payment is completed or failed
        if (
          data.status === 'COMPLETED' ||
          data.status === 'FAILED' ||
          data.status === 'CANCELLED'
        ) {
          setIsPolling(false);

          if (data.status === 'COMPLETED') {
            // Redirect to success page
            window.location.href = '/payment/success';
          } else if (data.status === 'FAILED') {
            // Show error message
            alert('Payment failed. Please try again.');
          } else if (data.status === 'CANCELLED') {
            // Redirect to cancelled page
            window.location.href = '/payment/cancelled';
          }
        }
      } catch (error) {
        console.error('Error polling payment status:', error);
      }
    };

    // Poll immediately, then every 3 seconds
    pollStatus();
    const interval = setInterval(pollStatus, 3000);

    // Cleanup: Stop polling after 5 minutes (100 attempts)
    const timeout = setTimeout(() => {
      setIsPolling(false);
      clearInterval(interval);
    }, 5 * 60 * 1000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [orderId, orderTrackingId, isPolling]);

  return { status, isPolling, setIsPolling };
};
```

## Complete Payment Flow Example

```javascript
// 1. User clicks "Pay Now" button
const handlePayNow = async () => {
  // Create order first (if not already created)
  const order = await createOrder(cartItems);

  // Initiate payment
  const paymentResponse = await fetch(
    `${API_BASE_URL}/api/inventory/orders/${order.id}/initiate_payment/`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        callback_url: `${window.location.origin}/payment/callback?OrderTrackingId=${order.id}`,
        customer: {
          email: userEmail,
          phone_number: userPhone,
          first_name: userFirstName,
          last_name: userLastName,
        },
      }),
    }
  );

  const paymentData = await paymentResponse.json();

  if (paymentData.success && paymentData.redirect_url) {
    // ⚠️ CRITICAL: Redirect to Pesapal payment page
    window.location.href = paymentData.redirect_url;
  } else {
    alert('Failed to initiate payment: ' + (paymentData.error || 'Unknown error'));
  }
};

// 2. On callback page (after user returns from Pesapal)
const PaymentCallbackPage = () => {
  const { orderId } = useParams();
  const searchParams = new URLSearchParams(window.location.search);
  const orderTrackingId = searchParams.get('OrderTrackingId');

  const { status, isPolling } = usePaymentStatus(orderId, orderTrackingId);

  return (
    <div>
      {status === 'PENDING' && (
        <div>
          <Spinner />
          <p>Processing Payment...</p>
          <p>Payment is being processed...</p>
        </div>
      )}
      {status === 'COMPLETED' && (
        <div>
          <SuccessIcon />
          <p>Payment Successful!</p>
          <Link to="/orders">View Orders</Link>
        </div>
      )}
      {status === 'FAILED' && (
        <div>
          <ErrorIcon />
          <p>Payment Failed</p>
          <button onClick={() => window.location.href = '/cart'}>
            Try Again
          </button>
        </div>
      )}
    </div>
  );
};
```

## Common Issues and Solutions

### Issue 1: Payment Stuck in "PENDING" Status

**Problem:** Frontend is polling but payment never completes.

**Causes:**
1. ❌ User was never redirected to Pesapal payment page
2. ❌ User didn't complete payment on Pesapal
3. ❌ IPN callback not received (but this is now handled by API polling)

**Solution:**
- ✅ **Always redirect user to `redirect_url` immediately after payment initiation**
- ✅ The backend now queries Pesapal API directly, so status will update even without IPN

### Issue 2: User Returns to Callback Page But Payment Still Pending

**Solution:**
- This is normal! The callback page should show a "Processing Payment" message
- Poll the status endpoint every 3 seconds
- The backend will query Pesapal API to get real-time status
- Status will update automatically when payment is completed

### Issue 3: Payment Completed But Order Not Updated

**Solution:**
- The backend automatically updates order status when payment is completed
- If using IPN, the backend verifies the payment before marking as paid
- Check backend logs if order status doesn't update

## Best Practices

1. ✅ **Always redirect to `redirect_url` immediately** - Don't wait, don't show intermediate pages
2. ✅ **Only poll on callback page** - Don't poll on the checkout page
3. ✅ **Set polling timeout** - Stop polling after 5 minutes to avoid infinite loops
4. ✅ **Handle all statuses** - COMPLETED, FAILED, CANCELLED, PENDING
5. ✅ **Show user feedback** - Loading spinner, success message, error message
6. ✅ **Store order ID in URL** - Makes it easy to poll status on callback page

## Testing

### Test Payment Flow:

1. Create a test order
2. Initiate payment - verify `redirect_url` is returned
3. **Verify redirect happens** - User should be sent to Pesapal
4. Complete payment on Pesapal (or cancel)
5. Return to callback page
6. Verify status polling works
7. Verify status updates correctly

### Test Scenarios:

- ✅ Payment completed successfully
- ✅ Payment cancelled by user
- ✅ Payment failed (insufficient funds, etc.)
- ✅ Payment timeout/expired
- ✅ Network errors during polling
- ✅ User closes browser during payment

## API Response Examples

### Successful Payment Initiation:
```json
{
  "success": true,
  "redirect_url": "https://pay.pesapal.com/iframe/PesapalIframe3/Index?OrderTrackingId=9327d83d-05e5-4df2-bbe0-dae01e6fb6a4",
  "order_tracking_id": "9327d83d-05e5-4df2-bbe0-dae01e6fb6a4",
  "payment_id": "123"
}
```

### Payment Status (Pending):
```json
{
  "status": "PENDING",
  "order_tracking_id": "9327d83d-05e5-4df2-bbe0-dae01e6fb6a4",
  "payment_id": null,
  "payment_reference": null,
  "amount": "10.00",
  "currency": "KES",
  "payment_method": null,
  "redirect_url": "https://pay.pesapal.com/...",
  "initiated_at": "2026-01-08T19:14:36.398953Z",
  "completed_at": null,
  "is_verified": false,
  "ipn_received": false
}
```

### Payment Status (Completed):
```json
{
  "status": "COMPLETED",
  "order_tracking_id": "9327d83d-05e5-4df2-bbe0-dae01e6fb6a4",
  "payment_id": "PAY123",
  "payment_reference": "REF456",
  "amount": "10.00",
  "currency": "KES",
  "payment_method": "MPESA",
  "redirect_url": "https://pay.pesapal.com/...",
  "initiated_at": "2026-01-08T19:14:36.398953Z",
  "completed_at": "2026-01-08T19:15:42.123456Z",
  "is_verified": true,
  "ipn_received": true
}
```
