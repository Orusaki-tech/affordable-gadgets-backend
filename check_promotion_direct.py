#!/usr/bin/env python3
"""
Check promotion directly by ID and verify image status.
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
            status = response.getcode()
            data = json.loads(response.read().decode('utf-8'))
            return status, data
    except urllib.error.HTTPError as e:
        try:
            error_data = json.loads(e.read().decode('utf-8'))
            return e.code, error_data
        except:
            return e.code, str(e.reason)
    except Exception as e:
        return None, str(e)

def test_image(url):
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            return response.getcode() == 200, response.getcode()
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception as e:
        return False, str(e)

print("=" * 80)
print("CHECKING PROMOTION #1 DIRECTLY")
print("=" * 80)

# Try with brand header
headers = {'X-Brand-Code': 'AFFORDABLE_GADGETS'}
status, data = test_endpoint(f"{BACKEND_URL}/api/v1/public/promotions/1/", headers=headers)

if status == 200:
    print("✅ Promotion found!")
    print(f"\nPromotion Details:")
    print(f"  ID: {data.get('id')}")
    print(f"  Title: {data.get('title')}")
    print(f"  Is Active: {data.get('is_currently_active')}")
    print(f"  Start Date: {data.get('start_date')}")
    print(f"  End Date: {data.get('end_date')}")
    
    banner_url = data.get('banner_image') or data.get('banner_image_url')
    if banner_url:
        print(f"\n📸 Banner Image:")
        print(f"  URL: {banner_url[:100]}...")
        
        if 'cloudinary.com' in banner_url:
            print("  ✅ Is Cloudinary URL")
            
            # Test accessibility
            print("\n🔍 Testing Image...")
            is_accessible, status_code = test_image(banner_url)
            
            if is_accessible:
                print(f"  ✅ Image is ACCESSIBLE (Status: {status_code})")
                print("  ✅ Image should display correctly!")
            else:
                print(f"  ❌ Image NOT accessible (Status: {status_code})")
                print("\n  This means:")
                print("  - Image doesn't exist in Cloudinary")
                print("  - Or public_id doesn't match")
                print("  - Check Cloudinary dashboard for 'promotions' folder")
        else:
            print("  ⚠️  Not a Cloudinary URL")
    else:
        print("\n❌ No banner image URL")
        print("  Image might not have been uploaded")
        
    print("\n" + json.dumps(data, indent=2)[:500])
    
elif status == 404:
    print("❌ Promotion not found (404)")
    print("  Promotion might not exist or is filtered out")
else:
    print(f"❌ Error: {status}")
    print(f"  Response: {data}")

print("\n" + "=" * 80)
