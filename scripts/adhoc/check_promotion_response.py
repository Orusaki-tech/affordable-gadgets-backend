#!/usr/bin/env python3
"""
Check what the promotion API is actually returning for banner images.
"""

import json
import ssl
import urllib.error
import urllib.request

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"


def check_promotion_api():
    """Check what the promotion API returns."""
    print("=" * 80)
    print("CHECKING PROMOTION API RESPONSE")
    print("=" * 80)

    # Check inventory promotions (we'll get 401 but can see structure)
    # Actually, let's check the public API which might work
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"

    print("\n📡 Checking public promotions API...")
    print(f"   URL: {url}")

    try:
        req = urllib.request.Request(url)
        req.add_header("X-Brand-Code", "AFFORDABLE_GADGETS")

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode("utf-8"))

                print("\n✅ API Response:")
                print(json.dumps(data, indent=2))

                if "results" in data and len(data["results"]) > 0:
                    print(f"\n📋 Found {len(data['results'])} promotions")
                    for i, promotion in enumerate(data["results"], 1):
                        print(f"\n--- Promotion {i} ---")
                        print(f"ID: {promotion.get('id')}")
                        print(f"Title: {promotion.get('title')}")
                        print(f"Banner Image: {promotion.get('banner_image')}")
                        print(f"Banner Image URL: {promotion.get('banner_image_url')}")

                        # Check if it's a Cloudinary URL
                        banner = promotion.get("banner_image") or promotion.get("banner_image_url")
                        if banner:
                            if "cloudinary.com" in banner:
                                print("✅ URL is Cloudinary URL")
                            else:
                                print(f"❌ URL is NOT Cloudinary URL: {banner}")
                        else:
                            print("❌ No banner image URL")
                else:
                    print("\n⚠️  No promotions found")
            else:
                print(f"   Status: {response.getcode()}")
    except Exception as e:
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_promotion_api()
