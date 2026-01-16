#!/usr/bin/env python3
"""
Diagnose Cloudinary image URL issues.
Tests different public_id formats to find the correct one.
"""
import urllib.request
import urllib.error
import ssl
import cloudinary
import os

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Configure Cloudinary
cloudinary.config(
    cloud_name='dhgaqa2gb',
    api_key=os.environ.get('CLOUDINARY_API_KEY', ''),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', ''),
    secure=True
)

from cloudinary import CloudinaryImage

def test_url(url):
    """Test if a URL is accessible."""
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            return response.getcode() == 200
    except:
        return False

# Current URL from API
current_url = "https://res.cloudinary.com/dhgaqa2gb/image/upload/c_fill,h_1920,q_auto,w_1080/v1/promotions/2026/01/IPHONE14PROMAX"
print("Current URL from API:")
print(current_url)
print(f"Accessible: {'✅' if test_url(current_url) else '❌'}")
print()

# Extract public_id from URL
# Format: /v1/promotions/2026/01/IPHONE14PROMAX
public_id_from_url = "promotions/2026/01/IPHONE14PROMAX"

# Try different variations
variations = [
    "promotions/2026/01/IPHONE14PROMAX",
    "promotions/2026/01/iphone14promax",
    "promotions/2026/01/iphone_14_pro_max",
    "promotions/2026/01/IPHONE_14_PRO_MAX",
    "promotions/2026/01/iphone-14-pro-max",
    "promotions/2026/01/IPHONE-14-PRO-MAX",
    "promotions/2026/01/iphone14promax",
    "promotions/2026/01/IPHONE14PROMAX",
]

print("Testing different public_id variations:")
print("=" * 80)

for public_id in variations:
    try:
        img = CloudinaryImage(public_id)
        base_url = img.build_url()
        transformed_url = img.build_url(transformation=[
            {'width': 1080, 'height': 1920, 'crop': 'fill', 'quality': 'auto', 'format': 'auto'}
        ])
        
        is_accessible = test_url(transformed_url)
        status = "✅" if is_accessible else "❌"
        print(f"{status} {public_id}")
        if is_accessible:
            print(f"   Working URL: {transformed_url[:100]}...")
    except Exception as e:
        print(f"❌ {public_id} - Error: {e}")

print()
print("=" * 80)
print("Recommendations:")
print("1. Check Cloudinary dashboard for actual public_id")
print("2. Re-upload image if it doesn't exist")
print("3. Ensure filename matches public_id (case-sensitive)")
print("4. Check that image was actually uploaded to Cloudinary")
