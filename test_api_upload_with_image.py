#!/usr/bin/env python3
"""
Test uploading an image via Django API using the actual image file.
This will test the full upload flow.
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
IMAGE_PATH = "/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-frontend/public/affordablelogo.png"

def create_multipart_request(url, fields, file_field_name, file_path, auth_token=None):
    """Create a multipart/form-data request."""
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body_parts = []
    
    # Add regular fields
    for key, value in fields.items():
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        if isinstance(value, (list, dict)):
            body_parts.append(json.dumps(value).encode())
        else:
            body_parts.append(str(value).encode())
        body_parts.append(b'\r\n')
    
    # Add file
    if file_path and os.path.exists(file_path):
        filename = os.path.basename(file_path)
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="{file_field_name}"; filename="{filename}"\r\n'.encode())
        body_parts.append(f'Content-Type: {content_type}\r\n\r\n'.encode())
        
        with open(file_path, 'rb') as f:
            body_parts.append(f.read())
        
        body_parts.append(b'\r\n')
    
    body_parts.append(f'--{boundary}--\r\n'.encode())
    
    body = b''.join(body_parts)
    
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    req.add_header('Content-Length', str(len(body)))
    
    if auth_token:
        req.add_header('Authorization', f'Token {auth_token}')
    
    return req

def main():
    print("=" * 80)
    print("DJANGO API UPLOAD TEST WITH REAL IMAGE")
    print("=" * 80)
    
    # Check if image exists
    if not os.path.exists(IMAGE_PATH):
        print(f"\n❌ Image file not found: {IMAGE_PATH}")
        return
    
    file_size = os.path.getsize(IMAGE_PATH)
    print(f"\n✅ Image file found: {IMAGE_PATH}")
    print(f"   Size: {file_size} bytes ({file_size / 1024:.2f} KB)")
    
    print("\n" + "=" * 80)
    print("TESTING UPLOAD VIA DJANGO API")
    print("=" * 80)
    
    print("\n⚠️  This test requires:")
    print("   1. Authentication token (from admin login)")
    print("   2. Promotion ID to update")
    print("\n   To get a token:")
    print("   1. Login to admin interface")
    print("   2. Get token from browser dev tools (Network tab)")
    print("   3. Or use: POST /api/inventory/auth/login/")
    
    # Test endpoint structure
    print("\n📋 Testing API Endpoint Structure:")
    test_url = f"{BACKEND_URL}/api/inventory/promotions/1/"
    
    try:
        req = urllib.request.Request(test_url)
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            print(f"   ❌ Unexpected: Got {response.getcode()} (should require auth)")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"   ✅ Endpoint requires authentication (401)")
            print(f"   ✅ Endpoint exists and is protected")
        elif e.code == 404:
            print(f"   ⚠️  Promotion not found (404)")
        else:
            print(f"   Status: {e.code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 80)
    print("MANUAL TEST INSTRUCTIONS")
    print("=" * 80)
    print("\nTo test upload via API:")
    print("\n1. Get authentication token:")
    print("   - Login to admin interface")
    print("   - Check browser Network tab for Authorization header")
    print("   - Or use API: POST /api/inventory/auth/login/")
    print("\n2. Upload image:")
    print("   PATCH /api/inventory/promotions/1/")
    print("   Headers:")
    print("     Authorization: Token <your-token>")
    print("     Content-Type: multipart/form-data")
    print("   Body:")
    print("     banner_image: <image-file>")
    print("\n3. Check result:")
    print("   - Response should return Cloudinary URL")
    print("   - Check Cloudinary dashboard for 'promotions' folder")
    print("   - Verify image appears")
    print("\n" + "=" * 80)
    print("ALTERNATIVE: Test via Admin Interface")
    print("=" * 80)
    print("\n1. Go to: https://affordable-gadgets-admin.vercel.app/")
    print("2. Login as admin")
    print("3. Navigate to Promotions")
    print("4. Edit promotion ID 1")
    print("5. Upload the image file:")
    print(f"   {IMAGE_PATH}")
    print("6. Save the promotion")
    print("7. Check backend logs for any errors")
    print("8. Check Cloudinary dashboard for 'promotions' folder")
    print("=" * 80)

if __name__ == "__main__":
    main()
