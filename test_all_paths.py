#!/usr/bin/env python3
"""
Test all possible Cloudinary paths to find where the image actually is.
"""
import urllib.request
import urllib.error
import ssl

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

base_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload"
public_id_base = "promotions/2026/01/IPHONE14PROMAX"
media_public_id_base = "media/promotions/2026/01/IPHONE14PROMAX"

transformations = "c_fill,h_1920,q_auto,w_1080"

# Test all possible combinations
test_urls = [
    # Without media/ prefix
    (f"{base_url}/{transformations}/{public_id_base}", "Original (no media/, with transformations)"),
    (f"{base_url}/{public_id_base}", "No media/, no transformations"),
    (f"{base_url}/v1/{public_id_base}", "No media/, with version v1"),
    (f"{base_url}/{transformations}/v1/{public_id_base}", "No media/, with version and transformations"),
    
    # With media/ prefix
    (f"{base_url}/{transformations}/{media_public_id_base}", "With media/, with transformations"),
    (f"{base_url}/{media_public_id_base}", "With media/, no transformations"),
    (f"{base_url}/v1/{media_public_id_base}", "With media/, with version v1"),
    (f"{base_url}/{transformations}/v1/{media_public_id_base}", "With media/, with version and transformations"),
    
    # Try different filename variations
    (f"{base_url}/{transformations}/v1/media/promotions/2026/01/IPHONE14PROMAX.auto", "With .auto extension"),
    (f"{base_url}/{transformations}/v1/media/promotions/2026/01/IPHONE14PROMAX.jpg", "With .jpg extension"),
    (f"{base_url}/{transformations}/v1/media/promotions/2026/01/IPHONE14PROMAX.png", "With .png extension"),
    
    # Try lowercase
    (f"{base_url}/{transformations}/v1/media/promotions/2026/01/iphone14promax", "Lowercase filename"),
    (f"{base_url}/{transformations}/v1/media/promotions/2026/01/iphone14promaxxx_mxptk2", "Original filename"),
]

print("=" * 80)
print("TESTING ALL POSSIBLE CLOUDINARY PATHS")
print("=" * 80)
print(f"\nBase public_id: {public_id_base}")
print(f"With media/: {media_public_id_base}\n")

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
        pass  # Skip errors

if not found:
    print("❌ Image not found at any of the tested paths")
    print("\n💡 This suggests:")
    print("   1. The file might not have been uploaded successfully")
    print("   2. The file might be at a completely different path")
    print("   3. The filename might be different")
    print("\n📋 Next steps:")
    print("   1. Check Cloudinary dashboard manually")
    print("   2. Check Render logs for upload errors")
    print("   3. Re-upload the image after deploying the fix")

print("\n" + "=" * 80)
