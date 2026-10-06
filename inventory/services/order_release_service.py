"""Release abandoned unpaid pending orders so unique units return to stock."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from inventory.models import InventoryUnit, Order, PesapalPayment

logger = logging.getLogger(__name__)


class OrderReleaseService:
    @staticmethod
    def _restore_unit_for_order(order: Order, unit: InventoryUnit) -> bool:
        """Restore a unit held by an unpaid pending order. Never touch SOLD units."""
        if unit.sale_status == InventoryUnit.SaleStatusChoices.SOLD:
            return False
        if unit.sale_status not in {
            InventoryUnit.SaleStatusChoices.PENDING_PAYMENT,
            InventoryUnit.SaleStatusChoices.RESERVED,
        }:
            return False

        if order.order_source == Order.OrderSourceChoices.ONLINE:
            unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
        else:
            unit.sale_status = InventoryUnit.SaleStatusChoices.RESERVED
        unit.reserved_by = None
        unit.reserved_until = None
        unit.save(update_fields=["sale_status", "reserved_by", "reserved_until"])
        return True

    @staticmethod
    @transaction.atomic
    def release_order(order: Order, *, reason: str = "") -> bool:
        """
        Cancel an unpaid pending order and free its unique units.

        Never releases orders with items already paid (partial split-pay).
        """
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.StatusChoices.PENDING:
            return False
        if order.is_items_paid:
            return False
        if order.pesapal_payments.filter(status=PesapalPayment.StatusChoices.COMPLETED).exists():
            return False

        order.status = Order.StatusChoices.CANCELED
        order.save(update_fields=["status"])

        restored = 0
        for item in order.order_items.select_related("inventory_unit"):
            unit = item.inventory_unit
            if unit is None:
                continue
            if OrderReleaseService._restore_unit_for_order(order, unit):
                restored += 1

        logger.info(
            "Released abandoned pending order %s (restored_units=%s, reason=%s)",
            order.order_id,
            restored,
            reason or "unspecified",
        )
        return True

    @staticmethod
    def is_abandoned(order: Order, *, older_than_hours: float = 2.0) -> bool:
        if order.status != Order.StatusChoices.PENDING:
            return False
        if order.is_items_paid:
            return False
        cutoff = timezone.now() - timedelta(hours=older_than_hours)
        if order.created_at and order.created_at > cutoff:
            return False
        if order.pesapal_payments.filter(status=PesapalPayment.StatusChoices.COMPLETED).exists():
            return False
        return True

    @staticmethod
    def maybe_release_order(order: Order, *, older_than_hours: float = 2.0) -> bool:
        if not OrderReleaseService.is_abandoned(order, older_than_hours=older_than_hours):
            return False
        return OrderReleaseService.release_order(
            order, reason=f"abandoned>{older_than_hours}h"
        )

    @staticmethod
    def release_abandoned_pending_orders(
        *, older_than_hours: float = 2.0, dry_run: bool = False, limit: int = 500
    ) -> dict:
        """
        Cancel unpaid PENDING orders older than the cutoff and free inventory.

        Skips orders with is_items_paid or any COMPLETED Pesapal payment.
        """
        cutoff = timezone.now() - timedelta(hours=older_than_hours)
        qs = (
            Order.objects.filter(
                status=Order.StatusChoices.PENDING,
                created_at__lt=cutoff,
                is_items_paid=False,
            )
            .exclude(pesapal_payments__status=PesapalPayment.StatusChoices.COMPLETED)
            .distinct()
            .order_by("created_at")[:limit]
        )
        candidates = list(qs)
        released = 0
        for order in candidates:
            if dry_run:
                released += 1
                continue
            if OrderReleaseService.release_order(order, reason=f"cron>{older_than_hours}h"):
                released += 1
        return {
            "candidates": len(candidates),
            "released": released,
            "older_than_hours": older_than_hours,
            "dry_run": dry_run,
        }

    @staticmethod
    def release_conflicting_claims_for_unit(
        inventory_unit: InventoryUnit, *, older_than_hours: float = 2.0
    ) -> int:
        """Release abandoned pending orders that still claim this unique unit."""
        from inventory.models import OrderItem

        items = (
            OrderItem.objects.filter(
                inventory_unit=inventory_unit,
                order__status=Order.StatusChoices.PENDING,
            )
            .filter(Q(order__is_items_paid=False))
            .select_related("order")
        )
        released = 0
        for item in items:
            if OrderReleaseService.maybe_release_order(
                item.order, older_than_hours=older_than_hours
            ):
                released += 1
        return released
