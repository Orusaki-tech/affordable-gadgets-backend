from decimal import Decimal

import pytest

from inventory.models import DeliveryRate
from inventory.services.delivery_service import (
    DeliveryResolutionError,
    get_delivery_fee,
    resolve_online_delivery,
)

pytestmark = pytest.mark.django_db


class TestResolveOnlineDelivery:
    def test_pickup_explicit_zero_fee(self):
        fulfillment, fee = resolve_online_delivery(fulfillment_method="PICKUP")
        assert fulfillment == "PICKUP"
        assert fee == Decimal("0.00")

    def test_inferred_pickup_when_no_delivery_fields(self):
        fulfillment, fee = resolve_online_delivery()
        assert fulfillment == "PICKUP"
        assert fee == Decimal("0.00")

    def test_address_without_county_rejected(self):
        with pytest.raises(DeliveryResolutionError) as exc:
            resolve_online_delivery(delivery_address="Somewhere in Nairobi")
        assert "delivery_county" in exc.value.errors

    def test_delivery_requires_configured_rate(self):
        with pytest.raises(DeliveryResolutionError) as exc:
            resolve_online_delivery(
                fulfillment_method="DELIVERY", delivery_county="Nowhereville"
            )
        assert "delivery_county" in exc.value.errors

    def test_delivery_with_rate(self):
        DeliveryRate.objects.create(
            county="Nairobi", ward=None, price=Decimal("500.00"), is_active=True
        )
        DeliveryRate.objects.create(
            county="Nairobi", ward="Westlands", price=Decimal("300.00"), is_active=True
        )
        fulfillment, fee = resolve_online_delivery(
            fulfillment_method="DELIVERY",
            delivery_county="Nairobi",
            delivery_ward="Westlands",
        )
        assert fulfillment == "DELIVERY"
        assert fee == Decimal("300.00")

    def test_nairobi_requires_ward(self):
        DeliveryRate.objects.create(
            county="Nairobi", ward=None, price=Decimal("500.00"), is_active=True
        )
        with pytest.raises(DeliveryResolutionError) as exc:
            resolve_online_delivery(
                fulfillment_method="DELIVERY", delivery_county="Nairobi"
            )
        assert "delivery_ward" in exc.value.errors


class TestGetDeliveryFee:
    def test_county_only_match(self):
        DeliveryRate.objects.create(
            county="Nairobi", ward=None, price=Decimal("500.00"), is_active=True
        )
        fee, rate = get_delivery_fee("Nairobi")
        assert fee == Decimal("500.00")
        assert rate is not None
        assert rate.county == "Nairobi"

    def test_ward_overrides_county(self):
        DeliveryRate.objects.create(
            county="Nairobi", ward=None, price=Decimal("500.00"), is_active=True
        )
        DeliveryRate.objects.create(
            county="Nairobi", ward="Westlands", price=Decimal("300.00"), is_active=True
        )
        fee, _ = get_delivery_fee("Nairobi", "Westlands")
        assert fee == Decimal("300.00")

    def test_county_fallback_when_no_ward_match(self):
        DeliveryRate.objects.create(
            county="Nairobi", ward=None, price=Decimal("500.00"), is_active=True
        )
        fee, _ = get_delivery_fee("Nairobi", "UnknownWard")
        assert fee == Decimal("500.00")

    def test_no_match_returns_zero(self):
        fee, rate = get_delivery_fee("NonExistentCounty")
        assert fee == Decimal("0.00")
        assert rate is None

    def test_null_county_returns_zero(self):
        fee, rate = get_delivery_fee(None)
        assert fee == Decimal("0.00")
        assert rate is None

    def test_empty_county_returns_zero(self):
        fee, rate = get_delivery_fee("")
        assert fee == Decimal("0.00")
        assert rate is None

    def test_case_insensitive_county(self):
        DeliveryRate.objects.create(
            county="Mombasa", ward=None, price=Decimal("800.00"), is_active=True
        )
        fee, _ = get_delivery_fee("mombasa")
        assert fee == Decimal("800.00")

    def test_inactive_rate_ignored(self):
        DeliveryRate.objects.create(
            county="Nairobi", ward=None, price=Decimal("500.00"), is_active=True
        )
        DeliveryRate.objects.create(
            county="Nairobi", ward=None, price=Decimal("400.00"), is_active=False
        )
        fee, _ = get_delivery_fee("Nairobi")
        assert fee == Decimal("500.00")
