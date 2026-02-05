"""
Clean receipt generation service using custom template.
Handles PDF generation, receipt storage, and email delivery.
"""
import os
import logging
from decimal import Decimal
from typing import Optional, Tuple
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration
from num2words import num2words
from inventory.models import Order, Receipt

logger = logging.getLogger(__name__)


class ReceiptService:
    """Service for generating and managing receipts using custom template."""
    
    @staticmethod
    def number_to_words(amount: Decimal) -> str:
        """Convert number to words (Kenyan Shillings)."""
        try:
            shillings = int(amount)
            cents = int((amount - shillings) * 100)
            words = num2words(shillings, lang='en').title()
            result = f"{words} Kenya Shillings"
            if cents > 0:
                cents_words = num2words(cents, lang='en').title()
                result += f" And {cents_words} Cents"
            return result
        except Exception as e:
            logger.error(f"Error converting number to words: {e}")
            return "Amount in words unavailable"
    
    @staticmethod
    def generate_receipt_number(order: Order) -> str:
        """Generate unique receipt number from order ID."""
        order_id_str = str(order.order_id).replace('-', '')[:8].upper()
        base_number = f"SL_{order_id_str}"
        
        # Check if receipt number already exists, if so add counter
        if Receipt.objects.filter(receipt_number=base_number).exists():
            counter = 1
            while Receipt.objects.filter(receipt_number=f"{base_number}_{counter}").exists():
                counter += 1
            return f"{base_number}_{counter}"
        
        return base_number

    @staticmethod
    def get_receipt_url(order: Order, format_type: str = 'pdf') -> str:
        base_url = getattr(settings, 'BACKEND_PUBLIC_URL', None) or 'https://affordable-gadgets-backend.onrender.com'
        base_url = base_url.rstrip('/')
        return f"{base_url}/api/inventory/orders/{order.order_id}/receipt/?format={format_type}"
    
    @staticmethod
    def get_receipt_context(order: Order) -> dict:
        """Prepare context data for receipt template."""
        # Get order items with all related data
        order_items = order.order_items.select_related(
            'inventory_unit__product_template',
            'inventory_unit__product_color',
            'bundle'
        ).all()
        
        # Get customer details
        customer = order.customer
        customer_name = customer.name or (customer.user.username if customer.user else 'Unknown')
        customer_phone = customer.phone or getattr(customer, 'phone_number', '') or ''
        customer_email = customer.email or (customer.user.email if customer.user and hasattr(customer.user, 'email') else '')
        
        # Get served by (staff member who created order)
        served_by = 'System'
        if order.user:
            served_by = order.user.get_full_name() or order.user.username
        
        # Get payment method from Pesapal payment if available, otherwise default to CASH
        payment_method = 'CASH'
        payment_methods_checked = ['cash']
        try:
            pesapal_payment = order.pesapal_payments.filter(status='COMPLETED').first()
            if pesapal_payment and pesapal_payment.payment_method:
                raw_method = pesapal_payment.payment_method.upper()
                payment_method = raw_method
                mapped_methods = set()
                if any(token in raw_method for token in ['MPESA', 'M-PESA', 'MOBILE_MONEY', 'MOBILE MONEY']):
                    mapped_methods.add('mpesa')
                if any(token in raw_method for token in ['BANK', 'VISA', 'MASTERCARD', 'AMEX', 'CARD', 'BANK_TRANSFER']):
                    mapped_methods.add('bank')
                if 'CASH' in raw_method:
                    mapped_methods.add('cash')
                if mapped_methods:
                    payment_methods_checked = sorted(mapped_methods)
                else:
                    # Default to bank for unknown card-like methods
                    payment_methods_checked = ['bank']
        except Exception as e:
            logger.warning(f"Could not determine payment method: {e}")
        
        # Build bundle groups (if any)
        bundle_groups = {}
        for item in order_items:
            if not item.bundle_group_id:
                continue
            group_key = str(item.bundle_group_id)
            if group_key not in bundle_groups:
                bundle_groups[group_key] = {
                    'bundle_title': item.bundle.title if item.bundle else 'Bundle',
                    'items': [],
                    'total': Decimal('0.00')
                }
            item_total = item.unit_price_at_purchase * item.quantity
            bundle_groups[group_key]['items'].append({
                'product_name': item.inventory_unit.product_template.product_name if item.inventory_unit else 'Item',
                'quantity': item.quantity,
                'unit_price': item.unit_price_at_purchase,
                'total': item_total
            })
            bundle_groups[group_key]['total'] += item_total

        bundle_summary = list(bundle_groups.values())

        # Get first order item (for single-item receipts)
        order_item = order_items.first()
        inventory_unit = order_item.inventory_unit if order_item else None
        
        # Format date for stamp (DD MON YYYY format)
        date_obj = order.created_at
        months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        stamp_date = f"{date_obj.day:02d} {months[date_obj.month - 1]}<br>{date_obj.year}"
        
        # Format date for input (YYYY-MM-DD)
        date_input = date_obj.strftime('%Y-%m-%d')
        
        # Format date for display (DD/MM/YYYY)
        date_display = date_obj.strftime('%d/%m/%Y')
        
        context = {
            'order': order,
            'order_item': order_item,
            'inventory_unit': inventory_unit,
            'receipt_number': ReceiptService.generate_receipt_number(order),
            'date': date_input,
            'date_display': date_display,
            'stamp_date': stamp_date,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'customer_email': customer_email,
            'amount_ksh': f"{order.total_amount:,.2f}".replace(',', ''),
            'amount_words': ReceiptService.number_to_words(order.total_amount),
            'item_description': inventory_unit.product_template.product_name if inventory_unit else '',
            'storage': f"{inventory_unit.storage_gb}GB" if inventory_unit and inventory_unit.storage_gb else '',
            'serial_no': inventory_unit.serial_number if inventory_unit else '',
            'imei': inventory_unit.imei if inventory_unit else '',
            'served_by': served_by,
            'payment_method': payment_method,
            'payment_methods_checked': payment_methods_checked,
            'phone_number': '+254717881573',  # Company phone
            'bundle_summary': bundle_summary,
        }
        
        return context
    
    @staticmethod
    def generate_receipt_html(order: Order) -> str:
        """Generate HTML receipt from custom template."""
        try:
            context = ReceiptService.get_receipt_context(order)
            html_content = render_to_string('receipts/affordable_gadgets_receipt.html', context)
            return html_content
        except Exception as e:
            logger.error(f"Error generating receipt HTML for order {order.order_id}: {e}", exc_info=True)
            raise
    
    @staticmethod
    def generate_receipt_pdf(order: Order, html_content: Optional[str] = None) -> bytes:
        """Generate PDF receipt from HTML."""
        try:
            if html_content is None:
                html_content = ReceiptService.generate_receipt_html(order)
            
            # Generate PDF using WeasyPrint
            # Try multiple approaches to handle compatibility issues
            font_config = FontConfiguration()
            html_doc = HTML(string=html_content)
            
            # Try method 1: Standard write_pdf with font_config
            try:
                pdf_bytes = html_doc.write_pdf(font_config=font_config)
                return pdf_bytes
            except (AttributeError, TypeError):
                # Try method 2: Without font_config (fallback)
                try:
                    pdf_bytes = html_doc.write_pdf()
                    return pdf_bytes
                except Exception:
                    # Try method 3: Using BytesIO buffer
                    from io import BytesIO
                    buffer = BytesIO()
                    html_doc.write_pdf(buffer, font_config=font_config)
                    pdf_bytes = buffer.getvalue()
                    buffer.close()
                    return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating receipt PDF for order {order.order_id}: {e}", exc_info=True)
            raise
    
    @staticmethod
    def create_and_save_receipt(order: Order, generate_pdf: bool = False) -> Receipt:
        """Create receipt record and optionally save PDF file."""
        try:
            # Generate HTML
            html_content = ReceiptService.generate_receipt_html(order)

            # Generate receipt number
            receipt_number = ReceiptService.generate_receipt_number(order)
            
            # Save PDF file
            pdf_filename = f"receipt_{order.order_id}_{receipt_number}.pdf"
            pdf_path = os.path.join('receipts', timezone.now().strftime('%Y/%m'), pdf_filename)
            
            # Create receipt record
            receipt, created = Receipt.objects.get_or_create(
                order=order,
                defaults={
                    'receipt_number': receipt_number,
                    'html_content': html_content,
                }
            )
            
            # Ensure receipt_number is set even if receipt already existed
            if not receipt.receipt_number:
                receipt.receipt_number = receipt_number
                receipt.save(update_fields=['receipt_number'])
            
            # Update html_content if it's missing
            if not receipt.html_content:
                receipt.html_content = html_content
                receipt.save(update_fields=['html_content'])
            
            # Save PDF file only if requested
            if generate_pdf:
                pdf_bytes = ReceiptService.generate_receipt_pdf(order, html_content)
                if not receipt.pdf_file or (receipt.pdf_file and not os.path.exists(receipt.pdf_file.path)):
                    receipt.pdf_file.save(pdf_path, ContentFile(pdf_bytes), save=True)
            
            logger.info(f"Receipt created for order {order.order_id}: {receipt_number}")
            return receipt
            
        except Exception as e:
            logger.error(f"Error creating receipt for order {order.order_id}: {e}", exc_info=True)
            raise
    
    @staticmethod
    def send_receipt_email(order: Order, receipt: Optional[Receipt] = None) -> bool:
        """Send receipt via email to customer."""
        try:
            if receipt is None:
                receipt, _ = Receipt.objects.get_or_create(order=order)
            
            # Ensure receipt has receipt_number
            if not receipt.receipt_number:
                receipt.receipt_number = ReceiptService.generate_receipt_number(order)
                receipt.save(update_fields=['receipt_number'])
            
            # Get customer email
            customer = order.customer
            customer_email = customer.email or (customer.user.email if customer.user and hasattr(customer.user, 'email') else None)
            
            if not customer_email:
                logger.warning(f"No email found for order {order.order_id}, cannot send receipt")
                return False
            
            receipt_url = ReceiptService.get_receipt_url(order, format_type='pdf')
            
            # Prepare email
            customer_name = customer.name or 'Customer'
            subject = f"Receipt for Order {receipt.receipt_number} - Affordable Gadgets"
            message = f"""Dear {customer_name},

Thank you for your purchase! Please find your receipt attached.
You can also download it here: {receipt_url}

Receipt Number: {receipt.receipt_number}
Order ID: {order.order_id}
Total Amount: Ksh {order.total_amount:,.2f}

If you have any questions, please contact us at +254717881573.

Best regards,
Affordable Gadgets Team
"""
            
            # Create email message
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[customer_email],
            )
            
            # Attach PDF if already generated
            if receipt.pdf_file and os.path.exists(receipt.pdf_file.path):
                email.attach_file(receipt.pdf_file.path)
            
            # Send email
            email.send()
            
            # Update receipt record
            receipt.email_sent = True
            receipt.email_sent_at = timezone.now()
            receipt.save()
            
            logger.info(f"Receipt email sent for order {order.order_id} to {customer_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending receipt email for order {order.order_id}: {e}", exc_info=True)
            return False
    
    @staticmethod
    def send_receipt_whatsapp(order: Order, receipt: Optional[Receipt] = None) -> bool:
        """Send receipt via WhatsApp to customer."""
        try:
            if receipt is None:
                receipt, _ = Receipt.objects.get_or_create(order=order)
            
            # Ensure receipt has receipt_number
            if not receipt.receipt_number:
                receipt.receipt_number = ReceiptService.generate_receipt_number(order)
                receipt.save(update_fields=['receipt_number'])
            
            # Get customer phone number
            customer = order.customer
            customer_phone = customer.phone or getattr(customer, 'phone_number', '') or ''
            
            # Try to get phone from source_lead for online orders
            if not customer_phone and hasattr(order, 'source_lead') and order.source_lead:
                customer_phone = getattr(order.source_lead, 'customer_phone', '') or ''
            
            if not customer_phone:
                logger.warning(f"No phone number found for order {order.order_id}, cannot send WhatsApp receipt")
                return False
            
            from inventory.services.whatsapp_service import WhatsAppService
            
            customer_name = customer.name or 'Customer'
            
            receipt_url = ReceiptService.get_receipt_url(order, format_type='pdf')
            # Send WhatsApp message
            whatsapp_sent = WhatsAppService.send_receipt_whatsapp(
                phone_number=customer_phone,
                receipt_number=receipt.receipt_number,
                order_id=str(order.order_id),
                total_amount=float(order.total_amount),
                customer_name=customer_name,
                pdf_url=receipt_url
            )
            
            if whatsapp_sent:
                # Update receipt record
                receipt.whatsapp_sent = True
                receipt.whatsapp_sent_at = timezone.now()
                receipt.save()
                logger.info(f"Receipt WhatsApp sent for order {order.order_id} to {customer_phone}")
            
            return whatsapp_sent
            
        except Exception as e:
            logger.error(f"Error sending receipt WhatsApp for order {order.order_id}: {e}", exc_info=True)
            return False

    @staticmethod
    def generate_and_send_receipt(order: Order) -> Tuple[Receipt, bool, bool]:
        """
        Generate receipt and send via email and WhatsApp.
        Returns (receipt, email_sent, whatsapp_sent).
        """
        try:
            # Create receipt
            receipt = ReceiptService.create_and_save_receipt(order, generate_pdf=False)
            
            # Send email only if not already sent
            email_sent = receipt.email_sent
            if not email_sent:
                email_sent = ReceiptService.send_receipt_email(order, receipt)
            
            # Send WhatsApp only if not already sent
            whatsapp_sent = receipt.whatsapp_sent
            if not whatsapp_sent:
                whatsapp_sent = ReceiptService.send_receipt_whatsapp(order, receipt)

            return receipt, email_sent, whatsapp_sent
            
        except Exception as e:
            logger.error(f"Error in generate_and_send_receipt for order {order.order_id}: {e}", exc_info=True)
            raise
