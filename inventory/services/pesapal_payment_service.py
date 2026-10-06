"""
Pesapal payment service with comprehensive error handling and failover.
Manages order submission, IPN handling, and payment status tracking.
"""

import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from inventory.models import (
    InventoryUnit,
    Order,
    PesapalPayment,
)
from inventory.services.pesapal_service import PesapalService

logger = logging.getLogger(__name__)


class PesapalPaymentService:
    """Service to manage Pesapal payment operations with failover support."""

    def __init__(self):
        print("[PESAPAL] Initializing PesapalPaymentService...")
        self.pesapal_service = PesapalService()
        self.payment_expiry_hours = 24
        print("[PESAPAL] PesapalPaymentService initialized")

    @staticmethod
    def resolve_effective_payment_mode(order: Order, payment_mode: str = "BOTH") -> str:
        """
        Narrow BOTH to the unpaid remainder so we never re-charge a settled leg.
        """
        mode = (payment_mode or "BOTH").strip().upper()
        if mode not in {"ITEMS_ONLY", "DELIVERY_ONLY", "BOTH"}:
            mode = "BOTH"
        if mode == "BOTH":
            if order.is_items_paid and not order.is_delivery_paid:
                return "DELIVERY_ONLY"
            if order.is_delivery_paid and not order.is_items_paid:
                return "ITEMS_ONLY"
        return mode

    @staticmethod
    def get_effective_order_total(order: Order, payment_mode: str = "BOTH") -> Decimal:
        """
        Compute remaining payable total for gateway submission based on payment_mode:
        - ITEMS_ONLY: unpaid order items (0 if items already paid)
        - DELIVERY_ONLY: unpaid delivery fee (0 if delivery already paid)
        - BOTH: sum of unpaid legs (auto-narrowed via resolve_effective_payment_mode)
        """
        items_total = sum((item.sub_total for item in order.order_items.all()), Decimal("0.00"))
        delivery_fee = order.delivery_fee or Decimal("0.00")
        items_due = Decimal("0.00") if order.is_items_paid else items_total
        delivery_due = Decimal("0.00") if order.is_delivery_paid else delivery_fee
        mode = PesapalPaymentService.resolve_effective_payment_mode(order, payment_mode)
        if mode == "ITEMS_ONLY":
            return items_due
        if mode == "DELIVERY_ONLY":
            return delivery_due
        return items_due + delivery_due

    @staticmethod
    def validate_pesapal_amount(payment: PesapalPayment, status_result: dict | None):
        """
        Fail closed: Pesapal status must include an amount matching payment.amount.

        Returns (ok, error_message). ok=False means do not mark the payment completed.
        """
        if not status_result:
            return False, "Missing Pesapal status payload for amount validation."

        pesapal_amount_str = status_result.get("amount")
        if pesapal_amount_str is None or str(pesapal_amount_str).strip() == "":
            return False, "Pesapal status response did not include a payment amount."

        try:
            pesapal_amount = Decimal(str(pesapal_amount_str))
        except (ValueError, TypeError, ArithmeticError):
            return False, f"Could not parse Pesapal amount: {pesapal_amount_str!r}"

        expected = Decimal(str(payment.amount))
        if abs(pesapal_amount - expected) > Decimal("0.01"):
            return (
                False,
                (
                    f"Amount mismatch for order {payment.order.order_id}: "
                    f"expected {expected}, Pesapal {pesapal_amount}."
                ),
            )
        return True, None

    def _mark_order_units_sold(self, payment: PesapalPayment) -> list[int]:
        """Mark/decrement inventory for an order whose items are now paid."""
        from inventory.models import Admin, Product, ReservationRequest

        units_updated: list[int] = []
        for order_item in payment.order.order_items.all():
            unit = order_item.inventory_unit
            if not unit:
                continue

            if unit.product_template.product_type == Product.ProductType.ACCESSORY:
                reserved_consumed = 0
                try:
                    admin = (
                        Admin.objects.get(user=payment.order.user) if payment.order.user else None
                    )
                except Admin.DoesNotExist:
                    admin = None
                if admin:
                    remaining_to_consume = order_item.quantity
                    reservation_requests = ReservationRequest.objects.filter(
                        requesting_salesperson=admin,
                        status=ReservationRequest.StatusChoices.APPROVED,
                        inventory_units=unit,
                    ).order_by("approved_at", "requested_at")
                    for req in reservation_requests:
                        unit_quantities = req.inventory_unit_quantities or {}
                        qty = (
                            unit_quantities.get(str(unit.id))
                            or unit_quantities.get(unit.id)
                            or 0
                        )
                        if qty <= 0:
                            continue
                        consume = min(remaining_to_consume, qty)
                        unit_quantities[str(unit.id)] = qty - consume
                        req.inventory_unit_quantities = unit_quantities
                        if all(v == 0 for v in unit_quantities.values()):
                            req.status = ReservationRequest.StatusChoices.RETURNED
                            req.expires_at = timezone.now()
                        req.save(
                            update_fields=[
                                "inventory_unit_quantities",
                                "status",
                                "expires_at",
                            ]
                        )
                        reserved_consumed += consume
                        remaining_to_consume -= consume
                        if remaining_to_consume == 0:
                            break

                decrement_qty = max(0, order_item.quantity - reserved_consumed)
                if decrement_qty > 0:
                    unit.quantity = max(0, unit.quantity - decrement_qty)
                if unit.quantity == 0:
                    unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
                else:
                    unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                unit.save(update_fields=["quantity", "sale_status"])
                units_updated.append(unit.id)
                print(
                    f"[PESAPAL] ✓ Accessory unit {unit.id} reserved_consumed={reserved_consumed}, "
                    f"decremented={decrement_qty}, new quantity: {unit.quantity}, "
                    f"status: {unit.get_sale_status_display()}"
                )
            else:
                if unit.sale_status == InventoryUnit.SaleStatusChoices.PENDING_PAYMENT:
                    unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
                    unit.save(update_fields=["sale_status"])
                    units_updated.append(unit.id)
                    print(
                        f"[PESAPAL] ✓ Unit {unit.id} updated from PENDING_PAYMENT to SOLD"
                    )

        return units_updated

    @transaction.atomic
    def initiate_payment(
        self,
        order: Order,
        callback_url: str,
        cancellation_url: str | None = None,
        customer: dict | None = None,
        billing_address: dict | None = None,
        payment_mode: str = "BOTH",
    ) -> dict:
        """Initiate Pesapal payment for an order."""
        mode = self.resolve_effective_payment_mode(order, payment_mode)
        payable_amount = self.get_effective_order_total(order, payment_mode=mode)

        print("\n[PESAPAL] ========== INITIATE PAYMENT START ==========")
        print(f"[PESAPAL] Order ID: {order.order_id}")
        print(f"[PESAPAL] Order Amount: {payable_amount}")
        print(f"[PESAPAL] Order Status: {order.status}")
        print(f"[PESAPAL] Payment Mode (requested/effective): {payment_mode}/{mode}")
        print(f"[PESAPAL] Callback URL: {callback_url}")
        print(f"[PESAPAL] Cancellation URL: {cancellation_url}")
        print(f"[PESAPAL] Customer: {json.dumps(customer, indent=2) if customer else 'None'}")

        try:
            if order.is_items_paid and order.is_delivery_paid:
                return {
                    "success": False,
                    "error": "Order is already fully paid. Cannot initiate payment.",
                }
            if mode == "ITEMS_ONLY" and order.is_items_paid:
                return {
                    "success": False,
                    "error": "Items are already paid for this order.",
                }
            if mode == "DELIVERY_ONLY" and order.is_delivery_paid:
                return {
                    "success": False,
                    "error": "Delivery is already paid for this order.",
                }
            if payable_amount <= 0:
                return {
                    "success": False,
                    "error": "Nothing left to pay for this order.",
                }

            # Only reuse an in-flight PENDING session for the same purpose + amount.
            # Never reuse COMPLETED rows — that blocks ITEMS_ONLY → DELIVERY_ONLY split pay.
            existing_payment = (
                PesapalPayment.objects.filter(
                    order=order,
                    pesapal_order_tracking_id__isnull=False,
                    status=PesapalPayment.StatusChoices.PENDING,
                    payment_purpose=mode,
                )
                .order_by("-initiated_at")
                .first()
            )

            if (
                existing_payment
                and existing_payment.redirect_url
                and abs(Decimal(str(existing_payment.amount)) - payable_amount) <= Decimal("0.01")
            ):
                print("[PESAPAL] Found matching PENDING payment - returning it")
                print(
                    f"[PESAPAL] Existing Tracking ID: {existing_payment.pesapal_order_tracking_id}"
                )
                print(f"[PESAPAL] Existing Status: {existing_payment.status}")
                logger.info(f"Returning existing payment for order {order.order_id}")
                return {
                    "success": True,
                    "redirect_url": existing_payment.redirect_url,
                    "order_tracking_id": existing_payment.pesapal_order_tracking_id,
                    "payment_id": str(existing_payment.id),
                }

            ipn_url = getattr(settings, "PESAPAL_IPN_URL", "")
            if not ipn_url:
                print("[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print("[PESAPAL] ERROR: PESAPAL_IPN_URL not configured")
                print("[PESAPAL] ============================================\n")
                return {"success": False, "error": "PESAPAL_IPN_URL not configured in settings"}

            print(f"[PESAPAL] IPN URL: {ipn_url}")

            if not customer and order.customer:
                customer = {}
                if order.customer.email:
                    customer["email"] = order.customer.email
                if order.customer.phone:
                    customer["phone_number"] = order.customer.phone
                if order.customer.name:
                    name_parts = order.customer.name.split(" ", 1)
                    customer["first_name"] = name_parts[0] if len(name_parts) > 0 else ""
                    customer["last_name"] = name_parts[1] if len(name_parts) > 1 else ""
                print(f"[PESAPAL] Built customer data from order: {json.dumps(customer, indent=2)}")

            items = []
            for order_item in order.order_items.all():
                item = {
                    "id": str(order_item.inventory_unit.id)
                    if order_item.inventory_unit
                    else str(order_item.id),
                    "name": order_item.inventory_unit.product_template.product_name
                    if order_item.inventory_unit
                    else "Item",
                    "quantity": order_item.quantity,
                    "unit_price": str(order_item.unit_price_at_purchase),
                }
                items.append(item)

            print(f"[PESAPAL] Order Items: {json.dumps(items, indent=2)}")

            # Get notification_id and IPN URL
            notification_id = getattr(settings, "PESAPAL_NOTIFICATION_ID", "").strip()
            ipn_url = getattr(settings, "PESAPAL_IPN_URL", "").strip()

            print(
                f"[PESAPAL] Notification ID from settings: '{notification_id}' (length: {len(notification_id)})"
            )
            print(f"[PESAPAL] IPN URL from settings: '{ipn_url}'")

            # If notification_id is empty but IPN URL is set, try to register it and get notification_id
            if not notification_id and ipn_url:
                print(
                    "[PESAPAL] No notification_id but IPN URL is set - attempting to register IPN URL..."
                )
                registered_id, reg_error = self.pesapal_service.register_ipn_url(ipn_url, "GET")
                if registered_id:
                    notification_id = registered_id
                    print(
                        f"[PESAPAL] Successfully registered IPN URL, got notification_id: {notification_id}"
                    )
                    print(
                        f'[PESAPAL] NOTE: You should add this to your .env: PESAPAL_NOTIFICATION_ID="{notification_id}"'
                    )
                else:
                    print(f"[PESAPAL] WARNING: Failed to register IPN URL: {reg_error}")
                    print("[PESAPAL] Will try using ipn_notification_url instead...")

            order_data = {
                "id": str(order.order_id),
                "currency": "KES",
                "amount": str(payable_amount),
                "description": f"Order #{order.order_id}",
                "callback_url": callback_url,
                "cancellation_url": cancellation_url or callback_url,
                "billing_address": billing_address or {},
                "items": items,
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
                print("[PESAPAL] ERROR: Neither notification_id nor IPN URL configured")
                print("[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(
                    "[PESAPAL] ERROR: PESAPAL_NOTIFICATION_ID or PESAPAL_IPN_URL must be configured"
                )
                print("[PESAPAL] ============================================\n")
                return {
                    "success": False,
                    "error": "PESAPAL_NOTIFICATION_ID or PESAPAL_IPN_URL must be configured in settings",
                }

            if customer:
                # Drop blank strings — empty phone_number/email makes Pesapal return 400.
                cleaned_customer = {
                    key: value
                    for key, value in customer.items()
                    if value is not None and str(value).strip() != ""
                }
                if cleaned_customer:
                    order_data["customer"] = cleaned_customer

            print(f"[PESAPAL] Order Data to submit: {json.dumps(order_data, indent=2)}")
            print("[PESAPAL] Calling PesapalService.submit_order_request...")

            result, error = self.pesapal_service.submit_order_request(order_data)

            if error:
                print("[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR from PesapalService: {error}")
                print("[PESAPAL] ============================================\n")
                logger.error(f"Failed to submit order to Pesapal: {error}")
                return {"success": False, "error": error}

            if not result:
                print("[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print("[PESAPAL] ERROR: No response from Pesapal API")
                print("[PESAPAL] ============================================\n")
                return {"success": False, "error": "No response from Pesapal API"}

            print(f"[PESAPAL] Response from PesapalService: {json.dumps(result, indent=2)}")

            order_tracking_id = result.get("order_tracking_id")
            redirect_url = result.get("redirect_url")

            if not order_tracking_id or not redirect_url:
                print("[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print("[PESAPAL] ERROR: Invalid response from Pesapal API")
                print("[PESAPAL] Missing order_tracking_id or redirect_url")
                print("[PESAPAL] ============================================\n")
                return {"success": False, "error": "Invalid response from Pesapal API"}

            print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
            print(f"[PESAPAL] Redirect URL: {redirect_url}")

            # Check if payment with this tracking ID already exists
            existing_payment_by_tracking = PesapalPayment.objects.filter(
                pesapal_order_tracking_id=order_tracking_id
            ).first()

            if existing_payment_by_tracking:
                print("[PESAPAL] Payment with tracking ID already exists, returning existing")
                logger.info(
                    f"Payment with tracking ID {order_tracking_id} already exists, returning existing payment"
                )
                return {
                    "success": True,
                    "redirect_url": existing_payment_by_tracking.redirect_url or redirect_url,
                    "order_tracking_id": order_tracking_id,
                    "payment_id": str(existing_payment_by_tracking.id),
                }

            try:
                print("[PESAPAL] Creating PesapalPayment record in database...")
                payment = PesapalPayment.objects.create(
                    order=order,
                    pesapal_order_tracking_id=order_tracking_id,
                    amount=payable_amount,
                    currency="KES",
                    payment_purpose=mode,
                    redirect_url=redirect_url,
                    callback_url=callback_url,
                    customer_email=customer.get("email") if customer else None,
                    customer_phone=customer.get("phone_number") if customer else None,
                    customer_name=order.customer.name if order.customer else None,
                    status=PesapalPayment.StatusChoices.PENDING,
                    api_request_data=order_data,
                    api_response_data=result,
                    expired_at=timezone.now() + timedelta(hours=self.payment_expiry_hours),
                )

                # Track payment initiation
                from inventory.observability import PAYMENTS_TOTAL

                try:
                    brand_code = order.brand.code if order.brand else "unknown"
                    PAYMENTS_TOTAL.labels(
                        method="pesapal", status="PENDING", brand=brand_code
                    ).inc()
                except Exception:
                    pass

                print("[PESAPAL] ========== INITIATE PAYMENT SUCCESS ==========")
                print(f"[PESAPAL] Payment record created - ID: {payment.id}")
                print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
                print(f"[PESAPAL] Redirect URL: {redirect_url}")
                print("[PESAPAL] =============================================\n")
                logger.info(f"Payment initiated for order {order.order_id}: {order_tracking_id}")

                return {
                    "success": True,
                    "redirect_url": redirect_url,
                    "order_tracking_id": order_tracking_id,
                    "payment_id": str(payment.id),
                }

            except Exception as e:
                # Handle IntegrityError (duplicate tracking ID) gracefully
                from django.db import IntegrityError

                if isinstance(e, IntegrityError) and "pesapal_order_tracking_id" in str(e):
                    print(
                        "[PESAPAL] WARNING: Payment with tracking ID already exists (race condition)"
                    )
                    print(f"[PESAPAL] Error: {str(e)}")
                    logger.warning(
                        f"Payment with tracking ID {order_tracking_id} already exists (race condition)"
                    )
                    # Try to get the existing payment
                    existing = PesapalPayment.objects.filter(
                        pesapal_order_tracking_id=order_tracking_id
                    ).first()
                    if existing:
                        print("[PESAPAL] Found existing payment, returning it")
                        return {
                            "success": True,
                            "redirect_url": existing.redirect_url or redirect_url,
                            "order_tracking_id": order_tracking_id,
                            "payment_id": str(existing.id),
                        }

                print("[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR creating payment record: {str(e)}")
                print("[PESAPAL] ============================================\n")
                logger.error(f"Error creating payment record: {str(e)}")
                return {"success": False, "error": f"Failed to create payment record: {str(e)}"}

        except Exception as e:
            print("[PESAPAL] ========== INITIATE PAYMENT FAILED ==========")
            print(f"[PESAPAL] UNEXPECTED ERROR: {str(e)}")
            import traceback

            print(f"[PESAPAL] Traceback:\n{traceback.format_exc()}")
            print("[PESAPAL] ============================================\n")
            logger.error(f"Unexpected error initiating payment: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    @transaction.atomic
    def handle_ipn(
        self,
        order_tracking_id: str,
        order_notification_type: str | None = None,
        order_merchant_reference: str | None = None,
        payment_status_description: str | None = None,
        payment_method: str | None = None,
        payment_account: str | None = None,
        ipn_data: dict | None = None,
    ) -> dict:
        """Handle IPN callback from Pesapal."""
        print("\n[PESAPAL] ========== HANDLE IPN START ==========")
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
                print("[PESAPAL] ========== HANDLE IPN FAILED ==========")
                print(
                    f"[PESAPAL] ERROR: Payment not found for order_tracking_id: {order_tracking_id}"
                )
                print("[PESAPAL] =======================================\n")
                logger.warning(f"IPN received for unknown order_tracking_id: {order_tracking_id}")
                return {
                    "success": False,
                    "message": f"Payment not found for order_tracking_id: {order_tracking_id}",
                }

            print(
                f"[PESAPAL] Found payment record - ID: {payment.id}, Order: {payment.order.order_id}"
            )
            print(f"[PESAPAL] Current payment status: {payment.status}")

            payment.ipn_data = ipn_data or {}
            payment.ipn_received = True
            payment.ipn_received_at = timezone.now()

            status_mapping = {
                "COMPLETED": PesapalPayment.StatusChoices.COMPLETED,
                "FAILED": PesapalPayment.StatusChoices.FAILED,
                "INVALID": PesapalPayment.StatusChoices.FAILED,
            }

            if payment_status_description:
                payment_status_upper = payment_status_description.upper()
                print(f"[PESAPAL] Processing payment status: {payment_status_upper}")
                if payment_status_upper in status_mapping:
                    # SECURITY: Don't mark as completed from IPN alone - wait for status verification
                    # Status verification will validate the amount before marking as paid
                    if payment_status_upper == "COMPLETED":
                        print(
                            "[PESAPAL] IPN reports COMPLETED - will verify with Pesapal API (including amount validation)"
                        )
                        # Don't mark as paid yet - wait for API verification with amount check below
                    else:
                        payment.status = status_mapping[payment_status_upper]
                        print(f"[PESAPAL] Updated payment status to: {payment.status}")

            if payment_method:
                payment.payment_method = payment_method
                print(f"[PESAPAL] Payment method set to: {payment_method}")

            print("[PESAPAL] Calling get_transaction_status to verify...")
            status_result, status_error = self.pesapal_service.get_transaction_status(
                order_tracking_id
            )
            if status_result and not status_error:
                print(
                    f"[PESAPAL] Status verification response: {json.dumps(status_result, indent=2)}"
                )
                payment.api_response_data = status_result

                # SECURITY: require amount match before marking paid (fail closed if missing).
                amount_ok, amount_error = self.validate_pesapal_amount(payment, status_result)
                if not amount_ok:
                    error_msg = f"SECURITY ALERT: {amount_error}"
                    print("[PESAPAL] ========== SECURITY: AMOUNT VALIDATION FAILED ==========")
                    print(f"[PESAPAL] {error_msg}")
                    print("[PESAPAL] ======================================================\n")
                    logger.error(error_msg)
                    payment.status = PesapalPayment.StatusChoices.FAILED
                    payment.save(update_fields=["status", "api_response_data"])
                    return {
                        "success": False,
                        "message": "Payment amount validation failed. Payment rejected for security.",
                        "error": amount_error or "Amount validation failed",
                    }
                print(
                    f"[PESAPAL] ✓ Amount validation passed: "
                    f"{status_result.get('amount')} == {payment.amount}"
                )

                payment_status = status_result.get("payment_status_description", "").upper()
                if payment_status in status_mapping:
                    payment.status = status_mapping[payment_status]
                    print(f"[PESAPAL] Updated payment status from verification: {payment.status}")
                    if payment.status == PesapalPayment.StatusChoices.COMPLETED:
                        # All validations passed - mark as paid
                        payment.completed_at = timezone.now()
                        payment.is_verified = True
                        payment.verified_at = timezone.now()
                        purpose = (payment.payment_purpose or "BOTH").strip().upper()
                        if purpose in ["ITEMS_ONLY", "BOTH"]:
                            payment.order.is_items_paid = True
                        if purpose in ["DELIVERY_ONLY", "BOTH"]:
                            payment.order.is_delivery_paid = True
                        if payment.order.is_items_paid and payment.order.is_delivery_paid:
                            payment.order.status = Order.StatusChoices.PAID
                            print(
                                "[PESAPAL] ✓ Payment verified - Order marked as PAID (items + delivery paid)"
                            )
                        else:
                            print(
                                "[PESAPAL] ✓ Payment verified - Order is PARTIALLY paid "
                                f"(items_paid={payment.order.is_items_paid}, delivery_paid={payment.order.is_delivery_paid})"
                            )
                        payment.order.save(
                            update_fields=["is_items_paid", "is_delivery_paid", "status"]
                        )
                        logger.info(
                            f"Payment completed and verified for order {payment.order.order_id}"
                        )

                        # Track payment and revenue metrics
                        from inventory.observability import (
                            ORDERS_TOTAL,
                            PAYMENTS_TOTAL,
                            REVENUE_EARNED,
                        )

                        try:
                            brand_code = (
                                payment.order.brand.code if payment.order.brand else "unknown"
                            )
                            pm = payment.payment_method or "pesapal"
                            PAYMENTS_TOTAL.labels(
                                method=pm, status=payment.status, brand=brand_code
                            ).inc()
                            REVENUE_EARNED.labels(brand=brand_code).inc(float(payment.amount))
                            if payment.order.status == Order.StatusChoices.PAID:
                                ORDERS_TOTAL.labels(
                                    status="Paid", payment_method=pm, brand=brand_code
                                ).inc()
                        except Exception:
                            pass

                        # Inventory only moves when items are paid — never on DELIVERY_ONLY alone.
                        if purpose in ["ITEMS_ONLY", "BOTH"] and payment.order.is_items_paid:
                            units_updated = self._mark_order_units_sold(payment)
                            if units_updated:
                                logger.info(
                                    f"Updated {len(units_updated)} inventory units to SOLD for order {payment.order.order_id}"
                                )
                                print(
                                    f"[PESAPAL] ✓ Updated {len(units_updated)} inventory units to SOLD"
                                )
                            else:
                                logger.warning(
                                    f"No units with PENDING_PAYMENT status found for order {payment.order.order_id}"
                                )
                                print(
                                    "[PESAPAL] ⚠ No units with PENDING_PAYMENT status found - units may already be SOLD"
                                )
                        else:
                            print(
                                "[PESAPAL] Skipping inventory SOLD update "
                                f"(purpose={purpose}, is_items_paid={payment.order.is_items_paid})"
                            )

                        # Full receipt only when the order is fully PAID (not on partial legs).
                        if payment.order.status == Order.StatusChoices.PAID:
                            try:
                                from inventory.services.receipt_service import ReceiptService

                                receipt, email_sent, whatsapp_sent = (
                                    ReceiptService.generate_and_send_receipt(payment.order)
                                )
                                print(
                                    f"[PESAPAL] Receipt generated: {receipt.receipt_number}, Email sent: {email_sent}, WhatsApp sent: {whatsapp_sent}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to generate receipt for order {payment.order.order_id}: {e}"
                                )
                                print(f"[PESAPAL] WARNING: Receipt generation failed: {e}")

                        # Clear shop cart only after the order is fully PAID.
                        if payment.order.status == Order.StatusChoices.PAID:
                            try:
                                from inventory.services.cart_service import CartService

                                cleared = CartService.clear_open_carts_for_order(payment.order)
                                if cleared:
                                    print(
                                        f"[PESAPAL] Cleared {cleared} open cart(s) after full payment"
                                    )
                            except Exception as cart_err:
                                logger.warning(
                                    "Could not clear cart after Pesapal payment for order %s: %s",
                                    payment.order.order_id,
                                    cart_err,
                                )
            elif status_error:
                print(f"[PESAPAL] WARNING: Status verification failed: {status_error}")

            payment.save()

            print("[PESAPAL] ========== HANDLE IPN SUCCESS ==========")
            print(f"[PESAPAL] Final payment status: {payment.status}")
            print(f"[PESAPAL] Order status: {payment.order.status}")
            print("[PESAPAL] ========================================\n")
            logger.info(f"IPN processed for order {payment.order.order_id}: {payment.status}")

            return {"success": True, "message": "IPN processed successfully"}

        except Exception as e:
            print("[PESAPAL] ========== HANDLE IPN FAILED ==========")
            print(f"[PESAPAL] ERROR: {str(e)}")
            import traceback

            print(f"[PESAPAL] Traceback:\n{traceback.format_exc()}")
            print("[PESAPAL] ========================================\n")
            logger.error(f"Error handling IPN: {str(e)}", exc_info=True)
            return {"success": False, "message": f"Error processing IPN: {str(e)}"}

    def get_payment_status(self, order: Order) -> dict:
        """Get current payment status for an order. Queries Pesapal API directly if status is PENDING."""
        # #region agent log
        import json
        import time

        log_path = (
            "/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log"
        )
        try:
            with open(log_path, "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "inventory/services/pesapal_payment_service.py:get_payment_status",
                            "message": "get_payment_status called",
                            "data": {
                                "order_id": str(order.order_id),
                                "order_status": order.status,
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        print("\n[PESAPAL] ========== GET PAYMENT STATUS START ==========")
        print(f"[PESAPAL] Order ID: {order.order_id}")

        payments = PesapalPayment.objects.filter(order=order)
        pending_payment = (
            payments.filter(status=PesapalPayment.StatusChoices.PENDING)
            .order_by("-initiated_at")
            .first()
        )
        completed_payment = (
            payments.filter(status=PesapalPayment.StatusChoices.COMPLETED)
            .order_by("-completed_at", "-initiated_at")
            .first()
        )
        latest_payment = payments.order_by("-initiated_at").first()

        # Prefer in-flight PENDING (active Pesapal session), else COMPLETED, else latest.
        payment = pending_payment or completed_payment or latest_payment

        if not payment:
            print("[PESAPAL] No payment found for this order")
            print("[PESAPAL] ===========================================\n")
            return {
                "status": "NO_PAYMENT",
                "message": "No payment initiated for this order",
                "order_status": order.status,
                "is_items_paid": bool(order.is_items_paid),
                "is_delivery_paid": bool(order.is_delivery_paid),
            }

        print(f"[PESAPAL] Payment found - ID: {payment.id}")
        print(f"[PESAPAL] Payment Status: {payment.status}")
        print(f"[PESAPAL] Order Tracking ID: {payment.pesapal_order_tracking_id}")
        print(f"[PESAPAL] Amount: {payment.amount}")
        print(f"[PESAPAL] IPN Received: {payment.ipn_received}")

        # If status is PENDING and we have a tracking ID, query Pesapal API for real-time status
        if (
            payment.status == PesapalPayment.StatusChoices.PENDING
            and payment.pesapal_order_tracking_id
        ):
            print("[PESAPAL] Status is PENDING - Querying Pesapal API for real-time status...")
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "B",
                                "location": "inventory/services/pesapal_payment_service.py:get_payment_status",
                                "message": "Querying Pesapal API for PENDING payment",
                                "data": {
                                    "order_tracking_id": payment.pesapal_order_tracking_id,
                                    "current_status": payment.status,
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion

            status_result, status_error = self.pesapal_service.get_transaction_status(
                payment.pesapal_order_tracking_id
            )

            if status_result and not status_error:
                print(
                    f"[PESAPAL] Pesapal API response received: {json.dumps(status_result, indent=2)}"
                )
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(
                            json.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "B",
                                    "location": "inventory/services/pesapal_payment_service.py:get_payment_status",
                                    "message": "Pesapal API response received",
                                    "data": {
                                        "payment_status_description": status_result.get(
                                            "payment_status_description"
                                        ),
                                        "status_result_keys": list(status_result.keys()),
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion

                # Map Pesapal status to our status
                status_mapping = {
                    "COMPLETED": PesapalPayment.StatusChoices.COMPLETED,
                    "FAILED": PesapalPayment.StatusChoices.FAILED,
                    "CANCELLED": PesapalPayment.StatusChoices.CANCELLED,
                    "PENDING": PesapalPayment.StatusChoices.PENDING,
                }

                payment_status = status_result.get("payment_status_description", "").upper()
                new_status = status_mapping.get(payment_status)

                # Extract additional fields from Pesapal response
                pesapal_payment_id = status_result.get("payment_id") or status_result.get(
                    "pesapal_payment_id"
                )
                pesapal_reference = status_result.get("payment_reference") or status_result.get(
                    "pesapal_reference"
                )
                payment_method_from_api = status_result.get("payment_method")

                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(
                            json.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "D",
                                    "location": "inventory/services/pesapal_payment_service.py:get_payment_status",
                                    "message": "Extracting fields from Pesapal response",
                                    "data": {
                                        "pesapal_payment_id": pesapal_payment_id,
                                        "pesapal_reference": pesapal_reference,
                                        "payment_method": payment_method_from_api,
                                        "status_result_keys": list(status_result.keys()),
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion

                if new_status and new_status != payment.status:
                    print(f"[PESAPAL] Status changed from {payment.status} to {new_status}")
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(
                                json.dumps(
                                    {
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "C",
                                        "location": "inventory/services/pesapal_payment_service.py:get_payment_status",
                                        "message": "Payment status updated from Pesapal API",
                                        "data": {
                                            "old_status": payment.status,
                                            "new_status": new_status,
                                            "pesapal_status": payment_status,
                                        },
                                        "timestamp": int(time.time() * 1000),
                                    }
                                )
                                + "\n"
                            )
                    except Exception:
                        pass
                    # #endregion

                    payment.status = new_status
                    payment.api_response_data = status_result

                    # Update payment_id and payment_reference if available
                    if pesapal_payment_id and not payment.pesapal_payment_id:
                        payment.pesapal_payment_id = pesapal_payment_id
                        print(f"[PESAPAL] Payment ID set: {pesapal_payment_id}")

                    if pesapal_reference and not payment.pesapal_reference:
                        payment.pesapal_reference = pesapal_reference
                        print(f"[PESAPAL] Payment reference set: {pesapal_reference}")

                    # Update payment method if available
                    if payment_method_from_api and not payment.payment_method:
                        payment.payment_method = payment_method_from_api
                        print(f"[PESAPAL] Payment method set: {payment_method_from_api}")

                    # If completed, require amount match (fail closed) before marking paid.
                    if new_status == PesapalPayment.StatusChoices.COMPLETED:
                        amount_ok, amount_error = self.validate_pesapal_amount(
                            payment, status_result
                        )
                        if not amount_ok:
                            error_msg = f"SECURITY ALERT: {amount_error}"
                            print(
                                "[PESAPAL] ========== SECURITY: AMOUNT VALIDATION FAILED =========="
                            )
                            print(f"[PESAPAL] {error_msg}")
                            print(
                                "[PESAPAL] ======================================================\n"
                            )
                            logger.error(error_msg)
                            payment.status = PesapalPayment.StatusChoices.FAILED
                            payment.save()
                            new_status = payment.status
                        else:
                            payment.completed_at = timezone.now()
                            payment.is_verified = True
                            payment.verified_at = timezone.now()
                            purpose = (payment.payment_purpose or "BOTH").strip().upper()
                            if purpose in ["ITEMS_ONLY", "BOTH"]:
                                payment.order.is_items_paid = True
                            if purpose in ["DELIVERY_ONLY", "BOTH"]:
                                payment.order.is_delivery_paid = True
                            if payment.order.is_items_paid and payment.order.is_delivery_paid:
                                payment.order.status = Order.StatusChoices.PAID
                                print(
                                    "[PESAPAL] ✓ Payment verified - Order marked as PAID (items + delivery paid)"
                                )
                            else:
                                print(
                                    "[PESAPAL] ✓ Payment verified - Order is PARTIALLY paid "
                                    f"(items_paid={payment.order.is_items_paid}, delivery_paid={payment.order.is_delivery_paid})"
                                )
                            payment.order.save(
                                update_fields=["is_items_paid", "is_delivery_paid", "status"]
                            )

                            # Inventory only when items are paid — never on DELIVERY_ONLY alone.
                            if purpose in ["ITEMS_ONLY", "BOTH"] and payment.order.is_items_paid:
                                self._mark_order_units_sold(payment)
                            else:
                                print(
                                    "[PESAPAL] Skipping inventory SOLD update "
                                    f"(purpose={purpose}, is_items_paid={payment.order.is_items_paid})"
                                )

                            # Track payment completion via callback
                            from inventory.observability import (
                                ORDERS_TOTAL,
                                PAYMENTS_TOTAL,
                                REVENUE_EARNED,
                            )

                            try:
                                brand_code = (
                                    payment.order.brand.code if payment.order.brand else "unknown"
                                )
                                pm = payment.payment_method or "pesapal"
                                PAYMENTS_TOTAL.labels(
                                    method=pm, status=new_status, brand=brand_code
                                ).inc()
                                REVENUE_EARNED.labels(brand=brand_code).inc(float(payment.amount))
                                if payment.order.status == Order.StatusChoices.PAID:
                                    ORDERS_TOTAL.labels(
                                        status="Paid", payment_method=pm, brand=brand_code
                                    ).inc()
                            except Exception:
                                pass

                            print(
                                "[PESAPAL] ✓ Payment verified as completed - Order marked as PAID"
                            )

                            # Full receipt only when the order is fully PAID (not on partial legs).
                            if payment.order.status == Order.StatusChoices.PAID:
                                try:
                                    from inventory.services.receipt_service import ReceiptService

                                    receipt, email_sent, whatsapp_sent = (
                                        ReceiptService.generate_and_send_receipt(payment.order)
                                    )
                                    print(
                                        f"[PESAPAL] Receipt generated: {receipt.receipt_number}, Email sent: {email_sent}, WhatsApp sent: {whatsapp_sent}"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Failed to generate receipt for order {payment.order.order_id}: {e}"
                                    )
                                    print(f"[PESAPAL] WARNING: Receipt generation failed: {e}")

                            # Clear shop cart only after the order is fully PAID.
                            if payment.order.status == Order.StatusChoices.PAID:
                                try:
                                    from inventory.services.cart_service import CartService

                                    cleared = CartService.clear_open_carts_for_order(payment.order)
                                    if cleared:
                                        print(
                                            f"[PESAPAL] Cleared {cleared} open cart(s) after full payment"
                                        )
                                except Exception as cart_err:
                                    logger.warning(
                                        "Could not clear cart after Pesapal payment for order %s: %s",
                                        payment.order.order_id,
                                        cart_err,
                                    )

                    payment.save()
                    print("[PESAPAL] Payment status updated in database")
                elif new_status == payment.status:
                    # Even if status didn't change, update other fields if they're missing
                    updated = False
                    if pesapal_payment_id and not payment.pesapal_payment_id:
                        payment.pesapal_payment_id = pesapal_payment_id
                        updated = True
                        print(f"[PESAPAL] Payment ID updated: {pesapal_payment_id}")

                    if pesapal_reference and not payment.pesapal_reference:
                        payment.pesapal_reference = pesapal_reference
                        updated = True
                        print(f"[PESAPAL] Payment reference updated: {pesapal_reference}")

                    if payment_method_from_api and not payment.payment_method:
                        payment.payment_method = payment_method_from_api
                        updated = True
                        print(f"[PESAPAL] Payment method updated: {payment_method_from_api}")

                    if updated:
                        payment.api_response_data = status_result
                        payment.save()
                        print("[PESAPAL] Payment fields updated from Pesapal API")
            elif status_error:
                print(f"[PESAPAL] Error querying Pesapal API: {status_error}")
                print("[PESAPAL] Returning cached database status")

        print("[PESAPAL] ===========================================\n")

        # Refresh payment + order from database to get updated status/flags
        payment.refresh_from_db()
        payment.order.refresh_from_db()
        receipt_email_sent = None
        receipt_whatsapp_sent = None
        try:
            if payment.status == PesapalPayment.StatusChoices.COMPLETED:
                receipt = getattr(payment.order, "receipt", None)
                if receipt:
                    receipt_email_sent = receipt.email_sent
                    receipt_whatsapp_sent = receipt.whatsapp_sent
        except Exception:
            pass

        # Convert datetime objects to ISO format strings for JSON serialization
        initiated_at_str = payment.initiated_at.isoformat() if payment.initiated_at else None
        completed_at_str = payment.completed_at.isoformat() if payment.completed_at else None

        # Aggregate display status for split-pay: full PAID wins; else active PENDING;
        # else any COMPLETED leg.
        order_obj = payment.order
        has_completed_leg = (
            payment.status == PesapalPayment.StatusChoices.COMPLETED
            or PesapalPayment.objects.filter(
                order=order_obj, status=PesapalPayment.StatusChoices.COMPLETED
            ).exists()
        )
        if order_obj.status == Order.StatusChoices.PAID:
            status_out = PesapalPayment.StatusChoices.COMPLETED
        elif payment.status == PesapalPayment.StatusChoices.PENDING:
            status_out = PesapalPayment.StatusChoices.PENDING
        elif has_completed_leg:
            status_out = PesapalPayment.StatusChoices.COMPLETED
        else:
            status_out = payment.status

        return {
            "status": status_out,
            "order_status": order_obj.status,
            "order_tracking_id": payment.pesapal_order_tracking_id,
            "payment_id": payment.pesapal_payment_id,
            "payment_reference": payment.pesapal_reference,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "payment_method": payment.payment_method,
            "payment_purpose": payment.payment_purpose,
            "redirect_url": payment.redirect_url,
            "initiated_at": initiated_at_str,
            "completed_at": completed_at_str,
            "is_verified": payment.is_verified,
            "ipn_received": payment.ipn_received,
            "is_items_paid": bool(order_obj.is_items_paid),
            "is_delivery_paid": bool(order_obj.is_delivery_paid),
            "receipt_email_sent": receipt_email_sent,
            "receipt_whatsapp_sent": receipt_whatsapp_sent,
        }
