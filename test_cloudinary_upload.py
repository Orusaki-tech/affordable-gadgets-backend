#!/usr/bin/env python3
"""
Test Cloudinary image upload using API calls.
Tests direct Cloudinary upload with proper authentication.
"""
import os
import sys
import urllib.request
import urllib.error
import ssl
import json
import base64
import hmac
import hashlib
import time
import urllib.parse

# Cloudinary credentials
CLOUD_NAME = "dhgaqa2gb"
API_KEY = "428511131769392"
API_SECRET = "inHa4tnZC0znEW_hynKzcF0XFr4"

# Create SSL context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def create_test_image():
    """Create a simple 1x1 pixel PNG image for testing."""
    # Minimal valid PNG (1x1 transparent pixel)
    png_data = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    )
    return png_data

def test_cloudinary_upload_base64():
    """Test uploading to Cloudinary using base64 encoding (simplest method)."""
    print("=" * 80)
    print("TEST: Cloudinary Direct Upload (Base64 Method)")
    print("=" * 80)
    
    # Create test image
    test_image = create_test_image()
    image_base64 = base64.b64encode(test_image).decode('utf-8')
    
    # Cloudinary upload endpoint
    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"
    
    # Prepare parameters with signature
    timestamp = str(int(time.time()))
    
    # Parameters for signature (must be in specific order)
    params_for_signature = {
        'folder': 'promotions/2026/01/',
        'public_id': 'test_upload_api',
        'timestamp': timestamp,
    }
    
    # Create signature string (sorted keys, joined with &, then append secret)
    signature_parts = []
    for key in sorted(params_for_signature.keys()):
        signature_parts.append(f"{key}={params_for_signature[key]}")
    signature_string = '&'.join(signature_parts) + API_SECRET
    signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()
    
    # All parameters including file
    params = {
        'file': f'data:image/png;base64,{image_base64}',
        'folder': 'promotions/2026/01/',
        'public_id': 'test_upload_api',
        'timestamp': timestamp,
        'api_key': API_KEY,
        'signature': signature
    }
    
    print(f"   Signature string: {signature_string[:50]}...")
    print(f"   Generated signature: {signature}")
    
    print(f"\n📤 Uploading test image...")
    print(f"   Folder: promotions/2026/01/")
    print(f"   Public ID: test_upload_api")
    
    # Make request
    try:
        data = urllib.parse.urlencode(params).encode('utf-8')
        req = urllib.request.Request(upload_url, data=data)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            if response.getcode() == 200:
                result = json.loads(response.read().decode('utf-8'))
                print("\n✅ Upload successful!")
                print(f"   Public ID: {result.get('public_id')}")
                print(f"   URL: {result.get('secure_url')}")
                print(f"   Format: {result.get('format')}")
                print(f"   Size: {result.get('bytes')} bytes")
                print(f"   Width: {result.get('width')}px")
                print(f"   Height: {result.get('height')}px")
                
                # Test if image is accessible
                image_url = result.get('secure_url')
                print(f"\n🔍 Testing image accessibility...")
                try:
                    img_req = urllib.request.Request(image_url, method='HEAD')
                    with urllib.request.urlopen(img_req, timeout=5, context=ssl_context) as img_response:
                        status = img_response.getcode()
                        if status == 200:
                            print(f"   ✅ Image is accessible! (Status: {status})")
                            print(f"   ✅ Image URL works: {image_url}")
                            return result
                        else:
                            print(f"   ⚠️  Image returned status: {status}")
                except Exception as e:
                    print(f"   ⚠️  Could not verify accessibility: {e}")
                
                return result
            else:
                error_data = response.read().decode('utf-8')
                print(f"\n❌ Upload failed: HTTP {response.getcode()}")
                try:
                    error_json = json.loads(error_data)
                    print(f"   Error: {error_json.get('error', {}).get('message', error_data)}")
                except:
                    print(f"   Error: {error_data}")
                return None
    except urllib.error.HTTPError as e:
        error_data = e.read().decode('utf-8')
        print(f"\n❌ Upload failed: HTTP {e.code}")
        try:
            error_json = json.loads(error_data)
            print(f"   Error: {error_json.get('error', {}).get('message', error_data)}")
        except:
            print(f"   Error: {error_data}")
        return None
    except Exception as e:
        print(f"\n❌ Upload error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_django_api_upload_with_image():
    """Test uploading via Django API using a real image file."""
    print("\n" + "=" * 80)
    print("TEST: Django API Upload (via Promotion endpoint)")
    print("=" * 80)
    
    # Check if we have an image file to use
    image_paths = [
        '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-frontend/public/affordablelogo.png',
        '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-frontend/affordablelogo.png',
    ]
    
    image_path = None
    for path in image_paths:
        if os.path.exists(path):
            image_path = path
            break
    
    if not image_path:
        print("⚠️  No image file found to test Django API upload")
        print("   Would need authentication token to test this")
        return None
    
    print(f"📁 Found image: {image_path}")
    print("⚠️  Django API upload requires:")
    print("   1. Authentication token (from admin login)")
    print("   2. Promotion ID to update")
    print("   3. Proper multipart form data")
    print("\n   Skipping Django API test (requires authentication)")
    return None

def main():
    print("\n" + "=" * 80)
    print("CLOUDINARY UPLOAD TEST")
    print("=" * 80)
    print(f"Cloud Name: {CLOUD_NAME}")
    print(f"API Key: {API_KEY}")
    print(f"API Secret: {'*' * 10}...{API_SECRET[-4:]}")
    print()
    
    # Test direct Cloudinary upload
    upload_result = test_cloudinary_upload_base64()
    
    if upload_result:
        print("\n" + "=" * 80)
        print("✅ UPLOAD TEST SUCCESSFUL!")
        print("=" * 80)
        print("\n🎉 The image was successfully uploaded to Cloudinary!")
        print("\n📋 Next Steps:")
        print("1. Go to your Cloudinary dashboard")
        print("2. Navigate to Media Library > Folders")
        print("3. Look for 'promotions' folder")
        print("4. You should see: promotions/2026/01/test_upload_api")
        print("\n✅ This proves:")
        print("   - Your API keys work correctly")
        print("   - Cloudinary accepts uploads")
        print("   - The issue is with Django's upload process")
        print("\n💡 The problem is likely:")
        print("   - Django's Cloudinary storage not working")
        print("   - Upload failing silently in Django")
        print("   - Need to check Django logs for errors")
    else:
        print("\n" + "=" * 80)
        print("❌ UPLOAD TEST FAILED")
        print("=" * 80)
        print("\nPossible issues:")
        print("1. API keys are incorrect")
        print("2. API keys don't have upload permissions")
        print("3. Network/firewall blocking Cloudinary")
        print("4. Cloudinary account limits reached")
        print("5. Signature generation error")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
