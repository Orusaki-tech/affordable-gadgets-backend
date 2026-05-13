"""Tests for Product.default_selling_price and public price fallback."""

from decimal import Decimal

from django.test import TestCase

from inventory.models import InventoryUnit, Product
from inventory.serializers import InventoryUnitSerializer
from inventory.serializers_public import PublicProductSerializer


class PublicProductDefaultPriceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            product_name="Default Price Catalog Item",
            brand="TestBrand",
            model_series="X1",
            product_type=Product.ProductType.ACCESSORY,
            default_selling_price=Decimal("12500.50"),
        )

    def test_min_max_fallback_when_no_listable_units_prefetched(self):
        setattr(self.product, "available_units_list", [])
        ser = PublicProductSerializer(
            self.product, context={"view_action": "list"}
        )
        self.assertEqual(ser.data["min_price"], 12500.5)
        self.assertEqual(ser.data["max_price"], 12500.5)

    def test_min_max_from_units_when_listable_units_exist(self):
        InventoryUnit.objects.create(
            product_template=self.product,
            cost_of_unit=Decimal("100.00"),
            selling_price=Decimal("200.00"),
            quantity=3,
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True,
        )
        ser = PublicProductSerializer(self.product, context={})
        self.assertEqual(ser.data["min_price"], 200.0)
        self.assertEqual(ser.data["max_price"], 200.0)

    def test_no_fallback_when_default_unset(self):
        bare = Product.objects.create(
            product_name="No Default",
            brand="B",
            model_series="M",
            product_type=Product.ProductType.ACCESSORY,
        )
        setattr(bare, "available_units_list", [])
        ser = PublicProductSerializer(bare, context={"view_action": "list"})
        self.assertIsNone(ser.data["min_price"])
        self.assertIsNone(ser.data["max_price"])


class InventoryUnitDefaultSellingPriceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            product_name="Accessory With Default",
            brand="B",
            model_series="M",
            product_type=Product.ProductType.ACCESSORY,
            default_selling_price=Decimal("88.00"),
        )

    def test_create_uses_product_default_when_selling_price_omitted(self):
        ser = InventoryUnitSerializer(
            data={
                "product_template_id": self.product.id,
                "cost_of_unit": "40.00",
                "quantity": 2,
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["selling_price"], Decimal("88.00"))

    def test_create_requires_selling_price_when_no_product_default(self):
        bare = Product.objects.create(
            product_name="No Default Product",
            brand="B",
            model_series="M2",
            product_type=Product.ProductType.ACCESSORY,
        )
        ser = InventoryUnitSerializer(
            data={
                "product_template_id": bare.id,
                "cost_of_unit": "10.00",
                "quantity": 1,
            }
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("selling_price", ser.errors)
