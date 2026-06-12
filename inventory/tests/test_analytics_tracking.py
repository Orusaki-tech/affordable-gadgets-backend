"""Tests for user activity tracking and session backfill."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from inventory.models import Cart, Customer, ObservabilityEvent, Product
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
    ObservabilityEvent.objects.create(
        session_key="sess-abc12",
        event_type="product_view",
        brand_code="AFFORDABLE_GADGETS",
        ip_address="10.0.0.1",
    )

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
def test_record_event_accepts_whatsapp_click(brand):
    product = Product.objects.create(product_name="Test Phone", brand="Samsung")
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
def test_legacy_record_event_url_delegates_to_record_event_view(brand):
    product = Product.objects.create(product_name="Legacy Phone", brand="Samsung")
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
