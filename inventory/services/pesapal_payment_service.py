"""
Pesapal payment service with comprehensive error handling and failover.
Manages order submission, IPN handling, and payment status tracking.
"""
import logging
import json
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from decimal import Decimal
from typing import Dict, Optional
from inventory.models import Order, PesapalPayment, PesapalRefund, PaymentNotification
from inventory.services.pesapal_service import PesapalService

logger = logging.getLogger(__name__)

class PesapalPaymentService:
    """Service to manage Pesapal payment operations with failover support."""
    
    def __init__(self):
        print(f"[PESAPAL] Initializing PesapalPaymentService...")
        self.pesapal_service = PesapalService()
        self.payment_expiry_hours = 24
        print(f"[PESAPAL] PesapalPaymentService initialized")
    
    @transaction.atomic
    def initiate_payment(
        self,
        order: Order,
        callback_url: str,
        cancellation_url: Optional[str] = None,
        customer: Optional[Dict] = None,
        billing_address: Optional[Dict] = None
    ) -> Dict:
        """Initiate Pesapal payment for an order."""
        print(f"\n[PESAPAL] ========== INITIATE PAYMENT START ==========")
        print(f"[PESAPAL] Order ID: {order.order_id}")
        print(f"[PESAPAL] Order Amount: {order.total_amount}")
        print(f"[PESAPAL] Order Status: {order.status}")
        print(f"[PESAPAL] Callback URL: {callback_url}")
        print(f"[PESAPAL] Cancellation URL: {cancellation_url}")
        print(f"[PESAPAL] Customer: {json.dumps(customer, indent=2) if customer else 'None'}")
        
        try:
            existing_payment = PesapalPayment.objects.filter(
                order=order,
                pesapal_order_tracking_id__isnull=False
            ).order_by('-initiated_at').first()
            
            if existing_payment and existing_payment.status not in [
                PesapalPayment.StatusChoices.FAILED,
                PesapalPayment.StatusChoices.CANCELLED,
                PesapalPayment.StatusChoices.EXPIRED
            ]:
                if existing_payment.redirect_url:
                    print(f"[PESAPAL] Found existing payment - returning it")
                    print(f"[PESAPAL] Existing Tracking ID: {existing_payment.pesapal_order_tracking_id}")
                    print(f"[PESAPAL] Existing Status: {existing_payment.status}")
                    logger.info(f"Returning existing payment for order {order.order_id}")
                    return {
                        'success': True,
                        'redirect_url': existing_payment.redirect_url,
                        'order_tracking_id': existing_payment.pesapal_order_tracking_id,
                        'payment_id': str(existing_payment.id)
                    }
            
            ipn_url = getattr(settings, 'PESAPAL_IPN_URL', '')
            if not ipn_url:
                print(f"[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR: PESAPAL_IPN_URL not configured")
                print(f"[PESAPAL] ============================================\n")
                return {'success': False, 'error': 'PESAPAL_IPN_URL not configured in settings'}
            
            print(f"[PESAPAL] IPN URL: {ipn_url}")
            
            if not customer and order.customer:
                customer = {}
                if order.customer.email:
                    customer['email'] = order.customer.email
                if order.customer.phone:
                    customer['phone_number'] = order.customer.phone
                if order.customer.name:
                    name_parts = order.customer.name.split(' ', 1)
                    customer['first_name'] = name_parts[0] if len(name_parts) > 0 else ''
                    customer['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
                print(f"[PESAPAL] Built customer data from order: {json.dumps(customer, indent=2)}")
            
            items = []
            for order_item in order.order_items.all():
                item = {
                    "id": str(order_item.inventory_unit.id) if order_item.inventory_unit else str(order_item.id),
                    "name": order_item.inventory_unit.product_template.product_name if order_item.inventory_unit else "Item",
                    "quantity": order_item.quantity,
                    "unit_price": str(order_item.unit_price_at_purchase)
                }
                items.append(item)
            
            print(f"[PESAPAL] Order Items: {json.dumps(items, indent=2)}")
            
            # Get notification_id and IPN URL
            notification_id = getattr(settings, 'PESAPAL_NOTIFICATION_ID', '').strip()
            ipn_url = getattr(settings, 'PESAPAL_IPN_URL', '').strip()
            
            print(f"[PESAPAL] Notification ID from settings: '{notification_id}' (length: {len(notification_id)})")
            print(f"[PESAPAL] IPN URL from settings: '{ipn_url}'")
            
            # If notification_id is empty but IPN URL is set, try to register it and get notification_id
            if not notification_id and ipn_url:
                print(f"[PESAPAL] No notification_id but IPN URL is set - attempting to register IPN URL...")
                registered_id, reg_error = self.pesapal_service.register_ipn_url(ipn_url, 'GET')
                if registered_id:
                    notification_id = registered_id
                    print(f"[PESAPAL] Successfully registered IPN URL, got notification_id: {notification_id}")
                    print(f"[PESAPAL] NOTE: You should add this to your .env: PESAPAL_NOTIFICATION_ID=\"{notification_id}\"")
                else:
                    print(f"[PESAPAL] WARNING: Failed to register IPN URL: {reg_error}")
                    print(f"[PESAPAL] Will try using ipn_notification_url instead...")
            
            order_data = {
                "id": str(order.order_id),
                "currency": "KES",
                "amount": str(order.total_amount),
                "description": f"Order #{order.order_id}",
                "callback_url": callback_url,
                "cancellation_url": cancellation_url or callback_url,
                "billing_address": billing_address or {},
                "items": items
            }
            
            # Pesapal API v3: Use notification_id if available, otherwise use ipn_notification_url
            # DO NOT send empty notification_id - Pesapal rejects it
            if notification_id:
                order_data["notification_id"] = notification_id
                print(f"[PESAPAL] Including notification_id: {notification_id}")
            elif ipn_url:
                # Use ipn_notification_url when notification_id is not available
                order_data["ipn_notification_url"] = ipn_url
                print(f"[PESAPAL] Using ipn_notification_url (no notification_id): {ipn_url}")
            else:
                print(f"[PESAPAL] ERROR: Neither notification_id nor IPN URL configured")
                print(f"[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR: PESAPAL_NOTIFICATION_ID or PESAPAL_IPN_URL must be configured")
                print(f"[PESAPAL] ============================================\n")
                return {'success': False, 'error': 'PESAPAL_NOTIFICATION_ID or PESAPAL_IPN_URL must be configured in settings'}
            
            if customer:
                order_data["customer"] = customer
            
            print(f"[PESAPAL] Order Data to submit: {json.dumps(order_data, indent=2)}")
            print(f"[PESAPAL] Calling PesapalService.submit_order_request...")
            
            result, error = self.pesapal_service.submit_order_request(order_data)
            
            if error:
                print(f"[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR from PesapalService: {error}")
                print(f"[PESAPAL] ============================================\n")
                logger.error(f"Failed to submit order to Pesapal: {error}")
                return {'success': False, 'error': error}
            
            if not result:
                print(f"[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR: No response from Pesapal API")
                print(f"[PESAPAL] ============================================\n")
                return {'success': False, 'error': 'No response from Pesapal API'}
            
            print(f"[PESAPAL] Response from PesapalService: {json.dumps(result, indent=2)}")
            
            order_tracking_id = result.get('order_tracking_id')
            redirect_url = result.get('redirect_url')
            
            if not order_tracking_id or not redirect_url:
                print(f"[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR: Invalid response from Pesapal API")
                print(f"[PESAPAL] Missing order_tracking_id or redirect_url")
                print(f"[PESAPAL] ============================================\n")
                return {'success': False, 'error': 'Invalid response from Pesapal API'}
            
            print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
            print(f"[PESAPAL] Redirect URL: {redirect_url}")
            
            # Check if payment with this tracking ID already exists
            existing_payment_by_tracking = PesapalPayment.objects.filter(
                pesapal_order_tracking_id=order_tracking_id
            ).first()
            
            if existing_payment_by_tracking:
                print(f"[PESAPAL] Payment with tracking ID already exists, returning existing")
                logger.info(f"Payment with tracking ID {order_tracking_id} already exists, returning existing payment")
                return {
                    'success': True,
                    'redirect_url': existing_payment_by_tracking.redirect_url or redirect_url,
                    'order_tracking_id': order_tracking_id,
                    'payment_id': str(existing_payment_by_tracking.id)
                }
            
            try:
                print(f"[PESAPAL] Creating PesapalPayment record in database...")
                payment = PesapalPayment.objects.create(
                    order=order,
                    pesapal_order_tracking_id=order_tracking_id,
                    amount=order.total_amount,
                    currency='KES',
                    redirect_url=redirect_url,
                    callback_url=callback_url,
                    customer_email=customer.get('email') if customer else None,
                    customer_phone=customer.get('phone_number') if customer else None,
                    customer_name=order.customer.name if order.customer else None,
                    status=PesapalPayment.StatusChoices.PENDING,
                    api_request_data=order_data,
                    api_response_data=result,
                    expired_at=timezone.now() + timedelta(hours=self.payment_expiry_hours)
                )
                
                print(f"[PESAPAL] ========== INITIATE PAYMENT SUCCESS ==========")
                print(f"[PESAPAL] Payment record created - ID: {payment.id}")
                print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
                print(f"[PESAPAL] Redirect URL: {redirect_url}")
                print(f"[PESAPAL] =============================================\n")
                logger.info(f"Payment initiated for order {order.order_id}: {order_tracking_id}")
                
                return {
                    'success': True,
                    'redirect_url': redirect_url,
                    'order_tracking_id': order_tracking_id,
                    'payment_id': str(payment.id)
                }
                
            except Exception as e:
                # Handle IntegrityError (duplicate tracking ID) gracefully
                from django.db import IntegrityError
                if isinstance(e, IntegrityError) and 'pesapal_order_tracking_id' in str(e):
                    print(f"[PESAPAL] WARNING: Payment with tracking ID already exists (race condition)")
                    print(f"[PESAPAL] Error: {str(e)}")
                    logger.warning(f"Payment with tracking ID {order_tracking_id} already exists (race condition)")
                    # Try to get the existing payment
                    existing = PesapalPayment.objects.filter(
                        pesapal_order_tracking_id=order_tracking_id
                    ).first()
                    if existing:
                        print(f"[PESAPAL] Found existing payment, returning it")
                        return {
                            'success': True,
                            'redirect_url': existing.redirect_url or redirect_url,
                            'order_tracking_id': order_tracking_id,
                            'payment_id': str(existing.id)
                        }
                
                print(f"[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR creating payment record: {str(e)}")
                print(f"[PESAPAL] ============================================\n")
                logger.error(f"Error creating payment record: {str(e)}")
                return {'success': False, 'error': f'Failed to create payment record: {str(e)}'}
                
        except Exception as e:
            print(f"[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
            print(f"[PESAPAL] UNEXPECTED ERROR: {str(e)}")
            import traceback
            print(f"[PESAPAL] Traceback:\n{traceback.format_exc()}")
            print(f"[PESAPAL] ============================================\n")
            logger.error(f"Unexpected error initiating payment: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
    
    @transaction.atomic
    def handle_ipn(
        self,
        order_tracking_id: str,
        order_notification_type: Optional[str] = None,
        order_merchant_reference: Optional[str] = None,
        payment_status_description: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_account: Optional[str] = None,
        ipn_data: Optional[Dict] = None
    ) -> Dict:
        """Handle IPN callback from Pesapal."""
        print(f"\n[PESAPAL] ========== HANDLE IPN START ==========")
        print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
        print(f"[PESAPAL] Notification Type: {order_notification_type}")
        print(f"[PESAPAL] Payment Status: {payment_status_description}")
        print(f"[PESAPAL] Payment Method: {payment_method}")
        print(f"[PESAPAL] IPN Data: {json.dumps(ipn_data, indent=2) if ipn_data else 'None'}")
        
        try:
            payment = PesapalPayment.objects.filter(
                pesapal_order_tracking_id=order_tracking_id
            ).first()
            
            if not payment:
                print(f"[PESAPAL] ========== HANDLE IPN FAILED ==========")
                print(f"[PESAPAL] ERROR: Payment not found for order_tracking_id: {order_tracking_id}")
                print(f"[PESAPAL] =======================================\n")
                logger.warning(f"IPN received for unknown order_tracking_id: {order_tracking_id}")
                return {'success': False, 'message': f'Payment not found for order_tracking_id: {order_tracking_id}'}
            
            print(f"[PESAPAL] Found payment record - ID: {payment.id}, Order: {payment.order.order_id}")
            print(f"[PESAPAL] Current payment status: {payment.status}")
            
            payment.ipn_data = ipn_data or {}
            payment.ipn_received = True
            payment.ipn_received_at = timezone.now()
            
            status_mapping = {
                'COMPLETED': PesapalPayment.StatusChoices.COMPLETED,
                'FAILED': PesapalPayment.StatusChoices.FAILED,
                'INVALID': PesapalPayment.StatusChoices.FAILED,
            }
            
            if payment_status_description:
                payment_status_upper = payment_status_description.upper()
                print(f"[PESAPAL] Processing payment status: {payment_status_upper}")
                if payment_status_upper in status_mapping:
                    # SECURITY: Don't mark as completed from IPN alone - wait for status verification
                    # Status verification will validate the amount before marking as paid
                    if payment_status_upper == 'COMPLETED':
                        print(f"[PESAPAL] IPN reports COMPLETED - will verify with Pesapal API (including amount validation)")
                        # Don't mark as paid yet - wait for API verification with amount check below
                    else:
                        payment.status = status_mapping[payment_status_upper]
                        print(f"[PESAPAL] Updated payment status to: {payment.status}")
            
            if payment_method:
                payment.payment_method = payment_method
                print(f"[PESAPAL] Payment method set to: {payment_method}")
            
            print(f"[PESAPAL] Calling get_transaction_status to verify...")
            status_result, status_error = self.pesapal_service.get_transaction_status(order_tracking_id)
            if status_result and not status_error:
                print(f"[PESAPAL] Status verification response: {json.dumps(status_result, indent=2)}")
                payment.api_response_data = status_result
                
                # SECURITY FIX: Validate payment amount matches order amount before marking as paid
                pesapal_amount_str = status_result.get('amount')
                amount_validated = False
                if pesapal_amount_str:
                    try:
                        pesapal_amount = Decimal(str(pesapal_amount_str))
                        order_amount = payment.order.total_amount
                        # Allow small rounding differences (0.01 KES)
                        amount_diff = abs(pesapal_amount - order_amount)
                        if amount_diff > Decimal('0.01'):
                            error_msg = (
                                f"SECURITY ALERT: Amount mismatch for order {payment.order.order_id}. "
                                f"Order amount: {order_amount}, Pesapal amount: {pesapal_amount}, "
                                f"Difference: {amount_diff}"
                            )
                            print(f"[PESAPAL] ========== SECURITY: AMOUNT MISMATCH ==========")
                            print(f"[PESAPAL] {error_msg}")
                            print(f"[PESAPAL] ============================================\n")
                            logger.error(error_msg)
                            # Don't mark as paid if amounts don't match
                            payment.status = PesapalPayment.StatusChoices.FAILED
                            payment.save()
                            return {
                                'success': False,
                                'message': 'Payment amount mismatch. Payment rejected for security.',
                                'error': 'Amount validation failed'
                            }
                        amount_validated = True
                        print(f"[PESAPAL] ✓ Amount validation passed: {pesapal_amount} == {order_amount}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not validate amount from Pesapal response: {e}")
                        print(f"[PESAPAL] WARNING: Could not parse amount from Pesapal: {e}")
                        # If we can't validate amount, be cautious but don't fail completely
                        # Log the warning and continue (Pesapal should always send amount)
                
                payment_status = status_result.get('payment_status_description', '').upper()
                if payment_status in status_mapping:
                    payment.status = status_mapping[payment_status]
                    print(f"[PESAPAL] Updated payment status from verification: {payment.status}")
                    if payment.status == PesapalPayment.StatusChoices.COMPLETED:
                        # Double-check amount before marking as paid (if not already validated above)
                        if not amount_validated:
                            pesapal_amount_str = status_result.get('amount')
                            if pesapal_amount_str:
                                try:
                                    pesapal_amount = Decimal(str(pesapal_amount_str))
                                    if abs(pesapal_amount - payment.order.total_amount) > Decimal('0.01'):
                                        error_msg = f"SECURITY ALERT: Final amount check failed for order {payment.order.order_id}"
                                        logger.error(error_msg)
                                        payment.status = PesapalPayment.StatusChoices.FAILED
                                        payment.save()
                                        return {
                                            'success': False,
                                            'message': 'Payment amount validation failed',
                                            'error': 'Amount mismatch'
                                        }
                                except (ValueError, TypeError):
                                    # If we can't parse amount, log warning but proceed
                                    # (Pesapal should always send valid amount)
                                    logger.warning(f"Could not validate amount in final check")
                        
                        # All validations passed - mark as paid
                        payment.completed_at = timezone.now()
                        payment.is_verified = True
                        payment.verified_at = timezone.now()
                        payment.order.status = Order.StatusChoices.PAID
                        payment.order.save()
                        print(f"[PESAPAL] ✓ Payment verified as completed - Order marked as PAID")
                        logger.info(f"Payment completed and verified for order {payment.order.order_id}")
                        
                        # Generate and send receipt automatically (email + WhatsApp)
                        try:
                            from inventory.services.receipt_service import ReceiptService
                            receipt, email_sent, whatsapp_sent = ReceiptService.generate_and_send_receipt(payment.order)
                            print(f"[PESAPAL] Receipt generated: {receipt.receipt_number}, Email sent: {email_sent}, WhatsApp sent: {whatsapp_sent}")
                        except Exception as e:
                            logger.error(f"Failed to generate receipt for order {payment.order.order_id}: {e}")
                            print(f"[PESAPAL] WARNING: Receipt generation failed: {e}")
                            # Don't fail payment confirmation if receipt generation fails
            elif status_error:
                print(f"[PESAPAL] WARNING: Status verification failed: {status_error}")
            
            payment.save()
            
            print(f"[PESAPAL] ========== HANDLE IPN SUCCESS ==========")
            print(f"[PESAPAL] Final payment status: {payment.status}")
            print(f"[PESAPAL] Order status: {payment.order.status}")
            print(f"[PESAPAL] ========================================\n")
            logger.info(f"IPN processed for order {payment.order.order_id}: {payment.status}")
            
            return {'success': True, 'message': 'IPN processed successfully'}
            
        except Exception as e:
            print(f"[PESAPAL] ========== HANDLE IPN FAILED ==========")
            print(f"[PESAPAL] ERROR: {str(e)}")
            import traceback
            print(f"[PESAPAL] Traceback:\n{traceback.format_exc()}")
            print(f"[PESAPAL] ========================================\n")
            logger.error(f"Error handling IPN: {str(e)}", exc_info=True)
            return {'success': False, 'message': f'Error processing IPN: {str(e)}'}
    
    def get_payment_status(self, order: Order) -> Dict:
        """Get current payment status for an order. Queries Pesapal API if status is PENDING."""
        print(f"\n[PESAPAL] ========== GET PAYMENT STATUS START ==========")
        print(f"[PESAPAL] Order ID: {order.order_id}")
        
        payment = PesapalPayment.objects.filter(order=order).order_by('-initiated_at').first()
        
        if not payment:
            print(f"[PESAPAL] No payment found for this order")
            print(f"[PESAPAL] ===========================================\n")
            return {'status': 'NO_PAYMENT', 'message': 'No payment initiated for this order'}
        
        print(f"[PESAPAL] Payment found - ID: {payment.id}")
        print(f"[PESAPAL] Payment Status: {payment.status}")
        print(f"[PESAPAL] Order Tracking ID: {payment.pesapal_order_tracking_id}")
        print(f"[PESAPAL] Amount: {payment.amount}")
        print(f"[PESAPAL] IPN Received: {payment.ipn_received}")
        
        # If status is PENDING and we have a tracking ID, query Pesapal API for real-time status
        if payment.status == PesapalPayment.StatusChoices.PENDING and payment.pesapal_order_tracking_id:
            print(f"[PESAPAL] Status is PENDING - querying Pesapal API for real-time status...")
            try:
                result, error = self.pesapal_service.get_transaction_status(payment.pesapal_order_tracking_id)
                
                if error:
                    print(f"[PESAPAL] Error querying Pesapal API: {error}")
                    print(f"[PESAPAL] Returning local status: {payment.status}")
                elif result:
                    print(f"[PESAPAL] Pesapal API Response: {json.dumps(result, indent=2, default=str)}")
                    
                    # Map Pesapal status to our status (same mapping as IPN handler)
                    pesapal_status = result.get('payment_status_description', '').upper()
                    pesapal_payment_method = result.get('payment_method', '')
                    pesapal_payment_id = result.get('payment_id')
                    pesapal_reference = result.get('payment_reference')
                    
                    status_mapping = {
                        'COMPLETED': PesapalPayment.StatusChoices.COMPLETED,
                        'FAILED': PesapalPayment.StatusChoices.FAILED,
                        'INVALID': PesapalPayment.StatusChoices.FAILED,
                        'CANCELLED': PesapalPayment.StatusChoices.CANCELLED,
                    }
                    
                    # Update payment record if status has changed
                    status_changed = False
                    if pesapal_status in status_mapping:
                        new_status = status_mapping[pesapal_status]
                        if payment.status != new_status:
                            payment.status = new_status
                            if new_status == PesapalPayment.StatusChoices.COMPLETED:
                                payment.completed_at = timezone.now()
                            status_changed = True
                            print(f"[PESAPAL] Status updated to {new_status} based on Pesapal API")
                    
                    # Update payment method and IDs if available
                    if pesapal_payment_method and not payment.payment_method:
                        # Map Pesapal payment method to our choices
                        method_upper = pesapal_payment_method.upper()
                        method_map = {
                            'MPESA': PesapalPayment.PaymentMethodChoices.MPESA,
                            'M-PESA': PesapalPayment.PaymentMethodChoices.MPESA,
                            'VISA': PesapalPayment.PaymentMethodChoices.VISA,
                            'MASTERCARD': PesapalPayment.PaymentMethodChoices.MASTERCARD,
                            'AMEX': PesapalPayment.PaymentMethodChoices.AMEX,
                            'AMERICAN EXPRESS': PesapalPayment.PaymentMethodChoices.AMEX,
                            'MOBILE MONEY': PesapalPayment.PaymentMethodChoices.MOBILE_MONEY,
                            'BANK': PesapalPayment.PaymentMethodChoices.BANK,
                        }
                        payment.payment_method = method_map.get(method_upper, PesapalPayment.PaymentMethodChoices.UNKNOWN)
                        print(f"[PESAPAL] Payment method updated to: {payment.payment_method}")
                    
                    if pesapal_payment_id and not payment.pesapal_payment_id:
                        payment.pesapal_payment_id = pesapal_payment_id
                    
                    if pesapal_reference and not payment.pesapal_reference:
                        payment.pesapal_reference = pesapal_reference
                    
                    # Update API response data
                    payment.api_response_data = result
                    
                    if status_changed:
                        payment.save()
                        print(f"[PESAPAL] Payment record updated in database")
            except Exception as e:
                print(f"[PESAPAL] Exception querying Pesapal API: {str(e)}")
                import traceback
                print(f"[PESAPAL] Traceback: {traceback.format_exc()}")
                # Continue with local status if API query fails
        
        # Refresh payment from database in case it was updated
        payment.refresh_from_db()
        
        print(f"[PESAPAL] Final Payment Status: {payment.status}")
        print(f"[PESAPAL] ===========================================\n")
        
        return {
            'status': payment.status,
            'order_tracking_id': payment.pesapal_order_tracking_id,
            'payment_id': payment.pesapal_payment_id,
            'payment_reference': payment.pesapal_reference,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'payment_method': payment.payment_method,
            'redirect_url': payment.redirect_url,
            'initiated_at': payment.initiated_at,
            'completed_at': payment.completed_at,
            'is_verified': payment.is_verified,
            'ipn_received': payment.ipn_received,
        }




