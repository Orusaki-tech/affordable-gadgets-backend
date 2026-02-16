#!/usr/bin/env python3
"""
Populate the database via API calls:
1. Create Products from products_list.csv (dedupe by product_name, set product_type PH/TB)
2. Create UnitAcquisitionSource from unique Source names in inventory_units.csv (source_type SU)
3. Create InventoryUnits from inventory_units.csv (exclude Colour and Grade; cost_of_unit=0; skip duplicate IMEI/serial or unknown product_name)

Usage:
  API_BASE=https://affordable-gadgets-backend.onrender.com \\
  API_USERNAME=admin API_PASSWORD=6foot7foot \\
  PRODUCTS_CSV=/path/to/products_list.csv UNITS_CSV=/path/to/inventory_units.csv \\
  python scripts/import_inventory_via_api.py

Or with defaults (admin/6foot7foot, frontend CSV paths):
  python scripts/import_inventory_via_api.py

Units only (products/sources already uploaded; use aligned inventory_units.csv):
  python scripts/import_inventory_via_api.py --units-only

Gap-fill: only create units for products that have no available units (out of stock); filter CSV to those products:
  python scripts/import_inventory_via_api.py --units-only-gap-fill

If requests time out on Render (Read timed out), use longer timeouts and more retries:
  REQUEST_TIMEOUT=180 UNIT_CREATE_TIMEOUT=360 UNIT_CREATE_RETRIES=5 python scripts/import_inventory_via_api.py --units-only
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import requests


# ---------------------------------------------------------------------------
# Config (env with defaults)
# ---------------------------------------------------------------------------
def _env(key: str, default: Optional[str] = None) -> str:
    v = os.environ.get(key, default)
    return (v or "").strip()


def _default_csv_dir() -> str:
    """Directory containing products_list.csv and inventory_units.csv (e.g. frontend repo)."""
    return _env("CSV_DIR") or os.path.join(
        os.path.dirname(__file__), "..", "..", "affordable-gadgets-frontend"
    )


def _default_products_csv() -> str:
    return os.path.join(_default_csv_dir(), "products_list.csv")


def _default_units_csv() -> str:
    return os.path.join(_default_csv_dir(), "inventory_units.csv")


API_BASE = _env("API_BASE", "https://affordable-gadgets-backend.onrender.com")
API_USERNAME = _env("API_USERNAME", "admin")
API_PASSWORD = _env("API_PASSWORD", "6foot7foot")
PRODUCTS_CSV = _env("PRODUCTS_CSV") or _default_products_csv()
UNITS_CSV = _env("UNITS_CSV") or _default_units_csv()
# Render free tier can take 60+ seconds to wake; use longer timeout and retries
REQUEST_TIMEOUT = int(_env("REQUEST_TIMEOUT", "120"))
REQUEST_RETRIES = max(1, int(_env("REQUEST_RETRIES", "3")))
# Unit creation POST can be very slow on cold Render; allow longer and more retries
UNIT_CREATE_TIMEOUT = int(_env("UNIT_CREATE_TIMEOUT", "300"))
UNIT_CREATE_RETRIES = max(1, int(_env("UNIT_CREATE_RETRIES", "5")))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _request_with_retries(
    method: str,
    url: str,
    retries: int = REQUEST_RETRIES,
    timeout: int = REQUEST_TIMEOUT,
    **kwargs: Any,
) -> requests.Response:
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = requests.request(method, url, timeout=timeout, **kwargs)
            # Retry on gateway/overload errors (common on Render free tier)
            if r.status_code in (502, 503) and attempt < retries - 1:
                wait = 10 if timeout >= 180 else 5
                time.sleep(wait)
                continue
            return r
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as e:
            last_err = e
            if attempt < retries - 1:
                wait = 10 if timeout >= 180 else 5
                time.sleep(wait)
                continue
            raise last_err
    raise last_err or RuntimeError("request failed")


def fetch_token(api_base: str, username: str, password: str) -> str:
    r = _request_with_retries(
        "POST",
        f"{api_base}/api/auth/token/login/",
        json={"username": username, "password": password},
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("token") or data.get("auth_token") or ""
    if not (token and str(token).strip()):
        raise ValueError("Login response had no 'token' or 'auth_token' key")
    return str(token).strip()


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Token {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helpers: paginated GET
# ---------------------------------------------------------------------------
def get_all_pages(
    api_base: str,
    token: str,
    url_path: str,
    page_size: int = 200,
    **extra_params: Any,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page = 1
    while True:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        params.update(extra_params)
        r = _request_with_retries(
            "GET",
            f"{api_base}{url_path}",
            headers=auth_headers(token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results, list):
            out.extend(results)
        if not isinstance(data, dict) or not data.get("next"):
            break
        page += 1
    return out


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
def normalize_product_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(re.split(r"\s+", str(name).strip()))


def infer_product_type(product_name: str) -> str:
    n = product_name.lower()
    if "ipad" in n:
        return "TB"
    return "PH"


def _normalize_csv_row_keys(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map BOM or 'Product Name' style headers to expected keys (product_name, Brand, Model)."""
    out = {}
    for key, value in row.items():
        k = key.strip().replace("\ufeff", "").strip()
        k_lower = k.lower().replace(" ", "_")
        if k_lower == "product_name":
            out["product_name"] = value
        elif k_lower == "brand":
            out["Brand"] = value
        elif k_lower == "model":
            out["Model"] = value
        else:
            out[key] = value
    if "product_name" not in out and row:
        out["product_name"] = list(row.values())[0] if row else ""
    if "Brand" not in out:
        out["Brand"] = row.get("Brand", row.get("brand", ""))
    if "Model" not in out:
        out["Model"] = row.get("Model", row.get("model", ""))
    return out


def load_products_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [_normalize_csv_row_keys(r) for r in rows]


def dedupe_products(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        name = normalize_product_name(row.get("product_name"))
        if not name or name in seen:
            continue
        seen.add(name)
        row = {**row, "product_name": name}
        out.append(row)
    return out


def fetch_existing_product_names(api_base: str, token: str) -> Set[str]:
    items = get_all_pages(api_base, token, "/api/inventory/products/")
    return {normalize_product_name(item.get("product_name")) for item in items if item.get("product_name")}


def fetch_products_name_to_id(api_base: str, token: str) -> Dict[str, int]:
    items = get_all_pages(api_base, token, "/api/inventory/products/")
    return {normalize_product_name(item.get("product_name")): item["id"] for item in items if item.get("product_name") and item.get("id")}


def fetch_product_id_to_brand(api_base: str, token: str) -> Dict[int, str]:
    """Product id -> brand string (for Apple vs non-Apple validation)."""
    items = get_all_pages(api_base, token, "/api/inventory/products/")
    return {item["id"]: (item.get("brand") or "").strip() for item in items if item.get("id") is not None}


def fetch_products_out_of_stock(
    api_base: str, token: str
) -> Tuple[Set[str], Dict[str, int], Dict[int, str]]:
    """Fetch products with no available units (out of stock). Returns (normalized_names_set, name_to_id, id_to_brand)."""
    items = get_all_pages(
        api_base, token, "/api/inventory/products/", stock_status="out_of_stock"
    )
    names: Set[str] = set()
    name_to_id: Dict[str, int] = {}
    id_to_brand: Dict[int, str] = {}
    for item in items:
        name = normalize_product_name(item.get("product_name"))
        if not name:
            continue
        pid = item.get("id")
        if pid is not None:
            names.add(name)
            name_to_id[name] = pid
            id_to_brand[pid] = (item.get("brand") or "").strip()
    return names, name_to_id, id_to_brand


def fetch_brands_name_to_id(api_base: str, token: str) -> Dict[str, int]:
    items = get_all_pages(api_base, token, "/api/inventory/brands/")
    by_name: Dict[str, int] = {}
    for b in items:
        bid = b.get("id")
        name = (b.get("name") or "").strip()
        code = (b.get("code") or "").strip()
        if bid is not None:
            if name:
                by_name[name] = bid
            if code:
                by_name[code] = bid
    return by_name


def create_product(
    api_base: str,
    token: str,
    row: Dict[str, Any],
    brand_ids_map: Dict[str, int],
    log: List[str],
    token_refresh: Optional[Any] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Returns (success, error_message, new_token_if_refreshed)."""
    product_name = normalize_product_name(row.get("product_name"))
    brand_str = (row.get("Brand") or "").strip()
    model_series = (row.get("Model") or "").strip() or "N/A"
    product_type = infer_product_type(product_name)
    payload: Dict[str, Any] = {
        "product_type": product_type,
        "product_name": product_name,
        "brand": brand_str or "N/A",
        "model_series": model_series,
    }
    brand_id = brand_ids_map.get(brand_str) if brand_str else None
    if brand_id is not None:
        payload["brand_ids"] = [brand_id]
    url = f"{api_base}/api/inventory/products/"
    r = _request_with_retries("POST", url, headers=auth_headers(token), json=payload)
    if r.status_code == 201:
        return True, None, None
    if r.status_code == 401 and token_refresh is not None:
        new_token = token_refresh()
        r2 = _request_with_retries("POST", url, headers=auth_headers(new_token), json=payload)
        if r2.status_code == 201:
            return True, None, new_token
        log.append(f"Product '{product_name}' -> 401, retry got {r2.status_code} {r2.text[:200]}")
        return False, r2.text[:300], new_token
    msg = r.text[:300]
    log.append(f"Product '{product_name}' -> {r.status_code} {msg}")
    return False, msg, None


# ---------------------------------------------------------------------------
# Sources (suppliers)
# ---------------------------------------------------------------------------
def fetch_sources_name_to_id(api_base: str, token: str) -> Dict[str, int]:
    items = get_all_pages(api_base, token, "/api/inventory/sources/")
    return {(item.get("name") or "").strip(): item["id"] for item in items if item.get("name") and item.get("id")}


def create_source(
    api_base: str,
    token: str,
    name: str,
    log: List[str],
    token_refresh: Optional[Any] = None,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Returns (success, source_id, new_token_if_refreshed)."""
    url = f"{api_base}/api/inventory/sources/"
    payload = {"source_type": "SU", "name": name, "phone_number": ""}
    r = _request_with_retries("POST", url, headers=auth_headers(token), json=payload)
    if r.status_code == 201:
        return True, r.json().get("id"), None
    if r.status_code == 401 and token_refresh is not None:
        new_token = token_refresh()
        r2 = _request_with_retries("POST", url, headers=auth_headers(new_token), json=payload)
        if r2.status_code == 201:
            return True, r2.json().get("id"), new_token
        log.append(f"Source '{name}' -> 401, retry got {r2.status_code}")
        return False, None, new_token
    log.append(f"Source '{name}' -> {r.status_code} {r.text[:200]}")
    return False, None, None


# ---------------------------------------------------------------------------
# Inventory units
# ---------------------------------------------------------------------------
def parse_date_dd_mm_yy(value: Optional[str]) -> Optional[str]:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    try:
        dt = datetime.strptime(s, "%d-%m-%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(s, "%d/%m/%y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None


def load_units_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def create_unit(
    api_base: str,
    token: str,
    row: Dict[str, Any],
    product_id: int,
    source_id: Optional[int],
    log: List[str],
    token_refresh: Optional[Any] = None,
    product_id_to_brand: Optional[Dict[int, str]] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Returns (success, error_message, new_token_if_refreshed)."""
    imei_raw = row.get("IMEI") or ""
    imei = str(imei_raw).strip()
    if not imei or imei.upper().startswith("E+"):
        imei = ""
    serial = (row.get("Serial Number") or "").strip()
    selling_price_raw = row.get("Selling Price") or "0"
    try:
        selling_price = int(float(str(selling_price_raw).replace(",", "")))
    except (ValueError, TypeError):
        selling_price = 0
    ram_raw = row.get("RAM (GB)") or "0"
    storage_raw = row.get("Storage (GB)") or "0"
    try:
        ram_val = int(float(ram_raw))
    except (ValueError, TypeError):
        ram_val = 0
    try:
        storage_val = int(float(storage_raw))
    except (ValueError, TypeError):
        storage_val = 0
    # API: non-Apple requires both ram_gb and storage_gb; Apple requires storage, ram must be blank/0
    is_apple = (product_id_to_brand or {}).get(product_id, "").strip().lower() == "apple"
    if is_apple:
        ram_gb = None if ram_val == 0 else ram_val
        storage_gb = storage_val if storage_val > 0 else 1
    else:
        ram_gb = ram_val if ram_val > 0 else 1
        storage_gb = storage_val if storage_val > 0 else 1
    date_sourced = parse_date_dd_mm_yy(row.get("Date"))
    condition = (row.get("Condition") or "N").strip().upper()[:1]
    if condition not in ("N", "R", "P", "D"):
        condition = "N"
    grade_raw = (row.get("Grade") or "").strip().upper()[:1]
    if grade_raw in ("A", "B"):
        grade = grade_raw
    elif grade_raw == "C":
        grade = "B"
    else:
        grade = "B"
    payload: Dict[str, Any] = {
        "product_template_id": product_id,
        "cost_of_unit": 0,
        "selling_price": selling_price,
        "source": "SU",
        "condition": condition,
        "quantity": 1,
        "available_online": True,
        "grade": grade,
    }
    if imei:
        payload["imei"] = imei[:15]
    if serial:
        payload["serial_number"] = serial[:100]
    if ram_gb is not None:
        payload["ram_gb"] = ram_gb
    payload["storage_gb"] = storage_gb
    if date_sourced:
        payload["date_sourced"] = date_sourced
    if source_id is not None:
        payload["acquisition_source_details_id"] = source_id
    url = f"{api_base}/api/inventory/units/"
    r = _request_with_retries(
        "POST",
        url,
        headers=auth_headers(token),
        json=payload,
        timeout=UNIT_CREATE_TIMEOUT,
        retries=UNIT_CREATE_RETRIES,
    )
    if r.status_code == 201:
        return True, None, None
    if r.status_code == 401 and token_refresh is not None:
        new_token = token_refresh()
        r2 = _request_with_retries(
            "POST",
            url,
            headers=auth_headers(new_token),
            json=payload,
            timeout=UNIT_CREATE_TIMEOUT,
            retries=UNIT_CREATE_RETRIES,
        )
        if r2.status_code == 201:
            return True, None, new_token
        log.append(f"Unit IMEI={imei or 'N/A'} -> 401, retry got {r2.status_code}")
        return False, r2.text[:300], new_token
    msg = r.text[:300]
    log.append(f"Unit IMEI={imei or 'N/A'} serial={serial or 'N/A'} -> {r.status_code} {msg}")
    return False, msg, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_units_only(
    token: str,
    refresh_token: Optional[Any],
    log: List[str],
) -> None:
    """Load units CSV, fetch product name->id and sources, create inventory units."""
    print("Loading units CSV...")
    unit_rows = load_units_csv(UNITS_CSV)
    print(f"  Rows: {len(unit_rows)}")
    source_names: Set[str] = set()
    for row in unit_rows:
        s = (row.get("Source") or "").strip()
        if s:
            source_names.add(s)
    print("Fetching sources (existing)...")
    sources_map = fetch_sources_name_to_id(API_BASE, token)
    print(f"  Sources: {len(sources_map)}")
    print("Fetching product name -> id map...")
    product_name_to_id = fetch_products_name_to_id(API_BASE, token)
    print(f"  Products on API: {len(product_name_to_id)}")
    product_id_to_brand = fetch_product_id_to_brand(API_BASE, token)

    created_units = 0
    skipped_no_product = 0
    skipped_duplicate = 0
    failed_units = 0
    seen_imei: Set[str] = set()
    seen_serial: Set[str] = set()
    for row in unit_rows:
        product_name = normalize_product_name(row.get("product_name"))
        product_id = product_name_to_id.get(product_name)
        if product_id is None:
            skipped_no_product += 1
            log.append(f"Unit skipped: no product for '{product_name}'")
            continue
        imei_raw = (row.get("IMEI") or "").strip()
        imei = str(imei_raw) if imei_raw and not str(imei_raw).upper().startswith("E+") else ""
        serial = (row.get("Serial Number") or "").strip()
        if imei and imei in seen_imei:
            skipped_duplicate += 1
            log.append(f"Unit skipped: duplicate IMEI {imei}")
            continue
        if serial and serial in seen_serial:
            skipped_duplicate += 1
            log.append(f"Unit skipped: duplicate serial {serial}")
            continue
        source_name = (row.get("Source") or "").strip()
        source_id = sources_map.get(source_name) if source_name else None
        ok, _, new_t = create_unit(
            API_BASE, token, row, product_id, source_id, log, token_refresh=refresh_token
        )
        if new_t is not None:
            token = new_t
        if ok:
            created_units += 1
            if imei:
                seen_imei.add(imei)
            if serial:
                seen_serial.add(serial)
        else:
            if "unique" in (log[-1] if log else "").lower() or "already exists" in (log[-1] if log else "").lower():
                skipped_duplicate += 1
            else:
                failed_units += 1
    print(f"Units: created={created_units} skipped_no_product={skipped_no_product} skipped_duplicate={skipped_duplicate} failed={failed_units}")


def run_units_only_gap_fill(
    token: str,
    refresh_token: Optional[Any],
    log: List[str],
) -> None:
    """Fetch products with no available units; filter units CSV to those products; create only those units."""
    print("Loading units CSV...")
    unit_rows = load_units_csv(UNITS_CSV)
    print(f"  Rows: {len(unit_rows)}")
    print("Fetching products with no available units (out of stock)...")
    names_set, product_name_to_id, product_id_to_brand = fetch_products_out_of_stock(
        API_BASE, token
    )
    print(f"  Out-of-stock products on API: {len(names_set)}")
    filtered_rows = [
        row
        for row in unit_rows
        if normalize_product_name(row.get("product_name")) in names_set
    ]
    print(f"  CSV rows matching those products: {len(filtered_rows)} (skipped {len(unit_rows) - len(filtered_rows)} others)")
    if not filtered_rows:
        print("No units to create. Done.")
        return
    source_names: Set[str] = set()
    for row in filtered_rows:
        s = (row.get("Source") or "").strip()
        if s:
            source_names.add(s)
    print("Fetching sources (existing)...")
    sources_map = fetch_sources_name_to_id(API_BASE, token)
    print(f"  Sources: {len(sources_map)}")

    created_units = 0
    skipped_no_product = 0
    skipped_duplicate = 0
    failed_units = 0
    seen_imei: Set[str] = set()
    seen_serial: Set[str] = set()
    for row in filtered_rows:
        product_name = normalize_product_name(row.get("product_name"))
        product_id = product_name_to_id.get(product_name)
        if product_id is None:
            skipped_no_product += 1
            log.append(f"Unit skipped: no product for '{product_name}'")
            continue
        imei_raw = (row.get("IMEI") or "").strip()
        imei = str(imei_raw) if imei_raw and not str(imei_raw).upper().startswith("E+") else ""
        serial = (row.get("Serial Number") or "").strip()
        if imei and imei in seen_imei:
            skipped_duplicate += 1
            log.append(f"Unit skipped: duplicate IMEI {imei}")
            continue
        if serial and serial in seen_serial:
            skipped_duplicate += 1
            log.append(f"Unit skipped: duplicate serial {serial}")
            continue
        source_name = (row.get("Source") or "").strip()
        source_id = sources_map.get(source_name) if source_name else None
        ok, _, new_t = create_unit(
            API_BASE,
            token,
            row,
            product_id,
            source_id,
            log,
            token_refresh=refresh_token,
            product_id_to_brand=product_id_to_brand,
        )
        if new_t is not None:
            token = new_t
        if ok:
            created_units += 1
            if imei:
                seen_imei.add(imei)
            if serial:
                seen_serial.add(serial)
        else:
            if "unique" in (log[-1] if log else "").lower() or "already exists" in (log[-1] if log else "").lower():
                skipped_duplicate += 1
            else:
                failed_units += 1
    print(f"Units: created={created_units} skipped_no_product={skipped_no_product} skipped_duplicate={skipped_duplicate} failed={failed_units}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import products and/or inventory units via API")
    parser.add_argument(
        "--units-only",
        action="store_true",
        help="Skip products and sources; only create inventory units from UNITS_CSV (use after products are already uploaded and CSV names are aligned)",
    )
    parser.add_argument(
        "--units-only-gap-fill",
        action="store_true",
        help="Only create units for products that have no available units (out of stock); filter CSV to those products.",
    )
    args = parser.parse_args()
    units_only = args.units_only
    units_only_gap_fill = args.units_only_gap_fill

    log: List[str] = []
    if units_only_gap_fill:
        print("Mode: units only — gap-fill (out-of-stock products only)")
    elif units_only:
        print("Mode: units only (products/sources already on API)")
    print("Products CSV:", os.path.abspath(PRODUCTS_CSV))
    print("Units CSV:   ", os.path.abspath(UNITS_CSV))
    if not units_only and not units_only_gap_fill and not os.path.isfile(PRODUCTS_CSV):
        print(f"Products CSV not found: {PRODUCTS_CSV}")
        sys.exit(1)
    if not os.path.isfile(UNITS_CSV):
        print(f"Units CSV not found: {UNITS_CSV}")
        sys.exit(1)
    print("Fetching token...")
    try:
        token = fetch_token(API_BASE, API_USERNAME, API_PASSWORD)
    except Exception as e:
        print("Login failed:", e)
        sys.exit(1)
    if not token:
        print("Login returned an empty token. Check API_USERNAME and API_PASSWORD.")
        sys.exit(1)
    print("Token OK (length %d)." % len(token))

    def refresh_token() -> str:
        t = fetch_token(API_BASE, API_USERNAME, API_PASSWORD)
        print("  (token refreshed after 401)")
        return t

    if units_only_gap_fill:
        run_units_only_gap_fill(token, refresh_token, log)
        for line in log[-50:]:
            print("  ", line)
        if len(log) > 50:
            print("  ... and", len(log) - 50, "more log lines")
        print("Done.")
        return
    if units_only:
        run_units_only(token, refresh_token, log)
        for line in log[-50:]:
            print("  ", line)
        if len(log) > 50:
            print("  ... and", len(log) - 50, "more log lines")
        print("Done.")
        return

    # 1) Brands map
    print("Fetching brands...")
    brand_ids_map = fetch_brands_name_to_id(API_BASE, token)
    print(f"  Brands: {len(brand_ids_map)} names/codes")

    # 2) Products
    print("Loading and deduping products CSV...")
    raw_product_rows = load_products_csv(PRODUCTS_CSV)
    product_rows = dedupe_products(raw_product_rows)
    print(f"  Rows in file: {len(raw_product_rows)}, unique products to consider: {len(product_rows)}")
    if len(product_rows) == 0 and len(raw_product_rows) > 0:
        first = raw_product_rows[0]
        print("  WARNING: 0 unique product names. First row keys:", list(first.keys())[:10])
        print("  First row product_name value:", repr(first.get("product_name", first.get("Product Name", "(missing)"))))
    existing_names = fetch_existing_product_names(API_BASE, token)
    created_products = 0
    skipped_products = 0
    failed_products = 0
    for row in product_rows:
        name = normalize_product_name(row.get("product_name"))
        if name in existing_names:
            skipped_products += 1
            continue
        ok, _, new_t = create_product(
            API_BASE, token, row, brand_ids_map, log, token_refresh=refresh_token
        )
        if new_t is not None:
            token = new_t
        if ok:
            created_products += 1
            existing_names.add(name)
        else:
            failed_products += 1
    print(f"Products: created={created_products} skipped={skipped_products} failed={failed_products}")

    # 3) Sources from units CSV
    print("Loading units CSV for unique sources...")
    unit_rows = load_units_csv(UNITS_CSV)
    source_names = set()
    for row in unit_rows:
        s = (row.get("Source") or "").strip()
        if s:
            source_names.add(s)
    sources_map = fetch_sources_name_to_id(API_BASE, token)
    created_sources = 0
    for name in source_names:
        if name in sources_map:
            continue
        ok, sid, new_t = create_source(API_BASE, token, name, log, token_refresh=refresh_token)
        if new_t is not None:
            token = new_t
        if ok and sid is not None:
            created_sources += 1
            sources_map[name] = sid
    print(f"Sources: created={created_sources} (total names: {len(source_names)})")

    # 4) Product name -> id for units
    print("Fetching product name -> id map...")
    product_name_to_id = fetch_products_name_to_id(API_BASE, token)
    product_id_to_brand = fetch_product_id_to_brand(API_BASE, token)

    # 5) Units
    created_units = 0
    skipped_no_product = 0
    skipped_duplicate = 0
    failed_units = 0
    seen_imei = set()
    seen_serial = set()
    for row in unit_rows:
        product_name = normalize_product_name(row.get("product_name"))
        product_id = product_name_to_id.get(product_name)
        if product_id is None:
            skipped_no_product += 1
            log.append(f"Unit skipped: no product for '{product_name}'")
            continue
        imei_raw = (row.get("IMEI") or "").strip()
        imei = str(imei_raw) if imei_raw and not str(imei_raw).upper().startswith("E+") else ""
        serial = (row.get("Serial Number") or "").strip()
        if imei and imei in seen_imei:
            skipped_duplicate += 1
            log.append(f"Unit skipped: duplicate IMEI {imei}")
            continue
        if serial and serial in seen_serial:
            skipped_duplicate += 1
            log.append(f"Unit skipped: duplicate serial {serial}")
            continue
        source_name = (row.get("Source") or "").strip()
        source_id = sources_map.get(source_name) if source_name else None
        ok, _, new_t = create_unit(
            API_BASE, token, row, product_id, source_id, log,
            token_refresh=refresh_token,
            product_id_to_brand=product_id_to_brand,
        )
        if new_t is not None:
            token = new_t
        if ok:
            created_units += 1
            if imei:
                seen_imei.add(imei)
            if serial:
                seen_serial.add(serial)
        else:
            if "unique" in (log[-1] if log else "").lower() or "already exists" in (log[-1] if log else "").lower():
                skipped_duplicate += 1
            else:
                failed_units += 1
    print(f"Units: created={created_units} skipped_no_product={skipped_no_product} skipped_duplicate={skipped_duplicate} failed={failed_units}")

    for line in log[-50:]:
        print("  ", line)
    if len(log) > 50:
        print("  ... and", len(log) - 50, "more log lines")
    print("Done.")


if __name__ == "__main__":
    main()
