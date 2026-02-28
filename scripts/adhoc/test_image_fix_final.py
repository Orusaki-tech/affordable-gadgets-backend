#!/usr/bin/env python3
"""
Test promotion images after the .auto extension fix.
"""

import json
import ssl
import urllib.error
import urllib.request

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

BACKEND_URL = "https://affordable-gadgets-backend.onrender.com"


def test_image_url(url):
    """Test if an image URL is accessible."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            return {
                "accessible": True,
                "status": response.getcode(),
                "content_type": response.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as e:
        return {"accessible": False, "status": e.code}
    except Exception as e:
        return {"accessible": False, "error": str(e)}


def test_promotions():
    """Test promotion images."""
    print("=" * 80)
    print("TESTING PROMOTION IMAGES AFTER .AUTO FIX")
    print("=" * 80)

    url = f"{BACKEND_URL}/api/v1/public/promotions/?brand_code=AFFORDABLE_GADGETS"

    try:
        req = urllib.request.Request(url)
        req.add_header("X-Brand-Code", "AFFORDABLE_GADGETS")

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode("utf-8"))

                print(f"\n✅ API Response: {response.getcode()}")
                print(f"📊 Found {data.get('count', 0)} promotions\n")

                if "results" in data and len(data["results"]) > 0:
                    all_working = True
                    for promotion in data["results"]:
                        print("-" * 80)
                        print(f"📋 Promotion {promotion.get('id')}: {promotion.get('title')}")

                        banner_image = promotion.get("banner_image")

                        if banner_image:
                            print("\n🖼️  Banner Image URL:")
                            print(f"   {banner_image}")

                            # Check if URL has .auto extension
                            if ".auto" in banner_image:
                                print(
                                    "   ⚠️  URL still has '.auto' extension (fix may not be deployed yet)"
                                )
                                all_working = False
                            else:
                                print("   ✅ URL does NOT have '.auto' extension")

                            # Test if accessible
                            result = test_image_url(banner_image)
                            if result["accessible"]:
                                print(f"   ✅ Image is accessible! (Status: {result['status']})")
                                if "content_type" in result:
                                    print(f"   Content-Type: {result['content_type']}")
                            else:
                                print(
                                    f"   ❌ Not accessible: HTTP {result.get('status', result.get('error'))}"
                                )
                                all_working = False

                                # Try without .auto if present
                                if ".auto" in banner_image:
                                    url_no_auto = banner_image.replace(".auto", "")
                                    print("\n   🔄 Trying without .auto extension:")
                                    print(f"   {url_no_auto}")
                                    result2 = test_image_url(url_no_auto)
                                    if result2["accessible"]:
                                        print(
                                            f"   ✅ Works without .auto! (Status: {result2['status']})"
                                        )
                                        print(
                                            "   💡 Fix needs to be deployed to remove .auto from URLs"
                                        )
                        else:
                            print("\n   ❌ No banner image URL")
                            all_working = False

                    print("\n" + "=" * 80)
                    if all_working:
                        print("✅ ALL IMAGES ARE ACCESSIBLE!")
                    else:
                        print("❌ Some images are not accessible")
                    print("=" * 80)
                else:
                    print("⚠️  No promotions found")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_promotions()
