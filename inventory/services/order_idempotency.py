"""Idempotency helpers for order create (payload fingerprint + match)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_order_payload(data: dict | None) -> dict:
    """Stable shape used for Idempotency-Key payload comparison."""
    data = data or {}
    items = []
    for raw in data.get("order_items") or []:
        if not isinstance(raw, dict):
            continue
        unit_id = _as_int(raw.get("inventory_unit_id") or raw.get("inventory_unit"))
        variant_id = _as_int(raw.get("variant_id") or raw.get("variant"))
        qty = _as_int(raw.get("quantity")) or 1
        items.append(
            {
                "inventory_unit_id": unit_id,
                "variant_id": variant_id,
                "quantity": qty,
            }
        )
    items.sort(
        key=lambda row: (
            row["inventory_unit_id"] or 0,
            row["variant_id"] or 0,
            row["quantity"],
        )
    )
    return {
        "items": items,
        "customer_phone": _as_str(data.get("customer_phone")),
        "delivery_county": _as_str(data.get("delivery_county")).lower(),
        "delivery_ward": _as_str(data.get("delivery_ward")).lower(),
        "delivery_address": _as_str(data.get("delivery_address")).lower(),
        "order_source": _as_str(data.get("order_source")).upper(),
        # Fulfillment is write-only on create; include so PICKUP vs DELIVERY diverge
        # even when address fields are empty on a mistaken retry.
        "fulfillment_method": _as_str(data.get("fulfillment_method")).upper(),
    }


def fingerprint_order_payload(data: dict | None) -> str:
    normalized = normalize_order_payload(data)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fingerprint_existing_order(order) -> str:
    """Build a fingerprint from a persisted Order for comparison with a create payload."""
    items = []
    for item in order.order_items.all():
        items.append(
            {
                "inventory_unit_id": item.inventory_unit_id,
                "variant_id": getattr(item, "variant_id", None),
                "quantity": item.quantity or 1,
            }
        )

    phone = ""
    if order.customer_id and getattr(order.customer, "phone", None):
        phone = _as_str(order.customer.phone)

    # Infer fulfillment from stored delivery fields (fulfillment_method is not persisted).
    has_delivery = bool(
        _as_str(order.delivery_county)
        or _as_str(order.delivery_ward)
        or _as_str(order.delivery_address)
        or (order.delivery_fee or 0) > 0
    )
    fulfillment = "DELIVERY" if has_delivery else "PICKUP"
    if order.order_source and order.order_source != order.OrderSourceChoices.ONLINE:
        fulfillment = ""

    payload = {
        "order_items": items,
        "customer_phone": phone,
        "delivery_county": order.delivery_county or "",
        "delivery_ward": order.delivery_ward or "",
        "delivery_address": order.delivery_address or "",
        "order_source": order.order_source or "",
        "fulfillment_method": fulfillment,
    }
    return fingerprint_order_payload(payload)


def order_matches_request(order, request_data: dict | None) -> bool:
    request_data = dict(request_data or {})
    # Align request fulfillment with how we infer it from persisted orders.
    fulfillment = _as_str(request_data.get("fulfillment_method")).upper()
    if not fulfillment:
        has_delivery = bool(
            _as_str(request_data.get("delivery_county"))
            or _as_str(request_data.get("delivery_ward"))
            or _as_str(request_data.get("delivery_address"))
        )
        if request_data.get("order_source") == "ONLINE" or _as_str(
            request_data.get("order_source")
        ).upper() == "ONLINE":
            request_data["fulfillment_method"] = "DELIVERY" if has_delivery else "PICKUP"
    return fingerprint_existing_order(order) == fingerprint_order_payload(request_data)
