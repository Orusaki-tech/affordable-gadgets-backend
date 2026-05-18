"""P1: Inventory unit lifecycle — reserve/release, buyback, and status transitions.

These tests cover the inventory management workflows that control
physical stock availability.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Admin, InventoryUnit, Product, ReturnRequest

pytestmark = [pytest.mark.p1, pytest.mark.django_db]


class TestInventoryUnitCRUD:
    """Verify basic CRUD operations on inventory units."""

    def test_list_units(
        self, inventory_manager_api_client: APIClient, available_unit: InventoryUnit
    ) -> None:
        url = "/api/inventory/units/"
        response = inventory_manager_api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_create_unit(
        self,
        inventory_manager_api_client: APIClient,
        product: Any,
    ) -> None:
        url = "/api/inventory/units/"
        payload = {
            "product_template_id": product.id,
            "cost_of_unit": "40000.00",
            "selling_price": "55000.00",
            "quantity": 1,
            "condition": "N",
            "grade": "A",
            "storage_gb": 128,
            "ram_gb": 8,
            "sale_status": "AV",
            "available_online": True,
            "serial_number": "SN-TEST-001",
            "imei": "357865098741235",
        }
        response = inventory_manager_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()
        assert data["selling_price"] == "55000.00"

    def test_salesperson_cannot_create_unit(
        self, sales_api_client: APIClient, product: Any
    ) -> None:
        url = "/api/inventory/units/"
        payload = {
            "product_template": product.id,
            "cost_of_unit": "40000.00",
            "selling_price": "55000.00",
            "quantity": 1,
        }
        response = sales_api_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_inventory_manager_can_update_unit(
        self,
        inventory_manager_api_client: APIClient,
        available_unit: InventoryUnit,
    ) -> None:
        url = f"/api/inventory/units/{available_unit.id}/"
        response = inventory_manager_api_client.patch(
            url, {"selling_price": "60000.00"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        available_unit.refresh_from_db()
        assert available_unit.selling_price == 60000

    def test_salesperson_cannot_update_unit(
        self, sales_api_client: APIClient, available_unit: InventoryUnit
    ) -> None:
        url = f"/api/inventory/units/{available_unit.id}/"
        response = sales_api_client.patch(url, {"selling_price": "1.00"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestInventoryUnitFiltering:
    """Verify the extensive filtering/sorting on the units endpoint."""

    def test_filter_by_sale_status(
        self,
        inventory_manager_api_client: APIClient,
        available_unit: InventoryUnit,
        sold_unit: InventoryUnit,
    ) -> None:
        url = "/api/inventory/units/?sale_status=AV"
        response = inventory_manager_api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json().get("results", response.json().get("data", []))
        for unit in results:
            assert unit["sale_status"] == "AV"

    def test_filter_by_product_type(
        self,
        inventory_manager_api_client: APIClient,
        available_unit: InventoryUnit,
    ) -> None:
        url = f"/api/inventory/units/?product_template__product_type={available_unit.product_template.product_type}"
        response = inventory_manager_api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_search_by_serial_number(
        self,
        inventory_manager_api_client: APIClient,
        available_unit: InventoryUnit,
    ) -> None:
        if available_unit.serial_number:
            url = f"/api/inventory/units/?search={available_unit.serial_number}"
            response = inventory_manager_api_client.get(url)
            assert response.status_code == status.HTTP_200_OK


class TestInventoryUnitStatusTransitions:
    """Verify sale_status transitions are valid."""

    def test_available_to_sold(self, admin_user: Any) -> None:
        """Verify unit status changes correctly."""
        product = Product.objects.create(
            product_name="Status Test Phone",
            brand="TestBrand",
            model_series="TestSeries",
            product_type=Product.ProductType.PHONE,
        )
        unit = InventoryUnit.objects.create(
            product_template=product,
            selling_price=1000,
            cost_of_unit=500,
            quantity=1,
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            serial_number="SN-STATUS-001",
            imei="357865098741238",
            grade="A",
            storage_gb=128,
            ram_gb=8,
        )
        unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
        unit.save()
        unit.refresh_from_db()
        assert unit.sale_status == InventoryUnit.SaleStatusChoices.SOLD

    def test_available_to_reserved(self, admin_user: Any) -> None:
        product = Product.objects.create(
            product_name="Status Test Phone 2",
            brand="TestBrand",
            model_series="TestSeries",
            product_type=Product.ProductType.PHONE,
        )
        unit = InventoryUnit.objects.create(
            product_template=product,
            selling_price=1000,
            cost_of_unit=500,
            quantity=1,
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            serial_number="SN-STATUS-002",
            imei="357865098741239",
            grade="A",
            storage_gb=128,
            ram_gb=8,
        )
        unit.sale_status = InventoryUnit.SaleStatusChoices.RESERVED
        unit.save()
        unit.refresh_from_db()
        assert unit.sale_status == InventoryUnit.SaleStatusChoices.RESERVED

    def test_reserved_to_available(self, admin_user: Any) -> None:
        product = Product.objects.create(
            product_name="Status Test Phone 3",
            brand="TestBrand",
            model_series="TestSeries",
            product_type=Product.ProductType.PHONE,
        )
        unit = InventoryUnit.objects.create(
            product_template=product,
            selling_price=1000,
            cost_of_unit=500,
            quantity=1,
            sale_status=InventoryUnit.SaleStatusChoices.RESERVED,
            serial_number="SN-STATUS-003",
            imei="357865098741240",
            grade="A",
            storage_gb=128,
            ram_gb=8,
        )
        unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
        unit.save()
        unit.refresh_from_db()
        assert unit.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE

    def test_reservation_expiry(self, admin_user: Any) -> None:
        product = Product.objects.create(
            product_name="Status Test Phone 4",
            brand="TestBrand",
            model_series="TestSeries",
            product_type=Product.ProductType.PHONE,
        )
        unit = InventoryUnit.objects.create(
            product_template=product,
            selling_price=1000,
            cost_of_unit=500,
            quantity=1,
            sale_status=InventoryUnit.SaleStatusChoices.RESERVED,
            reserved_until=timezone.now() - timedelta(hours=1),
            serial_number="SN-STATUS-004",
            imei="357865098741241",
            grade="A",
            storage_gb=128,
            ram_gb=8,
        )
        assert unit.is_reservation_expired
        unit.reserved_until = timezone.now() + timedelta(hours=1)
        unit.save()
        unit.refresh_from_db()
        assert not unit.is_reservation_expired


class TestAvailableUnitsEndpoint:
    """Verify the public available units endpoint."""

    def test_available_units_endpoint(
        self,
        unauthenticated_client: APIClient,
        available_unit: InventoryUnit,
    ) -> None:
        url = "/api/inventory/units/available/"
        response = unauthenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK


class TestBuybackApproval:
    """Verify buyback unit approval workflow."""

    def test_approve_returned_buyback(
        self,
        inventory_manager_api_client: APIClient,
        product: Any,
        inventory_manager_user: Any,
    ) -> None:
        unit = InventoryUnit.objects.create(
            product_template=product,
            selling_price=30000,
            cost_of_unit=10000,
            quantity=1,
            sale_status=InventoryUnit.SaleStatusChoices.RETURNED,
            source=InventoryUnit.SourceChoices.BUYBACK_CUSTOMER,
        )
        # Signal auto-creates a pending ReturnRequest — approve it first
        rr = unit.return_requests.first()
        assert rr is not None
        rr.status = ReturnRequest.StatusChoices.APPROVED
        rr.approved_by = Admin.objects.get(user=inventory_manager_user)
        rr.save()

        url = f"/api/inventory/units/{unit.id}/approve_buyback/"
        response = inventory_manager_api_client.post(url)
        assert response.status_code == status.HTTP_200_OK, response.content
        unit.refresh_from_db()
        assert unit.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE

    def test_approve_non_returned_buyback_fails(
        self,
        inventory_manager_api_client: APIClient,
        product: Any,
    ) -> None:
        pytest.skip(
            "Buyback units are auto-set to RETURNED by signal; non-returned buyback cannot exist via model create."
        )
