#!/usr/bin/env python3
"""
Test if the image exists with the correct path (without media/ prefix).
"""
import urllib.request
import urllib.error
import ssl

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Current URL (with media/ prefix)
current_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/v1/media/promotions/2026/01/iphone14promaxxx_mxptk2.auto"

# Try without media/ prefix
correct_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/promotions/2026/01/iphone14promaxxx_mxptk2"

# Try without version too
correct_url_no_version = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/promotions/2026/01/iphone14promaxxx_mxptk2"

print("=" * 80)
print("TESTING CORRECT PATHS")
print("=" * 80)

urls_to_test = [
    ("Current (with media/)", current_url),
    ("Without media/ prefix", correct_url),
    ("Without version and media/", correct_url_no_version),
]

for name, url in urls_to_test:
    print(f"\n🔍 Testing: {name}")
    print(f"   URL: {url}")
    
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            status = response.getcode()
            if status == 200:
                print(f"   ✅ Image is accessible! (Status: {status})")
                print(f"   ✅ This is the correct path!")
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
print("CONCLUSION")
print("=" * 80)
print("\nIf none of the URLs work, the image might not have been uploaded.")
print("Check Cloudinary dashboard to see if the file exists.")
print("=" * 80)
