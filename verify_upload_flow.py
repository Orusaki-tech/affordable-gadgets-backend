#!/usr/bin/env python3
"""
Verify that image uploads are working correctly.
Checks Cloudinary configuration and provides upload instructions.
"""
import os
import sys

print("=" * 80)
print("CLOUDINARY UPLOAD VERIFICATION")
print("=" * 80)

# Check environment variables
print("\n1. Environment Variables:")
cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', 'NOT SET')
api_key = os.environ.get('CLOUDINARY_API_KEY', 'NOT SET')
api_secret = os.environ.get('CLOUDINARY_API_SECRET', 'NOT SET')

print(f"   CLOUDINARY_CLOUD_NAME: {cloud_name}")
print(f"   CLOUDINARY_API_KEY: {'SET' if api_key != 'NOT SET' else 'NOT SET'}")
print(f"   CLOUDINARY_API_SECRET: {'SET' if api_secret != 'NOT SET' else 'NOT SET'}")

if cloud_name == 'NOT SET' or api_key == 'NOT SET' or api_secret == 'NOT SET':
    print("\n   ⚠️  WARNING: Cloudinary credentials not fully configured!")
    print("   Set these in your Render environment variables")
else:
    print("\n   ✅ Cloudinary credentials are configured")

# Check Django settings
try:
    import django
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
    django.setup()
    
    from django.conf import settings
    from django.core.files.storage import default_storage
    
    print("\n2. Django Storage Configuration:")
    print(f"   DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
    print(f"   Storage type: {type(default_storage)}")
    
    is_cloudinary = 'cloudinary' in str(type(default_storage)).lower()
    if is_cloudinary:
        print("   ✅ Using Cloudinary storage")
    else:
        print("   ❌ NOT using Cloudinary storage!")
        print("   This is the problem - images won't upload to Cloudinary")
    
    print("\n3. Cloudinary Storage Settings:")
    cloudinary_storage = getattr(settings, 'CLOUDINARY_STORAGE', {})
    print(f"   CLOUD_NAME: {cloudinary_storage.get('CLOUD_NAME', 'NOT SET')}")
    print(f"   API_KEY: {'SET' if cloudinary_storage.get('API_KEY') else 'NOT SET'}")
    print(f"   API_SECRET: {'SET' if cloudinary_storage.get('API_SECRET') else 'NOT SET'}")
    print(f"   SECURE: {cloudinary_storage.get('SECURE', False)}")
    
except Exception as e:
    print(f"\n   ⚠️  Could not check Django settings: {e}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)
print("1. Verify Cloudinary credentials in Render dashboard")
print("2. Check that DEFAULT_FILE_STORAGE is set correctly")
print("3. Upload a test image via admin interface")
print("4. Check Cloudinary dashboard for the 'promotions' folder")
print("5. If folder doesn't appear, check backend logs for errors")
print("=" * 80)
