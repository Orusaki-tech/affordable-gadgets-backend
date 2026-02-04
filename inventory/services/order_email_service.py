"""
Order-related email helpers (order confirmation, updates).
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage

from inventory.models import Order

logger = logging.getLogger(__name__)


class OrderEmailService:
    @staticmethod
    def send_order_confirmation_email(order: Order) -> bool:
        """Send order confirmation email to the customer."""
        try:
            customer = order.customer
            customer_email = customer.email or (
                customer.user.email if customer.user and hasattr(customer.user, "email") else None
            )
            if not customer_email:
                logger.warning("No email found for order %s; skipping confirmation.", order.order_id)
                return False

            customer_name = customer.name or (
                customer.user.get_full_name() if customer.user else "Customer"
            )

            items = order.order_items.select_related(
                "inventory_unit__product_template", "bundle"
            ).all()
            item_lines = []
            for item in items:
                product_name = "Item"
                if item.inventory_unit and item.inventory_unit.product_template:
                    product_name = item.inventory_unit.product_template.product_name
                if item.bundle and item.bundle.title:
                    product_name = f"{product_name} (Bundle: {item.bundle.title})"
                item_lines.append(
                    f"- {product_name} x{item.quantity} @ Ksh {item.unit_price_at_purchase:,.2f}"
                )

            items_text = "\n".join(item_lines) if item_lines else "Items will be listed on your receipt."

            subject = f"Order Confirmation {order.order_id} - Affordable Gadgets"
            message = (
                f"Dear {customer_name},\n\n"
                "Thank you for your order! We have received it and will process it shortly.\n\n"
                f"Order ID: {order.order_id}\n"
                f"Status: {order.status}\n"
                "Items:\n"
                f"{items_text}\n\n"
                f"Total Amount: Ksh {order.total_amount:,.2f}\n\n"
                "If you have any questions, please contact us at +254717881573.\n\n"
                "Best regards,\n"
                "Affordable Gadgets Team\n"
            )

            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[customer_email],
            )
            email.send()
            return True
        except Exception:
            logger.exception("Failed to send order confirmation for %s", order.order_id)
            return False
