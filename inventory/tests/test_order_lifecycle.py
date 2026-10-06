"""P0: Order creation, idempotency, stock deduction, and status transitions.

These are the most critical money-moving code paths in the system.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Brand, InventoryUnit, Order, Product

pytestmark = [pytest.mark.p0, pytest.mark.django_db]


class TestOrderCreation:
    """Verify order can be created with nested order items."""

    def test_create_order_with_items(
        self,
        sales_api_client: APIClient,
        customer: Any,
        product: Product,
        available_unit: InventoryUnit,
        brand: Brand,
    ) -> None:
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "total_amount": "55000.00",
            "order_source": "WALK_IN",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                }
            ],
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()
        assert "order_id" in data
        assert data["status"] == "Pending"

    def test_ignores_client_unit_price_undercut(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        brand: Brand,
    ) -> None:
        """Client-supplied unit_price_at_purchase must not undercut list/cart price."""
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                    "unit_price_at_purchase": "0.00",
                }
            ],
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()
        assert Decimal(str(data["total_amount"])) == available_unit.selling_price
        item = data["order_items"][0]
        assert Decimal(str(item["unit_price_at_purchase"])) == available_unit.selling_price

    def test_online_order_uses_cart_items_not_client_sku_swap(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        make_unit: Any,
        product: Product,
        brand: Brand,
    ) -> None:
        """If an open cart exists, order lines come from the cart — not a swapped unit id."""
        from inventory.models import Cart, CartItem

        cheap_unit = make_unit(product)
        cart = Cart.objects.create(customer=customer, brand=brand, is_submitted=False)
        CartItem.objects.create(
            cart=cart,
            inventory_unit=available_unit,
            quantity=1,
            unit_price=available_unit.selling_price,
        )

        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": cheap_unit.id,
                    "quantity": 1,
                }
            ],
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()
        assert len(data["order_items"]) == 1
        assert data["order_items"][0]["inventory_unit"] == available_unit.id

    def test_online_order_ignores_other_brand_cart_same_phone(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        make_unit: Any,
        product: Product,
        brand: Brand,
        other_brand: Brand,
    ) -> None:
        """Phone match must not pull lines from another brand's open cart."""
        from inventory.models import Cart, CartItem

        other_unit = make_unit(product)
        Cart.objects.create(
            customer_phone=customer.phone,
            brand=other_brand,
            is_submitted=False,
        )
        other_cart = Cart.objects.filter(brand=other_brand, customer_phone=customer.phone).first()
        CartItem.objects.create(
            cart=other_cart,
            inventory_unit=other_unit,
            quantity=1,
            unit_price=other_unit.selling_price,
        )
        # No open cart on the order brand — order should use the requested unit only.
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": customer.phone,
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                }
            ],
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()
        assert len(data["order_items"]) == 1
        assert data["order_items"][0]["inventory_unit"] == available_unit.id

    def test_online_order_ignores_other_customer_cart_same_phone(
        self,
        customer: Any,
        available_unit: InventoryUnit,
        make_unit: Any,
        product: Product,
        brand: Brand,
        django_user_model: Any,
    ) -> None:
        """Same phone on another customer's cart must not rebuild this order."""
        from inventory.models import Cart, CartItem, Customer

        other_user = django_user_model.objects.create_user(
            username="phone-twin", email="twin@example.com", password="x"
        )
        other_customer = Customer.objects.create(
            user=other_user, name="Twin", phone=customer.phone, email="twin@example.com"
        )
        other_unit = make_unit(product)
        other_cart = Cart.objects.create(
            customer=other_customer,
            customer_phone=customer.phone,
            brand=brand,
            is_submitted=False,
        )
        CartItem.objects.create(
            cart=other_cart,
            inventory_unit=other_unit,
            quantity=1,
            unit_price=other_unit.selling_price,
        )

        # Authenticate as the ordering customer (not staff) so phone get_or_create
        # cannot reassign the order to the phone-twin account.
        client = APIClient()
        client.force_authenticate(user=customer.user)
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": customer.phone,
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                }
            ],
        }
        response = client.post(url, payload, format="json", HTTP_X_BRAND_CODE=brand.code)
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()
        assert data["order_items"][0]["inventory_unit"] == available_unit.id

    def test_confirm_payment_sets_partial_paid_flags(
        self,
        sales_api_client: APIClient,
        order_with_units: Order,
        available_unit: InventoryUnit,
    ) -> None:
        available_unit.sale_status = InventoryUnit.SaleStatusChoices.PENDING_PAYMENT
        available_unit.save(update_fields=["sale_status"])
        order_with_units.is_items_paid = False
        order_with_units.is_delivery_paid = False
        order_with_units.status = Order.StatusChoices.PENDING
        order_with_units.save(
            update_fields=["is_items_paid", "is_delivery_paid", "status"]
        )

        url = f"/api/inventory/orders/{order_with_units.order_id}/confirm_payment/"
        response = sales_api_client.post(url, {"payment_method": "CASH"}, format="json")
        assert response.status_code == status.HTTP_200_OK, response.content
        order_with_units.refresh_from_db()
        assert order_with_units.status == Order.StatusChoices.PAID
        assert order_with_units.is_items_paid is True
        assert order_with_units.is_delivery_paid is True

    def test_online_delivery_without_county_rejected(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        brand: Brand,
    ) -> None:
        """Address-only online orders must not silently get free delivery."""
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "order_source": "ONLINE",
            "delivery_address": "Westlands, Nairobi",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                }
            ],
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.content
        body = response.json()
        details = body.get("details") or body
        assert "delivery_county" in details

    def test_create_order_with_empty_items_allowed(
        self,
        sales_api_client: APIClient,
        customer: Any,
        brand: Brand,
    ) -> None:
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "total_amount": "0.00",
            "order_source": "WALK_IN",
            "brand_id": brand.id,
            "order_items": [],
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.content


class TestOrderIdempotency:
    """Verify that the idempotency key prevents duplicate orders."""

    def test_idempotency_key_prevents_duplicate(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        brand: Brand,
    ) -> None:
        url = "/api/inventory/orders/"
        idempotency_key = "test-idem-key-001"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "total_amount": "55000.00",
            "order_source": "WALK_IN",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                }
            ],
        }

        response1 = sales_api_client.post(
            url, payload, format="json", HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        assert response1.status_code == status.HTTP_201_CREATED, response1.content
        order_id_1 = response1.json().get("order_id")

        response2 = sales_api_client.post(
            url, payload, format="json", HTTP_IDEMPOTENCY_KEY=idempotency_key
        )
        order_id_2 = response2.json().get("order_id")

        assert response2.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        ), response2.content
        assert order_id_2 == order_id_1, "Same idempotency key should return same order"

    def test_different_idempotency_keys_create_different_orders(
        self,
        sales_api_client: APIClient,
        customer: Any,
        product: Product,
        make_unit: Any,
        brand: Brand,
    ) -> None:
        url = "/api/inventory/orders/"
        unit1 = make_unit(product)
        unit2 = make_unit(product)
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "total_amount": "55000.00",
            "order_source": "WALK_IN",
            "brand_id": brand.id,
        }

        response1 = sales_api_client.post(
            url,
            {**payload, "order_items": [{"inventory_unit_id": unit1.id, "quantity": 1}]},
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-a",
        )
        order_id_1 = response1.json().get("order_id")

        response2 = sales_api_client.post(
            url,
            {**payload, "order_items": [{"inventory_unit_id": unit2.id, "quantity": 1}]},
            format="json",
            HTTP_IDEMPOTENCY_KEY="key-b",
        )
        order_id_2 = response2.json().get("order_id")

        assert order_id_1 != order_id_2, "Different keys should create different orders"

    def test_x_idempotency_key_header(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        brand: Brand,
    ) -> None:
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "total_amount": "55000.00",
            "order_source": "WALK_IN",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                }
            ],
        }
        response1 = sales_api_client.post(
            url, payload, format="json", HTTP_X_IDEMPOTENCY_KEY="alt-key-1"
        )
        assert response1.status_code == status.HTTP_201_CREATED, response1.content


class TestOrderStatusTransitions:
    """Verify valid and invalid order status transitions."""

    def test_cancel_pending_order(
        self,
        inventory_manager_api_client: APIClient,
        order: Order,
    ) -> None:
        url = f"/api/inventory/orders/{order.order_id}/"
        response = inventory_manager_api_client.patch(url, {"status": "Canceled"}, format="json")
        assert response.status_code == status.HTTP_200_OK, response.content
        order.refresh_from_db()
        assert order.status == Order.StatusChoices.CANCELED

    def test_mark_order_paid(
        self,
        order_manager_api_client: APIClient,
        order: Order,
    ) -> None:
        url = f"/api/inventory/orders/{order.order_id}/"
        response = order_manager_api_client.patch(url, {"status": "Paid"}, format="json")
        assert response.status_code == status.HTTP_200_OK, response.content
        order.refresh_from_db()
        assert order.status == Order.StatusChoices.PAID

    def test_deliver_paid_order(
        self,
        order_manager_api_client: APIClient,
        paid_order: Order,
    ) -> None:
        url = f"/api/inventory/orders/{paid_order.order_id}/"
        response = order_manager_api_client.patch(url, {"status": "Delivered"}, format="json")
        assert response.status_code == status.HTTP_200_OK, response.content
        paid_order.refresh_from_db()
        assert paid_order.status == Order.StatusChoices.DELIVERED


class TestOrderRetrieval:
    """Verify order retrieval by UUID."""

    def test_retrieve_order_by_uuid(
        self,
        inventory_manager_api_client: APIClient,
        order: Order,
    ) -> None:
        url = f"/api/inventory/orders/{order.order_id}/"
        response = inventory_manager_api_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.content
        data = response.json()
        assert str(order.order_id) in data.get("order_id", "")

    def test_list_orders(
        self,
        sales_api_client: APIClient,
        order: Order,
        paid_order: Order,
    ) -> None:
        url = "/api/inventory/orders/"
        response = sales_api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] >= 2


class TestInventoryUnitStatusAfterOrder:
    """Verify inventory unit status remains unchanged after order creation
    (payment confirmation handles status transition).
    """

    def test_unit_stays_available_after_pending_order(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        brand: Brand,
    ) -> None:
        url = "/api/inventory/orders/"
        payload = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "total_amount": str(available_unit.selling_price),
            "order_source": "WALK_IN",
            "brand_id": brand.id,
            "order_items": [
                {
                    "inventory_unit_id": available_unit.id,
                    "quantity": 1,
                }
            ],
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.content

        available_unit.refresh_from_db()
        assert available_unit.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE
