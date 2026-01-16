#!/usr/bin/env python3
"""
Check what URL the API is actually returning for the promotion image.
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
    """Check what URL the API returns."""
    print("=" * 80)
    print("CHECKING API RESPONSE")
    print("=" * 80)
    
    # Check public API
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('X-Brand-Code', 'AFFORDABLE_GADGETS')
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                
                print(f"\n📋 Full API Response:")
                print(json.dumps(data, indent=2))
                
                if 'results' in data and len(data['results']) > 0:
                    for promotion in data['results']:
                        print(f"\n--- Promotion {promotion.get('id')} ---")
                        print(f"Title: {promotion.get('title')}")
                        print(f"Banner Image: {promotion.get('banner_image')}")
                        print(f"Banner Image URL: {promotion.get('banner_image_url')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_api()
