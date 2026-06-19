#!/usr/bin/env python3
"""Build products + variants CSVs from the June 2026 supplier stock list.

Usage:
    python scripts/build_stock_list_csv.py

Outputs:
    inventory/data/stock_list_2026_06_19_products.csv
    inventory/data/stock_list_2026_06_19_variants.csv
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "inventory" / "data"
PRODUCTS_CSV = DATA_DIR / "stock_list_2026_06_19_products.csv"
VARIANTS_CSV = DATA_DIR / "stock_list_2026_06_19_variants.csv"

PRODUCT_FIELDS = [
    "product_type",
    "product_name",
    "product_description",
    "brand",
    "model_series",
    "is_published",
    "default_selling_price",
]

VARIANT_FIELDS = [
    "product_name",
    "storage_gb",
    "ram_gb",
    "ref_sell_kes",
    "ref_cost_kes",
    "is_active",
]


@dataclass
class ProductRow:
    product_type: str
    product_name: str
    brand: str
    model_series: str
    product_description: str = ""
    is_published: bool = True
    variants: list[tuple[int | None, int | None, int]] = field(default_factory=list)

    def min_price(self) -> str:
        if not self.variants:
            return ""
        return str(min(p for _, _, p in self.variants))


def p(
    product_type: str,
    name: str,
    brand: str,
    series: str,
    desc: str,
    *variants: tuple[int | None, int | None, int],
) -> ProductRow:
    # model_series must be unique per (brand, product_type) — use product name.
    return ProductRow(product_type, name, brand, name, desc, True, list(variants))


def acc(name: str, brand: str, series: str, price: int, desc: str = "") -> ProductRow:
    return ProductRow("AC", name, brand, name, desc, True, [(None, None, price)])


def tb(name: str, brand: str, series: str, desc: str, *variants: tuple[int | None, int | None, int]) -> ProductRow:
    return p("TB", name, brand, name, desc, *variants)


def lt(name: str, brand: str, series: str, desc: str, *variants: tuple[int | None, int | None, int]) -> ProductRow:
    return p("LT", name, brand, name, desc, *variants)


APPLE_WARRANTY = (
    "Official Apple Service Center warranty only. No in-house shop warranty. Non-activated."
)
# Apple iPhones: E-SIM and physical SIM are separate products (different prices).
# Product names must include ``E-SIM`` or ``SIM`` — never a generic ``iPhone 17`` row.
CARRIER_LOCKED = "Carrier-locked units only. No warranty."
NOTHING_DESC = "Carrier-locked units only."


def build_catalog() -> list[ProductRow]:
    rows: list[ProductRow] = []

    # --- Apple iPhones E-SIM ---
    rows += [
        p("PH", "iPhone 16E E-SIM", "Apple", "iPhone", APPLE_WARRANTY, (128, None, 88000)),
        p("PH", "iPhone 17 E-SIM", "Apple", "iPhone", APPLE_WARRANTY, (256, None, 114000)),
        p(
            "PH",
            "iPhone 17 Air E-SIM Blue/Black",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 125000),
        ),
        p(
            "PH",
            "iPhone 17 Air E-SIM 2 Year Warranty Blue/Black",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 127000),
        ),
        p(
            "PH",
            "iPhone 17 Air E-SIM White/Gold",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 128500),
        ),
        p(
            "PH",
            "iPhone 17 Pro E-SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 162000),
            (512, None, 186000),
            (1024, None, 216000),
        ),
        p(
            "PH",
            "iPhone 17 Pro Max E-SIM All Colors",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 172000),
        ),
        p(
            "PH",
            "iPhone 17 Pro Max E-SIM Silver/Blue",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (512, None, 204000),
        ),
        p(
            "PH",
            "iPhone 17 Pro Max E-SIM Orange",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (512, None, 203000),
        ),
        p(
            "PH",
            "iPhone 17 Pro Max E-SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (1024, None, 226000),
        ),
    ]

    # --- Apple iPhones Physical SIM ---
    rows += [
        p("PH", "iPhone 13 SIM", "Apple", "iPhone", APPLE_WARRANTY, (128, None, 79000), (256, None, 88500)),
        p("PH", "iPhone 14 SIM", "Apple", "iPhone", APPLE_WARRANTY, (256, None, 92000)),
        p(
            "PH",
            "iPhone 15 SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (128, None, 91000),
            (256, None, 101000),
        ),
        p(
            "PH",
            "iPhone 15 SIM 2 Year Warranty",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 103500),
        ),
        p("PH", "iPhone 15 Plus SIM", "Apple", "iPhone", APPLE_WARRANTY, (128, None, 101000)),
        p("PH", "iPhone 15 Pro SIM", "Apple", "iPhone", APPLE_WARRANTY, (128, None, 125000)),
        p("PH", "iPhone 16 SIM", "Apple", "iPhone", APPLE_WARRANTY, (128, None, 98000)),
        p(
            "PH",
            "iPhone 16 Plus SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (128, None, 113000),
            (256, None, 122000),
        ),
        p("PH", "iPhone 16 Pro SIM", "Apple", "iPhone", APPLE_WARRANTY, (128, None, 140000)),
        p(
            "PH",
            "iPhone 16 Pro Max SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 162000),
        ),
        p(
            "PH",
            "iPhone 16 Pro Max SIM Natural",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 167500),
        ),
        p(
            "PH",
            "iPhone 16 Pro Max SIM Active",
            "Apple",
            "iPhone",
            APPLE_WARRANTY + " Active SIM.",
            (512, None, 175000),
        ),
        p(
            "PH",
            "iPhone 16 Pro Max SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (512, None, 193000),
        ),
        p("PH", "iPhone 17E SIM", "Apple", "iPhone", APPLE_WARRANTY, (256, None, 93500)),
        p("PH", "iPhone 17 SIM", "Apple", "iPhone", APPLE_WARRANTY, (256, None, 118500)),
        p(
            "PH",
            "iPhone 17 SIM 2 Year Warranty",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 120500),
        ),
        p(
            "PH",
            "iPhone 17 Pro SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 176000),
        ),
        p(
            "PH",
            "iPhone 17 Pro SIM 2 Year Warranty",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 177000),
        ),
        p(
            "PH",
            "iPhone 17 Pro SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (512, None, 207000),
            (1024, None, 229000),
        ),
        p(
            "PH",
            "iPhone 17 Pro Max SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 189000),
            (512, None, 219500),
        ),
    ]

    # Fix duplicate iPhone 16 Pro Max SIM and iPhone 17 Pro SIM - merge variants in one product
    # Rebuild those two as single entries with all variants
    rows = [r for r in rows if r.product_name not in (
        "iPhone 16 Pro Max SIM",
        "iPhone 17 Pro SIM",
    )]
    rows += [
        p(
            "PH",
            "iPhone 16 Pro Max SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 162000),
            (512, None, 193000),
        ),
        p(
            "PH",
            "iPhone 17 Pro SIM",
            "Apple",
            "iPhone",
            APPLE_WARRANTY,
            (256, None, 176000),
            (512, None, 207000),
            (1024, None, 229000),
        ),
    ]

    # --- Apple iPads ---
    rows += [
        tb("iPad 11th Gen WiFi", "Apple", "iPad", APPLE_WARRANTY, (128, None, 53000), (256, None, 74000)),
        tb("iPad 11th Gen Cellular", "Apple", "iPad", APPLE_WARRANTY, (128, None, 73500), (256, None, 96000)),
        tb("iPad Air M3 WiFi", "Apple", "iPad", APPLE_WARRANTY, (128, None, 83000), (256, None, 100000)),
        tb("iPad Air M3 Cellular", "Apple", "iPad", APPLE_WARRANTY, (128, None, 101000), (256, None, 122000)),
        tb("iPad Mini 7 Cellular", "Apple", "iPad", APPLE_WARRANTY, (128, None, 91000), (256, None, 115000)),
        tb("iPad Pro M4 11\" WiFi", "Apple", "iPad", APPLE_WARRANTY, (256, None, 127000)),
        tb("iPad Pro M4 11\" Cellular", "Apple", "iPad", APPLE_WARRANTY, (256, None, 137000)),
        tb("iPad Pro M5 11\" WiFi", "Apple", "iPad", APPLE_WARRANTY, (256, None, 140500)),
        tb("iPad Pro M4 13\" Cellular", "Apple", "iPad", APPLE_WARRANTY, (256, None, 151000)),
        tb("iPad Pro M5 11\" Cellular", "Apple", "iPad", APPLE_WARRANTY, (256, None, 152000)),
    ]

    # --- MacBooks & Mac Mini ---
    rows += [
        lt("MacBook 13\" Neo", "Apple", "MacBook", APPLE_WARRANTY, (256, 8, 94500), (512, 8, 975000)),
        lt("Mac Mini M4", "Apple", "Mac", APPLE_WARRANTY, (256, 16, 110000), (512, 16, 172000)),
        lt("MacBook Air M4 13\"", "Apple", "MacBook", APPLE_WARRANTY, (256, 16, 147000), (512, 16, 149000)),
        lt("MacBook Air M5 13\"", "Apple", "MacBook", APPLE_WARRANTY, (512, 16, 155000)),
        lt("MacBook Pro M5 14.2\"", "Apple", "MacBook", APPLE_WARRANTY, (512, 16, 227000), (1024, 24, 258000)),
        lt("MacBook Pro M4 Pro 14.2\"", "Apple", "MacBook", APPLE_WARRANTY, (512, 24, 267000)),
        lt("MacBook Pro M5 Pro 14.2\"", "Apple", "MacBook", APPLE_WARRANTY, (1024, 24, 304000)),
    ]

    # --- Apple Audio & Wearables ---
    rows += [
        acc("Apple 20W Adapter (2-pin)", "Apple", "Accessory", 4800, APPLE_WARRANTY),
        acc("Apple Pencil 2", "Apple", "Accessory", 12500, APPLE_WARRANTY),
        acc("Magic Mouse (White)", "Apple", "Accessory", 13500, APPLE_WARRANTY),
        acc("Apple Pencil 2 (Type-C)", "Apple", "Accessory", 14000, APPLE_WARRANTY),
        acc("Magic Mouse (Black)", "Apple", "Accessory", 16000, APPLE_WARRANTY),
        acc("AirPods 4", "Apple", "AirPods", 19000, APPLE_WARRANTY),
        acc("Apple Pencil 2 Pro", "Apple", "Accessory", 19999, APPLE_WARRANTY),
        acc("AirPods 4 ANC", "Apple", "AirPods", 26500, APPLE_WARRANTY),
        acc("Apple Watch SE 2 40mm", "Apple", "Apple Watch", 29000, APPLE_WARRANTY),
        acc("AirPods Pro 2", "Apple", "AirPods", 30000, APPLE_WARRANTY),
        acc("Apple Watch SE 2 44mm", "Apple", "Apple Watch", 31000, APPLE_WARRANTY),
        acc("AirPods Pro 3 (2 Years Warranty)", "Apple", "AirPods", 35000, APPLE_WARRANTY),
        acc("Apple Watch SE 3 40mm", "Apple", "Apple Watch", 38000, APPLE_WARRANTY),
        acc("Apple Watch SE 3 44mm", "Apple", "Apple Watch", 42000, APPLE_WARRANTY),
        acc("Apple Watch Series 10 42mm", "Apple", "Apple Watch", 47500, APPLE_WARRANTY),
        acc("Apple Watch Series 10 46mm", "Apple", "Apple Watch", 48000, APPLE_WARRANTY),
        acc("Apple Watch Series 11 42mm", "Apple", "Apple Watch", 49000, APPLE_WARRANTY),
        acc("Apple Watch Series 11 46mm", "Apple", "Apple Watch", 54000, APPLE_WARRANTY),
        acc("AirPods Max (Type-C)", "Apple", "AirPods", 76000, APPLE_WARRANTY),
        acc("Apple Watch Ultra 3 49mm (2025)", "Apple", "Apple Watch", 108500, APPLE_WARRANTY),
        acc("Apple Watch Ultra 3 49mm Milanese (2025)", "Apple", "Apple Watch", 132000, APPLE_WARRANTY),
    ]

    # --- Samsung Galaxy A Series ---
    rows += [
        p("PH", "Galaxy A16", "Samsung", "A Series", CARRIER_LOCKED, (128, 4, 18700)),
        p("PH", "Galaxy A17", "Samsung", "A Series", CARRIER_LOCKED, (128, 4, 20700), (128, 6, 23500)),
        p("PH", "Galaxy A17 4G", "Samsung", "A Series", CARRIER_LOCKED, (256, 8, 26000)),
        p("PH", "Galaxy A17 5G", "Samsung", "A Series", CARRIER_LOCKED, (256, 8, 28500)),
        p("PH", "Galaxy A36", "Samsung", "A Series", CARRIER_LOCKED, (256, 8, 41000), (256, 12, 41000)),
        p("PH", "Galaxy A37", "Samsung", "A Series", CARRIER_LOCKED, (256, 8, 52500), (256, 12, 53500)),
        p("PH", "Galaxy A56", "Samsung", "A Series", CARRIER_LOCKED, (256, 8, 49500), (256, 12, 52000)),
        p("PH", "Galaxy A57", "Samsung", "A Series", CARRIER_LOCKED, (256, 8, 60000), (256, 12, 63000)),
    ]

    # --- Samsung budget (bottom list only) ---
    rows += [
        p("PH", "Galaxy A06", "Samsung", "A Series", CARRIER_LOCKED, (64, 4, 13500)),
        p("PH", "Galaxy A07", "Samsung", "A Series", CARRIER_LOCKED, (64, 4, 15100), (128, 4, 16400)),
        p("PH", "Galaxy A37", "Samsung", "A Series", CARRIER_LOCKED, (128, 8, 42000)),
        p("PH", "Galaxy A57", "Samsung", "A Series", CARRIER_LOCKED, (128, 8, 51000)),
    ]

    # --- Samsung S & Z Flagships ---
    rows += [
        p("PH", "Galaxy S24 FE", "Samsung", "S Series", CARRIER_LOCKED, (128, 8, 54000)),
        p("PH", "Galaxy S24", "Samsung", "S Series", CARRIER_LOCKED, (128, 8, 68000), (256, 8, 73000)),
        p("PH", "Galaxy S25 FE", "Samsung", "S Series", CARRIER_LOCKED, (128, 8, 71000), (256, 8, 75000)),
        p("PH", "Galaxy S25", "Samsung", "S Series", CARRIER_LOCKED, (128, 12, 84000), (256, 12, 89000)),
        p("PH", "Galaxy S25 Edge", "Samsung", "S Series", CARRIER_LOCKED, (256, 12, 87500)),
        p("PH", "Galaxy S25 Plus", "Samsung", "S Series", CARRIER_LOCKED, (256, 12, 95000)),
        p("PH", "Galaxy S26", "Samsung", "S Series", CARRIER_LOCKED, (256, 12, 100000)),
        p("PH", "Galaxy Z Flip 5", "Samsung", "Z Series", CARRIER_LOCKED, (256, 8, 70000), (512, 8, 74500)),
        p("PH", "Galaxy S25 Ultra", "Samsung", "S Series", CARRIER_LOCKED, (256, 12, 119000), (512, 12, 134000)),
        p("PH", "Galaxy Z Flip 7", "Samsung", "Z Series", CARRIER_LOCKED, (256, 12, 119000)),
        p("PH", "Galaxy S26 Ultra", "Samsung", "S Series", CARRIER_LOCKED, (256, 12, 139000), (512, 12, 158000)),
        p("PH", "Galaxy Z Fold 7", "Samsung", "Z Series", CARRIER_LOCKED, (256, 12, 180000), (512, 12, 196000)),
    ]

    # --- Samsung Tablets ---
    rows += [
        tb("Galaxy Tab A11 Cellular", "Samsung", "Tab A", CARRIER_LOCKED, (128, None, 26000)),
        tb("Galaxy Tab A11 Plus Cellular", "Samsung", "Tab A", CARRIER_LOCKED, (128, None, 37000), (256, None, 43000)),
        tb("Galaxy Tab S10 FE WiFi", "Samsung", "Tab S", CARRIER_LOCKED, (128, None, 60000)),
        tb("Galaxy Tab S10 Lite Cellular", "Samsung", "Tab S", CARRIER_LOCKED, (256, None, 68000)),
        tb("Galaxy Tab S10 FE Cellular", "Samsung", "Tab S", CARRIER_LOCKED, (128, None, 73000)),
        tb("Galaxy Tab S9 Cellular", "Samsung", "Tab S", CARRIER_LOCKED, (256, None, 100000)),
        tb("Galaxy Tab S10 Ultra WiFi", "Samsung", "Tab S", CARRIER_LOCKED, (256, None, 116000)),
        tb("Galaxy Tab S11 Ultra WiFi", "Samsung", "Tab S", CARRIER_LOCKED, (256, None, 122000)),
        tb("Galaxy Tab S11 Ultra Cellular", "Samsung", "Tab S", CARRIER_LOCKED, (256, None, 155000)),
    ]

    # --- Samsung Audio & Wearables ---
    rows += [
        acc("Galaxy Buds Core", "Samsung", "Buds", 7500, CARRIER_LOCKED),
        acc("Galaxy Buds 3 FE", "Samsung", "Buds", 12700, CARRIER_LOCKED),
        acc("Galaxy Buds 3", "Samsung", "Buds", 13000, CARRIER_LOCKED),
        acc("Galaxy Buds 3 Pro", "Samsung", "Buds", 19000, CARRIER_LOCKED),
        acc("Galaxy Buds 4", "Samsung", "Buds", 19000, CARRIER_LOCKED),
        acc("Galaxy Watch 6 Classic 47mm", "Samsung", "Watch", 24000, CARRIER_LOCKED),
        acc("Galaxy Watch 7 44mm", "Samsung", "Watch", 24500, CARRIER_LOCKED),
        acc("Galaxy Buds 4 Pro", "Samsung", "Buds", 25599, CARRIER_LOCKED),
        acc("Galaxy Watch 8 40mm", "Samsung", "Watch", 29500, CARRIER_LOCKED),
        acc("Galaxy Watch 8 44mm", "Samsung", "Watch", 31500, CARRIER_LOCKED),
        acc("Galaxy Watch 8 Classic 46mm", "Samsung", "Watch", 30500, CARRIER_LOCKED),
        acc("Samsung 25W Adapter", "Samsung", "Accessory", 1000, CARRIER_LOCKED),
    ]

    # --- Google Pixel ---
    rows += [
        p("PH", "Pixel 9A", "Google", "Pixel", CARRIER_LOCKED, (256, 8, 63500)),
        p("PH", "Pixel 10A", "Google", "Pixel", CARRIER_LOCKED, (128, 8, 69000), (256, 8, 72500)),
        p("PH", "Pixel 10", "Google", "Pixel", CARRIER_LOCKED, (128, 12, 90000), (256, 12, 100500)),
        p("PH", "Pixel 9 Pro XL", "Google", "Pixel", CARRIER_LOCKED, (256, 12, 104000)),
        p("PH", "Pixel 10 Pro", "Google", "Pixel", CARRIER_LOCKED, (256, 12, 125000)),
        p("PH", "Pixel 10 Pro XL", "Google", "Pixel", CARRIER_LOCKED, (256, 12, 128000), (512, 12, 157000)),
    ]

    # --- OnePlus ---
    rows += [
        p("PH", "OnePlus Nord CE 5", "OnePlus", "Nord", CARRIER_LOCKED, (256, 8, 42000)),
        p("PH", "OnePlus 13s", "OnePlus", "13 Series", CARRIER_LOCKED, (256, 12, 75500)),
        p("PH", "OnePlus 13", "OnePlus", "13 Series", CARRIER_LOCKED, (256, 12, 96000), (512, 16, 101000)),
        p("PH", "OnePlus 15", "OnePlus", "15 Series", CARRIER_LOCKED, (256, 12, 109000)),
    ]

    # --- Nothing Phone ---
    rows += [
        p("PH", "Nothing Phone 3A Pro", "Nothing", "Phone", NOTHING_DESC, (256, 12, 65000)),
        p("PH", "Nothing Phone 3", "Nothing", "Phone", NOTHING_DESC, (256, 12, 87500)),
    ]

    # --- Honor (flagship section) ---
    rows += [
        p("PH", "Honor 7D", "Honor", "7 Series", CARRIER_LOCKED, (256, 8, 28000)),
        p("PH", "Honor X9D", "Honor", "X Series", CARRIER_LOCKED, (256, 8, 48000)),
        p("PH", "Honor H400", "Honor", "H Series", CARRIER_LOCKED, (512, 12, 61000)),
        p("PH", "Honor H400 Pro", "Honor", "H Series", CARRIER_LOCKED, (512, 12, 82000)),
    ]

    # --- Honor (budget bottom list) ---
    rows += [
        p("PH", "Honor Play10", "Honor", "Play", CARRIER_LOCKED, (64, 3, 13300)),
        p("PH", "Honor X5B", "Honor", "X Series", CARRIER_LOCKED, (64, 4, 13400)),
        p("PH", "Honor X5C", "Honor", "X Series", CARRIER_LOCKED, (64, 4, 15500)),
        p("PH", "Honor X5C Plus", "Honor", "X Series", CARRIER_LOCKED, (128, 4, 16800)),
        p("PH", "Honor X6c", "Honor", "X Series", CARRIER_LOCKED, (128, 6, 20900), (256, 6, 22100)),
        p("PH", "Honor X7c", "Honor", "X Series", CARRIER_LOCKED, (256, 8, 24200)),
        p("PH", "Honor X7D", "Honor", "X Series", CARRIER_LOCKED, (256, 8, 25500)),
    ]

    # --- Xiaomi ---
    rows += [
        p("PH", "Xiaomi 17 Pro Max", "Xiaomi", "17 Series", CARRIER_LOCKED, (512, 12, 135000), (512, 16, 139000)),
    ]

    # --- Infinix ---
    rows += [
        p("PH", "Infinix Smart 10", "Infinix", "Smart", CARRIER_LOCKED, (64, 4, 13300), (128, 4, 14700)),
        p("PH", "Infinix Smart 20", "Infinix", "Smart", CARRIER_LOCKED, (64, 4, 14700), (128, 4, 15900)),
        p("PH", "Infinix Hot 60i", "Infinix", "Hot", CARRIER_LOCKED, (128, 6, 16900), (256, 8, 19700)),
        p("PH", "Infinix Hot 60 Pro", "Infinix", "Hot", CARRIER_LOCKED, (128, 8, 21000)),
        p("PH", "Infinix Hot 60 Pro+", "Infinix", "Hot", CARRIER_LOCKED, (256, 8, 28500)),
        p("PH", "Infinix Note Edge", "Infinix", "Note", CARRIER_LOCKED, (256, 8, 37900)),
        p("PH", "Infinix Note 60 Pro", "Infinix", "Note", CARRIER_LOCKED, (256, 8, 43800)),
    ]

    # --- Tecno ---
    rows += [
        p("PH", "Tecno Pop 10", "Tecno", "Pop", CARRIER_LOCKED, (64, 3, 13500)),
        p("PH", "Tecno Pop 20", "Tecno", "Pop", CARRIER_LOCKED, (64, 4, 14200), (128, 4, 16300)),
        p("PH", "Tecno Spark 50", "Tecno", "Spark", CARRIER_LOCKED, (128, 4, 18800), (256, 8, 21600)),
        p("PH", "Tecno Spark 40 Pro", "Tecno", "Spark", CARRIER_LOCKED, (128, 8, 22400)),
        p("PH", "Tecno Camon 50", "Tecno", "Camon", CARRIER_LOCKED, (256, 8, 37000)),
        p("PH", "Tecno Camon 50 Pro", "Tecno", "Camon", CARRIER_LOCKED, (256, 8, 40900)),
        p("PH", "Tecno Camon 50 Ultra", "Tecno", "Camon", CARRIER_LOCKED, (512, 12, 65000)),
    ]

    # --- Vivo ---
    rows += [
        p("PH", "Vivo Y04e", "Vivo", "Y Series", CARRIER_LOCKED, (64, 4, 14100)),
        p("PH", "Vivo Y04", "Vivo", "Y Series", CARRIER_LOCKED, (64, 4, 15900), (128, 4, 17400)),
        p("PH", "Vivo Y05", "Vivo", "Y Series", CARRIER_LOCKED, (64, 4, 17500), (128, 4, 20200)),
        p("PH", "Vivo Y21D", "Vivo", "Y Series", CARRIER_LOCKED, (128, 4, 20800), (256, 6, 25100)),
        p("PH", "Vivo Y31D", "Vivo", "Y Series", CARRIER_LOCKED, (128, 6, 26900), (256, 8, 30100)),
        p("PH", "Vivo Y28", "Vivo", "Y Series", CARRIER_LOCKED, (128, 8, 24000)),
        p("PH", "Vivo V60 Lite 4G", "Vivo", "V Series", CARRIER_LOCKED, (256, 8, 36000)),
        p("PH", "Vivo V60 Lite 5G", "Vivo", "V Series", CARRIER_LOCKED, (256, 8, 44000)),
        p("PH", "Vivo V70 FE", "Vivo", "V Series", CARRIER_LOCKED, (512, 12, 60500), (512, 8, 69500)),
        p("PH", "Vivo V70", "Vivo", "V Series", CARRIER_LOCKED, (512, 12, 83800)),
    ]

    # --- Redmi ---
    rows += [
        p("PH", "Redmi A7", "Redmi", "A Series", CARRIER_LOCKED, (64, 3, 14000)),
        p("PH", "Redmi A7 Pro", "Redmi", "A Series", CARRIER_LOCKED, (64, 4, 15000), (128, 4, 16900)),
        p("PH", "Redmi 15C", "Redmi", "15 Series", CARRIER_LOCKED, (128, 4, 17900), (256, 8, 22900)),
        p("PH", "Redmi 15", "Redmi", "15 Series", CARRIER_LOCKED, (128, 6, 20900), (256, 8, 31900)),
        p("PH", "Redmi Note 15", "Redmi", "Note", CARRIER_LOCKED, (128, 6, 28700), (256, 8, 34200)),
        p("PH", "Redmi Note 15 Pro", "Redmi", "Note", CARRIER_LOCKED, (256, 8, 41300)),
    ]

    # --- Realme ---
    rows += [
        p("PH", "Realme Note 50", "Realme", "Note", CARRIER_LOCKED, (128, 4, 15300)),
        p("PH", "Realme Note 60x", "Realme", "Note", CARRIER_LOCKED, (64, 3, 15300), (64, 4, 16300)),
        p("PH", "Realme Note 70", "Realme", "Note", CARRIER_LOCKED, (128, 4, 18900)),
        p("PH", "Realme C100i", "Realme", "C Series", CARRIER_LOCKED, (64, 4, 20300), (128, 4, 21800)),
        p("PH", "Realme C85 Pro", "Realme", "C Series", CARRIER_LOCKED, (256, 8, 32200)),
        p("PH", "Realme C75", "Realme", "C Series", CARRIER_LOCKED, (128, 8, 24400), (256, 8, 26100), (512, 8, 30100)),
        p("PH", "Realme 12+", "Realme", "12 Series", CARRIER_LOCKED, (512, 12, 49800)),
    ]

    # --- Oppo ---
    rows += [
        p("PH", "Oppo Reno 15 Pro 5G", "Oppo", "Reno", CARRIER_LOCKED, (512, 12, 83800)),
        p("PH", "Oppo Reno 15 5G", "Oppo", "Reno", CARRIER_LOCKED, (512, 12, 75000)),
        p("PH", "Oppo Reno 15F 5G", "Oppo", "Reno", CARRIER_LOCKED, (512, 12, 62400)),
        p("PH", "Oppo A6 Pro 4G", "Oppo", "A Series", CARRIER_LOCKED, (256, 8, 45900)),
        p("PH", "Oppo A6 4G", "Oppo", "A Series", CARRIER_LOCKED, (256, 8, 36700), (256, 6, 36700)),
        p("PH", "Oppo A3", "Oppo", "A Series", CARRIER_LOCKED, (256, 8, 29700), (128, 6, 24400)),
        p("PH", "Oppo A5", "Oppo", "A Series", CARRIER_LOCKED, (128, 6, 25300)),
        p(
            "PH",
            "Oppo A6X",
            "Oppo",
            "A Series",
            CARRIER_LOCKED,
            (256, 8, 23100),
            (128, 4, 19900),
            (64, 4, 16200),
        ),
        p("PH", "Oppo A3x", "Oppo", "A Series", CARRIER_LOCKED, (128, 4, 18900)),
    ]

    # --- Itel ---
    rows += [
        p("PH", "Itel A04", "Itel", "A Series", CARRIER_LOCKED, (32, 2, 10300)),
        p("PH", "Itel A100c", "Itel", "A Series", CARRIER_LOCKED, (None, None, 12400)),
        p("PH", "Itel P70", "Itel", "P Series", CARRIER_LOCKED, (128, 4, 13800)),
        p("PH", "Itel City 200", "Itel", "City", CARRIER_LOCKED, (128, 4, 16700)),
        p("PH", "Itel A200", "Itel", "A Series", CARRIER_LOCKED, (128, 3, 14600)),
        p("PH", "Itel S26 Ultra", "Itel", "S Series", CARRIER_LOCKED, (None, None, 25600)),
    ]

    return merge_duplicate_products(rows)


def merge_duplicate_products(rows: list[ProductRow]) -> list[ProductRow]:
    """Merge rows with the same product_name, combining variants (last price wins)."""
    by_name: dict[str, ProductRow] = {}
    for row in rows:
        if row.product_name not in by_name:
            by_name[row.product_name] = ProductRow(
                row.product_type,
                row.product_name,
                row.brand,
                row.model_series,
                row.product_description,
                row.is_published,
                list(row.variants),
            )
            continue
        existing = by_name[row.product_name]
        variant_map: dict[tuple[int | None, int | None], int] = {
            (s, r): p for s, r, p in existing.variants
        }
        for storage, ram, price in row.variants:
            variant_map[(storage, ram)] = price
        existing.variants = [(s, r, p) for (s, r), p in sorted(variant_map.items())]
    return list(by_name.values())


def write_csvs(rows: list[ProductRow]) -> tuple[int, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    variant_rows: list[dict[str, str]] = []
    product_rows: list[dict[str, str]] = []

    for row in sorted(rows, key=lambda r: (r.brand, r.product_name)):
        product_rows.append(
            {
                "product_type": row.product_type,
                "product_name": row.product_name,
                "product_description": row.product_description,
                "brand": row.brand,
                "model_series": row.model_series,
                "is_published": "true" if row.is_published else "false",
                "default_selling_price": row.min_price(),
            }
        )
        for storage, ram, price in row.variants:
            variant_rows.append(
                {
                    "product_name": row.product_name,
                    "storage_gb": "" if storage is None else str(storage),
                    "ram_gb": "" if ram is None else str(ram),
                    "ref_sell_kes": str(price),
                    "ref_cost_kes": "0",
                    "is_active": "true",
                }
            )

    with PRODUCTS_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PRODUCT_FIELDS)
        writer.writeheader()
        writer.writerows(product_rows)

    with VARIANTS_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=VARIANT_FIELDS)
        writer.writeheader()
        writer.writerows(variant_rows)

    return len(product_rows), len(variant_rows)


def main() -> None:
    rows = build_catalog()
    product_count, variant_count = write_csvs(rows)
    print(f"Wrote {product_count} products -> {PRODUCTS_CSV}")
    print(f"Wrote {variant_count} variants -> {VARIANTS_CSV}")


if __name__ == "__main__":
    main()
