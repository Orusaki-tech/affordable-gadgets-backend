from decimal import Decimal

from inventory.models import DeliveryRate

# Match storefront rules (CartPage): these counties need a ward for delivery.
WARDS_REQUIRED_COUNTIES = frozenset({"nairobi", "kiambu"})


class DeliveryResolutionError(Exception):
    """Structured delivery validation failure for serializers."""

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


def _normalize(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def get_delivery_fee(county, ward=None):
    county = _normalize(county)
    ward = _normalize(ward)

    if not county:
        return Decimal("0.00"), None

    if ward:
        ward_rate = DeliveryRate.objects.filter(
            county__iexact=county, ward__iexact=ward, is_active=True
        ).first()
        if ward_rate:
            return ward_rate.price, ward_rate

    county_rate = DeliveryRate.objects.filter(
        county__iexact=county, ward__isnull=True, is_active=True
    ).first()

    if not county_rate:
        county_rate = DeliveryRate.objects.filter(
            county__iexact=county, ward__exact="", is_active=True
        ).first()

    if county_rate:
        return county_rate.price, county_rate

    return Decimal("0.00"), None


def resolve_online_delivery(
    fulfillment_method=None,
    delivery_county=None,
    delivery_ward=None,
    delivery_address=None,
    delivery_window_start=None,
):
    """
    Resolve pickup vs delivery for online orders.

    Returns (fulfillment, fee) where fulfillment is \"PICKUP\" or \"DELIVERY\".
    Rejects delivery claims that omit county/ward or have no configured rate
    (previously those silently charged fee=0).
    """
    method = (_normalize(fulfillment_method) or "").upper()
    county = _normalize(delivery_county)
    ward = _normalize(delivery_ward)
    address = _normalize(delivery_address)
    has_delivery_signals = bool(county or address or delivery_window_start)

    if method not in {"PICKUP", "DELIVERY", ""}:
        raise DeliveryResolutionError(
            {"fulfillment_method": "Must be PICKUP or DELIVERY."}
        )

    if not method:
        method = "DELIVERY" if has_delivery_signals else "PICKUP"

    if method == "PICKUP":
        # Explicit pickup: fee is always 0 even if stale county fields remain in the payload.
        return "PICKUP", Decimal("0.00")

    # DELIVERY
    if not county:
        raise DeliveryResolutionError(
            {"delivery_county": "This field is required for delivery orders."}
        )

    if county.lower() in WARDS_REQUIRED_COUNTIES and not ward:
        raise DeliveryResolutionError(
            {"delivery_ward": "This field is required for the selected county."}
        )

    fee, rate = get_delivery_fee(county, ward)
    if rate is None:
        raise DeliveryResolutionError(
            {
                "delivery_county": (
                    "Delivery is not available for the selected location. "
                    "Choose a supported county/ward or pick up in store."
                )
            }
        )

    return "DELIVERY", fee
