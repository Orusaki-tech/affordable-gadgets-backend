from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.models import InventoryUnit, Product, Promotion
from inventory.serializers_public import PublicPromotionSerializer


@pytest.mark.django_db
def test_public_promotion_exposes_featured_override_and_promo_card_without_online_units(brand):
    product = Product.objects.create(
        product_name="iPhone 17 Pro E-SIM",
        brand=brand.name,
        model_series="iPhone 17 Pro E-SIM",
        product_type=Product.ProductType.PHONE,
        slug="apple-iphone-17-pro-e-sim",
        is_published=True,
    )
    InventoryUnit.objects.create(
        product_template=product,
        selling_price=Decimal("162000.00"),
        cost_of_unit=Decimal("150000.00"),
        quantity=1,
        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
        available_online=False,
        condition=InventoryUnit.ConditionChoices.NEW,
        grade="A",
        source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        storage_gb=256,
        ram_gb=8,
        serial_number="SN-PROMO-OVERRIDE-001",
        imei="357865098741299",
    )

    now = timezone.now()
    promotion = Promotion.objects.create(
        brand=brand,
        title="Override promo",
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=30),
        is_active=True,
        featured_product=product,
        featured_sale_price=Decimal("148000.00"),
    )
    promotion.products.add(product)

    data = PublicPromotionSerializer(promotion, context={"brand": brand}).data

    assert data["featured_product"] == product.id
    assert Decimal(str(data["featured_sale_price"])) == Decimal("148000.00")
    assert data["promo_card"] is not None
    assert data["promo_card"]["product_slug"] == "apple-iphone-17-pro-e-sim"
    assert Decimal(str(data["promo_card"]["original_price"])) == Decimal("162000.00")
    assert Decimal(str(data["promo_card"]["promotional_price"])) == Decimal("148000.00")
