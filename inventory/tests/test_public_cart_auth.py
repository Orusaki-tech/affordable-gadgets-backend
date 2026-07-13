"""Tests that cart API requires authentication."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from inventory.models import Cart, Customer

User = get_user_model()


@pytest.mark.django_db
def test_cart_create_requires_auth(brand):
    client = APIClient()
    client.credentials(HTTP_X_BRAND_CODE=brand.code)
    response = client.post("/api/v1/public/cart/", {}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_cart_create_for_authenticated_customer(brand):
    user = User.objects.create_user(username="buyer", email="buyer@test.com", password="pass")
    customer = Customer.objects.create(
        user=user,
        email=user.email,
        phone="+254700000099",
        email_verified=True,
    )
    token, _ = Token.objects.get_or_create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}", HTTP_X_BRAND_CODE=brand.code)
    response = client.post("/api/v1/public/cart/", {}, format="json")
    assert response.status_code == 200
    cart = Cart.objects.get(customer=customer, brand=brand, is_submitted=False)
    assert cart.id == response.data["id"]


@pytest.mark.django_db
def test_cart_create_for_user_without_customer_profile(brand):
    user = User.objects.create_user(
        username="google_user",
        email="google@test.com",
        password="unused",
    )
    user.set_unusable_password()
    user.supabase_uid = "supabase-uid-123"
    user.save(update_fields=["password", "supabase_uid"])
    token, _ = Token.objects.get_or_create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}", HTTP_X_BRAND_CODE=brand.code)
    response = client.post("/api/v1/public/cart/", {}, format="json")
    assert response.status_code == 200
    customer = Customer.objects.get(user=user)
    assert customer.email_verified is True
    cart = Cart.objects.get(customer=customer, brand=brand, is_submitted=False)
    assert cart.id == response.data["id"]


@pytest.mark.django_db
def test_cart_create_for_staff_user_without_customer_profile(brand):
    """Staff accounts used on the storefront must still get a Customer + cart."""
    user = User.objects.create_user(
        username="shop_admin",
        email="admin-shop@test.com",
        password="pass",
        is_staff=True,
    )
    token, _ = Token.objects.get_or_create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}", HTTP_X_BRAND_CODE=brand.code)
    response = client.post("/api/v1/public/cart/", {}, format="json")
    assert response.status_code == 200
    customer = Customer.objects.get(user=user)
    cart = Cart.objects.get(customer=customer, brand=brand, is_submitted=False)
    assert cart.id == response.data["id"]


@pytest.mark.django_db
def test_cart_add_item_requires_auth(brand):
    cart = Cart.objects.create(session_key="anon", brand=brand)
    client = APIClient()
    client.credentials(HTTP_X_BRAND_CODE=brand.code)
    response = client.post(
        f"/api/v1/public/cart/{cart.id}/items/",
        {"inventory_unit_id": 1, "quantity": 1},
        format="json",
    )
    assert response.status_code == 401
