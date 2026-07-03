"""Tests for cleanup_carts management command."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from inventory.models import Cart, Customer
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_cleanup_carts_deletes_stale_unsubmitted_carts(brand):
    old_cart = Cart.objects.create(
        session_key="stale-anon",
        brand=brand,
        is_submitted=False,
    )
    Cart.objects.filter(pk=old_cart.pk).update(
        updated_at=timezone.now() - timedelta(days=70),
        expires_at=timezone.now() - timedelta(days=69),
    )

    recent_cart = Cart.objects.create(
        session_key="recent-anon",
        brand=brand,
        is_submitted=False,
    )

    call_command("cleanup_carts", stale_months=2)

    assert not Cart.objects.filter(pk=old_cart.pk).exists()
    assert Cart.objects.filter(pk=recent_cart.pk).exists()


@pytest.mark.django_db
def test_cleanup_carts_dry_run_keeps_carts(brand):
    old_cart = Cart.objects.create(session_key="dry-run", brand=brand, is_submitted=False)
    Cart.objects.filter(pk=old_cart.pk).update(
        updated_at=timezone.now() - timedelta(days=70),
    )

    call_command("cleanup_carts", stale_months=2, dry_run=True)

    assert Cart.objects.filter(pk=old_cart.pk).exists()


@pytest.mark.django_db
def test_cleanup_carts_keeps_recent_user_linked_cart(brand):
    user = User.objects.create_user(username="keeper", email="keeper@test.com", password="pass")
    customer = Customer.objects.create(user=user, email=user.email, email_verified=True)
    cart = Cart.objects.create(
        session_key="linked-recent",
        brand=brand,
        customer=customer,
        is_submitted=False,
    )
    Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now() - timedelta(days=10))

    call_command("cleanup_carts", stale_months=2)

    assert Cart.objects.filter(pk=cart.pk).exists()


@pytest.mark.django_db
def test_cleanup_carts_purge_anonymous(brand):
    user = User.objects.create_user(username="linked", email="linked@test.com", password="pass")
    customer = Customer.objects.create(user=user, email=user.email, email_verified=True)
    anon = Cart.objects.create(session_key="anon-purge", brand=brand, is_submitted=False)
    linked = Cart.objects.create(
        session_key="linked-purge",
        brand=brand,
        customer=customer,
        is_submitted=False,
    )

    call_command("cleanup_carts", purge_anonymous=True)

    assert not Cart.objects.filter(pk=anon.pk).exists()
    assert Cart.objects.filter(pk=linked.pk).exists()
