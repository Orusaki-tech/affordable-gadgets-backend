"""Tests for cart-add and WhatsApp lead email notifications."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from inventory.models import Cart, Customer, Product, WhatsAppClickEvent
from inventory.services.whatsapp_lead_service import (
    notify_cart_add,
    notify_whatsapp_lead,
    sync_customer_phone_from_cart,
)

User = get_user_model()


@pytest.mark.django_db
def test_sync_customer_phone_from_cart(brand):
    user = User.objects.create_user(username="phoneuser", email="phone@test.com", password="pass")
    customer = Customer.objects.create(user=user, email=user.email, email_verified=True)
    cart = Cart.objects.create(brand=brand, customer=customer, customer_phone="254712345678")

    sync_customer_phone_from_cart(cart)
    customer.refresh_from_db()
    assert customer.phone == "254712345678"


@pytest.mark.django_db
@patch("inventory.services.whatsapp_lead_service._send_shop_lead_email", return_value=True)
def test_notify_cart_add_sends_email(mock_send, brand, available_unit):
    user = User.objects.create_user(username="buyer", email="buyer@test.com", password="pass")
    customer = Customer.objects.create(
        user=user,
        email=user.email,
        phone="254799988877",
        email_verified=True,
    )
    cart = Cart.objects.create(
        brand=brand,
        customer=customer,
        customer_phone="254799988877",
        customer_email=user.email,
    )
    product = available_unit.product_template

    notify_cart_add(cart=cart, product=product, quantity=2, inventory_unit_id=available_unit.id)

    mock_send.assert_called_once()
    subject, message = mock_send.call_args[0]
    assert "Cart Add" in subject
    assert product.product_name in subject
    assert "254799988877" in message
    assert "buyer@test.com" in message
    assert "Quantity: 2" in message


@pytest.mark.django_db
@patch("inventory.services.whatsapp_lead_service._send_shop_lead_email", return_value=True)
def test_notify_cart_add_skips_without_phone(mock_send, brand, available_unit):
    user = User.objects.create_user(username="nophone", email="nophone@test.com", password="pass")
    customer = Customer.objects.create(user=user, email=user.email, email_verified=True)
    cart = Cart.objects.create(brand=brand, customer=customer)
    product = available_unit.product_template

    notify_cart_add(cart=cart, product=product, quantity=1)

    mock_send.assert_not_called()


@pytest.mark.django_db
@patch("inventory.services.whatsapp_lead_service._send_shop_lead_email", return_value=True)
def test_notify_whatsapp_lead_sends_email(mock_send, brand, product):
    event = WhatsAppClickEvent.objects.create(
        product=product,
        brand_code=brand.code,
        phone="254711122233",
        email="lead@test.com",
    )

    notify_whatsapp_lead(event)

    mock_send.assert_called_once()
    subject, message = mock_send.call_args[0]
    assert "WhatsApp Lead" in subject
    assert "254711122233" in message
    assert "lead@test.com" in message
