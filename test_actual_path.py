#!/usr/bin/env python3
"""
Test the actual path where the image is stored in Cloudinary.
"""
import urllib.request
import urllib.error
import ssl

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# The API returns this URL (without media/)
api_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/v1/promotions/2026/01/iphone14promaxxx_mxptk2"

# But the file is actually at media/promotions/... (with media/)
actual_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/v1/media/promotions/2026/01/iphone14promaxxx_mxptk2"

# Also try without version
actual_url_no_version = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/media/promotions/2026/01/iphone14promaxxx_mxptk2"

print("=" * 80)
print("TESTING ACTUAL CLOUDINARY PATHS")
print("=" * 80)

urls_to_test = [
    ("API URL (without media/)", api_url),
    ("With media/ prefix", actual_url),
    ("Without version, with media/", actual_url_no_version),
]

for name, url in urls_to_test:
    print(f"\n🔍 Testing: {name}")
    print(f"   {url}")
    
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            status = response.getcode()
            if status == 200:
                print(f"   ✅ Image is accessible! (Status: {status})")
                print(f"   ✅ THIS IS THE CORRECT URL!")
                break
            else:
                print(f"   ❌ Status: {status}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"   ❌ Image not found (404)")
        else:
            print(f"   ❌ Error: HTTP {e.code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 80)
