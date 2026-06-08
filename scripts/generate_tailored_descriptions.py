"""
Generate per-product descriptions (product_description, long_description)
that highlight each product's specific features using available data.

Prioritises real InventoryUnit data, falls back to parsing specs from
product_name, then falls back to type-aware feature highlighting.

Run in container: python3 manage.py runscript scripts.generate_tailored_descriptions
Or standalone:    python3 scripts/generate_tailored_descriptions.py
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings_production")

import django
django.setup()

from django.db.models import Min, Max
from inventory.models import Product, InventoryUnit

_GB_RE = re.compile(r'(\d+)\s*GB', re.IGNORECASE)
_RAM_RE = re.compile(r'(\d+)\s*(?:GB)?\s*RAM', re.IGNORECASE)
_INCH_RE = re.compile(r'(\d+\.?\d*)\s*"?inch', re.IGNORECASE)
_MHZ_RE = re.compile(r'(\d+(?:\.\d+)?)\s*GHz', re.IGNORECASE)
_BATTERY_RE = re.compile(r'(\d+)\s*m[Aa][Hh]', re.IGNORECASE)

PHONE_FEATURES = {
    "samsung galaxy s25 ultra": ["200MP camera", "S Pen", "Snapdragon 8 Elite chip", "large Dynamic AMOLED display"],
    "samsung galaxy s25": ["powerful Snapdragon 8 Elite chip", "advanced camera system", "vivid Dynamic AMOLED display"],
    "samsung galaxy s24 ultra": ["200MP camera with 100x Space Zoom", "S Pen support", "Snapdragon 8 Gen 3 chip", "titanium frame"],
    "samsung galaxy s24": ["Exynos 2400 chip", "AI-powered features", "120Hz AMOLED display", "long-lasting battery"],
    "samsung galaxy s23 ultra": ["200MP camera", "built-in S Pen", "Snapdragon 8 Gen 2 chip", "stunning 120Hz display"],
    "samsung galaxy s23": ["pro-grade camera system", "Snapdragon 8 Gen 2 performance", "compact and elegant design"],
    "samsung galaxy s22": ["50MP camera with nightography", "4nm processor", "Dynamic AMOLED 2X display"],
    "samsung galaxy s21": ["64MP camera", "Exynos 2100 chip", "120Hz display", "iconic contour-cut design"],
    "samsung galaxy s20": ["64MP camera with 8K video", "120Hz display", "powerful performance"],
    "samsung galaxy z fold": ["foldable 7.6-inch display", "powerful multitasking", "flagship performance"],
    "samsung galaxy z flip": ["compact foldable design", "Flex Mode camera", "iconic design"],
    "samsung galaxy a": ["massive battery and sharp display", "affordable flagship features"],
    "samsung galaxy m": ["massive battery", "Super AMOLED display", "great value for money"],
    "iphone 16 pro max": ["A18 Pro chip", "48MP Fusion camera system", "titanium design", "largest iPhone display ever"],
    "iphone 16 pro": ["A18 Pro chip", "48MP camera with 5x optical zoom", "titanium design"],
    "iphone 16": ["A18 chip", "48MP camera", "Action Button", "Apple Intelligence"],
    "iphone 15 pro max": ["A17 Pro chip", "48MP camera with 5x optical zoom", "titanium design", "USB-C"],
    "iphone 15 pro": ["A17 Pro chip", "48MP camera", "titanium design", "USB-C"],
    "iphone 15": ["48MP camera", "Dynamic Island", "A16 Bionic chip", "USB-C"],
    "iphone 14 pro max": ["48MP camera", "Dynamic Island", "A16 Bionic chip", "always-on display"],
    "iphone 14": ["A15 Bionic chip", "great camera system", "long battery life"],
    "iphone 13": ["A15 Bionic chip", "great dual-camera system", "long battery life"],
    "iphone 12 pro max": ["LiDAR scanner", "triple 12MP camera system", "ceramic shield"],
    "iphone 12": ["A14 Bionic chip", "OLED display", "MagSafe support"],
    "iphone se": ["A15 Bionic chip", "compact design", "Touch ID", "great value"],
    "iphone 11": ["dual 12MP camera system", "A13 Bionic chip", "long battery life"],
    "pixel": ["best-in-class camera", "pure Android experience", "AI-powered features", "Google Tensor chip"],
    "xiaomi": ["flagship camera specs", "fast charging", "great value", "high refresh rate display"],
    "oneplus": ["flagship performance", "fast charging", "smooth display", "clean software experience"],
    "sony xperia": ["professional camera features", "4K HDR display", "headphone jack", "expandable storage"],
}

TABLET_FEATURES = {
    "ipad pro": ["M-series chip", "Liquid Retina XDR display", "pro-level performance", "Apple Pencil support"],
    "ipad air": ["M-series chip", "Liquid Retina display", "slim and lightweight", "Apple Pencil support"],
    "ipad": ["A-series chip", "Liquid Retina display", "great for everyday use", "Apple Pencil support"],
    "galaxy tab s": ["Dynamic AMOLED display", "S Pen included", "flagship performance", "DeX mode"],
    "galaxy tab a": ["great value tablet", "long battery life", "expandable storage", "kids-friendly features"],
}

LAPTOP_FEATURES = {
    "macbook pro": ["M-series chip", "stunning Retina display", "all-day battery life", "pro-level performance"],
    "macbook air": ["M-series chip", "lightweight design", "silent fanless operation", "all-day battery life"],
    "dell xps": ["InfinityEdge display", "Intel Core processors", "premium build", "compact design"],
    "thinkpad": ["legendary keyboard", "durable build", "enterprise-grade security", "TrackPoint"],
    "hp spectre": ["360-degree hinge", "premium design", "high-res touch display", "HP Pen support"],
    "surface pro": ["versatile 2-in-1 design", "Surface Pen support", "full Windows experience", "kickstand"],
}


def _parse_specs_from_name(name):
    """Extract storage, RAM from product name like 'iPhone 15 128GB' or 'Samsung Galaxy S25 FE 128GB 8GB RAM'"""
    storage = None
    ram = None
    display_size = None
    processor_ghz = None
    battery = None

    # Find all "XXGB" patterns
    gb_matches = _GB_RE.findall(name)
    ram_match = _RAM_RE.search(name)

    if ram_match:
        ram = int(ram_match.group(1))
        gb_matches = [m for m in gb_matches if int(m) != ram]

    if gb_matches:
        storage = max(int(x) for x in gb_matches)

    inch_match = _INCH_RE.search(name)
    if inch_match:
        display_size = float(inch_match.group(1))

    ghz_match = _MHZ_RE.search(name)
    if ghz_match:
        processor_ghz = float(ghz_match.group(1))

    battery_match = _BATTERY_RE.search(name)
    if battery_match:
        battery = int(battery_match.group(1))

    return storage, ram, display_size, processor_ghz, battery


def _get_unit_data(product):
    units = InventoryUnit.objects.filter(product_template=product, available_online=True)
    has_data = units.exists()

    if has_data:
        agg = units.aggregate(min_price=Min("selling_price"), max_price=Max("selling_price"))
        storages = sorted(set(u.storage_gb for u in units if u.storage_gb))
        rams = sorted(set(u.ram_gb for u in units if u.ram_gb))
        batteries = sorted(set(u.battery_mah for u in units if u.battery_mah))
        colors = sorted(set(u.product_color.name for u in units if u.product_color and u.product_color.name))
        processors = sorted(set(u.processor_details for u in units if u.processor_details))
        conditions = sorted(set(u.get_condition_display() for u in units if u.condition))
    else:
        agg = {}
        storages, rams, _, _, batteries = _parse_specs_from_name(product.product_name)
        storages = [storages] if storages else []
        rams = [rams] if rams else []
        batteries = [batteries] if batteries else []
        colors = []
        processors = []
        conditions = []

    return {
        "min_price": agg.get("min_price") if has_data else None,
        "max_price": agg.get("max_price") if has_data else None,
        "storages": storages,
        "rams": rams,
        "batteries": batteries,
        "colors": colors,
        "processors": processors,
        "conditions": conditions,
        "has_data": has_data,
    }


def _price_str(d):
    mp = d.get("min_price")
    if not mp:
        return ""
    mx = d.get("max_price")
    if mp == mx or mx is None:
        return f" from Ksh {mp:,.0f}"
    return f" from Ksh {mp:,.0f} to Ksh {mx:,.0f}"


def _colors_str(d):
    cs = d.get("colors", [])
    if not cs:
        return ""
    if len(cs) == 1:
        return f" Available in {cs[0]}."
    return f" Available in {', '.join(cs[:-1])} and {cs[-1]}."


def _condition_str(d):
    cs = d.get("conditions", [])
    if not cs:
        return ""
    return f" ({' / '.join(cs)})"


def _spec_line(d):
    parts = []
    storages = d.get("storages", [])
    rams = d.get("rams", [])
    if storages:
        parts.append(f"{max(storages)}GB storage")
    if rams:
        parts.append(f"{max(rams)}GB RAM")
    return " with " + ", ".join(parts) if parts else ""


def _known_features(product, db):
    """Look up product in known-feature dicts based on lowercase name match."""
    name_lower = product.product_name.lower()
    brand_lower = (product.brand or "").lower()

    if product.product_type == "PH":
        candidates = PHONE_FEATURES
    elif product.product_type == "TB":
        candidates = TABLET_FEATURES
    elif product.product_type == "LT":
        candidates = LAPTOP_FEATURES
    else:
        return None

    for key, features in candidates.items():
        if key in name_lower:
            return features

    if brand_lower in candidates:
        return candidates[brand_lower]

    return None


TYPE_ADJECTIVES = {
    "PH": {
        "short_adj": "a powerful and reliable smartphone",
        "long_adj": "delivers outstanding performance and great value",
    },
    "TB": {
        "short_adj": "a sleek and portable tablet",
        "long_adj": "combines portability with powerful features for work and entertainment",
    },
    "LT": {
        "short_adj": "a powerful and portable laptop",
        "long_adj": "is built for productivity and performance whether at home or on the go",
    },
    "AC": {
        "short_adj": "a must-have accessory",
        "long_adj": "is the perfect addition to your device setup",
    },
}


def generate_short_description(p):
    d = _get_unit_data(p)
    ptype = p.product_type
    adj = TYPE_ADJECTIVES.get(ptype, TYPE_ADJECTIVES["AC"])
    features = _known_features(p, d)
    price_s = _price_str(d)

    if features:
        top = features[0]
        return (
            f"The {p.product_name} by {p.brand}{price_s} features {top}"
            f"{_spec_line(d)}. Order at Affordable Gadgets KE in Nairobi with warranty and fast delivery across Kenya."
        )

    if d.get("storages") or d.get("rams"):
        return (
            f"The {p.product_name} by {p.brand}{price_s} features {adj['short_adj']}"
            f"{_spec_line(d)}.{_colors_str(d)} Order at Affordable Gadgets KE in Nairobi with warranty and fast delivery across Kenya."
        )

    return (
        f"The {p.product_name} by {p.brand}{price_s} is {adj['short_adj']}"
        f". Order at Affordable Gadgets KE in Nairobi with warranty and fast delivery across Kenya."
    )


def generate_long_description(p):
    d = _get_unit_data(p)
    ptype = p.product_type
    adj = TYPE_ADJECTIVES.get(ptype, TYPE_ADJECTIVES["AC"])
    features = _known_features(p, d)

    parts = [f"The {p.product_name} by {p.brand} {adj['long_adj']}."]

    if features:
        parts.append(f"Highlights include {', '.join(features)}.")

    if d.get("storages") or d.get("rams"):
        parts.append(
            f"With {_format_storage_ram(d)}, it is ready to handle your daily tasks with ease."
        )

    if d.get("batteries") and ptype == "PH":
        parts.append(
            f"The {max(d['batteries'])}mAh battery keeps you powered all day."
        )

    if d.get("colors"):
        parts.append(f"Available in {_format_colors(d)}.{_colors_str(d)}")

    parts.append(
        f"Shop at Affordable Gadgets KE in Nairobi{_condition_str(d)} with warranty coverage and fast delivery across Kenya."
    )
    return " ".join(parts)


def _format_storage_ram(d):
    storages = d.get("storages", [])
    rams = d.get("rams", [])
    if storages and rams:
        return f"up to {max(storages)}GB storage and {max(rams)}GB RAM"
    elif storages:
        return f"up to {max(storages)}GB storage"
    elif rams:
        return f"up to {max(rams)}GB RAM"
    return "ample storage and memory"


def _format_colors(d):
    cs = d.get("colors", [])
    if not cs:
        return ""
    if len(cs) == 1:
        return cs[0]
    return ", ".join(cs[:-1]) + " and " + cs[-1]


def main():
    qs = Product.objects.filter(is_published=True).order_by("id")
    total = qs.count()

    updated_desc = 0
    updated_long = 0

    for p in qs:
        short = generate_short_description(p)
        long = generate_long_description(p)
        changed = False
        if p.product_description != short:
            p.product_description = short
            changed = True
        if p.long_description != long:
            p.long_description = long
            changed = True
        if changed:
            p.save(update_fields=["product_description", "long_description"])
            updated_desc += 1
            updated_long += 1

    print(f"Products processed: {total}")
    print(f"Short descriptions updated: {updated_desc}")
    print(f"Long descriptions updated: {updated_long}")


if __name__ == "__main__":
    main()
