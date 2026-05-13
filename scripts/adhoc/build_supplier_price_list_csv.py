"""
One-off script that materialises ``inventory/data/supplier_price_list_2026_05_04.csv``
and ``inventory/data/supplier_price_list_2026_05_04_issues.csv`` from the
supplier price list dated 4 May 2026.

Re-run any time you need to regenerate the CSV after correcting data or adding
new supplier rows. The CSV is the source of truth for
``python manage.py import_supplier_price_list``.

Usage:
    python scripts/adhoc/build_supplier_price_list_csv.py
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "inventory" / "data"
CLEAN_CSV = DATA_DIR / "supplier_price_list_2026_05_04.csv"
ISSUES_CSV = DATA_DIR / "supplier_price_list_2026_05_04_issues.csv"

# --- Description templates ----------------------------------------------------
APPLE_DUBAI_DESC = (
    "Non-activated. Sourced from Dubai (stock dated 4 May 2026). "
    "Warranty: Apple service center only — no shop warranty."
)
APPLE_OFFICIAL_DESC = (
    "Non-activated. Warranty: 24 months device + 6 months screen warranty."
)
APPLE_OFFICIAL_NON_PHONE_DESC = (
    "Warranty: 24 months device + 6 months screen warranty."
)
LOCKED_NO_WARRANTY_DESC = (
    "Carrier-locked phone. No warranty. Sourced from Dubai (stock dated 4 May 2026)."
)
SAMSUNG_AC_DESC = "No warranty. Sourced from Dubai (stock dated 4 May 2026)."


CATEGORY_WORD = {"PH": "phone", "TB": "tablet", "LT": "laptop", "AC": "accessory"}


@dataclass
class Item:
    product_type: str  # PH / TB / LT / AC
    brand: str
    model_series: str
    product_name: str
    description: str
    ref_cost: int
    ref_sell: int | None = None
    keywords_extra: list[str] = field(default_factory=list)


def _row(item: Item) -> dict:
    category = CATEGORY_WORD[item.product_type]
    meta_title = item.product_name[:60]
    meta_description = (
        f"Explore the {item.product_name} by {item.brand}, "
        f"a high-quality {category}."
    )[:160]
    long_description = (
        f"Discover the {item.product_name} from {item.brand}. "
        f"This {category} offers exceptional performance and features."
    )
    keyword_tokens: list[str] = []
    seen = set()
    for token in [item.brand.lower(), item.model_series.lower(), category, item.product_name.lower(), *item.keywords_extra]:
        clean = token.strip()
        if clean and clean not in seen:
            seen.add(clean)
            keyword_tokens.append(clean)
    return {
        "product_type": item.product_type,
        "product_name": item.product_name,
        "product_description": item.description,
        "brand": item.brand,
        "model_series": item.model_series,
        "min_stock_threshold": 5,
        "reorder_point": 10,
        "is_discontinued": "False",
        "meta_title": meta_title,
        "meta_description": meta_description,
        "slug": "",
        "keywords": ", ".join(keyword_tokens),
        "og_image": "",
        "product_highlights": "[]",
        "long_description": long_description,
        "is_published": "True",
        "product_video_url": "",
        "product_video_file": "",
        "tag_ids": "[]",
        "brand_ids": "[]",
        "is_global": "False",
        "ref_cost_kes": item.ref_cost,
        "ref_sell_kes": "" if item.ref_sell is None else item.ref_sell,
    }


# --- A. Apple phones — Dubai E-SIM (15) ---------------------------------------
APPLE_DUBAI_ESIM: list[Item] = [
    Item("PH", "Apple", "16 128GB E-SIM (Dubai)", "iPhone 16 128GB E-SIM (Dubai)", APPLE_DUBAI_DESC, 85000, 90000),
    Item("PH", "Apple", "16 Pro 256GB E-SIM (Dubai)", "iPhone 16 Pro 256GB E-SIM (Dubai)", APPLE_DUBAI_DESC, 138000, 145000),
    Item("PH", "Apple", "17 256GB E-SIM (Dubai)", "iPhone 17 256GB E-SIM (Dubai)", APPLE_DUBAI_DESC, 104000, 110000),
    Item("PH", "Apple", "17 512GB E-SIM (Dubai)", "iPhone 17 512GB E-SIM (Dubai)", APPLE_DUBAI_DESC, 132000, 138000),
    Item("PH", "Apple", "17 Air 256GB E-SIM (Dubai)", "iPhone 17 Air 256GB E-SIM (Dubai)", APPLE_DUBAI_DESC, 116000, 120000),
    Item("PH", "Apple", "17 Air 256GB E-SIM White/Gold (Dubai)", "iPhone 17 Air 256GB E-SIM White/Gold (Dubai)", APPLE_DUBAI_DESC, 120000, 125000),
    Item("PH", "Apple", "17 Pro 256GB E-SIM (Dubai)", "iPhone 17 Pro 256GB E-SIM (Dubai)", APPLE_DUBAI_DESC, 161500, 166000),
    Item("PH", "Apple", "17 Pro 512GB E-SIM Orange/Blue (Dubai)", "iPhone 17 Pro 512GB E-SIM Orange/Blue (Dubai)", APPLE_DUBAI_DESC, 181500, 187500),
    Item("PH", "Apple", "17 Pro 512GB E-SIM Silver (Dubai)", "iPhone 17 Pro 512GB E-SIM Silver (Dubai)", APPLE_DUBAI_DESC, 185000, 193000),
    Item("PH", "Apple", "17 Pro 1TB E-SIM (Dubai)", "iPhone 17 Pro 1TB E-SIM (Dubai)", APPLE_DUBAI_DESC, 208500, 216000),
    Item("PH", "Apple", "17 Pro Max 256GB E-SIM Orange/Blue (Dubai)", "iPhone 17 Pro Max 256GB E-SIM Orange/Blue (Dubai)", APPLE_DUBAI_DESC, 174500, 179500),
    Item("PH", "Apple", "17 Pro Max 256GB E-SIM Silver (Dubai)", "iPhone 17 Pro Max 256GB E-SIM Silver (Dubai)", APPLE_DUBAI_DESC, 176000, 182000),
    Item("PH", "Apple", "17 Pro Max 512GB E-SIM Orange/Blue (Dubai)", "iPhone 17 Pro Max 512GB E-SIM Orange/Blue (Dubai)", APPLE_DUBAI_DESC, 200500, 207000),
    Item("PH", "Apple", "17 Pro Max 512GB E-SIM Silver (Dubai)", "iPhone 17 Pro Max 512GB E-SIM Silver (Dubai)", APPLE_DUBAI_DESC, 208000, 216000),
    Item("PH", "Apple", "17 Pro Max 1TB E-SIM (Dubai)", "iPhone 17 Pro Max 1TB E-SIM (Dubai)", APPLE_DUBAI_DESC, 216000, 228500),
]

# --- B. Apple phones — Dubai SIM (26) -----------------------------------------
APPLE_DUBAI_SIM: list[Item] = [
    Item("PH", "Apple", "14 128GB SIM (Dubai)", "iPhone 14 128GB SIM (Dubai)", APPLE_DUBAI_DESC, 73000, 78000),
    Item("PH", "Apple", "14 256GB SIM (Dubai)", "iPhone 14 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 78500, 83500),
    Item("PH", "Apple", "15 128GB SIM (Dubai)", "iPhone 15 128GB SIM (Dubai)", APPLE_DUBAI_DESC, 81000, 86000),
    Item("PH", "Apple", "15 256GB SIM (Dubai)", "iPhone 15 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 94500, 98500),
    Item("PH", "Apple", "15 Plus 256GB SIM (Dubai)", "iPhone 15 Plus 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 106000, 112000),
    Item("PH", "Apple", "15 Pro Max 256GB SIM (Dubai)", "iPhone 15 Pro Max 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 133000, 142000),
    Item("PH", "Apple", "16E 128GB SIM (Dubai)", "iPhone 16E 128GB SIM (Dubai)", APPLE_DUBAI_DESC, 73000, 78000),
    Item("PH", "Apple", "16E 256GB SIM (Dubai)", "iPhone 16E 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 81000, 86000),
    Item("PH", "Apple", "16 128GB SIM (Dubai)", "iPhone 16 128GB SIM (Dubai)", APPLE_DUBAI_DESC, 91000, 96000),
    Item("PH", "Apple", "16 256GB SIM (Dubai)", "iPhone 16 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 102000, 110000),
    Item("PH", "Apple", "16 Plus 128GB SIM (Dubai)", "iPhone 16 Plus 128GB SIM (Dubai)", APPLE_DUBAI_DESC, 106000, 116000),
    Item("PH", "Apple", "16 Plus 256GB SIM (Dubai)", "iPhone 16 Plus 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 117500, 126000),
    Item("PH", "Apple", "16 Pro 128GB SIM (Dubai)", "iPhone 16 Pro 128GB SIM (Dubai)", APPLE_DUBAI_DESC, 127000, 137000),
    Item("PH", "Apple", "16 Pro Max 256GB SIM Desert (Dubai)", "iPhone 16 Pro Max 256GB SIM Desert (Dubai)", APPLE_DUBAI_DESC, 151000, 160000),
    Item("PH", "Apple", "16 Pro Max 256GB SIM Black (Dubai)", "iPhone 16 Pro Max 256GB SIM Black (Dubai)", APPLE_DUBAI_DESC, 156000, 166000),
    Item("PH", "Apple", "16 Pro Max 512GB SIM (Dubai)", "iPhone 16 Pro Max 512GB SIM (Dubai)", APPLE_DUBAI_DESC, 176000, 186000),
    Item("PH", "Apple", "17 256GB SIM (Dubai)", "iPhone 17 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 109500, 116500),
    Item("PH", "Apple", "17 512GB SIM (Dubai)", "iPhone 17 512GB SIM (Dubai)", APPLE_DUBAI_DESC, 140000, 148000),
    Item("PH", "Apple", "17 Pro 256GB SIM (Dubai)", "iPhone 17 Pro 256GB SIM (Dubai)", APPLE_DUBAI_DESC, 171500, 181500),
    Item("PH", "Apple", "17 Pro 256GB SIM Silver (Dubai)", "iPhone 17 Pro 256GB SIM Silver (Dubai)", APPLE_DUBAI_DESC, 172000, 182000),
    Item("PH", "Apple", "17 Pro 512GB SIM (Dubai)", "iPhone 17 Pro 512GB SIM (Dubai)", APPLE_DUBAI_DESC, 200000, 212000),
    Item("PH", "Apple", "17 Pro 1TB SIM (Dubai)", "iPhone 17 Pro 1TB SIM (Dubai)", APPLE_DUBAI_DESC, 228000, 240000),
    Item("PH", "Apple", "17 Pro Max 256GB SIM Blue/Orange (Dubai)", "iPhone 17 Pro Max 256GB SIM Blue/Orange (Dubai)", APPLE_DUBAI_DESC, 187000, 195000),
    Item("PH", "Apple", "17 Pro Max 256GB SIM Silver (Dubai)", "iPhone 17 Pro Max 256GB SIM Silver (Dubai)", APPLE_DUBAI_DESC, 189000, 197000),
    Item("PH", "Apple", "17 Pro Max 512GB SIM (Dubai)", "iPhone 17 Pro Max 512GB SIM (Dubai)", APPLE_DUBAI_DESC, 217000, 228000),
    Item("PH", "Apple", "17 Pro Max 1TB SIM (Dubai)", "iPhone 17 Pro Max 1TB SIM (Dubai)", APPLE_DUBAI_DESC, 250500, 270000),
]

# --- C. Apple phones — Official 24m (5) ---------------------------------------
APPLE_OFFICIAL: list[Item] = [
    Item("PH", "Apple", "16 128GB SIM (Official)", "iPhone 16 128GB SIM (Official)", APPLE_OFFICIAL_DESC, 94500, 100000),
    Item("PH", "Apple", "16 Plus 128GB SIM (Official)", "iPhone 16 Plus 128GB SIM (Official)", APPLE_OFFICIAL_DESC, 104500, 115000),
    Item("PH", "Apple", "17 256GB SIM (Official)", "iPhone 17 256GB SIM (Official)", APPLE_OFFICIAL_DESC, 116000, 125000),
    Item("PH", "Apple", "17E 256GB SIM (Official)", "iPhone 17E 256GB SIM (Official)", APPLE_OFFICIAL_DESC, 89500, 95500),
    Item("PH", "Apple", "17 Pro Max 256GB SIM (Official)", "iPhone 17 Pro Max 256GB SIM (Official)", APPLE_OFFICIAL_DESC, 188000, 198000),
]

# --- D. Apple iPads (13) ------------------------------------------------------
APPLE_IPADS: list[Item] = [
    Item("TB", "Apple", "iPad mini 7 128GB WiFi", "iPad mini 7 128GB WiFi", APPLE_OFFICIAL_NON_PHONE_DESC, 61000, 65500),
    Item("TB", "Apple", "iPad 10th gen 64GB Cellular", "iPad 10th gen 64GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 51000, 55000),
    Item("TB", "Apple", "iPad 11th gen 128GB Cellular", "iPad 11th gen 128GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 64500, 68500),
    Item("TB", "Apple", "iPad 11th gen 256GB WiFi", "iPad 11th gen 256GB WiFi", APPLE_OFFICIAL_NON_PHONE_DESC, 64000, 68000),
    Item("TB", "Apple", "iPad 11th gen 256GB Cellular", "iPad 11th gen 256GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 87000, 92000),
    Item("TB", "Apple", "iPad Air M3 128GB WiFi", "iPad Air M3 128GB WiFi", APPLE_OFFICIAL_NON_PHONE_DESC, 76000, 80000),
    Item("TB", "Apple", "iPad Air M3 128GB Cellular", "iPad Air M3 128GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 94000, 100000),
    Item("TB", "Apple", "iPad Air M3 256GB Cellular", "iPad Air M3 256GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 117000, 125000),
    Item("TB", "Apple", "iPad Pro M4 11 inch 256GB WiFi", "iPad Pro M4 11 inch 256GB WiFi", APPLE_OFFICIAL_NON_PHONE_DESC, 118000, 128000),
    Item("TB", "Apple", "iPad Pro M4 11 inch 256GB Cellular", "iPad Pro M4 11 inch 256GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 128000, 136000),
    Item("TB", "Apple", "iPad Pro M4 13 inch 256GB Cellular", "iPad Pro M4 13 inch 256GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 137000, 147000),
    Item("TB", "Apple", "iPad Pro M5 11 inch 256GB Cellular", "iPad Pro M5 11 inch 256GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 145500, 160000),
    Item("TB", "Apple", "iPad Pro M5 13 inch 256GB Cellular", "iPad Pro M5 13 inch 256GB Cellular", APPLE_OFFICIAL_NON_PHONE_DESC, 159000, 165000),
]

# --- E. Apple Macs / iMac (8) -------------------------------------------------
APPLE_MACS: list[Item] = [
    Item("LT", "Apple", "MacBook Air M1 13 inch 256GB 8GB", "MacBook Air M1 13 inch 256GB 8GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 71500, 80000),
    Item("LT", "Apple", "MacBook Air M2 13 inch 256GB 16GB", "MacBook Air M2 13 inch 256GB 16GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 100000, 108000),
    Item("LT", "Apple", "MacBook Air M3 13 inch 512GB 16GB", "MacBook Air M3 13 inch 512GB 16GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 128000, 138000),
    Item("LT", "Apple", "MacBook Air M4 13 inch 256GB 16GB", "MacBook Air M4 13 inch 256GB 16GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 138000, 150000),
    Item("LT", "Apple", "MacBook Air M5 13 inch 512GB 16GB", "MacBook Air M5 13 inch 512GB 16GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 149000, 165000),
    Item("LT", "Apple", "MacBook Pro M4 14.2 inch 512GB 16GB", "MacBook Pro M4 14.2 inch 512GB 16GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 198000, 218000),
    Item("LT", "Apple", "MacBook Pro M5 14.2 inch 512GB 16GB", "MacBook Pro M5 14.2 inch 512GB 16GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 211000, 230000),
    Item("LT", "Apple", "iMac M1 24 inch 256GB 8GB", "iMac M1 24 inch 256GB 8GB RAM", APPLE_OFFICIAL_NON_PHONE_DESC, 130000, 145000),
]

# --- F. Apple accessories (12) -----------------------------------------------
APPLE_ACCESSORIES: list[Item] = [
    Item("AC", "Apple", "Magic Mouse", "Apple Magic Mouse", APPLE_OFFICIAL_NON_PHONE_DESC, 10000, 13000),
    Item("AC", "Apple", "AirPods 4", "AirPods 4", APPLE_OFFICIAL_NON_PHONE_DESC, 15500, 18500),
    Item("AC", "Apple", "AirPods Pro 2", "AirPods Pro 2", APPLE_OFFICIAL_NON_PHONE_DESC, 25000, 27500),
    Item("AC", "Apple", "AirPods Pro 3", "AirPods Pro 3", APPLE_OFFICIAL_NON_PHONE_DESC, 31000, 32500),
    Item("AC", "Apple", "AirPods Max USB-C", "AirPods Max (USB-C)", APPLE_OFFICIAL_NON_PHONE_DESC, 66000, 70000),
    Item("AC", "Apple", "Watch SE 2 44mm", "Apple Watch SE 2 44mm", APPLE_OFFICIAL_NON_PHONE_DESC, 28500, 31500),
    Item("AC", "Apple", "Watch SE 3 40mm", "Apple Watch SE 3 40mm", APPLE_OFFICIAL_NON_PHONE_DESC, 33000, 36000),
    Item("AC", "Apple", "Watch SE 3 44mm", "Apple Watch SE 3 44mm", APPLE_OFFICIAL_NON_PHONE_DESC, 36000, 39000),
    Item("AC", "Apple", "Watch Series 10 46mm", "Apple Watch Series 10 46mm", APPLE_OFFICIAL_NON_PHONE_DESC, 43000, 46000),
    Item("AC", "Apple", "Watch Series 11 42mm", "Apple Watch Series 11 42mm", APPLE_OFFICIAL_NON_PHONE_DESC, 44000, 47000),
    Item("AC", "Apple", "Watch Series 11 46mm", "Apple Watch Series 11 46mm", APPLE_OFFICIAL_NON_PHONE_DESC, 50000, 53500),
    Item("AC", "Apple", "Watch Ultra 3 2025 49mm", "Apple Watch Ultra 3 (2025) 49mm", APPLE_OFFICIAL_NON_PHONE_DESC, 100000, 110000),
]

# --- G. Samsung phones (26) ---------------------------------------------------
SAMSUNG_PHONES: list[Item] = [
    Item("PH", "Samsung", "A16 128GB 4GB", "Samsung Galaxy A16 128GB 4GB RAM", LOCKED_NO_WARRANTY_DESC, 15500, 18000),
    Item("PH", "Samsung", "A16 256GB 8GB", "Samsung Galaxy A16 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 22200, 24500),
    Item("PH", "Samsung", "A26 128GB 6GB", "Samsung Galaxy A26 128GB 6GB RAM", LOCKED_NO_WARRANTY_DESC, 25500, 27500),
    Item("PH", "Samsung", "A26 256GB 8GB", "Samsung Galaxy A26 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 29000, 31500),
    Item("PH", "Samsung", "A36 256GB 8GB", "Samsung Galaxy A36 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 36000, 38500),
    Item("PH", "Samsung", "A36 256GB 12GB", "Samsung Galaxy A36 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 37500, 40500),
    Item("PH", "Samsung", "A37 256GB 8GB", "Samsung Galaxy A37 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 48500, 51500),
    Item("PH", "Samsung", "A56 256GB 8GB", "Samsung Galaxy A56 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 44000, 47500),
    Item("PH", "Samsung", "A56 256GB 12GB", "Samsung Galaxy A56 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 48000, 51500),
    Item("PH", "Samsung", "A57 256GB 8GB", "Samsung Galaxy A57 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 53500, 58000),
    Item("PH", "Samsung", "A57 256GB 12GB", "Samsung Galaxy A57 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 57000, 61500),
    Item("PH", "Samsung", "S24 256GB 8GB", "Samsung Galaxy S24 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 70000, 73500),
    Item("PH", "Samsung", "S25 FE 128GB 8GB", "Samsung Galaxy S25 FE 128GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 61000, 65000),
    Item("PH", "Samsung", "S25 FE 256GB 8GB", "Samsung Galaxy S25 FE 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 68500, 71500),
    Item("PH", "Samsung", "S25 128GB 12GB", "Samsung Galaxy S25 128GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 76500, 80500),
    Item("PH", "Samsung", "S25 256GB 12GB", "Samsung Galaxy S25 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 82000, 85500),
    Item("PH", "Samsung", "S25 Edge 256GB 12GB", "Samsung Galaxy S25 Edge 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 80000, 85000),
    Item("PH", "Samsung", "S25 Ultra 256GB 12GB", "Samsung Galaxy S25 Ultra 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 114000, 120000),
    Item("PH", "Samsung", "S25 Ultra 512GB 12GB", "Samsung Galaxy S25 Ultra 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 129000, 135000),
    Item("PH", "Samsung", "S26 256GB 12GB", "Samsung Galaxy S26 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 102000, 108000),
    Item("PH", "Samsung", "S26 Ultra 256GB 12GB", "Samsung Galaxy S26 Ultra 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 135000, 142000),
    Item("PH", "Samsung", "S26 Ultra 512GB 12GB", "Samsung Galaxy S26 Ultra 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 148000, 153500),
    Item("PH", "Samsung", "Z Flip 7 256GB 12GB", "Samsung Galaxy Z Flip 7 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 109000, 116000),
    Item("PH", "Samsung", "Z Fold 4 512GB 12GB", "Samsung Galaxy Z Fold 4 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 91000, 96000),
    Item("PH", "Samsung", "Z Fold 7 256GB 12GB", "Samsung Galaxy Z Fold 7 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 172500, 182500),
    Item("PH", "Samsung", "Z Fold 7 512GB 12GB", "Samsung Galaxy Z Fold 7 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 183000, 193000),
]

# --- H. Samsung tablets (8) ---------------------------------------------------
SAMSUNG_TABLETS: list[Item] = [
    Item("TB", "Samsung", "Tab A11 128GB 8GB Cellular", "Samsung Galaxy Tab A11 128GB 8GB RAM Cellular", SAMSUNG_AC_DESC, 23000, 26000),
    Item("TB", "Samsung", "Tab A11 Plus 128GB 6GB Cellular", "Samsung Galaxy Tab A11 Plus 128GB 6GB RAM Cellular", SAMSUNG_AC_DESC, 32000, 35000),
    Item("TB", "Samsung", "Tab S9 256GB 12GB Cellular", "Samsung Galaxy Tab S9 256GB 12GB RAM Cellular", SAMSUNG_AC_DESC, 80000, 86000),
    Item("TB", "Samsung", "Tab S10 Lite 256GB 8GB Cellular", "Samsung Galaxy Tab S10 Lite 256GB 8GB RAM Cellular", SAMSUNG_AC_DESC, 58000, 63000),
    Item("TB", "Samsung", "Tab S10 Ultra 256GB 12GB WiFi", "Samsung Galaxy Tab S10 Ultra 256GB 12GB RAM WiFi", SAMSUNG_AC_DESC, 110000, 118000),
    Item("TB", "Samsung", "Tab S10 Ultra 256GB 12GB Cellular", "Samsung Galaxy Tab S10 Ultra 256GB 12GB RAM Cellular", SAMSUNG_AC_DESC, 126000, 135000),
    Item("TB", "Samsung", "Tab S11 Ultra 256GB 12GB WiFi", "Samsung Galaxy Tab S11 Ultra 256GB 12GB RAM WiFi", SAMSUNG_AC_DESC, 117000, 127000),
    Item("TB", "Samsung", "Tab S11 Ultra 256GB 12GB Cellular", "Samsung Galaxy Tab S11 Ultra 256GB 12GB RAM Cellular", SAMSUNG_AC_DESC, 139000, 150000),
]

# --- I. Samsung accessories (10) ----------------------------------------------
SAMSUNG_ACCESSORIES: list[Item] = [
    Item("AC", "Samsung", "Buds 3 FE", "Samsung Galaxy Buds 3 FE", SAMSUNG_AC_DESC, 14000, 16000),
    Item("AC", "Samsung", "Buds 3 Pro", "Samsung Galaxy Buds 3 Pro", SAMSUNG_AC_DESC, 17000, 19500),
    Item("AC", "Samsung", "Buds 4", "Samsung Galaxy Buds 4", SAMSUNG_AC_DESC, 19500, 22000),
    Item("AC", "Samsung", "Buds 4 Pro", "Samsung Galaxy Buds 4 Pro", SAMSUNG_AC_DESC, 27500, 30500),
    Item("AC", "Samsung", "Watch 6 Classic 43mm", "Samsung Galaxy Watch 6 Classic 43mm", SAMSUNG_AC_DESC, 20000, 23500),
    Item("AC", "Samsung", "Watch 6 Classic 47mm", "Samsung Galaxy Watch 6 Classic 47mm", SAMSUNG_AC_DESC, 21000, 24500),
    Item("AC", "Samsung", "Watch 7 40mm", "Samsung Galaxy Watch 7 40mm", SAMSUNG_AC_DESC, 21000, 24500),
    Item("AC", "Samsung", "Watch 7 44mm", "Samsung Galaxy Watch 7 44mm", SAMSUNG_AC_DESC, 21500, 25000),
    Item("AC", "Samsung", "Watch 8 40mm", "Samsung Galaxy Watch 8 40mm", SAMSUNG_AC_DESC, 26500, 29000),
    Item("AC", "Samsung", "Watch 8 44mm", "Samsung Galaxy Watch 8 44mm", SAMSUNG_AC_DESC, 28500, 37000),
]

# --- J. Pixel (Google) phones (6) ---------------------------------------------
PIXEL_PHONES: list[Item] = [
    Item("PH", "Google", "Pixel 8 256GB 8GB", "Pixel 8 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 59000, 65000, keywords_extra=["pixel"]),
    Item("PH", "Google", "Pixel 9 Pro XL 256GB 12GB", "Pixel 9 Pro XL 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 96500, 101500, keywords_extra=["pixel"]),
    Item("PH", "Google", "Pixel 10 128GB 12GB", "Pixel 10 128GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 80000, 85000, keywords_extra=["pixel"]),
    Item("PH", "Google", "Pixel 10 Pro 256GB 12GB", "Pixel 10 Pro 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 115000, 120500, keywords_extra=["pixel"]),
    Item("PH", "Google", "Pixel 10 Pro XL 256GB 12GB", "Pixel 10 Pro XL 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 127000, 133000, keywords_extra=["pixel"]),
    Item("PH", "Google", "Pixel 10 Pro XL 512GB 12GB", "Pixel 10 Pro XL 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 139000, 145000, keywords_extra=["pixel"]),
]

# --- K. OnePlus phones (5) ----------------------------------------------------
ONEPLUS_PHONES: list[Item] = [
    Item("PH", "OnePlus", "Nord CE 5 256GB 8GB", "OnePlus Nord CE 5 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 37000, 43000),
    Item("PH", "OnePlus", "13 256GB 12GB", "OnePlus 13 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 86000, 92000),
    Item("PH", "OnePlus", "13 512GB 16GB", "OnePlus 13 512GB 16GB RAM", LOCKED_NO_WARRANTY_DESC, 90000, 95000),
    Item("PH", "OnePlus", "13s 256GB 12GB", "OnePlus 13s 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 65500, 71500),
    Item("PH", "OnePlus", "15 512GB 12GB", "OnePlus 15 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 109000, 113500),
]

# --- L. Nothing phones (3) ----------------------------------------------------
NOTHING_PHONES: list[Item] = [
    Item("PH", "Nothing", "Phone 3A 256GB 8GB", "Nothing Phone 3A 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 47000, 50000),
    Item("PH", "Nothing", "Phone 3A Pro 256GB 12GB", "Nothing Phone 3A Pro 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 63000, 68000),
    Item("PH", "Nothing", "Phone 3 256GB 12GB", "Nothing Phone 3 256GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 80500, 85000),
]

# --- M. Honor phones (4) — 7D and H400 Lite skipped --------------------------
HONOR_PHONES: list[Item] = [
    Item("PH", "Honor", "X6C 256GB 6GB", "Honor X6C 256GB 6GB RAM", LOCKED_NO_WARRANTY_DESC, 16500, 18500),
    Item("PH", "Honor", "X9D 256GB 8GB", "Honor X9D 256GB 8GB RAM", LOCKED_NO_WARRANTY_DESC, 43000, 45500),
    Item("PH", "Honor", "H400 512GB 12GB", "Honor H400 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 49000, 51500),
    Item("PH", "Honor", "H400 Pro 512GB 12GB", "Honor H400 Pro 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 74500, 78000),
]

# --- N. Xiaomi phones (2) -----------------------------------------------------
XIAOMI_PHONES: list[Item] = [
    Item("PH", "Xiaomi", "17 Pro Max 512GB 12GB", "Xiaomi 17 Pro Max 512GB 12GB RAM", LOCKED_NO_WARRANTY_DESC, 130000, 133500),
    Item("PH", "Xiaomi", "17 Pro Max 512GB 16GB", "Xiaomi 17 Pro Max 512GB 16GB RAM", LOCKED_NO_WARRANTY_DESC, 133000, 136500),
]


CLEAN_ITEMS: list[Item] = (
    APPLE_DUBAI_ESIM
    + APPLE_DUBAI_SIM
    + APPLE_OFFICIAL
    + APPLE_IPADS
    + APPLE_MACS
    + APPLE_ACCESSORIES
    + SAMSUNG_PHONES
    + SAMSUNG_TABLETS
    + SAMSUNG_ACCESSORIES
    + PIXEL_PHONES
    + ONEPLUS_PHONES
    + NOTHING_PHONES
    + HONOR_PHONES
    + XIAOMI_PHONES
)

# --- Issues CSV (6 rows) ------------------------------------------------------
ISSUES: list[dict] = [
    {
        "row_id": 1,
        "supplier_list_line": "MacBook Neo 256GB@91000 new — KES 100,500",
        "proposed_brand": "Apple",
        "proposed_product_type": "LT",
        "proposed_model_series": "MacBook Neo 256GB",
        "proposed_product_name": "MacBook Neo 256GB",
        "ref_cost_kes": 91000,
        "ref_sell_kes": 100500,
        "issue": "'MacBook Neo' is not a known Apple SKU",
        "what_we_need_from_you": (
            "Confirm exact model (e.g. MacBook Air M1/M2/M3) or that this is a "
            "third-party device. If keeping, give the real product_name."
        ),
    },
    {
        "row_id": 2,
        "supplier_list_line": "MacBook Pro M3 14.2 inch 512+8@143000 — KES 265,000",
        "proposed_brand": "Apple",
        "proposed_product_type": "LT",
        "proposed_model_series": "MacBook Pro M3 14.2 inch 512GB 8GB",
        "proposed_product_name": "MacBook Pro M3 14.2 inch 512GB 8GB RAM",
        "ref_cost_kes": 143000,
        "ref_sell_kes": 265000,
        "issue": (
            "Sell price 265,000 implies ~85% markup; every other Mac in the list is ~5-12% "
            "(e.g. M4 198k->218k = 10%, M5 211k->230k = 9%)."
        ),
        "what_we_need_from_you": (
            "Confirm correct sell price (likely 155,000-165,000) OR confirm 265,000 is intentional."
        ),
    },
    {
        "row_id": 3,
        "supplier_list_line": "Pencil 2 pro@16000 — KES 18,000",
        "proposed_brand": "Apple",
        "proposed_product_type": "AC",
        "proposed_model_series": "Pencil 2 Pro",
        "proposed_product_name": "Apple Pencil 2 Pro",
        "ref_cost_kes": 16000,
        "ref_sell_kes": 18000,
        "issue": (
            "'Pencil 2 Pro' isn't a real Apple SKU. Apple sells: "
            "Apple Pencil (2nd gen), Apple Pencil USB-C, and Apple Pencil Pro."
        ),
        "what_we_need_from_you": (
            "Confirm which one — most likely 'Apple Pencil Pro' given the price."
        ),
    },
    {
        "row_id": 4,
        "supplier_list_line": "Watch 8 classic 46mm@33500",
        "proposed_brand": "Samsung",
        "proposed_product_type": "AC",
        "proposed_model_series": "Watch 8 Classic 46mm",
        "proposed_product_name": "Samsung Galaxy Watch 8 Classic 46mm",
        "ref_cost_kes": 33500,
        "ref_sell_kes": "",
        "issue": "Sell price missing from source list.",
        "what_we_need_from_you": "Provide sell price in KES.",
    },
    {
        "row_id": 5,
        "supplier_list_line": "Honor 7D 256+8@22000 — KES 24,000",
        "proposed_brand": "Honor",
        "proposed_product_type": "PH",
        "proposed_model_series": "7D 256GB 8GB",
        "proposed_product_name": "Honor 7D 256GB 8GB RAM",
        "ref_cost_kes": 22000,
        "ref_sell_kes": 24000,
        "issue": "Honor doesn't sell a '7D' model. Closest match is 'Honor X7D'.",
        "what_we_need_from_you": "Confirm whether this is Honor X7D or another model name.",
    },
    {
        "row_id": 6,
        "supplier_list_line": "Honor H400 Lite 256+@32000 — KES 34,500",
        "proposed_brand": "Honor",
        "proposed_product_type": "PH",
        "proposed_model_series": "H400 Lite 256GB ?GB",
        "proposed_product_name": "Honor H400 Lite 256GB ?GB RAM",
        "ref_cost_kes": 32000,
        "ref_sell_kes": 34500,
        "issue": "RAM is blank in source ('256+@' missing the RAM number).",
        "what_we_need_from_you": "Provide RAM in GB (likely 6 or 8 for the Lite variant).",
    },
]


CLEAN_FIELDS = [
    "product_type",
    "product_name",
    "product_description",
    "brand",
    "model_series",
    "min_stock_threshold",
    "reorder_point",
    "is_discontinued",
    "meta_title",
    "meta_description",
    "slug",
    "keywords",
    "og_image",
    "product_highlights",
    "long_description",
    "is_published",
    "product_video_url",
    "product_video_file",
    "tag_ids",
    "brand_ids",
    "is_global",
    "ref_cost_kes",
    "ref_sell_kes",
]

ISSUE_FIELDS = [
    "row_id",
    "supplier_list_line",
    "proposed_brand",
    "proposed_product_type",
    "proposed_model_series",
    "proposed_product_name",
    "ref_cost_kes",
    "ref_sell_kes",
    "issue",
    "what_we_need_from_you",
]


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Validate uniqueness on (brand, model_series, product_type)
    seen: dict[tuple[str, str, str], str] = {}
    for item in CLEAN_ITEMS:
        key = (item.brand, item.model_series, item.product_type)
        if key in seen:
            raise SystemExit(
                f"Duplicate (brand, model_series, product_type) detected: {key}\n"
                f"  first:  {seen[key]}\n"
                f"  second: {item.product_name}"
            )
        seen[key] = item.product_name

    # Validate product_name uniqueness (helps importer skip-if-exists)
    seen_names: dict[str, str] = {}
    for item in CLEAN_ITEMS:
        if item.product_name in seen_names:
            raise SystemExit(
                f"Duplicate product_name detected: {item.product_name!r}"
            )
        seen_names[item.product_name] = item.brand

    with CLEAN_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CLEAN_FIELDS)
        writer.writeheader()
        for item in CLEAN_ITEMS:
            writer.writerow(_row(item))

    with ISSUES_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ISSUE_FIELDS)
        writer.writeheader()
        for issue in ISSUES:
            writer.writerow(issue)

    print(f"Wrote {len(CLEAN_ITEMS)} clean rows to {CLEAN_CSV}")
    print(f"Wrote {len(ISSUES)} issue rows to  {ISSUES_CSV}")

    # Per-category breakdown
    counts: dict[str, int] = {}
    by_brand: dict[tuple[str, str], int] = {}
    for item in CLEAN_ITEMS:
        counts[item.product_type] = counts.get(item.product_type, 0) + 1
        by_brand[(item.brand, item.product_type)] = (
            by_brand.get((item.brand, item.product_type), 0) + 1
        )
    print("By product_type:", json.dumps(counts, indent=2))
    print("By (brand, product_type):", json.dumps({f"{b}-{t}": c for (b, t), c in by_brand.items()}, indent=2))


if __name__ == "__main__":
    main()
