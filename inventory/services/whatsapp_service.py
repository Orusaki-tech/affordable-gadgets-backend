"""
WhatsApp service for sending receipts via Twilio WhatsApp API.
"""
import logging
import re
from typing import Optional
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for sending WhatsApp messages via Twilio."""
    
    @staticmethod
    def format_phone_number(phone: str) -> Optional[str]:
        """
        Format phone number to E.164 format for WhatsApp (+254XXXXXXXXX).
        Handles various Kenyan phone number formats.
        """
        if not phone:
            return None
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Handle Kenyan phone numbers
        if digits.startswith('254'):
            # Already has country code
            return f"+{digits}"
        elif digits.startswith('0'):
            # Remove leading 0 and add country code
            return f"+254{digits[1:]}"
        elif len(digits) == 9:
            # 9 digits, add country code
            return f"+254{digits}"
        elif len(digits) == 10:
            # 10 digits starting with 0, remove 0 and add country code
            if digits.startswith('0'):
                return f"+254{digits[1:]}"
            else:
                return f"+254{digits}"
        else:
            # Try to add country code if it looks like a Kenyan number
            if len(digits) >= 9:
                return f"+254{digits[-9:]}"
        
        logger.warning(f"Could not format phone number: {phone}")
        return None
    
    @staticmethod
    def send_receipt_whatsapp(
        phone_number: str,
        receipt_number: str,
        order_id: str,
        total_amount: float,
        pdf_url: Optional[str] = None,
        customer_name: str = "Customer"
    ) -> bool:
        """
        Send receipt via WhatsApp using Twilio.
        
        Args:
            phone_number: Customer phone number
            receipt_number: Receipt number
            order_id: Order ID
            total_amount: Total order amount
            pdf_url: Optional URL to PDF receipt (if hosted)
            customer_name: Customer name
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException
            from twilio.http.http_client import HttpClient
        except ImportError:
            logger.error("Twilio library not installed. Install with: pip install twilio")
            return False

    @staticmethod
    def send_message(phone_number: str, message_body: str) -> bool:
        """Send a plain WhatsApp message via Twilio."""
        try:
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException
            from twilio.http.http_client import HttpClient
        except ImportError:
            logger.error("Twilio library not installed. Install with: pip install twilio")
            return False

        try:
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', None)

            if not all([account_sid, auth_token, whatsapp_from]):
                logger.warning("Twilio WhatsApp not configured. Skipping WhatsApp delivery.")
                return False

            formatted_phone = WhatsAppService.format_phone_number(phone_number)
            if not formatted_phone:
                logger.warning(f"Invalid phone number format: {phone_number}")
                return False

            timeout = int(getattr(settings, 'TWILIO_TIMEOUT', 10))
            http_client = HttpClient(logger=logger, is_async=False, timeout=timeout)
            client = Client(account_sid, auth_token, http_client=http_client)

            message = client.messages.create(
                body=message_body,
                from_=whatsapp_from,
                to=f"whatsapp:{formatted_phone}"
            )
            logger.info(f"WhatsApp message sent to {formatted_phone}. Message SID: {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"Twilio error sending WhatsApp to {phone_number}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message to {phone_number}: {e}")
            return False
        
        try:
            # Check if Twilio is configured
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', None)
            
            if not all([account_sid, auth_token, whatsapp_from]):
                logger.warning("Twilio WhatsApp not configured. Skipping WhatsApp delivery.")
                return False
            
            # Format phone number
            formatted_phone = WhatsAppService.format_phone_number(phone_number)
            if not formatted_phone:
                logger.warning(f"Invalid phone number format: {phone_number}")
                return False
            
            # Initialize Twilio client with timeout to avoid blocking workers
            timeout = int(getattr(settings, 'TWILIO_TIMEOUT', 10))
            http_client = HttpClient(logger=logger, is_async=False, timeout=timeout)
            client = Client(account_sid, auth_token, http_client=http_client)
            
            # Prepare message
            receipt_line = f"\n📄 Receipt: {pdf_url}\n" if pdf_url else "\n"
            message_body = f"""🎉 *Payment Confirmed!*

Dear {customer_name},

Thank you for your purchase at Affordable Gadgets!

📋 *Receipt Details:*
• Receipt No: {receipt_number}
• Order ID: {order_id}
• Total Amount: Ksh {total_amount:,.2f}
{receipt_line}
Your receipt has been sent to your email. If you have any questions, please contact us at +254717881573.

Best regards,
Affordable Gadgets Team
📍 Kimathi House, Fourth Floor, Room 409"""
            
            # Send WhatsApp message
            message = client.messages.create(
                body=message_body,
                from_=whatsapp_from,  # Twilio WhatsApp number (format: whatsapp:+14155238886)
                to=f"whatsapp:{formatted_phone}"
            )
            
            logger.info(f"WhatsApp receipt sent to {formatted_phone} for order {order_id}. Message SID: {message.sid}")
            return True
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending WhatsApp to {phone_number}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp receipt to {phone_number}: {e}")
            return False
    
    @staticmethod
    def send_receipt_with_media(
        phone_number: str,
        receipt_number: str,
        order_id: str,
        total_amount: float,
        media_url: str,
        customer_name: str = "Customer"
    ) -> bool:
        """
        Send receipt via WhatsApp with PDF attachment.
        Note: Twilio WhatsApp requires media to be hosted on a publicly accessible URL.
        
        Args:
            phone_number: Customer phone number
            receipt_number: Receipt number
            order_id: Order ID
            total_amount: Total order amount
            media_url: Public URL to PDF file
            customer_name: Customer name
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException
            from twilio.http.http_client import HttpClient
        except ImportError:
            logger.error("Twilio library not installed. Install with: pip install twilio")
            return False
        
        try:
            # Check if Twilio is configured
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', None)
            
            if not all([account_sid, auth_token, whatsapp_from]):
                logger.warning("Twilio WhatsApp not configured. Skipping WhatsApp delivery.")
                return False
            
            # Format phone number
            formatted_phone = WhatsAppService.format_phone_number(phone_number)
            if not formatted_phone:
                logger.warning(f"Invalid phone number format: {phone_number}")
                return False
            
            # Initialize Twilio client with timeout to avoid blocking workers
            timeout = int(getattr(settings, 'TWILIO_TIMEOUT', 10))
            http_client = HttpClient(logger=logger, is_async=False, timeout=timeout)
            client = Client(account_sid, auth_token, http_client=http_client)
            
            # Prepare message
            message_body = f"""🎉 *Payment Confirmed!*

Dear {customer_name},

Thank you for your purchase at Affordable Gadgets!

📋 *Receipt Details:*
• Receipt No: {receipt_number}
• Order ID: {order_id}
• Total Amount: Ksh {total_amount:,.2f}

Please find your receipt attached.

If you have any questions, contact us at +254717881573.

Best regards,
Affordable Gadgets Team"""
            
            # Send WhatsApp message with media
            message = client.messages.create(
                body=message_body,
                from_=whatsapp_from,
                to=f"whatsapp:{formatted_phone}",
                media_url=[media_url]  # List of media URLs
            )
            
            logger.info(f"WhatsApp receipt with PDF sent to {formatted_phone} for order {order_id}. Message SID: {message.sid}")
            return True
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending WhatsApp with media to {phone_number}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp receipt with media to {phone_number}: {e}")
            return False






