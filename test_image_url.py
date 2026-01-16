#!/usr/bin/env python3
"""
Test if the Cloudinary image URL is actually accessible.
"""
import urllib.request
import urllib.error
import ssl
import json

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# The URL from the API response
image_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/v1/promotions/2026/01/IPHONE14PROMAX_uIgOYGR"

print("=" * 80)
print("TESTING CLOUDINARY IMAGE URL")
print("=" * 80)
print(f"\n📡 Testing URL: {image_url}")

# Test HEAD request
try:
    req = urllib.request.Request(image_url, method='HEAD')
    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
        status = response.getcode()
        print(f"\n✅ Image is accessible! Status: {status}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        print(f"   Content-Length: {response.headers.get('Content-Length', 'Unknown')} bytes")
except urllib.error.HTTPError as e:
    print(f"\n❌ Image NOT accessible! Status: {e.code}")
    if e.code == 404:
        print(f"   ❌ Image doesn't exist in Cloudinary!")
        print(f"   The URL is generated but the file was never uploaded")
        
        # Try without the /v1/ version
        print(f"\n🔍 Trying without /v1/ version...")
        url_without_version = image_url.replace('/v1/', '/')
        print(f"   URL: {url_without_version}")
        try:
            req2 = urllib.request.Request(url_without_version, method='HEAD')
            with urllib.request.urlopen(req2, timeout=10, context=ssl_context) as response2:
                print(f"   ✅ Image accessible without /v1/!")
                print(f"   The issue is the version parameter in the URL")
        except Exception as e2:
            print(f"   ❌ Still not accessible: {e2}")
    else:
        print(f"   Error: {e}")
except Exception as e:
    print(f"   Error: {e}")

# Extract public_id from URL
print(f"\n📋 URL Analysis:")
print(f"   Public ID (from URL): promotions/2026/01/IPHONE14PROMAX_uIgOYGR")
print(f"   Version: v1")
print(f"   Transformations: c_fill,h_1920,q_auto,w_1080")

print(f"\n💡 The URL structure suggests:")
print(f"   - File should be at: promotions/2026/01/IPHONE14PROMAX_uIgOYGR")
print(f"   - But it might not exist in Cloudinary")
print(f"   - Or the version parameter (/v1/) might be wrong")
