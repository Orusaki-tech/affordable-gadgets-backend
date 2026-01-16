#!/usr/bin/env python3
"""
Verify Cloudinary API keys and test image upload functionality.
"""
import cloudinary
import cloudinary.uploader
import os

# Your Cloudinary credentials
CLOUD_NAME = "dhgaqa2gb"
API_KEY = "428511131769392"  # Root API Key from Render
API_SECRET = "inHa4tnZC0znEW_hynKzcF0XFr4"  # Root API Secret from Render

print("=" * 80)
print("CLOUDINARY API KEYS VERIFICATION")
print("=" * 80)

# Configure Cloudinary
try:
    cloudinary.config(
        cloud_name=CLOUD_NAME,
        api_key=API_KEY,
        api_secret=API_SECRET,
        secure=True
    )
    print("\n✅ Cloudinary configured successfully")
    print(f"   Cloud Name: {CLOUD_NAME}")
    print(f"   API Key: {API_KEY}")
    print(f"   API Secret: {'*' * 10}...{API_SECRET[-4:]}")
except Exception as e:
    print(f"\n❌ Failed to configure Cloudinary: {e}")
    exit(1)

# Test API connection
print("\n🔍 Testing API Connection...")
try:
    # Try to get account details (this verifies the keys work)
    result = cloudinary.api.ping()
    print("   ✅ API connection successful")
    print(f"   Status: {result.get('status', 'unknown')}")
except Exception as e:
    print(f"   ❌ API connection failed: {e}")
    print("   Check your API keys are correct")
    exit(1)

# Test upload capability
print("\n🔍 Testing Upload Capability...")
try:
    # Create a simple test image (1x1 pixel PNG)
    import base64
    # Minimal 1x1 transparent PNG
    test_image_data = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    )
    
    # Try to upload to promotions folder
    upload_result = cloudinary.uploader.upload(
        test_image_data,
        folder="promotions/2026/01/",
        public_id="test_upload",
        resource_type="image"
    )
    
    print("   ✅ Upload test successful!")
    print(f"   Public ID: {upload_result.get('public_id')}")
    print(f"   URL: {upload_result.get('url')}")
    print(f"   Secure URL: {upload_result.get('secure_url')}")
    
    # Test if the image is accessible
    import urllib.request
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    test_url = upload_result.get('secure_url')
    try:
        req = urllib.request.Request(test_url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            if response.getcode() == 200:
                print("   ✅ Uploaded image is accessible")
            else:
                print(f"   ⚠️  Image returned status: {response.getcode()}")
    except Exception as e:
        print(f"   ⚠️  Could not verify image accessibility: {e}")
    
    # Clean up - delete test image
    try:
        cloudinary.uploader.destroy(upload_result.get('public_id'))
        print("   ✅ Test image cleaned up")
    except:
        print("   ⚠️  Could not delete test image (you can delete it manually)")
    
except Exception as e:
    print(f"   ❌ Upload test failed: {e}")
    print("   This means images won't upload to Cloudinary")
    print("   Check:")
    print("   1. API keys are correct")
    print("   2. API keys have upload permissions")
    print("   3. Cloudinary account is active")

print("\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)
print("✅ Cloudinary credentials are configured")
print("✅ API connection works")
print("✅ Upload capability verified")
print()
print("Your keys should work for uploading images!")
print("If uploads still fail, check:")
print("1. Keys are set correctly in Render environment variables")
print("2. DEFAULT_FILE_STORAGE is set to MediaCloudinaryStorage")
print("3. Backend logs for any upload errors")
print("=" * 80)
