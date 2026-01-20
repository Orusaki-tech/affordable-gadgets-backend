"""Public API serializers for e-commerce frontend."""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer, OpenApiTypes
from decimal import Decimal
from django.db.models import Q, Sum
from inventory.models import Product, InventoryUnit, Cart, CartItem, Lead, LeadItem, Promotion
from inventory.services.interest_service import InterestService
import logging
import sys

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
            'id', 'product_id', 'product_name', 'product_slug', 'selling_price', 
            'condition', 'grade', 'storage_gb', 'ram_gb', 'battery_mah', 'product_color', 
            'color_name', 'interest_count', 'images'
        ]
    
    @extend_schema_field(OpenApiTypes.INT)
    def get_interest_count(self, obj):
        return InterestService.get_interest_count(obj)
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
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
            'primary_image', 'slug', 'product_video_url', 'tags',
            'meta_title', 'meta_description'  # SEO fields
        ]
    
    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_tags(self, obj):
        """Return list of tag names."""
        return [tag.name for tag in obj.tags.all()]
    
    @extend_schema_field(OpenApiTypes.INT)
    def get_available_units_count(self, obj):
        """Count available units for current brand - use prefetched list for accurate brand filtering."""
        # Use prefetched available_units_list if available (correctly filtered by brand)
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
            # For accessories, sum quantities; for phones/laptops/tablets, count units
            if obj.product_type == Product.ProductType.ACCESSORY:
                return sum(unit.quantity for unit in units)
            else:
                return len(units)
        
        # Fallback to annotation (may not be brand-filtered correctly)
        if hasattr(obj, 'available_units_count'):
            return obj.available_units_count or 0
        
        # Final fallback: query directly
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        # For accessories, sum quantities; for phones/laptops/tablets, count units
        if obj.product_type == Product.ProductType.ACCESSORY:
            return units.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        else:
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
        """Get min price for available units - use prefetched list for accurate brand filtering."""
        # Use prefetched available_units_list if available (correctly filtered by brand)
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
            if units:
                prices = [float(unit.selling_price) for unit in units]
                return min(prices) if prices else None
        
        # Fallback to annotation (may not be brand-filtered correctly)
        if hasattr(obj, 'min_price') and obj.min_price is not None:
            return float(obj.min_price)
        
        # Final fallback: query directly
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
        """Get max price for available units - use prefetched list for accurate brand filtering."""
        # Use prefetched available_units_list if available (correctly filtered by brand)
        if hasattr(obj, 'available_units_list'):
            units = obj.available_units_list
            if units:
                prices = [float(unit.selling_price) for unit in units]
                return max(prices) if prices else None
        
        # Fallback to annotation (may not be brand-filtered correctly)
        if hasattr(obj, 'max_price') and obj.max_price is not None:
            return float(obj.max_price)
        
        # Final fallback: query directly
        brand = self.context.get('brand')
        units = obj.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        prices = units.values_list('selling_price', flat=True)
        return float(max(prices)) if prices else None
    
    @extend_schema_field(serializers.URLField(allow_null=True))
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


class PublicProductListSerializer(PublicProductSerializer):
    """Lightweight product serializer for list endpoints."""

    class Meta(PublicProductSerializer.Meta):
        fields = [
            'id', 'product_name', 'brand', 'model_series', 'product_type',
            'available_units_count', 'min_price', 'max_price',
            'primary_image', 'slug', 'product_video_url'
        ]


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
    
    @extend_schema_field(OpenApiTypes.NUMBER)
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


class CheckoutResponseSerializer(serializers.Serializer):
    """Serializer for checkout response."""
    message = serializers.CharField()
    lead_reference = serializers.CharField()
    lead = LeadSerializer()


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
            from inventory.cloudinary_utils import get_optimized_image_url
            import os
            import json
            import cloudinary
            from cloudinary import CloudinaryImage
            from django.core.files.storage import default_storage
            from django.conf import settings
            request = self.context.get('request')
            
            # Check what storage is configured
            configured_storage = getattr(settings, 'DEFAULT_FILE_STORAGE', 'Not set')
            
            # Check if the storage backend is Cloudinary
            storage_type = str(type(default_storage))
            storage_module = getattr(default_storage, '__module__', '')
            storage_class = getattr(default_storage, '__class__', type(default_storage))
            is_cloudinary_storage = ('cloudinary' in storage_type.lower() or 
                                   'cloudinary' in storage_module.lower() or
                                   'cloudinary' in str(storage_class).lower())
            
            # Get the URL from the field - Cloudinary storage should return Cloudinary URL
            original_url = obj.banner_image.url
            banner_image_name = obj.banner_image.name if hasattr(obj.banner_image, 'name') else None
            # #region agent log
            log_data = {"location":"serializers_public.py:311","message":"get_banner_image called","data":{"promotion_id":obj.id,"original_url":original_url,"configured_storage":configured_storage,"storage_type":storage_type,"storage_module":storage_module,"storage_class":str(storage_class),"is_cloudinary_storage":is_cloudinary_storage,"banner_image_name":banner_image_name,"is_cloudinary_url":'cloudinary.com' in str(original_url).lower()},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}
            try:
                with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps(log_data) + '\n')
            except: pass
            logger.info(f"[DEBUG] get_banner_image: {log_data}")
            print(f"[DEBUG] get_banner_image: {log_data}", file=sys.stderr)
            # #endregion
            
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
                            transform_str = 'c_fill,h_1920,q_auto,w_1080'
                            
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
                    cloudinary_url = get_optimized_image_url(obj.banner_image, width=1080, height=1920, crop='fill')
                    return cloudinary_url if cloudinary_url else original_url
                
                # If parsing failed, try the utility function
                cloudinary_url = get_optimized_image_url(obj.banner_image, width=1080, height=1920, crop='fill')
                return cloudinary_url if cloudinary_url else original_url
            
            # If URL is local (relative or absolute), try to construct Cloudinary URL from image name
            # This handles cases where images were uploaded before Cloudinary was configured
            is_local_path = (original_url.startswith('/media/') or original_url.startswith('/static/') or 
                           '/media/' in original_url or '/static/' in original_url)
            # #region agent log
            log_data = {"location":"serializers_public.py:340","message":"Checking local path condition","data":{"promotion_id":obj.id,"is_local_path":is_local_path,"is_cloudinary_storage":is_cloudinary_storage,"condition_met":is_local_path,"has_name":hasattr(obj.banner_image, 'name'),"name_value":obj.banner_image.name if hasattr(obj.banner_image, 'name') else None},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}
            try:
                with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps(log_data) + '\n')
            except: pass
            logger.info(f"[DEBUG] local path check: {log_data}")
            print(f"[DEBUG] local path check: {log_data}", file=sys.stderr)
            # #endregion
            # Always try Cloudinary URL construction if we detect a local path
            # This handles images uploaded before Cloudinary was configured
            if is_local_path:
                if hasattr(obj.banner_image, 'name') and obj.banner_image.name:
                    try:
                        # Configure Cloudinary
                        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
                        api_key = os.environ.get('CLOUDINARY_API_KEY')
                        api_secret = os.environ.get('CLOUDINARY_API_SECRET')
                        # #region agent log
                        try:
                            with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({"location":"serializers_public.py:330","message":"Attempting to construct Cloudinary URL","data":{"promotion_id":obj.id,"has_cloud_name":bool(cloud_name),"has_api_key":bool(api_key),"has_api_secret":bool(api_secret),"banner_image_name":obj.banner_image.name},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                        except: pass
                        # #endregion
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
                                {'width': 1080, 'height': 1920, 'crop': 'fill', 'quality': 'auto'}
                                # Removed 'format': 'auto' - Cloudinary handles auto-format automatically
                            ])
                            
                            # Verify it's a valid Cloudinary URL
                            if cloudinary_url and 'cloudinary.com' in cloudinary_url:
                                # #region agent log
                                try:
                                    with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                                        f.write(json.dumps({"location":"serializers_public.py:375","message":"Cloudinary URL constructed","data":{"promotion_id":obj.id,"public_id":public_id,"cloudinary_url":cloudinary_url,"is_valid":'cloudinary.com' in str(cloudinary_url).lower()},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                                except: pass
                                # #endregion
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
                                    {'width': 1080, 'height': 1920, 'crop': 'fill', 'quality': 'auto', 'format': 'auto'}
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
                                    {'width': 1080, 'height': 1920, 'crop': 'fill', 'quality': 'auto', 'format': 'auto'}
                                ])
                                if cloudinary_url and 'cloudinary.com' in cloudinary_url:
                                    return cloudinary_url
                            except Exception as e:
                                logger.warning(f"Failed to build Cloudinary URL with 'media/' prefix: {e}")
                    except Exception as e:
                        # #region agent log
                        try:
                            with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({"location":"serializers_public.py:360","message":"Cloudinary URL construction failed","data":{"promotion_id":obj.id,"error":str(e)},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + '\n')
                        except: pass
                        # #endregion
                        # If Cloudinary construction fails, fall back to absolute URL
                        pass
            
            # If it's a local path, build absolute URL
            # #region agent log
            try:
                with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"location":"serializers_public.py:403","message":"Falling back to absolute URL construction","data":{"promotion_id":obj.id,"original_url":original_url,"has_request":bool(request),"starts_with_media":original_url.startswith('/media/') if original_url else False,"starts_with_static":original_url.startswith('/static/') if original_url else False},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
            except: pass
            # #endregion
            if (original_url.startswith('/media/') or original_url.startswith('/static/')) and request:
                absolute_url = request.build_absolute_uri(original_url)
                # #region agent log
                try:
                    with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"location":"serializers_public.py:410","message":"Returning absolute URL with request","data":{"promotion_id":obj.id,"absolute_url":absolute_url},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
                except: pass
                # #endregion
                return absolute_url
            elif original_url.startswith('/media/') or original_url.startswith('/static/'):
                # Construct absolute URL manually if no request context
                host = os.environ.get('DJANGO_HOST', 'affordable-gadgets-backend.onrender.com')
                protocol = 'https'
                absolute_url = f"{protocol}://{host}{original_url}"
                # #region agent log
                try:
                    with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"location":"serializers_public.py:420","message":"Returning absolute URL without request","data":{"promotion_id":obj.id,"absolute_url":absolute_url,"host":host},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
                except: pass
                # #endregion
                return absolute_url
            
            # Return the URL as-is (might already be absolute)
            # #region agent log
            try:
                with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"location":"serializers_public.py:428","message":"Returning original URL as-is","data":{"promotion_id":obj.id,"original_url":original_url},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + '\n')
            except: pass
            # #endregion
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

