import pytest
from unittest.mock import patch, MagicMock
from inventory.models import Order
from inventory.services.order_email_service import OrderEmailService


pytestmark = pytest.mark.django_db


class TestSendOrderConfirmationEmail:
    def test_sends_email_for_valid_order(self, order, settings):
        settings.DEFAULT_FROM_EMAIL = "noreply@test.com"
        with patch("inventory.services.order_email_service.EmailMessage") as mock_email_cls:
            mock_email = MagicMock()
            mock_email_cls.return_value = mock_email
            result = OrderEmailService.send_order_confirmation_email(order)
        assert result is True
        mock_email.send.assert_called_once()
        subject = mock_email_cls.call_args[1]["subject"]
        assert str(order.order_id) in subject

    def test_returns_false_when_no_customer_email(self, order):
        order.customer.email = None
        order.customer.user.email = None
        order.customer.user = None
        order.customer.save()
        order.refresh_from_db()
        result = OrderEmailService.send_order_confirmation_email(order)
        assert result is False
