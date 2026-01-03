"""Public API serializers for e-commerce frontend."""
from rest_framework import serializers
from decimal import Decimal
from django.db.models import Q
from inventory.models import Product, InventoryUnit, Cart, CartItem, Lead, LeadItem, Promotion
from inventory.services.interest_service import InterestService


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
            'id', 'product_id', 'product_name', 'product_slug', 'selling_price', 
            'condition', 'grade', 'storage_gb', 'ram_gb', 'battery_mah', 'product_color', 
            'color_name', 'interest_count', 'images'
        ]
    
    def get_interest_count(self, obj):
        return InterestService.get_interest_count(obj)
    
    def get_images(self, obj):
        """Return list of image URLs for this unit with color information."""
        from inventory.cloudinary_utils import get_optimized_image_url
        request = self.context.get('request')
        images = obj.images.all().order_by('-is_primary', 'id')
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


class PublicProductSerializer(serializers.ModelSerializer):
    """Public product serializer (stripped down)."""
    available_units_count = serializers.SerializerMethodField()
    interest_count = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
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
            'primary_image', 'slug', 'product_video_url', 'tags'
        ]
    
    def get_tags(self, obj):
        """Return list of tag names."""
        return [tag.name for tag in obj.tags.all()]
    
    def get_available_units_count(self, obj):
        """Count available units for current brand - use annotation if available."""
        # Use annotation from queryset if available (optimized)
        if hasattr(obj, 'available_units_count'):
            return obj.available_units_count or 0
        # Fallback to query (shouldn't happen with optimized queryset)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        return units.count()
    
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
    
    def get_min_price(self, obj):
        """Get min price for available units - use annotation if available."""
        # Use annotation from queryset if available (optimized)
        if hasattr(obj, 'min_price'):
            return float(obj.min_price) if obj.min_price is not None else None
        # Fallback to query (shouldn't happen with optimized queryset)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        prices = units.values_list('selling_price', flat=True)
        return float(min(prices)) if prices else None
    
    def get_max_price(self, obj):
        """Get max price for available units - use annotation if available."""
        # Use annotation from queryset if available (optimized)
        if hasattr(obj, 'max_price'):
            return float(obj.max_price) if obj.max_price is not None else None
        # Fallback to query (shouldn't happen with optimized queryset)
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        prices = units.values_list('selling_price', flat=True)
        return float(max(prices)) if prices else None
    
    def get_primary_image(self, obj):
        """Get primary product image URL - use prefetched data if available."""
        from inventory.cloudinary_utils import get_optimized_image_url
        # Use prefetched primary images if available
        if hasattr(obj, 'primary_images_list') and obj.primary_images_list:
            primary_image = obj.primary_images_list[0]
        else:
            # Fallback to query (shouldn't happen with optimized queryset)
            primary_image = obj.images.filter(is_primary=True).first()
        
        if primary_image and primary_image.image:
            # Get request from context for absolute URL building
            request = self.context.get('request')
            if request:
                # Store request temporarily for URL building
                original_url = primary_image.image.url
                # Build absolute URL if it's a local path
                if original_url.startswith('/media/') or original_url.startswith('/static/'):
                    absolute_url = request.build_absolute_uri(original_url)
                    # Return optimized URL if Cloudinary, otherwise absolute local URL
                    cloudinary_url = get_optimized_image_url(primary_image.image)
                    # If Cloudinary URL is different (Cloudinary was used), return it
                    # Otherwise return absolute local URL
                    if cloudinary_url and cloudinary_url != original_url and 'cloudinary.com' in cloudinary_url:
                        return cloudinary_url
                    return absolute_url
            # Return optimized image URL from Cloudinary or local URL
            return get_optimized_image_url(primary_image.image)
        return None


class CartItemSerializer(serializers.ModelSerializer):
    """Cart item serializer."""
    inventory_unit = PublicInventoryUnitSerializer(read_only=True)
    inventory_unit_id = serializers.IntegerField(write_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    promotion_id = serializers.IntegerField(source='promotion.id', read_only=True, allow_null=True)
    
    class Meta:
        model = CartItem
        fields = ['id', 'inventory_unit', 'inventory_unit_id', 'quantity', 'unit_price', 'promotion_id']


class CartSerializer(serializers.ModelSerializer):
    """Cart serializer."""
    items = CartItemSerializer(many=True, read_only=True)
    total_value = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = [
            'id', 'items', 'customer_name', 'customer_phone', 'customer_email',
            'delivery_address', 'total_value', 'expires_at', 'is_submitted'
        ]
    
    def get_total_value(self, obj):
        total = Decimal('0.00')
        for item in obj.items.all():
            unit_price = item.get_unit_price()  # Use stored promotion price
            total += unit_price * item.quantity
        return float(total)


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


class PublicPromotionSerializer(serializers.ModelSerializer):
    """Public promotion serializer (limited fields)."""
    is_currently_active = serializers.BooleanField(read_only=True)
    discount_display = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    banner_image_url = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Promotion
        fields = (
            'id', 'title', 'description', 'banner_image', 'banner_image_url',
            'discount_percentage', 'discount_amount', 'discount_display',
            'start_date', 'end_date', 'is_currently_active', 'product_types',
            'display_locations', 'carousel_position', 'products'
        )
        read_only_fields = ('is_currently_active', 'discount_display', 'products', 'banner_image_url')
    
    def get_banner_image_url(self, obj):
        """Return optimized banner image URL for public API"""
        if obj.banner_image:
            from inventory.cloudinary_utils import get_optimized_image_url
            request = self.context.get('request')
            original_url = obj.banner_image.url
            # Build absolute URL if it's a local path
            if (original_url.startswith('/media/') or original_url.startswith('/static/')) and request:
                absolute_url = request.build_absolute_uri(original_url)
                # Try to get Cloudinary URL
                cloudinary_url = get_optimized_image_url(obj.banner_image, width=1080, height=1920, crop='fill')
                # If Cloudinary URL is different and valid, return it
                if cloudinary_url and cloudinary_url != original_url and 'cloudinary.com' in cloudinary_url:
                    return cloudinary_url
                return absolute_url
            # Optimized for stories carousel (1080x1920) or banners (1200x400)
            # Using 1080x1920 for stories carousel
            return get_optimized_image_url(obj.banner_image, width=1080, height=1920, crop='fill')
        return None
    
    def get_products(self, obj):
        """Return list of product IDs associated with this promotion."""
        return list(obj.products.values_list('id', flat=True))
    
    def get_discount_display(self, obj):
        """Get formatted discount display."""
        if obj.discount_percentage:
            return f"{obj.discount_percentage}% OFF"
        elif obj.discount_amount:
            return f"KES {obj.discount_amount} OFF"
        return None

