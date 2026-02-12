import logging

import csv
import io
from decimal import Decimal
from django.db import transaction

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Product, InventoryUnit # ... and your other models


from rest_framework import viewsets, generics, permissions, exceptions, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.core.cache import cache
from urllib.parse import urlencode
from decimal import Decimal
from django.db.models import (
    F,
    Count,
    Min,
    Max,
    Q,
    Sum,
    Case,
    When,
    IntegerField,
    Value,
    Exists,
    OuterRef,
    ExpressionWrapper,
    FloatField,
) # Added Count, Min, Max, Q for aggregation/filtering
from django.db.models.functions import Coalesce
from rest_framework.decorators import action # Required for potential custom actions
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
# NEW IMPORTS for Filtering and Searching
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.conf import settings 
from django.http import HttpResponse, FileResponse
from django.core.files.base import ContentFile
from .serializers import CustomerRegistrationSerializer, CustomerLoginSerializer, AdminAuthTokenSerializer
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token 
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiTypes, OpenApiParameter

# --- Schema helpers (drf-spectacular) ---
class EmptySerializer(serializers.Serializer):
    pass


class FixProductVisibilitySerializer(serializers.Serializer):
    secret_key = serializers.CharField(required=False, allow_blank=True)

# Assume these models are imported from your app's models.py
from .models import (
    Product, ProductAccessory, Review, Color, UnitAcquisitionSource, 
    InventoryUnit, Order, OrderItem, Customer, Admin, User,  ProductImage, InventoryUnitImage,
    AdminRole, ReservationRequest, ReturnRequest, UnitTransfer, Notification, AuditLog, Tag,
    Brand, Lead, LeadItem, Cart, CartItem, Promotion, PromotionType, Receipt,
    Bundle, BundleItem, DeliveryRate
)

# Assume these serializers are defined in your app's serializers.py
from .permissions import (
    IsAdminOrReadOnly, IsAdminUser, IsCustomerOwnerOrAdmin, IsReviewOwnerOrAdmin,
    HasRole, IsSalesperson, IsInventoryManager, IsContentCreator,
    IsSalespersonOrInventoryManager, CanReserveUnits, CanApproveRequests,
    IsSalespersonOrInventoryManagerOrMarketingManagerReadOnly,
    CanCreateReviews, IsInventoryManagerOrSalespersonReadOnly,
    IsInventoryManagerOrReadOnly, IsSuperuser, IsMarketingManager, IsOrderManager,
    IsInventoryManagerOrMarketingManagerReadOnly, IsContentCreatorOrInventoryManager,
    IsContentCreatorOrInventoryManagerOrReadOnly, IsBundleManagerOrReadOnly,
    get_admin_from_user
)
from .serializers import (
    ProductImageSerializer, ProductSerializer, ProductAccessorySerializer, ReviewSerializer, 
    ColorSerializer, UnitAcquisitionSourceSerializer, InventoryUnitSerializer,
    OrderSerializer, OrderItemSerializer, CustomerProfileUpdateSerializer, 
    AdminSerializer, AdminCreateSerializer, AdminRoleSerializer, DiscountCalculatorSerializer, 
    CustomerRegistrationSerializer, # <--- NEW: Import the Registration Serializer
    PublicInventoryUnitSerializer, InventoryUnitImageSerializer,
    ReservationRequestSerializer, ReturnRequestSerializer, UnitTransferSerializer, NotificationSerializer,
    AuditLogSerializer, TagSerializer, BrandSerializer, LeadSerializer, CartSerializer, PromotionSerializer,
    PromotionTypeSerializer, InitiatePaymentRequestSerializer,
    BundleSerializer, BundleItemSerializer, DeliveryRateSerializer
)
from .services.lead_service import LeadService

logger = logging.getLogger(__name__)

def resolve_staff_brand_or_raise(request, brand_id=None, *, require_brand=False):
    """
    Resolve a brand for staff actions and enforce role-based brand access.
    Returns a Brand instance or None.
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return None

    admin = get_admin_from_user(request.user)
    if not admin:
        raise exceptions.PermissionDenied("Staff account is missing an admin profile.")

    is_global = request.user.is_superuser or admin.is_global_admin

    if brand_id:
        try:
            brand_id = int(brand_id)
        except (TypeError, ValueError):
            raise exceptions.ValidationError({'brand': 'Brand must be a valid integer.'})

        try:
            brand = Brand.objects.get(id=brand_id, is_active=True)
        except Brand.DoesNotExist:
            raise exceptions.ValidationError({'brand': 'Invalid brand.'})

        if not is_global and not admin.brands.filter(id=brand.id).exists():
            raise exceptions.PermissionDenied("Brand is not assigned to your role.")

        return brand

    if is_global:
        if require_brand:
            raise exceptions.ValidationError({'brand': 'Brand is required.'})
        return None

    if admin.brands.count() == 1:
        return admin.brands.first()

    if require_brand:
        raise exceptions.ValidationError({'brand': 'Brand is required for staff actions.'})

    return None


# --- CORE INVENTORY AND CATALOG VIEWSETS ---

class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD for Product Templates.
    - Public: Read-only access
    - Inventory Manager: Full CRUD access
    - Content Creator: Can update content via update_content only (no create/delete)
    - Salesperson: Read-only access
    - Superuser: Full access
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product_name', 'brand', 'model_series', 'product_description']
    ordering_fields = ['product_name', 'available_stock', 'created_at', 'updated_at']
    
    def get_queryset(self):
        """Filter products by admin's assigned brands."""
        queryset = super().get_queryset()
        user = self.request.user
        
        skip_brand_filter = False

        # Superuser sees all products
        if user.is_superuser:
            skip_brand_filter = True
        
        # For staff users (admins), filter by their assigned brands
        elif user.is_staff:
            try:
                admin = Admin.objects.get(user=user)
                if admin.is_global_admin:
                    skip_brand_filter = True
                
                # Salespersons need to see all products to make reservations
                # They should see all products regardless of brand assignment
                if admin.is_salesperson:
                    skip_brand_filter = True
                
                # Inventory Managers need to see all products to manage inventory
                # They should see all products regardless of brand assignment
                if admin.is_inventory_manager:
                    skip_brand_filter = True
                
                # Marketing Managers need to see all products to view and attach promotions
                # They should see all products regardless of brand assignment
                if admin.is_marketing_manager:
                    skip_brand_filter = True
                
                # Content Creators need to see all products to select them for reviews
                # They should see all products regardless of brand assignment
                if admin.is_content_creator:
                    skip_brand_filter = True
                
                # Filter products by admin's assigned brands (for other roles)
                if not skip_brand_filter:
                    if admin.brands.exists():
                        # Products can be associated with multiple brands or be global
                        # Show products that are either:
                        # 1. Associated with one of admin's brands
                        # 2. Global products (no brand association or is_global=True)
                        queryset = queryset.filter(
                            Q(brands__in=admin.brands.all()) | 
                            Q(brands__isnull=True) | 
                            Q(is_global=True)
                        ).distinct()
                    else:
                        # Admin with no brands sees nothing (except salespersons, inventory managers, and marketing managers who see all)
                        queryset = queryset.none()
            except Admin.DoesNotExist:
                # Staff user without admin profile sees nothing
                queryset = queryset.none()
        
        # Optional filtering for admin list views
        available_units_filter = Q(inventory_units__sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE)
        if self.action == 'list':
            available_stock_expr = Case(
                When(
                    product_type=Product.ProductType.ACCESSORY,
                    then=Coalesce(Sum('inventory_units__quantity', filter=available_units_filter), Value(0)),
                ),
                default=Coalesce(Count('inventory_units', filter=available_units_filter), Value(0)),
                output_field=IntegerField(),
            )
            queryset = queryset.annotate(available_stock=available_stock_expr)

        product_type = self.request.query_params.get('product_type')
        if product_type:
            queryset = queryset.filter(product_type=product_type)

        brand = self.request.query_params.get('brand')
        if brand:
            queryset = queryset.filter(brand__icontains=brand)

        stock_status = self.request.query_params.get('stock_status')
        if stock_status:
            if stock_status == 'discontinued':
                queryset = queryset.filter(is_discontinued=True)
            elif stock_status == 'out_of_stock':
                queryset = queryset.filter(is_discontinued=False, available_stock=0)
            elif stock_status == 'low_stock':
                queryset = queryset.filter(is_discontinued=False, min_stock_threshold__isnull=False)
                queryset = queryset.filter(available_stock__gt=0, available_stock__lt=F('min_stock_threshold'))
            elif stock_status == 'in_stock':
                queryset = queryset.filter(is_discontinued=False, available_stock__gt=0)
                queryset = queryset.filter(Q(min_stock_threshold__isnull=True) | Q(available_stock__gte=F('min_stock_threshold')))

        seo_status = self.request.query_params.get('seo_status')
        if seo_status:
            images_with_alt = ProductImage.objects.filter(
                product=OuterRef('pk'),
                alt_text__isnull=False,
            ).exclude(alt_text='')

            seo_score_points = (
                Case(
                    When(Q(meta_title__isnull=False) & ~Q(meta_title=''), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(Q(meta_description__isnull=False) & ~Q(meta_description=''), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(Q(slug__isnull=False) & ~Q(slug=''), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(Q(og_image__isnull=False) & ~Q(og_image=''), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(Q(product_description__isnull=False) & ~Q(product_description=''), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(Exists(images_with_alt), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(Q(product_highlights__isnull=False) & ~Q(product_highlights=[]), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(Q(keywords__isnull=False) & ~Q(keywords=''), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )

            queryset = queryset.annotate(
                seo_score=ExpressionWrapper(seo_score_points * Value(100.0) / Value(8.0), output_field=FloatField())
            )

            if seo_status == 'missing-seo':
                complete_q = (
                    Q(meta_title__isnull=False) & ~Q(meta_title='') &
                    Q(meta_description__isnull=False) & ~Q(meta_description='') &
                    Q(slug__isnull=False) & ~Q(slug='') &
                    Q(seo_score__gte=50)
                )
                queryset = queryset.exclude(complete_q)
            elif seo_status == 'incomplete':
                queryset = queryset.filter(seo_score__lt=50)
            elif seo_status == 'complete':
                queryset = queryset.filter(seo_score__gte=50)

        return queryset
    
    def get_permissions(self):
        """Apply different permissions based on action"""
        if self.action in ['create', 'destroy']:
            # Only Inventory Managers and Superusers can create/delete products
            from .permissions import IsInventoryManagerOrSuperuser
            return [IsInventoryManagerOrSuperuser()]
        if self.action in ['update', 'partial_update']:
            # Only Inventory Managers and Superusers can update full product fields
            from .permissions import IsInventoryManagerOrSuperuser
            return [IsInventoryManagerOrSuperuser()]
        if self.action == 'update_content':
            # Content Creators and Inventory Managers can update content fields
            from .permissions import IsContentCreatorOrInventoryManager
            return [IsContentCreatorOrInventoryManager()]
        # For read operations, allow Salespersons, Inventory Managers, and Marketing Managers (read-only for Salespersons and Marketing Managers)
        return [IsSalespersonOrInventoryManagerOrMarketingManagerReadOnly()]
    
    def perform_create(self, serializer):
        """Set created_by and updated_by, and auto-assign to admin's brands if not specified."""
        # Get the admin profile
        try:
            admin = Admin.objects.get(user=self.request.user)
        except Admin.DoesNotExist:
            admin = None
        
        # Save the product instance first
        product_instance = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        
        # Auto-assign to admin's brands if brand_ids not explicitly provided
        if admin and admin.brands.exists() and not admin.is_global_admin:
            # Check if brand_ids were provided in the request
            brand_ids_provided = 'brand_ids' in self.request.data
            
            if not brand_ids_provided:
                # No brand_ids provided - auto-assign to admin's brands
                product_instance.brands.set(admin.brands.all())
            elif self.request.data.get('brand_ids') is None or (
                isinstance(self.request.data.get('brand_ids'), list) and 
                len(self.request.data.get('brand_ids', [])) == 0
            ):
                # Empty brand_ids list provided - auto-assign to admin's brands
                product_instance.brands.set(admin.brands.all())
            # If brand_ids were provided and not empty, the serializer will handle it
        elif admin and admin.is_global_admin:
            # Global admin - don't auto-assign, let them choose
            pass
        else:
            # No admin or admin has no brands - assign to default brand if exists
            default_brand = Brand.objects.filter(code='AFFORDABLE_GADGETS', is_active=True).first()
            if default_brand:
                product_instance.brands.set([default_brand])
    
    def perform_update(self, serializer):
        """Update updated_by and auto-assign to admin's brands if product has no brands."""
        product_instance = serializer.save(updated_by=self.request.user)
        
        # Auto-assign to admin's brands if product has no brands and admin has brands
        if not product_instance.brands.exists():
            try:
                admin = Admin.objects.get(user=self.request.user)
                if admin and admin.brands.exists() and not admin.is_global_admin:
                    product_instance.brands.set(admin.brands.all())
            except Admin.DoesNotExist:
                # If no admin, try to assign to default brand
                default_brand = Brand.objects.filter(code='AFFORDABLE_GADGETS', is_active=True).first()
                if default_brand:
                    product_instance.brands.set([default_brand])
    
    def perform_destroy(self, instance):
        """
        Override destroy to check for related objects before deletion.
        Prevents deletion if product has inventory units (PROTECT constraint).
        """
        # Check for AVAILABLE inventory units only
        available_units = instance.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE
        )
        # For accessories, sum quantities; for unique units, count rows
        available_units_count = available_units.aggregate(
            total=Coalesce(Sum('quantity'), Value(0))
        )['total'] or 0
        if available_units_count > 0:
            from rest_framework.exceptions import ValidationError
            error_message = (
                f'Unable to delete product "{instance.product_name}" because it still has '
                f'{available_units_count} available inventory unit(s) associated with it. '
                f'Please delete or reassign all available inventory units first.'
            )
            # DRF ValidationError with a dict returns it as {"detail": "message"} which is easier to parse
            raise ValidationError({'detail': error_message})
        
        # Check for other related objects that might prevent deletion
        # ProductAccessory (CASCADE - will be deleted automatically)
        # ProductImage (CASCADE - will be deleted automatically)
        # Review (CASCADE - will be deleted automatically)
        # created_by/updated_by (PROTECT - but these are users, not products)

        # Clear protected relations that can block deletion when no available units exist
        try:
            if instance.bundle_items.exists():
                instance.bundle_items.all().delete()
            if instance.inventory_units.exists():
                instance.inventory_units.all().delete()
        except Exception as e:
            logger.error(f"Error cleaning related data for product {instance.id}: {str(e)}", exc_info=True)
            from rest_framework.exceptions import ValidationError
            raise ValidationError(f'Failed to delete product: {str(e)}')
        
        # Attempt deletion
        try:
            instance.delete()
        except Exception as e:
            # Log the error for debugging
            logger.error(f"Error deleting product {instance.id}: {str(e)}", exc_info=True)
            # Re-raise with a user-friendly message
            from rest_framework.exceptions import ValidationError
            raise ValidationError(f'Failed to delete product: {str(e)}')
    
    @action(detail=True, methods=['patch'], permission_classes=[IsContentCreator])
    def update_content(self, request, pk=None):
        """
        Custom action for Content Creators to update only content fields.
        This allows Content Creators to update product content without touching inventory fields.
        """
        product = self.get_object()
        
        # Define allowed content fields
        content_fields = {
            'product_name', 'product_description', 'long_description',
            'meta_title', 'meta_description', 'slug', 'keywords', 'og_image',
            'product_highlights', 'is_published',
            'product_video_url', 'product_video_file', 'tag_ids'
        }
        
        # Filter request data to only include content fields
        content_data = {k: v for k, v in request.data.items() if k in content_fields}
        
        serializer = self.get_serializer(product, data=content_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='stock-summary', permission_classes=[IsSalespersonOrInventoryManagerOrMarketingManagerReadOnly])
    def stock_summary(self, request, pk=None):
        """
        Custom action to retrieve the available inventory count, min price, and max price 
        for a specific Product (template). Accessible by staff users (read-only).
        
        Example URL: /api/products/{product_id}/stock-summary/
        """
        try:
            # 1. Get the specific Product Template
            product = self.get_object()
        except exceptions.NotFound:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        # 2. Filter Inventory Units by the product template and availability
        # We use a Q object to specify Inventory Units that are currently marked 'AVAILABLE'
        # The related name from Product to InventoryUnit is 'inventory_units'
        inventory_queryset = product.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE 
        )

        # 3. Perform Aggregation
        # For accessories, sum quantities; for phones/laptops/tablets, count units (quantity is always 1)
        if product.product_type == Product.ProductType.ACCESSORY:
            # Accessories: sum quantities across all units
            summary = inventory_queryset.aggregate(
                total_available_stock=Sum('quantity'),
                min_price=Min('selling_price'),
                max_price=Max('selling_price')
            )
        else:
            # Phones/Laptops/Tablets: count units (each unit has quantity=1)
            summary = inventory_queryset.aggregate(
                total_available_stock=Count('id'),
                min_price=Min('selling_price'),
                max_price=Max('selling_price')
            )
        
        # #region agent log
        try:
            import json, time
            count_units = inventory_queryset.count()
            sum_qty = inventory_queryset.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
            import os
            os.makedirs("/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor", exist_ok=True)
            with open("/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log", "a") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H1",
                    "location": "inventory/views.py:stock_summary",
                    "message": "Stock summary count vs quantity",
                    "data": {
                        "product_id": product.pk,
                        "product_type": product.product_type,
                        "count_units": count_units,
                        "sum_quantity": sum_qty,
                        "available_stock": summary.get("total_available_stock")
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception:
            pass
        # #endregion

        # 4. Construct the response data
        response_data = {
            "product_id": product.pk,
            "product_name": product.product_name,
            "available_stock": summary['total_available_stock'],
            "min_price": summary['min_price'] if summary['min_price'] is not None else 0.00,
            "max_price": summary['max_price'] if summary['max_price'] is not None else 0.00,
            "currency": "KES", # Assuming KES, adapt as needed
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='available-units', permission_classes=[permissions.AllowAny])
    def available_units(self, request, pk=None):
        """
        Public: List available units (public fields) for a specific product template, paginated.
        Intended for product detail pages to show purchasable configurations.
        """
        product = self.get_object()
        qs = product.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE
        ).select_related('product_color').order_by('selling_price')

        page = self.paginate_queryset(qs)
        serializer = PublicInventoryUnitSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class ProductImageViewSet(viewsets.ModelViewSet):
    """
    CRUD for individual product images.
    Only Admins can add/manage images; everyone can view product images 
    (which are nested in ProductViewSet).
    Uses IsContentCreatorOrInventoryManagerOrReadOnly.
    """
    queryset = ProductImage.objects.all().select_related('product')
    serializer_class = ProductImageSerializer
    permission_classes = [IsContentCreatorOrInventoryManagerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

class InventoryUnitImageViewSet(viewsets.ModelViewSet):
    """
    CRUD for individual inventory unit images.
    Only Admins can add/manage images; everyone can view unit images 
    (which are nested in InventoryUnitViewSet).
    Uses IsAdminOrReadOnly.
    """
    queryset = InventoryUnitImage.objects.all().select_related('inventory_unit')
    serializer_class = InventoryUnitImageSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

class InventoryUnitViewSet(viewsets.ModelViewSet):
    """
    CRUD for individual physical Inventory Units.
    - Inventory Manager: Full access (read/write)
    - Marketing Manager: Read-only access
    - Salesperson: Read-only access
    - Superuser: Full access
    
    NEW: Includes filtering and searching capabilities for efficient inventory management.
    """

     parser_classes = [MultiPartParser, FormParser, JSONParser] 
     
    # Optimized queryset for related field lookups
    queryset = InventoryUnit.objects.all().select_related('product_template', 'product_color', 'acquisition_source_details', 'reserved_by__user')
    serializer_class = InventoryUnitSerializer
    permission_classes = [IsInventoryManagerOrMarketingManagerReadOnly]
    
    # 1. Add Filter Backends
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # 2. Define fields for Filtering (Exact matches, ranges, etc.)
    filterset_fields = {
        'product_template': ['exact'],             # Filter by Product Template ID
        'product_template__product_type': ['exact'], # Filter by Phone, Laptop, Accessory, etc.
        'product_template__brand': ['exact'],      # Filter by Brand (Apple, Samsung, etc.)
        'condition': ['exact'],                    # Filter by unit Condition (New, Used)
        'sale_status': ['exact'],                  # Filter by unit Sale Status (Available, Sold, etc.)
        'selling_price': ['lte', 'gte', 'exact'],  # Filter by price range (less than/greater than or equal to)
        'storage_gb': ['exact', 'gte'],            # Filter by minimum storage
        'ram_gb': ['exact', 'gte'],                # Filter by minimum RAM
    }
    
    # 3. Define fields for Searching (Partial matches across text fields)
    search_fields = [
        '=serial_number', # Exact match on SN
        '=imei',          # Exact match on IMEI
        'product_template__product_name', # Search within product name
        'product_template__model_series'  # Search within model series
    ]
    
    # 4. Define fields for Ordering
    ordering_fields = ['selling_price', 'date_sourced', 'storage_gb']
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve_buyback(self, request, pk=None):
        """
        Admin action to approve a RETURNED buyback item and make it AVAILABLE.
        Only buyback items (source=BB) with status RETURNED can be approved.
        
        Note: If a pending ReturnRequest exists for this unit, it should be approved via
        the ReturnRequestViewSet instead to maintain proper workflow.
        """
        unit = self.get_object()
        
        if unit.sale_status != InventoryUnit.SaleStatusChoices.RETURNED:
            return Response(
                {"error": "Only RETURNED items can be approved."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if unit.source != InventoryUnit.SourceChoices.BUYBACK_CUSTOMER:
            return Response(
                {"error": "Only buyback items can be approved."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if there's a pending ReturnRequest for this unit
        pending_request = unit.return_requests.filter(
            status=ReturnRequest.StatusChoices.PENDING
        ).first()
        
        if pending_request:
            return Response(
                {
                    "error": "This unit has a pending ReturnRequest. Please approve the ReturnRequest instead to maintain proper workflow.",
                    "return_request_id": pending_request.id,
                    "return_request_url": f"/api/inventory/return-requests/{pending_request.id}/"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
        unit.save()
        
        serializer = self.get_serializer(unit)
        return Response({
            "message": "Buyback item approved and made available.",
            "unit": serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def create_order(self, request, pk=None):
        """Create an order from a RESERVED unit - transitions to PENDING_PAYMENT."""
        from inventory.services.customer_service import CustomerService
        
        try:
            unit = self.get_object()
        except Exception as e:
            logger.error(f"Error getting unit {pk}: {str(e)}", exc_info=True)
            return Response({
                'error': f'Unit not found: {str(e)}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if unit is RESERVED
        if unit.sale_status != InventoryUnit.SaleStatusChoices.RESERVED:
            return Response({
                'error': f'Unit must be RESERVED to create order. Current status: {unit.get_sale_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get required data from request
        customer_name = request.data.get('customer_name')
        customer_phone = request.data.get('customer_phone')
        brand_id = request.data.get('brand_id') or request.data.get('brand')
        
        if not customer_name or not customer_phone:
            return Response({
                'error': 'customer_name and customer_phone are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            brand = resolve_staff_brand_or_raise(request, brand_id=brand_id, require_brand=True)
        except exceptions.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        except exceptions.PermissionDenied as exc:
            return Response({'error': exc.detail}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            with transaction.atomic():
                # Get or create customer
                try:
                    customer, created = CustomerService.get_or_create_customer(
                        name=customer_name,
                        phone=customer_phone
                    )
                except Exception as e:
                    logger.error(f"Error creating/getting customer: {str(e)}", exc_info=True)
                    return Response({
                        'error': f'Failed to create/get customer: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # Create order
                try:
                    order = Order.objects.create(
                        customer=customer,
                        user=customer.user if customer.user else None,
                        brand=brand,
                        order_source=Order.OrderSourceChoices.WALK_IN,
                        status=Order.StatusChoices.PENDING,
                        total_amount=unit.selling_price
                    )
                except Exception as e:
                    logger.error(f"Error creating order: {str(e)}", exc_info=True)
                    return Response({
                        'error': f'Failed to create order: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # Create order item
                try:
                    OrderItem.objects.create(
                        order=order,
                        inventory_unit=unit,
                        quantity=1,
                        unit_price_at_purchase=unit.selling_price
                    )
                except Exception as e:
                    logger.error(f"Error creating order item: {str(e)}", exc_info=True)
                    return Response({
                        'error': f'Failed to create order item: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                # Transition unit to PENDING_PAYMENT
                try:
                    unit.sale_status = InventoryUnit.SaleStatusChoices.PENDING_PAYMENT
                    unit.save(update_fields=['sale_status'])
                except Exception as e:
                    logger.error(f"Error updating unit status: {str(e)}", exc_info=True)
                    return Response({
                        'error': f'Failed to update unit status: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                return Response({
                    'message': 'Order created successfully',
                    'order_id': str(order.order_id),
                    'unit_status': unit.get_sale_status_display(),
                    'customer_id': customer.id,
                    'customer_created': created
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Unexpected error in create_order: {str(e)}", exc_info=True)
            return Response({
                'error': f'Unexpected error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[IsInventoryManagerOrSalespersonReadOnly])
    def export_csv(self, request):
        """Export inventory units to CSV file."""
        import csv
        from django.http import HttpResponse
        
        # Get all units with filters applied
        queryset = self.filter_queryset(self.get_queryset())
        
        # Create HTTP response with CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="inventory_units_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'ID', 'Serial Number', 'IMEI', 'Product', 'Color', 'Condition', 'Grade',
            'Storage (GB)', 'RAM (GB)', 'Selling Price', 'Sale Status', 'Source', 
            'Date Sourced', 'Reserved By', 'Reserved Until', 'Notes'
        ])
        
        # Write data
        for unit in queryset:
            writer.writerow([
                unit.id,
                unit.serial_number or '',
                unit.imei or '',
                unit.product_template_name or '',
                unit.product_color.name if unit.product_color else '',
                unit.condition or '',
                unit.grade or '',
                unit.storage_gb or '',
                unit.ram_gb or '',
                str(unit.selling_price) if unit.selling_price else '',
                unit.sale_status or '',
                unit.acquisition_source_details.name if unit.acquisition_source_details else '',
                unit.date_sourced.strftime('%Y-%m-%d') if unit.date_sourced else '',
                unit.reserved_by_username or '',
                unit.reserved_until.strftime('%Y-%m-%d %H:%M') if unit.reserved_until else '',
                unit.notes or ''
            ])
        
        return response
    
 # Add these to your InventoryUnitViewSet class
   

    @action(detail=False, methods=['post'], permission_classes=[IsInventoryManager | IsSuperuser])
    def import_csv(self, request):
        import csv
        import io
        from decimal import Decimal

        file = request.FILES.get('file')
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_file = file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
        except Exception as e:
            return Response({"error": f"Encoding error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        errors = []

        with transaction.atomic():
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Look up Product (strip spaces for safety)
                    model_name = (row.get('Model') or '').strip()
                    if not model_name:
                        continue # Skip empty rows

                    product = Product.objects.filter(product_name__iexact=model_name).first()
                    
                    if not product:
                        errors.append(f"Row {row_num}: Product '{model_name}' not found.")
                        continue

                    # Clean Price
                    raw_price = str(row.get('Selling Price', '0')).replace(',', '').strip()
                    price = Decimal(raw_price) if raw_price and raw_price != 'None' else Decimal('0.00')

                    InventoryUnit.objects.create(
                        product_template=product,
                        serial_number=row.get('Serial Number'),
                        imei=row.get('IMEI'),
                        condition=row.get('Condition', 'N'),
                        grade=row.get('Grade'),
                        storage_gb=int(row['Storage (GB)']) if row.get('Storage (GB)') and str(row['Storage (GB)']).isdigit() else 0,
                        ram_gb=int(row['RAM (GB)']) if row.get('RAM (GB)') and str(row['RAM (GB)']).isdigit() else 0,
                        selling_price=price,
                        notes=row.get('Notes', ''),
                        created_by=request.user,
                        updated_by=request.user,
                        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE 
                    )
                    created_count += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

        return Response({
            "success": len(errors) == 0,
            "created": created_count,
            "failed": len(errors),
            "errors": errors
        }, status=status.HTTP_201_CREATED if created_count > 0 else status.HTTP_400_BAD_REQUEST)


        # Read CSV
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        created_count = 0
        failed_count = 0
        errors = []
        
        try:
            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header
                    try:
                        # Basic validation
                        if not row.get('Product') or not row.get('Selling Price'):
                            errors.append(f"Row {row_num}: Missing required fields (Product, Selling Price)")
                            failed_count += 1
                            continue
                        
                        # Find product by name
                        product = Product.objects.filter(product_name=row['Product']).first()
                        if not product:
                            errors.append(f"Row {row_num}: Product '{row['Product']}' not found")
                            failed_count += 1
                            continue
                        
                        # Determine source (default to EXTERNAL_SUPPLIER if not provided)
                        source = row.get('Source', InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER)
                        if source not in [choice[0] for choice in InventoryUnit.SourceChoices.choices]:
                            source = InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER
                        
                        # Auto-set sale_status based on source:
                        # - Buyback (BB) → RETURNED (needs admin approval via ReturnRequest)
                        # - Supplier/Import (SU/IM) → AVAILABLE
                        if source == InventoryUnit.SourceChoices.BUYBACK_CUSTOMER:
                            sale_status = InventoryUnit.SaleStatusChoices.RETURNED
                        else:
                            sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                        
                        # Create unit
                        unit = InventoryUnit.objects.create(
                            product_template=product,
                            serial_number=row.get('Serial Number'),
                            imei=row.get('IMEI'),
                            condition=row.get('Condition', 'N'),
                            grade=row.get('Grade'),
                            storage_gb=int(row['Storage (GB)']) if row.get('Storage (GB)') else None,
                            ram_gb=int(row['RAM (GB)']) if row.get('RAM (GB)') else None,
                            selling_price=Decimal(row['Selling Price']),
                            source=source,
                            sale_status=sale_status,
                            notes=row.get('Notes', ''),
                            created_by=request.user,
                        )
                        
                        # Auto-create ReturnRequest for buyback units
                        # Note: The signal also creates ReturnRequest, so check if one already exists
                        if source == InventoryUnit.SourceChoices.BUYBACK_CUSTOMER:
                            existing_request = unit.return_requests.filter(
                                status=ReturnRequest.StatusChoices.PENDING
                            ).first()
                            
                            if not existing_request:
                                return_request = ReturnRequest.objects.create(
                                    requesting_salesperson=None,  # Buyback units don't have a salesperson
                                    status=ReturnRequest.StatusChoices.PENDING,
                                    notes=f"Auto-created for buyback unit from CSV import (Row {row_num})"
                                )
                                return_request.inventory_units.add(unit)
                        
                        created_count += 1
                        
                        # Log the import
                        AuditLog.log_action(
                            user=request.user,
                            action=AuditLog.ActionType.CREATE,
                            obj=unit,
                            new_data={'source': 'CSV Import'},
                            request=request
                        )
                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
                        failed_count += 1
                
                # If too many errors, rollback
                if failed_count > created_count:
                    raise Exception("Too many errors, import cancelled")
        
        except Exception as e:
            return Response({
                "error": f"Import failed: {str(e)}",
                "created": 0,
                "failed": failed_count,
                "errors": errors[:10]  # Limit error messages
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            "success": True,
            "created": created_count,
            "failed": failed_count,
            "errors": errors[:10] if errors else None
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], permission_classes=[CanApproveRequests])
    def bulk_update(self, request):
        """
        Bulk update operations for inventory units (Inventory Manager only).
        Supports: price updates, status changes, archiving (for sold units).
        
        Request body:
        {
            "unit_ids": [1, 2, 3],
            "operation": "update_price" | "update_status" | "archive",
            "data": { ... operation-specific data ... }
        }
        """
        unit_ids = request.data.get('unit_ids', [])
        operation = request.data.get('operation')
        data = request.data.get('data', {})
        
        if not unit_ids or not isinstance(unit_ids, list):
            return Response(
                {"error": "unit_ids must be a non-empty list"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(unit_ids) > 100:
            return Response(
                {"error": "Maximum 100 units can be updated at once"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Fetch the units
        units = InventoryUnit.objects.filter(id__in=unit_ids)
        
        if units.count() != len(unit_ids):
            return Response(
                {"error": f"Some unit IDs not found. Requested: {len(unit_ids)}, Found: {units.count()}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = 0
        errors = []
        
        try:
            with transaction.atomic():
                if operation == 'update_price':
                    new_price = data.get('selling_price')
                    if not new_price:
                        return Response(
                            {"error": "selling_price is required for update_price operation"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Update prices
                    for unit in units:
                        unit.selling_price = Decimal(str(new_price))
                        unit.save(update_fields=['selling_price', 'updated_at'])
                        updated_count += 1
                    
                    message = f"Successfully updated price for {updated_count} unit(s)"
                
                elif operation == 'update_status':
                    new_status = data.get('sale_status')
                    if not new_status:
                        return Response(
                            {"error": "sale_status is required for update_status operation"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Validate status
                    valid_statuses = [choice[0] for choice in InventoryUnit.SaleStatusChoices.choices]
                    if new_status not in valid_statuses:
                        return Response(
                            {"error": f"Invalid status. Must be one of: {valid_statuses}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Update status
                    for unit in units:
                        # Prevent changing status of sold units
                        if unit.sale_status == InventoryUnit.SaleStatusChoices.SOLD:
                            errors.append(f"Unit #{unit.id} is already sold and cannot be modified")
                            continue
                        
                        unit.sale_status = new_status
                        unit.save(update_fields=['sale_status', 'updated_at'])
                        updated_count += 1
                    
                    message = f"Successfully updated status for {updated_count} unit(s)"
                
                elif operation == 'archive':
                    # Archive sold units (soft delete - mark as archived)
                    for unit in units:
                        if unit.sale_status != InventoryUnit.SaleStatusChoices.SOLD:
                            errors.append(f"Unit #{unit.id} must be SOLD before archiving")
                            continue
                        
                        # Mark as archived (you may want to add an 'is_archived' field to the model)
                        # For now, we'll just add a note in the description
                        unit.notes = (unit.notes or '') + f" [ARCHIVED: {timezone.now()}]"
                        unit.save(update_fields=['notes', 'updated_at'])
                        updated_count += 1
                    
                    message = f"Successfully archived {updated_count} unit(s)"
                
                else:
                    return Response(
                        {"error": f"Invalid operation: {operation}. Must be: update_price, update_status, or archive"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                return Response({
                    "success": True,
                    "message": message,
                    "updated_count": updated_count,
                    "errors": errors if errors else None
                }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"error": f"Bulk operation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# --- NEW: CUSTOMER-FACING SEARCH VIEW ---

class PhoneSearchByBudgetView(generics.ListAPIView):
    """
    GET: Allows customers to search for available phone Inventory Units 
    within a specified budget range.
    
    Query Params required:
    - min_price (required, decimal)
    - max_price (required, decimal)
    
    Example URL: /api/phone-search/?min_price=15000&max_price=30000
    """
    serializer_class = PublicInventoryUnitSerializer
    permission_classes = [permissions.AllowAny] 
    
    def get_queryset(self):
        # Retrieve and validate query parameters
        min_price_str = self.request.query_params.get('min_price')
        max_price_str = self.request.query_params.get('max_price')

        if not min_price_str or not max_price_str:
            # Raise exception if required params are missing
            raise exceptions.ParseError(
                "Both 'min_price' and 'max_price' query parameters are required for budget search."
            )

        try:
            min_price = Decimal(min_price_str)
            max_price = Decimal(max_price_str)
        except Exception:
            # Raise exception if prices are not valid numbers
            raise exceptions.ParseError("Prices must be valid numeric values.")
            
        if min_price > max_price:
             raise exceptions.ParseError("Minimum price cannot be greater than maximum price.")

        # 1. Start with available inventory units
        queryset = InventoryUnit.objects.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            # 2. Filter by Product Type: 'Phone' (case-insensitive for safety)
            product_template__product_type__iexact='Phone' 
        )
        
        # 3. Filter by Price Range
        queryset = queryset.filter(
            selling_price__gte=min_price,
            selling_price__lte=max_price
        )
        
        # 4. Optimize lookup for nested serializer display
        queryset = queryset.select_related(
            'product_template', 
            'product_color'
        ).order_by('selling_price') # Order by ascending price
        
        return queryset

    def list(self, request, *args, **kwargs):
        """Cache budget search results to smooth spikes."""
        debug_enabled = settings.DEBUG or request.query_params.get('debug') == '1'
        cache_enabled = not debug_enabled and request.method == 'GET'
        if cache_enabled:
            cache_key = "public_phone_search:" + urlencode(sorted(request.query_params.items()))
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

        response = super().list(request, *args, **kwargs)
        if cache_enabled and hasattr(response, 'data'):
            cache.set(cache_key, response.data, 120)
        return response


class PublicAvailableUnitsView(generics.ListAPIView):
    """
    Public: Browse all available units (public fields), with optional filters.
    Intended for storefront discovery pages (shop/browse/search).
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicInventoryUnitSerializer

    def get_queryset(self):
        qs = InventoryUnit.objects.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE
        ).select_related('product_template', 'product_color').order_by('selling_price')

        brand = self.request.query_params.get('brand')
        if brand:
            qs = qs.filter(product_template__brand__iexact=brand)

        product_type = self.request.query_params.get('product_type')
        if product_type:
            qs = qs.filter(product_template__product_type__iexact=product_type)

        return qs


# --- SALES AND REVIEWS VIEWSETS ---

class ReviewViewSet(viewsets.ModelViewSet):
    """
    Handles customer and admin reviews.
    - Everyone can read (GET).
    - Authenticated users can create (POST).
    - Owners or Admins can update/delete (PUT/PATCH/DELETE).
    - Uses IsReviewOwnerOrAdmin.
    - Supports video file uploads via multipart/form-data.
    """
    queryset = Review.objects.all().select_related('product', 'customer__user').order_by('-date_posted')
    serializer_class = ReviewSerializer
    permission_classes = [IsReviewOwnerOrAdmin]  # Base permission, overridden in get_permissions
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product']  # Allow filtering by product ID
    search_fields = ['comment', 'product__product_name']
    ordering_fields = ['date_posted', 'rating']
    ordering = ['-date_posted']  # Default ordering
    
    def get_queryset(self):
        """Filter reviews by brand for public API."""
        queryset = super().get_queryset()
        
        # For public API, filter by brand if available
        brand = getattr(self.request, 'brand', None)
        if brand:
            queryset = queryset.filter(
                Q(product__brands=brand) |
                Q(product__brands__isnull=True) |
                Q(product__is_global=True)
            ).distinct()
        
        return queryset
    
    # Enable multipart parsing for file uploads
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        """Apply role-based permissions."""
        # Allow public read access (list and retrieve)
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        elif self.action == 'create':
            # For staff users, check if they're Content Creator
            # For non-staff, allow authenticated customers
            if self.request.user.is_authenticated and self.request.user.is_staff:
                return [CanCreateReviews()]
            elif self.request.user.is_authenticated:
                return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Content Creators can edit/delete all reviews
            if self.request.user.is_authenticated and self.request.user.is_staff:
                admin = get_admin_from_user(self.request.user)
                if admin and admin.is_content_creator:
                    return [IsAdminUser()]  # Allow Content Creators to edit any review
        return [IsReviewOwnerOrAdmin()]
    
    def perform_create(self, serializer):
        """
        Injects the authenticated user's Customer profile into the Review before saving.
        If user is admin (Content Creator), customer is set to None (admin review).
        """
        if not self.request.user.is_authenticated:
            raise exceptions.AuthenticationFailed("You must be logged in to post a review.")

        # Check if user is admin (staff) - Content Creator or other admin
        if self.request.user.is_staff:
            # Admin/Content Creator can create reviews without a customer profile
            serializer.save(customer=None)
        else:
            # Regular customers must have a Customer profile
            try:
                customer = Customer.objects.get(user=self.request.user)
                review = serializer.save(customer=customer)
            except Customer.DoesNotExist:
                raise exceptions.PermissionDenied("Review creation requires a valid Customer profile.")

            if review and (not review.purchase_date or not review.product_condition):
                order_item = (
                    OrderItem.objects
                    .filter(
                        order__customer=review.customer,
                        inventory_unit__product_template=review.product,
                        order__status__in=[Order.StatusChoices.PAID, Order.StatusChoices.DELIVERED]
                    )
                    .select_related('order', 'inventory_unit')
                    .order_by('-order__created_at')
                    .first()
                )

                if order_item:
                    update_fields = []
                    if not review.purchase_date:
                        review.purchase_date = order_item.order.created_at.date()
                        update_fields.append('purchase_date')
                    if not review.product_condition and order_item.inventory_unit:
                        review.product_condition = order_item.inventory_unit.get_condition_display()
                        update_fields.append('product_condition')

                    if update_fields:
                        review.save(update_fields=update_fields)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def bulk_action(self, request):
        """
        Bulk actions for reviews (approve, reject, delete, hide).
        Content Creators can use this to moderate reviews.
        """
        action_type = request.data.get('action')  # 'approve', 'reject', 'delete', 'hide'
        review_ids = request.data.get('review_ids', [])
        
        if not action_type or not review_ids:
            return Response(
                {'error': 'action and review_ids are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reviews = Review.objects.filter(id__in=review_ids)
        
        if action_type == 'delete':
            count = reviews.count()
            reviews.delete()
            return Response({'message': f'{count} review(s) deleted successfully'})
        elif action_type == 'hide':
            # Add a hidden flag if needed, or use a status field
            # For now, we'll just return success
            return Response({'message': f'{reviews.count()} review(s) hidden successfully'})
        else:
            return Response(
                {'error': f'Unknown action: {action_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class AdminRoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing available admin roles.
    Read-only access to see what roles can be assigned.
    """
    queryset = AdminRole.objects.all()
    serializer_class = AdminRoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Return all roles without pagination


class TagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product tags.
    - All authenticated staff users can read
    - Content Creators and Inventory Managers can create/edit/delete
    """
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None  # Return all tags without pagination (reasonable assumption)


class AdminViewSet(viewsets.ModelViewSet):
    """
    Admin management ViewSet. Superuser-only access.
    - List all admins
    - Create new admin accounts
    - Retrieve/Update/Delete admin profiles
    - Assign/remove roles
    """
    queryset = Admin.objects.all().select_related('user').prefetch_related('roles', 'brands').order_by('-id')
    permission_classes = [IsSuperuser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AdminCreateSerializer
        return AdminSerializer
    
    def get_queryset(self):
        """Return admins with user details for list view."""
        return Admin.objects.all().select_related('user').prefetch_related('roles', 'brands').order_by('-user__date_joined')
    
    def create(self, request, *args, **kwargs):
        """Override create to provide better error handling."""
        from rest_framework import serializers

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except serializers.ValidationError as e:
            # Return validation errors in a clear format
            logger.error(f"Admin creation validation error: {e.detail}")
            return Response(
                {"error": "Validation failed", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Catch any other exceptions and return a proper error message
            import traceback

            error_trace = traceback.format_exc()
            logger.error(f"Admin creation error: {str(e)}\n{error_trace}")
            return Response(
                {
                    "error": "Failed to create admin",
                    "detail": str(e)
                    if settings.DEBUG
                    else "An error occurred while creating the admin account. Please check that all fields are valid and the admin code is unique.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    @action(detail=True, methods=['post', 'put'], url_path='roles')
    def assign_roles(self, request, pk=None):
        """Assign or update roles for an admin."""
        admin = self.get_object()
        role_ids = request.data.get('role_ids', [])
        
        if not isinstance(role_ids, list):
            return Response({'error': 'role_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            roles = AdminRole.objects.filter(id__in=role_ids)
            admin.roles.set(roles)
            serializer = self.get_serializer(admin)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post', 'put'], url_path='brands')
    def assign_brands(self, request, pk=None):
        """Assign or update brands for an admin."""
        admin = self.get_object()
        brand_ids = request.data.get('brand_ids', [])
        is_global = request.data.get('is_global_admin', False)
        
        if not isinstance(brand_ids, list):
            return Response(
                {'error': 'brand_ids must be a list'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Update global admin flag
            admin.is_global_admin = is_global
            admin.save()
            
            # Assign brands (empty list = no brands, global admin can have empty brands)
            if not is_global:
                brands = Brand.objects.filter(id__in=brand_ids, is_active=True)
                admin.brands.set(brands)
            else:
                # Global admin doesn't need specific brand assignments
                admin.brands.clear()
            
            serializer = self.get_serializer(admin)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def perform_destroy(self, instance):
        """
        Override to delete the associated User when an Admin is deleted.
        This allows the email and username to be reused for new admin accounts.
        
        Note: The User is only deleted if it's not associated with a Customer.
        If the User has a Customer profile, we keep the User but remove the Admin association.
        """
        user = instance.user
        admin_code = instance.admin_code
        
        logger.info(f"Deleting admin {admin_code} and associated user {user.username if user else 'None'}")
        
        # Delete the Admin instance first
        instance.delete()
        
        # Delete the associated User if it exists and has no Customer profile
        # This allows the email and username to be reused for new admin accounts
        if user:
            try:
                # Check if user has a Customer profile
                has_customer = hasattr(user, 'customer') and user.customer is not None
                
                if has_customer:
                    logger.warning(
                        f"User {user.username} has a Customer profile. "
                        f"Keeping User but Admin association removed. "
                        f"Email/username will not be available for reuse."
                    )
                else:
                    # Safe to delete the User - no Customer profile exists
                    user.delete()
                    logger.info(f"Successfully deleted user {user.username} associated with admin {admin_code}")
            except Exception as e:
                logger.error(f"Error deleting user {user.username}: {str(e)}")
                # Don't raise exception - admin is already deleted
                # Just log the error


class OrderViewSet(viewsets.ModelViewSet):
    """
    Handles Order creation and management.
    - Admins can view/manage all orders.
    - Customers can only view/manage their own orders.
    - Guest users can create orders (no login required).
    """
    serializer_class = OrderSerializer
    lookup_field = 'order_id'  # Use order_id (UUID) as the lookup field instead of default 'pk'
    lookup_url_kwarg = 'order_id'  # Explicitly set URL kwarg name to match lookup_field
    
    def get_permissions(self):
        """
        Allow unauthenticated access for:
        - create (order creation)
        - initiate_payment (payment initiation for guest checkout)
        - payment_status (checking payment status for guest checkout)
        - receipt (receipt download for paid orders, including guest checkout)
        - retrieve (order detail view for paid orders, including guest checkout)
        Require authentication for all other actions.
        """
        if self.action in ['create', 'initiate_payment', 'payment_status', 'receipt', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """
        Filters the queryset:
        - Salespersons: See all their orders (PENDING and PAID) from their assigned brands
        - Order Managers: See only orders where payment is confirmed (PAID, DELIVERED, CANCELED)
        - Superusers/Global Admins: See all orders
        - Customers: See only their own orders
        Includes extensive prefetching for N+1 query optimization.
        """
        # Base query for all users
        queryset = Order.objects.all().order_by('-created_at').select_related('customer__user', 'brand')
        
        # Prefetch related data to optimize nested serializer lookups:
        queryset = queryset.prefetch_related(
            # Prefetch all order items for the order
            'order_items',
            # Prefetch the InventoryUnit linked to each OrderItem
            'order_items__inventory_unit',
            # Prefetch the Product Template linked to the Inventory Unit
            'order_items__inventory_unit__product_template',
            # Prefetch the Color linked to the Inventory Unit
            'order_items__inventory_unit__product_color',
            # Prefetch source_lead for online orders (to get delivery address and phone)
            'source_lead'
        )

        if self.request.user.is_staff:
            user = self.request.user
            
            # Superuser sees all orders
            if user.is_superuser:
                return queryset
            
            try:
                admin = Admin.objects.get(user=user)
                
                if admin.is_global_admin:
                    # Global admins see all orders
                    return queryset
                
                # Salespersons see all their orders (PENDING and PAID) from their assigned brands
                if admin.is_salesperson:
                    if admin.brands.exists():
                        # Filter by orders from salesperson's assigned brands
                        queryset = queryset.filter(brand__in=admin.brands.all())
                    else:
                        # Salesperson with no brands sees only WALK_IN orders (they created)
                        queryset = queryset.filter(order_source=Order.OrderSourceChoices.WALK_IN)
                    return queryset
                
                # Order Managers only see ONLINE orders where payment is confirmed
                # Walk-in orders are handled by salespersons
                if admin.is_order_manager:
                    queryset = queryset.filter(
                        order_source=Order.OrderSourceChoices.ONLINE,  # Only ONLINE orders
                        status__in=[
                            Order.StatusChoices.PAID,
                            Order.StatusChoices.DELIVERED,
                            Order.StatusChoices.CANCELED
                        ]
                    )
                    # Filter by assigned brands if not global
                    if admin.brands.exists():
                        queryset = queryset.filter(brand__in=admin.brands.all())
                    return queryset
                
                # Other admins filter by brand
                if admin.brands.exists():
                    queryset = queryset.filter(brand__in=admin.brands.all())
                else:
                    return Order.objects.none()
            except Admin.DoesNotExist:
                # Staff user without admin profile sees nothing
                return Order.objects.none()
        
        # Non-staff users (Customers) filter by their own Customer profile
        if not self.request.user.is_authenticated:
            # Unauthenticated users can only access orders by order_id (via detail view)
            # They cannot list orders
            if self.action == 'list':
                return Order.objects.none()
            # For detail/retrieve, allow access (will be filtered by order_id lookup)
            # Permission check for paid orders is done in retrieve() method
            return queryset
        
        try:
            customer = Customer.objects.get(user=self.request.user)
            return queryset.filter(customer=customer)
        except Customer.DoesNotExist:
            # If an authenticated user somehow lacks a Customer profile, show nothing
            return Order.objects.none()

    def get_object(self):
        """
        Override get_object to handle unauthenticated access for receipt and retrieve actions.
        For these actions, we allow direct lookup by order_id without queryset filtering.
        
        IMPORTANT: This method is called by DRF BEFORE the action method runs.
        If this raises a 404, the action method never gets called.
        """
        # Get the lookup value from kwargs
        # DRF might use 'pk' or the actual lookup_field name
        # When lookup_field='order_id', DRF uses 'order_id' as the URL kwarg name
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        # Try multiple possible kwarg names: order_id, pk, or the lookup_field value
        lookup_value = (
            self.kwargs.get(lookup_url_kwarg) or 
            self.kwargs.get('pk') or 
            self.kwargs.get('order_id') or
            self.kwargs.get(self.lookup_field)
        )
        
        # #region agent log
        import json, time
        log_path = '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log'
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'B',
                    'location': 'inventory/views.py:get_object',
                    'message': 'get_object() called',
                    'data': {
                        'action': getattr(self, 'action', 'NOT_SET'),
                        'path': self.request.path,
                        'full_url': self.request.build_absolute_uri() if hasattr(self.request, 'build_absolute_uri') else 'N/A',
                        'has_receipt_in_path': 'receipt' in self.request.path,
                        'lookup_value': str(lookup_value) if lookup_value else None,
                        'resolver_match_route': self.request.resolver_match.route if hasattr(self.request, 'resolver_match') and self.request.resolver_match else None,
                        'resolver_match_url_name': self.request.resolver_match.url_name if hasattr(self.request, 'resolver_match') and self.request.resolver_match else None,
                        'resolver_match_kwargs': dict(self.request.resolver_match.kwargs) if hasattr(self.request, 'resolver_match') and self.request.resolver_match else None,
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[DEBUG] Failed to write log: {e}")
        # #endregion
        
        # Log the lookup attempt
        print(f"\n[GET_OBJECT] ========== get_object() CALLED ==========")
        print(f"[GET_OBJECT] Action: {getattr(self, 'action', 'NOT_SET')}")
        print(f"[GET_OBJECT] Lookup field: {self.lookup_field}")
        print(f"[GET_OBJECT] Lookup URL kwarg: {lookup_url_kwarg}")
        print(f"[GET_OBJECT] Lookup value: {lookup_value}")
        print(f"[GET_OBJECT] Request path: {self.request.path}")
        print(f"[GET_OBJECT] Full URL: {self.request.build_absolute_uri() if hasattr(self.request, 'build_absolute_uri') else 'N/A'}")
        if hasattr(self.request, 'resolver_match') and self.request.resolver_match:
            print(f"[GET_OBJECT] Resolver route: {self.request.resolver_match.route}")
            print(f"[GET_OBJECT] Resolver URL name: {self.request.resolver_match.url_name}")
        print(f"[GET_OBJECT] All kwargs: {self.kwargs}")
        
        logger.info("get_object() called", extra={
            'action': getattr(self, 'action', 'NOT_SET'),
            'lookup_field': self.lookup_field,
            'lookup_url_kwarg': lookup_url_kwarg,
            'lookup_value': str(lookup_value) if lookup_value else None,
            'request_path': self.request.path,
            'all_kwargs': dict(self.kwargs),
        })
        
        # Check if this is a receipt or retrieve request by examining the path
        # This is critical because self.action might not be set when get_object() is called
        # CRITICAL: Check resolver_match to see what route actually matched
        is_receipt_request = False
        if hasattr(self.request, 'resolver_match') and self.request.resolver_match:
            route = self.request.resolver_match.route
            url_name = getattr(self.request.resolver_match, 'url_name', '')
            print(f"[GET_OBJECT] Resolver route: {route}")
            print(f"[GET_OBJECT] Resolver URL name: {url_name}")
            # Check if the route or URL name indicates receipt
            if 'receipt' in route or 'receipt' in url_name:
                is_receipt_request = True
                # Force action to be 'receipt' so DRF routes correctly
                self.action = 'receipt'
                print(f"[GET_OBJECT] DETECTED receipt route, forcing action to 'receipt'")
        
        # Also check the path directly as fallback
        if not is_receipt_request and 'receipt' in self.request.path:
            is_receipt_request = True
            self.action = 'receipt'
            print(f"[GET_OBJECT] DETECTED 'receipt' in path, forcing action to 'receipt'")
            print(f"[GET_OBJECT] WARNING: Resolver route doesn't match receipt, but path contains 'receipt'")
            print(f"[GET_OBJECT] This suggests a routing issue - receipt route may not be registered correctly")
        
        is_receipt_or_retrieve = is_receipt_request or getattr(self, 'action', None) in ['receipt', 'retrieve']
        
        # For receipt/retrieve requests, always do direct lookup to bypass queryset filtering
        # First, ensure we have the lookup_value (extract from path if needed)
        if is_receipt_or_retrieve and not lookup_value:
            path_parts = [p for p in self.request.path.split('/') if p]  # Remove empty strings
            if 'orders' in path_parts:
                orders_index = path_parts.index('orders')
                if orders_index + 1 < len(path_parts):
                    potential_order_id = path_parts[orders_index + 1]
                    # Validate it looks like a UUID (with or without dashes)
                    if len(potential_order_id) >= 32:  # Accept both formats
                        lookup_value = potential_order_id
                        print(f"[GET_OBJECT] Extracted lookup_value from path for receipt/retrieve: {lookup_value}")
        
        # If lookup_field is 'order_id' and we have a lookup_value, try direct lookup
        # This works for both receipt/retrieve and other actions
        if self.lookup_field == 'order_id' and lookup_value:
            try:
                # Direct lookup by order_id, bypassing queryset filtering
                # Handle both UUID string and UUID object
                from uuid import UUID
                if isinstance(lookup_value, str):
                    # Try to convert string to UUID if needed
                    try:
                        lookup_value = UUID(lookup_value)
                    except ValueError:
                        # If it's not a valid UUID string, use as-is (might be a different format)
                        pass
                
                print(f"[GET_OBJECT] Attempting direct lookup for order_id: {lookup_value} (type: {type(lookup_value).__name__})")
                # #region agent log
                try:
                    order_exists = Order.objects.filter(order_id=lookup_value).exists()
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'B',
                            'location': 'inventory/views.py:get_object',
                            'message': 'Before Order.objects.get()',
                            'data': {
                                'order_id': str(lookup_value),
                                'order_exists': order_exists,
                            },
                            'timestamp': int(time.time() * 1000)
                        }) + '\n')
                except Exception as e:
                    print(f"[DEBUG] Failed to write log: {e}")
                # #endregion
                order = Order.objects.get(order_id=lookup_value)
                print(f"[GET_OBJECT] Order found: {order.order_id}, status: {order.status}")
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'B',
                            'location': 'inventory/views.py:get_object',
                            'message': 'Order found in get_object()',
                            'data': {
                                'order_id': str(order.order_id),
                                'order_status': order.status,
                            },
                            'timestamp': int(time.time() * 1000)
                        }) + '\n')
                except Exception as e:
                    print(f"[DEBUG] Failed to write log: {e}")
                # #endregion
                logger.info("Order found via get_object() direct lookup", extra={
                    'order_id': str(order.order_id),
                    'order_status': order.status,
                    'is_receipt_or_retrieve': is_receipt_or_retrieve,
                })
                return order
            except Order.DoesNotExist:
                print(f"[GET_OBJECT] Order not found: {lookup_value}")
                # #region agent log
                try:
                    total_orders = Order.objects.count()
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'B',
                            'location': 'inventory/views.py:get_object',
                            'message': 'Order.DoesNotExist in get_object()',
                            'data': {
                                'order_id': str(lookup_value),
                                'total_orders_in_db': total_orders,
                                'error': 'Order.DoesNotExist',
                            },
                            'timestamp': int(time.time() * 1000)
                        }) + '\n')
                except Exception as e:
                    print(f"[DEBUG] Failed to write log: {e}")
                # #endregion
                logger.error(f"Order not found in get_object(): {lookup_value}", extra={
                    'lookup_value': str(lookup_value),
                    'lookup_value_type': type(lookup_value).__name__,
                    'request_path': self.request.path,
                    'all_kwargs': dict(self.kwargs),
                })
                # Check if order exists at all
                total_orders = Order.objects.count()
                logger.warning(f"Total orders in database: {total_orders}")
                raise exceptions.NotFound(f"Order with ID {lookup_value} not found.")
            except Exception as e:
                print(f"[GET_OBJECT] Error in lookup: {str(e)}")
                logger.error(f"Error in get_object(): {str(e)}", exc_info=True, extra={
                    'lookup_value': str(lookup_value),
                    'error_type': type(e).__name__,
                })
                raise
        
        # For other actions, use default behavior
        print(f"[GET_OBJECT] Using default get_object() behavior")
        try:
            return super().get_object()
        except Exception as e:
            print(f"[GET_OBJECT] Default get_object() failed: {str(e)}")
            logger.error(f"Default get_object() failed: {str(e)}", exc_info=True)
            raise

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to allow unauthenticated users to view paid orders.
        This enables guest checkout users to view their order details after payment.
        
        CRITICAL FIX: Also check if this is actually a receipt request that was
        incorrectly routed to retrieve. If the path contains '/receipt/', redirect to receipt method.
        """
        # #region agent log
        logger.info("DEBUG: OrderViewSet.retrieve() called", extra={
            'hypothesisId': 'B',
            'location': 'inventory/views.py:retrieve',
            'path': request.path,
            'full_url': request.build_absolute_uri() if hasattr(request, 'build_absolute_uri') else 'N/A',
            'has_receipt_in_path': 'receipt' in request.path,
            'method': request.method,
            'resolver_match_route': request.resolver_match.route if hasattr(request, 'resolver_match') and request.resolver_match else None,
            'resolver_match_url_name': request.resolver_match.url_name if hasattr(request, 'resolver_match') and request.resolver_match else None,
        })
        # #endregion
        
        order = self.get_object()
        
        # Check permissions:
        # - Staff can always view orders
        # - Authenticated users can view their own orders
        # - Unauthenticated users can only view paid orders (guest checkout after payment)
        if request.user.is_staff:
            # Staff can view any order
            pass
        elif request.user.is_authenticated:
            # Authenticated users can only view their own orders
            try:
                customer = Customer.objects.get(user=request.user)
                if order.customer != customer:
                    return Response(
                        {'error': 'You do not have permission to view this order.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Customer.DoesNotExist:
                # If user has no customer profile, deny access
                return Response(
                    {'error': 'You do not have permission to view this order.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            # Unauthenticated users can only view paid orders (guest checkout)
            if order.status != Order.StatusChoices.PAID:
                return Response(
                    {'error': 'Order details are only available for paid orders.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Use parent retrieve method to return the order
        return super().retrieve(request, *args, **kwargs)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Override create to handle idempotency via Idempotency-Key header.
        If an order with the same idempotency key exists, return it instead of creating a new one.
        """
        # #region agent log
        import json, time
        from django.conf import settings
        from django.utils import timezone
        # Use PESAPAL_LOG_PATH from environment variable, fallback to /tmp/pesapal_debug.log
        log_path = getattr(settings, 'PESAPAL_LOG_PATH', '/tmp/pesapal_debug.log')
        logger.info("Order creation request received", extra={
            'has_idempotency_key_header': bool(request.headers.get('Idempotency-Key') or request.headers.get('X-Idempotency-Key')),
            'method': request.method,
            'user_authenticated': request.user.is_authenticated if hasattr(request, 'user') else False,
        })
        # #endregion
        
        # Check for idempotency key in header
        idempotency_key = request.headers.get('Idempotency-Key') or request.headers.get('X-Idempotency-Key')
        
        # #region agent log
        logger.info("Idempotency key extracted from header", extra={
            'idempotency_key_present': bool(idempotency_key),
            'idempotency_key_preview': idempotency_key[:20] + '...' if idempotency_key else None,
        })
        # #endregion
        
        if idempotency_key:
            # Check if order with this key already exists
            try:
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'B',
                            'location': 'inventory/views.py:OrderViewSet.create',
                            'message': 'Attempting to query existing order by idempotency_key',
                            'data': {
                                'idempotency_key': idempotency_key[:20] + '...',
                            },
                            'timestamp': int(timezone.now().timestamp() * 1000)
                        }) + '\n')
                except Exception as e:
                    print(f"[DEBUG] Failed to write log: {e}")
                # #endregion
                
                # Check if idempotency_key column exists in database
                column_exists = False
                try:
                    from django.db import connection
                    with connection.cursor() as cursor:
                        # Try to get table name from model's db_table or use default
                        table_name = Order._meta.db_table
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                            AND column_name = 'idempotency_key'
                        """, [table_name])
                        column_exists = cursor.fetchone() is not None
                except Exception as db_check_error:
                    # #region agent log
                    try:
                        import traceback
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'A',
                                'location': 'inventory/views.py:OrderViewSet.create',
                                'message': 'ERROR checking if idempotency_key column exists',
                                'data': {
                                    'error_type': type(db_check_error).__name__,
                                    'error_message': str(db_check_error),
                                    'traceback': traceback.format_exc(),
                                },
                                'timestamp': int(timezone.now().timestamp() * 1000)
                            }) + '\n')
                    except Exception as e:
                        print(f"[DEBUG] Failed to write log: {e}")
                    # #endregion
                    # If we can't check, assume column doesn't exist to be safe
                    column_exists = False
                    logger.warning(f"Could not check if idempotency_key column exists: {str(db_check_error)}")
                
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'A',
                            'location': 'inventory/views.py:OrderViewSet.create',
                            'message': 'Checked if idempotency_key column exists',
                            'data': {
                                'column_exists': column_exists,
                            },
                            'timestamp': int(timezone.now().timestamp() * 1000)
                        }) + '\n')
                except Exception as e:
                    print(f"[DEBUG] Failed to write log: {e}")
                # #endregion
                
                if not column_exists:
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'A',
                                'location': 'inventory/views.py:OrderViewSet.create',
                                'message': 'CONFIRMED: idempotency_key column does not exist - migration not run',
                                'data': {
                                    'error': 'Migration 0027_add_idempotency_key_to_order has not been applied',
                                },
                                'timestamp': int(timezone.now().timestamp() * 1000)
                            }) + '\n')
                    except Exception as e:
                        print(f"[DEBUG] Failed to write log: {e}")
                    # #endregion
                    # Column doesn't exist - skip idempotency check and proceed with normal creation
                    logger.warning("idempotency_key column does not exist - migration may not have been run. Proceeding without idempotency check.")
                else:
                    # Column exists - proceed with idempotency check
                    try:
                        existing_order = Order.objects.select_related('customer', 'user').prefetch_related('order_items').get(
                            idempotency_key=idempotency_key
                        )
                    
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'B',
                                    'location': 'inventory/views.py:OrderViewSet.create',
                                    'message': 'Existing order found - returning idempotent response',
                                    'data': {
                                        'existing_order_id': str(existing_order.order_id),
                                    },
                                    'timestamp': int(timezone.now().timestamp() * 1000)
                                }) + '\n')
                        except Exception as e:
                            print(f"[DEBUG] Failed to write log: {e}")
                        # #endregion
                        
                        # Order with this idempotency key already exists - return it (idempotent)
                        logger.info(f"Idempotent order request - returning existing order {existing_order.order_id} for key {idempotency_key}")
                        response_serializer = self.get_serializer(existing_order)
                        headers = self.get_success_headers(response_serializer.data)
                        # Return 200 OK with existing order data
                        return Response(response_serializer.data, status=status.HTTP_200_OK, headers=headers)
                    except Order.DoesNotExist:
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'B',
                                    'location': 'inventory/views.py:OrderViewSet.create',
                                    'message': 'No existing order found - proceeding with creation',
                                    'data': {},
                                    'timestamp': int(timezone.now().timestamp() * 1000)
                                }) + '\n')
                        except Exception as e:
                            print(f"[DEBUG] Failed to write log: {e}")
                        # #endregion
                        # No existing order with this key - proceed with creation
                        pass
                    except Exception as e:
                        # #region agent log
                        try:
                            import traceback
                            with open(log_path, 'a') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'B',
                                    'location': 'inventory/views.py:OrderViewSet.create',
                                    'message': 'ERROR checking idempotency key - database query failed',
                                    'data': {
                                        'error_type': type(e).__name__,
                                        'error_message': str(e),
                                        'traceback': traceback.format_exc(),
                                    },
                                    'timestamp': int(timezone.now().timestamp() * 1000)
                                }) + '\n')
                        except Exception as log_err:
                            print(f"[DEBUG] Failed to write log: {log_err}")
                        # #endregion
                        # Log error but continue with order creation
                        logger.warning(f"Error checking idempotency key: {str(e)}")
            except Exception as e:
                # Catch any other exceptions from the idempotency check (e.g., database connection errors)
                logger.warning(f"Unexpected error during idempotency check: {str(e)}")
                # Continue with normal order creation
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'inventory/views.py:OrderViewSet.create',
                    'message': 'Proceeding to super().create()',
                    'data': {},
                    'timestamp': int(timezone.now().timestamp() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[DEBUG] Failed to write log: {e}")
        # #endregion
        
        # Continue with normal order creation flow
        try:
            logger.info("About to call super().create()", extra={
                'request_data_keys': list(request.data.keys()) if hasattr(request, 'data') else [],
            })
            
            result = super().create(request, *args, **kwargs)
            
            logger.info("super().create() completed successfully", extra={
                'status_code': result.status_code if hasattr(result, 'status_code') else None,
            })
            return result
        except exceptions.ValidationError as e:
            # Handle validation errors separately - return 400 instead of 500
            logger.error(f"Order creation validation error: {e.detail}", exc_info=True)
            return Response(
                {"error": "Validation failed", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Log the full error with traceback - this will show up in Render logs
            logger.error(
                f"ERROR in order creation: {type(e).__name__}: {str(e)}",
                exc_info=True,
                extra={
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'location': 'OrderViewSet.create',
                    'request_data': str(request.data) if hasattr(request, 'data') else 'N/A',
                }
            )
            # Re-raise the exception so it's returned as 500 error
            raise

    @transaction.atomic
    def perform_create(self, serializer):
        """
        Creates order for authenticated or guest customers.
        For guest customers, creates/gets customer from form data.
        The OrderSerializer's .create() method handles the full, atomic inventory update logic.
        Supports idempotency via Idempotency-Key header.
        """
        from inventory.services.customer_service import CustomerService
        
        # Get idempotency key from header (already checked in create method, but need it here too)
        idempotency_key = self.request.headers.get('Idempotency-Key') or self.request.headers.get('X-Idempotency-Key')
        
        # Get customer data from request
        customer_name = self.request.data.get('customer_name')
        customer_phone = self.request.data.get('customer_phone')
        customer_email = self.request.data.get('customer_email')
        delivery_address = self.request.data.get('delivery_address')
        
        admin = get_admin_from_user(self.request.user) if self.request.user.is_authenticated and self.request.user.is_staff else None
        
        if self.request.user.is_authenticated and self.request.user.is_staff:
            # Sales/admin staff create walk-in orders for the provided customer details
            if not admin:
                raise exceptions.PermissionDenied("Staff account is missing an admin profile.")
            is_walk_in_creator = (
                self.request.user.is_superuser or
                (admin and (admin.is_salesperson or admin.is_global_admin))
            )
            if not is_walk_in_creator:
                raise exceptions.PermissionDenied("You do not have permission to create walk-in orders.")
            if not customer_name or not customer_phone:
                raise exceptions.ValidationError({
                    'customer_name': 'This field is required for walk-in orders.',
                    'customer_phone': 'This field is required for walk-in orders.'
                })
            customer, _ = CustomerService.get_or_create_customer(
                name=customer_name,
                phone=customer_phone,
                email=customer_email,
                delivery_address=delivery_address
            )
            user = customer.user if customer and customer.user else None
        elif self.request.user.is_authenticated:
            # Authenticated customer - use existing customer profile
            try:
                customer = Customer.objects.get(user=self.request.user)
                user = self.request.user
            except Customer.DoesNotExist:
                raise exceptions.PermissionDenied("Cannot place order without a Customer profile.")
        else:
            # Guest customer - create/get customer from form data
            if not customer_name or not customer_phone:
                raise exceptions.ValidationError({
                    'customer_name': 'This field is required for guest orders.',
                    'customer_phone': 'This field is required for guest orders.'
                })
            
            customer, _ = CustomerService.get_or_create_customer(
                name=customer_name,
                phone=customer_phone,
                email=customer_email,
                delivery_address=delivery_address
            )
            user = None  # No user account for guest customers
        
        # Set order_source default based on context (walk-in for staff, online for others)
        order_source = self.request.data.get('order_source')
        if not order_source:
            if self.request.user.is_authenticated and self.request.user.is_staff:
                order_source = Order.OrderSourceChoices.WALK_IN
            else:
                order_source = Order.OrderSourceChoices.ONLINE
        if 'order_source' not in serializer.validated_data:
            serializer.validated_data['order_source'] = order_source

        # Ensure staff orders are associated with a brand
        # Exception: ONLINE orders created by staff don't require brand (they're customer-facing)
        brand_id = self.request.data.get('brand') or self.request.data.get('brand_id')
        brand = None
        if brand_id:
            try:
                brand = Brand.objects.get(id=brand_id, is_active=True)
            except Brand.DoesNotExist:
                raise exceptions.ValidationError({'brand': 'Invalid brand.'})
            if self.request.user.is_authenticated and self.request.user.is_staff:
                if not admin:
                    raise exceptions.PermissionDenied("Staff account is missing an admin profile.")
                if not (self.request.user.is_superuser or admin.is_global_admin):
                    if admin.brands.exists():
                        if not admin.brands.filter(id=brand.id).exists():
                            raise exceptions.PermissionDenied("Brand is not assigned to your role.")
                    else:
                        raise exceptions.PermissionDenied("You must be assigned to at least one brand to create orders.")
        elif self.request.user.is_authenticated and self.request.user.is_staff:
            if not admin:
                raise exceptions.PermissionDenied("Staff account is missing an admin profile.")
            # Only require brand for WALK_IN orders; ONLINE orders can proceed without brand
            if order_source == Order.OrderSourceChoices.WALK_IN:
                if admin.brands.count() == 1:
                    brand = admin.brands.first()
                else:
                    raise exceptions.ValidationError({'brand': 'Brand is required for walk-in orders created by staff.'})
            # For ONLINE orders, allow proceeding without brand (similar to guest orders)
            # If salesperson has exactly one brand, auto-assign it for convenience
            elif order_source == Order.OrderSourceChoices.ONLINE:
                if admin.brands.count() == 1:
                    brand = admin.brands.first()
                # If 0 or 2+ brands, allow order to proceed without brand (ONLINE orders don't require brand)
                # brand will remain None, which is acceptable for ONLINE orders
        
        logger.info("About to save order", extra={
            'has_idempotency_key': bool(idempotency_key),
            'idempotency_key_preview': idempotency_key[:20] + '...' if idempotency_key else None,
            'customer_id': customer.id if customer else None,
            'user_id': user.id if user else None,
            'order_source': order_source,
            'brand_id': brand.id if brand else None,
        })
        
        # Save the order, passing the customer, user, order_source, and idempotency_key to the serializer's create() method
        # The serializer handles the rest (OrderItem creation, inventory deduction, total calculation).
        # Migration 0027 is applied, so idempotency_key column exists
        try:
            save_kwargs = {
                'customer': customer,
                'user': user,
                'order_source': order_source,
            }
            if brand:
                save_kwargs['brand'] = brand
            if idempotency_key:
                save_kwargs['idempotency_key'] = idempotency_key
                logger.info(f"Saving order with idempotency_key: {idempotency_key[:20]}...")
            else:
                logger.info("Saving order without idempotency_key")
            
            serializer.save(**save_kwargs)
            
            logger.info(f"Order saved successfully: {serializer.instance.order_id if serializer.instance else 'N/A'}")
        except Exception as e:
            # Log the full error with traceback - this will show up in Render logs
            logger.error(
                f"ERROR in perform_create: {type(e).__name__}: {str(e)}",
                exc_info=True,
                extra={
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'location': 'OrderViewSet.perform_create',
                    'has_idempotency_key': bool(idempotency_key),
                    'customer_id': customer.id if customer else None,
                    'order_source': order_source,
                }
            )
            raise
    
    def update(self, request, *args, **kwargs):
        """
        Override update to allow partial updates (status-only updates).
        This allows updating just the status without requiring all fields.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)  # Always use partial=True
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Refresh from DB to get latest state
        instance.refresh_from_db()
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        """
        Handle order status updates. When order is canceled, restore inventory units.
        - Website orders (ONLINE) → AVAILABLE
        - Inventory system orders (WALK_IN) → RESERVED (salespersons can create return requests)
        """
        instance = serializer.instance
        old_status = instance.status
        
        # Get the new status from validated data
        new_status = serializer.validated_data.get('status', old_status)
        
        # If order is being canceled, restore inventory units
        if new_status == Order.StatusChoices.CANCELED and old_status != Order.StatusChoices.CANCELED:
            with transaction.atomic():
                # Restore all inventory units in this order
                for order_item in instance.order_items.all():
                    if order_item.inventory_unit:
                        unit = order_item.inventory_unit
                        # Only restore if unit is SOLD or PENDING_PAYMENT
                        if unit.sale_status in [
                            InventoryUnit.SaleStatusChoices.SOLD,
                            InventoryUnit.SaleStatusChoices.PENDING_PAYMENT
                        ]:
                            # Website orders → AVAILABLE
                            if instance.order_source == Order.OrderSourceChoices.ONLINE:
                                unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                            # Inventory system orders → RESERVED
                            elif instance.order_source == Order.OrderSourceChoices.WALK_IN:
                                unit.sale_status = InventoryUnit.SaleStatusChoices.RESERVED
                            
                            # Clear any reservation timestamps
                            unit.reserved_by = None
                            unit.reserved_until = None
                            unit.save(update_fields=['sale_status', 'reserved_by', 'reserved_until'])
        
        # Save the order with updated status
        # The serializer.update() method already set instance.status, so save() will persist it
        serializer.save()
        
        # Explicitly ensure status is saved (in case serializer.save() didn't pick it up)
        if 'status' in serializer.validated_data:
            instance.status = serializer.validated_data['status']
            instance.save(update_fields=['status'])
    
    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None, order_id=None):
        """Confirm payment for an order - transitions units from PENDING_PAYMENT to SOLD and status to PAID."""
        order = self.get_object()
        payment_method = (request.data.get('payment_method') or 'CASH').upper()
        if payment_method != 'CASH':
            return Response(
                {'error': 'Manual payment confirmation is only allowed for CASH payments.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions (salespersons can confirm their own orders, Order Managers can confirm any)
        if not request.user.is_staff:
            raise exceptions.PermissionDenied("Only staff can confirm payment.")
        
        # Check if order is already paid
        if order.status == Order.StatusChoices.PAID:
            return Response({
                'message': 'Payment already confirmed for this order.',
                'order_id': str(order.order_id),
                'order_status': order.get_status_display()
            })
        
        # Salespersons can only confirm orders from their assigned brands
        try:
            admin = Admin.objects.get(user=request.user)
            if admin.is_salesperson and not admin.is_global_admin:
                # Check if order is from salesperson's brand
                if order.brand and order.brand not in admin.brands.all():
                    raise exceptions.PermissionDenied("You can only confirm payment for orders from your assigned brands.")
        except Admin.DoesNotExist:
            pass
        
        with transaction.atomic():
            # Get all order items
            order_items = order.order_items.all()
            
            if not order_items.exists():
                return Response({'error': 'Order has no items'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Update inventory units: For accessories, decrement quantity and mark as SOLD if quantity reaches 0
            # For unique items, mark as SOLD
            from inventory.models import Product
            units_updated = []
            for order_item in order_items:
                unit = order_item.inventory_unit
                if not unit:
                    continue
                
                if unit.product_template.product_type == Product.ProductType.ACCESSORY:
                    # Accessory: consume reserved quantities first (if any), then decrement remaining
                    reserved_consumed = 0
                    try:
                        admin = Admin.objects.get(user=order.user) if order.user else None
                    except Admin.DoesNotExist:
                        admin = None
                    if admin:
                        remaining_to_consume = order_item.quantity
                        reservation_requests = ReservationRequest.objects.filter(
                            requesting_salesperson=admin,
                            status=ReservationRequest.StatusChoices.APPROVED,
                            inventory_units=unit
                        ).order_by('approved_at', 'requested_at')
                        for req in reservation_requests:
                            unit_quantities = req.inventory_unit_quantities or {}
                            qty = unit_quantities.get(str(unit.id)) or unit_quantities.get(unit.id) or 0
                            if qty <= 0:
                                continue
                            consume = min(remaining_to_consume, qty)
                            unit_quantities[str(unit.id)] = qty - consume
                            req.inventory_unit_quantities = unit_quantities
                            if all(v == 0 for v in unit_quantities.values()):
                                req.status = ReservationRequest.StatusChoices.RETURNED
                                req.expires_at = timezone.now()
                            req.save(update_fields=['inventory_unit_quantities', 'status', 'expires_at'])
                            reserved_consumed += consume
                            remaining_to_consume -= consume
                            if remaining_to_consume == 0:
                                break

                    decrement_qty = max(0, order_item.quantity - reserved_consumed)
                    if decrement_qty > 0:
                        unit.quantity = max(0, unit.quantity - decrement_qty)
                    if unit.quantity == 0:
                        unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
                    else:
                        unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                    unit.save(update_fields=['quantity', 'sale_status'])
                    units_updated.append(unit.id)
                else:
                    # Unique item (Phone/Laptop/Tablet): Mark as SOLD
                    if unit.sale_status == InventoryUnit.SaleStatusChoices.PENDING_PAYMENT:
                        unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
                        unit.save(update_fields=['sale_status'])
                        units_updated.append(unit.id)
            
            if not units_updated:
                return Response({
                    'message': 'No units with PENDING_PAYMENT status found. Payment may already be confirmed.',
                    'units_updated': 0
                })
            
            # Update order status to PAID (now visible to Order Manager)
            order.status = Order.StatusChoices.PAID
            order.save(update_fields=['status'])
            
            # Generate and send receipt automatically (email + WhatsApp)
            try:
                from inventory.services.receipt_service import ReceiptService
                receipt, email_sent, whatsapp_sent = ReceiptService.generate_and_send_receipt(order)
                logger.info(
                    "Receipt generated after cash confirmation",
                    extra={
                        'order_id': str(order.order_id),
                        'receipt_number': receipt.receipt_number,
                        'email_sent': email_sent,
                        'whatsapp_sent': whatsapp_sent,
                    },
                )
            except Exception as e:
                logger.error(
                    f"Failed to generate receipt after cash confirmation for order {order.order_id}: {e}",
                    exc_info=True,
                )
                # Don't fail payment confirmation if receipt generation fails
            
            # Clear the associated cart if it exists (cart is linked to lead, which is linked to order)
            # This ensures the customer's cart is cleared once payment is confirmed
            cart_cleared = False
            try:
                if hasattr(order, 'source_lead') and order.source_lead:
                    lead = order.source_lead
                    if hasattr(lead, 'cart') and lead.cart:
                        cart = lead.cart
                        cart.delete()
                        cart_cleared = True
                        print(f"Cart {cart.id} deleted after payment confirmed for order {order.order_id}")
            except Exception as e:
                # Log but don't fail payment confirmation if cart deletion fails
                print(f"Warning: Could not delete cart after payment confirmation: {e}")
            
            message = f'Payment confirmed. {len(units_updated)} unit(s) marked as SOLD. Order is now visible to Order Managers.'
            if cart_cleared:
                message += ' Cart has been cleared.'
            
            return Response({
                'message': message,
                'payment_method': payment_method,
                'units_updated': units_updated,
                'order_id': str(order.order_id),
                'order_status': order.get_status_display(),
                'cart_cleared': cart_cleared
            })
    
    @extend_schema(request=InitiatePaymentRequestSerializer, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny], authentication_classes=[])
    def initiate_payment(self, request, pk=None, **kwargs):
        """Initiate Pesapal payment for an order."""
        print(f"\n[PESAPAL] ========== VIEW: INITIATE PAYMENT START ==========")
        print(f"[PESAPAL] Order PK: {pk}")
        print(f"[PESAPAL] Request Method: {request.method}")
        print(f"[PESAPAL] Additional kwargs: {kwargs}")
        import json
        print(f"[PESAPAL] Request Data: {json.dumps(request.data, indent=2, default=str)}")
        print(f"[PESAPAL] User Authenticated: {request.user.is_authenticated}")
        
        try:
            from inventory.services.pesapal_payment_service import PesapalPaymentService
            
            print(f"[PESAPAL] Getting order object...")
            order = self.get_object()
            print(f"[PESAPAL] Order retrieved - ID: {order.order_id}, Status: {order.status}, Amount: {order.total_amount}")
            
            service = PesapalPaymentService()
            
            if order.status != Order.StatusChoices.PENDING:
                print(f"[PESAPAL] ========== VIEW: INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR: Order is already {order.status}")
                print(f"[PESAPAL] ==================================================\n")
                return Response(
                    {'error': f'Order is already {order.status}. Cannot initiate payment.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if order.total_amount <= 0:
                print(f"[PESAPAL] ========== VIEW: INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] ERROR: Order total amount must be greater than 0")
                print(f"[PESAPAL] ==================================================\n")
                return Response(
                    {'error': 'Order total amount must be greater than 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            callback_url = request.data.get('callback_url')
            if not callback_url:
                callback_url = getattr(settings, 'PESAPAL_CALLBACK_URL', '')
                if not callback_url:
                    print(f"[PESAPAL] ========== VIEW: INITIATE PAYMENT FAILED ==========")
                    print(f"[PESAPAL] ERROR: callback_url is required")
                    print(f"[PESAPAL] ==================================================\n")
                    return Response(
                        {'error': 'callback_url is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            cancellation_url = request.data.get('cancellation_url', callback_url)
            customer = request.data.get('customer', None)
            billing_address = request.data.get('billing_address', None)
            
            # For walk-in orders, build customer details from the order if not provided
            if not customer and order.customer:
                customer = {}
                customer_email = order.customer.email
                customer_phone = order.customer.phone or order.customer.phone_number
                if customer_email:
                    customer['email'] = customer_email
                if customer_phone:
                    customer['phone_number'] = customer_phone
                if order.customer.name:
                    name_parts = order.customer.name.split(' ', 1)
                    customer['first_name'] = name_parts[0] if len(name_parts) > 0 else ''
                    customer['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
            
            # Ensure walk-in payments have a phone number for Pesapal
            if order.order_source == Order.OrderSourceChoices.WALK_IN:
                customer_phone = None
                if customer:
                    customer_phone = customer.get('phone_number') or customer.get('phone')
                if not customer_phone:
                    return Response(
                        {'error': 'customer_phone is required to initiate walk-in payment.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if not billing_address and order.customer and order.customer.delivery_address:
                billing_address = {
                    'line_1': order.customer.delivery_address
                }
            
            print(f"[PESAPAL] Calling service.initiate_payment...")
            result = service.initiate_payment(
                order=order,
                callback_url=callback_url,
                cancellation_url=cancellation_url,
                customer=customer,
                billing_address=billing_address
            )
            
            print(f"[PESAPAL] Service result: {json.dumps(result, indent=2, default=str)}")
            
            if not result.get('success'):
                print(f"[PESAPAL] ========== VIEW: INITIATE PAYMENT FAILED ==========")
                print(f"[PESAPAL] Service returned failure")
                print(f"[PESAPAL] ==================================================\n")
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
            print(f"[PESAPAL] ========== VIEW: INITIATE PAYMENT SUCCESS ==========")
            print(f"[PESAPAL] Returning success response to client")
            print(f"[PESAPAL] Response includes redirect_url: {result.get('redirect_url', 'NOT PROVIDED')}")
            print(f"[PESAPAL] ⚠️  FRONTEND MUST REDIRECT USER TO redirect_url IMMEDIATELY")
            print(f"[PESAPAL] ===================================================\n")
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            error_msg = f"Error initiating payment for order {pk}: {str(e)}"
            print(f"[PESAPAL] ========== VIEW: INITIATE PAYMENT EXCEPTION ==========")
            print(f"[PESAPAL] ERROR: {error_msg}")
            print(f"[PESAPAL] Traceback:\n{traceback.format_exc()}")
            print(f"[PESAPAL] =====================================================\n")
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return Response(
                {
                    'error': 'Failed to initiate payment',
                    'detail': str(e) if settings.DEBUG else 'An error occurred while initiating payment. Please try again or contact support.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny], authentication_classes=[])
    def payment_status(self, request, pk=None, **kwargs):
        """Get payment status for an order."""
        # #region agent log
        import json
        import os
        import time
        log_path = '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log'
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'inventory/views.py:payment_status',
                    'message': 'payment_status called',
                    'data': {
                        'pk': str(pk) if pk else None,
                        'kwargs': dict(kwargs),
                        'request_method': request.method,
                        'lookup_field': getattr(self, 'lookup_field', None),
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except Exception as e:
            pass
        # #endregion
        print(f"\n[PESAPAL] ========== VIEW: PAYMENT STATUS START ==========")
        print(f"[PESAPAL] Order PK: {pk}")
        print(f"[PESAPAL] Additional kwargs: {kwargs}")
        print(f"[PESAPAL] Request Method: {request.method}")
        
        try:
            from inventory.services.pesapal_payment_service import PesapalPaymentService
            import json
            
            order = self.get_object()
            print(f"[PESAPAL] Order retrieved - ID: {order.order_id}")
            
            service = PesapalPaymentService()
            
            print(f"[PESAPAL] Calling service.get_payment_status...")
            result = service.get_payment_status(order)
            
            print(f"[PESAPAL] Service result: {json.dumps(result, indent=2, default=str)}")
            print(f"[PESAPAL] ========== VIEW: PAYMENT STATUS SUCCESS ==========\n")
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"[PESAPAL] ========== VIEW: PAYMENT STATUS EXCEPTION ==========")
            print(f"[PESAPAL] ERROR: {str(e)}")
            import traceback
            print(f"[PESAPAL] Traceback:\n{traceback.format_exc()}")
            print(f"[PESAPAL] ===================================================\n")
            logger.error(f"Error getting payment status: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to get payment status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderItemViewSet(viewsets.ModelViewSet):
    """
    CRUD for Order Items. Strictly Admin-only access.
    Generally used only for reporting and admin-level viewing of existing orders.
    Uses IsAdminUser.
    """
    queryset = OrderItem.objects.all().select_related('order', 'inventory_unit')
    serializer_class = OrderItemSerializer
    permission_classes = [IsAdminUser]


class DeliveryRateViewSet(viewsets.ModelViewSet):
    """Manage delivery rates (order manager only)."""
    queryset = DeliveryRate.objects.all().order_by('county', 'ward')
    serializer_class = DeliveryRateSerializer
    permission_classes = [IsOrderManager]

# --- LOOKUP TABLES VIEWSETS ---

class ColorViewSet(viewsets.ModelViewSet):
    """
    Color lookup table. Admin-only write, public read.
    Uses IsAdminOrReadOnly.
    """
    queryset = Color.objects.all()
    serializer_class = ColorSerializer
    permission_classes = [IsAdminOrReadOnly]

class UnitAcquisitionSourceViewSet(viewsets.ModelViewSet):
    """
    Acquisition Source lookup table. Admin-only write, public read.
    Uses IsAdminOrReadOnly.
    """
    queryset = UnitAcquisitionSource.objects.all()
    serializer_class = UnitAcquisitionSourceSerializer
    permission_classes = [IsAdminOrReadOnly]

class ProductAccessoryViewSet(viewsets.ModelViewSet):
    """
    Link model between products and accessories. Admin-only write, public read.
    Uses IsAdminOrReadOnly.
    Allows all product types to have accessories (including accessories having accessories).
    """
    queryset = ProductAccessory.objects.all().select_related('main_product', 'accessory')
    serializer_class = ProductAccessorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['main_product', 'accessory']
    
    def get_serializer_context(self):
        """Add request to serializer context for absolute URL building."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

# --- CUSTOM APIVIEW ENDPOINTS ---

# Use APIView or GenericAPIView for simple, non-model specific operations
class CustomerRegistrationView(generics.CreateAPIView):
    """
    Handles POST requests to /register/ to create a new User and Customer instance.
    - Uses CustomerRegistrationSerializer for validation and atomic creation.
    - Does not require authentication (AllowAny).
    - Returns the created user data and the authentication token.
    """
    serializer_class = CustomerRegistrationSerializer
    permission_classes = (permissions.AllowAny,)

    # The CreateAPIView handles the POST request logic automatically:
    # 1. Takes data from the request.
    # 2. Passes it to serializer (CustomerRegistrationSerializer).
    # 3. Calls serializer.is_valid(raise_exception=True).
    # 4. Calls serializer.save() which executes your custom .create() method.
    # 5. Returns 201 Created with the data from .to_representation().
    pass
    
# NOTE: Include your other views here (e.g., ProductListView, OrderCreateView, etc.)

class AdminTokenLoginView(ObtainAuthToken):
    """
    Custom token login view that updates last_login field.
    Use this instead of the default obtain_auth_token for admin users.
    
    Supports both username and email login (username field can contain an email).
    Only allows users with is_staff=True or is_superuser=True to login.
    """
    serializer_class = AdminAuthTokenSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        # Update last_login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Get or create token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({'token': token.key})

class CustomerLoginView(generics.GenericAPIView):
    """
    POST: Authenticates a user (customer) and returns their authentication token 
    and basic user details (email, user_id).
    - Uses CustomerLoginSerializer for credential validation and token retrieval.
    """
    serializer_class = CustomerLoginSerializer
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        # 1. Pass data to the serializer for validation (where the authentication happens)
        serializer = self.get_serializer(data=request.data)
        
        # This calls serializer.validate(), which attempts authentication and raises 
        # an exception if authentication fails.
        serializer.is_valid(raise_exception=True)
        
        # 2. If valid, return the data populated by the serializer's validate method 
        # (token, user_id, email).
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class CustomerEmailVerificationView(generics.GenericAPIView):
    """
    POST: Verifies a customer's email using uid and token.
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        uid = request.data.get('uid')
        token = request.data.get('token')

        if not uid or not token:
            return Response({'error': 'uid and token are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            customer = Customer.objects.select_related('user').get(user__id=uid)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if customer.email_verified:
            return Response({'message': 'Email is already verified.'}, status=status.HTTP_200_OK)

        if not customer.email_verification_token or str(customer.email_verification_token) != str(token):
            return Response({'error': 'Invalid verification token.'}, status=status.HTTP_400_BAD_REQUEST)

        if customer.email_verification_sent_at:
            expiry = customer.email_verification_sent_at + timedelta(hours=48)
            if timezone.now() > expiry:
                return Response({'error': 'Verification link has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        customer.email_verified = True
        customer.email_verification_token = None
        customer.save(update_fields=['email_verified', 'email_verification_token'])

        return Response({'message': 'Email verified successfully.'}, status=status.HTTP_200_OK)


class CustomerResendVerificationView(generics.GenericAPIView):
    """
    POST: Re-send verification email for a customer.
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        from inventory.services.email_verification_service import send_verification_email

        email = request.data.get('email')
        if not email:
            return Response({'error': 'email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            customer = Customer.objects.select_related('user').get(user__email__iexact=email)
        except Customer.DoesNotExist:
            # Avoid leaking which emails exist
            return Response({'message': 'If the email exists, a verification link has been sent.'}, status=status.HTTP_200_OK)

        if customer.email_verified:
            return Response({'message': 'Email is already verified.'}, status=status.HTTP_200_OK)

        customer.issue_email_verification()
        send_verification_email(customer)

        return Response({'message': 'Verification email sent.'}, status=status.HTTP_200_OK)
    
class CustomerLogoutView(generics.GenericAPIView):
    """
    POST: Logs out the user by deleting their authentication token.
    Requires authentication (IsAuthenticated) via the provided token header.
    """
    serializer_class = EmptySerializer
    # Restrict the view to only allow POST requests. This prevents the GET request 
    # (which triggers the browsable API) from demanding a serializer.
    http_method_names = ['post']
    
    # Only authenticated users can perform this action
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=EmptySerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        try:
            # TokenAuthentication attaches the Token instance to request.auth.
            if request.auth:
                request.auth.delete() # Deletes the token from the database
                return Response({"detail": "Successfully logged out. Token deleted."}, status=status.HTTP_200_OK)
            else:
                # Should not be reached if IsAuthenticated is working, but safe check.
                return Response({"detail": "Logout attempted without an active token."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Handle unexpected errors during deletion
            return Response({"detail": "An error occurred during logout."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class CustomerProfileView(generics.RetrieveUpdateAPIView):
    """
    GET: Retrieve the authenticated user's Customer profile.
    PUT/PATCH: Update the authenticated user's Customer profile.
    Uses IsCustomerOwnerOrAdmin.
    """
    # Swapping to the correct serializer for profile updates
    serializer_class = CustomerProfileUpdateSerializer 
    permission_classes = [IsCustomerOwnerOrAdmin]

    def get_object(self):
        """Returns the Customer object linked to the authenticated user."""
        try:
            # Ensure the user is authenticated before attempting to fetch the profile
            if not self.request.user.is_authenticated:
                 raise exceptions.AuthenticationFailed("Authentication credentials were not provided.")
                 
            return Customer.objects.get(user=self.request.user)
        except Customer.DoesNotExist:
            raise exceptions.NotFound("Customer profile not found for the authenticated user.")

class AdminProfileView(generics.RetrieveAPIView):
    """
    GET: Retrieve the authenticated user's Admin profile. Admin-only access.
    Creates Admin profile if it doesn't exist (for staff users without Admin profile).
    """
    serializer_class = AdminSerializer 
    permission_classes = [IsAdminUser]

    def get_object(self):
        """Returns the Admin object linked to the authenticated staff user."""
        try:
            return Admin.objects.get(user=self.request.user)
        except Admin.DoesNotExist:
            # Auto-create Admin profile for staff users
            if self.request.user.is_staff or self.request.user.is_superuser:
                admin_code = f"ADM-{self.request.user.username.upper()[:10]}"
                admin = Admin.objects.create(user=self.request.user, admin_code=admin_code)
                return admin
            else:
                raise exceptions.NotFound("Admin profile not found for the authenticated admin user.")


class OrderReceiptView(APIView):
    """
    Simple, secure receipt endpoint using custom template.
    This is a clean implementation that bypasses ViewSet routing complexity.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = EmptySerializer
    
    def perform_content_negotiation(self, request, force=False):
        """
        Override to skip DRF's content negotiation.
        This view handles format (html/pdf) directly in get(), so we don't need DRF's negotiation.
        """
        # Return None to skip content negotiation
        # DRF will use default renderers, but we handle format ourselves in get()
        return (None, None)
    
    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, order_id):
        """
        Generate and return receipt HTML/PDF.
        
        Security validations:
        1. Order must exist
        2. For unauthenticated users: Order must be PAID
        3. For authenticated users: Must be their own order (unless staff)
        """
        from inventory.models import Order, Receipt
        from inventory.services.receipt_service import ReceiptService
        from rest_framework import status
        from rest_framework.response import Response
        from django.http import HttpResponse, FileResponse
        from django.core.files.base import ContentFile
        from django.utils import timezone
        from uuid import UUID
        import os
        
        # 1. Validate and get order
        try:
            if isinstance(order_id, str):
                order_id = UUID(order_id)
            order = Order.objects.get(order_id=order_id)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid order ID format: {order_id}")
            return Response(
                {'error': 'Invalid order ID format.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error retrieving order: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve order.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # 2. Security: Check permissions
        if request.user.is_staff:
            # Staff can view any receipt
            pass
        elif request.user.is_authenticated:
            # Authenticated users can only view their own receipts
            if order.customer.user != request.user:
                return Response(
                    {'error': 'You do not have permission to view this receipt.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            # Unauthenticated users: only for PAID orders (guest checkout)
            if order.status != Order.StatusChoices.PAID:
                return Response(
                    {'error': 'Receipt is only available for paid orders.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # 3. Generate receipt
        format_type = request.query_params.get('format', 'html')
        
        try:
            if format_type == 'pdf':
                # Get or create receipt record
                receipt, created = Receipt.objects.get_or_create(order=order)
                if not receipt.receipt_number:
                    receipt.receipt_number = ReceiptService.generate_receipt_number(order)
                    receipt.save(update_fields=['receipt_number'])
                
                # Generate PDF if not exists or file is missing
                if not receipt.pdf_file or (receipt.pdf_file and not os.path.exists(receipt.pdf_file.path)):
                    pdf_bytes = ReceiptService.generate_receipt_pdf(order)
                    pdf_filename = f"receipt_{order.order_id}_{receipt.receipt_number}.pdf"
                    pdf_path = os.path.join('receipts', timezone.now().strftime('%Y/%m'), pdf_filename)
                    receipt.pdf_file.save(pdf_path, ContentFile(pdf_bytes), save=True)
                
                # Return PDF
                response = FileResponse(
                    open(receipt.pdf_file.path, 'rb'),
                    content_type='application/pdf'
                )
                response['Content-Disposition'] = f'attachment; filename="receipt_{receipt.receipt_number}.pdf"'
                return response
            else:
                # Return HTML
                html_content = ReceiptService.generate_receipt_html(order)
                return HttpResponse(html_content, content_type='text/html')
                
        except Exception as e:
            logger.error(f"Error generating receipt for order {order.order_id}: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to generate receipt. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DiscountCalculatorView(generics.GenericAPIView):
    """
    Utility endpoint to calculate a final price based on various discounts and rules.
    This is a complex business logic endpoint, requiring POST data.
    """
    serializer_class = DiscountCalculatorSerializer
    permission_classes = [permissions.AllowAny] # Usually accessible by anyone browsing

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 1. Get validated input data
        original_price = serializer.validated_data['original_price']
        
        # The DiscountCalculatorSerializer from our previous step only calculated percentage,
        # but the request likely sent 'base_price', 'discount_code', and 'customer_status'.
        # Assuming the POST request provides the fields needed for the logic below:
        base_price = original_price 
        discount_code = request.data.get('discount_code', '')
        customer_status = request.data.get('customer_status', '')

        final_price = base_price

        # --- Example Discount Logic (Placeholder) ---
        if discount_code.upper() == 'SUMMER20':
            final_price *= Decimal('0.80') # 20% off
        
        if customer_status.upper() == 'VIP':
            final_price *= Decimal('0.95') # Additional 5% off

        return Response({
            'original_price': base_price,
            'final_price': round(final_price, 2),
            'currency': 'KES',
            'details': f"Applied discount code '{discount_code or 'None'}' and status '{customer_status or 'None'}'."
        })


# -------------------------------------------------------------------------
# REQUEST MANAGEMENT VIEWSETS
# -------------------------------------------------------------------------
# -------------------------------------------------------------------------
# REQUEST MANAGEMENT VIEWSETS
# -------------------------------------------------------------------------

class ReservationRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reservation requests.
    - Salespersons can create requests and view their own
    - Inventory Managers can approve/reject and view all pending requests
    """
    serializer_class = ReservationRequestSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        if not user.is_authenticated:
            return ReservationRequest.objects.none()
        
        # Superuser sees all
        if user.is_superuser:
            return ReservationRequest.objects.all().select_related(
                'requesting_salesperson__user', 'inventory_unit__product_template', 'approved_by__user'
            ).prefetch_related('inventory_units__product_template')
        
        try:
            admin = Admin.objects.get(user=user)
        except Admin.DoesNotExist:
            return ReservationRequest.objects.none()
        
        # Inventory Manager sees all requests (pending, approved, rejected, expired)
        # This allows them to see the status changes after approval and manage all requests
        if admin.is_inventory_manager:
            return ReservationRequest.objects.all().select_related(
                'requesting_salesperson__user', 'inventory_unit__product_template', 'approved_by__user'
            ).prefetch_related('inventory_units__product_template')
        
        # Salesperson sees only their own requests
        if admin.is_salesperson:
            return ReservationRequest.objects.filter(
                requesting_salesperson=admin
            ).select_related('requesting_salesperson__user', 'inventory_unit__product_template', 'approved_by__user').prefetch_related('inventory_units__product_template')
        
        return ReservationRequest.objects.none()
    
    def get_permissions(self):
        """Apply role-based permissions."""
        if self.action == 'create':
            return [CanReserveUnits()]
        elif self.action in ['update', 'partial_update']:
            # Allow salespersons to edit their own PENDING requests
            # Allow inventory managers to approve/reject
            # Get object directly from DB to avoid recursion (don't use get_object() which triggers permission checks)
            request_obj = None
            pk = self.kwargs.get('pk')
            if pk:
                try:
                    request_obj = ReservationRequest.objects.get(pk=pk)
                except ReservationRequest.DoesNotExist:
                    pass
            
            if request_obj and request_obj.status == ReservationRequest.StatusChoices.PENDING:
                try:
                    admin = Admin.objects.get(user=self.request.user)
                    # Salesperson can edit their own pending requests
                    if admin.is_salesperson and request_obj.requesting_salesperson == admin:
                        return [IsAdminUser()]  # Allow edit
                except Admin.DoesNotExist:
                    pass
            # For approval/rejection, require CanApproveRequests
            return [CanApproveRequests()]
        return [IsAdminUser()]

    def create(self, request, *args, **kwargs):
        """Override create to provide clearer validation errors."""
        from rest_framework import serializers as drf_serializers

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except drf_serializers.ValidationError as e:
            logger.error(f"Reservation request creation validation error: {e.detail}")
            error_message = "Validation failed"
            if isinstance(e.detail, dict):
                error_parts = []
                for field, messages in e.detail.items():
                    if isinstance(messages, list):
                        error_parts.append(f"{field}: {', '.join(str(m) for m in messages)}")
                    else:
                        error_parts.append(f"{field}: {messages}")
                if error_parts:
                    error_message = "; ".join(error_parts)
            elif isinstance(e.detail, list):
                error_message = "; ".join(str(m) for m in e.detail)
            else:
                error_message = str(e.detail)

            return Response(
                {"error": error_message, "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Reservation request creation error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to create reservation request: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
    def update(self, request, *args, **kwargs):
        """Override update to ensure we return the refreshed object after approval/rejection."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Call perform_update which handles the actual approval/rejection logic
        # Pass the instance to ensure we're working with the same object
        self.perform_update(serializer, instance=instance)
        
        # Refresh the instance from database to ensure we have the latest state
        instance.refresh_from_db()
        
        # Return the updated object
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        
        # Re-serialize the refreshed instance
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def perform_update(self, serializer, instance=None):
        """Handle approval/rejection of reservation requests or editing PENDING requests."""
        try:
            # Use the passed instance if provided, otherwise get it
            request_obj = instance if instance is not None else self.get_object()
            new_status = serializer.validated_data.get('status')
            logger.info(
                "ReservationRequestViewSet.perform_update called",
                extra={
                    "request_id": request_obj.id,
                    "current_status": request_obj.status,
                    "incoming_validated_data": serializer.validated_data,
                    "new_status": new_status,
                    "request_user": getattr(self.request.user, "username", None),
                },
            )
            
            # If status is not being changed and request is PENDING, allow editing units/notes
            if not new_status or new_status == request_obj.status:
                if request_obj.status == ReservationRequest.StatusChoices.PENDING:
                    # This is an edit operation (units or notes)
                    try:
                        serializer.save()
                        logger.info(f"Successfully saved edit to reservation request {request_obj.id}")
                        return
                    except Exception as e:
                        import traceback
                        logger.error(f"Error saving edit to reservation request {request_obj.id}: {str(e)}\n{traceback.format_exc()}")
                        raise
            
            # Status change operation (approval/rejection)
            if new_status == ReservationRequest.StatusChoices.APPROVED:
                # Get approving admin
                try:
                    approving_admin = Admin.objects.get(user=self.request.user)
                    if not approving_admin.is_inventory_manager:
                        logger.warning(f"User {self.request.user.username} attempted to approve but is not an inventory manager")
                        raise exceptions.PermissionDenied("Only Inventory Managers can approve reservation requests.")
                except Admin.DoesNotExist:
                    logger.error(f"Admin profile not found for user {self.request.user.username}")
                    raise exceptions.PermissionDenied("Admin profile required.")
                
                approved_at = timezone.now()
                expires_at = approved_at + timedelta(days=2)

                # Expire any other active approvals for units in this request (regardless of salesperson)
                units_to_reserve = request_obj.inventory_units.all()
                if not units_to_reserve.exists() and request_obj.inventory_unit:
                    units_to_reserve = [request_obj.inventory_unit]
                
                unit_ids = [unit.id for unit in units_to_reserve]
                
                # Find other approved requests that include any of these units
                other_active_approvals = ReservationRequest.objects.filter(
                    inventory_units__id__in=unit_ids,
                    status=ReservationRequest.StatusChoices.APPROVED,
                ).exclude(pk=request_obj.pk).distinct()
                
                # Also check old single unit field
                if request_obj.inventory_unit:
                    other_active_approvals_old = ReservationRequest.objects.filter(
                        inventory_unit=request_obj.inventory_unit,
                        status=ReservationRequest.StatusChoices.APPROVED,
                    ).exclude(pk=request_obj.pk).distinct()
                    # Combine both querysets - both must have distinct() before combining
                    other_active_approvals = (other_active_approvals | other_active_approvals_old).distinct()

                if other_active_approvals.exists():
                    logger.info(
                        "Expiring other approved reservations for unit before approval",
                        extra={
                            "current_request_id": request_obj.id,
                            "unit_id": request_obj.inventory_unit_id,
                            "other_request_ids": list(other_active_approvals.values_list("id", flat=True)),
                        },
                    )
                    other_active_approvals.update(
                        status=ReservationRequest.StatusChoices.EXPIRED,
                        expires_at=timezone.now(),
                    )

                    # Release unit associations from previously approved requests
                    for expired_req in other_active_approvals:
                        # Handle new ManyToMany field
                        expired_units = expired_req.inventory_units.all()
                        if not expired_units.exists() and expired_req.inventory_unit:
                            expired_units = [expired_req.inventory_unit]
                        
                        for unit in expired_units:
                            if unit.reserved_by == expired_req.requesting_salesperson:
                                unit.reserved_by = None
                                unit.reserved_until = None
                                unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                                unit.save(update_fields=["reserved_by", "reserved_until", "sale_status"])
                
                # Save the approval - explicitly set all fields on the instance
                # This ensures the status is actually saved to the database
                request_obj.approved_by = approving_admin
                request_obj.approved_at = approved_at
                request_obj.expires_at = expires_at
                request_obj.status = new_status
                
                # Save the instance directly to ensure status is persisted
                request_obj.save(update_fields=['approved_by', 'approved_at', 'expires_at', 'status'])
                
                # Also update the serializer's instance to keep it in sync
                serializer.instance = request_obj
                
                # Log the saved status to verify it was saved correctly
                logger.info(
                    f"Reservation request {request_obj.id} approved. Status after save: {request_obj.status}, "
                    f"Approved by: {approving_admin.user.username}, Approved at: {request_obj.approved_at}"
                )
                
                # Refresh the object from database to ensure we have the latest state
                request_obj.refresh_from_db()
                
                # Double-check the status was saved
                if request_obj.status != ReservationRequest.StatusChoices.APPROVED:
                    logger.error(
                        f"CRITICAL: Reservation request {request_obj.id} status is {request_obj.status} "
                        f"after save, expected {ReservationRequest.StatusChoices.APPROVED}"
                    )
                
                # Update all inventory units in the request
                units = request_obj.inventory_units.all()
                if not units.exists() and request_obj.inventory_unit:
                    # Fallback to old single unit during migration
                    units = [request_obj.inventory_unit]
                
                # Log if no units found
                if not units.exists() and not request_obj.inventory_unit:
                    logger.warning(
                        f"Reservation request {request_obj.id} approved but has no inventory units associated. "
                        f"inventory_units.count()={request_obj.inventory_units.count()}, "
                        f"inventory_unit={request_obj.inventory_unit}"
                    )
                
                unit_names = []
                updated_units = []
                updated_quantities = {}
                unit_quantities = request_obj.inventory_unit_quantities or {}
                for unit in units:
                    requested_qty = unit_quantities.get(str(unit.id)) or unit_quantities.get(unit.id) or 1
                    if requested_qty > unit.quantity:
                        requested_qty = unit.quantity

                    if unit.product_template.product_type == Product.ProductType.ACCESSORY:
                        # Accessories: reserve only the requested quantity.
                        # Decrement available quantity and keep the same inventory unit.
                        unit.quantity = max(0, unit.quantity - requested_qty)
                        if unit.quantity == 0:
                            unit.sale_status = InventoryUnit.SaleStatusChoices.RESERVED
                            unit.reserved_by = request_obj.requesting_salesperson
                            unit.reserved_until = timezone.now() + timedelta(days=2)
                        else:
                            unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                            unit.reserved_by = None
                            unit.reserved_until = None
                        unit.save(update_fields=['quantity', 'sale_status', 'reserved_by', 'reserved_until'])
                        updated_units.append(unit)
                        updated_quantities[unit.id] = requested_qty
                        unit_names.append(unit.product_template.product_name)
                    else:
                        unit.sale_status = InventoryUnit.SaleStatusChoices.RESERVED
                        unit.reserved_by = request_obj.requesting_salesperson
                        unit.reserved_until = timezone.now() + timedelta(days=2)
                        unit.save()
                        updated_units.append(unit)
                        updated_quantities[unit.id] = 1
                        unit_names.append(unit.product_template.product_name)

                if updated_units:
                    request_obj.inventory_units.set(updated_units)
                    request_obj.inventory_unit_quantities = updated_quantities
                    request_obj.save(update_fields=['inventory_unit_quantities'])
                
                # Create notification message
                if len(unit_names) == 1:
                    message = f"Your reservation request for {unit_names[0]} has been approved."
                else:
                    message = f"Your reservation request for {len(unit_names)} units has been approved."
                
                # Create notifications - wrap in try-except to prevent notification errors from breaking approval
                try:
                    Notification.objects.create(
                        recipient=request_obj.requesting_salesperson.user,
                        notification_type=Notification.NotificationType.RESERVATION_APPROVED,
                        title="Reservation Approved",
                        message=message,
                        content_type=ContentType.objects.get_for_model(ReservationRequest),
                        object_id=request_obj.id
                    )
                    logger.info(f"Created approval notification for salesperson {request_obj.requesting_salesperson.user.username} for request {request_obj.id}")
                except Exception as e:
                    logger.error(f"Failed to create approval notification for salesperson {request_obj.requesting_salesperson.user.username} for request {request_obj.id}: {str(e)}")
                    # Don't raise - notification failure shouldn't break approval
                
                # Notify inventory managers and superusers
                approval_message = f"Reservation for {len(unit_names)} unit(s) has been approved." if len(unit_names) > 1 else f"Reservation for {unit_names[0]} has been approved."
                
                try:
                    managers = Admin.objects.filter(roles__name=AdminRole.RoleChoices.INVENTORY_MANAGER).select_related('user')
                    for manager in managers:
                        try:
                            Notification.objects.create(
                                recipient=manager.user,
                                notification_type=Notification.NotificationType.REQUEST_PENDING_APPROVAL,
                                title="New Reservation Approved",
                                message=approval_message,
                                content_type=ContentType.objects.get_for_model(ReservationRequest),
                                object_id=request_obj.id
                            )
                        except Exception as e:
                            logger.error(f"Failed to create notification for manager {manager.user.username}: {str(e)}")
                    
                    superusers = User.objects.filter(is_superuser=True)
                    for superuser in superusers:
                        try:
                            Notification.objects.create(
                                recipient=superuser,
                                notification_type=Notification.NotificationType.RESERVATION_APPROVED,
                                title="Reservation Approved",
                                message=approval_message,
                                content_type=ContentType.objects.get_for_model(ReservationRequest),
                                object_id=request_obj.id
                            )
                        except Exception as e:
                            logger.error(f"Failed to create notification for superuser {superuser.username}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error creating manager/superuser notifications for request {request_obj.id}: {str(e)}")
                    # Don't raise - notification failure shouldn't break approval
            
            elif new_status == ReservationRequest.StatusChoices.REJECTED:
                try:
                    approving_admin = Admin.objects.get(user=self.request.user)
                    if not approving_admin.is_inventory_manager:
                        logger.warning(f"User {self.request.user.username} attempted to reject but is not an inventory manager")
                        raise exceptions.PermissionDenied("Only Inventory Managers can reject reservation requests.")
                except Admin.DoesNotExist:
                    logger.error(f"Admin profile not found for user {self.request.user.username}")
                    raise exceptions.PermissionDenied("Admin profile required.")
                
                # Save the rejection - explicitly set all fields on the instance
                request_obj.approved_by = approving_admin
                request_obj.approved_at = timezone.now()
                request_obj.status = new_status
                
                # Save the instance directly to ensure status is persisted
                request_obj.save(update_fields=['approved_by', 'approved_at', 'status'])
                
                # Also update the serializer's instance to keep it in sync
                serializer.instance = request_obj
                
                # Log the saved status
                logger.info(
                    f"Reservation request {request_obj.id} rejected. Status after save: {request_obj.status}, "
                    f"Rejected by: {approving_admin.user.username}"
                )
                
                # Refresh to verify
                request_obj.refresh_from_db()
                
                # Get unit names for notification
                units = request_obj.inventory_units.all()
                if not units.exists() and request_obj.inventory_unit:
                    units = [request_obj.inventory_unit]
                
                unit_names = [unit.product_template.product_name for unit in units]
                rejection_message = f"Your reservation request for {len(unit_names)} unit(s) has been rejected." if len(unit_names) > 1 else f"Your reservation request for {unit_names[0]} has been rejected."
                
                # Create notification - wrap in try-except to prevent notification errors from breaking rejection
                try:
                    Notification.objects.create(
                        recipient=request_obj.requesting_salesperson.user,
                        notification_type=Notification.NotificationType.RESERVATION_REJECTED,
                        title="Reservation Rejected",
                        message=rejection_message,
                        content_type=ContentType.objects.get_for_model(ReservationRequest),
                        object_id=request_obj.id
                    )
                    logger.info(f"Created rejection notification for salesperson {request_obj.requesting_salesperson.user.username} for request {request_obj.id}")
                except Exception as e:
                    logger.error(f"Failed to create rejection notification for salesperson {request_obj.requesting_salesperson.user.username} for request {request_obj.id}: {str(e)}")
                    # Don't raise - notification failure shouldn't break rejection
            else:
                serializer.save()
        
        except Exception as e:
            import traceback
            error_msg = f"Error updating reservation request {request_obj.id if 'request_obj' in locals() else 'unknown'}: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            # Re-raise with more context
            if isinstance(e, (exceptions.PermissionDenied, exceptions.ValidationError)):
                raise
            raise exceptions.ValidationError(f"Failed to update reservation request: {str(e)}")


class ReturnRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing return requests (bulk returns of reserved units).
    - Salespersons can create return requests for their reserved units
    - Inventory Managers can approve/reject return requests
    """
    serializer_class = ReturnRequestSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        if not user.is_authenticated:
            return ReturnRequest.objects.none()
        
        queryset = ReturnRequest.objects.none()
        
        if user.is_superuser:
            queryset = ReturnRequest.objects.all()
        else:
            try:
                admin = Admin.objects.get(user=user)
            except Admin.DoesNotExist:
                return ReturnRequest.objects.none()
            
            if admin.is_inventory_manager:
                queryset = ReturnRequest.objects.all()
            elif admin.is_salesperson:
                queryset = ReturnRequest.objects.filter(
                    requesting_salesperson=admin
                )
            else:
                return ReturnRequest.objects.none()
        
        # Optional status filter (?status=PE/AP/RE)
        status_param = self.request.query_params.get('status')
        if status_param and status_param in dict(ReturnRequest.StatusChoices.choices):
            queryset = queryset.filter(status=status_param)
        
        return queryset.select_related(
            'requesting_salesperson__user', 'approved_by__user'
        ).prefetch_related('inventory_units__product_template')
    
    def get_permissions(self):
        """Apply role-based permissions."""
        if self.action == 'create':
            return [IsSalesperson()]
        elif self.action in ['update', 'partial_update']:
            return [CanApproveRequests()]
        return [IsAdminUser()]
    
    def create(self, request, *args, **kwargs):
        """Override create to provide better error handling."""
        from rest_framework import serializers as drf_serializers
        
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except drf_serializers.ValidationError as e:
            # Return validation errors in a clear format
            logger.error(f"Return request creation validation error: {e.detail}")
            error_message = "Validation failed"
            if isinstance(e.detail, dict):
                # Format field-specific errors
                error_parts = []
                for field, messages in e.detail.items():
                    if isinstance(messages, list):
                        error_parts.append(f"{field}: {', '.join(str(m) for m in messages)}")
                    else:
                        error_parts.append(f"{field}: {messages}")
                if error_parts:
                    error_message = "; ".join(error_parts)
            elif isinstance(e.detail, list):
                error_message = "; ".join(str(m) for m in e.detail)
            else:
                error_message = str(e.detail)
            
            return Response(
                {"error": error_message, "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Catch any other exceptions and return a proper error message
            logger.error(f"Return request creation error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to create return request: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
    def perform_update(self, serializer):
        """Handle approval/rejection of return requests."""
        request_obj = self.get_object()
        new_status = serializer.validated_data.get('status')
        
        if new_status == ReturnRequest.StatusChoices.APPROVED:
            try:
                approving_admin = Admin.objects.get(user=self.request.user)
            except Admin.DoesNotExist:
                raise exceptions.PermissionDenied("Admin profile required.")
            
            serializer.save(
                approved_by=approving_admin,
                approved_at=timezone.now(),
                status=new_status
            )
            
            # Update all inventory units based on current status
            # Handle both salesperson returns (RESERVED → AVAILABLE) and buyback approvals (RETURNED → AVAILABLE)
            units = request_obj.inventory_units.all()
            for unit in units:
                if unit.product_template.product_type == Product.ProductType.ACCESSORY:
                    # Restore reserved quantities for accessories based on approved reservation requests
                    reservation_requests = ReservationRequest.objects.filter(
                        requesting_salesperson=request_obj.requesting_salesperson,
                        status=ReservationRequest.StatusChoices.APPROVED,
                        inventory_units=unit
                    )
                    restore_qty = 0
                    for req in reservation_requests:
                        unit_quantities = req.inventory_unit_quantities or {}
                        qty = unit_quantities.get(str(unit.id)) or unit_quantities.get(unit.id) or 0
                        restore_qty += qty
                    if restore_qty > 0:
                        unit.quantity += restore_qty
                    unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                    unit.reserved_by = None
                    unit.reserved_until = None
                    unit.save(update_fields=['quantity', 'sale_status', 'reserved_by', 'reserved_until'])
                else:
                    if unit.sale_status == InventoryUnit.SaleStatusChoices.RESERVED:
                        # Salesperson return: clear reservation and make available
                        unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                        unit.reserved_by = None
                        unit.reserved_until = None
                    elif unit.sale_status == InventoryUnit.SaleStatusChoices.RETURNED:
                        # Buyback approval: just change status to available
                        unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                    unit.save()

            # Mark any related approved reservation requests as returned
            ReservationRequest.objects.filter(
                requesting_salesperson=request_obj.requesting_salesperson,
                status=ReservationRequest.StatusChoices.APPROVED
            ).filter(
                Q(inventory_units__in=units) | Q(inventory_unit__in=units)
            ).update(
                status=ReservationRequest.StatusChoices.RETURNED,
                expires_at=timezone.now()
            )
            
            # Create notifications (salesperson returns only; buybacks have no salesperson)
            if request_obj.requesting_salesperson and request_obj.requesting_salesperson.user:
                Notification.objects.create(
                    recipient=request_obj.requesting_salesperson.user,
                    notification_type=Notification.NotificationType.RETURN_APPROVED,
                    title="Return Approved",
                    message=f"Your return request for {units.count()} unit(s) has been approved. Units are now available.",
                    content_type=ContentType.objects.get_for_model(ReturnRequest),
                    object_id=request_obj.id
                )
            
            # Notify inventory managers and superusers
            managers = Admin.objects.filter(roles__name=AdminRole.RoleChoices.INVENTORY_MANAGER).select_related('user')
            for manager in managers:
                Notification.objects.create(
                    recipient=manager.user,
                    notification_type=Notification.NotificationType.RETURN_APPROVED,
                    title="Return Approved",
                    message=f"Return request for {units.count()} unit(s) has been approved.",
                    content_type=ContentType.objects.get_for_model(ReturnRequest),
                    object_id=request_obj.id
                )
            
            superusers = User.objects.filter(is_superuser=True)
            for superuser in superusers:
                Notification.objects.create(
                    recipient=superuser,
                    notification_type=Notification.NotificationType.RETURN_APPROVED,
                    title="Return Approved",
                    message=f"Return request for {units.count()} unit(s) has been approved.",
                    content_type=ContentType.objects.get_for_model(ReturnRequest),
                    object_id=request_obj.id
                )
        
        elif new_status == ReturnRequest.StatusChoices.REJECTED:
            try:
                approving_admin = Admin.objects.get(user=self.request.user)
            except Admin.DoesNotExist:
                raise exceptions.PermissionDenied("Admin profile required.")
            
            serializer.save(
                approved_by=approving_admin,
                approved_at=timezone.now(),
                status=new_status
            )
            
            # Only notify salesperson if this is not a buyback (buybacks have no salesperson)
            if request_obj.requesting_salesperson:
                Notification.objects.create(
                    recipient=request_obj.requesting_salesperson.user,
                    notification_type=Notification.NotificationType.RETURN_REJECTED,
                    title="Return Rejected",
                    message=f"Your return request for {request_obj.inventory_units.count()} unit(s) has been rejected.",
                    content_type=ContentType.objects.get_for_model(ReturnRequest),
                    object_id=request_obj.id
                )
        else:
            serializer.save()
    
    @action(detail=False, methods=['post'], permission_classes=[CanApproveRequests])
    def bulk_approve(self, request):
        """Bulk approve multiple return requests."""
        request_ids = request.data.get('request_ids', [])
        if not request_ids:
            return Response({'error': 'request_ids required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            approving_admin = Admin.objects.get(user=request.user)
        except Admin.DoesNotExist:
            return Response({'error': 'Admin profile required'}, status=status.HTTP_403_FORBIDDEN)
        
        approved_count = 0
        with transaction.atomic():
            requests = ReturnRequest.objects.filter(
                id__in=request_ids,
                status=ReturnRequest.StatusChoices.PENDING
            )
            
            for req in requests:
                req.status = ReturnRequest.StatusChoices.APPROVED
                req.approved_by = approving_admin
                req.approved_at = timezone.now()
                req.save()
                
                # Update units
                for unit in req.inventory_units.all():
                    unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                    unit.reserved_by = None
                    unit.reserved_until = None
                    unit.save()
                
                approved_count += 1
        
        return Response({'message': f'{approved_count} return requests approved'}, status=status.HTTP_200_OK)


class UnitTransferViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing unit transfers between salespersons.
    - Salespersons can request transfers
    - Inventory Managers can approve/reject transfers
    """
    serializer_class = UnitTransferSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        if not user.is_authenticated:
            return UnitTransfer.objects.none()
        
        if user.is_superuser:
            return UnitTransfer.objects.all().select_related(
                'inventory_unit__product_template', 'from_salesperson__user',
                'to_salesperson__user', 'approved_by__user'
            )
        
        try:
            admin = Admin.objects.get(user=user)
        except Admin.DoesNotExist:
            return UnitTransfer.objects.none()
        
        if admin.is_inventory_manager:
            return UnitTransfer.objects.filter(
                status=UnitTransfer.StatusChoices.PENDING
            ).select_related('inventory_unit__product_template', 'from_salesperson__user', 'to_salesperson__user', 'approved_by__user')
        
        if admin.is_salesperson:
            return UnitTransfer.objects.filter(
                Q(from_salesperson=admin) | Q(to_salesperson=admin)
            ).select_related('inventory_unit__product_template', 'from_salesperson__user', 'to_salesperson__user', 'approved_by__user')
        
        return UnitTransfer.objects.none()
    
    def get_permissions(self):
        """Apply role-based permissions."""
        if self.action == 'create':
            return [IsSalesperson()]
        elif self.action in ['update', 'partial_update']:
            return [CanApproveRequests()]
        return [IsAdminUser()]
    
    def perform_create(self, serializer):
        """Handle creation of transfer requests and notify Inventory Managers."""
        transfer_obj = serializer.save()
        
        # Notify all Inventory Managers about the new transfer request
        managers = Admin.objects.filter(roles__name=AdminRole.RoleChoices.INVENTORY_MANAGER).select_related('user')
        unit = transfer_obj.inventory_unit
        
        for manager in managers:
            Notification.objects.create(
                recipient=manager.user,
                notification_type=Notification.NotificationType.REQUEST_PENDING_APPROVAL,
                title="New Unit Transfer Request",
                message=f"Unit {unit.product_template.product_name} (#{unit.serial_number or unit.id}) transfer requested from {transfer_obj.from_salesperson.user.username} to {transfer_obj.to_salesperson.user.username}. Review and approve if needed.",
                content_type=ContentType.objects.get_for_model(UnitTransfer),
                object_id=transfer_obj.id
            )
        
        # Also notify superusers
        superusers = User.objects.filter(is_superuser=True)
        for superuser in superusers:
            Notification.objects.create(
                recipient=superuser,
                notification_type=Notification.NotificationType.REQUEST_PENDING_APPROVAL,
                title="New Unit Transfer Request",
                message=f"Unit {unit.product_template.product_name} (#{unit.serial_number or unit.id}) transfer requested from {transfer_obj.from_salesperson.user.username} to {transfer_obj.to_salesperson.user.username}.",
                content_type=ContentType.objects.get_for_model(UnitTransfer),
                object_id=transfer_obj.id
            )
    
    def perform_update(self, serializer):
        """Handle approval/rejection of transfer requests."""
        transfer_obj = self.get_object()
        new_status = serializer.validated_data.get('status')
        
        if new_status == UnitTransfer.StatusChoices.APPROVED:
            try:
                approving_admin = Admin.objects.get(user=self.request.user)
            except Admin.DoesNotExist:
                raise exceptions.PermissionDenied("Admin profile required.")
            
            serializer.save(
                approved_by=approving_admin,
                approved_at=timezone.now(),
                status=new_status
            )
            
            # Update inventory unit: change reserved_by
            unit = transfer_obj.inventory_unit
            unit.reserved_by = transfer_obj.to_salesperson
            unit.save()
            
            # Create notifications
            Notification.objects.create(
                recipient=transfer_obj.from_salesperson.user,
                notification_type=Notification.NotificationType.TRANSFER_APPROVED,
                title="Transfer Approved",
                message=f"Unit {unit.product_template.product_name} has been transferred to {transfer_obj.to_salesperson.user.username}.",
                content_type=ContentType.objects.get_for_model(UnitTransfer),
                object_id=transfer_obj.id
            )
            
            Notification.objects.create(
                recipient=transfer_obj.to_salesperson.user,
                notification_type=Notification.NotificationType.TRANSFER_APPROVED,
                title="Unit Transferred",
                message=f"Unit {unit.product_template.product_name} has been transferred to you from {transfer_obj.from_salesperson.user.username}.",
                content_type=ContentType.objects.get_for_model(UnitTransfer),
                object_id=transfer_obj.id
            )
            
            # Notify Inventory Managers about completed transfer
            managers = Admin.objects.filter(roles__name=AdminRole.RoleChoices.INVENTORY_MANAGER).select_related('user')
            for manager in managers:
                Notification.objects.create(
                    recipient=manager.user,
                    notification_type=Notification.NotificationType.TRANSFER_APPROVED,
                    title="Unit Transfer Completed",
                    message=f"Unit {unit.product_template.product_name} (#{unit.serial_number or unit.id}) transferred from {transfer_obj.from_salesperson.user.username} to {transfer_obj.to_salesperson.user.username}. This may affect return requests.",
                content_type=ContentType.objects.get_for_model(UnitTransfer),
                object_id=transfer_obj.id
            )
            
            # Notify superusers
            superusers = User.objects.filter(is_superuser=True)
            for superuser in superusers:
                Notification.objects.create(
                    recipient=superuser,
                    notification_type=Notification.NotificationType.UNIT_RESERVED,
                    title="Unit Transfer Completed",
                    message=f"Unit {unit.product_template.product_name} transferred from {transfer_obj.from_salesperson.user.username} to {transfer_obj.to_salesperson.user.username}.",
                    content_type=ContentType.objects.get_for_model(UnitTransfer),
                    object_id=transfer_obj.id
                )
        
        elif new_status == UnitTransfer.StatusChoices.REJECTED:
            try:
                approving_admin = Admin.objects.get(user=self.request.user)
            except Admin.DoesNotExist:
                raise exceptions.PermissionDenied("Admin profile required.")
            
            serializer.save(
                approved_by=approving_admin,
                approved_at=timezone.now(),
                status=new_status
            )
            
            Notification.objects.create(
                recipient=transfer_obj.from_salesperson.user,
                notification_type=Notification.NotificationType.TRANSFER_REJECTED,
                title="Transfer Rejected",
                message=f"Your transfer request for {transfer_obj.inventory_unit.product_template.product_name} has been rejected.",
                content_type=ContentType.objects.get_for_model(UnitTransfer),
                object_id=transfer_obj.id
            )
        else:
            serializer.save()


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for notifications (read-only, with mark-as-read action).
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Return notifications for current user."""
        user = self.request.user
        if not user.is_authenticated:
            return Notification.objects.none()
        
        return Notification.objects.filter(recipient=user).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications."""
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)


class ReportsViewSet(viewsets.ViewSet):
    """
    ViewSet for inventory reports (Inventory Manager only).
    Provides various analytical reports for decision-making.
    """
    permission_classes = [CanApproveRequests]  # Inventory Manager or Superuser
    serializer_class = EmptySerializer
    
    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'])
    def inventory_value(self, request):
        """Get inventory value report."""
        from .reports import get_inventory_value_report
        report_data = get_inventory_value_report()
        return Response(report_data, status=status.HTTP_200_OK)
    
    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'])
    def stock_movement(self, request):
        """Get stock movement report."""
        from .reports import get_stock_movement_report
        days = int(request.query_params.get('days', 30))
        report_data = get_stock_movement_report(days=days)
        return Response(report_data, status=status.HTTP_200_OK)
    
    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'])
    def product_performance(self, request):
        """Get product performance report."""
        from .reports import get_product_performance
        report_data = get_product_performance()
        return Response(report_data, status=status.HTTP_200_OK)
    
    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'])
    def aging_inventory(self, request):
        """Get aging inventory report."""
        from .reports import get_aging_inventory
        days_threshold = int(request.query_params.get('days', 30))
        report_data = get_aging_inventory(days_threshold=days_threshold)
        return Response(report_data, status=status.HTTP_200_OK)
    
    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'])
    def salesperson_performance(self, request):
        """Get salesperson performance report."""
        from .reports import get_salesperson_performance
        days = int(request.query_params.get('days', 30))
        report_data = get_salesperson_performance(days=days)
        return Response(report_data, status=status.HTTP_200_OK)
    
    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'])
    def request_management(self, request):
        """Get request management statistics."""
        from .reports import get_request_management_stats
        days = int(request.query_params.get('days', 30))
        report_data = get_request_management_stats(days=days)
        return Response(report_data, status=status.HTTP_200_OK)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for audit logs (Inventory Manager and Superuser only).
    Read-only access to view system audit trail.
    """
    serializer_class = AuditLogSerializer
    permission_classes = [CanApproveRequests]  # Inventory Manager or Superuser
    
    def get_queryset(self):
        """Return audit logs with optional filtering."""
        queryset = AuditLog.objects.all().select_related('user')
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by model
        model_name = self.request.query_params.get('model_name')
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        return queryset


class StockAlertsViewSet(viewsets.ViewSet):
    """
    ViewSet for stock alerts (Inventory Manager only).
    Returns alerts for low stock, expiring reservations, and status issues.
    """
    permission_classes = [CanApproveRequests]  # Inventory Manager or Superuser
    serializer_class = EmptySerializer
    
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def list(self, request):
        """Get all stock alerts."""
        alerts = []
        
        # 1. Low Stock Alerts - Products with fewer than min_stock_threshold units available
        # For accessories, sum quantities; for phones/laptops/tablets, count units
        low_stock_products = Product.objects.annotate(
            available_count=Case(
                When(product_type=Product.ProductType.ACCESSORY, 
                     then=Coalesce(Sum('inventory_units__quantity', filter=Q(inventory_units__sale_status='AV')), Value(0))),
                default=Count('inventory_units', filter=Q(inventory_units__sale_status='AV')),
                output_field=IntegerField()
            )
        ).filter(
            Q(min_stock_threshold__isnull=False) & Q(available_count__lt=F('min_stock_threshold'))
        )
        
        # #region agent log
        try:
            import json, time
            accessory_product = low_stock_products.filter(product_type=Product.ProductType.ACCESSORY).first()
            if accessory_product:
                accessory_units = InventoryUnit.objects.filter(
                    product_template=accessory_product,
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE
                )
                sum_qty = accessory_units.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
                count_units = accessory_units.count()
                import os
                os.makedirs("/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor", exist_ok=True)
                with open("/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "pre-fix",
                        "hypothesisId": "H4",
                        "location": "inventory/views.py:StockAlertsViewSet.list",
                        "message": "Low stock accessory count vs quantity",
                        "data": {
                            "product_id": accessory_product.id,
                            "count_units": count_units,
                            "sum_quantity": sum_qty,
                            "available_count": accessory_product.available_count
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
        except Exception:
            pass
        # #endregion
        
        for product in low_stock_products:
            alerts.append({
                'id': f'low-stock-{product.id}',
                'type': 'low_stock',
                'severity': 'high' if product.available_count == 0 else 'medium',
                'title': f'Low Stock: {product.product_name}',
                'message': f'Only {product.available_count} unit(s) available. Minimum threshold is {product.min_stock_threshold}.',
                'product_id': product.id,
                'product_name': product.product_name,
                'current_stock': product.available_count,
                'min_threshold': product.min_stock_threshold,
                'action': 'restock',
            })
        
        # 2. Expiring Reservation Alerts - Reserved units expiring within 24 hours
        expiring_soon = timezone.now() + timedelta(hours=24)
        expiring_units = InventoryUnit.objects.filter(
            sale_status='RS',
            reserved_until__isnull=False,
            reserved_until__lte=expiring_soon,
            reserved_until__gt=timezone.now()
        ).select_related('product_template', 'reserved_by')
        
        for unit in expiring_units:
            hours_left = (unit.reserved_until - timezone.now()).total_seconds() / 3600
            alerts.append({
                'id': f'expiring-{unit.id}',
                'type': 'expiring_reservation',
                'severity': 'medium' if hours_left > 6 else 'high',
                'title': f'Reservation Expiring: {unit.product_template_name or "Unit"}',
                'message': f'Unit #{unit.id} reserved by {unit.reserved_by_username} expires in {int(hours_left)} hour(s).',
                'unit_id': unit.id,
                'serial_number': unit.serial_number,
                'reserved_by': unit.reserved_by_username,
                'expires_at': unit.reserved_until.isoformat() if unit.reserved_until else None,
                'hours_remaining': round(hours_left, 1),
                'action': 'release_or_extend',
            })
        
        # 3. Out of Stock Alerts - Products with no available units
        # For accessories, sum quantities; for phones/laptops/tablets, count units
        out_of_stock_products = Product.objects.annotate(
            available_count=Case(
                When(product_type=Product.ProductType.ACCESSORY, 
                     then=Coalesce(Sum('inventory_units__quantity', filter=Q(inventory_units__sale_status='AV')), Value(0))),
                default=Count('inventory_units', filter=Q(inventory_units__sale_status='AV')),
                output_field=IntegerField()
            )
        ).filter(available_count=0, is_discontinued=False)
        
        for product in out_of_stock_products:
            alerts.append({
                'id': f'out-of-stock-{product.id}',
                'type': 'out_of_stock',
                'severity': 'critical',
                'title': f'Out of Stock: {product.product_name}',
                'message': f'No available units for {product.product_name}. Consider restocking.',
                'product_id': product.id,
                'product_name': product.product_name,
                'action': 'restock',
            })
        
        # 4. Pending Approvals - Requests waiting for approval
        pending_reservations = ReservationRequest.objects.filter(status='PE').count()
        pending_returns = ReturnRequest.objects.filter(status='PE').count()
        pending_transfers = UnitTransfer.objects.filter(status='PE').count()
        
        if pending_reservations > 0:
            alerts.append({
                'id': 'pending-reservations',
                'type': 'pending_approval',
                'severity': 'low',
                'title': f'{pending_reservations} Pending Reservation Request(s)',
                'message': f'{pending_reservations} reservation request(s) waiting for approval.',
                'count': pending_reservations,
                'action': 'approve_requests',
                'link': '/reservation-requests',
            })
        
        if pending_returns > 0:
            alerts.append({
                'id': 'pending-returns',
                'type': 'pending_approval',
                'severity': 'low',
                'title': f'{pending_returns} Pending Return Request(s)',
                'message': f'{pending_returns} return request(s) waiting for approval.',
                'count': pending_returns,
                'action': 'approve_requests',
                'link': '/return-requests',
            })
        
        if pending_transfers > 0:
            alerts.append({
                'id': 'pending-transfers',
                'type': 'pending_approval',
                'severity': 'low',
                'title': f'{pending_transfers} Pending Transfer Request(s)',
                'message': f'{pending_transfers} transfer request(s) waiting for approval.',
                'count': pending_transfers,
                'action': 'approve_requests',
                'link': '/unit-transfers',
            })
        
        # Sort alerts by severity (critical > high > medium > low)
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        alerts.sort(key=lambda x: severity_order.get(x['severity'], 4))
        
        return Response({
            'count': len(alerts),
            'alerts': alerts
        }, status=status.HTTP_200_OK)


# -------------------------------------------------------------------------
# BRAND & LEAD MANAGEMENT VIEWSETS
# -------------------------------------------------------------------------

class BrandViewSet(viewsets.ModelViewSet):
    """Brand management ViewSet."""
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superuser sees all brands
        if user.is_superuser:
            return queryset
        
        # Check if admin is global admin
        try:
            admin = Admin.objects.get(user=user)
            if admin.is_global_admin:
                return queryset
            
            # Filter by admin's assigned brands
            if admin.brands.exists():
                return queryset.filter(id__in=admin.brands.values_list('id', flat=True))
        except Admin.DoesNotExist:
            pass
        
        return queryset.none()


@extend_schema_view(
    retrieve=extend_schema(parameters=[OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.PATH)]),
    update=extend_schema(parameters=[OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.PATH)]),
    partial_update=extend_schema(parameters=[OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.PATH)]),
    destroy=extend_schema(parameters=[OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.PATH)]),
    assign=extend_schema(parameters=[OpenApiParameter('id', OpenApiTypes.INT, OpenApiParameter.PATH)]),
)
class LeadViewSet(viewsets.ModelViewSet):
    """Lead management for salespersons only."""
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [IsAdminUser]  # Base permission, refined in get_permissions
    
    def get_permissions(self):
        """Restrict all lead actions to salespersons only."""
        # For all actions (list, retrieve, create, update, delete, and custom actions),
        # only salespersons should have access
        return [IsSalesperson()]
    
    def get_queryset(self):
        user = self.request.user
        brand = getattr(self.request, 'brand', None)
        
        queryset = Lead.objects.all().select_related(
            'customer', 'brand', 'assigned_salesperson__user', 'order'
        ).prefetch_related('items__inventory_unit__product_template')
        
        # Filter by brand if specified
        if brand:
            queryset = queryset.filter(brand=brand)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Superuser sees all
        if user.is_superuser:
            return queryset
        
        # Only salespersons can see leads (inventory managers cannot)
        try:
            admin = Admin.objects.get(user=user)
            if admin.is_salesperson:
                if admin.brands.exists() and not admin.is_global_admin:
                    queryset = queryset.filter(brand__in=admin.brands.all())
                elif admin.is_global_admin:
                    # Global admins see all leads
                    pass
            else:
                # Other roles (including inventory managers) don't see leads
                return Lead.objects.none()
        except Admin.DoesNotExist:
            return Lead.objects.none()
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Self-assign lead (salesperson claims lead). Only salespersons can claim leads."""
        import json
        import os
        
        # Use PESAPAL_LOG_PATH from environment variable, fallback to /tmp/pesapal_debug.log
        from django.conf import settings
        log_path = getattr(settings, 'PESAPAL_LOG_PATH', '/tmp/pesapal_debug.log')
        
        #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'views.py:2810',
                    'message': 'LeadViewSet.assign() ENTRY',
                    'data': {
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'username': request.user.username if request.user.is_authenticated else None,
                        'is_staff': request.user.is_staff if request.user.is_authenticated else False,
                        'lead_id': pk
                    },
                    'timestamp': int(__import__('time').time() * 1000)
                }) + '\n')
        except: pass
        #endregion
        
        lead = self.get_object()
        
        #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'B',
                    'location': 'views.py:2813',
                    'message': 'BEFORE checking admin and salesperson status',
                    'data': {
                        'lead_id': lead.id,
                        'lead_brand_id': lead.brand.id if lead.brand else None,
                        'lead_brand_name': lead.brand.name if lead.brand else None
                    },
                    'timestamp': int(__import__('time').time() * 1000)
                }) + '\n')
        except: pass
        #endregion
        
        try:
            admin = Admin.objects.get(user=request.user)
            
            #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'B',
                        'location': 'views.py:2815',
                        'message': 'Admin found - checking salesperson status',
                        'data': {
                            'admin_id': admin.id,
                            'admin_code': admin.admin_code,
                            'is_salesperson': admin.is_salesperson,
                            'is_global_admin': admin.is_global_admin,
                            'user_roles': list(admin.roles.values_list('name', flat=True)),
                            'admin_brand_ids': list(admin.brands.values_list('id', flat=True))
                        },
                        'timestamp': int(__import__('time').time() * 1000)
                    }) + '\n')
            except: pass
            #endregion
            
            # Double-check: Only salespersons can assign leads (permission should catch this, but verify)
            if not admin.is_salesperson and not request.user.is_superuser:
                #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'C',
                            'location': 'views.py:2816',
                            'message': 'PERMISSION DENIED: User is not a salesperson',
                            'data': {
                                'admin_id': admin.id,
                                'is_salesperson': admin.is_salesperson,
                                'roles': list(admin.roles.values_list('name', flat=True))
                            },
                            'timestamp': int(__import__('time').time() * 1000)
                        }) + '\n')
                except: pass
                #endregion
                return Response(
                    {'error': 'Only salespersons can assign leads'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Validate salesperson is associated with lead's brand (unless global admin)
            if not admin.is_global_admin and not request.user.is_superuser:
                if lead.brand not in admin.brands.all():
                    #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'E',
                                'location': 'views.py:2820',
                                'message': 'PERMISSION DENIED: Salesperson not associated with lead brand',
                                'data': {
                                    'lead_brand_id': lead.brand.id,
                                    'admin_brand_ids': list(admin.brands.values_list('id', flat=True)),
                                    'is_global_admin': admin.is_global_admin
                                },
                                'timestamp': int(__import__('time').time() * 1000)
                            }) + '\n')
                    except: pass
                    #endregion
                    return Response(
                        {'error': 'You are not associated with this lead\'s brand'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Allow salespersons to claim leads even if already assigned (reassignment)
            # This allows any salesperson to claim any lead for their brand
            lead.assigned_salesperson = admin
            lead.save()
            
            #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'D',
                        'location': 'views.py:2826',
                        'message': 'SUCCESS: Lead assigned to salesperson',
                        'data': {
                            'lead_id': lead.id,
                            'assigned_admin_id': admin.id,
                            'assigned_admin_code': admin.admin_code
                        },
                        'timestamp': int(__import__('time').time() * 1000)
                    }) + '\n')
            except: pass
            #endregion
            
            return Response({'message': 'Lead assigned successfully'})
        except Admin.DoesNotExist:
            #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'F',
                        'location': 'views.py:2828',
                        'message': 'ERROR: Admin profile not found',
                        'data': {'user_id': request.user.id},
                        'timestamp': int(__import__('time').time() * 1000)
                    }) + '\n')
            except: pass
            #endregion
            return Response(
                {'error': 'Admin profile not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def contact(self, request, pk=None):
        """Mark lead as contacted. Only salespersons can mark leads as contacted."""
        lead = self.get_object()
        
        # Verify user is a salesperson
        try:
            admin = Admin.objects.get(user=request.user)
            if not admin.is_salesperson and not request.user.is_superuser:
                return Response(
                    {'error': 'Only salespersons can mark leads as contacted'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify salesperson is assigned to this lead or is global admin
            if not request.user.is_superuser and not admin.is_global_admin:
                if lead.assigned_salesperson != admin:
                    return Response(
                        {'error': 'You can only mark leads as contacted if you are assigned to them'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
        except Admin.DoesNotExist:
            return Response(
                {'error': 'Admin profile not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        lead.status = Lead.StatusChoices.CONTACTED
        lead.contacted_at = timezone.now()
        lead.salesperson_notes = request.data.get('notes', '')
        lead.save()
        return Response({'message': 'Lead marked as contacted'})
    
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convert lead to order. Only salespersons can convert leads."""
        lead = self.get_object()
        try:
            admin = Admin.objects.get(user=request.user)
            
            # Verify user is a salesperson
            if not admin.is_salesperson and not request.user.is_superuser:
                return Response(
                    {'error': 'Only salespersons can convert leads to orders'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify salesperson is assigned to this lead or is global admin
            if not request.user.is_superuser and not admin.is_global_admin:
                if lead.assigned_salesperson != admin:
                    return Response(
                        {'error': 'You can only convert leads that are assigned to you'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            if lead.status != Lead.StatusChoices.CONTACTED:
                return Response(
                    {'error': 'Lead must be contacted first'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order = LeadService.convert_lead_to_order(lead, admin)
            return Response({
                'message': 'Lead converted to order',
                'order_id': str(order.order_id)
            })
        except Admin.DoesNotExist:
            return Response(
                {'error': 'Admin profile not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close lead (no sale) and release inventory units back to stock. Only salespersons can close leads."""
        from inventory.models import Cart, InventoryUnit
        from django.db import transaction
        
        lead = self.get_object()
        
        # Verify user is a salesperson
        try:
            admin = Admin.objects.get(user=request.user)
            if not admin.is_salesperson and not request.user.is_superuser:
                return Response(
                    {'error': 'Only salespersons can close leads'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify salesperson is assigned to this lead or is global admin
            if not request.user.is_superuser and not admin.is_global_admin:
                if lead.assigned_salesperson != admin:
                    return Response(
                        {'error': 'You can only close leads that are assigned to you'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
        except Admin.DoesNotExist:
            return Response(
                {'error': 'Admin profile not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Update lead status
            lead.status = Lead.StatusChoices.CLOSED
            lead.salesperson_notes = request.data.get('notes', '')
            lead.save()
            
            # Free up all inventory units in this lead
            lead_items = lead.items.all()
            units_freed = []
            
            for lead_item in lead_items:
                unit = lead_item.inventory_unit
                # Only free units that are RESERVED (not already SOLD or AVAILABLE)
                if unit.sale_status == InventoryUnit.SaleStatusChoices.RESERVED:
                    unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                    unit.reserved_by = None
                    unit.reserved_until = None
                    unit.save()
                    units_freed.append(unit)
            
            return Response({
                'message': f'Lead closed. {len(units_freed)} unit(s) released back to stock.',
                'units_freed': len(units_freed)
            })


class PromotionTypeViewSet(viewsets.ModelViewSet):
    """PromotionType management ViewSet (admin and marketing managers)."""
    queryset = PromotionType.objects.filter(is_active=True)
    serializer_class = PromotionTypeSerializer
    permission_classes = [IsAdminUser | IsMarketingManager]
    
    def get_queryset(self):
        """Return all promotion types (active and inactive) for admins."""
        queryset = PromotionType.objects.all()
        
        # Filter by is_active if provided
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('display_order', 'name')


class PromotionViewSet(viewsets.ModelViewSet):
    """Promotion management ViewSet (admin and marketing managers)."""
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    permission_classes = [IsAdminUser | IsMarketingManager]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # Support file uploads
    
    def get_queryset(self):
        queryset = super().get_queryset()
        brand = getattr(self.request, 'brand', None)
        user = self.request.user
        
        # Filter by brand if specified
        if brand:
            queryset = queryset.filter(brand=brand)
        
        # Filter by status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Superuser sees all
        if user.is_superuser:
            return queryset
        
        # Filter by admin's assigned brands
        try:
            admin = Admin.objects.get(user=user)
            if admin.is_global_admin:
                return queryset
            if admin.brands.exists():
                queryset = queryset.filter(brand__in=admin.brands.all())
        except Admin.DoesNotExist:
            return Promotion.objects.none()
        
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by to current admin and validate promotion requirements."""
        try:
            admin = Admin.objects.get(user=self.request.user)
        except Admin.DoesNotExist:
            admin = None
        
        # Validate: require at least one product or product_type
        # Handle products from both JSON and FormData
        if 'products' in self.request.data:
            products = self.request.data.get('products', [])
            # Handle QueryDict (FormData) format
            if hasattr(self.request.data, 'getlist'):
                products_list = self.request.data.getlist('products')
                has_products = len(products_list) > 0 and any(p for p in products_list if p)
            elif isinstance(products, list):
                has_products = len(products) > 0
            else:
                has_products = bool(products)
        else:
            has_products = False
        
        product_types = self.request.data.get('product_types', '')
        
        if not has_products and not product_types:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'non_field_errors': ['At least one product or product type must be specified.']
            })
        
        # Validate: cannot use both discount_percentage and discount_amount
        discount_percentage = self.request.data.get('discount_percentage')
        discount_amount = self.request.data.get('discount_amount')
        
        if discount_percentage and discount_amount:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'non_field_errors': ['Cannot use both discount_percentage and discount_amount. Use one or the other.']
            })
        
        # Validate: start_date must be before end_date
        start_date = self.request.data.get('start_date')
        end_date = self.request.data.get('end_date')
        
        if start_date and end_date:
            from django.utils.dateparse import parse_datetime
            start = parse_datetime(start_date)
            end = parse_datetime(end_date)
            if start and end and start >= end:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'non_field_errors': ['Start date must be before end date.']
                })
        
        # Validate: display_locations
        display_locations = self.request.data.get('display_locations', [])
        # Parse JSON string if it comes from FormData
        if isinstance(display_locations, str):
            import json
            try:
                display_locations = json.loads(display_locations)
                # Update request.data with parsed value so serializer can use it
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = True
                self.request.data['display_locations'] = display_locations
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = False
            except (json.JSONDecodeError, ValueError):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'display_locations': ['Display locations must be valid JSON.']
                })
        if not isinstance(display_locations, list):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'display_locations': ['Display locations must be a list.']
            })
        
        # Parse is_active from FormData (handle both string and boolean)
        if 'is_active' in self.request.data:
            is_active_value = self.request.data['is_active']
            if isinstance(is_active_value, str):
                # Convert string 'true'/'false' to boolean
                is_active_bool = is_active_value.lower() == 'true'
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = True
                self.request.data['is_active'] = is_active_bool
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = False
        
        valid_locations = ['stories_carousel', 'special_offers', 'flash_sales']
        invalid_locations = [loc for loc in display_locations if loc not in valid_locations]
        if invalid_locations:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'display_locations': [f'Invalid location(s): {", ".join(invalid_locations)}. Valid options: {", ".join(valid_locations)}.']
            })
        
        # Validate: banner_image required for stories_carousel
        if 'stories_carousel' in display_locations:
            banner_image = self.request.data.get('banner_image')
            if not banner_image and not serializer.instance:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'banner_image': ['Banner image is required when selecting Stories Carousel as a display location.']
                })
            elif serializer.instance and not banner_image and not serializer.instance.banner_image:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'banner_image': ['Banner image is required when selecting Stories Carousel as a display location.']
                })
        
        # Auto-assign brand if not provided and admin has brands
        brand_id = self.request.data.get('brand')
        if not brand_id and admin and admin.brands.exists() and not admin.is_global_admin:
            # Auto-assign to first brand if admin has only one, or require selection if multiple
            if admin.brands.count() == 1:
                brand_id = admin.brands.first().id
                # Update request.data to include the brand
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = True
                self.request.data['brand'] = brand_id
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = False
            else:
                # Multiple brands - require explicit selection
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'brand': ['You are assigned to multiple brands. Please select which brand this promotion is for.']
                })
        
        # Ensure brand is from admin's assigned brands (for non-superusers)
        user = self.request.user
        if admin and not admin.is_global_admin and not user.is_superuser:
            if brand_id:
                if admin.brands.exists():
                    if not admin.brands.filter(id=brand_id).exists():
                        from rest_framework.exceptions import PermissionDenied
                        raise PermissionDenied('You can only create promotions for your assigned brands.')
                else:
                    # Admin with no assigned brands cannot create promotions
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied('You must be assigned to at least one brand to create promotions.')
        
        # Promotion code will be auto-generated in model's save() method if not provided
        # #region agent log
        import json
        import os
        from django.core.files.storage import default_storage
        try:
            with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                storage_type = str(type(default_storage))
                has_banner = 'banner_image' in self.request.data
                banner_file = self.request.data.get('banner_image')
                f.write(json.dumps({"location":"views.py:4200","message":"Before promotion save - checking storage and banner_image","data":{"storage_type":storage_type,"is_cloudinary":'cloudinary' in storage_type.lower(),"has_banner_image":has_banner,"banner_image_type":str(type(banner_file)) if banner_file else None,"cloudinary_configured":bool(os.environ.get('CLOUDINARY_CLOUD_NAME'))},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except: pass
        # #endregion
        promotion_instance = serializer.save(created_by=admin)
        
        # DEBUG: Log banner image upload status (print to stdout for Render logs)
        import logging
        logger = logging.getLogger(__name__)
        if promotion_instance.banner_image:
            banner_url = promotion_instance.banner_image.url
            banner_name = promotion_instance.banner_image.name
            is_cloudinary = 'cloudinary.com' in banner_url.lower()
            storage_type = str(type(default_storage))
            logger.info(f"DEBUG: Banner image after save - URL: {banner_url}, Name: {banner_name}, IsCloudinary: {is_cloudinary}, Storage: {storage_type}")
            print(f"DEBUG: Banner image after save - URL: {banner_url}, Name: {banner_name}, IsCloudinary: {is_cloudinary}, Storage: {storage_type}")
        else:
            logger.info("DEBUG: No banner image after save")
            print("DEBUG: No banner image after save")
        
        # #region agent log
        try:
            with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                banner_url = promotion_instance.banner_image.url if promotion_instance.banner_image else None
                banner_name = promotion_instance.banner_image.name if promotion_instance.banner_image else None
                f.write(json.dumps({"location":"views.py:4203","message":"After promotion save - banner_image URL","data":{"promotion_id":promotion_instance.id,"banner_image_url":banner_url,"banner_image_name":banner_name,"is_cloudinary_url":'cloudinary.com' in str(banner_url).lower() if banner_url else False},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except: pass
        # #endregion
        
        # Handle products ManyToMany field (needs to be set after instance is created)
        # Always process products, even if empty (to clear existing associations if needed)
        product_ids = []
        
        # Check if products are in request data
        if 'products' in self.request.data:
            products = self.request.data.get('products', [])
            # Handle both list and QueryDict (FormData) formats
            if hasattr(self.request.data, 'getlist'):
                # QueryDict format (from FormData) - getlist returns all values
                product_ids = [int(p) for p in self.request.data.getlist('products') if p]
            elif isinstance(products, list):
                product_ids = [int(p) if isinstance(p, (int, str)) else (p.id if hasattr(p, 'id') else p) for p in products if p]
            elif products:
                product_ids = [int(products)] if str(products).isdigit() else []
        
        # Set products (empty list clears all products)
        promotion_instance.products.set(product_ids)
        
        # If promotion_code was provided, ensure it's unique
        promotion_code = self.request.data.get('promotion_code')
        if promotion_code:
            if Promotion.objects.filter(promotion_code=promotion_code).exclude(id=promotion_instance.id).exists():
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'promotion_code': ['A promotion with this code already exists.']
                })
            promotion_instance.promotion_code = promotion_code
            promotion_instance.save()
    
    def perform_update(self, serializer):
        """Allow update for Marketing Managers (full access)."""
        instance = serializer.instance
        user = self.request.user
        
        # #region agent log
        import json
        import os
        from django.core.files.storage import default_storage
        try:
            with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                storage_type = str(type(default_storage))
                has_banner = 'banner_image' in self.request.data
                banner_file = self.request.data.get('banner_image')
                old_banner_url = instance.banner_image.url if instance.banner_image else None
                f.write(json.dumps({"location":"views.py:4258","message":"Before promotion update - checking storage and banner_image","data":{"promotion_id":instance.id,"storage_type":storage_type,"is_cloudinary":'cloudinary' in storage_type.lower(),"has_banner_image":has_banner,"banner_image_type":str(type(banner_file)) if banner_file else None,"old_banner_url":old_banner_url,"cloudinary_configured":bool(os.environ.get('CLOUDINARY_CLOUD_NAME'))},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
        except: pass
        # #endregion
        
        # Superusers and global admins can edit any promotion
        if user.is_superuser:
            promotion_instance = serializer.save()
            # #region agent log
            try:
                with open('/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log', 'a') as f:
                    banner_url = promotion_instance.banner_image.url if promotion_instance.banner_image else None
                    banner_name = promotion_instance.banner_image.name if promotion_instance.banner_image else None
                    f.write(json.dumps({"location":"views.py:4265","message":"After promotion update - banner_image URL","data":{"promotion_id":promotion_instance.id,"banner_image_url":banner_url,"banner_image_name":banner_name,"is_cloudinary_url":'cloudinary.com' in str(banner_url).lower() if banner_url else False},"timestamp":int(__import__('time').time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + '\n')
            except: pass
            # #endregion
            return
        
        try:
            admin = Admin.objects.get(user=user)
            if admin.is_global_admin:
                serializer.save()
                return
            # Marketing Managers can edit any promotion (full access)
            if admin.is_marketing_manager:
                # Parse display_locations JSON string if it comes from FormData
                display_locations = self.request.data.get('display_locations')
                if display_locations is not None and isinstance(display_locations, str):
                    import json
                    try:
                        display_locations = json.loads(display_locations)
                        if hasattr(self.request.data, '_mutable'):
                            self.request.data._mutable = True
                        self.request.data['display_locations'] = display_locations
                        if hasattr(self.request.data, '_mutable'):
                            self.request.data._mutable = False
                    except (json.JSONDecodeError, ValueError):
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError({
                            'display_locations': ['Display locations must be valid JSON.']
                        })
                
                # Parse is_active from FormData
                if 'is_active' in self.request.data:
                    is_active_value = self.request.data['is_active']
                    if isinstance(is_active_value, str):
                        is_active_bool = is_active_value.lower() == 'true'
                        if hasattr(self.request.data, '_mutable'):
                            self.request.data._mutable = True
                        self.request.data['is_active'] = is_active_bool
                        if hasattr(self.request.data, '_mutable'):
                            self.request.data._mutable = False
                
                # Validate same requirements as create
                if 'products' in self.request.data:
                    products = self.request.data.get('products', [])
                    if hasattr(self.request.data, 'getlist'):
                        products_list = self.request.data.getlist('products')
                        has_products = len(products_list) > 0 and any(p for p in products_list if p)
                    elif isinstance(products, list):
                        has_products = len(products) > 0
                    else:
                        has_products = bool(products)
                else:
                    has_products = instance.products.exists() if instance else False
                
                product_types = self.request.data.get('product_types', instance.product_types if instance else '')
                
                if not has_products and not product_types:
                    from rest_framework.exceptions import ValidationError
                    raise ValidationError({
                        'non_field_errors': ['At least one product or product type must be specified.']
                    })
                
                promotion_instance = serializer.save()
                
                # Handle products ManyToMany field
                if 'products' in self.request.data:
                    products = self.request.data.get('products', [])
                    product_ids = []
                    
                    if hasattr(self.request.data, 'getlist'):
                        product_ids = [int(p) for p in self.request.data.getlist('products') if p]
                    elif isinstance(products, list):
                        product_ids = [int(p) if isinstance(p, (int, str)) else (p.id if hasattr(p, 'id') else p) for p in products if p]
                    elif products:
                        product_ids = [int(products)] if str(products).isdigit() else []
                    
                    promotion_instance.products.set(product_ids)
                
                return
        except Admin.DoesNotExist:
            pass
        
        # Fallback for other admin types - check ownership
        if instance.created_by and instance.created_by.user != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only edit promotions you created.')
        
        # Parse display_locations JSON string if it comes from FormData (same as in perform_create)
        display_locations = self.request.data.get('display_locations')
        if display_locations is not None and isinstance(display_locations, str):
            import json
            try:
                display_locations = json.loads(display_locations)
                # Update request.data with parsed value so serializer can use it
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = True
                self.request.data['display_locations'] = display_locations
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = False
            except (json.JSONDecodeError, ValueError):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'display_locations': ['Display locations must be valid JSON.']
                })
        
        # Parse is_active from FormData (handle both string and boolean)
        if 'is_active' in self.request.data:
            is_active_value = self.request.data['is_active']
            if isinstance(is_active_value, str):
                # Convert string 'true'/'false' to boolean
                is_active_bool = is_active_value.lower() == 'true'
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = True
                self.request.data['is_active'] = is_active_bool
                if hasattr(self.request.data, '_mutable'):
                    self.request.data._mutable = False
        
        # Validate same requirements as create
        # Handle products from both JSON and FormData
        if 'products' in self.request.data:
            products = self.request.data.get('products', [])
            # Handle QueryDict (FormData) format
            if hasattr(self.request.data, 'getlist'):
                products_list = self.request.data.getlist('products')
                has_products = len(products_list) > 0 and any(p for p in products_list if p)
            elif isinstance(products, list):
                has_products = len(products) > 0
            else:
                has_products = bool(products)
        else:
            # No products in request, check existing instance
            has_products = instance.products.exists() if instance else False
        
        product_types = self.request.data.get('product_types', instance.product_types if instance else '')
        
        if not has_products and not product_types:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'non_field_errors': ['At least one product or product type must be specified.']
            })
        
        promotion_instance = serializer.save()
        
        # Handle products ManyToMany field (needs to be set after instance is updated)
        # Always process products if they're in the request
        if 'products' in self.request.data:
            products = self.request.data.get('products', [])
            product_ids = []
            
            # Handle both list and QueryDict (FormData) formats
            if hasattr(self.request.data, 'getlist'):
                # QueryDict format (from FormData) - getlist returns all values
                product_ids = [int(p) for p in self.request.data.getlist('products') if p]
            elif isinstance(products, list):
                product_ids = [int(p) if isinstance(p, (int, str)) else (p.id if hasattr(p, 'id') else p) for p in products if p]
            elif products:
                product_ids = [int(products)] if str(products).isdigit() else []
            
            # Set products (empty list clears all products)
            promotion_instance.products.set(product_ids)
    
    def perform_destroy(self, instance):
        """Allow delete for Marketing Managers (full access)."""
        user = self.request.user
        
        # Superusers and global admins can delete any promotion
        if user.is_superuser:
            instance.delete()
            return
        
        try:
            admin = Admin.objects.get(user=user)
            if admin.is_global_admin:
                instance.delete()
                return
            # Marketing Managers can delete any promotion (full access)
            if admin.is_marketing_manager:
                instance.delete()
                return
        except Admin.DoesNotExist:
            pass
        
        # Fallback for other admin types - check ownership
        if instance.created_by and instance.created_by.user != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only delete promotions you created.')
        
        instance.delete()


class FixProductVisibilityView(APIView):
    """Admin endpoint to fix product visibility by setting units to AVAILABLE."""
    permission_classes = [permissions.AllowAny]  # Allow access with secret key
    serializer_class = FixProductVisibilitySerializer
    
    @extend_schema(request=FixProductVisibilitySerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        """Fix all inventory units to be available."""
        from inventory.models import InventoryUnit
        from django.db.models import Q
        from django.conf import settings
        
        # Check for secret key (set in environment: FIX_PRODUCTS_SECRET_KEY)
        secret_key = request.data.get('secret_key') or request.headers.get('X-Fix-Secret-Key')
        expected_secret = getattr(settings, 'FIX_PRODUCTS_SECRET_KEY', '')
        
        # Also allow authenticated admin users
        is_admin = request.user.is_authenticated and hasattr(request.user, 'admin')
        
        if not is_admin and (not secret_key or secret_key != expected_secret):
            return Response(
                {"detail": "Authentication required. Provide secret_key in body or X-Fix-Secret-Key header, or authenticate as admin."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            # Find all units that need fixing
            units_to_fix = InventoryUnit.objects.filter(
                ~Q(sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE) |
                Q(available_online=False)
            )
            
            total_count = units_to_fix.count()
            
            if total_count == 0:
                return Response({
                    "success": True,
                    "message": "All units are already available!",
                    "units_fixed": 0
                })
            
            # Fix all units
            updated = InventoryUnit.objects.filter(
                ~Q(sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE) |
                Q(available_online=False)
            ).update(
                sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                available_online=True
            )
            
            return Response({
                "success": True,
                "message": f"Fixed {updated} units! Products should now be visible.",
                "units_fixed": updated,
                "total_units_checked": total_count
            })
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BundleViewSet(viewsets.ModelViewSet):
    """Bundle management ViewSet (admin and marketing managers)."""
    queryset = Bundle.objects.all().select_related('brand', 'main_product').prefetch_related('items')
    serializer_class = BundleSerializer
    permission_classes = [IsBundleManagerOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        brand = getattr(self.request, 'brand', None)
        user = self.request.user
        
        if brand:
            queryset = queryset.filter(brand=brand)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if user.is_superuser:
            return queryset
        
        try:
            admin = Admin.objects.get(user=user)
            if admin.is_global_admin:
                return queryset
            if admin.brands.exists():
                queryset = queryset.filter(brand__in=admin.brands.all())
        except Admin.DoesNotExist:
            return Bundle.objects.none()
        
        return queryset
    
    def perform_create(self, serializer):
        try:
            admin = Admin.objects.get(user=self.request.user)
        except Admin.DoesNotExist:
            admin = None
        serializer.save(created_by=admin)


class BundleItemViewSet(viewsets.ModelViewSet):
    """Bundle item management (admin and marketing managers)."""
    queryset = BundleItem.objects.all().select_related('bundle', 'product')
    serializer_class = BundleItemSerializer
    permission_classes = [IsBundleManagerOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        bundle_id = self.request.query_params.get('bundle')
        if bundle_id:
            try:
                queryset = queryset.filter(bundle_id=int(bundle_id))
            except (TypeError, ValueError):
                return BundleItem.objects.none()
        return queryset


class PesapalIPNView(APIView):
    """Handle Pesapal IPN (Instant Payment Notification) callbacks."""
    permission_classes = [permissions.AllowAny]  # Pesapal will call this
    serializer_class = EmptySerializer
    
    @extend_schema(
        parameters=[
            OpenApiParameter('OrderTrackingId', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('OrderNotificationType', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('OrderMerchantReference', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('PaymentStatusDescription', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('PaymentMethod', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('PaymentAccount', OpenApiTypes.STR, OpenApiParameter.QUERY),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        print(f"\n[PESAPAL] ========== VIEW: IPN CALLBACK START ==========")
        print(f"[PESAPAL] Request Method: {request.method}")
        import json
        print(f"[PESAPAL] Request GET Params: {dict(request.GET)}")
        print(f"[PESAPAL] Request IP: {request.META.get('REMOTE_ADDR', 'Unknown')}")
        
        try:
            from inventory.services.pesapal_payment_service import PesapalPaymentService
            
            service = PesapalPaymentService()
            
            order_tracking_id = request.GET.get('OrderTrackingId')
            order_notification_type = request.GET.get('OrderNotificationType')
            order_merchant_reference = request.GET.get('OrderMerchantReference')
            payment_status_description = request.GET.get('PaymentStatusDescription')
            payment_method = request.GET.get('PaymentMethod')
            payment_account = request.GET.get('PaymentAccount')
            
            print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
            print(f"[PESAPAL] Notification Type: {order_notification_type}")
            print(f"[PESAPAL] Payment Status: {payment_status_description}")
            print(f"[PESAPAL] Payment Method: {payment_method}")
            
            if not order_tracking_id:
                print(f"[PESAPAL] ========== VIEW: IPN CALLBACK FAILED ==========")
                print(f"[PESAPAL] ERROR: OrderTrackingId required")
                print(f"[PESAPAL] =============================================\n")
                logger.warning("Pesapal IPN received without OrderTrackingId")
                return Response(
                    {'status': 'error', 'message': 'OrderTrackingId required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ipn_data = {
                'order_tracking_id': order_tracking_id,
                'order_notification_type': order_notification_type,
                'order_merchant_reference': order_merchant_reference,
                'payment_status_description': payment_status_description,
                'payment_method': payment_method,
                'payment_account': payment_account,
                'all_params': dict(request.GET)
            }
            
            print(f"[PESAPAL] Calling service.handle_ipn...")
            result = service.handle_ipn(
                order_tracking_id=order_tracking_id,
                order_notification_type=order_notification_type,
                order_merchant_reference=order_merchant_reference,
                payment_status_description=payment_status_description,
                payment_method=payment_method,
                payment_account=payment_account,
                ipn_data=ipn_data
            )
            
            print(f"[PESAPAL] Service result: {json.dumps(result, indent=2, default=str)}")
            logger.info(f"Pesapal IPN processed: {json.dumps(ipn_data)}")
            
            print(f"[PESAPAL] ========== VIEW: IPN CALLBACK SUCCESS ==========\n")
            return Response(
                {'status': 'success', 'message': 'IPN processed'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            print(f"[PESAPAL] ========== VIEW: IPN CALLBACK EXCEPTION ==========")
            print(f"[PESAPAL] ERROR: {str(e)}")
            import traceback
            print(f"[PESAPAL] Traceback:\n{traceback.format_exc()}")
            print(f"[PESAPAL] =================================================\n")
            logger.error(f"Error processing Pesapal IPN: {str(e)}", exc_info=True)
            return Response(
                {'status': 'error', 'message': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """Handle POST IPN (if Pesapal sends POST instead of GET)."""
        print(f"[PESAPAL] IPN POST request received, forwarding to GET handler")
        return self.get(request)

