"""
SMS service for sending notifications via Twilio SMS API.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class SmsService:
    """
    Send SMS messages through Twilio.
    """

    @staticmethod
    def send_message(phone_number: str, message_body: str) -> bool:
        """Send a plain SMS message via Twilio."""
        try:
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException
        except ImportError:
            logger.error("Twilio library not installed. Install with: pip install twilio")
            return False

        try:
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            sms_from = getattr(settings, 'TWILIO_SMS_FROM', None)

            if not all([account_sid, auth_token, sms_from]):
                logger.warning("Twilio SMS not configured. Skipping SMS delivery.")
                return False

            # Reuse WhatsApp phone normalization for Kenya numbers
            from inventory.services.whatsapp_service import WhatsAppService

            formatted_phone = WhatsAppService.format_phone_number(phone_number)
            if not formatted_phone:
                logger.warning(f"Invalid phone number format: {phone_number}")
                return False

            timeout = int(getattr(settings, 'TWILIO_TIMEOUT', 10))
            try:
                from twilio.http.http_client import TwilioHttpClient as TwilioClientClass
            except ImportError:
                from twilio.http.http_client import HttpClient as TwilioClientClass

            http_client = None
            try:
                http_client = TwilioClientClass(logger=logger, is_async=False, timeout=timeout)
            except Exception:
                try:
                    http_client = TwilioClientClass(timeout=timeout)
                except Exception:
                    http_client = None

            client = Client(account_sid, auth_token, http_client=http_client) if http_client else Client(account_sid, auth_token)

            message = client.messages.create(
                body=message_body,
                from_=sms_from,
                to=formatted_phone
            )
            logger.info(f"SMS sent to {formatted_phone}. Message SID: {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {phone_number}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending SMS to {phone_number}: {e}")
            return False
