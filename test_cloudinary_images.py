#!/usr/bin/env python3
"""
Test script to check Cloudinary image URLs from the deployed API.
"""
import urllib.request
import urllib.error
import ssl
import json
import sys

# Create SSL context that doesn't verify certificates (for testing only)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# API endpoints
BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"
PUBLIC_API = f"{BACKEND_URL}/api/v1/public/products/"

def test_api_endpoint(url, headers=None):
    """Test an API endpoint and return the response."""
    try:
        print(f"\n🔍 Testing: {url}")
        req = urllib.request.Request(url)
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            status_code = response.getcode()
            print(f"   Status Code: {status_code}")
            
            if status_code == 200:
                data = response.read().decode('utf-8')
                return json.loads(data)
            else:
                data = response.read().decode('utf-8')
                print(f"   Error: {data[:200]}")
                return None
    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP Error: {e.code} - {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            print(f"   Error body: {error_body[:200]}")
        except:
            pass
        return None
    except urllib.error.URLError as e:
        print(f"   ❌ URL Error: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON decode error: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return None

def analyze_image_urls(data):
    """Analyze image URLs in the API response."""
    if not data:
        return
    
    print("\n📸 Image URL Analysis:")
    print("=" * 80)
    
    # Check if it's a paginated response
    if 'results' in data:
        products = data['results']
        print(f"Found {len(products)} products in response")
    elif isinstance(data, list):
        products = data
        print(f"Found {len(products)} products in response")
    else:
        products = [data]
        print("Single product response")
    
    cloudinary_count = 0
    local_count = 0
    missing_count = 0
    
    for product in products[:5]:  # Check first 5 products
        product_name = product.get('product_name', 'Unknown')
        primary_image = product.get('primary_image')
        
        print(f"\n📦 Product: {product_name}")
        print(f"   Primary Image: {primary_image}")
        
        if not primary_image:
            missing_count += 1
            print("   ⚠️  No primary image")
        elif 'cloudinary.com' in primary_image or 'res.cloudinary.com' in primary_image:
            cloudinary_count += 1
            print("   ✅ Cloudinary URL")
            # Check if it has optimization parameters
            if '/upload/q_auto' in primary_image or '/upload/w_' in primary_image:
                print("   ✅ Has optimization parameters")
        elif primary_image.startswith('http'):
            local_count += 1
            print("   ⚠️  External URL (not Cloudinary)")
        else:
            local_count += 1
            print("   ⚠️  Local/Relative URL")
        
        # Check images array if available
        if 'images' in product:
            images = product['images']
            print(f"   Total images: {len(images)}")
            for idx, img in enumerate(images[:3]):  # Check first 3 images
                img_url = img.get('image_url', '')
                if img_url:
                    if 'cloudinary.com' in img_url:
                        print(f"      Image {idx+1}: ✅ Cloudinary")
                    else:
                        print(f"      Image {idx+1}: ⚠️  {img_url[:60]}...")
    
    print("\n" + "=" * 80)
    print(f"Summary: {cloudinary_count} Cloudinary, {local_count} Local/Missing, {missing_count} Missing")

def test_image_accessibility(url):
    """Test if an image URL is accessible."""
    if not url or not url.startswith('http'):
        return False
    
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            return response.getcode() == 200
    except:
        return False

def main():
    print("🚀 Testing Cloudinary Image Configuration")
    print("=" * 80)
    
    # Test 1: Public API - Products list
    print("\n📋 Test 1: Public Products API")
    data = test_api_endpoint(f"{PUBLIC_API}?page_size=3")
    if data:
        analyze_image_urls(data)
    
    # Test 2: Check a specific product if available
    if data and 'results' in data and len(data['results']) > 0:
        first_product = data['results'][0]
        product_id = first_product.get('id')
        product_slug = first_product.get('slug')
        
        # Print full product structure for debugging
        print(f"\n📋 Test 2: Full Product Structure (ID: {product_id})")
        print(json.dumps(first_product, indent=2)[:1000])  # First 1000 chars
        
        if product_id:
            print(f"\n📋 Test 3: Specific Product by ID")
            product_data = test_api_endpoint(f"{PUBLIC_API}{product_id}/")
            if product_data:
                print("\nFull product response:")
                print(json.dumps(product_data, indent=2)[:1500])
                analyze_image_urls(product_data)
        
        if product_slug:
            print(f"\n📋 Test 4: Specific Product (slug: {product_slug})")
            product_data = test_api_endpoint(f"{PUBLIC_API}{product_slug}/")
            if product_data:
                analyze_image_urls(product_data)
        
        # Test image accessibility
        primary_image = first_product.get('primary_image')
        if primary_image and primary_image.startswith('http'):
            print(f"\n🔗 Test 5: Image Accessibility")
            print(f"   Testing: {primary_image[:80]}...")
            is_accessible = test_image_accessibility(primary_image)
            if is_accessible:
                print("   ✅ Image is accessible")
            else:
                print("   ❌ Image is NOT accessible")
    
    # Test 6: Check backend root
    print(f"\n📋 Test 6: Backend Root")
    root_data = test_api_endpoint(BACKEND_URL)
    
    print("\n" + "=" * 80)
    print("✅ Testing Complete")
    print("\n💡 Recommendations:")
    print("   1. If images are not Cloudinary URLs, check CLOUDINARY_* environment variables")
    print("   2. If images are Cloudinary URLs but not accessible, check Cloudinary dashboard")
    print("   3. Ensure DEFAULT_FILE_STORAGE is set to MediaCloudinaryStorage")
    print("   4. Check that images were uploaded AFTER Cloudinary was configured")

if __name__ == "__main__":
    main()
