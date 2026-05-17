"""P0: Role-Based Access Control permission matrix.

Tests every admin role against every major ViewSet endpoint to ensure
the permission classes work correctly. Catches regressions in the
20+ custom permission classes in permissions.py.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth.models import AbstractUser
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Admin, Brand, InventoryUnit, Order, Product, UnitAcquisitionSource

pytestmark = [pytest.mark.p0, pytest.mark.django_db]


# ---------------------------------------------------------------------------
# Permission matrix: each row is (role_client_fixture, endpoint, method, expected_status)
# ---------------------------------------------------------------------------

# Endpoint URL builder helpers
PRODUCTS = "/api/inventory/products/"
UNITS = "/api/inventory/units/"
ORDERS = "/api/inventory/orders/"
REVIEWS = "/api/inventory/reviews/"
BRANDS = "/api/inventory/brands/"
PROMOTIONS = "/api/inventory/promotions/"
BUNDLES = "/api/inventory/bundles/"
RESERVATIONS = "/api/inventory/reservation-requests/"
RETURNS = "/api/inventory/return-requests/"
TRANSFERS = "/api/inventory/unit-transfers/"
ADMINS_EP = "/api/inventory/admins/"
LEADS = "/api/inventory/leads/"
DELIVERY_RATES = "/api/inventory/delivery-rates/"
FINANCING_OFFERS = "/api/inventory/financing-offers/"
NOTIFICATIONS = "/api/inventory/notifications/"
COLORS = "/api/inventory/colors/"
TAGS = "/api/inventory/tags/"
SOURCES = "/api/inventory/sources/"
ACCESSORIES = "/api/inventory/accessories-link/"
FINANCING_PROVIDERS = "/api/inventory/financing-providers/"
STOCK_ALERTS = "/api/inventory/stock-alerts/"

# Permission legend:
#   Y = full access (CRUD), R = read-only, N = no access (403/401)
#   SU = Superuser, IM = Inventory Manager, SP = Salesperson
#   CC = Content Creator, OM = Order Manager, MM = Marketing Manager

RoleClient = str  # fixture name for the authenticated API client


def _expected_read_only_status(is_list: bool) -> int:
    return status.HTTP_200_OK if is_list else status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    ("client_fixture", "endpoint", "method", "expected"),
    [
        # ---- Products ----
        # IsSalespersonOrInventoryManagerOrMarketingManagerReadOnly
        ("sales_api_client", PRODUCTS, "GET", status.HTTP_200_OK),
        ("sales_api_client", PRODUCTS, "POST", status.HTTP_403_FORBIDDEN),
        ("inventory_manager_api_client", PRODUCTS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", PRODUCTS, "POST", status.HTTP_201_CREATED),
        ("content_creator_api_client", PRODUCTS, "GET", status.HTTP_200_OK),
        ("content_creator_api_client", PRODUCTS, "POST", status.HTTP_403_FORBIDDEN),
        ("marketing_manager_api_client", PRODUCTS, "GET", status.HTTP_200_OK),
        ("marketing_manager_api_client", PRODUCTS, "POST", status.HTTP_403_FORBIDDEN),
        ("order_manager_api_client", PRODUCTS, "GET", status.HTTP_403_FORBIDDEN),
        ("super_api_client", PRODUCTS, "GET", status.HTTP_200_OK),
        ("super_api_client", PRODUCTS, "POST", status.HTTP_201_CREATED),
        ("unauthenticated_client", PRODUCTS, "GET", status.HTTP_401_UNAUTHORIZED),
        # ---- Inventory Units ----
        # IsInventoryManagerOrSalespersonReadOnly
        ("inventory_manager_api_client", UNITS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", UNITS, "POST", status.HTTP_201_CREATED),
        ("sales_api_client", UNITS, "GET", status.HTTP_200_OK),
        ("sales_api_client", UNITS, "POST", status.HTTP_403_FORBIDDEN),
        ("content_creator_api_client", UNITS, "GET", status.HTTP_403_FORBIDDEN),
        # ---- Orders (create via guest/unauthenticated; list via authenticated roles) ----
        ("unauthenticated_client", ORDERS, "POST", status.HTTP_201_CREATED),
        ("order_manager_api_client", ORDERS, "GET", status.HTTP_200_OK),
        ("sales_api_client", ORDERS, "GET", status.HTTP_200_OK),
        ("sales_api_client", ORDERS, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", ORDERS, "GET", status.HTTP_200_OK),
        ("content_creator_api_client", ORDERS, "GET", status.HTTP_200_OK),
        # ---- Brands ----
        # IsAdminOrReadOnly
        ("inventory_manager_api_client", BRANDS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", BRANDS, "POST", status.HTTP_201_CREATED),
        ("sales_api_client", BRANDS, "GET", status.HTTP_200_OK),
        ("sales_api_client", BRANDS, "POST", status.HTTP_403_FORBIDDEN),
        ("unauthenticated_client", BRANDS, "GET", status.HTTP_200_OK),
        # ---- Promotions ----
        ("marketing_manager_api_client", PROMOTIONS, "GET", status.HTTP_200_OK),
        ("marketing_manager_api_client", PROMOTIONS, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", PROMOTIONS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", PROMOTIONS, "POST", status.HTTP_403_FORBIDDEN),
        ("sales_api_client", PROMOTIONS, "GET", status.HTTP_403_FORBIDDEN),
        # ---- Bundles ----
        # IsBundleManagerOrReadOnly
        ("marketing_manager_api_client", BUNDLES, "GET", status.HTTP_200_OK),
        ("marketing_manager_api_client", BUNDLES, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", BUNDLES, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", BUNDLES, "POST", status.HTTP_403_FORBIDDEN),
        ("sales_api_client", BUNDLES, "GET", status.HTTP_200_OK),
        ("sales_api_client", BUNDLES, "POST", status.HTTP_403_FORBIDDEN),
        # ---- Reservation Requests ----
        # CanReserveUnits (SP or IM)
        ("sales_api_client", RESERVATIONS, "GET", status.HTTP_200_OK),
        ("sales_api_client", RESERVATIONS, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", RESERVATIONS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", RESERVATIONS, "POST", status.HTTP_201_CREATED),
        ("content_creator_api_client", RESERVATIONS, "GET", status.HTTP_403_FORBIDDEN),
        # ---- Return Requests ----
        ("sales_api_client", RETURNS, "GET", status.HTTP_200_OK),
        ("sales_api_client", RETURNS, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", RETURNS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", RETURNS, "POST", status.HTTP_201_CREATED),
        # ---- Unit Transfers ----
        ("sales_api_client", TRANSFERS, "GET", status.HTTP_200_OK),
        ("sales_api_client", TRANSFERS, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", TRANSFERS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", TRANSFERS, "POST", status.HTTP_201_CREATED),
        # ---- Admins (superuser only) ----
        ("super_api_client", ADMINS_EP, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", ADMINS_EP, "GET", status.HTTP_403_FORBIDDEN),
        ("sales_api_client", ADMINS_EP, "GET", status.HTTP_403_FORBIDDEN),
        # ---- Leads ----
        ("sales_api_client", LEADS, "GET", status.HTTP_200_OK),
        ("sales_api_client", LEADS, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", LEADS, "GET", status.HTTP_200_OK),
        ("content_creator_api_client", LEADS, "GET", status.HTTP_403_FORBIDDEN),
        # ---- Lookup tables (read-only for all, write for IM) ----
        ("inventory_manager_api_client", COLORS, "POST", status.HTTP_201_CREATED),
        ("sales_api_client", COLORS, "POST", status.HTTP_403_FORBIDDEN),
        ("unauthenticated_client", COLORS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", TAGS, "POST", status.HTTP_201_CREATED),
        ("sales_api_client", TAGS, "POST", status.HTTP_403_FORBIDDEN),
        # ---- Acquisition Sources ----
        ("inventory_manager_api_client", SOURCES, "GET", status.HTTP_200_OK),
        ("sales_api_client", SOURCES, "GET", status.HTTP_200_OK),
        # ---- Financing ----
        ("inventory_manager_api_client", FINANCING_PROVIDERS, "GET", status.HTTP_200_OK),
        ("inventory_manager_api_client", FINANCING_OFFERS, "GET", status.HTTP_200_OK),
        # ---- Notifications ----
        ("inventory_manager_api_client", NOTIFICATIONS, "GET", status.HTTP_200_OK),
        ("sales_api_client", NOTIFICATIONS, "GET", status.HTTP_200_OK),
        # ---- Delivery Rates ----
        ("inventory_manager_api_client", DELIVERY_RATES, "GET", status.HTTP_200_OK),
        ("order_manager_api_client", DELIVERY_RATES, "GET", status.HTTP_200_OK),
        ("sales_api_client", DELIVERY_RATES, "GET", status.HTTP_200_OK),
    ],
)
def test_rbac_permission_matrix(
    request: pytest.FixtureRequest,
    client_fixture: str,
    endpoint: str,
    method: str,
    expected: int,
    build_admin: Any,
    sales_role: Any,
    inventory_manager_role: Any,
    brand: Any,
) -> None:
    """Verify that each role gets the expected HTTP response for each endpoint."""
    client: APIClient = request.getfixturevalue(client_fixture)

    if method == "GET":
        data = {}
    elif method == "POST":
        data = _payload_for_endpoint(endpoint, brand)

    user_fixture = client_fixture.replace("_api_client", "_user")
    try:
        user: AbstractUser = request.getfixturevalue(user_fixture)
    except pytest.FixtureLookupError:
        user = None

    # Set up preconditions for endpoints that need existing DB objects
    if endpoint == RESERVATIONS and method == "POST":
        unit = _create_available_unit()
        data["inventory_unit_ids"] = [unit.id]
    elif endpoint == RETURNS and method == "POST" and user is not None:
        admin = Admin.objects.get(user=user)
        unit = _create_reserved_unit(admin)
        data["unit_ids"] = [unit.id]
    elif endpoint == TRANSFERS and method == "POST" and user is not None:
        admin = Admin.objects.get(user=user)
        unit = _create_reserved_unit(admin)
        target_user, target_admin = build_admin("target_sales", [sales_role])
        data["inventory_unit"] = unit.id
        data["inventory_unit_id"] = unit.id
        data["to_salesperson"] = target_admin.id
        data["to_salesperson_id"] = target_admin.id

    response = client.generic(method, endpoint, json.dumps(data), content_type="application/json")

    msg = (
        f"{client_fixture} → {method} {endpoint}: "
        f"expected {expected}, got {response.status_code}: {response.content[:200]}"
    )
    assert response.status_code == expected, msg


def _unit_payload() -> dict:
    """Create a product + acquisition source and return a valid unit payload."""
    source = UnitAcquisitionSource.objects.get_or_create(
        source_type=UnitAcquisitionSource.SourceType.SUPPLIER,
        name="RBAC Test Supplier",
        defaults={"phone_number": "+254700000000"},
    )[0]
    product, _ = Product.objects.get_or_create(
        product_name="RBAC Unit Test Product",
        defaults={
            "brand": "TestBrand",
            "model_series": "RBAC",
            "product_type": Product.ProductType.PHONE,
        },
    )
    return {
        "product_template_id": product.id,
        "cost_of_unit": "1000.00",
        "selling_price": "2000.00",
        "quantity": 1,
        "serial_number": "SN-RBAC-UNIT",
        "imei": "357865098741250",
        "grade": "A",
        "storage_gb": 128,
        "ram_gb": 8,
        "source": InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        "acquisition_source_details_id": source.id,
    }


_unit_counter = 0


def _create_available_unit() -> InventoryUnit:
    """Create an AVAILABLE inventory unit and return it."""
    global _unit_counter
    _unit_counter += 1
    source, _ = UnitAcquisitionSource.objects.get_or_create(
        source_type=UnitAcquisitionSource.SourceType.SUPPLIER,
        name="RBAC Test Supplier",
        defaults={"phone_number": "+254700000000"},
    )
    product, _ = Product.objects.get_or_create(
        product_name="RBAC Available Unit Product",
        defaults={
            "brand": "TestBrand",
            "model_series": "RBAC",
            "product_type": Product.ProductType.PHONE,
        },
    )
    return InventoryUnit.objects.create(
        product_template=product,
        selling_price=Decimal("2000.00"),
        cost_of_unit=Decimal("1000.00"),
        quantity=1,
        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
        available_online=True,
        condition=InventoryUnit.ConditionChoices.NEW,
        grade="A",
        source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        acquisition_source_details=source,
        storage_gb=128,
        ram_gb=8,
        serial_number=f"SN-AVAIL-{_unit_counter:04d}",
        imei=f"35{_unit_counter + 1000000000000:013d}",
    )


def _create_reserved_unit(admin: Admin) -> InventoryUnit:
    """Create an InventoryUnit and then set it to RESERVED status (signal resets to AVAILABLE)."""
    unit = _create_available_unit()
    unit.sale_status = InventoryUnit.SaleStatusChoices.RESERVED
    unit.reserved_by = admin
    unit.available_online = False
    unit.save()
    return unit


def _payload_for_endpoint(endpoint: str, brand: Any) -> dict:
    """Generate a minimally valid POST payload for each endpoint."""
    if endpoint == PRODUCTS:
        return {
            "product_name": "RBAC Test Product",
            "brand": brand.name,
            "model_series": "RBAC",
            "product_type": "PH",
        }
    if endpoint == UNITS:
        return _unit_payload()
    if endpoint == ORDERS:
        return {
            "customer_name": "Test Customer",
            "customer_phone": "+254700000000",
            "delivery_address": "123 Test Street, Nairobi",
            "total_amount": "1000.00",
            "order_source": "ONLINE",
            "order_items": [],
        }
    if endpoint == BRANDS:
        return {"code": "TEST_BRAND", "name": "Test Brand", "is_active": True}
    if endpoint == PROMOTIONS:
        return {
            "title": "Test Promotion",
            "description": "Test",
            "promotion_code": "TEST10",
            "brand": brand.id,
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2026-12-31T23:59:59Z",
            "product_types": "PH",
        }
    if endpoint == BUNDLES:
        return {
            "title": "Test Bundle",
            "brand": brand.id,
            "main_product": Product.objects.get_or_create(
                brand="BundleBrand",
                model_series="BundleSeries",
                product_type=Product.ProductType.PHONE,
                defaults={"product_name": "RBAC Bundle Product"},
            )[0].id,
            "pricing_mode": "FX",
            "bundle_price": "1000.00",
        }
    if endpoint == RESERVATIONS:
        return {"notes": "Test reservation"}
    if endpoint == RETURNS:
        return {"notes": "Test return"}
    if endpoint == TRANSFERS:
        return {"notes": "Test transfer"}
    if endpoint == ADMINS_EP:
        return {"admin_code": "ADM-RBAC-001", "user_id": 1}
    if endpoint == LEADS:
        return {"customer_name": "Test Lead", "customer_phone": "+254700000000", "brand": brand.id}
    if endpoint == COLORS:
        return {"name": "Test Color", "hex_code": "#000000"}
    if endpoint == TAGS:
        return {"name": "Test Tag", "slug": "test-tag"}
    if endpoint == FINANCING_PROVIDERS:
        return {"name": "Test Provider"}
    if endpoint == FINANCING_OFFERS:
        return {"product_id": 1, "financing_provider_id": 1}
    if endpoint == SOURCES:
        return {"name": "Test Source", "source_type": "SU"}
    if endpoint == DELIVERY_RATES:
        return {"county": "Nairobi", "price": "500.00"}
    if endpoint == NOTIFICATIONS:
        return {}
    if endpoint == ACCESSORIES:
        return {}
    if endpoint == STOCK_ALERTS:
        return {}
    return {}


# ---------------------------------------------------------------------------
# Role-based action tests for endpoints that need existing objects
# ---------------------------------------------------------------------------


class TestProductPermissionsByRole:
    """Verify PATCH and DELETE on product detail endpoint per role."""

    def test_inventory_manager_can_update_product(
        self, inventory_manager_api_client: APIClient, product: Product
    ) -> None:
        url = f"/api/inventory/products/{product.id}/"
        response = inventory_manager_api_client.patch(url, {"product_name": "Updated"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.product_name == "Updated"

    def test_salesperson_cannot_update_product(
        self, sales_api_client: APIClient, product: Product
    ) -> None:
        url = f"/api/inventory/products/{product.id}/"
        response = sales_api_client.patch(url, {"product_name": "Hack"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_marketing_manager_cannot_update_product(
        self, marketing_manager_api_client: APIClient, product: Product
    ) -> None:
        url = f"/api/inventory/products/{product.id}/"
        response = marketing_manager_api_client.patch(url, {"product_name": "Hack"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestOrderPermissionsByRole:
    """Verify role-based access to order detail endpoints."""

    def test_order_manager_can_update_order(
        self, order_manager_api_client: APIClient, order: Any
    ) -> None:
        url = f"/api/inventory/orders/{order.order_id}/"
        response = order_manager_api_client.patch(url, {"status": "Paid"}, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_salesperson_cannot_update_order_status(
        self, sales_api_client: APIClient, order: Any
    ) -> None:
        url = f"/api/inventory/orders/{order.order_id}/"
        response = sales_api_client.patch(url, {"status": "Paid"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestProductContentPermissionsByRole:
    """Verify who can update product content (SEO, article, description)."""

    def test_content_creator_can_update_content(
        self, content_creator_api_client: APIClient, product: Product
    ) -> None:
        from django.urls import reverse
        url = reverse("product-update-content", args=[product.id])
        response = content_creator_api_client.patch(
            url, {"product_description": "CC content"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.product_description == "CC content"

    def test_salesperson_cannot_update_content(
        self, sales_api_client: APIClient, product: Product
    ) -> None:
        from django.urls import reverse
        url = reverse("product-update-content", args=[product.id])
        response = sales_api_client.patch(url, {"product_description": "No"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_inventory_manager_can_update_content(
        self, inventory_manager_api_client: APIClient, product: Product
    ) -> None:
        from django.urls import reverse
        url = reverse("product-update-content", args=[product.id])
        response = inventory_manager_api_client.patch(
            url, {"product_description": "IM content"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.product_description == "IM content"


class TestUnauthenticatedAccess:
    """Verify unauthenticated users get 401 on admin endpoints and 200 on public."""

    def test_admin_endpoints_require_auth(
        self, unauthenticated_client: APIClient
    ) -> None:
        endpoints = [PRODUCTS, UNITS, ORDERS, PROMOTIONS]
        for ep in endpoints:
            response = unauthenticated_client.get(ep)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{ep} should 401"

    def test_public_endpoints_allow_anonymous(
        self, unauthenticated_client: APIClient
    ) -> None:
        public_endpoints = [
            "/api/v1/public/products/",
            "/api/v1/public/promotions/",
            "/api/v1/public/bundles/",
        ]
        for ep in public_endpoints:
            response = unauthenticated_client.get(ep)
            assert response.status_code == status.HTTP_200_OK, f"{ep} should allow anonymous"
