#!/usr/bin/env python3
"""
Check if the promotion image was successfully uploaded to Cloudinary.
Tests the current API response and verifies image accessibility.
"""
import urllib.request
import urllib.error
import ssl
import json
import time

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

def test_image_url(url):
    """Test if image URL is accessible."""
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            return response.getcode() == 200, response.getcode()
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception as e:
        return False, str(e)

print("=" * 80)
print("CHECKING PROMOTION IMAGE AFTER UPLOAD")
print("=" * 80)
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print()

headers = {'X-Brand-Code': 'AFFORDABLE_GADGETS'}
data = test_endpoint(f"{BACKEND_URL}/api/v1/public/promotions/", headers=headers)

if data and 'results' in data and len(data['results']) > 0:
    promo = data['results'][0]
    print(f"✅ Promotion Found:")
    print(f"   ID: {promo.get('id')}")
    print(f"   Title: {promo.get('title')}")
    print()
    
    banner_url = promo.get('banner_image') or promo.get('banner_image_url')
    if banner_url:
        print(f"📸 Banner Image URL:")
        print(f"   {banner_url}")
        print()
        
        # Check if it's a Cloudinary URL
        if 'cloudinary.com' in banner_url:
            print("✅ Is Cloudinary URL")
            
            # Extract public_id for reference
            if '/upload/' in banner_url:
                parts = banner_url.split('/upload/')
                if len(parts) > 1:
                    after_upload = parts[1]
                    # Remove version and transformations
                    path_parts = after_upload.split('/')
                    if path_parts and path_parts[0].startswith('v') and path_parts[0][1:].isdigit():
                        path_parts = path_parts[1:]
                    # Get public_id (last part, remove extension)
                    if path_parts:
                        public_id_parts = path_parts[-1].split('.')
                        public_id = '/'.join(path_parts[:-1] + [public_id_parts[0]]) if len(path_parts) > 1 else public_id_parts[0]
                        print(f"   Public ID: {public_id}")
            
            print()
            print("🔍 Testing Image Accessibility...")
            is_accessible, status = test_image_url(banner_url)
            
            if is_accessible:
                print("   ✅ Image is ACCESSIBLE (200 OK)")
                print("   ✅ Image should display correctly!")
            else:
                print(f"   ❌ Image is NOT accessible (Status: {status})")
                print()
                print("   Possible issues:")
                print("   1. Image not uploaded to Cloudinary yet (wait a few seconds)")
                print("   2. Public ID mismatch (check Cloudinary dashboard)")
                print("   3. Image was deleted from Cloudinary")
                print("   4. Cloudinary credentials incorrect")
        else:
            print("⚠️  Not a Cloudinary URL")
            print("   Image might be stored locally instead of Cloudinary")
    else:
        print("❌ No banner image URL in response")
        print("   Image might not have been uploaded")
else:
    print("❌ No promotions found")

print()
print("=" * 80)
print("NEXT STEPS:")
print("=" * 80)
print("1. If image is accessible: ✅ Everything is working!")
print("2. If image is NOT accessible:")
print("   - Check Cloudinary dashboard for the 'promotions' folder")
print("   - Verify the image exists with the correct public_id")
print("   - Re-upload the image if it doesn't exist")
print("   - Wait a few seconds after upload for Cloudinary to process")
print("=" * 80)
