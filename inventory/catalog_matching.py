"""Shared product-name tokenization for catalog donor matching."""

from __future__ import annotations

import re

STOP_TOKENS = frozenset(
    {
        "gb",
        "tb",
        "ram",
        "wifi",
        "cellular",
        "sim",
        "e",
        "non",
        "act",
        "dubai",
        "official",
        "year",
        "years",
        "warranty",
        "the",
        "and",
        "for",
        "with",
        "inch",
        "gen",
        "generation",
        "blue",
        "black",
        "white",
        "gold",
        "orange",
        "silver",
        "colors",
        "all",
        "milanese",
        "type",
        "c",
        "usb",
        "max",
        "pro",
        "plus",
        "mini",
        "neo",
        "pin",
        "mm",
    }
)

CANONICAL_MARKETING_NAME = re.compile(r"^iphone air$|^iphone \d+e$", re.I)
STOCK_SKU_MARKERS = (" e-sim", " sim", "warranty", "dubai", "/", "2 year", "non-act")


def normalize_product_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def normalize_tokens(name: str) -> set[str]:
    text = name.lower().replace('"', " inch ").replace("'", "")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*inch\b", r"\1inch", text)
    text = re.sub(r"[^\w\s]", " ", text)
    tokens: set[str] = set()
    for raw in text.split():
        token = raw.strip()
        if not token or token in STOP_TOKENS:
            continue
        if token.isdigit():
            continue
        tokens.add(token)
        if token.endswith("e") and len(token) > 2 and token[-2].isdigit():
            tokens.add(token[:-1] + "e")
    return tokens


def name_similarity(left: str, right: str) -> float:
    a, b = normalize_tokens(left), normalize_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_canonical_marketing_product(name: str) -> bool:
    return bool(CANONICAL_MARKETING_NAME.match(name.strip()))


def is_stock_sku_variant(name: str) -> bool:
    lower = name.lower()
    return any(marker in lower for marker in STOCK_SKU_MARKERS)


def should_skip_article_copy(source_name: str, target_name: str) -> bool:
    """Marketing blogs (iPhone Air, iPhone 17e) must not copy onto priced stock SKUs."""
    if not is_canonical_marketing_product(source_name):
        return False
    return is_stock_sku_variant(target_name)
