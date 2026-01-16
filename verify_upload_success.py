#!/usr/bin/env python3
"""
Verify if the upload was successful by checking the API response and Cloudinary.
"""
import urllib.request
import urllib.error
import ssl
import json

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def check_promotion():
    """Check promotion 2 to see if image was uploaded successfully."""
    print("=" * 80)
    print("VERIFYING UPLOAD SUCCESS")
    print("=" * 80)
    
    # Check public promotions API
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"
    
    print(f"\n📡 Checking promotions API...")
    
    try:
        req = urllib.request.Request(url)
        req.add_header('X-Brand-Code', 'AFFORDABLE_GADGETS')
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                
                if 'results' in data and len(data['results']) > 0:
                    print(f"\n✅ Found {len(data['results'])} promotions")
                    
                    for promotion in data['results']:
                        if promotion.get('id') == 2:
                            print(f"\n📋 Promotion 2 Details:")
                            print(f"   ID: {promotion.get('id')}")
                            print(f"   Title: {promotion.get('title')}")
                            
                            banner_image = promotion.get('banner_image')
                            banner_image_url = promotion.get('banner_image_url')
                            
                            image_url = banner_image or banner_image_url
                            
                            if image_url:
                                print(f"\n🖼️  Banner Image URL:")
                                print(f"   {image_url}")
                                
                                # Check if it's Cloudinary
                                if 'cloudinary.com' in image_url:
                                    print(f"   ✅ URL is Cloudinary URL")
                                    
                                    # Test if accessible
                                    try:
                                        img_req = urllib.request.Request(image_url, method='HEAD')
                                        with urllib.request.urlopen(img_req, timeout=5, context=ssl_context) as img_response:
                                            status = img_response.getcode()
                                            if status == 200:
                                                print(f"   ✅ Image is accessible! (Status: {status})")
                                                print(f"   ✅ UPLOAD SUCCESSFUL!")
                                                print(f"\n🎉 The image is now in Cloudinary and accessible!")
                                                return True
                                            else:
                                                print(f"   ⚠️  Image returned status: {status}")
                                    except urllib.error.HTTPError as e:
                                        if e.code == 404:
                                            print(f"   ❌ Image not found in Cloudinary (404)")
                                            print(f"   ❌ Upload might have failed")
                                        else:
                                            print(f"   ❌ Image error: HTTP {e.code}")
                                    except Exception as e:
                                        print(f"   ⚠️  Error checking image: {e}")
                                else:
                                    print(f"   ❌ URL is NOT Cloudinary URL")
                                    print(f"   ❌ Still using local storage")
                            else:
                                print(f"   ❌ No banner image URL")
                else:
                    print(f"\n⚠️  No promotions found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return False

if __name__ == "__main__":
    success = check_promotion()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ UPLOAD VERIFIED: Image is in Cloudinary and accessible!")
    else:
        print("⚠️  Could not verify upload - check Cloudinary dashboard manually")
    print("=" * 80)
