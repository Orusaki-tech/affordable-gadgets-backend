from unittest.mock import patch

import pytest

from inventory.services.otp_service import OtpService

pytestmark = pytest.mark.django_db


class TestOtpServiceGenerateCode:
    def test_generates_numeric_code(self):
        code = OtpService.generate_code()
        assert code.isdigit()
        assert len(code) == 6

    def test_custom_length(self):
        code = OtpService.generate_code(8)
        assert len(code) == 8

    def test_different_codes(self):
        codes = {OtpService.generate_code() for _ in range(100)}
        assert len(codes) > 1


class TestOtpServiceSendReviewOtp:
    def test_sends_otp_and_returns_debug_code(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail") as mock_send:
            result = OtpService.send_review_otp("test@example.com")
        assert result["sent"] is True
        assert "debug_code" in result
        assert len(result["debug_code"]) == 6
        mock_send.assert_called_once()

    def test_rate_limiting(self):
        with patch("inventory.services.otp_service.send_mail"):
            for _ in range(3):
                OtpService.send_review_otp("rate@test.com")
            result = OtpService.send_review_otp("rate@test.com")
        assert result["sent"] is False
        assert "Too many" in result["error"]

    def test_email_verification_roundtrip(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail"):
            result = OtpService.send_review_otp("roundtrip@test.com")
        assert result["sent"] is True
        code = result["debug_code"]
        assert OtpService.verify_review_otp("roundtrip@test.com", code) is True

    def test_wrong_otp_fails(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail"):
            OtpService.send_review_otp("wrong@test.com")
        assert OtpService.verify_review_otp("wrong@test.com", "000000") is False

    def test_expired_otp_fails(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail"):
            OtpService.send_review_otp("expire@test.com")
        from django.core.cache import cache

        cache.clear()
        assert OtpService.verify_review_otp("expire@test.com", "111111") is False

    def test_empty_otp_fails(self):
        assert OtpService.verify_review_otp("empty@test.com", "") is False
        assert OtpService.verify_review_otp("empty@test.com", None) is False


class TestOtpServiceSendOrderOtp:
    def test_sends_order_otp(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail") as mock_send:
            result = OtpService.send_order_otp("order@test.com")
        assert result["sent"] is True
        assert "debug_code" in result
        mock_send.assert_called_once()

    def test_order_otp_verification_roundtrip(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail"):
            result = OtpService.send_order_otp("order_verify@test.com")
        assert OtpService.verify_order_otp("order_verify@test.com", result["debug_code"]) is True

    def test_review_and_order_keys_isolated(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail"):
            review_result = OtpService.send_review_otp("isolated@test.com")
            order_result = OtpService.send_order_otp("isolated@test.com")
        assert (
            OtpService.verify_review_otp("isolated@test.com", review_result["debug_code"]) is True
        )
        assert OtpService.verify_order_otp("isolated@test.com", order_result["debug_code"]) is True
        assert (
            OtpService.verify_order_otp("isolated@test.com", review_result["debug_code"]) is False
        )

    def test_order_otp_sent_with_correct_subject(self, settings):
        settings.DEBUG = True
        with patch("inventory.services.otp_service.send_mail") as mock_send:
            OtpService.send_order_otp("subject@test.com")
        subject = mock_send.call_args[1].get("subject", "")
        assert "order" in subject.lower()
