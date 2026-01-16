#!/usr/bin/env python3
"""
Test the inventory API to check if images exist in the database.
"""
import urllib.request
import urllib.error
import ssl
import json

# Create SSL context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def test_endpoint(url):
    """Test an API endpoint."""
    try:
        print(f"\n🔍 Testing: {url}")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data
            else:
                print(f"   Status: {response.getcode()}")
                return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

# Test images endpoint
print("🚀 Testing Inventory API - Images")
print("=" * 80)

# Test product images
images_data = test_endpoint(f"{BACKEND_URL}/api/inventory/images/?page_size=5")
if images_data:
    print(f"\n📸 Product Images Found: {images_data.get('count', 0)}")
    if 'results' in images_data and images_data['results']:
        print("\nFirst few images:")
        for img in images_data['results'][:3]:
            print(f"  - ID: {img.get('id')}, Product: {img.get('product')}, URL: {img.get('image_url', 'N/A')[:80]}")

# Test products with images
products_data = test_endpoint(f"{BACKEND_URL}/api/inventory/products/?page_size=3")
if products_data:
    print(f"\n📦 Products in Inventory API: {products_data.get('count', 0)}")
    if 'results' in products_data and products_data['results']:
        first_product = products_data['results'][0]
        print(f"\nFirst Product Details:")
        print(f"  ID: {first_product.get('id')}")
        print(f"  Name: {first_product.get('product_name')}")
        if 'images' in first_product:
            images = first_product['images']
            print(f"  Images: {len(images) if isinstance(images, list) else 'N/A'}")
            if isinstance(images, list) and images:
                print(f"  First Image URL: {images[0].get('image_url', 'N/A')[:100]}")
        else:
            print("  Images field: Not present in response")
