import pytest
import responses

from inventory.services.pesapal_service import PesapalService

pytestmark = pytest.mark.django_db


@pytest.fixture
def pesapal_settings(settings):
    settings.PESAPAL_CONSUMER_KEY = "test-consumer-key"
    settings.PESAPAL_CONSUMER_SECRET = "test-consumer-secret"
    settings.PESAPAL_ENVIRONMENT = "test"
    settings.PESAPAL_LOG_PATH = "/dev/null"
    return settings


@pytest.fixture
def service(pesapal_settings):
    return PesapalService()


class TestGetAccessToken:
    def test_success(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"token": "test-token-12345"},
                status=200,
            )
            token = service.get_access_token()
            assert token == "test-token-12345"

    def test_caches_token(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"token": "cached-token"},
                status=200,
            )
            t1 = service.get_access_token()
            t2 = service.get_access_token()
            assert t1 == t2 == "cached-token"
            assert len(rsps.calls) == 1

    def test_no_credentials_returns_none(self, settings):
        settings.PESAPAL_CONSUMER_KEY = ""
        settings.PESAPAL_CONSUMER_SECRET = ""
        s = PesapalService()
        assert s.get_access_token() is None

    def test_api_error_returns_none(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"error": {"message": "Invalid credentials"}},
                status=401,
            )
            assert service.get_access_token() is None

    def test_no_token_in_response_returns_none(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"status": "ok"},
                status=200,
            )
            assert service.get_access_token() is None


class TestSubmitOrderRequest:
    def test_success(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"token": "order-token"},
                status=200,
            )
            rsps.post(
                "https://pay.pesapal.com/v3/api/Transactions/SubmitOrderRequest",
                json={
                    "order_tracking_id": "TRACK-001",
                    "redirect_url": "https://pay.pesapal.com/checkout",
                },
                status=200,
            )
            result, error = service.submit_order_request({"amount": 1000, "currency": "KES"})
            assert error is None
            assert result["order_tracking_id"] == "TRACK-001"

    def test_no_token_returns_error(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                status=401,
            )
            result, error = service.submit_order_request({"amount": 1000})
            assert result is None
            assert error is not None

    def test_api_error_returns_error(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"token": "order-token-2"},
                status=200,
            )
            rsps.post(
                "https://pay.pesapal.com/v3/api/Transactions/SubmitOrderRequest",
                json={"error": {"message": "Invalid request"}},
                status=400,
            )
            result, error = service.submit_order_request({"amount": -1})
            assert result is None
            assert error is not None


class TestGetTransactionStatus:
    def test_success(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"token": "status-token"},
                status=200,
            )
            rsps.get(
                "https://pay.pesapal.com/v3/api/Transactions/GetTransactionStatus?orderTrackingId=TRACK-001",
                json={"status": "COMPLETED", "amount": 1000},
                status=200,
            )
            result, error = service.get_transaction_status("TRACK-001")
            assert error is None
            assert result["status"] == "COMPLETED"

    def test_no_token_returns_error(self, service):
        with responses.RequestsMock() as rsps:
            result, error = service.get_transaction_status("TRACK-002")
            assert result is None
            assert error is not None


class TestRegisterIPNUrl:
    def test_success(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"token": "ipn-token"},
                status=200,
            )
            rsps.post(
                "https://pay.pesapal.com/v3/api/URLSetup/RegisterIPN",
                json={"ipn_id": "IPN-001"},
                status=200,
            )
            ipn_id, error = service.register_ipn_url("https://example.com/ipn")
            assert error is None
            assert ipn_id == "IPN-001"

    def test_no_ipn_id_returns_error(self, service):
        with responses.RequestsMock() as rsps:
            rsps.post(
                "https://pay.pesapal.com/v3/api/Auth/RequestToken",
                json={"token": "ipn-token-2"},
                status=200,
            )
            rsps.post(
                "https://pay.pesapal.com/v3/api/URLSetup/RegisterIPN",
                json={"status": "ok"},
                status=200,
            )
            ipn_id, error = service.register_ipn_url("https://example.com/ipn")
            assert ipn_id is None
            assert error is not None
