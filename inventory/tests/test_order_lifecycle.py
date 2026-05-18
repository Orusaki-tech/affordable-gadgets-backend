"""P0: Order creation, idempotency, stock deduction, and status transitions.

These are the most critical money-moving code paths in the system.
"""

from __future__ import annotations

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
