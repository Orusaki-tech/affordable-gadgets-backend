"""Helpers for linking anonymous activity to authenticated users."""

from inventory.models import Cart, Customer, ObservabilityEvent


def resolve_request_session_key(request) -> str:
    """Resolve session key from body, query, header, or Django session."""
    return (
        request.data.get("session_key")
        or request.query_params.get("session_key")
        or request.META.get("HTTP_X_SESSION_KEY")
        or getattr(request.session, "session_key", None)
        or ""
    )


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


def backfill_session_events_to_user(user, session_key: str) -> int:
    """Assign anonymous observability events to a user after login."""
    if not user or not session_key:
        return 0
    return ObservabilityEvent.objects.filter(
        session_key=session_key,
        user__isnull=True,
    ).update(user=user)


def link_session_carts_to_customer(user, session_key: str, brand_code: str | None = None) -> int:
    """Link anonymous session carts to the customer after login."""
    customer = get_customer_for_user(user)
    if not customer or not session_key:
        return 0
    qs = Cart.objects.filter(
        session_key=session_key,
        is_submitted=False,
        customer__isnull=True,
    )
    if brand_code:
        qs = qs.filter(brand__code=brand_code)
    return qs.update(customer=customer)


def attach_session_activity_to_user(user, session_key: str, brand_code: str | None = None) -> dict:
    """Backfill events and carts for a session key after authentication."""
    return {
        "events_linked": backfill_session_events_to_user(user, session_key),
        "carts_linked": link_session_carts_to_customer(user, session_key, brand_code),
    }
