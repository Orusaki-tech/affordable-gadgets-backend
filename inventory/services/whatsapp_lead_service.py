import logging
from django.conf import settings
from django.core.mail import send_mail
from inventory.models import WhatsAppClickEvent, Product

logger = logging.getLogger(__name__)


def notify_whatsapp_lead(event: WhatsAppClickEvent) -> None:
    if not event.phone:
        return
    try:
        product_name = "Unknown"
        product_url = ""
        if event.product_id:
            product = Product.objects.filter(id=event.product_id).only("product_name", "slug").first()
            if product:
                product_name = product.product_name or "Unknown"
                product_url = f"https://api.affordable-gadgetske.com/admin/inventory/product/{event.product_id}/change/"

        subject = f"New WhatsApp Lead — {product_name}"
        message = (
            f"A user is interested in a product via WhatsApp.\n\n"
            f"Phone: {event.phone}\n"
            f"Product: {product_name}\n"
            f"Email: {event.email or 'Not provided'}\n"
            f"Time: {event.clicked_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Admin link: {product_url}\n"
        )

        recipient = getattr(settings, "WHATSAPP_LEAD_NOTIFICATION_EMAIL", None) or settings.DEFAULT_FROM_EMAIL
        if not recipient:
            logger.warning("WHATSAPP_LEAD_NOTIFICATION_EMAIL and DEFAULT_FROM_EMAIL are empty — cannot send notification")
            return

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info("WhatsApp lead notification sent for phone %s (product %s)", event.phone, product_name)
    except Exception:
        logger.exception("Failed to send WhatsApp lead notification")
