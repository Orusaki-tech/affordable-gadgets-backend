#!/usr/bin/env python3
"""
Check the actual result of the promotion upload to see what's happening.
"""

import json
import ssl
import urllib.error
import urllib.request

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"


def check_promotion():
    """Check promotion 1 to see what banner_image URL is returned."""
    print("=" * 80)
    print("CHECKING PROMOTION UPLOAD RESULT")
    print("=" * 80)

    # Check public promotions API (doesn't require auth)
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"

    print("\n📡 Checking public promotions API...")
    print(f"   URL: {url}")

    try:
        req = urllib.request.Request(url)
        req.add_header("X-Brand-Code", "AFFORDABLE_GADGETS")

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode("utf-8"))
                print("\n✅ API Response received")

                if "results" in data and len(data["results"]) > 0:
                    promotion = data["results"][0]
                    print("\n📋 Promotion Details:")
                    print(f"   ID: {promotion.get('id')}")
                    print(f"   Title: {promotion.get('title')}")
                    print(f"   Banner Image: {promotion.get('banner_image')}")
                    print(f"   Banner Image URL: {promotion.get('banner_image_url')}")

                    banner_url = promotion.get("banner_image") or promotion.get("banner_image_url")

                    if banner_url:
                        print("\n🔍 Testing banner image URL...")
                        print(f"   URL: {banner_url}")

                        # Test if image is accessible
                        try:
                            img_req = urllib.request.Request(banner_url, method="HEAD")
                            with urllib.request.urlopen(
                                img_req, timeout=5, context=ssl_context
                            ) as img_response:
                                status = img_response.getcode()
                                if status == 200:
                                    print(f"   ✅ Image is accessible! (Status: {status})")
                                    print("   ✅ Upload worked!")
                                else:
                                    print(f"   ❌ Image returned status: {status}")
                                    print("   ❌ Image not accessible")
                        except urllib.error.HTTPError as e:
                            print(f"   ❌ Image not accessible: HTTP {e.code}")
                            if e.code == 404:
                                print("   ❌ Image doesn't exist in Cloudinary!")
                        except Exception as e:
                            print(f"   ⚠️  Error checking image: {e}")
                    else:
                        print("\n❌ No banner image URL in response!")
                        print("   This means the image wasn't uploaded or saved")
                else:
                    print("\n⚠️  No promotions found in response")
                    print(f"   Response: {json.dumps(data, indent=2)}")
            else:
                print(f"❌ API returned status: {response.getcode()}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_promotion()
