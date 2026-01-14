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
    def get_receipt_context(order: Order) -> dict:
        """Prepare context data for receipt template."""
        # Get order items with all related data
        order_items = order.order_items.select_related(
            'inventory_unit__product_template',
            'inventory_unit__product_color'
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
        
        # Get payment method from Pesapal payment if available
        payment_method = 'MPESA'  # Default
        payment_methods_checked = []
        try:
            pesapal_payment = order.pesapal_payments.filter(status='COMPLETED').first()
            if pesapal_payment and pesapal_payment.payment_method:
                payment_method = pesapal_payment.payment_method.upper()
                # Map payment method to checkboxes
                if 'MPESA' in payment_method or 'M-PESA' in payment_method:
                    payment_methods_checked.append('mpesa')
                elif 'BANK' in payment_method:
                    payment_methods_checked.append('bank')
                else:
                    payment_methods_checked.append('cash')
        except Exception as e:
            logger.warning(f"Could not determine payment method: {e}")
            payment_methods_checked.append('mpesa')  # Default to MPESA
        
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
            
            # #region agent log
            logger.info(f"DEBUG[PDF] Starting PDF generation for order {order.order_id}")
            # #endregion
            
            # Try method 1: Standard write_pdf with font_config
            try:
                # #region agent log
                logger.info(f"DEBUG[PDF] Attempting standard write_pdf with font_config")
                # #endregion
                pdf_bytes = html_doc.write_pdf(font_config=font_config)
                # #region agent log
                logger.info(f"DEBUG[PDF] PDF generated successfully using standard method, size={len(pdf_bytes)} bytes")
                # #endregion
                return pdf_bytes
            except (AttributeError, TypeError) as e:
                # #region agent log
                logger.warning(f"DEBUG[PDF] Standard method failed: {e}, trying without font_config")
                # #endregion
                # Try method 2: Without font_config (fallback)
                try:
                    pdf_bytes = html_doc.write_pdf()
                    # #region agent log
                    logger.info(f"DEBUG[PDF] PDF generated successfully without font_config, size={len(pdf_bytes)} bytes")
                    # #endregion
                    return pdf_bytes
                except Exception as e2:
                    # #region agent log
                    logger.warning(f"DEBUG[PDF] Method without font_config also failed: {e2}, trying with BytesIO")
                    # #endregion
                    # Try method 3: Using BytesIO buffer
                    from io import BytesIO
                    buffer = BytesIO()
                    html_doc.write_pdf(buffer, font_config=font_config)
                    pdf_bytes = buffer.getvalue()
                    buffer.close()
                    # #region agent log
                    logger.info(f"DEBUG[PDF] PDF generated successfully using BytesIO, size={len(pdf_bytes)} bytes")
                    # #endregion
                    return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error generating receipt PDF for order {order.order_id}: {e}", exc_info=True)
            # #region agent log
            logger.error(f"DEBUG[PDF] All PDF generation methods failed for order {order.order_id}")
            # #endregion
            raise
    
    @staticmethod
    def create_and_save_receipt(order: Order) -> Receipt:
        """Create receipt record and save PDF file."""
        try:
            # Generate HTML
            html_content = ReceiptService.generate_receipt_html(order)
            
            # Generate PDF
            pdf_bytes = ReceiptService.generate_receipt_pdf(order, html_content)
            
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
            
            # Save PDF file
            if not receipt.pdf_file or (receipt.pdf_file and not os.path.exists(receipt.pdf_file.path)):
                receipt.pdf_file.save(pdf_path, 
                    ContentFile(pdf_bytes), 
                    save=True
                )
            
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
            
            # Generate PDF if not exists
            if not receipt.pdf_file or (receipt.pdf_file and not os.path.exists(receipt.pdf_file.path)):
                pdf_bytes = ReceiptService.generate_receipt_pdf(order)
                pdf_filename = f"receipt_{order.order_id}_{receipt.receipt_number}.pdf"
                pdf_path = os.path.join('receipts', timezone.now().strftime('%Y/%m'), pdf_filename)
                receipt.pdf_file.save(pdf_path, ContentFile(pdf_bytes), save=True)
            
            # Prepare email
            customer_name = customer.name or 'Customer'
            subject = f"Receipt for Order {receipt.receipt_number} - Affordable Gadgets"
            message = f"""Dear {customer_name},

Thank you for your purchase! Please find your receipt attached.

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
            
            # Attach PDF
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
            
            # Send WhatsApp message
            whatsapp_sent = WhatsAppService.send_receipt_whatsapp(
                phone_number=customer_phone,
                receipt_number=receipt.receipt_number,
                order_id=str(order.order_id),
                total_amount=float(order.total_amount),
                customer_name=customer_name
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
            receipt = ReceiptService.create_and_save_receipt(order)
            
            # Send email
            email_sent = ReceiptService.send_receipt_email(order, receipt)
            
            # Send WhatsApp
            whatsapp_sent = ReceiptService.send_receipt_whatsapp(order, receipt)
            
            return receipt, email_sent, whatsapp_sent
            
        except Exception as e:
            logger.error(f"Error in generate_and_send_receipt for order {order.order_id}: {e}", exc_info=True)
            raise
