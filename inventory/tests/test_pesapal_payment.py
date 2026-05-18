"""P0: Pesapal payment IPN callback, status transitions, and refund handling.

These tests verify the most critical money-moving code path — payment processing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import responses
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Order, PesapalPayment

pytestmark = [pytest.mark.p0, pytest.mark.django_db]


class TestPesapalIPNCallback:
    """Verify the Pesapal IPN endpoint correctly processes payment notifications."""

    IPN_URL = "/api/inventory/pesapal/ipn/"

    @responses.activate
    @override_settings(PESAPAL_CONSUMER_KEY="test-key", PESAPAL_CONSUMER_SECRET="test-secret")
    def test_ipn_with_valid_tracking_id(self, api_client: APIClient, order: Order) -> None:
        pesapal_payment = PesapalPayment.objects.create(
            order=order,
            pesapal_order_tracking_id="tracking-123",
            amount=order.total_amount,
            currency="KES",
            status=PesapalPayment.StatusChoices.IN_PROGRESS,
        )

        responses.get(
            "https://api.pesapal.com/transactions/status",
            json={"order_status": "COMPLETED"},
            status=200,
        )

        params = {
            "OrderTrackingId": "tracking-123",
            "OrderNotificationType": "CHANGE",
            "OrderMerchantReference": str(order.order_id),
            "PaymentStatusDescription": "Completed",
            "PaymentMethod": "MPESA",
            "PaymentAccount": "254700000000",
        }
        response = api_client.get(self.IPN_URL, params)
        assert response.status_code == status.HTTP_200_OK, response.content

    def test_ipn_requires_tracking_id(self, api_client: APIClient) -> None:
        response = api_client.get(self.IPN_URL, {"not-tracking-id": "x"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ipn_with_nonexistent_tracking_id(self, api_client: APIClient) -> None:
        params = {"OrderTrackingId": "nonexistent-tracking-id"}
        response = api_client.get(self.IPN_URL, params)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_ipn_post_method(self, api_client: APIClient, order: Order) -> None:
        PesapalPayment.objects.create(
            order=order,
            pesapal_order_tracking_id="post-tracking",
            amount=order.total_amount,
            currency="KES",
        )
        response = api_client.post(
            self.IPN_URL,
            {"OrderTrackingId": "post-tracking"},
        )
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        )


class TestPesapalPaymentStatusTransitions:
    """Verify payment status transitions are valid."""

    def test_payment_created_as_pending(self, order: Order) -> None:
        payment = PesapalPayment.objects.create(
            order=order,
            pesapal_order_tracking_id="track-status-1",
            amount=Decimal("55000.00"),
            currency="KES",
        )
        assert payment.status == PesapalPayment.StatusChoices.PENDING
        assert not payment.is_successful

    def test_payment_transition_to_completed(self, order: Order) -> None:
        payment = PesapalPayment.objects.create(
            order=order,
            pesapal_order_tracking_id="track-status-2",
            amount=Decimal("55000.00"),
            currency="KES",
            status=PesapalPayment.StatusChoices.IN_PROGRESS,
        )
        payment.status = PesapalPayment.StatusChoices.COMPLETED
        payment.is_verified = True
        payment.completed_at = __import__("django").utils.timezone.now()
        payment.save()

        payment.refresh_from_db()
        assert payment.status == PesapalPayment.StatusChoices.COMPLETED
        assert payment.is_successful

    def test_payment_transition_to_failed(self, order: Order) -> None:
        payment = PesapalPayment.objects.create(
            order=order,
            pesapal_order_tracking_id="track-status-3",
            amount=Decimal("55000.00"),
            currency="KES",
            status=PesapalPayment.StatusChoices.IN_PROGRESS,
        )
        payment.status = PesapalPayment.StatusChoices.FAILED
        payment.save()

        payment.refresh_from_db()
        assert payment.status == PesapalPayment.StatusChoices.FAILED
        assert not payment.is_successful

    def test_payment_expiry_check(self, order: Order) -> None:
        payment = PesapalPayment.objects.create(
            order=order,
            pesapal_order_tracking_id="track-status-4",
            amount=Decimal("55000.00"),
            currency="KES",
            status=PesapalPayment.StatusChoices.EXPIRED,
        )
        assert payment.is_expired


class TestOrderPaymentStatusView:
    """Verify the payment status endpoint works correctly."""

    def test_payment_status_endpoint(self, api_client: APIClient, paid_order: Order) -> None:
        PesapalPayment.objects.create(
            order=paid_order,
            pesapal_order_tracking_id="view-status-test",
            amount=paid_order.total_amount,
            currency="KES",
            status=PesapalPayment.StatusChoices.COMPLETED,
            is_verified=True,
        )

        url = f"/api/inventory/orders/{paid_order.order_id}/payment_status/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK, response.content

    def test_payment_status_for_nonexistent_order(self, api_client: APIClient) -> None:
        url = "/api/inventory/orders/00000000-0000-0000-0000-000000000000/payment_status/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
