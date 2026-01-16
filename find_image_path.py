#!/usr/bin/env python3
"""
Find where the newly uploaded image actually is in Cloudinary.
"""
import urllib.request
import urllib.error
import ssl

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

base_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload"
public_id = "media/promotions/2026/01/iphone14promaxxx"
transformations = "c_fill,h_1920,q_auto,w_1080"

# Test all possible combinations
test_urls = [
    # With version v1
    (f"{base_url}/{transformations}/v1/{public_id}.png", "With v1 and .png"),
    (f"{base_url}/{transformations}/v1/{public_id}", "With v1, no extension"),
    (f"{base_url}/v1/{public_id}.png", "With v1, no transformations, .png"),
    (f"{base_url}/v1/{public_id}", "With v1, no transformations, no extension"),
    
    # Without version
    (f"{base_url}/{transformations}/{public_id}.png", "No version, with .png"),
    (f"{base_url}/{transformations}/{public_id}", "No version, no extension"),
    (f"{base_url}/{public_id}.png", "No version, no transformations, .png"),
    (f"{base_url}/{public_id}", "No version, no transformations, no extension"),
    
    # Try different extensions
    (f"{base_url}/{transformations}/v1/{public_id}.jpg", "With v1 and .jpg"),
    (f"{base_url}/{transformations}/v1/{public_id}.jpeg", "With v1 and .jpeg"),
    (f"{base_url}/{transformations}/v1/{public_id}.webp", "With v1 and .webp"),
    
    # Try auto format
    (f"{base_url}/{transformations}/v1/{public_id}.auto", "With v1 and .auto"),
]

print("=" * 80)
print("FINDING IMAGE PATH IN CLOUDINARY")
print("=" * 80)
print(f"\nBase public_id: {public_id}\n")

found = False
for url, description in test_urls:
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            status = response.getcode()
            if status == 200:
                content_type = response.headers.get('Content-Type', 'unknown')
                print(f"✅ FOUND! {description}")
                print(f"   URL: {url}")
                print(f"   Status: {status}")
                print(f"   Content-Type: {content_type}")
                print()
                found = True
                break
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"⚠️  {description}: HTTP {e.code}")
    except Exception as e:
        pass

if not found:
    print("❌ Image not found at any of the tested paths")
    print("\n💡 Possible issues:")
    print("   1. The file might not have been uploaded successfully")
    print("   2. The filename might be different (check Cloudinary dashboard)")
    print("   3. The file might be in a different folder")
    print("\n📋 Check Render logs for upload errors:")
    print("   Look for: 'DEBUG: Banner image after save - URL: ..., Name: ...'")

print("\n" + "=" * 80)
