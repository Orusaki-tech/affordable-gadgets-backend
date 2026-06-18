"""Storefront product list ordering helpers."""

from __future__ import annotations

from django.db.models import F, QuerySet

VALID_ORDERING_FIELDS = frozenset(
    {
        "product_name",
        "min_price",
        "max_price",
        "release_date",
        "available_units_count",
        "id",
        "created_at",
    }
)


def apply_product_ordering(queryset: QuerySet, ordering_param: str | None) -> QuerySet:
    """Sort products by latest release date first by default."""
    if ordering_param:
        validated_ordering = []
        for field in (part.strip() for part in ordering_param.split(",") if part.strip()):
            field_name = field.lstrip("-")
            if field_name in VALID_ORDERING_FIELDS:
                validated_ordering.append(field)
        if validated_ordering:
            resolved = []
            for field in validated_ordering:
                if field.lstrip("-") == "release_date":
                    descending = field.startswith("-")
                    resolved.append(
                        F("release_date").desc(nulls_last=True)
                        if descending
                        else F("release_date").asc(nulls_last=True)
                    )
                else:
                    resolved.append(field)
            return queryset.order_by(*resolved)

    return queryset.order_by(F("release_date").desc(nulls_last=True), "-id")
