#!/usr/bin/env python3
"""
Test the image display fix by checking API responses and image accessibility.
"""
import urllib.request
import urllib.error
import ssl
import json
from urllib.parse import urlparse

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"

def test_image_url(url, description):
    """Test if an image URL is accessible."""
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            status = response.getcode()
            content_type = response.headers.get('Content-Type', 'unknown')
            return {
                'accessible': True,
                'status': status,
                'content_type': content_type,
                'error': None
            }
    except urllib.error.HTTPError as e:
        return {
            'accessible': False,
            'status': e.code,
            'content_type': None,
            'error': f'HTTP {e.code}'
        }
    except Exception as e:
        return {
            'accessible': False,
            'status': None,
            'content_type': None,
            'error': str(e)
        }

def analyze_cloudinary_url(url):
    """Analyze a Cloudinary URL to extract the public_id."""
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        
        # Find upload segment
        if 'upload' in path_parts:
            upload_idx = path_parts.index('upload')
            after_upload = path_parts[upload_idx + 1:]
            
            # Remove transformations if present (check first, before version)
            if after_upload and ',' in after_upload[0]:
                transformations = after_upload[0]
                after_upload = after_upload[1:]
            else:
                transformations = None
            
            # Remove version if present (after transformations)
            if after_upload and after_upload[0].startswith('v') and after_upload[0][1:].isdigit():
                version = after_upload[0]
                after_upload = after_upload[1:]
            else:
                version = None
            
            # Get public_id (everything remaining)
            public_id = '/'.join(after_upload)
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            return {
                'version': version,
                'transformations': transformations,
                'public_id': public_id,
                'has_media_prefix': public_id.startswith('media/')
            }
    except Exception as e:
        return {'error': str(e)}
    
    return {'error': 'Could not parse URL'}

def test_promotions_api():
    """Test the public promotions API."""
    print("=" * 80)
    print("TESTING PROMOTIONS API - IMAGE DISPLAY FIX")
    print("=" * 80)
    
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"
    
    print(f"\n📡 Fetching promotions from: {url}")
    
    try:
        req = urllib.request.Request(url)
        req.add_header('X-Brand-Code', 'AFFORDABLE_GADGETS')
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                
                print(f"✅ API Response: {response.getcode()}")
                print(f"📊 Found {data.get('count', 0)} promotions\n")
                
                if 'results' in data and len(data['results']) > 0:
                    for promotion in data['results']:
                        print("-" * 80)
                        print(f"📋 Promotion ID: {promotion.get('id')}")
                        print(f"   Title: {promotion.get('title')}")
                        
                        banner_image = promotion.get('banner_image')
                        banner_image_url = promotion.get('banner_image_url')
                        
                        image_url = banner_image or banner_image_url
                        
                        if image_url:
                            print(f"\n🖼️  Banner Image URL:")
                            print(f"   {image_url}")
                            
                            # Analyze the URL
                            analysis = analyze_cloudinary_url(image_url)
                            if 'error' not in analysis:
                                print(f"\n   📊 URL Analysis:")
                                print(f"      Version: {analysis.get('version', 'None')}")
                                print(f"      Transformations: {analysis.get('transformations', 'None')}")
                                print(f"      Public ID: {analysis.get('public_id')}")
                                print(f"      Has 'media/' prefix: {'✅ YES' if analysis.get('has_media_prefix') else '❌ NO'}")
                                
                                if not analysis.get('has_media_prefix'):
                                    # Try with media/ prefix
                                    public_id = analysis.get('public_id')
                                    corrected_url = image_url.replace(f"/{public_id}", f"/media/{public_id}")
                                    print(f"\n   🔄 Trying corrected URL (with media/ prefix):")
                                    print(f"      {corrected_url}")
                                    
                                    result = test_image_url(corrected_url, "Corrected URL")
                                    if result['accessible']:
                                        print(f"      ✅ Image is accessible! (Status: {result['status']})")
                                        print(f"      ✅ THIS IS THE CORRECT URL!")
                                    else:
                                        print(f"      ❌ Not accessible: {result['error']}")
                            
                            # Test the original URL
                            print(f"\n   🔍 Testing original URL:")
                            result = test_image_url(image_url, "Original URL")
                            if result['accessible']:
                                print(f"      ✅ Image is accessible! (Status: {result['status']})")
                                print(f"      Content-Type: {result['content_type']}")
                            else:
                                print(f"      ❌ Not accessible: {result['error']}")
                                
                                # Try alternative paths
                                print(f"\n   🔄 Trying alternative paths:")
                                
                                # Try with media/ prefix
                                if '/v1/' in image_url:
                                    alt_url1 = image_url.replace('/v1/promotions/', '/v1/media/promotions/')
                                    result1 = test_image_url(alt_url1, "With media/ prefix")
                                    if result1['accessible']:
                                        print(f"      ✅ With media/: {alt_url1}")
                                        print(f"         Status: {result1['status']}")
                                    else:
                                        print(f"      ❌ With media/: {result1['error']}")
                                
                                # Try without version
                                if '/v1/' in image_url:
                                    alt_url2 = image_url.replace('/v1/', '/')
                                    result2 = test_image_url(alt_url2, "Without version")
                                    if result2['accessible']:
                                        print(f"      ✅ Without version: {alt_url2}")
                                        print(f"         Status: {result2['status']}")
                                    else:
                                        print(f"      ❌ Without version: {result2['error']}")
                                
                                # Try with media/ and without version
                                if '/v1/' in image_url:
                                    alt_url3 = image_url.replace('/v1/promotions/', '/media/promotions/')
                                    result3 = test_image_url(alt_url3, "With media/ and no version")
                                    if result3['accessible']:
                                        print(f"      ✅ With media/ and no version: {alt_url3}")
                                        print(f"         Status: {result3['status']}")
                                    else:
                                        print(f"      ❌ With media/ and no version: {result3['error']}")
                        else:
                            print(f"\n   ❌ No banner image URL")
                else:
                    print("⚠️  No promotions found")
            else:
                print(f"❌ API returned status: {response.getcode()}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\n✅ If URL has 'media/' prefix and is accessible → Fix is working!")
    print("❌ If URL doesn't have 'media/' prefix → Fix needs to be deployed")
    print("❌ If URL has 'media/' but returns 404 → File might not be uploaded correctly")
    print("=" * 80)

if __name__ == "__main__":
    test_promotions_api()
