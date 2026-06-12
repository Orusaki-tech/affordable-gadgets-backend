"""Helpers for linking anonymous activity to authenticated users."""

import re
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from inventory.models import Cart, Customer, ObservabilityEvent

_SESSION_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,40}$")
_LEGACY_NULL_IP_WINDOW = timedelta(days=30)


def resolve_request_session_key(request) -> str:
    """Resolve session key from body, query, header, or Django session."""
    return (
        request.data.get("session_key")
        or request.query_params.get("session_key")
        or request.META.get("HTTP_X_SESSION_KEY")
        or getattr(request.session, "session_key", None)
        or ""
    )


def get_client_ip(request) -> str:
    """Client IP, honoring X-Forwarded-For when behind a proxy."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def is_valid_session_key(session_key: str) -> bool:
    return bool(session_key and _SESSION_KEY_RE.match(session_key))


def get_customer_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.customer
    except Customer.DoesNotExist:
        return None


def link_cart_to_authenticated_user(cart, user):
    """Attach cart to the logged-in customer's profile when possible."""
    customer = get_customer_for_user(user)
    if not customer:
        return cart

    update_fields = []
    if cart.customer_id != customer.id:
        cart.customer = customer
        update_fields.append("customer")
    if user.email and not cart.customer_email:
        cart.customer_email = user.email
        update_fields.append("customer_email")
    if customer.phone and not cart.customer_phone:
        cart.customer_phone = customer.phone
        update_fields.append("customer_phone")
    if update_fields:
        cart.save(update_fields=update_fields)
    return cart


def _anonymous_session_events(session_key: str):
    return ObservabilityEvent.objects.filter(session_key=session_key, user__isnull=True)


def _claimable_events_qs(session_key: str, request_ip: str):
    """Events that may be assigned to the user claiming this session."""
    if not is_valid_session_key(session_key) or not request_ip:
        return ObservabilityEvent.objects.none()

    anonymous = _anonymous_session_events(session_key)
    if not anonymous.exists():
        return ObservabilityEvent.objects.none()

    if anonymous.filter(ip_address=request_ip).exists():
        return anonymous.filter(
            Q(ip_address=request_ip)
            | Q(ip_address__isnull=True)
            | Q(ip_address="")
        )

    # Session has IP-tagged events from another client — do not allow hijack.
    if anonymous.filter(ip_address__isnull=False).exists():
        return ObservabilityEvent.objects.none()

    # Legacy rows without IP (e.g. server-side cart_add before IP was stored).
    cutoff = timezone.now() - _LEGACY_NULL_IP_WINDOW
    return anonymous.filter(created_at__gte=cutoff)


def session_is_claimable(session_key: str, request_ip: str) -> bool:
    return _claimable_events_qs(session_key, request_ip).exists()


def backfill_session_events_to_user(user, session_key: str, request_ip: str | None = None) -> int:
    """Assign anonymous observability events to a user after login."""
    if not user or not session_key:
        return 0
    return _claimable_events_qs(session_key, request_ip or "").update(user=user)


def link_session_carts_to_customer(
    user,
    session_key: str,
    brand_code: str | None = None,
    request_ip: str | None = None,
) -> int:
    """Link anonymous session carts to the customer after login."""
    customer = get_customer_for_user(user)
    if not customer or not session_key or not session_is_claimable(session_key, request_ip or ""):
        return 0

    qs = Cart.objects.filter(
        session_key=session_key,
        is_submitted=False,
        customer__isnull=True,
    )
    if brand_code:
        qs = qs.filter(brand__code=brand_code)

    linked = 0
    for cart in qs:
        link_cart_to_authenticated_user(cart, user)
        linked += 1
    return linked


def attach_session_activity_to_user(
    user,
    session_key: str,
    brand_code: str | None = None,
    request_ip: str | None = None,
) -> dict:
    """Backfill events and carts for a session key after authentication."""
    return {
        "events_linked": backfill_session_events_to_user(user, session_key, request_ip),
        "carts_linked": link_session_carts_to_customer(
            user, session_key, brand_code, request_ip
        ),
    }
