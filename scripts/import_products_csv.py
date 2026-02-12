import csv
import json
import os
from typing import Any, Dict, Optional, Tuple

import requests


def parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def parse_json_list(value: Optional[str]) -> Optional[list]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


ALLOWED_PRODUCT_TYPES = {"PH", "LT", "TB", "AC"}
PRODUCT_TYPE_MAP = {"LA": "LT", "TA": "TB"}


def normalize_product_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().upper()
    cleaned = PRODUCT_TYPE_MAP.get(cleaned, cleaned)
    return cleaned if cleaned in ALLOWED_PRODUCT_TYPES else None


def normalize_meta_title(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:60]


def build_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "product_type": normalize_product_type(row.get("product_type")),
        "product_name": row.get("product_name"),
        "brand": row.get("brand"),
        "model_series": row.get("model_series"),
        "product_description": row.get("product_description"),
        "min_stock_threshold": parse_int(row.get("min_stock_threshold")),
        "reorder_point": parse_int(row.get("reorder_point")),
        "is_discontinued": parse_bool(row.get("is_discontinued")),
        "meta_title": normalize_meta_title(row.get("meta_title")),
        "meta_description": row.get("meta_description"),
        "keywords": row.get("keywords"),
        "product_highlights": parse_json_list(row.get("product_highlights")),
        "long_description": row.get("long_description"),
        "is_published": parse_bool(row.get("is_published")),
        "product_video_url": row.get("product_video_url"),
        "tag_ids": parse_json_list(row.get("tag_ids")),
        "brand_ids": parse_json_list(row.get("brand_ids")),
        "is_global": parse_bool(row.get("is_global")),
    }
    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def fetch_existing_names(api_base: str, token: str) -> Optional[set]:
    names = set()
    page = 1
    while True:
        try:
            response = requests.get(
                f"{api_base}/api/inventory/products/",
                headers={"Authorization": f"Token {token}"},
                params={"page": page, "page_size": 200},
                timeout=30,
            )
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        data = response.json()
        results = data.get("results", [])
        for item in results:
            name = item.get("product_name")
            if name:
                names.add(name)
        if not data.get("next"):
            break
        page += 1
    return names


def fetch_token(api_base: str, username: str, password: str) -> str:
    response = requests.post(
        f"{api_base}/api/auth/token/login/",
        json={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["token"]


def main() -> None:
    api_base = os.environ.get("API_BASE")
    token = os.environ.get("API_TOKEN")
    username = os.environ.get("API_USERNAME")
    password = os.environ.get("API_PASSWORD")
    csv_path = os.environ.get("CSV_PATH")
    skip_existing = os.environ.get("SKIP_EXISTING", "1") == "1"

    if not api_base or not csv_path:
        raise SystemExit(
            "Missing env vars. Set API_BASE and CSV_PATH, plus API_TOKEN or API_USERNAME/API_PASSWORD."
        )

    if not token and username and password:
        token = fetch_token(api_base, username, password)

    if not token:
        raise SystemExit("Missing API_TOKEN and no credentials provided.")

    created = 0
    skipped = 0
    failed = 0
    existing_names = fetch_existing_names(api_base, token) if skip_existing else None

    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = row.get("product_name") or "<unknown>"
            if skip_existing and existing_names is not None and name in existing_names:
                print(name, "skip: already exists")
                skipped += 1
                continue
            payload = build_payload(row)
            response = requests.post(
                f"{api_base}/api/inventory/products/",
                headers={"Authorization": f"Token {token}"},
                json=payload,
                timeout=30,
            )
            if response.status_code == 401 and username and password:
                token = fetch_token(api_base, username, password)
                response = requests.post(
                    f"{api_base}/api/inventory/products/",
                    headers={"Authorization": f"Token {token}"},
                    json=payload,
                    timeout=30,
                )
            print(name, response.status_code, response.text[:200])
            if response.status_code == 201:
                created += 1
                if existing_names is not None:
                    existing_names.add(name)
            elif response.status_code == 200:
                created += 1
                if existing_names is not None:
                    existing_names.add(name)
            else:
                failed += 1

    print(f"Done. created={created} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
