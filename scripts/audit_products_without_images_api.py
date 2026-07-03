#!/usr/bin/env python3
"""List published products missing primary_image via the public products API.

Usage:
  python scripts/audit_products_without_images_api.py
  python scripts/audit_products_without_images_api.py --base-url https://api.affordable-gadgetske.com
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter


def fetch_page(base_url: str, page: int, page_size: int) -> dict:
    params = urllib.parse.urlencode({"page": page, "page_size": page_size})
    url = f"{base_url.rstrip('/')}/api/v1/public/products/?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "1",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="https://affordable-gadgets-backend-i2s6.onrender.com",
        help="API base URL (default: Render backend)",
    )
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=50)
    args = parser.parse_args()

    no_image: list[dict] = []
    with_image = 0
    page = 1

    try:
        while page <= args.max_pages:
            data = fetch_page(args.base_url, page, args.page_size)
            results = data.get("results") or []
            if not results:
                break
            for product in results:
                primary = product.get("primary_image")
                if primary and str(primary).strip():
                    with_image += 1
                else:
                    no_image.append(
                        {
                            "slug": product.get("slug"),
                            "name": product.get("product_name"),
                            "brand": product.get("brand"),
                            "type": product.get("product_type"),
                        }
                    )
            if not data.get("next"):
                break
            page += 1
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} from API: {body[:200]}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"API unreachable: {exc.reason}", file=sys.stderr)
        return 1

    total = with_image + len(no_image)
    print(f"=== Products without primary_image ({args.base_url}) ===")
    print(f"total_scanned={total}")
    print(f"with_image={with_image}")
    print(f"without_image={len(no_image)}")
    print()
    print("By brand:")
    for brand, count in Counter(p["brand"] or "N/A" for p in no_image).most_common():
        print(f"  {brand}: {count}")
    print()
    print("By type:")
    for ptype, count in Counter(p["type"] or "N/A" for p in no_image).most_common():
        print(f"  {ptype}: {count}")
    print()
    print("Sample (first 40):")
    for p in no_image[:40]:
        print(f"  [{p['brand']}|{p['type']}] {p['name']} (slug={p['slug']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
