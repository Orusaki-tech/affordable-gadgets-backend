#!/usr/bin/env python
"""
Test script for receipt functionality.
Tests receipt generation for a given order ID.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
django.setup()

from inventory.models import Order, Receipt
from inventory.services.receipt_service import ReceiptService
from uuid import UUID

def test_receipt_generation(order_id_str):
    """Test receipt generation for a given order ID."""
    print(f"\n{'='*60}")
    print(f"Testing Receipt Generation")
    print(f"{'='*60}\n")
    
    try:
        # Convert string to UUID
        order_id = UUID(order_id_str)
        print(f"Order ID: {order_id}")
        
        # Check if order exists
        try:
            order = Order.objects.get(order_id=order_id)
            print(f"✅ Order found!")
            print(f"   Status: {order.status}")
            print(f"   Total Amount: Ksh {order.total_amount}")
            print(f"   Customer: {order.customer.name if order.customer else 'N/A'}")
            print(f"   Created: {order.created_at}")
        except Order.DoesNotExist:
            print(f"❌ Order not found in database!")
            print(f"   Order ID: {order_id_str}")
            return False
        
        # Test receipt number generation
        print(f"\n{'─'*60}")
        print("Testing Receipt Number Generation")
        print(f"{'─'*60}")
        receipt_number = ReceiptService.generate_receipt_number(order)
        print(f"✅ Receipt Number Generated: {receipt_number}")
        
        # Check if receipt already exists
        try:
            existing_receipt = Receipt.objects.get(order=order)
            print(f"ℹ️  Receipt already exists:")
            print(f"   Receipt Number: {existing_receipt.receipt_number}")
            print(f"   Generated At: {existing_receipt.generated_at}")
            print(f"   Email Sent: {existing_receipt.email_sent}")
            print(f"   WhatsApp Sent: {existing_receipt.whatsapp_sent}")
        except Receipt.DoesNotExist:
            print(f"ℹ️  No existing receipt found")
        
        # Test HTML generation
        print(f"\n{'─'*60}")
        print("Testing HTML Receipt Generation")
        print(f"{'─'*60}")
        try:
            html_content = ReceiptService.generate_receipt_html(order)
            html_length = len(html_content)
            print(f"✅ HTML Receipt Generated: {html_length} characters")
            if 'AFFORDABLE GADGETS' in html_content:
                print(f"✅ Contains company name")
            if receipt_number in html_content:
                print(f"✅ Contains receipt number")
            if str(order.total_amount) in html_content:
                print(f"✅ Contains order amount")
        except Exception as e:
            print(f"❌ HTML Generation Failed: {e}")
            return False
        
        # Test PDF generation
        print(f"\n{'─'*60}")
        print("Testing PDF Receipt Generation")
        print(f"{'─'*60}")
        try:
            pdf_bytes = ReceiptService.generate_receipt_pdf(order, html_content)
            pdf_size = len(pdf_bytes)
            print(f"✅ PDF Receipt Generated: {pdf_size} bytes ({pdf_size/1024:.2f} KB)")
            if pdf_size > 0:
                print(f"✅ PDF is not empty")
        except Exception as e:
            print(f"❌ PDF Generation Failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test receipt creation and saving
        print(f"\n{'─'*60}")
        print("Testing Receipt Creation and Saving")
        print(f"{'─'*60}")
        try:
            receipt = ReceiptService.create_and_save_receipt(order)
            print(f"✅ Receipt Created/Saved:")
            print(f"   Receipt Number: {receipt.receipt_number}")
            print(f"   PDF File: {receipt.pdf_file.name if receipt.pdf_file else 'Not saved'}")
            if receipt.pdf_file:
                file_exists = os.path.exists(receipt.pdf_file.path) if receipt.pdf_file else False
                print(f"   File Exists: {file_exists}")
        except Exception as e:
            print(f"❌ Receipt Creation Failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print(f"\n{'='*60}")
        print("✅ ALL TESTS PASSED!")
        print(f"{'='*60}\n")
        return True
        
    except ValueError as e:
        print(f"❌ Invalid Order ID format: {order_id_str}")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_receipt_endpoint_url(order_id_str):
    """Display the receipt endpoint URL for testing."""
    print(f"\n{'='*60}")
    print("Receipt Endpoint URLs")
    print(f"{'='*60}\n")
    
    base_url = "https://affordable-gadgets-backend.onrender.com"
    html_url = f"{base_url}/api/inventory/orders/{order_id_str}/receipt/?format=html"
    pdf_url = f"{base_url}/api/inventory/orders/{order_id_str}/receipt/?format=pdf"
    
    print(f"HTML Format:")
    print(f"  {html_url}\n")
    print(f"PDF Format:")
    print(f"  {pdf_url}\n")
    print(f"Test in browser or with curl:")
    print(f"  curl -I \"{html_url}\"")
    print(f"  curl -o receipt.pdf \"{pdf_url}\"\n")

if __name__ == '__main__':
    # Test with order ID from screenshot
    test_order_id = "f970caff-54d6-4957-88f0-b450d2d01fb3"
    
    if len(sys.argv) > 1:
        test_order_id = sys.argv[1]
    
    print(f"\n🧪 Receipt Functionality Test")
    print(f"Testing with Order ID: {test_order_id}\n")
    
    # Run tests
    success = test_receipt_generation(test_order_id)
    
    # Show endpoint URLs
    test_receipt_endpoint_url(test_order_id)
    
    sys.exit(0 if success else 1)

