from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from inventory.models import PesapalPayment
from inventory.services.pesapal_payment_service import PesapalPaymentService

pytestmark = pytest.mark.django_db


@pytest.fixture
def pesapal_payment_settings(settings):
    settings.PESAPAL_CONSUMER_KEY = "test-key"
    settings.PESAPAL_CONSUMER_SECRET = "test-secret"
    settings.PESAPAL_IPN_URL = "https://example.com/ipn"
    settings.PESAPAL_NOTIFICATION_ID = "notif-001"
    settings.PESAPAL_ENVIRONMENT = "test"
    settings.PESAPAL_LOG_PATH = "/dev/null"
    return settings


class TestGetEffectiveOrderTotal:
    def test_items_only(self, order_with_units):
        total = PesapalPaymentService.get_effective_order_total(order_with_units, "ITEMS_ONLY")
        assert total > Decimal("0")

    def test_both(self, order_with_units):
        total = PesapalPaymentService.get_effective_order_total(order_with_units, "BOTH")
        items_total = sum(
            (item.sub_total for item in order_with_units.order_items.all()), Decimal("0.00")
        )
        delivery_fee = order_with_units.delivery_fee or Decimal("0.00")
        assert total == items_total + delivery_fee

    def test_defaults_to_both(self, order_with_units):
        total = PesapalPaymentService.get_effective_order_total(order_with_units)
        total_explicit = PesapalPaymentService.get_effective_order_total(order_with_units, "BOTH")
        assert total == total_explicit


class TestInitiatePayment:
    def test_returns_existing_payment(self, order_with_units, pesapal_payment_settings):
        payment = PesapalPayment.objects.create(
            order=order_with_units,
            pesapal_order_tracking_id="TRACK-EXISTING",
            redirect_url="https://pay.pesapal.com/checkout",
            status=PesapalPayment.StatusChoices.PENDING,
            amount=order_with_units.total_amount,
        )
        with patch.object(PesapalPaymentService, "pesapal_service", create=True):
            service = PesapalPaymentService()
            result = service.initiate_payment(
                order_with_units, callback_url="https://example.com/callback"
            )
            assert result["success"] is True
            assert result["order_tracking_id"] == "TRACK-EXISTING"

    def test_no_ipn_url_returns_error(self, order_with_units, settings):
        settings.PESAPAL_IPN_URL = ""
        service = PesapalPaymentService()
        result = service.initiate_payment(
            order_with_units, callback_url="https://example.com/callback"
        )
        assert result["success"] is False
        assert "IPN" in result.get("error", "")

    @patch("inventory.services.pesapal_payment_service.PesapalService")
    def test_successful_payment_initiation(
        self, mock_pesapal_cls, order_with_units, pesapal_payment_settings
    ):
        mock_service = MagicMock()
        mock_service.submit_order_request.return_value = (
            {"order_tracking_id": "TRACK-NEW", "redirect_url": "https://pay.pesapal.com/go"},
            None,
        )
        mock_pesapal_cls.return_value = mock_service

        service = PesapalPaymentService()
        result = service.initiate_payment(
            order_with_units, callback_url="https://example.com/callback"
        )

        assert result["success"] is True
        assert result["order_tracking_id"] == "TRACK-NEW"
        assert PesapalPayment.objects.filter(
            order=order_with_units, pesapal_order_tracking_id="TRACK-NEW"
        ).exists()

    @patch("inventory.services.pesapal_payment_service.PesapalService")
    def test_pesapal_error_returns_error(
        self, mock_pesapal_cls, order_with_units, pesapal_payment_settings
    ):
        mock_service = MagicMock()
        mock_service.submit_order_request.return_value = (None, "API error")
        mock_pesapal_cls.return_value = mock_service

        service = PesapalPaymentService()
        result = service.initiate_payment(
            order_with_units, callback_url="https://example.com/callback"
        )

        assert result["success"] is False
        assert result.get("error") is not None
