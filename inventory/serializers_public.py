"""Public API serializers for e-commerce frontend."""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer, OpenApiTypes
from decimal import Decimal
from django.db.models import Q, Sum, Avg, Min
from django.utils import timezone
from inventory.models import Product, InventoryUnit, Cart, CartItem, Lead, LeadItem, Promotion, Bundle, BundleItem, ProductImage, Review, WishlistItem, DeliveryRate, Order, OrderItem
from inventory.services.interest_service import InterestService
import logging

logger = logging.getLogger(__name__)


@extend_schema_serializer(component_name="PublicInventoryUnitPublic")
class PublicInventoryUnitSerializer(serializers.ModelSerializer):
    """Public unit serializer with interest count."""
    interest_count = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product_template.product_name', read_only=True)
    product_id = serializers.IntegerField(source='product_template.id', read_only=True)
    product_slug = serializers.CharField(source='product_template.slug', read_only=True)
    color_name = serializers.CharField(source='product_color.name', read_only=True, allow_null=True)
    images = serializers.SerializerMethodField()
    
    class Meta:
        model = InventoryUnit
        fields = [
            'id', 'product_id', 'product_name', 'product_slug', 'selling_price', 'compare_at_price',
            'condition', 'grade', 'storage_gb', 'ram_gb', 'battery_mah', 'product_color',
            'color_name', 'interest_count', 'images'
        ]
    
    @extend_schema_field(OpenApiTypes.INT)
    def get_interest_count(self, obj):
        # Use annotated value when provided by the view (avoids N+1)
        if hasattr(obj, 'interest_count'):
            return obj.interest_count
        return InterestService.get_interest_count(obj)
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_images(self, obj):
        """Return list of image URLs for this unit with color information. Use prefetched images (order set by view)."""
        from inventory.cloudinary_utils import get_optimized_image_url
        request = self.context.get('request')
        # Avoid .order_by() so the prefetched cache is used (order already applied in view's Prefetch)
        images = obj.images.all()
        result = []
        for img in images:
            if img.image:
                original_url = img.image.url
                cloudinary_url = get_optimized_image_url(img.image)
                thumbnail_url = get_optimized_image_url(img.image, width=200, height=200)
                
                # Build absolute URLs for local files
                if (original_url.startswith('/media/') or original_url.startswith('/static/')) and request:
                    absolute_url = request.build_absolute_uri(original_url)
                    absolute_thumbnail = request.build_absolute_uri(original_url)  # Same URL for thumbnail
                    # Use Cloudinary if available, otherwise absolute local URL
                    final_url = cloudinary_url if (cloudinary_url and cloudinary_url != original_url and 'cloudinary.com' in cloudinary_url) else absolute_url
                    final_thumbnail = thumbnail_url if (thumbnail_url and thumbnail_url != original_url and 'cloudinary.com' in thumbnail_url) else absolute_thumbnail
                else:
                    final_url = cloudinary_url
                    final_thumbnail = thumbnail_url
                
                result.append({
                    'id': img.id,
                    'image_url': final_url,
                    'thumbnail_url': final_thumbnail,
                    'is_primary': img.is_primary,
                    'color_id': img.color.id if img.color else None,
                    'color_name': img.color.name if img.color else None,
                    'created_at': img.created_at.isoformat() if img.created_at else None
                })
        return result


class ReviewOtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class ReviewEligibilityRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6)


class OrderOtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class OrderHistoryRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6)


class ReviewEligibilityItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_slug = serializers.CharField(allow_blank=True, required=False)
    order_id = serializers.UUIDField()
    order_item_id = serializers.IntegerField()
    purchase_date = serializers.DateField(allow_null=True, required=False)


class PublicOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='inventory_unit.product_template.product_name', read_only=True)
    sub_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'quantity', 'unit_price_at_purchase', 'sub_total']

    def get_sub_total(self, obj):
        return obj.unit_price_at_purchase * obj.quantity


class PublicOrderSerializer(serializers.ModelSerializer):
    order_items = PublicOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_id', 'created_at', 'status', 'total_amount',
            'delivery_address', 'delivery_county', 'delivery_ward', 'delivery_fee',
            'delivery_window_start', 'delivery_window_end', 'delivery_notes',
            'order_items'
        ]


class PublicReviewSubmitSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6)
    product_id = serializers.IntegerField()
    order_item_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField()
    review_image = serializers.ImageField(required=False, allow_null=True)
    video_url = serializers.URLField(required=False, allow_null=True)


class PublicProductSerializer(serializers.ModelSerializer):
    """Public product serializer (stripped down)."""
    available_units_count = serializers.SerializerMethodField()
    interest_count = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    compare_at_min_price = serializers.SerializerMethodField()
    compare_at_max_price = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    has_active_bundle = serializers.SerializerMethodField()
    bundle_price_preview = serializers.SerializerMethodField()
    product_highlights = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
        required=False
    )
    long_description = serializers.CharField(read_only=True, required=False)
    
    class Meta:
        model = Product
        fields = [
            'id', 'product_name', 'brand', 'model_series', 'product_type',
            'product_description', 'long_description', 'product_highlights',
            'available_units_count', 'interest_count', 'min_price', 'max_price',
            'compare_at_min_price', 'compare_at_max_price', 'discount_percent',
            'review_count', 'average_rating',
            'primary_image', 'slug', 'product_video_url', 'tags', 'has_active_bundle', 'bundle_price_preview',
            'meta_title', 'meta_description'  # SEO fields
        ]
    
    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_tags(self, obj):
        """Return list of tag names."""
        return [tag.name for tag in obj.tags.all()]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_active_bundle(self, obj):
        # Use annotated value from view when present (avoids N+1 on list).
        if hasattr(obj, 'has_active_bundle'):
            return bool(obj.has_active_bundle)
        # Use prefetched list from view when available (avoids N+1).
        active = getattr(obj, 'active_bundles_list', None)
        if active is not None:
            return len(active) > 0
        from inventory.models import Bundle
        from django.utils import timezone
        brand = self.context.get('brand')
        now = timezone.now()
        queryset = Bundle.objects.filter(
            main_product=obj,
            is_active=True,
            show_in_listings=True
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now),
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        if brand:
            queryset = queryset.filter(brand=brand)
        return queryset.exists()

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_bundle_price_preview(self, obj):
        """Return minimum effective bundle price for listings (if available)."""
        # Use prefetched list from view when available (avoids N+1).
        bundles_prefetched = getattr(obj, 'active_bundles_list', None)
        if bundles_prefetched is not None:
            bundles = list(bundles_prefetched)
        else:
            brand = self.context.get('brand')
            now = timezone.now()
            bundles = Bundle.objects.filter(
                main_product=obj,
                is_active=True,
                show_in_listings=True
            ).filter(
                Q(start_date__isnull=True) | Q(start_date__lte=now),
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            )
            if brand:
                bundles = bundles.filter(brand=brand)
            bundles = bundles.prefetch_related('items__product')

        # Collect product ids that need min_price from DB (bundle item products not in main list)
        product_ids_needing_min = set()
        for bundle in bundles:
            for item in bundle.items.all():
                if item.override_price is not None:
                    continue
                p = item.product
                if getattr(p, 'min_price', None) is None and p is not None:
                    product_ids_needing_min.add(p.id)
        # Single query for min selling_price per product (avoids N+1)
        min_price_by_product = {}
        if product_ids_needing_min:
            rows = (
                InventoryUnit.objects.filter(
                    product_template_id__in=product_ids_needing_min,
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    available_online=True,
                )
                .values('product_template_id')
                .annotate(min_p=Min('selling_price'))
            )
            min_price_by_product = {r['product_template_id']: r['min_p'] for r in rows}

        def items_min_total(bundle):
            total = Decimal('0.00')
            for item in bundle.items.all():
                if item.override_price is not None:
                    price = Decimal(str(item.override_price))
                else:
                    min_price = getattr(item.product, 'min_price', None)
                    if min_price is None and item.product_id:
                        min_price = min_price_by_product.get(item.product_id)
                    if min_price is None:
                        return None
                    price = Decimal(str(min_price))
                total += price * item.quantity
            return total

        best_price = None
        for bundle in bundles:
            if bundle.pricing_mode == Bundle.PricingMode.FIXED and bundle.bundle_price is not None:
                price = Decimal(str(bundle.bundle_price))
            else:
                base_total = items_min_total(bundle)
                if base_total is None:
                    continue
                if bundle.pricing_mode == Bundle.PricingMode.PERCENT and bundle.discount_percentage is not None:
                    discount = (base_total * Decimal(str(bundle.discount_percentage))) / Decimal('100')
                    price = max(Decimal('0.00'), base_total - discount)
                elif bundle.pricing_mode == Bundle.PricingMode.AMOUNT and bundle.discount_amount is not None:
                    price = max(Decimal('0.00'), base_total - Decimal(str(bundle.discount_amount)))
                else:
                    price = base_total
            if best_price is None or price < best_price:
                best_price = price
        return float(best_price) if best_price is not None else None
    
    @extend_schema_field(OpenApiTypes.INT)
    def get_available_units_count(self, obj):
        """Count available units for current brand - use prefetched list for accurate brand filtering."""
        # List view: use only prefetched data to avoid N+1 (never hit DB)
        if self.context.get('view_action') == 'list':
            units = getattr(obj, 'available_units_list', None)
            if units is None:
                return 0
            if obj.product_type == Product.ProductType.ACCESSORY:
                return sum(unit.quantity for unit in units)
            return len(units)
        # Use prefetched available_units_list if available (correctly filtered by brand)
        if getattr(obj, 'available_units_list', None) is not None:
            units = obj.available_units_list
            if obj.product_type == Product.ProductType.ACCESSORY:
                return sum(unit.quantity for unit in units)
            return len(units)
        # Fallback to annotation (may not be brand-filtered correctly)
        if hasattr(obj, 'available_units_count'):
            return obj.available_units_count or 0
        # Final fallback: query directly (detail/other only)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        if obj.product_type == Product.ProductType.ACCESSORY:
            return units.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        return units.count()
    
    @extend_schema_field(OpenApiTypes.INT)
    def get_interest_count(self, obj):
        """Get total interest count for product - optimized version."""
        # Use prefetched available units if available
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
        else:
            # Fallback
            brand = self.context.get('brand')
            units = obj.inventory_units.filter(
                sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                available_online=True
            )
            if brand:
                units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
            units = list(units)
        
        # Calculate interest count more efficiently
        if not units:
            return 0
        
        from inventory.models import Lead
        from django.utils import timezone
        active_statuses = [Lead.StatusChoices.NEW, Lead.StatusChoices.CONTACTED]
        unit_ids = [unit.id for unit in units]
        
        # Single query for all units
        return Lead.objects.filter(
            items__inventory_unit_id__in=unit_ids,
            status__in=active_statuses,
            expires_at__gt=timezone.now()
        ).distinct().count()
    
    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_min_price(self, obj):
        """Get min price for available units - use annotation when present (list), else prefetched list or query."""
        # List view: prefer annotation to avoid iterating available_units_list
        if self.context.get('view_action') == 'list' and getattr(obj, 'min_price', None) is not None:
            return float(obj.min_price)
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
            if units:
                prices = [float(unit.selling_price) for unit in units]
                return min(prices) if prices else None
        if self.context.get('view_action') == 'list':
            return None
        # Fallback to annotation (may not be brand-filtered correctly)
        if hasattr(obj, 'min_price') and obj.min_price is not None:
            return float(obj.min_price)
        # Final fallback: query directly (detail only)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        prices = units.values_list('selling_price', flat=True)
        return float(min(prices)) if prices else None
    
    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_max_price(self, obj):
        """Get max price for available units - use annotation when present (list), else prefetched list or query."""
        if self.context.get('view_action') == 'list' and getattr(obj, 'max_price', None) is not None:
            return float(obj.max_price)
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
            if units:
                prices = [float(unit.selling_price) for unit in units]
                return max(prices) if prices else None
        if self.context.get('view_action') == 'list':
            return None
        # Fallback to annotation (may not be brand-filtered correctly)
        if hasattr(obj, 'max_price') and obj.max_price is not None:
            return float(obj.max_price)
        # Final fallback: query directly (detail only)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        prices = units.values_list('selling_price', flat=True)
        return float(max(prices)) if prices else None

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_compare_at_min_price(self, obj):
        """Get min compare-at price for available units."""
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
            prices = [float(unit.compare_at_price) for unit in units if unit.compare_at_price is not None]
            return min(prices) if prices else None
        if self.context.get('view_action') == 'list':
            return float(obj.compare_at_min_price) if getattr(obj, 'compare_at_min_price', None) is not None else None
        if hasattr(obj, 'compare_at_min_price') and obj.compare_at_min_price is not None:
            return float(obj.compare_at_min_price)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True,
            compare_at_price__isnull=False
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        prices = units.values_list('compare_at_price', flat=True)
        return float(min(prices)) if prices else None

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_compare_at_max_price(self, obj):
        """Get max compare-at price for available units."""
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
            prices = [float(unit.compare_at_price) for unit in units if unit.compare_at_price is not None]
            return max(prices) if prices else None
        if self.context.get('view_action') == 'list':
            return float(obj.compare_at_max_price) if getattr(obj, 'compare_at_max_price', None) is not None else None
        if hasattr(obj, 'compare_at_max_price') and obj.compare_at_max_price is not None:
            return float(obj.compare_at_max_price)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True,
            compare_at_price__isnull=False
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        prices = units.values_list('compare_at_price', flat=True)
        return float(max(prices)) if prices else None

    @extend_schema_field(OpenApiTypes.INT)
    def get_discount_percent(self, obj):
        compare_min = self.get_compare_at_min_price(obj)
        min_price = self.get_min_price(obj)
        if compare_min is None or min_price is None:
            return None
        if compare_min <= 0 or compare_min <= min_price:
            return None
        return int(round(((compare_min - min_price) / compare_min) * 100))

    @extend_schema_field(OpenApiTypes.INT)
    def get_review_count(self, obj):
        # Use annotated value when present (detail view)
        if hasattr(obj, 'review_count'):
            return int(obj.review_count) if obj.review_count is not None else 0
        # Use prefetched reviews when present (list view; avoids N+1)
        prefetched = getattr(obj, 'reviews_for_aggregates', None)
        if prefetched is not None:
            return len(prefetched)
        return Review.objects.filter(product=obj).count()

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_average_rating(self, obj):
        # Use annotated value when present (detail view)
        if hasattr(obj, 'average_rating'):
            return float(obj.average_rating) if obj.average_rating is not None else None
        # Use prefetched reviews when present (list view; avoids N+1)
        prefetched = getattr(obj, 'reviews_for_aggregates', None)
        if prefetched is not None:
            if not prefetched:
                return None
            total = sum(r.rating for r in prefetched)
            return round(total / len(prefetched), 2)
        aggregate = Review.objects.filter(product=obj).aggregate(avg=Avg('rating'))
        value = aggregate.get('avg')
        return float(value) if value is not None else None
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_primary_image(self, obj):
        """Get primary product image URL - use prefetched data if available."""
        from inventory.cloudinary_utils import get_optimized_image_url
        # List view: use only prefetched primary_images_list (no fallback to avoid extra query)
        if self.context.get('view_action') == 'list':
            pl = getattr(obj, 'primary_images_list', None)
            primary_image = pl[0] if pl and len(pl) > 0 else None
        else:
            pl = getattr(obj, 'primary_images_list', None)
            if pl and len(pl) > 0:
                primary_image = pl[0]
            else:
                images = list(obj.images.all())
                primary_image = next((img for img in images if img.is_primary), None) or (images[0] if images else None)
        
        if primary_image and primary_image.image:
            request = self.context.get('request')
            url_cache = self.context.get('_image_url_cache')
            # Cache key: avoid repeated get_optimized_image_url for same image in list views
            cache_key = None
            if url_cache is not None:
                cache_key = getattr(primary_image.image, 'name', None) or getattr(primary_image.image, 'url', None)

            def _optimized_url():
                if cache_key is not None and cache_key in url_cache:
                    return url_cache[cache_key]
                u = get_optimized_image_url(primary_image.image)
                if cache_key is not None:
                    url_cache[cache_key] = u
                return u

            if request:
                original_url = primary_image.image.url
                if original_url.startswith('/media/') or original_url.startswith('/static/'):
                    absolute_url = request.build_absolute_uri(original_url)
                    cloudinary_url = _optimized_url()
                    if cloudinary_url and cloudinary_url != original_url and 'cloudinary.com' in (cloudinary_url or ''):
                        return cloudinary_url
                    return absolute_url
            return _optimized_url()
        return None


class PublicProductListSerializer(PublicProductSerializer):
    """Lightweight product serializer for list endpoints."""

    class Meta(PublicProductSerializer.Meta):
        fields = [
            'id', 'product_name', 'brand', 'model_series', 'product_type',
            'available_units_count', 'min_price', 'max_price',
            'compare_at_min_price', 'compare_at_max_price', 'discount_percent',
            'review_count', 'average_rating',
            'primary_image', 'slug', 'product_video_url', 'has_active_bundle', 'bundle_price_preview'
        ]


class PublicWishlistItemSerializer(serializers.ModelSerializer):
    """Public wishlist item serializer."""
    product = PublicProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = WishlistItem
        fields = ['id', 'product', 'product_id', 'created_at']


class CartItemSerializer(serializers.ModelSerializer):
    """Cart item serializer."""
    inventory_unit = PublicInventoryUnitSerializer(read_only=True)
    inventory_unit_id = serializers.IntegerField(write_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    promotion_id = serializers.IntegerField(source='promotion.id', read_only=True, allow_null=True)
    bundle_id = serializers.IntegerField(source='bundle.id', read_only=True, allow_null=True)
    bundle_group_id = serializers.UUIDField(read_only=True, allow_null=True)
    
    class Meta:
        model = CartItem
        fields = ['id', 'inventory_unit', 'inventory_unit_id', 'quantity', 'unit_price', 'promotion_id', 'bundle_id', 'bundle_group_id']


class CartSerializer(serializers.ModelSerializer):
    """Cart serializer."""
    items = CartItemSerializer(many=True, read_only=True)
    total_value = serializers.SerializerMethodField()
    total_with_delivery = serializers.SerializerMethodField()
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    delivery_county = serializers.CharField(read_only=True)
    delivery_ward = serializers.CharField(read_only=True)
    delivery_window_start = serializers.DateTimeField(read_only=True)
    delivery_window_end = serializers.DateTimeField(read_only=True)
    delivery_notes = serializers.CharField(read_only=True)
    
    class Meta:
        model = Cart
        fields = [
            'id', 'items', 'customer_name', 'customer_phone', 'customer_email',
            'delivery_address', 'delivery_county', 'delivery_ward', 'delivery_fee',
            'delivery_window_start', 'delivery_window_end', 'delivery_notes',
            'total_value', 'total_with_delivery', 'expires_at', 'is_submitted'
        ]
    
    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_total_value(self, obj):
        total = Decimal('0.00')
        for item in obj.items.all():
            unit_price = item.get_unit_price()  # Use stored promotion price
            total += unit_price * item.quantity
        return float(total)

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_total_with_delivery(self, obj):
        items_total = Decimal(str(self.get_total_value(obj)))
        return float(items_total + (obj.delivery_fee or Decimal('0.00')))


# -------------------------------------------------------------------------
# BUNDLE SERIALIZERS (PUBLIC)
# -------------------------------------------------------------------------

class PublicBundleItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_type = serializers.CharField(source='product.product_type', read_only=True)
    primary_image = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    
    class Meta:
        model = BundleItem
        fields = [
            'id', 'product_id', 'product_name', 'product_slug', 'product_type',
            'quantity', 'override_price', 'display_order', 'primary_image',
            'min_price', 'max_price'
        ]

    def _get_price_range(self, product: Product):
        # Check if min_price and max_price annotations exist (from queryset annotations)
        if hasattr(product, 'min_price') and hasattr(product, 'max_price'):
            if product.min_price is not None and product.max_price is not None:
                return product.min_price, product.max_price
        # Fallback: query units directly to calculate price range
        units = InventoryUnit.objects.filter(product_template=product, sale_status='AV', available_online=True)
        if not units.exists():
            return None, None
        prices = list(units.values_list('selling_price', flat=True))
        return min(prices), max(prices)

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_min_price(self, obj):
        min_price, _ = self._get_price_range(obj.product)
        return min_price

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_max_price(self, obj):
        _, max_price = self._get_price_range(obj.product)
        return max_price

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_primary_image(self, obj):
        from inventory.cloudinary_utils import get_optimized_image_url
        primary_image = ProductImage.objects.filter(product=obj.product, is_primary=True).first()
        if primary_image and primary_image.image:
            original_url = primary_image.image.url
            cloudinary_url = get_optimized_image_url(primary_image.image)
            return cloudinary_url or original_url
        return None


class PublicBundleSerializer(serializers.ModelSerializer):
    items = PublicBundleItemSerializer(many=True, read_only=True)
    main_product_id = serializers.IntegerField(source='main_product.id', read_only=True)
    main_product_name = serializers.CharField(source='main_product.product_name', read_only=True)
    main_product_slug = serializers.CharField(source='main_product.slug', read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)
    items_min_total = serializers.SerializerMethodField()
    items_max_total = serializers.SerializerMethodField()
    
    class Meta:
        model = Bundle
        fields = [
            'id', 'brand', 'main_product_id', 'main_product_name', 'main_product_slug',
            'title', 'description', 'pricing_mode', 'bundle_price', 'discount_percentage',
            'discount_amount', 'show_in_listings', 'is_currently_active',
            'items', 'items_min_total', 'items_max_total'
        ]

    def _get_items_total(self, obj):
        min_total = Decimal('0.00')
        max_total = Decimal('0.00')
        for item in obj.items.all():
            if item.override_price is not None:
                price = Decimal(str(item.override_price))
                min_total += price * item.quantity
                max_total += price * item.quantity
                continue
            # Check if min_price and max_price annotations exist (from queryset annotations)
            min_price = None
            max_price = None
            if hasattr(item.product, 'min_price') and hasattr(item.product, 'max_price'):
                min_price = item.product.min_price
                max_price = item.product.max_price
            # If annotations don't exist or are None, query units directly
            if min_price is None or max_price is None:
                units = InventoryUnit.objects.filter(product_template=item.product, sale_status='AV', available_online=True)
                if units.exists():
                    prices = list(units.values_list('selling_price', flat=True))
                    min_price = min(prices)
                    max_price = max(prices)
            if min_price is not None:
                min_total += Decimal(str(min_price)) * item.quantity
            if max_price is not None:
                max_total += Decimal(str(max_price)) * item.quantity
        return min_total, max_total

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_items_min_total(self, obj):
        min_total, _ = self._get_items_total(obj)
        return min_total

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_items_max_total(self, obj):
        _, max_total = self._get_items_total(obj)
        return max_total


class LeadItemSerializer(serializers.ModelSerializer):
    """Lead item serializer for public API."""
    product_name = serializers.CharField(source='inventory_unit.product_template.product_name', read_only=True)
    
    class Meta:
        model = LeadItem
        fields = ['product_name', 'quantity', 'unit_price']


class LeadSerializer(serializers.ModelSerializer):
    """Lead serializer for public API (limited fields)."""
    items = LeadItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'lead_reference', 'status', 'submitted_at', 'total_value', 'items'
        ]
        read_only_fields = ['lead_reference', 'status', 'submitted_at', 'total_value']


class CheckoutSerializer(serializers.Serializer):
    """Serializer for checkout (cart to lead conversion)."""
    customer_name = serializers.CharField(max_length=255)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    delivery_county = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    delivery_ward = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    delivery_window_start = serializers.DateTimeField(required=False, allow_null=True)
    delivery_window_end = serializers.DateTimeField(required=False, allow_null=True)
    delivery_notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CartCreateSerializer(serializers.Serializer):
    """Serializer for cart creation (session + customer context)."""
    session_key = serializers.CharField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)


class CartItemCreateSerializer(serializers.Serializer):
    """Serializer for adding items to cart."""
    inventory_unit_id = serializers.IntegerField()
    quantity = serializers.IntegerField(required=False, default=1)
    promotion_id = serializers.IntegerField(required=False, allow_null=True)
    unit_price = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=2)


class CartBundleCreateSerializer(serializers.Serializer):
    """Serializer for adding a bundle to cart."""
    bundle_id = serializers.IntegerField()
    main_inventory_unit_id = serializers.IntegerField(required=False, allow_null=True)
    bundle_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )


class CheckoutResponseSerializer(serializers.Serializer):
    """Serializer for checkout response."""
    message = serializers.CharField()
    lead_reference = serializers.CharField()
    lead = LeadSerializer()


class PublicDeliveryRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRate
        fields = ['id', 'county', 'ward', 'price']


class PublicPromotionSerializer(serializers.ModelSerializer):
    """Public promotion serializer (limited fields)."""
    is_currently_active = serializers.BooleanField(read_only=True)
    discount_display = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    banner_image_url = serializers.SerializerMethodField(read_only=True)
    banner_image = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Promotion
        fields = (
            'id', 'title', 'description', 'banner_image', 'banner_image_url',
            'discount_percentage', 'discount_amount', 'discount_display',
            'start_date', 'end_date', 'is_currently_active', 'product_types',
            'display_locations', 'carousel_position', 'products'
        )
        read_only_fields = ('is_currently_active', 'discount_display', 'products', 'banner_image_url', 'banner_image')
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_banner_image(self, obj):
        """Return optimized banner image URL (prefer Cloudinary, fallback to absolute URL)"""
        if obj.banner_image:
            from inventory.cloudinary_utils import get_promotion_image_url
            import os
            import cloudinary
            from cloudinary import CloudinaryImage
            request = self.context.get('request')
            
            # Get the URL from the field - Cloudinary storage should return Cloudinary URL
            original_url = obj.banner_image.url
            
            # If already a Cloudinary URL, add transformations to it directly
            # This preserves the correct public_id that the storage backend knows about
            if 'cloudinary.com' in original_url or 'res.cloudinary.com' in original_url:
                # Use the URL from storage backend and add transformations
                # This avoids reconstructing the URL which might use wrong public_id
                try:
                    # Parse the URL and add transformations
                    if '/upload/' in original_url:
                        parts = original_url.split('/upload/')
                        if len(parts) == 2:
                            after_upload = parts[1]
                            # Build transformation string
                            transform_str = 'c_fill,h_1200,q_auto,w_1200'
                            
                            # Check if transformations already exist
                            path_parts = after_upload.split('/')
                            if path_parts and (',' in path_parts[0] or any(x in path_parts[0] for x in ['w_', 'h_', 'c_', 'q_', 'f_'])):
                                # Replace existing transformations
                                path_parts[0] = transform_str
                                new_after_upload = '/'.join(path_parts)
                            else:
                                # Add new transformations before the path
                                new_after_upload = f'{transform_str}/{after_upload}'
                            
                            optimized_url = f"{parts[0]}/upload/{new_after_upload}"
                            return optimized_url
                except Exception as e:
                    logger.warning(f"Failed to add transformations to Cloudinary URL: {e}. Using original URL.")
                    # Fall back to using get_optimized_image_url
                    cloudinary_url = get_promotion_image_url(obj.banner_image, size='lg', crop='fill')
                    return cloudinary_url if cloudinary_url else original_url
                
                # If parsing failed, try the utility function
                cloudinary_url = get_promotion_image_url(obj.banner_image, size='lg', crop='fill')
                return cloudinary_url if cloudinary_url else original_url
            
            # If URL is local (relative or absolute), try to construct Cloudinary URL from image name
            # This handles cases where images were uploaded before Cloudinary was configured
            is_local_path = (original_url.startswith('/media/') or original_url.startswith('/static/') or 
                           '/media/' in original_url or '/static/' in original_url)
            # Always try Cloudinary URL construction if we detect a local path
            # This handles images uploaded before Cloudinary was configured
            if is_local_path:
                if hasattr(obj.banner_image, 'name') and obj.banner_image.name:
                    try:
                        # Configure Cloudinary
                        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
                        api_key = os.environ.get('CLOUDINARY_API_KEY')
                        api_secret = os.environ.get('CLOUDINARY_API_SECRET')
                        cloudinary.config(
                            cloud_name=cloud_name,
                            api_key=api_key,
                            api_secret=api_secret,
                            secure=True
                        )
                        
                        # Get public_id from the image field name
                        # Cloudinary storage uses the upload_to path + filename as public_id
                        # Note: Depending on MEDIA_TAG setting, public_id might or might not have 'media/' prefix
                        public_id = obj.banner_image.name
                        
                        # Remove file extension for Cloudinary public_id (Cloudinary stores without extension)
                        if '.' in public_id:
                            public_id = public_id.rsplit('.', 1)[0]
                        
                        # Try to build Cloudinary URL with transformations
                        # Try with the public_id as-is first (preserves any prefix that was used during upload)
                        try:
                            cloudinary_img = CloudinaryImage(public_id)
                            cloudinary_url = cloudinary_img.build_url(transformation=[
                                {'width': 1200, 'height': 1200, 'crop': 'fill', 'quality': 'auto'}
                                # Removed 'format': 'auto' - Cloudinary handles auto-format automatically
                            ])
                            
                            # Verify it's a valid Cloudinary URL
                            if cloudinary_url and 'cloudinary.com' in cloudinary_url:
                                return cloudinary_url
                        except Exception as e:
                            logger.warning(f"Failed to build Cloudinary URL with public_id '{public_id}': {e}")
                        
                        # If that failed, try without 'media/' prefix if it was present
                        # This handles cases where MEDIA_TAG was set to empty string
                        if public_id.startswith('media/'):
                            try:
                                public_id_no_media = public_id[6:]  # Remove 'media/' prefix
                                cloudinary_img = CloudinaryImage(public_id_no_media)
                                cloudinary_url = cloudinary_img.build_url(transformation=[
                                    {'width': 1200, 'height': 1200, 'crop': 'fill', 'quality': 'auto', 'format': 'auto'}
                                ])
                                if cloudinary_url and 'cloudinary.com' in cloudinary_url:
                                    return cloudinary_url
                            except Exception as e:
                                logger.warning(f"Failed to build Cloudinary URL without 'media/' prefix: {e}")
                        
                        # If both attempts failed, try adding 'media/' prefix if it wasn't there
                        if not public_id.startswith('media/'):
                            try:
                                public_id_with_media = f'media/{public_id}'
                                cloudinary_img = CloudinaryImage(public_id_with_media)
                                cloudinary_url = cloudinary_img.build_url(transformation=[
                                    {'width': 1200, 'height': 1200, 'crop': 'fill', 'quality': 'auto', 'format': 'auto'}
                                ])
                                if cloudinary_url and 'cloudinary.com' in cloudinary_url:
                                    return cloudinary_url
                            except Exception as e:
                                logger.warning(f"Failed to build Cloudinary URL with 'media/' prefix: {e}")
                    except Exception as e:
                        # If Cloudinary construction fails, fall back to absolute URL
                        pass
            
            # If it's a local path, build absolute URL
            if (original_url.startswith('/media/') or original_url.startswith('/static/')) and request:
                absolute_url = request.build_absolute_uri(original_url)
                return absolute_url
            elif original_url.startswith('/media/') or original_url.startswith('/static/'):
                # Construct absolute URL manually if no request context
                host = os.environ.get('DJANGO_HOST', 'affordable-gadgets-backend.onrender.com')
                protocol = 'https'
                absolute_url = f"{protocol}://{host}{original_url}"
                return absolute_url
            
            # Return the URL as-is (might already be absolute)
            return original_url
        return None
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_banner_image_url(self, obj):
        """Return optimized banner image URL for public API"""
        # Use the same logic as get_banner_image
        return self.get_banner_image(obj)
    
    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
    def get_products(self, obj):
        """Return list of product IDs associated with this promotion."""
        return list(obj.products.values_list('id', flat=True))
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_discount_display(self, obj):
        """Get formatted discount display."""
        if obj.discount_percentage:
            return f"{obj.discount_percentage}% OFF"
        elif obj.discount_amount:
            return f"KES {obj.discount_amount} OFF"
        return None

