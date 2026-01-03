# M-Pesa Integration - Quick Start

## 🚀 Fast Setup (5 minutes)

### 1. Get M-Pesa Credentials

1. Go to [Safaricom Developer Portal](https://developer.safaricom.co.ke/)
2. Sign up/Login
3. Create an app (or use existing)
4. Copy your credentials:
   - Consumer Key
   - Consumer Secret
   - Passkey
   - Shortcode (use `174379` for sandbox)

### 2. Configure Environment

```bash
# Copy example file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

Add your credentials:
```bash
MPESA_CONSUMER_KEY=your_key_here
MPESA_CONSUMER_SECRET=your_secret_here
MPESA_PASSKEY=your_passkey_here
MPESA_SHORTCODE=174379
MPESA_CALLBACK_URL=https://yourdomain.com/api/inventory/mpesa/callback/
MPESA_ENVIRONMENT=sandbox
```

### 3. Run Setup Script

```bash
./setup_mpesa.sh
```

Or manually:
```bash
# Activate virtual environment
source venv/bin/activate

# Run migrations
python manage.py migrate
```

### 4. Set Up Callback URL (Local Development)

For local testing, use ngrok:

```bash
# Install ngrok (if not installed)
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Start Django server
python manage.py runserver

# In another terminal, start ngrok
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Update .env:
MPESA_CALLBACK_URL=https://abc123.ngrok.io/api/inventory/mpesa/callback/
```

### 5. Test Payment

#### Option A: Via API

```bash
# Get auth token first (login endpoint)
TOKEN="your_auth_token"

# Create an order first, then initiate payment
curl -X POST http://localhost:8000/api/inventory/orders/{order_id}/initiate_mpesa_payment/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "254708374149"}'
```

#### Option B: Via Django Admin

1. Go to `/admin/`
2. Navigate to Orders
3. Select an order
4. Use the payment initiation endpoint via API or custom admin action

#### Option C: Via Frontend

If you have a frontend, add a "Pay with M-Pesa" button that calls:
```
POST /api/inventory/orders/{order_id}/initiate_mpesa_payment/
Body: {"phone_number": "254712345678"}
```

### 6. Monitor Payments

```bash
# Check payment status
curl http://localhost:8000/api/inventory/orders/{order_id}/payment_status/ \
  -H "Authorization: Token $TOKEN"

# View analytics
curl http://localhost:8000/api/inventory/analytics/payments/ \
  -H "Authorization: Token $TOKEN"

# Run verification (handles missed callbacks, timeouts, etc.)
python manage.py verify_pending_payments
```

## 📋 Common Commands

```bash
# Verify pending payments (run every 5 minutes)
python manage.py verify_pending_payments

# Check payment status in Django shell
python manage.py shell
>>> from inventory.models import MpesaPayment
>>> MpesaPayment.objects.filter(status='INITIATED').count()
>>> MpesaPayment.objects.filter(status='COMPLETED').count()
```

## 🔧 Troubleshooting

### "Invalid phone number"
- Format: `2547XXXXXXXX` (12 digits total)
- Remove spaces, dashes, plus signs

### "API downtime"
- Check credentials in `.env`
- Verify you're using sandbox credentials for testing
- Check M-Pesa API status

### "Callback not received"
- Ensure callback URL is publicly accessible (use ngrok for local)
- Must be HTTPS in production
- Run `verify_pending_payments` to query status

### Payment stuck in "INITIATED"
- Run: `python manage.py verify_pending_payments`
- Check if customer completed payment on phone
- Check callback URL is working

## 📚 Full Documentation

See `MPESA_SETUP_GUIDE.md` for detailed setup instructions.

## 🎯 Next Steps

1. ✅ Set up credentials
2. ✅ Run migrations
3. ✅ Configure callback URL
4. ✅ Test payment initiation
5. ⏭️ Set up automated verification (cron or Celery)
6. ⏭️ Configure SMS provider (optional)
7. ⏭️ Test all failover scenarios
8. ⏭️ Go to production when ready








