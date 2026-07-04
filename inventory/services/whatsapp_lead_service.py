import logging

from django.conf import settings
from django.core.mail import send_mail

from inventory.models import Customer, Product, WhatsAppClickEvent

logger = logging.getLogger(__name__)


def _notification_recipient() -> str | None:
    recipient = (
        getattr(settings, "SHOP_LEAD_NOTIFICATION_EMAIL", None)
        or getattr(settings, "WHATSAPP_LEAD_NOTIFICATION_EMAIL", None)
        or settings.DEFAULT_FROM_EMAIL
    )
    return recipient or None


def _send_shop_lead_email(subject: str, message: str) -> bool:
    recipient = _notification_recipient()
    if not recipient:
        logger.warning(
            "SHOP_LEAD_NOTIFICATION_EMAIL / WHATSAPP_LEAD_NOTIFICATION_EMAIL / "
            "DEFAULT_FROM_EMAIL are empty — cannot send notification"
        )
        return False

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        recipient_list=[recipient],
        fail_silently=False,
    )
    return True


def _product_admin_context(product_id: int | None) -> tuple[str, str]:
    if not product_id:
        return "Unknown", ""
    product = Product.objects.filter(id=product_id).only("product_name", "slug").first()
    if not product:
        return "Unknown", ""
    product_name = product.product_name or "Unknown"
    product_url = (
        f"https://api.affordable-gadgetske.com/admin/inventory/product/{product_id}/change/"
    )
    return product_name, product_url


def sync_customer_phone_from_cart(cart) -> None:
    """Persist cart phone onto the linked customer profile when missing."""
    phone = (cart.customer_phone or "").strip()
    if not phone or not cart.customer_id:
        return
    customer = Customer.objects.filter(pk=cart.customer_id).first()
    if customer and not (customer.phone or "").strip():
        customer.phone = phone
        customer.save(update_fields=["phone"])


def sync_customer_phone_for_user(user, phone: str) -> None:
    if not user or not (phone or "").strip():
        return
    customer = Customer.objects.filter(user_id=user.id).first()
    if customer and not (customer.phone or "").strip():
        customer.phone = phone.strip()
        customer.save(update_fields=["phone"])


def resolve_cart_contact(cart) -> tuple[str, str]:
    phone = (cart.customer_phone or "").strip()
    email = (cart.customer_email or "").strip()
    if not cart.customer_id:
        return phone, email

    customer = Customer.objects.filter(pk=cart.customer_id).select_related("user").first()
    if not customer:
        return phone, email

    if not phone:
        phone = (customer.phone or "").strip()
    if not email:
        email = (customer.email or "").strip()
    if not email and customer.user_id:
        email = (customer.user.email or "").strip()
    return phone, email


def notify_cart_add(*, cart, product, quantity: int, inventory_unit_id: int | None = None) -> None:
    """Email the shop when a signed-in user adds an item to cart (phone required)."""
    try:
        cart.refresh_from_db(fields=["customer_phone", "customer_email", "customer_id"])
        sync_customer_phone_from_cart(cart)
        phone, email = resolve_cart_contact(cart)
        if not phone:
            logger.info("Skipping cart-add notification for cart %s — no phone", cart.id)
            return

        product_name = getattr(product, "product_name", None) or "Unknown"
        product_url = ""
        if getattr(product, "id", None):
            _, product_url = _product_admin_context(product.id)

        subject = f"New Cart Add — {product_name}"
        message = (
            f"A user added a product to their cart.\n\n"
            f"Phone: {phone}\n"
            f"Email: {email or 'Not provided'}\n"
            f"Product: {product_name}\n"
            f"Quantity: {quantity}\n"
            f"Cart ID: {cart.id}\n"
        )
        if inventory_unit_id:
            message += f"Inventory unit ID: {inventory_unit_id}\n"
        if product_url:
            message += f"Admin link: {product_url}\n"

        if _send_shop_lead_email(subject, message):
            logger.info(
                "Cart-add notification sent for phone %s (product %s, cart %s)",
                phone,
                product_name,
                cart.id,
            )
    except Exception:
        logger.exception("Failed to send cart-add notification for cart %s", cart.id)


def notify_whatsapp_lead(event: WhatsAppClickEvent) -> None:
    """Email the shop when a user submits the WhatsApp lead form."""
    if not (event.phone or "").strip():
        return
    try:
        if event.email:
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.filter(email__iexact=event.email).first()
            if user:
                sync_customer_phone_for_user(user, event.phone)

        product_name, product_url = _product_admin_context(event.product_id)
        subject = f"New WhatsApp Lead — {product_name}"
        message = (
            f"A user is interested in a product via WhatsApp.\n\n"
            f"Phone: {event.phone}\n"
            f"Product: {product_name}\n"
            f"Email: {event.email or 'Not provided'}\n"
            f"Time: {event.clicked_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        if product_url:
            message += f"Admin link: {product_url}\n"

        if _send_shop_lead_email(subject, message):
            logger.info(
                "WhatsApp lead notification sent for phone %s (product %s)",
                event.phone,
                product_name,
            )
    except Exception:
        logger.exception("Failed to send WhatsApp lead notification")
