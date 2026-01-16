#!/usr/bin/env python3
"""
Check the inventory API to see what banner_image.name contains.
This requires authentication, so we'll just check the public API structure.
"""
import urllib.request
import urllib.error
import ssl
import json

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def check_api():
    """Check both public and try to understand the structure."""
    print("=" * 80)
    print("CHECKING API RESPONSES")
    print("=" * 80)
    
    # Check public API
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"
    
    print(f"\n📡 Public API: {url}")
    
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
                    banner_image_url = promotion.get('banner_image_url')
                    
                    print(f"\n   banner_image: {banner_image}")
                    print(f"   banner_image_url: {banner_image_url}")
                    
                    # Check if it has .auto extension
                    if banner_image and '.auto' in banner_image:
                        print(f"\n   ⚠️  URL has '.auto' extension - this might be a transformation issue")
                    
                    # Check if it has media/ prefix
                    if banner_image and 'media/' in banner_image:
                        print(f"   ✅ URL has 'media/' prefix")
                    else:
                        print(f"   ❌ URL missing 'media/' prefix")
                    
                    # Try to find the actual file
                    print(f"\n   🔍 Testing if file exists with different paths...")
                    
                    # Extract base path
                    if banner_image:
                        # Try removing .auto
                        test_url = banner_image.replace('.auto', '')
                        test_urls = [
                            (test_url, "Without .auto extension"),
                            (test_url.replace('/v1/promotions/', '/v1/media/promotions/'), "With media/ prefix"),
                            (test_url.replace('/v1/promotions/', '/media/promotions/'), "With media/, no version"),
                        ]
                        
                        for url_to_test, desc in test_urls:
                            try:
                                req_test = urllib.request.Request(url_to_test, method='HEAD')
                                with urllib.request.urlopen(req_test, timeout=5, context=ssl_context) as resp:
                                    if resp.getcode() == 200:
                                        print(f"      ✅ {desc}: {url_to_test}")
                                        break
                            except:
                                pass
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_api()
