"""Tests for user activity tracking and session backfill."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from inventory.models import Customer, ObservabilityEvent, Product
from inventory.services.analytics_service import (
    backfill_session_events_to_user,
    link_cart_to_authenticated_user,
)

User = get_user_model()


@pytest.mark.django_db
def test_backfill_session_events_to_user():
    user = User.objects.create_user(username="shopper", email="shopper@test.com", password="pass")
    ObservabilityEvent.objects.create(
        session_key="sess-abc",
        event_type="product_view",
        brand_code="AFFORDABLE_GADGETS",
    )
    ObservabilityEvent.objects.create(
        session_key="sess-other",
        event_type="search",
        brand_code="AFFORDABLE_GADGETS",
    )

    linked = backfill_session_events_to_user(user, "sess-abc")

    assert linked == 1
    assert ObservabilityEvent.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_record_event_accepts_whatsapp_click(brand):
    product = Product.objects.create(product_name="Test Phone", brand="Samsung")
    client = APIClient()
    response = client.post(
        "/api/v1/public/events/",
        {
            "event_type": "whatsapp_click",
            "product_id": product.id,
            "session_key": "sess-wa",
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
        {"session_key": "sess-cart-1"},
        format="json",
    )

    assert response.status_code == 200
    cart_id = response.data["id"]
    from inventory.models import Cart

    cart = Cart.objects.get(id=cart_id)
    assert cart.customer_id == user.customer.id


@pytest.mark.django_db
def test_login_backfills_session_events(brand):
    user = User.objects.create_user(username="loginuser", email="login@test.com", password="pass")
    Customer.objects.create(user=user, email=user.email, email_verified=True)
    ObservabilityEvent.objects.create(
        session_key="sess-login",
        event_type="page_view",
        brand_code=brand.code,
        metadata={"path": "/"},
    )

    client = APIClient()
    response = client.post(
        "/api/inventory/login/",
        {
            "username_or_email": "login@test.com",
            "password": "pass",
            "session_key": "sess-login",
        },
        format="json",
        HTTP_X_BRAND_CODE=brand.code,
    )

    assert response.status_code == 200
    assert ObservabilityEvent.objects.filter(user=user, event_type="page_view").exists()


@pytest.mark.django_db
def test_link_cart_to_authenticated_user_sets_customer(brand):
    user = User.objects.create_user(username="linker", email="link@test.com", password="pass")
    customer = Customer.objects.create(user=user, email=user.email, email_verified=True)
    from inventory.models import Cart

    cart = Cart.objects.create(session_key="sess-link", brand=brand)
    link_cart_to_authenticated_user(cart, user)
    cart.refresh_from_db()
    assert cart.customer_id == customer.id
