#!/usr/bin/env python3
"""Audit stock-list CSV vs DB: published, variants, prices. Run inside ag-api-web container."""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

# Django setup when run via manage.py shell - expects models already imported
from inventory.models import Product, ProductVariant

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "inventory" / "data" / "stock_list_2026_06_19_products.csv"
VARIANTS_CSV = ROOT / "inventory" / "data" / "stock_list_2026_06_19_variants.csv"


def resolve_product(name: str) -> Product | None:
    product = Product.objects.filter(product_name=name).first()
    if product:
        return product
    product = Product.objects.filter(product_name__iexact=f"Samsung {name}").first()
    if product:
        return product
    product = Product.objects.filter(model_series=name).first()
    if product:
        return product
    return Product.objects.filter(product_name__iendswith=name).first()


def audit() -> int:
    with PRODUCTS_CSV.open(newline="", encoding="utf-8-sig") as fh:
        stock_products = list(csv.DictReader(fh))
    with VARIANTS_CSV.open(newline="", encoding="utf-8-sig") as fh:
        variant_rows = list(csv.DictReader(fh))

    variant_counts = Counter(r["product_name"] for r in variant_rows)
    expected_prices: dict[str, dict[tuple[int | None, int | None], Decimal]] = defaultdict(dict)
    for row in variant_rows:
        storage = int(row["storage_gb"]) if row.get("storage_gb") else None
        ram = int(row["ram_gb"]) if row.get("ram_gb") else None
        price = Decimal(str(row["ref_sell_kes"]).replace(",", ""))
        expected_prices[row["product_name"]][(storage, ram)] = price

    issues: list[tuple[str, str, str, str]] = []
    ok = 0

    for row in stock_products:
        name = row["product_name"]
        product = resolve_product(name)
        if product is None:
            issues.append(("MISSING", name, "-", "product not in DB"))
            continue
        if not product.is_published:
            issues.append(("UNPUBLISHED", name, str(product.id), "is_published=False"))
        expected_count = variant_counts[name]
        variants = list(ProductVariant.objects.filter(product=product, is_active=True))
        if len(variants) < expected_count:
            issues.append(
                ("VARIANTS", name, str(product.id), f"got {len(variants)}/{expected_count}")
            )
        if product.default_selling_price is None and not variants:
            issues.append(("NO_PRICE", name, str(product.id), "no price and no variants"))
        for variant in variants:
            key = (variant.storage_gb, variant.ram_gb)
            expected = expected_prices[name].get(key)
            if expected is not None and variant.default_selling_price != expected:
                issues.append(
                    (
                        "PRICE",
                        name,
                        str(product.id),
                        f"{key} csv={expected} db={variant.default_selling_price}",
                    )
                )
        if not any(issue[1] == name for issue in issues):
            ok += 1

    print(f"Stock list products: {len(stock_products)}")
    print(f"Fully OK: {ok}")
    print(f"Issues: {len(issues)}")
    for kind, name, pid, detail in issues:
        print(f"  [{kind}] id={pid} {name}: {detail}")

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(audit())
