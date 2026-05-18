from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.models import Lead
from inventory.services.interest_service import InterestService

pytestmark = pytest.mark.django_db


class TestInterestService:
    def test_get_interest_count_zero(self, available_unit):
        assert InterestService.get_interest_count(available_unit) == 0

    def test_get_interest_count_with_active_lead(self, available_unit, customer, brand):
        lead = Lead.objects.create(
            customer=customer,
            brand=brand,
            status=Lead.StatusChoices.NEW,
            expires_at=timezone.now() + timedelta(days=7),
        )
        lead.items.create(inventory_unit=available_unit, unit_price=Decimal("1000"))
        assert InterestService.get_interest_count(available_unit) == 1

    def test_expired_lead_not_counted(self, available_unit, customer, brand):
        lead = Lead.objects.create(
            customer=customer,
            brand=brand,
            status=Lead.StatusChoices.NEW,
            expires_at=timezone.now() - timedelta(days=1),
        )
        lead.items.create(inventory_unit=available_unit, unit_price=Decimal("1000"))
        assert InterestService.get_interest_count(available_unit) == 0

    def test_converted_lead_not_counted(self, available_unit, customer, brand):
        lead = Lead.objects.create(
            customer=customer,
            brand=brand,
            status=Lead.StatusChoices.CONVERTED,
            expires_at=timezone.now() + timedelta(days=7),
        )
        lead.items.create(inventory_unit=available_unit, unit_price=Decimal("1000"))
        assert InterestService.get_interest_count(available_unit) == 0

    def test_get_product_interest_count(self, product, available_unit, customer, brand):
        Lead.objects.create(
            customer=customer,
            brand=brand,
            status=Lead.StatusChoices.NEW,
            expires_at=timezone.now() + timedelta(days=7),
        ).items.create(inventory_unit=available_unit, unit_price=Decimal("1000"))
        assert InterestService.get_product_interest_count(product) >= 1

    def test_get_product_interest_zero_for_no_units(self, product):
        assert InterestService.get_product_interest_count(product) == 0
