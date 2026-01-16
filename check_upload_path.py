#!/usr/bin/env python3
"""
Check the actual upload path issue - why is 'media/' being added?
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

def analyze_url():
    """Analyze the Cloudinary URL to understand the path issue."""
    print("=" * 80)
    print("ANALYZING UPLOAD PATH ISSUE")
    print("=" * 80)
    
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('X-Brand-Code', 'AFFORDABLE_GADGETS')
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                
                if 'results' in data and len(data['results']) > 0:
                    for promotion in data['results']:
                        if promotion.get('id') == 2:
                            banner_url = promotion.get('banner_image') or promotion.get('banner_image_url')
                            
                            if banner_url and 'cloudinary.com' in banner_url:
                                print(f"\n📋 Current URL:")
                                print(f"   {banner_url}")
                                
                                # Parse the URL
                                parsed = urlparse(banner_url)
                                path_parts = parsed.path.split('/')
                                
                                print(f"\n🔍 URL Analysis:")
                                print(f"   Path parts: {path_parts}")
                                
                                # Find upload segment
                                try:
                                    upload_idx = path_parts.index('upload')
                                    after_upload = path_parts[upload_idx + 1:]
                                    
                                    print(f"\n   After 'upload': {after_upload}")
                                    
                                    # Check for version
                                    if after_upload and after_upload[0].startswith('v'):
                                        version = after_upload[0]
                                        print(f"   Version: {version}")
                                        after_upload = after_upload[1:]
                                    
                                    # Check for transformations
                                    if after_upload and ',' in after_upload[0]:
                                        transformations = after_upload[0]
                                        print(f"   Transformations: {transformations}")
                                        after_upload = after_upload[1:]
                                    
                                    # Get public_id
                                    public_id = '/'.join(after_upload)
                                    if '.' in public_id:
                                        public_id = public_id.rsplit('.', 1)[0]
                                    
                                    print(f"\n   Public ID: {public_id}")
                                    
                                    # Check if it has 'media/' prefix
                                    if public_id.startswith('media/'):
                                        print(f"\n   ❌ PROBLEM: Public ID starts with 'media/'")
                                        print(f"   ❌ This is wrong - should be 'promotions/...'")
                                        
                                        # Try without media/ prefix
                                        correct_public_id = public_id.replace('media/', '', 1)
                                        print(f"\n   ✅ Correct Public ID should be: {correct_public_id}")
                                        
                                        # Build correct URL
                                        from urllib.parse import urlunparse
                                        correct_path = f"/image/upload/c_fill,h_1920,q_auto,w_1080/{correct_public_id}"
                                        correct_url = urlunparse((
                                            parsed.scheme,
                                            parsed.netloc,
                                            correct_path,
                                            parsed.params,
                                            parsed.query,
                                            parsed.fragment
                                        ))
                                        
                                        print(f"\n   ✅ Correct URL should be:")
                                        print(f"   {correct_url}")
                                        
                                        # Test correct URL
                                        print(f"\n   🔍 Testing correct URL...")
                                        try:
                                            img_req = urllib.request.Request(correct_url, method='HEAD')
                                            with urllib.request.urlopen(img_req, timeout=5, context=ssl_context) as img_response:
                                                if img_response.getcode() == 200:
                                                    print(f"   ✅ Correct URL works! Image exists at: {correct_public_id}")
                                                else:
                                                    print(f"   ❌ Correct URL also returns: {img_response.getcode()}")
                                        except urllib.error.HTTPError as e:
                                            print(f"   ❌ Correct URL error: HTTP {e.code}")
                                        
                                    else:
                                        print(f"\n   ✅ Public ID doesn't have 'media/' prefix")
                                        
                                except ValueError:
                                    print(f"   ⚠️  Could not parse URL structure")
                                
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    analyze_url()
