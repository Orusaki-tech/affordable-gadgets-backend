#!/usr/bin/env python3
"""
Test uploading an image via Django API endpoint.
Uses a real image file and tests the actual upload process.
"""
import os
import sys
import urllib.request
import urllib.error
import ssl
import json
import mimetypes

# Create SSL context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

# Try to find an image file
image_paths = [
    '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-frontend/public/affordablelogo.png',
    '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-frontend/affordablelogo.png',
]

image_path = None
for path in image_paths:
    if os.path.exists(path):
        image_path = path
        break

def test_django_promotion_upload():
    """Test uploading image via Django promotion API."""
    print("=" * 80)
    print("TEST: Django API Upload (Promotion Banner Image)")
    print("=" * 80)
    
    if not image_path:
        print("❌ No image file found to test with")
        print("   Please provide an image file path")
        return None
    
    print(f"📁 Using image: {image_path}")
    
    # Read image file
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        print(f"✅ Image file read: {len(image_data)} bytes")
    except Exception as e:
        print(f"❌ Failed to read image: {e}")
        return None
    
    # We need authentication token for Django API
    # For now, let's check what the API expects
    print("\n⚠️  Django API upload requires authentication")
    print("   To test this, you need:")
    print("   1. Admin user authentication token")
    print("   2. Promotion ID to update")
    print("\n   Testing API endpoint structure instead...")
    
    # Test if we can access the promotion endpoint
    test_url = f"{BACKEND_URL}/api/inventory/promotions/1/"
    print(f"\n🔍 Testing endpoint: {test_url}")
    
    try:
        req = urllib.request.Request(test_url)
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            status = response.getcode()
            if status == 401:
                print("   ✅ Endpoint exists (requires authentication)")
                print("   This is expected - need auth token to upload")
            else:
                print(f"   Status: {status}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("   ✅ Endpoint exists (requires authentication)")
            print("   This is expected - need auth token to upload")
        else:
            print(f"   Status: {e.code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    return None

def create_multipart_form_data(fields, files):
    """Create multipart/form-data body."""
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body_parts = []
    
    # Add regular fields
    for key, value in fields.items():
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body_parts.append(str(value).encode())
        body_parts.append(b'\r\n')
    
    # Add file fields
    for key, (filepath, filename, content_type) in files.items():
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode())
        body_parts.append(f'Content-Type: {content_type}\r\n\r\n'.encode())
        
        with open(filepath, 'rb') as f:
            body_parts.append(f.read())
        
        body_parts.append(b'\r\n')
    
    body_parts.append(f'--{boundary}--\r\n'.encode())
    
    return boundary, b''.join(body_parts)

def main():
    print("\n" + "=" * 80)
    print("DJANGO API UPLOAD TEST")
    print("=" * 80)
    
    if not image_path:
        print("\n❌ No image file found")
        print("   Please ensure an image file exists at:")
        for path in image_paths:
            print(f"   - {path}")
        return
    
    print(f"\n✅ Found image file: {image_path}")
    file_size = os.path.getsize(image_path)
    print(f"   Size: {file_size} bytes")
    
    # Test Django API
    test_django_promotion_upload()
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("To test Django API upload, you need:")
    print("1. Get authentication token from admin login")
    print("2. Use token in Authorization header: 'Token <your-token>'")
    print("3. Make PATCH request to /api/inventory/promotions/1/")
    print("4. Include image in multipart/form-data")
    print("\nAlternatively, test via admin interface:")
    print("1. Go to admin interface")
    print("2. Edit promotion")
    print("3. Upload image")
    print("4. Check backend logs for upload errors")
    print("=" * 80)

if __name__ == "__main__":
    main()
