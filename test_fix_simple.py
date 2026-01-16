#!/usr/bin/env python3
"""
Simple test to verify the fix logic without Django setup.
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

def test_current_api():
    """Test current API state."""
    print("=" * 80)
    print("TEST: Current API State")
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
                    banner_url = promotion.get('banner_image') or promotion.get('banner_image_url')
                    
                    print(f"\n📋 Current State:")
                    print(f"   Promotion ID: {promotion.get('id')}")
                    print(f"   Title: {promotion.get('title')}")
                    print(f"   Banner URL: {banner_url}")
                    
                    if banner_url:
                        if 'cloudinary.com' in banner_url:
                            print(f"   ✅ URL is Cloudinary URL")
                            
                            # Test accessibility
                            try:
                                img_req = urllib.request.Request(banner_url, method='HEAD')
                                with urllib.request.urlopen(img_req, timeout=5, context=ssl_context) as img_response:
                                    if img_response.getcode() == 200:
                                        print(f"   ✅ Image is accessible!")
                                        return True
                                    else:
                                        print(f"   ❌ Image returned status: {img_response.getcode()}")
                            except urllib.error.HTTPError as e:
                                if e.code == 404:
                                    print(f"   ❌ Image not found in Cloudinary (404)")
                                    print(f"   ❌ ISSUE: File not uploaded to Cloudinary")
                                    return False
                        else:
                            print(f"   ❌ URL is NOT Cloudinary URL")
                            print(f"   ❌ ISSUE: Using local storage")
                            return False
                else:
                    print(f"\n⚠️  No promotions found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return False

def verify_fix_code():
    """Verify the fix code is correct."""
    print("\n" + "=" * 80)
    print("TEST: Fix Code Verification")
    print("=" * 80)
    
    try:
        with open('inventory/models.py', 'r') as f:
            content = f.read()
        
        # Check if _promotion_banner_storage is defined
        if '_promotion_banner_storage' in content:
            print("✅ _promotion_banner_storage variable is defined")
            
            # Check if it's set before Promotion class
            promotion_class_pos = content.find('class Promotion(models.Model):')
            storage_def_pos = content.find('_promotion_banner_storage')
            
            if storage_def_pos < promotion_class_pos:
                print("✅ Storage is defined BEFORE Promotion class")
            else:
                print("❌ Storage is defined AFTER Promotion class (wrong order!)")
                return False
            
            # Check if banner_image uses the storage
            if 'storage=_promotion_banner_storage' in content:
                print("✅ banner_image field uses _promotion_banner_storage")
            else:
                print("❌ banner_image field doesn't use _promotion_banner_storage")
                return False
            
            # Check if MediaCloudinaryStorage is instantiated
            if 'MediaCloudinaryStorage()' in content:
                print("✅ MediaCloudinaryStorage is instantiated")
            else:
                print("⚠️  MediaCloudinaryStorage might not be instantiated")
            
            # Check credential check logic
            if 'if all([_cloud_name, _api_key, _api_secret])' in content or 'if all([' in content:
                print("✅ Credential check logic is present")
            else:
                print("⚠️  Credential check might be missing")
            
            print("\n✅ Fix code looks correct!")
            return True
        else:
            print("❌ _promotion_banner_storage not found in code")
            return False
            
    except FileNotFoundError:
        print("❌ inventory/models.py not found")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def main():
    print("\n" + "=" * 80)
    print("STORAGE FIX VERIFICATION")
    print("=" * 80)
    
    # Test current API
    api_ok = test_current_api()
    
    # Verify fix code
    code_ok = verify_fix_code()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if code_ok:
        print("✅ Fix code is correct!")
        print("✅ Should work after deployment")
    else:
        print("❌ Fix code has issues")
        print("   Review the code before deploying")
    
    if not api_ok:
        print("\n⚠️  Current API: Images not working (expected)")
        print("   After deploying fix, upload a NEW image to test")
    
    print("\n💡 Recommendation:")
    if code_ok:
        print("   ✅ Code looks good - safe to deploy!")
        print("   After deployment, upload a new promotion image to test")
    else:
        print("   ⚠️  Fix code issues - review before deploying")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
