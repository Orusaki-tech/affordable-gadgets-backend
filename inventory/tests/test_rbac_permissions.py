"""P0: Role-Based Access Control permission matrix.

Tests every admin role against every major ViewSet endpoint to ensure
the permission classes work correctly. Catches regressions in the
20+ custom permission classes in permissions.py.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import AbstractUser
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Order, Product

pytestmark = pytest.mark.p0


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
        # ---- Orders ----
        ("order_manager_api_client", ORDERS, "GET", status.HTTP_200_OK),
        ("order_manager_api_client", ORDERS, "POST", status.HTTP_201_CREATED),
        ("sales_api_client", ORDERS, "GET", status.HTTP_200_OK),
        ("sales_api_client", ORDERS, "POST", status.HTTP_201_CREATED),
        ("inventory_manager_api_client", ORDERS, "GET", status.HTTP_200_OK),
        ("content_creator_api_client", ORDERS, "GET", status.HTTP_403_FORBIDDEN),
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

    response = client.generic(method, endpoint, data, content_type="application/json")

    msg = (
        f"{client_fixture} → {method} {endpoint}: "
        f"expected {expected}, got {response.status_code}: {response.content[:200]}"
    )
    assert response.status_code == expected, msg


def _payload_for_endpoint(endpoint: str, brand: Any) -> dict:
    """Generate a minimally valid POST payload for each endpoint."""
    payloads: dict[str, dict] = {
        PRODUCTS: {
            "product_name": "RBAC Test Product",
            "brand": brand.name,
            "model_series": "RBAC",
            "product_type": "PH",
        },
        UNITS: {
            "product_template_id": 1,
            "cost_of_unit": "1000.00",
            "selling_price": "2000.00",
            "quantity": 1,
        },
        ORDERS: {
            "customer_id": 1,
            "total_amount": "1000.00",
            "order_source": "ONLINE",
        },
        BRANDS: {
            "code": "TEST_BRAND",
            "name": "Test Brand",
            "is_active": True,
        },
        PROMOTIONS: {
            "title": "Test Promotion",
            "description": "Test",
            "promotion_code": "TEST10",
        },
        BUNDLES: {
            "title": "Test Bundle",
            "pricing_mode": "Fixed",
            "bundle_price": "1000.00",
        },
        RESERVATIONS: {"notes": "Test reservation"},
        RETURNS: {"notes": "Test return"},
        TRANSFERS: {"notes": "Test transfer"},
        ADMINS_EP: {
            "admin_code": "ADM-RBAC-001",
            "user_id": 1,
        },
        LEADS: {
            "customer_name": "Test Lead",
            "phone": "+254700000000",
        },
        COLORS: {"name": "Test Color", "hex_code": "#000000"},
        TAGS: {"name": "Test Tag"},
        FINANCING_PROVIDERS: {"name": "Test Provider"},
        FINANCING_OFFERS: {"product_id": 1, "financing_provider_id": 1},
        SOURCES: {"name": "Test Source", "source_type": "SU"},
        DELIVERY_RATES: {"county": "Nairobi", "price": "500.00"},
        NOTIFICATIONS: {},
        ACCESSORIES: {},
        STOCK_ALERTS: {},
    }
    return payloads.get(endpoint, {})


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
        endpoints = [PRODUCTS, UNITS, ORDERS, BRANDS, PROMOTIONS]
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
