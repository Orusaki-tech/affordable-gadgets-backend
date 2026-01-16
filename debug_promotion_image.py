#!/usr/bin/env python3
"""
Debug script to check promotion image URLs and Cloudinary configuration.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
django.setup()

from inventory.models import Promotion
from django.core.files.storage import default_storage
from django.conf import settings
import cloudinary
from cloudinary import CloudinaryImage

print("=" * 80)
print("PROMOTION IMAGE DEBUG")
print("=" * 80)

# Check Cloudinary configuration
print("\n1. Cloudinary Configuration:")
print(f"   DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"   Storage type: {type(default_storage)}")
print(f"   CLOUDINARY_CLOUD_NAME: {os.environ.get('CLOUDINARY_CLOUD_NAME', 'NOT SET')}")
print(f"   CLOUDINARY_API_KEY: {'SET' if os.environ.get('CLOUDINARY_API_KEY') else 'NOT SET'}")
print(f"   CLOUDINARY_API_SECRET: {'SET' if os.environ.get('CLOUDINARY_API_SECRET') else 'NOT SET'}")

# Get promotion
promotion = Promotion.objects.filter(id=1).first()
if not promotion:
    print("\n❌ Promotion with ID 1 not found")
    sys.exit(1)

print(f"\n2. Promotion Details:")
print(f"   ID: {promotion.id}")
print(f"   Title: {promotion.title}")
print(f"   Has banner_image: {bool(promotion.banner_image)}")

if promotion.banner_image:
    print(f"\n3. Banner Image Details:")
    print(f"   Image name: {promotion.banner_image.name}")
    print(f"   Image URL (from field): {promotion.banner_image.url}")
    
    # Check if it's a Cloudinary URL
    original_url = promotion.banner_image.url
    is_cloudinary = 'cloudinary.com' in original_url or 'res.cloudinary.com' in original_url
    print(f"   Is Cloudinary URL: {is_cloudinary}")
    
    if is_cloudinary:
        print(f"\n4. Cloudinary URL Analysis:")
        print(f"   Full URL: {original_url}")
        
        # Extract public_id from URL
        if '/upload/' in original_url:
            parts = original_url.split('/upload/')
            if len(parts) > 1:
                after_upload = parts[1]
                # Remove version if present (v1, v123, etc.)
                if after_upload.startswith('v') and after_upload[1:2].isdigit():
                    after_upload = after_upload.split('/', 1)[1] if '/' in after_upload else ''
                # Remove transformations
                if ',' in after_upload or 'c_fill' in after_upload:
                    # Find the actual public_id (after transformations)
                    parts_after_transform = after_upload.split('/')
                    # The last part should be the public_id
                    if parts_after_transform:
                        public_id = '/'.join(parts_after_transform[-1:])
                        print(f"   Extracted public_id: {public_id}")
                        
                        # Try to build URL without transformations
                        try:
                            cloudinary.config(
                                cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
                                api_key=os.environ.get('CLOUDINARY_API_KEY'),
                                api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
                                secure=True
                            )
                            cloudinary_img = CloudinaryImage(public_id)
                            base_url = cloudinary_img.build_url()
                            print(f"   Base Cloudinary URL: {base_url}")
                            
                            # Test if image exists
                            print(f"\n5. Testing Image Accessibility:")
                            import urllib.request
                            import ssl
                            ssl_context = ssl.create_default_context()
                            ssl_context.check_hostname = False
                            ssl_context.verify_mode = ssl.CERT_NONE
                            
                            try:
                                req = urllib.request.Request(base_url, method='HEAD')
                                with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                                    if response.getcode() == 200:
                                        print(f"   ✅ Base URL is accessible")
                                    else:
                                        print(f"   ❌ Base URL returned: {response.getcode()}")
                            except Exception as e:
                                print(f"   ❌ Base URL not accessible: {e}")
                            
                            # Test with transformations
                            transformed_url = cloudinary_img.build_url(transformation=[
                                {'width': 1080, 'height': 1920, 'crop': 'fill', 'quality': 'auto', 'format': 'auto'}
                            ])
                            print(f"   Transformed URL: {transformed_url[:100]}...")
                            
                            try:
                                req = urllib.request.Request(transformed_url, method='HEAD')
                                with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                                    if response.getcode() == 200:
                                        print(f"   ✅ Transformed URL is accessible")
                                    else:
                                        print(f"   ❌ Transformed URL returned: {response.getcode()}")
                            except Exception as e:
                                print(f"   ❌ Transformed URL not accessible: {e}")
                                
                        except Exception as e:
                            print(f"   ❌ Error building Cloudinary URL: {e}")
    else:
        print(f"\n4. Local URL Analysis:")
        print(f"   This is a local URL, not Cloudinary")
        print(f"   The image may have been uploaded before Cloudinary was configured")
        print(f"   Or Cloudinary storage is not working correctly")
        
        # Try to get the public_id from the image name
        if promotion.banner_image.name:
            public_id = promotion.banner_image.name
            # Remove file extension
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            print(f"   Image name (potential public_id): {public_id}")
            
            # Try to construct Cloudinary URL
            try:
                cloudinary.config(
                    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
                    api_key=os.environ.get('CLOUDINARY_API_KEY'),
                    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
                    secure=True
                )
                cloudinary_img = CloudinaryImage(public_id)
                cloudinary_url = cloudinary_img.build_url()
                print(f"   Constructed Cloudinary URL: {cloudinary_url}")
                
                # Test accessibility
                import urllib.request
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                try:
                    req = urllib.request.Request(cloudinary_url, method='HEAD')
                    with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                        if response.getcode() == 200:
                            print(f"   ✅ Constructed URL is accessible")
                        else:
                            print(f"   ❌ Constructed URL returned: {response.getcode()}")
                except Exception as e:
                    print(f"   ❌ Constructed URL not accessible: {e}")
            except Exception as e:
                print(f"   ❌ Error: {e}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS:")
print("=" * 80)
print("1. If image is not accessible, check Cloudinary dashboard")
print("2. If public_id doesn't match, re-upload the image")
print("3. Verify Cloudinary credentials are set correctly")
print("4. Check that DEFAULT_FILE_STORAGE is set to MediaCloudinaryStorage")
print("=" * 80)
