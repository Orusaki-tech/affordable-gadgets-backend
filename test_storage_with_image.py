#!/usr/bin/env python3
"""
Test Django Cloudinary storage with actual image file.
This will help diagnose why uploads aren't working.
"""
import os
import sys

# Add project to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')

try:
    import django
    django.setup()
    print("✅ Django setup successful")
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    print("   Make sure you're in the virtual environment")
    print("   Run: source venv/bin/activate")
    sys.exit(1)

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import tempfile

IMAGE_PATH = "/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-frontend/public/affordablelogo.png"

print("=" * 80)
print("DJANGO CLOUDINARY STORAGE TEST WITH REAL IMAGE")
print("=" * 80)

# Check image file
if not os.path.exists(IMAGE_PATH):
    print(f"\n❌ Image file not found: {IMAGE_PATH}")
    sys.exit(1)

file_size = os.path.getsize(IMAGE_PATH)
print(f"\n✅ Image file found: {IMAGE_PATH}")
print(f"   Size: {file_size} bytes ({file_size / 1024:.2f} KB)")

# Check storage configuration
print("\n1. Storage Configuration:")
print(f"   DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"   Storage type: {type(default_storage)}")
print(f"   Storage class: {default_storage.__class__.__name__}")

is_cloudinary = 'cloudinary' in str(type(default_storage)).lower() or 'cloudinary' in str(default_storage.__class__.__module__).lower()
if is_cloudinary:
    print("   ✅ Using Cloudinary storage")
else:
    print("   ❌ NOT using Cloudinary storage!")
    print("   This is likely the problem!")

# Check credentials
print("\n2. Cloudinary Credentials:")
cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
api_key = os.environ.get('CLOUDINARY_API_KEY', '')
api_secret = os.environ.get('CLOUDINARY_API_SECRET', '')

print(f"   CLOUDINARY_CLOUD_NAME: {cloud_name if cloud_name else 'NOT SET'}")
print(f"   CLOUDINARY_API_KEY: {'SET' if api_key else 'NOT SET'}")
print(f"   CLOUDINARY_API_SECRET: {'SET' if api_secret else 'NOT SET'}")

if not all([cloud_name, api_key, api_secret]):
    print("\n   ⚠️  WARNING: Credentials not fully set in environment")
    print("   They might be set in .env file or Render environment")

# Test saving the actual image file
print("\n3. Testing File Save to Cloudinary:")
try:
    # Read the image file
    with open(IMAGE_PATH, 'rb') as f:
        image_data = f.read()
    
    print(f"   Read {len(image_data)} bytes from image file")
    
    # Create Django ContentFile
    filename = os.path.basename(IMAGE_PATH)
    test_file = ContentFile(image_data, name=filename)
    
    # Try to save using Django storage
    save_path = f'promotions/2026/01/test_{filename}'
    print(f"   Attempting to save to: {save_path}")
    
    saved_path = default_storage.save(save_path, test_file)
    
    print(f"   ✅ File saved successfully!")
    print(f"   Saved path: {saved_path}")
    
    # Get the URL
    file_url = default_storage.url(saved_path)
    print(f"   File URL: {file_url}")
    
    if 'cloudinary.com' in file_url:
        print("   ✅ URL is a Cloudinary URL")
        
        # Test accessibility
        print("\n4. Testing Image Accessibility:")
        import urllib.request
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            req = urllib.request.Request(file_url, method='HEAD')
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                status = response.getcode()
                if status == 200:
                    print(f"   ✅ Image is accessible! (Status: {status})")
                    print(f"   ✅ Upload to Cloudinary worked!")
                    print(f"\n   🎉 SUCCESS! Images CAN be uploaded to Cloudinary!")
                    print(f"   Check your Cloudinary dashboard for the 'promotions' folder")
                else:
                    print(f"   ⚠️  Image returned status: {status}")
        except Exception as e:
            print(f"   ⚠️  Could not verify accessibility: {e}")
            print(f"   But file was saved, so upload might have worked")
    else:
        print("   ⚠️  URL is NOT a Cloudinary URL")
        print("   File might be saved locally instead of Cloudinary")
        print("   This means Cloudinary storage is not working")
    
    # Don't delete - let user see it in Cloudinary
    
except Exception as e:
    print(f"   ❌ File save failed: {e}")
    import traceback
    print("\n   Full error:")
    traceback.print_exc()
    print("\n   This error shows why uploads are failing!")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
if is_cloudinary:
    print("✅ Storage backend is Cloudinary")
    print("✅ If file saved successfully, uploads should work via Django")
    print("⚠️  If file save failed, check the error above")
else:
    print("❌ Storage backend is NOT Cloudinary")
    print("   This is why uploads aren't working!")
    print("   Check DEFAULT_FILE_STORAGE setting")
print("=" * 80)
