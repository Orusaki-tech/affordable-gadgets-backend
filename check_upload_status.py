#!/usr/bin/env python3
"""
Check what the database actually has for banner_image.name after upload.
We'll check the public API and try to infer what might be wrong.
"""
import urllib.request
import urllib.error
import ssl
import json
import re

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def extract_public_id_from_url(url):
    """Extract public_id from Cloudinary URL."""
    # Format: https://res.cloudinary.com/cloud/image/upload/TRANS/v1/public_id.ext
    match = re.search(r'/upload/[^/]+/v1/(.+?)(?:\.\w+)?$', url)
    if match:
        return match.group(1)
    # Try without version
    match = re.search(r'/upload/[^/]+/(.+?)(?:\.\w+)?$', url)
    if match:
        return match.group(1)
    return None

def test_all_variations(public_id_base):
    """Test all possible variations of the public_id."""
    base_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload"
    transformations = "c_fill,h_1920,q_auto,w_1080"
    
    variations = [
        # With transformations and version
        f"{base_url}/{transformations}/v1/{public_id_base}",
        f"{base_url}/{transformations}/v1/{public_id_base}.png",
        f"{base_url}/{transformations}/v1/{public_id_base}.jpg",
        # Without version
        f"{base_url}/{transformations}/{public_id_base}",
        f"{base_url}/{transformations}/{public_id_base}.png",
        # Without transformations
        f"{base_url}/v1/{public_id_base}",
        f"{base_url}/v1/{public_id_base}.png",
        f"{base_url}/{public_id_base}",
        f"{base_url}/{public_id_base}.png",
    ]
    
    for url in variations:
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                if response.getcode() == 200:
                    return url
        except:
            pass
    return None

def check_api():
    """Check the API and diagnose the issue."""
    print("=" * 80)
    print("DIAGNOSING IMAGE UPLOAD ISSUE")
    print("=" * 80)
    
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('X-Brand-Code', 'AFFORDABLE_GADGETS')
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                
                if 'results' in data and len(data['results']) > 0:
                    promotion = data['results'][0]
                    
                    print(f"\n📋 Promotion {promotion.get('id')}:")
                    print(f"   Title: {promotion.get('title')}")
                    
                    banner_image = promotion.get('banner_image')
                    
                    if banner_image:
                        print(f"\n🖼️  Banner Image URL from API:")
                        print(f"   {banner_image}")
                        
                        # Extract public_id
                        public_id = extract_public_id_from_url(banner_image)
                        if public_id:
                            print(f"\n   📊 Extracted Public ID: {public_id}")
                            
                            # Check if it has media/ prefix
                            if public_id.startswith('media/'):
                                print(f"   ✅ Has 'media/' prefix")
                            else:
                                print(f"   ❌ Missing 'media/' prefix")
                            
                            # Test if file exists
                            print(f"\n   🔍 Testing if file exists...")
                            found_url = test_all_variations(public_id)
                            
                            if found_url:
                                print(f"   ✅ Image found at: {found_url}")
                                print(f"\n   💡 The API URL is wrong, but the file exists!")
                                print(f"   💡 The correct URL should be: {found_url}")
                            else:
                                print(f"   ❌ Image not found at any variation")
                                print(f"\n   💡 Possible issues:")
                                print(f"      1. File upload failed silently")
                                print(f"      2. File is at a different path")
                                print(f"      3. Filename is different")
                                print(f"\n   📋 Check Render logs for:")
                                print(f"      'DEBUG: Banner image after save - URL: ..., Name: ...'")
                                print(f"      This will show what banner_image.name actually contains")
                    else:
                        print(f"\n   ❌ No banner image URL")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_api()
