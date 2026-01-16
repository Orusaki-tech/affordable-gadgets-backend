#!/usr/bin/env python3
"""
Test script to check Promotion images from the deployed API.
"""
import urllib.request
import urllib.error
import ssl
import json

# Create SSL context
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def test_endpoint(url, headers=None):
    """Test an API endpoint."""
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
                data = json.loads(response.read().decode('utf-8'))
                return data
            else:
                data = response.read().decode('utf-8')
                print(f"   Error Response: {data[:300]}")
                return None
    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP Error: {e.code} - {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            print(f"   Error body: {error_body[:200]}")
        except:
            pass
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

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

def analyze_promotion_images(data):
    """Analyze promotion images in the API response."""
    if not data:
        return
    
    print("\n📸 Promotion Image Analysis:")
    print("=" * 80)
    
    # Check if it's a paginated response
    if 'results' in data:
        promotions = data['results']
        print(f"Found {len(promotions)} promotions in response")
    elif isinstance(data, list):
        promotions = data
        print(f"Found {len(promotions)} promotions in response")
    else:
        promotions = [data]
        print("Single promotion response")
    
    cloudinary_count = 0
    local_count = 0
    missing_count = 0
    accessible_count = 0
    
    for promo in promotions[:10]:  # Check first 10 promotions
        promo_title = promo.get('title', 'Unknown')
        banner_image = promo.get('banner_image')
        banner_image_url = promo.get('banner_image_url')
        
        print(f"\n🎯 Promotion: {promo_title}")
        print(f"   ID: {promo.get('id')}")
        print(f"   Banner Image Field: {banner_image}")
        print(f"   Banner Image URL Field: {banner_image_url}")
        
        # Use banner_image_url if available, otherwise banner_image
        image_url = banner_image_url or banner_image
        
        if not image_url:
            missing_count += 1
            print("   ⚠️  No banner image")
        elif 'cloudinary.com' in image_url or 'res.cloudinary.com' in image_url:
            cloudinary_count += 1
            print("   ✅ Cloudinary URL")
            # Check if it has optimization parameters
            if '/upload/q_auto' in image_url or '/upload/w_' in image_url:
                print("   ✅ Has optimization parameters")
            
            # Test accessibility
            if test_image_accessibility(image_url):
                accessible_count += 1
                print("   ✅ Image is accessible")
            else:
                print("   ❌ Image is NOT accessible")
        elif image_url.startswith('http'):
            local_count += 1
            print(f"   ⚠️  External URL (not Cloudinary): {image_url[:80]}...")
        else:
            local_count += 1
            print(f"   ⚠️  Local/Relative URL: {image_url[:80]}...")
    
    print("\n" + "=" * 80)
    print(f"Summary: {cloudinary_count} Cloudinary, {local_count} Local/Missing, {missing_count} Missing, {accessible_count} Accessible")

def main():
    print("🚀 Testing Promotion Images")
    print("=" * 80)
    
    # Try common brand codes (from frontend config)
    brand_codes_to_try = ['AFFORDABLE_GADGETS', 'AFFORDABLE', 'SHWARI']
    
    # Test 1: Public Promotions API with brand headers
    print("\n📋 Test 1: Public Promotions API (with brand headers)")
    public_data = None
    used_brand_code = None
    
    for brand_code in brand_codes_to_try:
        print(f"\n   Trying brand code: {brand_code}")
        headers = {'X-Brand-Code': brand_code}
        data = test_endpoint(f"{BACKEND_URL}/api/v1/public/promotions/", headers=headers)
        if data and 'results' in data and len(data['results']) > 0:
            public_data = data
            used_brand_code = brand_code
            print(f"   ✅ Found promotions with brand code: {brand_code}")
            break
        elif data:
            print(f"   ⚠️  No promotions found for brand: {brand_code}")
    
    if public_data:
        analyze_promotion_images(public_data)
    else:
        print("\n   ⚠️  No promotions found with any brand code")
        print("   This could mean:")
        print("     1. No promotions exist in the database")
        print("     2. No active promotions (check is_active and date range)")
        print("     3. Brand code doesn't match any promotions")
        print("     4. Promotions exist but are not assigned to tested brands")
    
    # Test 2: Inventory Promotions API (might need auth)
    print("\n📋 Test 2: Inventory Promotions API")
    inventory_data = test_endpoint(f"{BACKEND_URL}/api/inventory/promotions/")
    if inventory_data:
        analyze_promotion_images(inventory_data)
    else:
        print("   ⚠️  Inventory API requires authentication or returned no data")
    
    # Test 3: Check specific promotion if available
    if public_data and 'results' in public_data and len(public_data['results']) > 0:
        first_promo = public_data['results'][0]
        promo_id = first_promo.get('id')
        
        if promo_id and used_brand_code:
            print(f"\n📋 Test 3: Specific Promotion (ID: {promo_id})")
            headers = {'X-Brand-Code': used_brand_code}
            promo_data = test_endpoint(f"{BACKEND_URL}/api/v1/public/promotions/{promo_id}/", headers=headers)
            if promo_data:
                print("\nFull promotion response:")
                print(json.dumps(promo_data, indent=2)[:1000])
                analyze_promotion_images(promo_data)
    
    print("\n" + "=" * 80)
    print("✅ Testing Complete")
    print("\n💡 Next Steps:")
    print("   1. If promotions have no images, upload banner images via admin")
    print("   2. Verify Cloudinary credentials are set in Render")
    print("   3. Check Cloudinary dashboard to confirm uploads")
    print("   4. Test image display on frontend websites")

if __name__ == "__main__":
    main()
