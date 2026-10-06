"""Idempotency payload match, race replay, and abandoned pending-order release."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Brand, InventoryUnit, Order, Product
from inventory.services.order_idempotency import order_matches_request
from inventory.services.order_release_service import OrderReleaseService

pytestmark = [pytest.mark.p0, pytest.mark.django_db]


class TestOrderIdempotencyPayload:
    def test_same_key_same_payload_returns_existing(
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
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [{"inventory_unit_id": available_unit.id, "quantity": 1}],
        }
        r1 = sales_api_client.post(
            url, payload, format="json", HTTP_IDEMPOTENCY_KEY="payload-key-1"
        )
        assert r1.status_code == status.HTTP_201_CREATED, r1.content
        order_id = r1.json()["order_id"]

        r2 = sales_api_client.post(
            url, payload, format="json", HTTP_IDEMPOTENCY_KEY="payload-key-1"
        )
        assert r2.status_code == status.HTTP_200_OK, r2.content
        assert r2.json()["order_id"] == order_id

    def test_same_key_different_payload_conflicts(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        make_unit: Any,
        product: Product,
        brand: Brand,
    ) -> None:
        url = "/api/inventory/orders/"
        other_unit = make_unit(product)
        payload_a = {
            "customer": customer.id,
            "customer_id": customer.id,
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [{"inventory_unit_id": available_unit.id, "quantity": 1}],
        }
        r1 = sales_api_client.post(
            url, payload_a, format="json", HTTP_IDEMPOTENCY_KEY="payload-key-2"
        )
        assert r1.status_code == status.HTTP_201_CREATED, r1.content

        payload_b = {
            **payload_a,
            "order_items": [{"inventory_unit_id": other_unit.id, "quantity": 1}],
        }
        r2 = sales_api_client.post(
            url, payload_b, format="json", HTTP_IDEMPOTENCY_KEY="payload-key-2"
        )
        assert r2.status_code == status.HTTP_409_CONFLICT, r2.content
        assert "different order payload" in r2.json().get("error", "").lower()

    def test_integrity_error_race_replays_existing(
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
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [{"inventory_unit_id": available_unit.id, "quantity": 1}],
        }
        r1 = sales_api_client.post(
            url, payload, format="json", HTTP_IDEMPOTENCY_KEY="race-key-1"
        )
        assert r1.status_code == status.HTTP_201_CREATED, r1.content
        order_id = r1.json()["order_id"]

        # Simulate parallel create: early lookup misses, insert hits unique constraint,
        # recovery loads the winner and returns 200.
        from rest_framework import mixins

        real_get = Order.objects.get

        def miss_idempotency_get(*args, **kwargs):
            if "idempotency_key" in kwargs:
                raise Order.DoesNotExist("Order matching query does not exist.")
            return real_get(*args, **kwargs)

        def boom(self, request, *args, **kwargs):
            raise IntegrityError(
                'duplicate key value violates unique constraint "idempotency_key"'
            )

        with patch.object(Order.objects, "get", side_effect=miss_idempotency_get):
            with patch.object(mixins.CreateModelMixin, "create", boom):
                r2 = sales_api_client.post(
                    url, payload, format="json", HTTP_IDEMPOTENCY_KEY="race-key-1"
                )

        assert r2.status_code == status.HTTP_200_OK, r2.content
        assert r2.json()["order_id"] == order_id
        assert order_matches_request(Order.objects.get(order_id=order_id), payload)


class TestAbandonedPendingRelease:
    def test_release_restores_unique_unit(
        self, order_with_units: Order, available_unit: InventoryUnit
    ) -> None:
        available_unit.sale_status = InventoryUnit.SaleStatusChoices.PENDING_PAYMENT
        available_unit.save(update_fields=["sale_status"])
        order_with_units.status = Order.StatusChoices.PENDING
        order_with_units.is_items_paid = False
        order_with_units.created_at = timezone.now() - timedelta(hours=3)
        order_with_units.save(update_fields=["status", "is_items_paid", "created_at"])

        assert OrderReleaseService.release_order(order_with_units, reason="test")
        order_with_units.refresh_from_db()
        available_unit.refresh_from_db()
        assert order_with_units.status == Order.StatusChoices.CANCELED
        assert available_unit.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE

    def test_does_not_release_items_paid_partial(
        self, order_with_units: Order, available_unit: InventoryUnit
    ) -> None:
        available_unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
        available_unit.save(update_fields=["sale_status"])
        order_with_units.is_items_paid = True
        order_with_units.is_delivery_paid = False
        order_with_units.status = Order.StatusChoices.PENDING
        order_with_units.created_at = timezone.now() - timedelta(hours=5)
        order_with_units.save(
            update_fields=["is_items_paid", "is_delivery_paid", "status", "created_at"]
        )

        assert not OrderReleaseService.maybe_release_order(order_with_units, older_than_hours=2)
        order_with_units.refresh_from_db()
        assert order_with_units.status == Order.StatusChoices.PENDING
        available_unit.refresh_from_db()
        assert available_unit.sale_status == InventoryUnit.SaleStatusChoices.SOLD

    def test_second_checkout_after_abandon_ttl(
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
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [{"inventory_unit_id": available_unit.id, "quantity": 1}],
        }
        first = sales_api_client.post(url, payload, format="json")
        assert first.status_code == status.HTTP_201_CREATED, first.content
        order = Order.objects.get(order_id=first.json()["order_id"])
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=3)
        )

        second = sales_api_client.post(url, payload, format="json")
        assert second.status_code == status.HTTP_201_CREATED, second.content
        order.refresh_from_db()
        assert order.status == Order.StatusChoices.CANCELED
        assert second.json()["order_id"] != str(order.order_id)

    def test_online_idempotency_matches_cart_rebuilt_lines(
        self,
        sales_api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        make_unit: Any,
        product: Product,
        brand: Brand,
    ) -> None:
        """Retry with swapped client SKU still matches when open cart owns the lines."""
        from inventory.models import Cart, CartItem

        decoy = make_unit(product)
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
            "customer_phone": customer.phone,
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "brand_id": brand.id,
            "order_items": [{"inventory_unit_id": decoy.id, "quantity": 1}],
        }
        r1 = sales_api_client.post(
            url, payload, format="json", HTTP_IDEMPOTENCY_KEY="cart-rebuild-key"
        )
        assert r1.status_code == status.HTTP_201_CREATED, r1.content
        assert r1.json()["order_items"][0]["inventory_unit"] == available_unit.id

        r2 = sales_api_client.post(
            url, payload, format="json", HTTP_IDEMPOTENCY_KEY="cart-rebuild-key"
        )
        assert r2.status_code == status.HTTP_200_OK, r2.content
        assert r2.json()["order_id"] == r1.json()["order_id"]

    def test_guest_online_order_persists_request_brand(
        self,
        api_client: APIClient,
        customer: Any,
        available_unit: InventoryUnit,
        brand: Brand,
    ) -> None:
        # Guest path: no staff auth, brand only via X-Brand-Code middleware.
        url = "/api/inventory/orders/"
        payload = {
            "customer_name": "Guest Buyer",
            "customer_phone": "+254711111111",
            "delivery_address": "Nairobi CBD",
            "order_source": "ONLINE",
            "fulfillment_method": "PICKUP",
            "order_items": [{"inventory_unit_id": available_unit.id, "quantity": 1}],
        }
        response = api_client.post(
            url, payload, format="json", HTTP_X_BRAND_CODE=brand.code
        )
        assert response.status_code == status.HTTP_201_CREATED, response.content
        order = Order.objects.get(order_id=response.json()["order_id"])
        assert order.brand_id == brand.id
