#!/usr/bin/env python3
"""
Quick check of promotion API response to see current image URLs.
"""
import urllib.request
import urllib.error
import ssl
import json

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def test_endpoint(url, headers=None):
    try:
        req = urllib.request.Request(url)
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error: {e}")
    return None

print("Checking Promotion API Response...")
print("=" * 80)

# Test public API
headers = {'X-Brand-Code': 'AFFORDABLE_GADGETS'}
data = test_endpoint(f"{BACKEND_URL}/api/v1/public/promotions/", headers=headers)

if data and 'results' in data and len(data['results']) > 0:
    promo = data['results'][0]
    print(f"\nPromotion ID: {promo.get('id')}")
    print(f"Title: {promo.get('title')}")
    print(f"\nBanner Image URL:")
    banner_url = promo.get('banner_image') or promo.get('banner_image_url')
    if banner_url:
        print(f"  {banner_url}")
        if 'cloudinary.com' in banner_url:
            print("  ✅ Is Cloudinary URL")
            # Test accessibility
            try:
                req = urllib.request.Request(banner_url, method='HEAD')
                with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                    if response.getcode() == 200:
                        print("  ✅ Image is accessible")
                    else:
                        print(f"  ❌ Image returned status: {response.getcode()}")
            except Exception as e:
                print(f"  ❌ Image not accessible: {e}")
        else:
            print("  ⚠️  Not a Cloudinary URL")
    else:
        print("  ❌ No banner image URL")
    
    print("\nFull response (first 500 chars):")
    print(json.dumps(promo, indent=2)[:500])
else:
    print("No promotions found")
