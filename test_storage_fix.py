#!/usr/bin/env python3
"""
Test if the storage fix will work by checking:
1. Current API state
2. Storage backend logic
3. Simulate what should happen with the fix
"""
import os
import sys
import urllib.request
import urllib.error
import ssl
import json

# Add project to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def test_current_api():
    """Test current API to see what's happening."""
    print("=" * 80)
    print("TEST 1: Current API State")
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
                    
                    print(f"\n📋 Promotion ID: {promotion.get('id')}")
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
                                    print(f"   ❌ Current issue: File not uploaded to Cloudinary")
                                else:
                                    print(f"   ❌ Image error: HTTP {e.code}")
                        else:
                            print(f"   ❌ URL is NOT Cloudinary URL")
                            print(f"   ❌ Current issue: Using local storage")
                else:
                    print(f"\n⚠️  No promotions found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return False

def test_storage_logic():
    """Test if the storage fix logic will work."""
    print("\n" + "=" * 80)
    print("TEST 2: Storage Fix Logic Verification")
    print("=" * 80)
    
    try:
        import django
        django.setup()
        print("✅ Django setup successful")
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False
    
    # Check credentials
    import os
    from django.conf import settings
    
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME') or getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
    api_key = os.environ.get('CLOUDINARY_API_KEY') or getattr(settings, 'CLOUDINARY_API_KEY', '')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET') or getattr(settings, 'CLOUDINARY_API_SECRET', '')
    
    print(f"\n📋 Credentials Check:")
    print(f"   CLOUD_NAME: {cloud_name if cloud_name else 'NOT SET'}")
    print(f"   API_KEY: {'SET' if api_key else 'NOT SET'}")
    print(f"   API_SECRET: {'SET' if api_secret else 'NOT SET'}")
    
    if not all([cloud_name, api_key, api_secret]):
        print(f"\n❌ Credentials not available in local environment")
        print(f"   (This is OK - they should be set in Render)")
        return False
    
    # Test if MediaCloudinaryStorage can be instantiated
    print(f"\n🔍 Testing MediaCloudinaryStorage instantiation...")
    try:
        from cloudinary_storage.storage import MediaCloudinaryStorage
        storage = MediaCloudinaryStorage()
        print(f"   ✅ MediaCloudinaryStorage can be instantiated")
        print(f"   ✅ Storage type: {type(storage)}")
        
        # Check if it's actually using Cloudinary
        storage_str = str(type(storage))
        if 'cloudinary' in storage_str.lower():
            print(f"   ✅ Storage is Cloudinary storage")
            return True
        else:
            print(f"   ⚠️  Storage type doesn't contain 'cloudinary'")
            print(f"   ⚠️  Might still fall back to local storage")
    except ImportError as e:
        print(f"   ❌ Cannot import MediaCloudinaryStorage: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error instantiating storage: {e}")
        return False
    
    return False

def test_model_storage():
    """Test if Promotion model will use the correct storage."""
    print("\n" + "=" * 80)
    print("TEST 3: Promotion Model Storage Check")
    print("=" * 80)
    
    try:
        from inventory.models import Promotion
        
        # Check banner_image field storage
        banner_field = Promotion._meta.get_field('banner_image')
        storage = banner_field.storage
        
        print(f"\n📋 Banner Image Field Storage:")
        print(f"   Storage: {storage}")
        print(f"   Storage type: {type(storage)}")
        
        storage_str = str(type(storage))
        if storage is None:
            print(f"   ⚠️  Storage is None - will use DEFAULT_FILE_STORAGE")
            print(f"   ⚠️  This might still use FileSystemStorage")
        elif 'cloudinary' in storage_str.lower():
            print(f"   ✅ Storage is Cloudinary storage!")
            print(f"   ✅ Fix should work!")
            return True
        else:
            print(f"   ❌ Storage is NOT Cloudinary: {storage_str}")
            print(f"   ❌ Fix might not work")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return False

def main():
    print("\n" + "=" * 80)
    print("STORAGE FIX VERIFICATION TEST")
    print("=" * 80)
    
    # Test 1: Current API state
    api_working = test_current_api()
    
    # Test 2: Storage logic
    storage_works = test_storage_logic()
    
    # Test 3: Model storage
    model_works = test_model_storage()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if model_works:
        print("✅ Fix should work! Promotion model is using Cloudinary storage")
    elif storage_works:
        print("⚠️  Storage can be instantiated, but model might not use it")
        print("   Check if _promotion_banner_storage is set correctly")
    else:
        print("❌ Fix might not work - storage not properly configured")
    
    if not api_working:
        print("\n⚠️  Current API: Images not in Cloudinary (expected)")
        print("   After deploying fix, upload a NEW image to test")
    
    print("\n💡 Next Steps:")
    print("   1. If all tests pass → Deploy and test with real upload")
    print("   2. If tests fail → Check credentials and storage setup")
    print("=" * 80)

if __name__ == "__main__":
    main()
