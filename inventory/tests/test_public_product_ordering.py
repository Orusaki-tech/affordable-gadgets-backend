from datetime import date

import pytest
from model_bakery import baker

from inventory.models import Product
from inventory.product_ordering import apply_product_ordering


@pytest.mark.django_db
def test_apply_product_ordering_latest_release_date_first():
    older = baker.make(
        Product,
        product_name="Galaxy S24",
        brand="Samsung",
        model_series="Galaxy S24",
        product_type=Product.ProductType.PHONE,
        release_date=date(2024, 1, 31),
    )
    newer = baker.make(
        Product,
        product_name="Galaxy S26 Ultra",
        brand="Samsung",
        model_series="Galaxy S26 Ultra",
        product_type=Product.ProductType.PHONE,
        release_date=date(2026, 2, 25),
    )
    undated = baker.make(
        Product,
        product_name="Adapter 20W",
        brand="Apple",
        model_series="Charger",
        product_type=Product.ProductType.ACCESSORY,
        release_date=None,
    )

    ordered_ids = list(
        apply_product_ordering(Product.objects.all(), None).values_list("id", flat=True)
    )

    assert ordered_ids.index(newer.id) < ordered_ids.index(older.id)
    assert ordered_ids.index(older.id) < ordered_ids.index(undated.id)
