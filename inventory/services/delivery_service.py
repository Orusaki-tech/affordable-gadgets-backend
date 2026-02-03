from decimal import Decimal

from inventory.models import DeliveryRate


def _normalize(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def get_delivery_fee(county, ward=None):
    county = _normalize(county)
    ward = _normalize(ward)

    if not county:
        return Decimal('0.00'), None

    if ward:
        ward_rate = DeliveryRate.objects.filter(
            county__iexact=county,
            ward__iexact=ward,
            is_active=True
        ).first()
        if ward_rate:
            return ward_rate.price, ward_rate

    county_rate = DeliveryRate.objects.filter(
        county__iexact=county,
        ward__isnull=True,
        is_active=True
    ).first()

    if not county_rate:
        county_rate = DeliveryRate.objects.filter(
            county__iexact=county,
            ward__exact='',
            is_active=True
        ).first()

    if county_rate:
        return county_rate.price, county_rate

    return Decimal('0.00'), None
