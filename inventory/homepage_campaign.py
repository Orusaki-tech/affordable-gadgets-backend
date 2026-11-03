"""Seasonal homepage campaign: public read and staff edit."""

import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateTimeField
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
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


def load_ordered_items(campaign: HomepageCampaign, *, published_only: bool):
    items = list(
        campaign.items.select_related("product").order_by("position", "id")
    )
    if published_only:
        items = [
            item
            for item in items
            if item.product.is_published and not item.product.is_discontinued
        ]
    if not items:
        return []
    product_ids = [item.product_id for item in items]
    queryset = Product.objects.filter(id__in=product_ids).prefetch_related(
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
    loaded = []
    for item in items:
        product = by_id.get(item.product_id)
        if product is None:
            continue
        item.product = product
        loaded.append(item)
    return loaded


def _promo_image_url(item: HomepageCampaignProduct, request) -> str | None:
    if not item.promo_image:
        return None
    try:
        url = item.promo_image.url
    except ValueError:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if request is None:
        return url
    return request.build_absolute_uri(url)


def serialize_campaign_items(items, request):
    products = [item.product for item in items]
    payload = PublicProductListSerializer(
        products,
        many=True,
        context={
            "request": request,
            "view_action": "list",
            "_image_url_cache": {},
        },
    ).data
    by_id = {item.product_id: item for item in items}
    for row in payload:
        item = by_id.get(row.get("id"))
        if item is None:
            continue
        row["promo_image_url"] = _promo_image_url(item, request)
        row["promo_price"] = float(item.promo_price) if item.promo_price is not None else None
    return payload


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


def _parse_price(value, field_name="promo_price"):
    if value in (None, ""):
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError({field_name: ["Enter a valid price."]}) from exc
    if price < 0:
        raise ValidationError({field_name: ["Price cannot be negative."]})
    return price.quantize(Decimal("0.01"))


def _parse_membership(data):
    """Return (ordered product ids, prices by id or None to preserve existing prices)."""
    if "products" in data:
        raw = data.get("products")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValidationError({"products": ["Products must be valid JSON."]}) from exc
        if not isinstance(raw, list):
            raise ValidationError({"products": ["Products must be a list."]})
        ordered: list[int] = []
        prices: dict[int, Decimal | None] = {}
        for entry in raw:
            if isinstance(entry, dict):
                raw_id = entry.get("product_id", entry.get("id"))
                price = _parse_price(entry.get("promo_price"))
            else:
                raw_id = entry
                price = None
            try:
                product_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    {"products": ["Each product id must be an integer."]}
                ) from exc
            if product_id in prices:
                continue
            ordered.append(product_id)
            prices[product_id] = price
        return ordered, prices

    raw_ids = data.get("product_ids")
    if not isinstance(raw_ids, list):
        raise ValidationError({"product_ids": ["Product ids must be a list."]})
    ordered = []
    for raw in raw_ids:
        try:
            product_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"product_ids": ["Each product id must be an integer."]}
            ) from exc
        if product_id not in ordered:
            ordered.append(product_id)
    return ordered, None


def _sync_products(campaign: HomepageCampaign, ordered: list[int], prices) -> None:
    if len(ordered) > MAX_CAMPAIGN_PRODUCTS:
        raise ValidationError(
            {"products": [f"Choose at most {MAX_CAMPAIGN_PRODUCTS} products."]}
        )
    found = set(Product.objects.filter(id__in=ordered).values_list("id", flat=True))
    missing = [product_id for product_id in ordered if product_id not in found]
    if missing:
        raise ValidationError({"products": [f"Unknown product id(s): {missing}."]})

    existing = {row.product_id: row for row in campaign.items.all()}
    keep_ids = []
    for index, product_id in enumerate(ordered):
        row = existing.get(product_id)
        if row is None:
            row = HomepageCampaignProduct(campaign=campaign, product_id=product_id)
        row.position = index
        if prices is not None:
            row.promo_price = prices.get(product_id)
        row.save()
        keep_ids.append(row.pk)

    removed = campaign.items.exclude(pk__in=keep_ids)
    for row in removed:
        if row.promo_image:
            row.promo_image.delete(save=False)
    removed.delete()


def _apply_promo_images(campaign: HomepageCampaign, request) -> None:
    clear_raw = request.data.getlist("clear_promo_image") if hasattr(request.data, "getlist") else []
    if not clear_raw and "clear_promo_image" in request.data:
        single = request.data.get("clear_promo_image")
        clear_raw = single if isinstance(single, list) else [single]
    clear_ids = set()
    for raw in clear_raw:
        try:
            clear_ids.add(int(raw))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"clear_promo_image": ["Each id must be an integer."]}
            ) from exc

    rows = {row.product_id: row for row in campaign.items.all()}
    for product_id in clear_ids:
        row = rows.get(product_id)
        if row and row.promo_image:
            row.promo_image.delete(save=True)

    for key, uploaded in request.FILES.items():
        if not str(key).startswith("promo_image_"):
            continue
        try:
            product_id = int(str(key).removeprefix("promo_image_"))
        except ValueError as exc:
            raise ValidationError({"promo_image": ["Image field name is invalid."]}) from exc
        row = rows.get(product_id)
        if row is None:
            raise ValidationError(
                {"promo_image": [f"Add product {product_id} before uploading its image."]}
            )
        if row.promo_image:
            row.promo_image.delete(save=False)
        row.promo_image = uploaded
        row.save(update_fields=["promo_image"])


def _campaign_payload(campaign: HomepageCampaign, request, *, published_only: bool, live: bool):
    items = load_ordered_items(campaign, published_only=published_only) if live else []
    return {
        "title": campaign.title,
        "animation": campaign.animation,
        "is_active": campaign.is_active,
        "starts_at": campaign.starts_at,
        "ends_at": campaign.ends_at,
        "products": serialize_campaign_items(items, request) if items else [],
    }


class PublicHomepageCampaignView(APIView):
    """Storefront seasonal row. Products are empty when the campaign is off or out of its window."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        campaign = get_seasonal_campaign()
        live = campaign_is_live(campaign)
        # Every product chosen in Studio is shown, including drafts that are
        # not on the public catalog yet.
        payload = _campaign_payload(campaign, request, published_only=False, live=live)
        return Response(
            {
                "title": payload["title"],
                "animation": payload["animation"],
                "products": payload["products"],
            }
        )


class StaffHomepageCampaignView(APIView):
    """Studio read/update for the seasonal campaign. Same roles as featured selection."""

    permission_classes = [IsContentCreatorOrInventoryManagerOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        campaign = get_seasonal_campaign()
        return Response(
            _campaign_payload(campaign, request, published_only=False, live=True)
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
            if "products" in data or "product_ids" in data:
                ordered, prices = _parse_membership(data)
                _sync_products(campaign, ordered, prices)
            _apply_promo_images(campaign, request)
            campaign.save()

        return Response(
            _campaign_payload(campaign, request, published_only=False, live=True),
            status=status.HTTP_200_OK,
        )
