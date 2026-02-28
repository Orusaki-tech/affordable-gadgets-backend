#!/usr/bin/env python3
"""
Check if the deployment is working and Cloudinary storage is being used.
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
    """Check promotion to see if images are now in Cloudinary."""
    print("=" * 80)
    print("CHECKING DEPLOYMENT STATUS")
    print("=" * 80)

    # Check public promotions
    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"

    print("\n📡 Checking promotions API...")

    try:
        req = urllib.request.Request(url)
        req.add_header("X-Brand-Code", "AFFORDABLE_GADGETS")

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode("utf-8"))

                if "results" in data and len(data["results"]) > 0:
                    print(f"\n✅ Found {len(data['results'])} promotions")

                    for i, promotion in enumerate(data["results"], 1):
                        print(f"\n--- Promotion {i} ---")
                        print(f"ID: {promotion.get('id')}")
                        print(f"Title: {promotion.get('title')}")

                        banner_image = promotion.get("banner_image")
                        banner_image_url = promotion.get("banner_image_url")

                        image_url = banner_image or banner_image_url

                        if image_url:
                            print(f"Banner Image URL: {image_url}")

                            # Check if it's Cloudinary
                            if "cloudinary.com" in image_url:
                                print("✅ URL is Cloudinary URL")

                                # Test if accessible
                                try:
                                    img_req = urllib.request.Request(image_url, method="HEAD")
                                    with urllib.request.urlopen(
                                        img_req, timeout=5, context=ssl_context
                                    ) as img_response:
                                        status = img_response.getcode()
                                        if status == 200:
                                            print(f"✅ Image is accessible! (Status: {status})")
                                            print("✅ UPLOAD IS WORKING!")
                                        else:
                                            print(f"❌ Image returned status: {status}")
                                except urllib.error.HTTPError as e:
                                    if e.code == 404:
                                        print("❌ Image not found in Cloudinary (404)")
                                        print("❌ Upload still not working - file doesn't exist")
                                    else:
                                        print(f"❌ Image error: HTTP {e.code}")
                            else:
                                print("❌ URL is NOT Cloudinary URL")
                                print("❌ Still using local storage")
                        else:
                            print("❌ No banner image URL")
                else:
                    print("\n⚠️  No promotions found")
            else:
                print(f"❌ API returned status: {response.getcode()}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_promotion()
