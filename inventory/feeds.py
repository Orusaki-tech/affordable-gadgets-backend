from __future__ import annotations

from decimal import Decimal
from typing import Optional
from urllib.parse import urljoin

from django.conf import settings
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.xmlutils import SimplerXMLGenerator

from inventory.models import Brand, InventoryUnit, InventoryUnitImage, ProductImage


def _normalize_site_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url.rstrip("/")


def _absolute_url(base_url: str, value: str) -> str:
    """
    Ensure value is an absolute https URL.
    - If value is already absolute, normalize to https.
    - If value is relative (e.g. /media/x.jpg), join to base_url.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    if raw.startswith("http://"):
        raw = "https://" + raw[len("http://") :]
    if raw.startswith(("http://", "https://")):
        return raw
    return urljoin(base_url.rstrip("/") + "/", raw.lstrip("/"))


def _get_site_base_url(request: HttpRequest, brand: Optional[Brand]) -> str:
    # Optional hard override so feeds fetched from ngrok still point to canonical domain.
    forced = _normalize_site_url(getattr(settings, "MERCHANT_FEED_SITE_BASE_URL", ""))
    if forced:
        return forced

    if brand and brand.ecommerce_domain:
        normalized = _normalize_site_url(brand.ecommerce_domain)
        if normalized:
            return normalized

    # Allow reusing existing frontend env var name too (common on deployments).
    public_site = _normalize_site_url(getattr(settings, "PUBLIC_SITE_URL", ""))
    if public_site:
        return public_site

    frontend = _normalize_site_url(getattr(settings, "FRONTEND_BASE_URL", ""))
    if frontend:
        return frontend

    # Last resort: derive from request host
    return _normalize_site_url(request.build_absolute_uri("/"))


def _get_media_base_url(site_base_url: str) -> str:
    """
    Base URL for media assets in the feed.

    If you always store images in Cloudinary, set:
      MERCHANT_FEED_MEDIA_BASE_URL=https://res.cloudinary.com/<cloud_name>/

    This is only used to resolve relative image paths (e.g. /media/..).
    Absolute URLs from storage are left as-is (normalized to https).
    """
    forced = _normalize_site_url(getattr(settings, "MERCHANT_FEED_MEDIA_BASE_URL", ""))
    return forced or site_base_url


def _cloudinary_url_from_name(name: str) -> str:
    """
    Build a direct Cloudinary delivery URL from a stored ImageField name/path.

    In some environments, even with Cloudinary configured, `image.url` can be a relative
    path like `/media/...` which Merchant Center rejects. Our DB typically stores a
    Cloudinary public-id-ish path in `image.name` (e.g. `media/product_photos/<public_id>`).
    """
    cloud_name = (
        (getattr(settings, "CLOUDINARY_CLOUD_NAME", "") or "").strip()
        or (getattr(settings, "CLOUDINARY_STORAGE", {}) or {}).get("CLOUD_NAME", "").strip()
    )
    raw = (name or "").strip().lstrip("/")
    if not cloud_name or not raw:
        return ""

    # Common: DB stores leading "media/" folder; strip it for cleaner public IDs.
    public_id = raw[len("media/") :] if raw.startswith("media/") else raw
    public_id = public_id.lstrip("/")

    # Cloudinary delivery URL (no version needed).
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}"


def _image_field_to_public_url(site_base_url: str, image_field) -> str:
    """
    Return an absolute https URL for a Django File/ImageField suitable for Merchant Center.
    """
    if not image_field:
        return ""

    media_base_url = _get_media_base_url(site_base_url)

    # 1) Prefer whatever storage gives us, if it's already absolute.
    try:
        raw_url = (image_field.url or "").strip()
    except Exception:
        raw_url = ""

    if raw_url.startswith(("http://", "https://", "//")):
        return _absolute_url(media_base_url, raw_url)

    # 2) If Cloudinary is configured, build a Cloudinary URL from the stored name.
    try:
        raw_name = (image_field.name or "").strip()
    except Exception:
        raw_name = ""

    cloudinary_url = _cloudinary_url_from_name(raw_name)
    if cloudinary_url:
        return cloudinary_url

    # 3) Last resort: make relative url/name absolute to media_base_url.
    return _absolute_url(media_base_url, raw_url or raw_name)


def _get_request_base_url(request: HttpRequest) -> str:
    """
    Base URL for resolving relative storage URLs coming from Django (e.g. /media/..).
    This should typically be the backend host (ngrok or your API domain), because that host
    is what actually serves /media/ in many deployments.
    """
    return _normalize_site_url(request.build_absolute_uri("/"))


def _get_brand_for_feed(request: HttpRequest) -> Optional[Brand]:
    header = request.headers.get("X-Brand-Code") or request.headers.get("x-brand-code")
    default_code = getattr(settings, "MERCHANT_FEED_BRAND_CODE", "") or "AFFORDABLE_GADGETS"
    brand_code = (header or default_code).strip()

    brand = None
    if brand_code:
        brand = Brand.objects.filter(code=brand_code, is_active=True).first()
        if brand:
            return brand

    # Fallback: prefer a brand that has an ecommerce domain set
    return Brand.objects.filter(is_active=True).exclude(ecommerce_domain="").first()


def _unit_condition_to_google(condition: str) -> str:
    # Google supported: new, used, refurbished
    mapping = {
        InventoryUnit.ConditionChoices.NEW: "new",
        InventoryUnit.ConditionChoices.REFURBISHED: "refurbished",
        InventoryUnit.ConditionChoices.PRE_OWNED: "used",
        InventoryUnit.ConditionChoices.DEFECTIVE: "used",
    }
    return mapping.get(condition, "used")


def _unit_availability_to_google(unit: InventoryUnit) -> str:
    if unit.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE and unit.available_online:
        if unit.product_template.product_type == unit.product_template.ProductType.ACCESSORY:
            return "in stock" if unit.quantity and unit.quantity > 0 else "out of stock"
        return "in stock"
    return "out of stock"


def _money_to_google(price: Decimal) -> str:
    # Merchant Center expects "12345.00 KES"
    try:
        quantized = price.quantize(Decimal("0.01"))
    except Exception:
        quantized = Decimal(str(price)).quantize(Decimal("0.01"))
    return f"{quantized} KES"


def _safe_text(value: str, max_len: int) -> str:
    text = strip_tags(value or "").strip()
    if not text:
        return ""
    return Truncator(text).chars(max_len, truncate="…")


def _pick_image_url(site_base_url: str, unit: InventoryUnit) -> str:
    # Prefer unit primary image, then any unit image, then product primary image, then any product image.
    unit_images = list(getattr(unit, "prefetched_images", []))
    if not unit_images and hasattr(unit, "images"):
        try:
            unit_images = list(unit.images.all())
        except Exception:
            unit_images = []

    primary_unit = next((img for img in unit_images if getattr(img, "is_primary", False)), None)
    chosen_unit = primary_unit or (unit_images[0] if unit_images else None)

    if chosen_unit and chosen_unit.image:
        try:
            return _image_field_to_public_url(site_base_url, chosen_unit.image)
        except Exception:
            pass

    product_images = list(getattr(unit.product_template, "prefetched_images", []))
    if not product_images and hasattr(unit.product_template, "images"):
        try:
            product_images = list(unit.product_template.images.all())
        except Exception:
            product_images = []

    primary_product = next((img for img in product_images if getattr(img, "is_primary", False)), None)
    chosen_product = primary_product or (product_images[0] if product_images else None)
    if chosen_product and chosen_product.image:
        try:
            return _image_field_to_public_url(site_base_url, chosen_product.image)
        except Exception:
            pass

    # Fallback to a known logo path on the frontend domain
    return _absolute_url(site_base_url, "affordablelogo.png")


def _build_unit_title(unit: InventoryUnit) -> str:
    parts = [unit.product_template.product_name]
    if unit.storage_gb:
        parts.append(f"{unit.storage_gb}GB")
    if unit.ram_gb:
        parts.append(f"{unit.ram_gb}GB RAM")
    if unit.product_color_id and getattr(unit.product_color, "name", None):
        parts.append(unit.product_color.name)
    # Condition/grade help disambiguate variants.
    cond = _unit_condition_to_google(unit.condition)
    if cond:
        parts.append(cond.title())
    if unit.grade:
        parts.append(f"Grade {unit.grade}")
    return " - ".join([p for p in parts if p])


def google_products_feed(request: HttpRequest) -> HttpResponse:
    """
    Google Merchant Center product feed (scheduled fetch).
    One item per sellable InventoryUnit (exact price + availability).
    """
    brand = _get_brand_for_feed(request)
    site_base_url = _get_site_base_url(request, brand)
    request_base_url = _get_request_base_url(request)

    qs = (
        InventoryUnit.objects.select_related("product_template", "product_color")
        .filter(
            available_online=True,
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            product_template__is_published=True,
            product_template__is_discontinued=False,
        )
        .prefetch_related(
            Prefetch(
                "images",
                queryset=InventoryUnitImage.objects.order_by("-is_primary", "id"),
                to_attr="prefetched_images",
            ),
            Prefetch(
                "product_template__images",
                queryset=ProductImage.objects.order_by("-is_primary", "display_order", "id"),
                to_attr="prefetched_images",
            ),
        )
        .order_by("id")
    )

    # Build XML response
    response = HttpResponse(content_type="application/rss+xml; charset=utf-8")
    generator = SimplerXMLGenerator(response, "utf-8")
    generator.startDocument()
    generator.startElement(
        "rss",
        {
            "version": "2.0",
            "xmlns:g": "http://base.google.com/ns/1.0",
        },
    )
    generator.startElement("channel", {})

    generator.addQuickElement("title", (brand.name if brand else "Affordable Gadgets Ke"))
    generator.addQuickElement("link", site_base_url)
    generator.addQuickElement(
        "description",
        "Google Merchant Center product feed generated from live inventory.",
    )
    generator.addQuickElement("lastBuildDate", timezone.now().strftime("%a, %d %b %Y %H:%M:%S %z"))

    for unit in qs.iterator(chunk_size=500):
        product = unit.product_template
        slug = product.slug
        if not slug:
            # Skip products without a stable frontend URL.
            continue

        product_link = _absolute_url(site_base_url, f"/products/{slug}")
        title = _build_unit_title(unit)
        description = _safe_text(
            product.meta_description
            or product.product_description
            or product.long_description
            or f"Shop {product.product_name} in Kenya.",
            4990,
        )

        image_link = _pick_image_url(site_base_url, unit)
        # If storage returned a relative URL (e.g. /media/...), resolve it to the backend host
        # so Merchant Center gets a valid absolute URL.
        if image_link.startswith("/"):
            image_link = _absolute_url(request_base_url, image_link)
        availability = _unit_availability_to_google(unit)
        condition = _unit_condition_to_google(unit.condition)

        price = unit.selling_price
        if price is None:
            continue

        generator.startElement("item", {})
        generator.addQuickElement("g:id", f"unit-{unit.id}")
        generator.addQuickElement("title", title)
        generator.addQuickElement("description", description)
        generator.addQuickElement("link", product_link)
        generator.addQuickElement("g:image_link", image_link)
        generator.addQuickElement("g:availability", availability)
        generator.addQuickElement("g:price", _money_to_google(price))
        generator.addQuickElement("g:condition", condition)
        generator.addQuickElement("g:brand", (product.brand or "N/A"))
        generator.addQuickElement("g:mpn", f"unit-{unit.id}")
        generator.addQuickElement("g:item_group_id", f"product-{product.id}")
        generator.endElement("item")

    generator.endElement("channel")
    generator.endElement("rss")
    generator.endDocument()

    return response

