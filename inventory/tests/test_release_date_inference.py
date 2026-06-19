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
    assert normalize_product_name("Samsung Galaxy Z Fold 7 256GB 12GB RAM") == "samsung galaxy z fold 7"
    assert normalize_product_name("OnePlus 13 256GB 12GB RAM") == "oneplus 13"
    assert normalize_product_name("iPad 11th gen 128GB Cellular") == "ipad 11 cellular"


def test_infer_release_date_for_flagship_phones():
    assert infer_release_date("Samsung Galaxy S26 Ultra 256GB 12GB RAM") == date(2026, 2, 1)
    assert infer_release_date("Samsung Galaxy Z Fold 7 256GB 12GB RAM") == date(2025, 7, 1)
    assert infer_release_date("OnePlus 13 256GB 12GB RAM") == date(2025, 1, 1)
    assert infer_release_date("Nothing Phone 3 256GB 12GB RAM") == date(2025, 7, 1)
    assert infer_release_date("Pixel 10 128GB 12GB RAM") == date(2025, 10, 1)
    assert infer_release_date("iPhone 17 Pro Max") == date(2025, 9, 1)
    assert infer_release_date("iPhone 17E 256GB SIM (Official)") == date(2026, 3, 1)
    assert infer_release_date("Google Pixel 9 Pro XL 256GB 12GB RAM") == date(2024, 8, 1)


def test_infer_release_date_for_budget_series():
    assert infer_release_date("Galaxy A42 5G") == date(2020, 12, 1)
    assert match_family_key("Galaxy A42 5G") == "galaxy-a42"


def test_infer_release_date_returns_none_for_generic_accessories():
    assert infer_release_date("Unknown Widget XYZ") is None


def test_infer_release_date_for_accessories_and_budget_phones():
    assert infer_release_date("Adapter 20W") == date(2020, 10, 1)
    assert infer_release_date("Galaxy A06") == date(2024, 8, 1)
    assert infer_release_date("Pixel 9A") == date(2025, 4, 1)
    assert infer_release_date("iPhone SE(3rd Gen)") == date(2022, 3, 1)
    assert infer_release_date("MacBook 13\" Neo") == date(2026, 3, 1)
