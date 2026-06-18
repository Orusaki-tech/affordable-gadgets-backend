from datetime import date

from inventory.release_date_inference import (
    infer_release_date,
    match_family_key,
    normalize_product_name,
)


def test_normalize_product_name_strips_storage_and_region_tags():
    assert (
        normalize_product_name("iPhone 17 Pro Max 256GB SIM (Dubai)")
        == "iphone 17 pro max"
    )


def test_infer_release_date_for_flagship_phones():
    assert infer_release_date("Samsung Galaxy S26 Ultra 256GB 12GB RAM") == date(2026, 2, 25)
    assert infer_release_date("iPhone 17 Pro Max") == date(2025, 9, 19)
    assert infer_release_date("Google Pixel 9 Pro XL 256GB 12GB RAM") == date(2024, 8, 22)


def test_infer_release_date_for_budget_series():
    assert infer_release_date("Galaxy A42 5G") == date(2020, 12, 2)
    assert match_family_key("Galaxy A42 5G") == "galaxy-a42"


def test_infer_release_date_returns_none_for_generic_accessories():
    assert infer_release_date("Adapter 20W") is None
    assert infer_release_date("3 in 1 wireless charger") is None
