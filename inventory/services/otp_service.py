"""OTP utilities for public review verification."""

import hashlib
import secrets

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail


class OtpService:
    """Lightweight OTP service backed by cache."""

    PURPOSE_REVIEW = "review"
    PURPOSE_ORDER = "order"

    @staticmethod
    def _otp_cache_key(identifier: str, purpose: str) -> str:
        return f"otp:{purpose}:{identifier}"

    @staticmethod
    def _otp_rate_key(identifier: str, purpose: str) -> str:
        return f"otp:{purpose}:rate:{identifier}"

    @staticmethod
    def _hash_code(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_code(length: int = 6) -> str:
        """Generate a numeric OTP."""
        return "".join(str(secrets.randbelow(10)) for _ in range(length))

    @classmethod
    def send_review_otp(cls, email: str) -> dict:
        """Generate and send OTP for review verification."""
        ttl_seconds = int(getattr(settings, "REVIEW_OTP_TTL_SECONDS", 600))
        max_sends = int(getattr(settings, "REVIEW_OTP_MAX_SENDS", 3))
        rate_window = int(getattr(settings, "REVIEW_OTP_RATE_WINDOW_SECONDS", 900))

        normalized_email = (email or "").strip().lower()
        rate_key = cls._otp_rate_key(normalized_email, cls.PURPOSE_REVIEW)
        sends = cache.get(rate_key, 0)
        if sends >= max_sends:
            return {
                "sent": False,
                "error": "Too many OTP requests. Please wait and try again.",
                "retry_after": rate_window,
            }

        code = cls.generate_code()
        cache.set(
            cls._otp_cache_key(normalized_email, cls.PURPOSE_REVIEW),
            cls._hash_code(code),
            ttl_seconds,
        )
        cache.set(rate_key, sends + 1, rate_window)

        try:
            send_mail(
                subject="Your Affordable Gadgets review verification code",
                message=(
                    "Your Affordable Gadgets review verification code is "
                    f"{code}. It expires in {ttl_seconds // 60} minutes."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[normalized_email],
                fail_silently=False,
            )
            sent = True
        except Exception:
            sent = False

        if not sent and not settings.DEBUG:
            return {
                "sent": False,
                "error": "Unable to send OTP. Please try again later.",
            }

        response = {
            "sent": True,
            "expires_in": ttl_seconds,
        }
        if settings.DEBUG:
            response["debug_code"] = code
        return response

    @classmethod
    def send_order_otp(cls, email: str) -> dict:
        """Generate and send OTP for order history verification."""
        ttl_seconds = int(
            getattr(
                settings, "ORDER_OTP_TTL_SECONDS", getattr(settings, "REVIEW_OTP_TTL_SECONDS", 600)
            )
        )
        max_sends = int(
            getattr(settings, "ORDER_OTP_MAX_SENDS", getattr(settings, "REVIEW_OTP_MAX_SENDS", 3))
        )
        rate_window = int(
            getattr(
                settings,
                "ORDER_OTP_RATE_WINDOW_SECONDS",
                getattr(settings, "REVIEW_OTP_RATE_WINDOW_SECONDS", 900),
            )
        )

        normalized_email = (email or "").strip().lower()
        rate_key = cls._otp_rate_key(normalized_email, cls.PURPOSE_ORDER)
        sends = cache.get(rate_key, 0)
        if sends >= max_sends:
            return {
                "sent": False,
                "error": "Too many OTP requests. Please wait and try again.",
                "retry_after": rate_window,
            }

        code = cls.generate_code()
        cache.set(
            cls._otp_cache_key(normalized_email, cls.PURPOSE_ORDER),
            cls._hash_code(code),
            ttl_seconds,
        )
        cache.set(rate_key, sends + 1, rate_window)

        try:
            send_mail(
                subject="Your Affordable Gadgets order verification code",
                message=(
                    "Your Affordable Gadgets order verification code is "
                    f"{code}. It expires in {ttl_seconds // 60} minutes."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[normalized_email],
                fail_silently=False,
            )
            sent = True
        except Exception:
            sent = False

        if not sent and not settings.DEBUG:
            return {
                "sent": False,
                "error": "Unable to send OTP. Please try again later.",
            }

        response = {
            "sent": True,
            "expires_in": ttl_seconds,
        }
        if settings.DEBUG:
            response["debug_code"] = code
        return response

    @classmethod
    def verify_review_otp(cls, email: str, otp: str) -> bool:
        """Verify OTP for review verification."""
        if not otp:
            return False
        normalized_email = (email or "").strip().lower()
        cached = cache.get(cls._otp_cache_key(normalized_email, cls.PURPOSE_REVIEW))
        if not cached:
            return False
        return cached == cls._hash_code(str(otp).strip())

    @classmethod
    def verify_order_otp(cls, email: str, otp: str) -> bool:
        """Verify OTP for order history verification."""
        if not otp:
            return False
        normalized_email = (email or "").strip().lower()
        cached = cache.get(cls._otp_cache_key(normalized_email, cls.PURPOSE_ORDER))
        if not cached:
            return False
        return cached == cls._hash_code(str(otp).strip())
