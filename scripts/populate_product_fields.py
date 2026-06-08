"""
Populate missing Product fields (product_description, long_description,
meta_description, meta_title, keywords) for all published products.

Run on production: python3 manage.py runscript scripts/populate_product_fields
Or via shell: python3 scripts/populate_product_fields.py
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "affordable_gadgets_backend.settings.production")

import django
django.setup()

from inventory.models import Product, ProductArticle


TYPE_LABELS = {
    "PH": "smartphone",
    "TB": "tablet",
    "LT": "laptop",
    "AC": "accessory",
    "TW": "earphones / audio",
    "SW": "smartwatch / wearable",
}


def generate_description(product):
    """Generate a short 1-2 sentence product description."""
    name = product.product_name
    brand = product.brand or ""
    ptype = TYPE_LABELS.get(product.product_type, "device")
    price = ""
    if product.default_selling_price:
        price = f" from Ksh {product.default_selling_price:,.0f}"
    
    templates = [
        f"Shop the {name} by {brand}{price}. This {ptype} delivers reliable performance and great value. Available at Affordable Gadgets KE in Nairobi with warranty and same day shipping.",
        f"The {name} by {brand}{price} offers excellent features and dependable performance. Order online at Affordable Gadgets KE with fast delivery across Kenya and warranty included.",
        f"Buy the {name} by {brand}{price} at Affordable Gadgets KE in Nairobi. A quality {ptype} built for everyday use. Free delivery within Nairobi and warranty on all purchases.",
    ]
    rng = random.Random(name + brand)
    return rng.choice(templates)


def generate_long_description(product):
    """Generate a longer product description."""
    name = product.product_name
    brand = product.brand or ""
    
    templates = [
        f"The {name} by {brand} is designed to deliver a seamless user experience with the features that matter most. Whether you are upgrading or buying your first device, this model offers a great balance of performance, design, and affordability. Available in Kenya at the best price with warranty and same day shipping within Nairobi from Affordable Gadgets KE.",
        f"Experience the {name} from {brand}, a device built for modern living. It combines thoughtful design with practical features to handle your daily tasks with ease. Order today at Affordable Gadgets KE and enjoy competitive pricing, warranty coverage, and fast delivery across Kenya.",
    ]
    rng = random.Random(name + brand + "_long")
    return rng.choice(templates)


def generate_meta_title(product):
    """Generate an SEO meta title."""
    name = product.product_name
    brand = product.brand or ""
    templates = [
        f"{name} | {brand} | Affordable Gadgets KE",
        f"Buy {name} in Kenya | {brand} | Affordable Gadgets KE",
        f"{name} at Best Price in Kenya | {brand} | Affordable Gadgets KE",
    ]
    rng = random.Random(name + brand + "_mt")
    return rng.choice(templates)[:60]


def generate_meta_description(product):
    """Generate an SEO meta description."""
    name = product.product_name
    brand = product.brand or ""
    price = ""
    if product.default_selling_price:
        price = f" from Ksh {product.default_selling_price:,.0f}"
    
    templates = [
        f"Shop the {name} by {brand}{price} in Kenya at Affordable Gadgets KE. ✓ Warranty ✓ Same day shipping in Nairobi. Order online today!",
        f"Buy the {name} by {brand}{price} at the best price in Kenya. Available at Affordable Gadgets KE with warranty and fast delivery. Order now!",
    ]
    rng = random.Random(name + brand + "_md")
    return rng.choice(templates).format(name=name, brand=brand, price=price)[:160]


def generate_keywords(product):
    """Generate SEO keywords string."""
    name = product.product_name
    brand = product.brand or ""
    ptype = TYPE_LABELS.get(product.product_type, "device")
    base = [name, brand, ptype, "Kenya", "best price", "Affordable Gadgets KE", "Nairobi", "buy online"]
    return ", ".join(base)


import random
random.seed(42)


def main():
    qs = Product.objects.filter(is_published=True)
    total = qs.count()
    
    updated = {
        "product_description": 0,
        "long_description": 0,
        "meta_title": 0,
        "meta_description": 0,
        "keywords": 0,
    }
    
    for p in qs:
        changed = False
        if not p.product_description:
            p.product_description = generate_description(p)
            changed = True
            updated["product_description"] += 1
        if not p.long_description:
            p.long_description = generate_long_description(p)
            changed = True
            updated["long_description"] += 1
        if not p.meta_title:
            p.meta_title = generate_meta_title(p)
            changed = True
            updated["meta_title"] += 1
        if not p.meta_description:
            p.meta_description = generate_meta_description(p)
            changed = True
            updated["meta_description"] += 1
        if not p.keywords:
            p.keywords = generate_keywords(p)
            changed = True
            updated["keywords"] += 1
        if changed:
            p.save(update_fields=["product_description", "long_description", "meta_title", "meta_description", "keywords"])
    
    print(f"Total products: {total}")
    for field, count in updated.items():
        print(f"Updated {field}: {count}")


if __name__ == "__main__":
    main()
