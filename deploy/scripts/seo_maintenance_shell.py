"""One-shot SEO maintenance for production (run via manage.py shell < script)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from django.db import transaction
from django.utils.text import slugify

from inventory.models import Product, ProductSlugRedirect

GENERIC_TOKENS = frozenset(
    {
        "samsung", "apple", "google", "xiaomi", "vivo", "tecno", "infinix", "oppo", "oneplus",
        "realme", "huawei", "nokia", "galaxy", "iphone", "ipad", "macbook", "phone", "series",
        "pro", "max", "plus", "ultra", "lite", "mini", "lte", "5g", "4g", "gb", "ram",
        "the", "and", "for", "with", "new",
    }
)
TEST_SLUG_RE = re.compile(
    r"^(test-|test\d|demo-|sample-)|(?:^|-)test(?:-|$)|test-payment|test-2test",
    re.IGNORECASE,
)
DRY_RUN = __import__("os").environ.get("SEO_MAINTENANCE_DRY_RUN", "0") == "1"


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def meaningful_tokens(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in slugify(part or "").split("-"):
            if token and token not in GENERIC_TOKENS:
                tokens.add(token)
    return tokens


def names_compatible(csv_name: str, product: Product) -> bool:
    left = normalize_name(csv_name)
    right = normalize_name(product.product_name)
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    overlap = meaningful_tokens(left) & meaningful_tokens(right)
    return len(overlap) >= 2 or any(re.search(r"\d", token) for token in overlap)


def slug_pair_compatible(old_slug: str, product: Product) -> bool:
    if not old_slug or old_slug == (product.slug or ""):
        return False
    old_tokens = meaningful_tokens(old_slug)
    live_tokens = meaningful_tokens(
        product.slug or "",
        product.product_name or "",
        product.model_series or "",
        product.brand or "",
    )
    if not old_tokens:
        return False
    overlap = old_tokens & live_tokens
    return len(overlap) >= 2 or (
        len(overlap) >= 1 and any(re.search(r"\d", token) for token in overlap)
    )


def variant_slugs(product: Product) -> set[str]:
    brand = (product.brand or "").strip()
    name = (product.product_name or "").strip()
    series = (product.model_series or "").strip()
    return {
        slug
        for slug in {
            slugify(name),
            slugify(f"{brand} {name}"),
            slugify(f"{brand} {series}"),
            slugify(series),
            slugify(f"{brand}-{series}"),
        }
        if slug
    }


def is_test_product(product: Product) -> bool:
    slug = (product.slug or "").strip().lower()
    name = (product.product_name or "").strip().lower()
    if TEST_SLUG_RE.search(slug):
        return True
    if name in {"test", "test1", "test payment product"}:
        return True
    return slug in {"test-payment-product", "test-2test1-test1"}


def main() -> None:
    products = list(
        Product.objects.filter(is_discontinued=False, is_published=True).only(
            "id", "slug", "product_name", "brand", "model_series", "is_published"
        )
    )
    products_by_slug = {(p.slug or "").strip(): p for p in products if p.slug}
    existing_redirects = {
        row.old_slug: row.product_id
        for row in ProductSlugRedirect.objects.values("old_slug", "product_id")
    }

    proposals: dict[str, int] = {}
    for product in products:
        for old_slug in variant_slugs(product):
            if slug_pair_compatible(old_slug, product):
                current_slug = (product.slug or "").strip()
                if old_slug == current_slug:
                    continue
                if old_slug in products_by_slug and products_by_slug[old_slug].id != product.id:
                    continue
                if old_slug in existing_redirects:
                    continue
                proposals[old_slug] = product.id

    csv_path = Path("products_final_schema.csv")
    if csv_path.is_file():
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("is_published", "").lower() != "true":
                    continue
                old_slug = (row.get("slug") or "").strip()
                if not old_slug:
                    continue
                brand = (row.get("brand") or "").strip()
                for product in products:
                    if brand and product.brand and brand.lower() != product.brand.lower():
                        continue
                    if not names_compatible(row.get("product_name", ""), product):
                        continue
                    if not slug_pair_compatible(old_slug, product):
                        continue
                    current_slug = (product.slug or "").strip()
                    if old_slug == current_slug or old_slug in existing_redirects:
                        continue
                    if old_slug in products_by_slug and products_by_slug[old_slug].id != product.id:
                        continue
                    proposals[old_slug] = product.id

    # Explicit high-traffic legacy slugs
    explicit_pairs = {
        "samsung-galaxy-a06": "samsung-a-series-galaxy-a06",
        "samsung-galaxy-s10e": "samsung-s-series-galaxy-s10e",
        "samsung-galaxy-fold-5": "samsung-galaxy-z-fold-5",
    }
    for old_slug, new_slug in explicit_pairs.items():
        product = products_by_slug.get(new_slug)
        if product and old_slug not in existing_redirects and old_slug not in proposals:
            proposals[old_slug] = product.id

    test_products = [p for p in products if is_test_product(p)]
    print(f"Published products: {len(products)}")
    print(f"Redirect candidates: {len(proposals)}")
    print(f"Test products to unpublish: {len(test_products)}")
    for old_slug, product_id in sorted(proposals.items())[:25]:
        product = next(p for p in products if p.id == product_id)
        print(f"  redirect {old_slug} -> {product.slug} (id={product.id})")
    if len(proposals) > 25:
        print(f"  ... +{len(proposals) - 25} more")
    for product in test_products:
        print(f"  unpublish id={product.id} {product.slug}")

    if DRY_RUN:
        print("DRY RUN — no changes written")
        return

    with transaction.atomic():
        ProductSlugRedirect.objects.bulk_create(
            [ProductSlugRedirect(old_slug=old_slug, product_id=product_id) for old_slug, product_id in proposals.items()],
            ignore_conflicts=True,
        )
        if test_products:
            for product in test_products:
                product.is_published = False
            Product.objects.bulk_update(test_products, ["is_published"])

    print(f"Created {len(proposals)} redirects; unpublished {len(test_products)} test products")


main()
