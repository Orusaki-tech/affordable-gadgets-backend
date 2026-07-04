"""Tests for user activity tracking and session backfill."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from inventory.models import Cart, CartItem, Customer, ObservabilityEvent
from inventory.services.analytics_service import (
    backfill_session_events_to_user,
    link_cart_to_authenticated_user,
    link_session_carts_to_customer,
)

User = get_user_model()
TEST_IP = "127.0.0.1"


@pytest.mark.django_db
def test_backfill_session_events_requires_matching_ip():
    user = User.objects.create_user(username="shopper", email="shopper@test.com", password="pass")
    event = ObservabilityEvent.objects.create(
        session_key="sess-abc12",
        event_type="product_view",
        brand_code="AFFORDABLE_GADGETS",
        ip_address="10.0.0.1",
    )
    event.refresh_from_db()
    assert str(event.ip_address) == "10.0.0.1"

    assert backfill_session_events_to_user(user, "sess-abc12", TEST_IP) == 0
    assert ObservabilityEvent.objects.filter(user=user).count() == 0

    assert backfill_session_events_to_user(user, "sess-abc12", "10.0.0.1") == 1


@pytest.mark.django_db
def test_backfill_session_events_claims_null_ip_when_ip_verified_exists():
    user = User.objects.create_user(username="shopper2", email="shopper2@test.com", password="pass")
    ObservabilityEvent.objects.create(
        session_key="sess-claim1",
        event_type="product_view",
        brand_code="AFFORDABLE_GADGETS",
        ip_address=TEST_IP,
    )
    ObservabilityEvent.objects.create(
        session_key="sess-claim1",
        event_type="cart_add",
        brand_code="AFFORDABLE_GADGETS",
        ip_address=None,
    )

    assert backfill_session_events_to_user(user, "sess-claim1", TEST_IP) == 2


@pytest.mark.django_db
def test_backfill_rejects_legacy_session_when_foreign_ip_present():
    user = User.objects.create_user(username="shopper3", email="shopper3@test.com", password="pass")
    ObservabilityEvent.objects.create(
        session_key="sess-legacy1",
        event_type="page_view",
        brand_code="AFFORDABLE_GADGETS",
        ip_address=None,
    )
    ObservabilityEvent.objects.create(
        session_key="sess-legacy1",
        event_type="product_view",
        brand_code="AFFORDABLE_GADGETS",
        ip_address="10.0.0.99",
    )

    assert backfill_session_events_to_user(user, "sess-legacy1", TEST_IP) == 0


@pytest.mark.django_db
def test_record_event_accepts_whatsapp_click(brand, product):
    client = APIClient()
    response = client.post(
        "/api/v1/public/events/",
        {
            "event_type": "whatsapp_click",
            "product_id": product.id,
            "session_key": "sess-wa-01",
        },
        format="json",
        HTTP_X_BRAND_CODE=brand.code,
    )

    assert response.status_code == 201
    assert ObservabilityEvent.objects.filter(
        event_type="whatsapp_click", product_id=product.id
    ).exists()


@pytest.mark.django_db
def test_legacy_record_event_url_delegates_to_record_event_view(brand, product):
    client = APIClient()
    response = client.post(
        "/api/inventory/observability/record-event/",
        {
            "event_type": "whatsapp_click",
            "product_id": product.id,
            "session_key": "sess-legacy1",
        },
        format="json",
        HTTP_X_BRAND_CODE=brand.code,
    )

    assert response.status_code == 201
    assert ObservabilityEvent.objects.filter(
        event_type="whatsapp_click", product_id=product.id
    ).exists()


@pytest.mark.django_db
def test_cart_create_links_authenticated_customer(brand):
    user = User.objects.create_user(username="cartuser", email="cart@test.com", password="pass")
    Customer.objects.create(user=user, email=user.email, email_verified=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}", HTTP_X_BRAND_CODE=brand.code)

    response = client.post(
        "/api/v1/public/cart/",
        {"session_key": "sess-cart1"},
        format="json",
    )

    assert response.status_code == 200
    cart = Cart.objects.get(id=response.data["id"])
    assert cart.customer_id == user.customer.id


@pytest.mark.django_db
def test_login_backfills_session_events(brand):
    user = User.objects.create_user(username="loginuser", email="login@test.com", password="pass")
    Customer.objects.create(user=user, email=user.email, email_verified=True)
    ObservabilityEvent.objects.create(
        session_key="sess-login1",
        event_type="page_view",
        brand_code=brand.code,
        metadata={"path": "/"},
        ip_address=TEST_IP,
    )

    client = APIClient()
    response = client.post(
        "/api/inventory/login/",
        {
            "username_or_email": "login@test.com",
            "password": "pass",
            "session_key": "sess-login1",
        },
        format="json",
        HTTP_X_BRAND_CODE=brand.code,
        REMOTE_ADDR=TEST_IP,
    )

    assert response.status_code == 200
    assert ObservabilityEvent.objects.filter(user=user, event_type="page_view").exists()


@pytest.mark.django_db
def test_link_session_carts_sets_contact_fields(brand):
    user = User.objects.create_user(
        username="linker",
        email="link@test.com",
        password="pass",
    )
    customer = Customer.objects.create(
        user=user,
        email=user.email,
        phone="+254700000001",
        email_verified=True,
    )
    ObservabilityEvent.objects.create(
        session_key="sess-link1",
        event_type="page_view",
        brand_code=brand.code,
        ip_address=TEST_IP,
    )
    cart = Cart.objects.create(session_key="sess-link1", brand=brand)

    linked = link_session_carts_to_customer(user, "sess-link1", brand.code, TEST_IP)
    cart.refresh_from_db()

    assert linked == 1
    assert cart.customer_id == customer.id
    assert cart.customer_email == user.email
    assert cart.customer_phone == customer.phone


@pytest.mark.django_db
def test_link_cart_to_authenticated_user_sets_customer(brand):
    user = User.objects.create_user(username="linker2", email="link2@test.com", password="pass")
    customer = Customer.objects.create(user=user, email=user.email, email_verified=True)
    cart = Cart.objects.create(session_key="sess-link2", brand=brand)
    link_cart_to_authenticated_user(cart, user)
    cart.refresh_from_db()
    assert cart.customer_id == customer.id


@pytest.mark.django_db
def test_registered_users_carts_endpoint(brand, available_unit):
    admin = User.objects.create_user(username="admincart", email="admin@test.com", password="pass")
    admin.is_staff = True
    admin.save()
    token, _ = Token.objects.get_or_create(user=admin)

    shopper = User.objects.create_user(username="shopper", email="shopper@test.com", password="pass")
    customer = Customer.objects.create(
        user=shopper,
        email=shopper.email,
        phone="+254711111111",
        email_verified=True,
    )
    cart_with_items = Cart.objects.create(session_key="sess-table1", brand=brand, customer=customer)
    CartItem.objects.create(cart=cart_with_items, inventory_unit=available_unit, quantity=1)
    Cart.objects.create(session_key="sess-empty-linked", brand=brand, customer=customer)
    Cart.objects.create(session_key="sess-anon", brand=brand)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    response = client.get("/api/inventory/analytics/registered-users-carts/")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_active_carts"] == 1
    assert data["summary"]["anonymous_active_carts"] == 0
    assert data["summary"]["user_linked_active_carts"] == 1
    assert data["summary"]["users_with_active_carts"] == 1
    assert len(data["users"]) == 1
    shopper_row = data["users"][0]
    assert shopper_row["email"] == "shopper@test.com"
    assert shopper_row["active_cart_count"] == 1
    assert shopper_row["cart_item_count"] == 1


@pytest.mark.django_db
def test_registered_users_activity_includes_active_cart_without_events(brand, available_unit):
    admin = User.objects.create_user(username="adminact", email="adminact@test.com", password="pass")
    admin.is_staff = True
    admin.save()
    admin_token, _ = Token.objects.get_or_create(user=admin)

    shopper = User.objects.create_user(username="cartshop", email="cartshop@test.com", password="pass")
    customer = Customer.objects.create(
        user=shopper,
        email=shopper.email,
        phone="+254722222222",
        email_verified=True,
    )
    cart = Cart.objects.create(session_key="sess-activity1", brand=brand, customer=customer)
    CartItem.objects.create(cart=cart, inventory_unit=available_unit, quantity=1)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
    response = client.get("/api/inventory/analytics/registered-users/")
    assert response.status_code == 200

    shopper_row = next(
        row for row in response.json()["users"] if row["email"] == "cartshop@test.com"
    )
    product_name = available_unit.product_template.product_name
    assert product_name in shopper_row["products_added_to_cart"]
    assert ObservabilityEvent.objects.filter(event_type="cart_add").count() == 0


@pytest.mark.django_db
def test_cart_add_item_records_observability_event(brand, available_unit):
    user = User.objects.create_user(username="buyer2", email="buyer2@test.com", password="pass")
    Customer.objects.create(
        user=user,
        email=user.email,
        phone="+254733333333",
        email_verified=True,
    )
    token, _ = Token.objects.get_or_create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}", HTTP_X_BRAND_CODE=brand.code)
    cart_resp = client.post("/api/v1/public/cart/", {}, format="json")
    assert cart_resp.status_code == 200

    add_resp = client.post(
        f"/api/v1/public/cart/{cart_resp.data['id']}/items/",
        {"inventory_unit_id": available_unit.id, "quantity": 1},
        format="json",
    )
    assert add_resp.status_code == 201
    event = ObservabilityEvent.objects.get(event_type="cart_add", user=user)
    assert event.product_id == available_unit.product_template_id


@pytest.mark.django_db
@patch("inventory.services.whatsapp_lead_service._send_shop_lead_email", return_value=True)
def test_cart_add_item_triggers_notification_email(mock_send, brand, available_unit):
    user = User.objects.create_user(username="buyer3", email="buyer3@test.com", password="pass")
    Customer.objects.create(
        user=user,
        email=user.email,
        phone="254788877766",
        email_verified=True,
    )
    token, _ = Token.objects.get_or_create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}", HTTP_X_BRAND_CODE=brand.code)
    cart_resp = client.post("/api/v1/public/cart/", {}, format="json")
    cart_id = cart_resp.data["id"]
    client.patch(
        f"/api/v1/public/cart/{cart_id}/",
        {"customer_phone": "254788877766"},
        format="json",
    )
    add_resp = client.post(
        f"/api/v1/public/cart/{cart_id}/items/",
        {"inventory_unit_id": available_unit.id, "quantity": 1},
        format="json",
    )
    assert add_resp.status_code == 201
    mock_send.assert_called_once()
