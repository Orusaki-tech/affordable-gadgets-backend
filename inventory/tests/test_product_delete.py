"""Product delete must succeed when buying guides protect the product row."""

from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Bundle, InventoryUnit, Product, ProductArticle, UnitAcquisitionSource

pytestmark = [pytest.mark.django_db]


def test_superuser_can_delete_product_that_has_articles(
    super_api_client: APIClient, product: Product
) -> None:
    ProductArticle.objects.create(
        product=product,
        slug="iphone-air-review-the-thinnest-iphone-ever-now-in-kenya",
        headline="Review",
        body="Review body",
        is_published=True,
    )
    ProductArticle.objects.create(
        product=product,
        slug="iphone-air-apples-thinnest-iphone-ever-now-in-kenya",
        headline="Guide",
        body="Guide body",
        is_published=True,
    )

    response = super_api_client.delete(f"/api/inventory/products/{product.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Product.objects.filter(pk=product.id).exists()
    kept = ProductArticle.objects.filter(
        slug__in=[
            "iphone-air-review-the-thinnest-iphone-ever-now-in-kenya",
            "iphone-air-apples-thinnest-iphone-ever-now-in-kenya",
        ]
    )
    assert kept.count() == 2
    assert all(article.product_id is None for article in kept)
    assert all(article.is_primary is False for article in kept)


def test_delete_renames_article_slug_when_standalone_slug_is_taken(
    super_api_client: APIClient, product: Product
) -> None:
    ProductArticle.objects.create(
        product=None,
        slug="shared-guide",
        headline="Already standalone",
        body="Existing",
    )
    attached = ProductArticle.objects.create(
        product=product,
        slug="shared-guide",
        headline="Attached",
        body="Attached body",
    )

    response = super_api_client.delete(f"/api/inventory/products/{product.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    attached.refresh_from_db()
    assert attached.product_id is None
    assert attached.slug == f"shared-guide-{product.id}"


def test_delete_removes_bundles_that_protect_the_product(
    super_api_client: APIClient, product: Product, brand
) -> None:
    bundle = Bundle.objects.create(brand=brand, main_product=product, title="Air kit")

    response = super_api_client.delete(f"/api/inventory/products/{product.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Bundle.objects.filter(pk=bundle.id).exists()
    assert not Product.objects.filter(pk=product.id).exists()


def test_delete_still_blocks_when_available_stock_exists(
    super_api_client: APIClient, product: Product
) -> None:
    source = UnitAcquisitionSource.objects.create(
        source_type=UnitAcquisitionSource.SourceType.SUPPLIER,
        name="Delete Guard Supplier",
    )
    InventoryUnit.objects.create(
        product_template=product,
        selling_price=Decimal("1000.00"),
        cost_of_unit=Decimal("500.00"),
        quantity=2,
        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
        condition=InventoryUnit.ConditionChoices.NEW,
        source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        acquisition_source_details=source,
    )
    ProductArticle.objects.create(product=product, slug="still-here", body="Guide")

    response = super_api_client.delete(f"/api/inventory/products/{product.id}/")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "available inventory unit" in response.data["detail"]
    assert Product.objects.filter(pk=product.id).exists()
    assert ProductArticle.objects.filter(product=product, slug="still-here").exists()
