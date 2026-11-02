"""Seasonal homepage campaign: public read and staff edit."""

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateTimeField
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import (
    HomepageCampaign,
    HomepageCampaignProduct,
    InventoryUnit,
    Product,
    ProductImage,
)
from inventory.permissions import IsContentCreatorOrInventoryManagerOrReadOnly
from inventory.serializers_public import PublicProductListSerializer

MAX_CAMPAIGN_PRODUCTS = 24
_DATETIME = DateTimeField()


def get_seasonal_campaign() -> HomepageCampaign:
    campaign, _created = HomepageCampaign.objects.get_or_create(
        key=HomepageCampaign.SEASONAL_KEY,
        defaults={
            "title": "Black November",
            "is_active": True,
            "animation": HomepageCampaign.Animation.NONE,
        },
    )
    return campaign


def campaign_is_live(campaign: HomepageCampaign, now=None) -> bool:
    now = now or timezone.now()
    if not campaign.is_active:
        return False
    if campaign.starts_at and now < campaign.starts_at:
        return False
    if campaign.ends_at and now > campaign.ends_at:
        return False
    return True


def load_ordered_products(campaign: HomepageCampaign, *, published_only: bool) -> list[Product]:
    product_ids = list(
        campaign.items.order_by("position", "id").values_list("product_id", flat=True)
    )
    if not product_ids:
        return []
    queryset = Product.objects.filter(id__in=product_ids)
    if published_only:
        queryset = queryset.filter(is_published=True, is_discontinued=False)
    queryset = queryset.prefetch_related(
        Prefetch(
            "images",
            queryset=ProductImage.objects.filter(is_primary=True),
            to_attr="primary_images_list",
        ),
        Prefetch(
            "inventory_units",
            queryset=InventoryUnit.objects.filter(
                sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                available_online=True,
            ),
            to_attr="available_units_list",
        ),
        "variants",
        "videos",
    )
    by_id = {product.id: product for product in queryset}
    return [by_id[product_id] for product_id in product_ids if product_id in by_id]


def serialize_products(products, request):
    return PublicProductListSerializer(
        products,
        many=True,
        context={
            "request": request,
            "view_action": "list",
            "_image_url_cache": {},
        },
    ).data


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_optional_datetime(value, field_name: str):
    if value in (None, ""):
        return None
    try:
        return _DATETIME.to_internal_value(value)
    except ValidationError as exc:
        raise ValidationError({field_name: exc.detail}) from exc


def _replace_products(campaign: HomepageCampaign, raw_ids) -> None:
    if not isinstance(raw_ids, list):
        raise ValidationError({"product_ids": ["Product ids must be a list."]})
    if len(raw_ids) > MAX_CAMPAIGN_PRODUCTS:
        raise ValidationError(
            {"product_ids": [f"Choose at most {MAX_CAMPAIGN_PRODUCTS} products."]}
        )
    ordered: list[int] = []
    for raw in raw_ids:
        try:
            product_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"product_ids": ["Each product id must be an integer."]}
            ) from exc
        if product_id not in ordered:
            ordered.append(product_id)
    found = set(Product.objects.filter(id__in=ordered).values_list("id", flat=True))
    missing = [product_id for product_id in ordered if product_id not in found]
    if missing:
        raise ValidationError({"product_ids": [f"Unknown product id(s): {missing}."]})
    HomepageCampaignProduct.objects.filter(campaign=campaign).delete()
    HomepageCampaignProduct.objects.bulk_create(
        [
            HomepageCampaignProduct(campaign=campaign, product_id=product_id, position=index)
            for index, product_id in enumerate(ordered)
        ]
    )


class PublicHomepageCampaignView(APIView):
    """Storefront seasonal row. Products are empty when the campaign is off or out of its window."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        campaign = get_seasonal_campaign()
        live = campaign_is_live(campaign)
        products = load_ordered_products(campaign, published_only=True) if live else []
        return Response(
            {
                "title": campaign.title,
                "animation": campaign.animation,
                "products": serialize_products(products, request) if products else [],
            }
        )


class StaffHomepageCampaignView(APIView):
    """Studio read/update for the seasonal campaign. Same roles as featured selection."""

    permission_classes = [IsContentCreatorOrInventoryManagerOrReadOnly]

    def get(self, request):
        campaign = get_seasonal_campaign()
        products = load_ordered_products(campaign, published_only=False)
        return Response(
            {
                "title": campaign.title,
                "animation": campaign.animation,
                "is_active": campaign.is_active,
                "starts_at": campaign.starts_at,
                "ends_at": campaign.ends_at,
                "products": serialize_products(products, request),
            }
        )

    def patch(self, request):
        campaign = get_seasonal_campaign()
        data = request.data if isinstance(request.data, dict) else {}

        if "title" in data:
            title = str(data.get("title") or "").strip()
            if not title:
                raise ValidationError({"title": ["Title is required."]})
            if len(title) > 80:
                raise ValidationError({"title": ["Title must be 80 characters or fewer."]})
            campaign.title = title

        if "animation" in data:
            animation = str(data.get("animation") or "").strip()
            allowed = {choice for choice, _label in HomepageCampaign.Animation.choices}
            if animation not in allowed:
                raise ValidationError(
                    {"animation": [f"Choose one of: {', '.join(sorted(allowed))}."]}
                )
            campaign.animation = animation

        if "is_active" in data:
            campaign.is_active = _parse_bool(data.get("is_active"))

        if "starts_at" in data:
            campaign.starts_at = _parse_optional_datetime(data.get("starts_at"), "starts_at")
        if "ends_at" in data:
            campaign.ends_at = _parse_optional_datetime(data.get("ends_at"), "ends_at")

        if campaign.starts_at and campaign.ends_at and campaign.ends_at < campaign.starts_at:
            raise ValidationError({"ends_at": ["End must be on or after the start."]})

        with transaction.atomic():
            if "product_ids" in data:
                _replace_products(campaign, data.get("product_ids"))
            campaign.save()

        products = load_ordered_products(campaign, published_only=False)
        return Response(
            {
                "title": campaign.title,
                "animation": campaign.animation,
                "is_active": campaign.is_active,
                "starts_at": campaign.starts_at,
                "ends_at": campaign.ends_at,
                "products": serialize_products(products, request),
            },
            status=status.HTTP_200_OK,
        )
