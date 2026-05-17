"""Shared test fixtures for all inventory tests.

Usage:
    def test_something(api_client, admin_user, product):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(f"/api/inventory/products/{product.id}/")
        assert response.status_code == 200
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from rest_framework.test import APIClient

from inventory.models import (
    Admin,
    AdminRole,
    Brand,
    Product,
    ProductArticle,
    InventoryUnit,
    UnitAcquisitionSource,
)

@pytest.fixture(autouse=True)
def disable_security_redirects(settings):
    """Disable HTTPS redirect and HSTS during tests to avoid 301 redirects."""
    settings.SECURE_SSL_REDIRECT = False
    settings.SECURE_HSTS_SECONDS = 0
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False

from inventory.models import (
    Admin,
    AdminRole,
    Brand,
    Customer,
    InventoryUnit,
    Order,
    OrderItem,
    Product,
    ProductArticle,
)

UserModel: type[AbstractUser] = get_user_model()


# ---------------------------------------------------------------------------
# Brand fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def brand() -> Brand:
    return Brand.objects.get_or_create(
        code="AFFORDABLE_GADGETS",
        defaults=dict(
            name="Affordable Gadgets",
            ecommerce_domain="affordable-gadgetske.com",
            is_active=True,
        ),
    )[0]


@pytest.fixture
def other_brand() -> Brand:
    return Brand.objects.get_or_create(
        code="SHWARI",
        defaults=dict(
            name="Shwari Phones",
            ecommerce_domain="shwariphones.com",
            is_active=True,
        ),
    )[0]


# ---------------------------------------------------------------------------
# Admin role fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sales_role() -> AdminRole:
    role, _ = AdminRole.objects.get_or_create(
        name=AdminRole.RoleChoices.SALESPERSON,
        defaults={"display_name": "Salesperson", "description": "Can view inventory and create orders"},
    )
    return role


@pytest.fixture
def inventory_manager_role() -> AdminRole:
    role, _ = AdminRole.objects.get_or_create(
        name=AdminRole.RoleChoices.INVENTORY_MANAGER,
        defaults={"display_name": "Inventory Manager", "description": "Manages inventory"},
    )
    return role


@pytest.fixture
def content_creator_role() -> AdminRole:
    role, _ = AdminRole.objects.get_or_create(
        name=AdminRole.RoleChoices.CONTENT_CREATOR,
        defaults={"display_name": "Content Creator", "description": "Creates reviews and content"},
    )
    return role


@pytest.fixture
def order_manager_role() -> AdminRole:
    role, _ = AdminRole.objects.get_or_create(
        name=AdminRole.RoleChoices.ORDER_MANAGER,
        defaults={"display_name": "Order Manager", "description": "Manages orders"},
    )
    return role


@pytest.fixture
def marketing_manager_role() -> AdminRole:
    role, _ = AdminRole.objects.get_or_create(
        name=AdminRole.RoleChoices.MARKETING_MANAGER,
        defaults={"display_name": "Marketing Manager", "description": "Manages promotions and bundles"},
    )
    return role


# ---------------------------------------------------------------------------
# User fixtures (unauthenticated)
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def unauthenticated_client() -> APIClient:
    return APIClient()


# ---------------------------------------------------------------------------
# Admin user fixtures
# ---------------------------------------------------------------------------

_AdminUserFixture = tuple[AbstractUser, Admin]


def _make_admin(username: str, roles: list[AdminRole], brand: Brand | None = None) -> _AdminUserFixture:
    user = UserModel.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="test-pass-123",
        is_staff=True,
    )
    admin = Admin.objects.create(user=user, admin_code=f"ADM-{username.upper()[:4]}-001")
    admin.roles.add(*roles)
    if brand:
        admin.brands.add(brand)
    return user, admin


@pytest.fixture
def sales_user(sales_role: AdminRole, brand: Brand) -> AbstractUser:
    user, _ = _make_admin("salesperson", [sales_role], brand=brand)
    return user


@pytest.fixture
def sales_admin(sales_role: AdminRole) -> Admin:
    _, admin = _make_admin("salesperson2", [sales_role])
    return admin


@pytest.fixture
def inventory_manager_user(inventory_manager_role: AdminRole) -> AbstractUser:
    user, _ = _make_admin("inventory_mgr", [inventory_manager_role])
    return user


@pytest.fixture
def content_creator_user(content_creator_role: AdminRole) -> AbstractUser:
    user, _ = _make_admin("content_creator", [content_creator_role])
    return user


@pytest.fixture
def order_manager_user(order_manager_role: AdminRole) -> AbstractUser:
    user, _ = _make_admin("order_mgr", [order_manager_role])
    return user


@pytest.fixture
def marketing_manager_user(marketing_manager_role: AdminRole) -> AbstractUser:
    user, _ = _make_admin("marketing_mgr", [marketing_manager_role])
    return user


@pytest.fixture
def super_user() -> AbstractUser:
    return UserModel.objects.create_superuser(
        username="superuser",
        email="super@example.com",
        password="test-pass-123",
    )


@pytest.fixture
def admin_user(inventory_manager_role: AdminRole) -> AbstractUser:
    """Convenience alias for an admin with inventory manager role."""
    user, _ = _make_admin("default_admin", [inventory_manager_role])
    return user


# ---------------------------------------------------------------------------
# Customer fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def customer_user() -> AbstractUser:
    return UserModel.objects.create_user(
        username="customer",
        email="customer@example.com",
        password="test-pass-123",
        is_staff=False,
    )


@pytest.fixture
def customer(customer_user: AbstractUser) -> Customer:
    return Customer.objects.create(
        user=customer_user,
        name="Test Customer",
        phone="+254700000000",
        email="customer@example.com",
    )


# ---------------------------------------------------------------------------
# Authenticated API clients
# ---------------------------------------------------------------------------


@pytest.fixture
def authed_api_client(api_client: APIClient, admin_user: AbstractUser) -> APIClient:
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def sales_api_client(api_client: APIClient, sales_user: AbstractUser) -> APIClient:
    api_client.force_authenticate(user=sales_user)
    return api_client


@pytest.fixture
def inventory_manager_api_client(
    api_client: APIClient, inventory_manager_user: AbstractUser
) -> APIClient:
    api_client.force_authenticate(user=inventory_manager_user)
    return api_client


@pytest.fixture
def content_creator_api_client(
    api_client: APIClient, content_creator_user: AbstractUser
) -> APIClient:
    api_client.force_authenticate(user=content_creator_user)
    return api_client


@pytest.fixture
def order_manager_api_client(
    api_client: APIClient, order_manager_user: AbstractUser
) -> APIClient:
    api_client.force_authenticate(user=order_manager_user)
    return api_client


@pytest.fixture
def marketing_manager_api_client(
    api_client: APIClient, marketing_manager_user: AbstractUser
) -> APIClient:
    api_client.force_authenticate(user=marketing_manager_user)
    return api_client


@pytest.fixture
def super_api_client(api_client: APIClient, super_user: AbstractUser) -> APIClient:
    api_client.force_authenticate(user=super_user)
    return api_client


# ---------------------------------------------------------------------------
# Product fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def product(brand: Brand) -> Product:
    return Product.objects.create(
        product_name="Test Phone",
        brand=brand.name,
        model_series="TestSeries",
        product_type=Product.ProductType.PHONE,
        slug="test-phone",
        is_published=True,
        default_selling_price=Decimal("50000.00"),
    )


@pytest.fixture
def accessory_product(brand: Brand) -> Product:
    return Product.objects.create(
        product_name="Test Accessory",
        brand=brand.name,
        model_series="AccSeries",
        product_type=Product.ProductType.ACCESSORY,
        slug="test-accessory",
        is_published=True,
        default_selling_price=Decimal("2500.00"),
    )


@pytest.fixture
def unpublished_product(brand: Brand) -> Product:
    return Product.objects.create(
        product_name="Unpublished Phone",
        brand=brand.name,
        model_series="Hidden",
        product_type=Product.ProductType.PHONE,
        slug="unpublished-phone",
        is_published=False,
    )


@pytest.fixture
def product_with_article(product: Product) -> Product:
    ProductArticle.objects.create(
        product=product,
        headline="Test Buying Guide",
        body="# Guide\n\nContent here.",
        seo_title="Test SEO Title",
        seo_description="Test meta description for this article.",
        is_published=True,
    )
    return product


# ---------------------------------------------------------------------------
# Inventory unit fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def acquisition_source() -> UnitAcquisitionSource:
    return UnitAcquisitionSource.objects.create(
        source_type=UnitAcquisitionSource.SourceType.SUPPLIER,
        name="Test Supplier",
        phone_number="+254700000000",
    )


@pytest.fixture
def available_unit(
    product: Product, acquisition_source: UnitAcquisitionSource
) -> InventoryUnit:
    return InventoryUnit.objects.create(
        product_template=product,
        selling_price=Decimal("55000.00"),
        cost_of_unit=Decimal("40000.00"),
        quantity=1,
        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
        available_online=True,
        condition=InventoryUnit.ConditionChoices.NEW,
        grade="A",
        source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        acquisition_source_details=acquisition_source,
        storage_gb=128,
        ram_gb=8,
        serial_number="SN-AVAILABLE-001",
        imei="357865098741236",
    )


@pytest.fixture
def sold_unit(
    product: Product, acquisition_source: UnitAcquisitionSource
) -> InventoryUnit:
    return InventoryUnit.objects.create(
        product_template=product,
        selling_price=Decimal("55000.00"),
        cost_of_unit=Decimal("40000.00"),
        quantity=1,
        sale_status=InventoryUnit.SaleStatusChoices.SOLD,
        available_online=False,
        condition=InventoryUnit.ConditionChoices.NEW,
        grade="A",
        source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        acquisition_source_details=acquisition_source,
        storage_gb=128,
        ram_gb=8,
        serial_number="SN-SOLD-001",
        imei="357865098741237",
    )


@pytest.fixture
def reserved_unit(product: Product, acquisition_source: UnitAcquisitionSource) -> InventoryUnit:
    return InventoryUnit.objects.create(
        product_template=product,
        selling_price=Decimal("55000.00"),
        cost_of_unit=Decimal("40000.00"),
        quantity=1,
        sale_status=InventoryUnit.SaleStatusChoices.RESERVED,
        available_online=False,
        condition=InventoryUnit.ConditionChoices.NEW,
        grade="A",
        source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        acquisition_source_details=acquisition_source,
        storage_gb=128,
        ram_gb=8,
        serial_number="SN-RESERVED-001",
        imei="357865098741242",
    )


@pytest.fixture
def pending_payment_unit(product: Product, acquisition_source: UnitAcquisitionSource) -> InventoryUnit:
    return InventoryUnit.objects.create(
        product_template=product,
        selling_price=Decimal("55000.00"),
        cost_of_unit=Decimal("40000.00"),
        quantity=1,
        sale_status=InventoryUnit.SaleStatusChoices.PENDING_PAYMENT,
        available_online=False,
        condition=InventoryUnit.ConditionChoices.NEW,
        grade="A",
        source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
        acquisition_source_details=acquisition_source,
        storage_gb=128,
        ram_gb=8,
        serial_number="SN-PENDINGPMT-001",
        imei="357865098741243",
    )


# ---------------------------------------------------------------------------
# Order fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def order(product: Product, customer: Customer, brand: Brand) -> Order:
    return Order.objects.create(
        customer=customer,
        brand=brand,
        total_amount=Decimal("55000.00"),
        status=Order.StatusChoices.PENDING,
        order_source=Order.OrderSourceChoices.ONLINE,
    )


@pytest.fixture
def paid_order(product: Product, customer: Customer, brand: Brand) -> Order:
    return Order.objects.create(
        customer=customer,
        brand=brand,
        total_amount=Decimal("55000.00"),
        status=Order.StatusChoices.PAID,
        order_source=Order.OrderSourceChoices.ONLINE,
    )


@pytest.fixture
def order_with_units(
    order: Order, available_unit: InventoryUnit
) -> Order:
    OrderItem.objects.create(
        order=order,
        inventory_unit=available_unit,
        quantity=1,
        unit_price_at_purchase=available_unit.selling_price,
    )
    return order


# ---------------------------------------------------------------------------
# URL reverse helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def reverse() -> Callable:
    from django.urls import reverse as _reverse
    return _reverse


# ---------------------------------------------------------------------------
# Convenience fixture for building admin users with specific roles
# ---------------------------------------------------------------------------


@pytest.fixture
def build_admin() -> Callable[..., tuple[AbstractUser, Admin]]:
    def _build(
        username: str,
        roles: list[AdminRole],
        is_superuser: bool = False,
        brand: Brand | None = None,
    ) -> tuple[AbstractUser, Admin]:
        extra = {"is_superuser": True} if is_superuser else {}
        user = UserModel.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="test-pass-123",
            is_staff=True,
            **extra,
        )
        admin = Admin.objects.create(user=user, admin_code=f"ADM-{username.upper()[:4]}-001")
        admin.roles.add(*roles)
        if brand:
            admin.brands.add(brand)
        return user, admin

    return _build


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def make_product(brand: Brand) -> Callable[..., Product]:
    counter = [0]

    def _make(overrides: dict[str, Any] | None = None) -> Product:
        counter[0] += 1
        defaults = {
            "product_name": f"Product {counter[0]}",
            "brand": brand.name,
            "model_series": f"Series{counter[0]}",
            "product_type": Product.ProductType.PHONE,
            "slug": f"product-{counter[0]}",
            "is_published": True,
        }
        if overrides:
            defaults.update(overrides)
        return Product.objects.create(**defaults)

    return _make


@pytest.fixture
def make_unit(make_product: Callable[..., Product], acquisition_source: UnitAcquisitionSource) -> Callable[..., InventoryUnit]:
    """Fixture factory that creates a bare InventoryUnit with required fields."""
    counter = [0]

    def _make(product: Product | None = None) -> InventoryUnit:
        counter[0] += 1
        if product is None:
            product = make_product()
        return InventoryUnit.objects.create(
            product_template=product,
            selling_price=Decimal("55000.00"),
            cost_of_unit=Decimal("40000.00"),
            quantity=1,
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True,
            condition=InventoryUnit.ConditionChoices.NEW,
            grade="A",
            source=InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER,
            acquisition_source_details=acquisition_source,
            storage_gb=128,
            ram_gb=8,
            serial_number=f"SN-MAKE-{counter[0]:04d}",
            imei=f"35786509874{counter[0]:04d}",
        )

    return _make
