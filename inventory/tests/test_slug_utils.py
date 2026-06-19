import pytest
from model_bakery import baker

from inventory.models import Product, ProductSlugRedirect
from inventory.slug_utils import (
    allocate_unique_slugs,
    build_seo_product_slug,
    resolve_product_for_slug,
)


@pytest.mark.parametrize(
    ("brand", "model_series", "product_name", "expected"),
    [
        ("Samsung", "Galaxy A57", "Samsung Galaxy A57", "samsung-galaxy-a57"),
        ("Samsung", "Samsung Galaxy S26 Ultra", "Galaxy S26 Ultra", "samsung-galaxy-s26-ultra"),
        ("Apple", "Watch Ultra 3 2025 49mm", "Apple Watch Ultra 3 (2025) 49mm", "apple-watch-ultra-3-2025-49mm"),
        ("Apple", "iPhone 20W Adapter", "Adapter 20W", "apple-iphone-20w-adapter"),
        ("Apple", "iPhone 17 Air E-SIM 2 Year Warranty Blue/Black", "iPhone 17 Air E-SIM 2 Year Warranty Blue/Black", "apple-iphone-17-air-e-sim-2-year-warranty-blueblack"),
        ("", "", "Google Pixel 7A", "google-pixel-7a"),
    ],
)
def test_build_seo_product_slug_examples(brand, model_series, product_name, expected):
    slug = build_seo_product_slug(
        brand=brand,
        model_series=model_series,
        product_name=product_name,
        product_type=Product.ProductType.PHONE,
    )
    assert slug == expected


def test_build_seo_product_slug_drops_type_suffix():
    slug = build_seo_product_slug(
        brand="Samsung",
        model_series="Galaxy A57",
        product_name="Samsung Galaxy A57",
        product_type="PH",
    )
    assert not slug.endswith("-ph")


def test_allocate_unique_slugs_handles_collisions():
    assigned = allocate_unique_slugs([(1, "iphone-15"), (2, "iphone-15"), (3, "pixel-8")])
    assert assigned[1] == "iphone-15"
    assert assigned[2] == "iphone-15-2"
    assert assigned[3] == "pixel-8"


@pytest.mark.django_db
def test_resolve_product_for_slug_uses_redirect():
    product = baker.make(
        Product,
        slug="samsung-galaxy-a57",
        product_name="Samsung Galaxy A57",
        brand="Samsung",
        model_series="Galaxy A57",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    ProductSlugRedirect.objects.create(old_slug="samsung-galaxy-a57-samsung-galaxy-a57-ph", product=product)

    resolved, legacy = resolve_product_for_slug(
        "samsung-galaxy-a57-samsung-galaxy-a57-ph",
        queryset=Product.objects.filter(is_published=True, is_discontinued=False),
    )
    assert legacy is True
    assert resolved == product

    canonical, legacy = resolve_product_for_slug(
        "samsung-galaxy-a57",
        queryset=Product.objects.filter(is_published=True, is_discontinued=False),
    )
    assert legacy is False
    assert canonical == product
