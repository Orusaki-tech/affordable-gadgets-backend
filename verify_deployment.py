#!/usr/bin/env python3
"""
Verify that the Cloudinary fix is deployed and working.
"""
import urllib.request
import urllib.error
import ssl
import json

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def check_promotion_api():
    """Check the promotion API to see if images are being returned correctly."""
    print("=" * 80)
    print("VERIFYING DEPLOYMENT - CHECKING PROMOTION API")
    print("=" * 80)
    
    # Check inventory promotions API (requires auth, but we can check structure)
    # First check if we can access the endpoint
    url = f"{BACKEND_URL}/api/inventory/promotions/1/"
    
    print(f"\n📡 Checking promotion endpoint...")
    print(f"   URL: {url}")
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            status = response.getcode()
            if status == 401:
                print("   ✅ Endpoint exists (requires authentication)")
                print("   This is expected")
            else:
                print(f"   Status: {status}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("   ✅ Endpoint exists (requires authentication)")
            print("   This is expected")
        elif e.code == 404:
            print("   ⚠️  Promotion not found (404)")
        else:
            print(f"   Status: {e.code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Check public promotions
    print(f"\n📡 Checking public promotions API...")
    public_url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"
    
    try:
        req = urllib.request.Request(public_url)
        req.add_header('X-Brand-Code', 'AFFORDABLE_GADGETS')
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                print(f"   ✅ API responded")
                
                if 'results' in data and len(data['results']) > 0:
                    promotion = data['results'][0]
                    print(f"\n📋 Promotion Found:")
                    print(f"   ID: {promotion.get('id')}")
                    print(f"   Title: {promotion.get('title')}")
                    
                    banner_image = promotion.get('banner_image')
                    banner_image_url = promotion.get('banner_image_url')
                    
                    print(f"\n🖼️  Image URLs:")
                    print(f"   banner_image: {banner_image}")
                    print(f"   banner_image_url: {banner_image_url}")
                    
                    # Check which URL to use
                    image_url = banner_image or banner_image_url
                    
                    if image_url:
                        print(f"\n🔍 Testing image accessibility...")
                        print(f"   URL: {image_url}")
                        
                        # Check if it's a Cloudinary URL
                        if 'cloudinary.com' in image_url or 'res.cloudinary.com' in image_url:
                            print(f"   ✅ URL is a Cloudinary URL")
                            
                            # Test accessibility
                            try:
                                img_req = urllib.request.Request(image_url, method='HEAD')
                                with urllib.request.urlopen(img_req, timeout=5, context=ssl_context) as img_response:
                                    status = img_response.getcode()
                                    if status == 200:
                                        print(f"   ✅ Image is accessible! (Status: {status})")
                                        print(f"   ✅ UPLOAD IS WORKING!")
                                        return True
                                    else:
                                        print(f"   ❌ Image returned status: {status}")
                                        print(f"   ❌ Image not accessible")
                            except urllib.error.HTTPError as e:
                                if e.code == 404:
                                    print(f"   ❌ Image not found in Cloudinary (404)")
                                    print(f"   ❌ Upload might have failed - image not in Cloudinary")
                                else:
                                    print(f"   ❌ Image error: HTTP {e.code}")
                            except Exception as e:
                                print(f"   ⚠️  Error checking image: {e}")
                        else:
                            print(f"   ⚠️  URL is NOT a Cloudinary URL")
                            print(f"   This means file is saved locally, not in Cloudinary")
                            print(f"   ❌ Upload is NOT working - using local storage")
                    else:
                        print(f"\n❌ No banner image URL in response")
                        print(f"   Image might not have been uploaded")
                else:
                    print(f"\n⚠️  No promotions found")
                    print(f"   Response: {json.dumps(data, indent=2)}")
            else:
                print(f"   Status: {response.getcode()}")
    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
    
    return False

def main():
    print("\n" + "=" * 80)
    print("DEPLOYMENT VERIFICATION")
    print("=" * 80)
    print("\nChecking if Cloudinary storage is working after deployment...")
    
    result = check_promotion_api()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if result:
        print("✅ Cloudinary storage IS working!")
        print("✅ Images are being uploaded to Cloudinary")
        print("✅ Images are accessible")
    else:
        print("❌ Cloudinary storage is NOT working")
        print("⚠️  Possible issues:")
        print("   1. Credentials not set in Render environment")
        print("   2. Fix not deployed yet")
        print("   3. Storage backend still using local storage")
        print("\n💡 Check Render logs for:")
        print("   - 'Cloudinary configured at startup for cloud: dhgaqa2gb'")
        print("   - 'Cloudinary storage enabled for cloud: dhgaqa2gb'")
    print("=" * 80)

if __name__ == "__main__":
    main()
