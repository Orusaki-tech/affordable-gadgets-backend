import pytest
from model_bakery import baker

from inventory.models import Product, ProductSlugRedirect
from inventory.management.commands.backfill_slug_redirects import (
    _names_compatible,
    _slug_pair_compatible,
    _variant_slugs,
)


@pytest.mark.django_db
def test_backfill_slug_pair_compatible_for_renamed_samsung_a06():
    product = baker.make(
        Product,
        slug="samsung-a-series-galaxy-a06",
        product_name="Galaxy A06",
        brand="Samsung",
        model_series="galaxy a06",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    assert _slug_pair_compatible("samsung-galaxy-a06", product)
    assert _names_compatible("Samsung Galaxy A06", product)


@pytest.mark.django_db
def test_variant_slugs_include_product_name_slug():
    product = baker.make(
        Product,
        slug="samsung-a-series-galaxy-a06",
        product_name="Galaxy A06",
        brand="Samsung",
        model_series="galaxy a06",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    variants = _variant_slugs(product)
    assert "galaxy-a06" in variants


@pytest.mark.django_db
def test_backfill_command_creates_redirect_for_explicit_pair():
    product = baker.make(
        Product,
        slug="samsung-a-series-galaxy-a06",
        product_name="Galaxy A06",
        brand="Samsung",
        model_series="galaxy a06",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )

    from django.core.management import call_command

    call_command(
        "backfill_slug_redirects",
        slug=[f"samsung-galaxy-a06={product.slug}"],
    )

    redirect = ProductSlugRedirect.objects.get(old_slug="samsung-galaxy-a06")
    assert redirect.product_id == product.id


@pytest.mark.django_db
def test_unpublish_test_products_command():
    test_product = baker.make(
        Product,
        slug="test-payment-product",
        product_name="test payment product",
        brand="test",
        product_type=Product.ProductType.ACCESSORY,
        is_published=True,
        is_discontinued=False,
    )
    live_product = baker.make(
        Product,
        slug="samsung-galaxy-a17-4g",
        product_name="Samsung Galaxy A17 4G",
        brand="Samsung",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )

    from django.core.management import call_command

    call_command("unpublish_test_products")

    test_product.refresh_from_db()
    live_product.refresh_from_db()
    assert test_product.is_published is False
    assert live_product.is_published is True
