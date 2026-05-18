from decimal import Decimal

import pytest

from inventory.models import DeliveryRate
from inventory.services.delivery_service import get_delivery_fee

pytestmark = pytest.mark.django_db


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
