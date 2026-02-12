import os
from typing import Dict, List, Optional, Tuple

import time
import requests


def fetch_token(api_base: str, username: str, password: str) -> str:
    response = requests.post(
        f"{api_base}/api/auth/token/login/",
        json={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["token"]


def get_with_retry(
    api_base: str,
    token_ref: Dict[str, str],
    username: Optional[str],
    password: Optional[str],
    params: Dict[str, int],
) -> requests.Response:
    for attempt in range(4):
        try:
            response = requests.get(
                f"{api_base}/api/inventory/products/",
                headers={"Authorization": f"Token {token_ref['token']}"},
                params=params,
                timeout=30,
            )
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
            continue
        if response.status_code == 401 and username and password:
            token_ref["token"] = fetch_token(api_base, username, password)
            response = requests.get(
                f"{api_base}/api/inventory/products/",
                headers={"Authorization": f"Token {token_ref['token']}"},
                params=params,
                timeout=30,
            )
        if response.status_code in {502, 503, 504}:
            if attempt == 3:
                response.raise_for_status()
            time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        return response
    raise RuntimeError("Failed to fetch products after retries.")


def delete_with_retry(
    api_base: str,
    token_ref: Dict[str, str],
    username: Optional[str],
    password: Optional[str],
    product_id: int,
) -> bool:
    for attempt in range(4):
        try:
            response = requests.delete(
                f"{api_base}/api/inventory/products/{product_id}/",
                headers={"Authorization": f"Token {token_ref['token']}"},
                timeout=30,
            )
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
            continue
        if response.status_code == 401 and username and password:
            token_ref["token"] = fetch_token(api_base, username, password)
            response = requests.delete(
                f"{api_base}/api/inventory/products/{product_id}/",
                headers={"Authorization": f"Token {token_ref['token']}"},
                timeout=30,
            )
        if response.status_code in {502, 503, 504}:
            if attempt == 3:
                response.raise_for_status()
            time.sleep(2 ** attempt)
            continue
        if response.status_code == 400:
            return False
        response.raise_for_status()
        return True
    return False


def fetch_all_products(
    api_base: str,
    token_ref: Dict[str, str],
    username: Optional[str],
    password: Optional[str],
) -> List[Dict]:
    products: List[Dict] = []
    page = 1
    while True:
        response = get_with_retry(
            api_base,
            token_ref,
            username,
            password,
            {"page": page, "page_size": 200},
        )
        data = response.json()
        results = data.get("results", [])
        products.extend(results)
        if not data.get("next"):
            break
        page += 1
    return products


def is_seed_product(product: Dict) -> bool:
    name = (product.get("product_name") or "").lower()
    slug = (product.get("slug") or "").lower()
    return "seed" in name or "seed" in slug


def find_duplicates(products: List[Dict]) -> List[Tuple[str, List[Dict]]]:
    buckets: Dict[str, List[Dict]] = {}
    for product in products:
        key = (product.get("product_name") or "").strip().lower()
        if not key:
            continue
        buckets.setdefault(key, []).append(product)
    return [(key, items) for key, items in buckets.items() if len(items) > 1]


def main() -> None:
    api_base = os.environ.get("API_BASE")
    username = os.environ.get("API_USERNAME")
    password = os.environ.get("API_PASSWORD")
    token = os.environ.get("API_TOKEN")

    if not api_base:
        raise SystemExit("Missing API_BASE.")

    if not token:
        if not username or not password:
            raise SystemExit("Missing API_TOKEN or API_USERNAME/API_PASSWORD.")
        token = fetch_token(api_base, username, password)

    token_ref = {"token": token}
    products = fetch_all_products(api_base, token_ref, username, password)

    seed_products = [p for p in products if is_seed_product(p)]
    duplicates = find_duplicates(products)

    delete_ids = set()

    for product in seed_products:
        if product.get("id") is not None:
            delete_ids.add(product["id"])

    for _, items in duplicates:
        items_sorted = sorted(items, key=lambda p: p.get("id") or 0)
        for product in items_sorted[1:]:
            if product.get("id") is not None:
                delete_ids.add(product["id"])

    deleted = 0
    for product_id in sorted(delete_ids):
        if delete_with_retry(api_base, token_ref, username, password, product_id):
            deleted += 1
            print(f"Deleted product id={product_id}")
        else:
            print(f"Skip delete product id={product_id} (server rejected)")

    print(
        f"Done. total_products={len(products)} "
        f"seed_matches={len(seed_products)} "
        f"duplicate_groups={len(duplicates)} "
        f"deleted={deleted}"
    )


if __name__ == "__main__":
    main()
