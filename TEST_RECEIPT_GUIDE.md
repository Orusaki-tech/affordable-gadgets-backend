# Receipt Testing Guide

## Quick Test Instructions

### Test Order ID
From your screenshot: `f970caff-54d6-4957-88f0-b450d2d01fb3`

### Method 1: Browser Test (Easiest)

1. **HTML Format** (View in browser):
   ```
   https://affordable-gadgets-backend.onrender.com/api/inventory/orders/f970caff-54d6-4957-88f0-b450d2d01fb3/receipt/?format=html
   ```
   - Should display receipt HTML in browser
   - Check for company name, order details, receipt number

2. **PDF Format** (Download):
   ```
   https://affordable-gadgets-backend.onrender.com/api/inventory/orders/f970caff-54d6-4957-88f0-b450d2d01fb3/receipt/?format=pdf
   ```
   - Should download PDF file
   - Open PDF to verify content

3. **From Frontend**:
   - Go to: `https://affordable-gadgets-frontend.vercel.app/orders/f970caff-54d6-4957-88f0-b450d2d01fb3`
   - Click "Download Receipt" button
   - Should open PDF in new tab

### Method 2: cURL Test

```bash
# Test HTML format
curl -I "https://affordable-gadgets-backend.onrender.com/api/inventory/orders/f970caff-54d6-4957-88f0-b450d2d01fb3/receipt/?format=html"

# Test PDF format (save to file)
curl -o receipt_test.pdf "https://affordable-gadgets-backend.onrender.com/api/inventory/orders/f970caff-54d6-4957-88f0-b450d2d01fb3/receipt/?format=pdf"

# Check response
curl -v "https://affordable-gadgets-backend.onrender.com/api/inventory/orders/f970caff-54d6-4957-88f0-b450d2d01fb3/receipt/?format=html" 2>&1 | head -30
```

### Method 3: Python Test Script

Run the test script (after activating virtual environment):

```bash
cd /Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend
source venv/bin/activate
python test_receipt.py f970caff-54d6-4957-88f0-b450d2d01fb3
```

Or use Django shell:

```bash
source venv/bin/activate
python manage.py shell
```

Then in the shell:
```python
from inventory.models import Order, Receipt
from inventory.services.receipt_service import ReceiptService
from uuid import UUID

order_id = UUID('f970caff-54d6-4957-88f0-b450d2d01fb3')
order = Order.objects.get(order_id=order_id)

# Test receipt number
receipt_num = ReceiptService.generate_receipt_number(order)
print(f"Receipt Number: {receipt_num}")

# Test HTML generation
html = ReceiptService.generate_receipt_html(order)
print(f"HTML Length: {len(html)}")

# Test PDF generation
pdf = ReceiptService.generate_receipt_pdf(order, html)
print(f"PDF Size: {len(pdf)} bytes")

# Create and save receipt
receipt = ReceiptService.create_and_save_receipt(order)
print(f"Receipt Created: {receipt.receipt_number}")
```

## Expected Results

### ✅ Success (200 OK)
- **HTML**: Displays receipt with:
  - Company name "AFFORDABLE GADGETS"
  - Receipt number (format: SL_XXXXXXXX)
  - Order details (items, amounts, customer info)
  - Payment method
  - Warranty information

- **PDF**: Downloads PDF file that:
  - Opens correctly in PDF viewer
  - Contains all order information
  - Has proper formatting

### ❌ Error Cases

#### 404 Not Found
```
{"detail": "Not found."}
```
**Possible causes:**
- Order doesn't exist in database
- Order ID format incorrect
- URL routing issue

**Solution:**
- Verify order exists: Check database or admin panel
- Check order ID format (should be UUID)

#### 403 Forbidden
```
{"error": "Receipt is only available for paid orders."}
```
**Possible causes:**
- Order status is not "Paid"
- Unauthenticated user trying to access unpaid order

**Solution:**
- Check order status
- Ensure order is marked as "Paid"

#### 500 Internal Server Error
```
{"error": "Failed to generate receipt"}
```
**Possible causes:**
- PDF generation failed (WeasyPrint issue)
- Missing dependencies
- Template rendering error

**Solution:**
- Check backend logs
- Verify WeasyPrint is installed
- Check receipt template exists

## Verification Checklist

- [ ] Receipt endpoint accessible (200 OK)
- [ ] HTML format displays correctly
- [ ] PDF format downloads correctly
- [ ] Receipt number is unique and formatted correctly (SL_XXXXXXXX)
- [ ] All order details are present:
  - [ ] Order ID
  - [ ] Customer name
  - [ ] Order items
  - [ ] Total amount
  - [ ] Payment method
  - [ ] Date
- [ ] No console errors in browser
- [ ] PDF opens correctly in PDF viewer
- [ ] Receipt can be downloaded from frontend

## Troubleshooting

### Issue: 404 Error
1. Check if order exists in database
2. Verify order ID is correct UUID format
3. Check backend logs for routing issues
4. Verify `get_object()` method is working

### Issue: PDF Generation Fails
1. Check if WeasyPrint is installed: `pip list | grep weasyprint`
2. Check backend logs for WeasyPrint errors
3. Verify receipt template exists: `inventory/templates/receipts/receipt.html`
4. Check file permissions for PDF storage

### Issue: Receipt Number Collision
1. Check if receipt number already exists
2. Verify uniqueness logic in `generate_receipt_number()`
3. Check database for duplicate receipt numbers

### Issue: CORS Errors
1. Verify CORS headers are set correctly
2. Check `CORS_ALLOWED_ORIGINS` includes frontend domain
3. Verify `idempotency-key` header is in allowed headers

## Test Results Template

```
Order ID: f970caff-54d6-4957-88f0-b450d2d01fb3
Test Date: [DATE]
Tester: [NAME]

HTML Format:
  Status Code: [200/404/500]
  Result: [PASS/FAIL]
  Notes: [Any issues]

PDF Format:
  Status Code: [200/404/500]
  Result: [PASS/FAIL]
  File Size: [BYTES]
  Notes: [Any issues]

Frontend Download:
  Result: [PASS/FAIL]
  Notes: [Any issues]

Console Errors:
  [List any errors]

Overall: [PASS/FAIL]
```

