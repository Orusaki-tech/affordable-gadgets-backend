#!/usr/bin/env python3
"""
Test Django's Cloudinary storage backend directly.
This simulates what happens when Django saves an image.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')

try:
    django.setup()
except Exception as e:
    print(f"❌ Failed to setup Django: {e}")
    print("   This script needs to run in the Django environment")
    sys.exit(1)

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import tempfile

print("=" * 80)
print("DJANGO CLOUDINARY STORAGE TEST")
print("=" * 80)

# Check configuration
print("\n1. Storage Configuration:")
print(f"   DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"   Storage type: {type(default_storage)}")
print(f"   Storage module: {default_storage.__class__.__module__}")

is_cloudinary = 'cloudinary' in str(type(default_storage)).lower()
if is_cloudinary:
    print("   ✅ Using Cloudinary storage")
else:
    print("   ❌ NOT using Cloudinary storage!")
    print("   This is the problem!")

# Check Cloudinary credentials
print("\n2. Cloudinary Credentials:")
cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
api_key = os.environ.get('CLOUDINARY_API_KEY', '')
api_secret = os.environ.get('CLOUDINARY_API_SECRET', '')

print(f"   CLOUDINARY_CLOUD_NAME: {cloud_name if cloud_name else 'NOT SET'}")
print(f"   CLOUDINARY_API_KEY: {'SET' if api_key else 'NOT SET'}")
print(f"   CLOUDINARY_API_SECRET: {'SET' if api_secret else 'NOT SET'}")

if not all([cloud_name, api_key, api_secret]):
    print("\n   ❌ Credentials not fully configured!")
    print("   Set these in environment variables or .env file")
    sys.exit(1)

# Test saving a file
print("\n3. Testing File Save:")
try:
    # Create a simple test image (1x1 PNG)
    import base64
    test_image_data = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    )
    
    # Create a ContentFile (Django file object)
    test_file = ContentFile(test_image_data, name='test_promotion.png')
    
    # Try to save it using Django's storage
    print("   Attempting to save file to: promotions/2026/01/test_django_storage.png")
    saved_path = default_storage.save('promotions/2026/01/test_django_storage.png', test_file)
    
    print(f"   ✅ File saved successfully!")
    print(f"   Saved path: {saved_path}")
    
    # Get the URL
    file_url = default_storage.url(saved_path)
    print(f"   File URL: {file_url}")
    
    if 'cloudinary.com' in file_url:
        print("   ✅ URL is a Cloudinary URL")
        
        # Test if file is accessible
        print("\n4. Testing File Accessibility:")
        import urllib.request
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            req = urllib.request.Request(file_url, method='HEAD')
            with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                if response.getcode() == 200:
                    print(f"   ✅ File is accessible! (Status: 200)")
                    print(f"   ✅ Upload to Cloudinary worked!")
                else:
                    print(f"   ⚠️  File returned status: {response.getcode()}")
        except Exception as e:
            print(f"   ⚠️  Could not verify accessibility: {e}")
    else:
        print("   ⚠️  URL is NOT a Cloudinary URL")
        print("   File might be saved locally instead of Cloudinary")
    
    # Clean up - try to delete test file
    try:
        default_storage.delete(saved_path)
        print("\n   ✅ Test file cleaned up")
    except Exception as e:
        print(f"\n   ⚠️  Could not delete test file: {e}")
        print("   You can delete it manually from Cloudinary dashboard")
    
except Exception as e:
    print(f"   ❌ File save failed: {e}")
    import traceback
    traceback.print_exc()
    print("\n   This error shows why uploads are failing!")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
if is_cloudinary and all([cloud_name, api_key, api_secret]):
    print("✅ Configuration looks correct")
    print("✅ If file saved successfully, uploads should work")
    print("⚠️  If file save failed, check the error above")
else:
    print("❌ Configuration issue detected")
    print("   Fix the configuration and try again")
print("=" * 80)
