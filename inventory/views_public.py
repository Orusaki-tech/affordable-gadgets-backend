"""Public API ViewSets for e-commerce frontend."""
from rest_framework import viewsets, permissions, status, filters, generics, exceptions
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiTypes, OpenApiParameter
from django.db.models import Q, Count, Min, Max, Prefetch, Sum, Case, When, IntegerField, Value, DecimalField, OuterRef, Subquery, Avg
from django.db.models.functions import Coalesce
from django.core.cache import cache
from urllib.parse import urlencode
from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone as django_timezone
from inventory.models import (
    Product, InventoryUnit, Cart, Lead, Brand, Promotion, ProductImage, Bundle, BundleItem,
    Order, OrderItem, Review, Customer, WishlistItem, DeliveryRate
)
from inventory.serializers_public import (
    PublicProductSerializer, PublicProductListSerializer, PublicInventoryUnitSerializer,
    CartSerializer, CartItemSerializer, CheckoutSerializer, PublicPromotionSerializer,
    CartCreateSerializer, CartItemCreateSerializer, CartBundleCreateSerializer, CheckoutResponseSerializer,
    PublicBundleSerializer, ReviewOtpRequestSerializer, ReviewEligibilityRequestSerializer,
    ReviewEligibilityItemSerializer, PublicReviewSubmitSerializer, PublicWishlistItemSerializer,
    PublicDeliveryRateSerializer, OrderOtpRequestSerializer, OrderHistoryRequestSerializer,
    PublicOrderSerializer
)
from inventory.serializers import LeadSerializer, ReviewSerializer
from inventory.services.cart_service import CartService
from inventory.services.customer_service import CustomerService
from inventory.services.delivery_service import get_delivery_fee
from inventory.services.otp_service import OtpService

# Optional Silk profiling: when SILKY_ENABLED, wrap views so the Silk "Profiling" tab has data
try:
    if getattr(settings, 'SILKY_ENABLED', False):
        from silk.profiling.profiler import silk_profile as _silk_profile
        from silk.collector import DataCollector as _silk_data_collector
    else:
        _silk_profile = None
        _silk_data_collector = None
except ImportError:
    _silk_profile = None
    _silk_data_collector = None

class _SilkProfileMixin:
    """When SILKY_ENABLED, wraps request in silk_profile() so the Silk Profiling tab shows Python profiler data.
    Only runs when DataCollector().request is set: Silk sets that only for intercepted requests
    (see SILKY_INTERCEPT_PERCENT in settings; default 10%). Use SILKY_INTERCEPT_PERCENT=100 to profile every request."""
    def dispatch(self, request, *args, **kwargs):
        if _silk_profile is not None and _silk_data_collector is not None:
            # Only use silk_profile when this request was intercepted (avoids "not installed correctly" warning)
            if _silk_data_collector().request is not None:
                try:
                    with _silk_profile(self.__class__.__name__):
                        return super().dispatch(request, *args, **kwargs)
                except (ValueError, Exception):
                    pass
        return super().dispatch(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter('page_size', OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter('type', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('search', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('brand_filter', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('min_price', OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
            OpenApiParameter('max_price', OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
            OpenApiParameter('ordering', OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter('promotion', OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter('slug', OpenApiTypes.STR, OpenApiParameter.QUERY),
        ]
    )
)
class PublicProductListPagination(PageNumberPagination):
    """Pagination for public product list that avoids the expensive COUNT query.
    Fetches page_size+1 rows to detect next page; does not return total count.
    """
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_size = 24

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        page_number = request.query_params.get(self.page_query_param, 1)
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            page_number = 1
        page_size = self.get_page_size(request)
        if page_number < 1:
            page_number = 1
        offset = (page_number - 1) * page_size
        # Fetch one extra to know if there is a next page (avoids COUNT query).
        chunk = list(queryset[offset : offset + page_size + 1])
        self._has_next = len(chunk) > page_size
        self._current_page = page_number
        self._page_size = page_size
        return chunk[:page_size]

    def get_paginated_response(self, data):
        from rest_framework.response import Response
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        request = getattr(self, 'request', None)
        if not request:
            return Response({'next': None, 'previous': None, 'results': data, 'count': None})
        base_url = request.build_absolute_uri(request.get_full_path())
        next_url = None
        if getattr(self, '_has_next', False):
            parsed = urlparse(base_url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            qs[self.page_query_param] = [str(self._current_page + 1)]
            next_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
        previous_url = None
        if self._current_page > 1:
            parsed = urlparse(base_url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            qs[self.page_query_param] = [str(self._current_page - 1)]
            previous_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
        return Response({
            'next': next_url,
            'previous': previous_url,
            'results': data,
            'count': None,  # Omitted to avoid expensive COUNT on complex queryset
        })


class PublicProductViewSet(_SilkProfileMixin, viewsets.ReadOnlyModelViewSet):
    """Public product browsing."""
    queryset = Product.objects.filter(is_discontinued=False, is_published=True)
    serializer_class = PublicProductSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = PublicProductListPagination
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ['product_name', 'brand', 'product_description']
    ordering_fields = ['product_name']  # Only order by real fields, not calculated ones
    # Don't set default ordering here - it will be applied in get_queryset after annotations
    lookup_field = 'pk'  # Use primary key for detail view

    def get_serializer_class(self):
        if getattr(self, 'action', None) == 'list' and not self.request.query_params.get('slug'):
            return PublicProductListSerializer
        return PublicProductSerializer

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def brands(self, request):
        """Return distinct brand names grouped by product type for menu use.
        Uses a minimal queryset (values_list) to avoid N+1 and heavy get_queryset pipeline.
        """
        product_type = request.query_params.get('type')
        available_types = {code for code, _ in Product.ProductType.choices}

        if product_type and product_type not in available_types:
            raise exceptions.ValidationError({"type": "Invalid product type."})

        # Minimal queryset: no prefetch/annotate, single query for distinct product_type + brand
        qs = Product.objects.filter(
            is_discontinued=False,
            is_published=True
        ).exclude(brand__isnull=True).exclude(brand__exact='')

        brand = getattr(request, 'brand', None)
        if brand:
            qs = qs.filter(
                Q(brands=brand) | Q(is_global=True) | Q(brands__isnull=True)
            ).distinct()

        if product_type:
            brands_list = (
                qs.filter(product_type=product_type)
                .values_list('brand', flat=True)
                .distinct()
                .order_by('brand')
            )
            return Response({"type": product_type, "results": list(brands_list)})

        brand_map = {code: [] for code, _ in Product.ProductType.choices}
        brand_rows = (
            qs.values_list('product_type', 'brand')
            .distinct()
            .order_by('product_type', 'brand')
        )
        for product_type_value, brand_name in brand_rows:
            brand_map.setdefault(product_type_value, []).append(brand_name)

        return Response({"results": brand_map})

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny], url_path='review-summary')
    def review_summary(self, request):
        """Return review summary (count + average) for a list of product IDs."""
        raw_ids = request.query_params.getlist('id')
        ids_param = request.query_params.get('ids')
        if not raw_ids and ids_param:
            raw_ids = [item.strip() for item in ids_param.split(',') if item.strip()]
        product_ids = []
        for raw_id in raw_ids:
            try:
                product_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue

        if not product_ids:
            return Response({"results": []})

        brand = getattr(request, 'brand', None)
        review_qs = Review.objects.filter(product_id__in=product_ids)
        if brand:
            review_qs = review_qs.filter(
                Q(product__brands=brand) |
                Q(product__brands__isnull=True) |
                Q(product__is_global=True)
            ).distinct()

        summary_rows = review_qs.values('product_id').annotate(
            review_count=Count('id'),
            average_rating=Avg('rating')
        )
        summary_map = {
            row['product_id']: {
                'review_count': row['review_count'],
                'average_rating': float(row['average_rating']) if row['average_rating'] is not None else None,
            }
            for row in summary_rows
        }

        results = [
            {
                'product_id': product_id,
                'review_count': summary_map.get(product_id, {}).get('review_count', 0),
                'average_rating': summary_map.get(product_id, {}).get('average_rating', None),
            }
            for product_id in product_ids
        ]
        return Response({"results": results})
    
    # #region agent log - Check ALL products in database (before any filtering)
    def _log_all_products_debug(self, debug_enabled=False):
        """Log all products in database for debugging visibility issues."""
        if not debug_enabled:
            return
        import json, time, os
        from inventory.models import Product, InventoryUnit
        try:
            os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
            # Get ALL products regardless of published/discontinued status
            all_products = Product.objects.all().values('id', 'product_name', 'is_published', 'is_discontinued', 'is_global')
            all_products_list = list(all_products)
            
            # Check brand assignments
            brand = getattr(self.request, 'brand', None)
            brand_code = self.request.headers.get('X-Brand-Code', 'NOT_PROVIDED')
            
            # For each product, check inventory units
            products_with_details = []
            for p in all_products_list[:10]:  # Limit to first 10 for performance
                product_obj = Product.objects.get(id=p['id'])
                total_units = product_obj.inventory_units.count()
                available_units = product_obj.inventory_units.filter(
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE
                ).count()
                available_online_units = product_obj.inventory_units.filter(
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    available_online=True
                ).count()
                
                # #region agent log - Detailed unit status breakdown
                unit_status_breakdown = {}
                if total_units > 0:
                    # Get actual unit statuses
                    units_by_status = product_obj.inventory_units.values('sale_status', 'available_online').annotate(
                        count=Count('id')
                    )
                    unit_status_breakdown = {f"{u['sale_status']}_online_{u['available_online']}": u['count'] for u in units_by_status}
                    # Also get sample unit details
                    sample_units = list(product_obj.inventory_units.values('id', 'sale_status', 'available_online')[:3])
                    unit_status_breakdown['sample_units'] = sample_units
                # #endregion
                
                # Check brand assignment
                product_brands = list(product_obj.brands.values_list('code', flat=True))
                is_global = product_obj.is_global
                brand_count = product_obj.brands.count()
                
                products_with_details.append({
                    'id': p['id'],
                    'product_name': p['product_name'],
                    'is_published': p['is_published'],
                    'is_discontinued': p['is_discontinued'],
                    'is_global': is_global,
                    'brand_count': brand_count,
                    'product_brands': product_brands,
                    'total_units': total_units,
                    'available_units': available_units,
                    'available_online_units': available_online_units,
                    'unit_status_breakdown': unit_status_breakdown,  # NEW: Detailed breakdown
                    'would_show_in_public': (
                        p['is_published'] and 
                        not p['is_discontinued'] and 
                        available_online_units > 0
                    )
                })
            
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "H1,H2,H3,H4,H5",
                "location": "inventory/views_public.py:PublicProductViewSet._log_all_products_debug",
                "message": "All products in database (first 10) - comprehensive check",
                "data": {
                    "total_products_in_db": Product.objects.count(),
                    "brand_code": brand_code,
                    "brand": str(brand) if brand else None,
                    "products": products_with_details
                },
                "timestamp": int(time.time() * 1000)
            }
            # Log to file (local) and Django logger (Render logs)
            try:
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except: pass
            # Use Django logger which Render captures
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"[PRODUCT_DEBUG] {json.dumps(log_entry)}")
        except Exception as e:
            try:
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H1,H2,H3,H4,H5",
                        "location": "inventory/views_public.py:PublicProductViewSet._log_all_products_debug",
                        "message": "Error in _log_all_products_debug",
                        "data": {"error": str(e)},
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except: pass
    # #endregion
    
    def list(self, request, *args, **kwargs):
        """Override list to catch exceptions during queryset evaluation."""
        import json, time, os, traceback
        debug_enabled = (
            settings.DEBUG
            or self.request.query_params.get('debug') == '1'
            or os.getenv("PUBLIC_PRODUCT_DEBUG") == "1"
        )
        import logging
        logger = logging.getLogger(__name__)
        start_time = time.perf_counter()
        cache_enabled = not debug_enabled and request.method == 'GET'
        if cache_enabled:
            cache_key = "public_products_list:" + request.headers.get('X-Brand-Code', '') + ":" + urlencode(sorted(request.query_params.items()))
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)
        
        try:
            # #region agent log - Before list call
            if debug_enabled:
                try:
                    queryset = self.get_queryset()
                    queryset_count = queryset.count()
                    
                    # Check if queryset can be evaluated (PostgreSQL might fail here)
                    try:
                        sample_products = list(queryset.values('id', 'product_name', 'is_global')[:3])
                        queryset_evaluates = True
                    except Exception as eval_err:
                        sample_products = []
                        queryset_evaluates = False
                        eval_error = str(eval_err)
                    
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H1,H2,H3,H4,H5",
                            "location": "inventory/views_public.py:PublicProductViewSet.list(before_super)",
                            "message": "Before calling super().list() - queryset evaluation test",
                            "data": {
                                "queryset_count": queryset_count,
                                "queryset_evaluates": queryset_evaluates,
                                "sample_products": sample_products,
                                "eval_error": eval_error if not queryset_evaluates else None,
                                "query_params": dict(request.query_params),
                                "page": request.query_params.get('page', '1'),
                                "page_size": request.query_params.get('page_size', '24'),
                                "brand_code": request.headers.get('X-Brand-Code', 'NOT_PROVIDED')
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except Exception as log_err:
                    try:
                        os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H1,H2,H3,H4,H5",
                                "location": "inventory/views_public.py:PublicProductViewSet.list(before_super_error)",
                                "message": "Error checking queryset before super().list()",
                                "data": {"error": str(log_err), "traceback": traceback.format_exc()},
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except: pass
            # #endregion
            
            response = super().list(request, *args, **kwargs)
            
            # #region agent log - After list call
            if debug_enabled:
                try:
                    response_data = response.data if hasattr(response, 'data') else None
                    result_count = len(response_data.get('results', [])) if response_data else 0

                    serialized_products = []
                    if response_data and response_data.get('results'):
                        for p in response_data.get('results', [])[:3]:
                            serialized_products.append({
                                "id": p.get("id"),
                                "product_name": p.get("product_name"),
                                "available_units_count": p.get("available_units_count", 0),
                            })

                    os.makedirs(
                        "/tmp/affordable-gadgets-debug",
                        exist_ok=True,
                    )
                    with open(
                        "/tmp/affordable-gadgets-debug/debug.log",
                        "a",
                    ) as f:
                        f.write(
                            json.dumps(
                                {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H5",
                                    "location": "inventory/views_public.py:PublicProductViewSet.list(after_super)",
                                    "message": "After calling super().list()",
                                    "data": {
                                        "response_count": response_data.get("count", 0) if response_data else 0,
                                        "results_count": result_count,
                                        "has_next": response_data.get("next") is not None if response_data else False,
                                        "has_previous": response_data.get("previous") is not None if response_data else False,
                                        "serialized_products": serialized_products,
                                    },
                                    "timestamp": int(time.time() * 1000),
                                }
                            )
                            + "\n"
                        )
                except Exception as log_err:
                    try:
                        os.makedirs(
                            "/tmp/affordable-gadgets-debug",
                            exist_ok=True,
                        )
                        with open(
                            "/tmp/affordable-gadgets-debug/debug.log",
                            "a",
                        ) as f:
                            f.write(
                                json.dumps(
                                    {
                                        "sessionId": "debug-session",
                                        "runId": "run1",
                                        "hypothesisId": "H5",
                                        "location": "inventory/views_public.py:PublicProductViewSet.list(after_super_error)",
                                        "message": "Error checking response after super().list()",
                                        "data": {"error": str(log_err), "traceback": traceback.format_exc()},
                                        "timestamp": int(time.time() * 1000),
                                    }
                                )
                                + "\n"
                            )
                    except Exception:
                        pass
            # #endregion
            
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "public_products_list completed in %sms (page=%s page_size=%s)",
                duration_ms,
                request.query_params.get('page', '1'),
                request.query_params.get('page_size', '24')
            )
            if cache_enabled and hasattr(response, 'data'):
                cache.set(cache_key, response.data, 180)
            return response
        except Exception as e:
            # #region agent log - List exception
            try:
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H1",
                        "location": "inventory/views_public.py:PublicProductViewSet.list(exception)",
                        "message": "Exception in list method",
                        "data": {
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "traceback": traceback.format_exc(),
                            "query_params": dict(request.query_params),
                            "brand_code": request.headers.get('X-Brand-Code', 'NOT_PROVIDED')
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except: pass
            # #endregion
            logger.error(f"Error in PublicProductViewSet.list: {e}", exc_info=True)
            return Response(
                {"detail": "An error occurred while loading products. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        """Cache public product detail responses."""
        debug_enabled = settings.DEBUG or request.query_params.get('debug') == '1'
        cache_enabled = not debug_enabled and request.method == 'GET'
        if cache_enabled:
            cache_key = "public_product_detail:" + request.headers.get('X-Brand-Code', '') + ":" + str(kwargs.get('pk'))
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)

        pk = kwargs.get('pk')
        product = Product.objects.filter(pk=pk).first()
        if product is None:
            raise exceptions.NotFound('No Product matches the given query.')
        serializer = self.get_serializer(product)
        response = Response(serializer.data)
        if cache_enabled:
            cache.set(cache_key, response.data, 120)
        return response
    
    def get_serializer_context(self):
        """Add request to serializer context for absolute URL building."""
        context = super().get_serializer_context()
        context['request'] = self.request
        context['brand'] = getattr(self.request, 'brand', None)
        return context
    
    def get_queryset(self):
        from inventory.models import ProductImage, Product
        import json, time, os, traceback
        debug_enabled = (
            settings.DEBUG
            or self.request.query_params.get('debug') == '1'
            or os.getenv("PUBLIC_PRODUCT_DEBUG") == "1"
        )
        
        def apply_public_ordering(queryset):
            """Apply safe ordering for public list endpoints."""
            ordering_param = self.request.query_params.get('ordering')
            if ordering_param:
                ordering_fields = [f.strip() for f in ordering_param.split(',')]
                valid_fields = ['product_name', 'min_price', 'max_price']
                validated_ordering = []
                for field in ordering_fields:
                    field_name = field.lstrip('-')
                    if field_name in valid_fields:
                        validated_ordering.append(field)
                if validated_ordering:
                    return queryset.order_by(*validated_ordering)
            # Default ordering for stable pagination
            return queryset.order_by('product_name')
        
        # #region agent log - Entry
        try:
            os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
            with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "H1,H2,H3,H4,H5",
                    "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(entry)",
                    "message": "get_queryset entry",
                    "data": {
                        "query_params": dict(self.request.query_params),
                        "brand_code": self.request.headers.get('X-Brand-Code', 'NOT_PROVIDED'),
                        "brand": str(getattr(self.request, 'brand', None))
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except: pass
        # #endregion
        
        # #region agent log - Comprehensive product check
        if debug_enabled:
            try:
                self._log_all_products_debug(debug_enabled=debug_enabled)
            except Exception as e:
                try:
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H1,H2,H3,H4,H5",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(debug_check_error)",
                            "message": "Error calling _log_all_products_debug",
                            "data": {"error": str(e)},
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
        # #endregion
        
        try:
            # Check for slug lookup early - if slug is provided, bypass brand filtering
            # This ensures accessories and other products are accessible by slug
            slug = self.request.query_params.get('slug')
            if slug:
                # For slug-based lookups, return product directly if it exists and is published
                # This bypasses brand filtering and available units filtering
                queryset = super().get_queryset().filter(slug=slug)
            
                # Still apply optimizations for the single product
                brand = getattr(self.request, 'brand', None)
                available_units_filter = Q(
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    available_online=True
                )
                if brand:
                    available_units_filter &= (Q(brands=brand) | Q(brands__isnull=True))
                
                available_units_prefetch = Prefetch(
                    'inventory_units',
                    queryset=InventoryUnit.objects.filter(available_units_filter).select_related('product_color'),
                    to_attr='available_units_list'
                )
                primary_images_prefetch = Prefetch(
                    'images',
                    queryset=ProductImage.objects.filter(is_primary=True),
                    to_attr='primary_images_list'
                )
                
                queryset = queryset.prefetch_related(
                    available_units_prefetch,
                    primary_images_prefetch
                )
                
                # For slug lookups, annotate aggregate fields for the detail serializer
                unit_base = InventoryUnit.objects.filter(
                    product_template=OuterRef('pk'),
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    available_online=True
                )
                if brand:
                    unit_base = unit_base.filter(Q(brands=brand) | Q(brands__isnull=True))

                unit_count_sub = unit_base.values('product_template').annotate(
                    total=Count('id')
                ).values('total')[:1]
                unit_qty_sub = unit_base.values('product_template').annotate(
                    total=Coalesce(Sum('quantity'), Value(0))
                ).values('total')[:1]
                min_price_sub = unit_base.order_by('selling_price').values('selling_price')[:1]
                max_price_sub = unit_base.order_by('-selling_price').values('selling_price')[:1]
                compare_unit_base = unit_base.filter(compare_at_price__isnull=False)
                compare_min_sub = compare_unit_base.order_by('compare_at_price').values('compare_at_price')[:1]
                compare_max_sub = compare_unit_base.order_by('-compare_at_price').values('compare_at_price')[:1]
                review_base = Review.objects.filter(product=OuterRef('pk'))
                review_count_sub = review_base.values('product').annotate(total=Count('id')).values('total')[:1]
                average_rating_sub = review_base.values('product').annotate(avg=Avg('rating')).values('avg')[:1]
                compare_unit_base = unit_base.filter(compare_at_price__isnull=False)
                compare_min_sub = compare_unit_base.order_by('compare_at_price').values('compare_at_price')[:1]
                compare_max_sub = compare_unit_base.order_by('-compare_at_price').values('compare_at_price')[:1]
                review_base = Review.objects.filter(product=OuterRef('pk'))
                review_count_sub = review_base.values('product').annotate(total=Count('id')).values('total')[:1]
                average_rating_sub = review_base.values('product').annotate(avg=Avg('rating')).values('avg')[:1]
                compare_unit_base = unit_base.filter(compare_at_price__isnull=False)
                compare_min_sub = compare_unit_base.order_by('compare_at_price').values('compare_at_price')[:1]
                compare_max_sub = compare_unit_base.order_by('-compare_at_price').values('compare_at_price')[:1]
                review_base = Review.objects.filter(product=OuterRef('pk'))
                review_count_sub = review_base.values('product').annotate(total=Count('id')).values('total')[:1]
                average_rating_sub = review_base.values('product').annotate(avg=Avg('rating')).values('avg')[:1]

                queryset = queryset.annotate(
                    available_units_count=Case(
                        When(
                            product_type=Product.ProductType.ACCESSORY,
                            then=Coalesce(Subquery(unit_qty_sub), Value(0)),
                        ),
                        default=Coalesce(Subquery(unit_count_sub), Value(0)),
                        output_field=IntegerField(),
                    ),
                    min_price=Coalesce(Subquery(min_price_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    max_price=Coalesce(Subquery(max_price_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    compare_at_min_price=Coalesce(Subquery(compare_min_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    compare_at_max_price=Coalesce(Subquery(compare_max_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    review_count=Coalesce(Subquery(review_count_sub), Value(0), output_field=IntegerField()),
                    average_rating=Coalesce(Subquery(average_rating_sub), Value(None), output_field=DecimalField(max_digits=4, decimal_places=2)),
                )
                
                # #region agent log
                try:
                    import json, time, os, traceback
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    accessory_sample = queryset.filter(product_type=Product.ProductType.ACCESSORY).first()
                    if accessory_sample:
                        accessory_units = accessory_sample.inventory_units.filter(units_filter)
                        sum_qty = accessory_units.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
                        count_units = accessory_units.count()
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "pre-fix",
                                "hypothesisId": "H2",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(slug)",
                                "message": "Public slug count vs quantity",
                                "data": {
                                    "product_id": accessory_sample.id,
                                    "count_units": count_units,
                                    "sum_quantity": sum_qty,
                                    "available_units_count": accessory_sample.available_units_count
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    else:
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "pre-fix",
                                "hypothesisId": "H2",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(slug)",
                                "message": "No accessory found in queryset",
                                "data": {"queryset_count": queryset.count()},
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                except Exception as e:
                    import os
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "pre-fix",
                            "hypothesisId": "H2",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(slug)",
                            "message": "Exception in logging",
                            "data": {"error": str(e)},
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                # #endregion
                
                return queryset
            
            # Normal queryset filtering for list views
            queryset = super().get_queryset()
            brand = getattr(self.request, 'brand', None)
            is_list = getattr(self, 'action', None) == 'list' and not self.request.query_params.get('slug')
            is_detail = getattr(self, 'action', None) == 'retrieve'
            
            # #region agent log - After initial queryset
            try:
                # Use exists() instead of count() to avoid evaluating queryset
                initial_exists = queryset.exists()
                # Get a sample of product IDs and their published status for debugging
                sample_products = []
                try:
                    sample_products = list(queryset.values('id', 'product_name', 'is_published', 'is_discontinued')[:5])
                except Exception:
                    sample_products = [{"error": "could_not_fetch"}]
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H2",
                        "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(after_initial)",
                        "message": "After initial queryset",
                        "data": {
                            "initial_exists": initial_exists,
                            "brand": str(brand),
                            "brand_id": brand.id if brand else None,
                            "sample_products": sample_products
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception as e:
                try:
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H1,H4",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(after_initial)",
                            "message": "Exception checking initial queryset",
                            "data": {"error": str(e), "traceback": traceback.format_exc()},
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
            # #endregion
            
            # Log for debugging (remove in production)
            import logging
            logger = logging.getLogger(__name__)
            try:
                logger.info(f"PublicProductViewSet: brand={brand}, initial queryset exists={queryset.exists()}")
                # Check a sample product's inventory units
                sample = queryset.first()
                if sample:
                    total_units = sample.inventory_units.count()
                    available_units = sample.inventory_units.filter(
                        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE
                    ).count()
                    available_online_units = sample.inventory_units.filter(
                        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                        available_online=True
                    ).count()
                    logger.info(f"Sample product {sample.id} ({sample.product_name}): total_units={total_units}, available={available_units}, available_online={available_online_units}")
            except Exception as e:
                logger.warning(f"PublicProductViewSet: brand={brand}, could not check queryset: {e}")
            
            # Base filter for available units
            available_units_filter = Q(
                sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                available_online=True
            )
            
            # Add brand filter to units if brand is provided
            if brand:
                available_units_filter &= (Q(brands=brand) | Q(brands__isnull=True))
            
            # #region agent log - Check inventory units
            try:
                # Check if products have any inventory units at all (regardless of status)
                sample_product = queryset.first()
                if sample_product:
                    total_units = sample_product.inventory_units.count()
                    available_units = sample_product.inventory_units.filter(
                        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE
                    ).count()
                    available_online_units = sample_product.inventory_units.filter(
                        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                        available_online=True
                    ).count()
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H5",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(units_check)",
                            "message": "Inventory units check for sample product",
                            "data": {
                                "product_id": sample_product.id,
                                "product_name": sample_product.product_name,
                                "total_units": total_units,
                                "available_units": available_units,
                                "available_online_units": available_online_units,
                                "brand_filter_applied": brand is not None
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
            except Exception as e:
                try:
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H5",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(units_check_exception)",
                            "message": "Exception checking inventory units",
                            "data": {"error": str(e)},
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
            # #endregion
            
            # Prefetch primary images
            primary_images_prefetch = Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_primary=True),
                to_attr='primary_images_list'
            )
            
            if is_list:
                # Annotate review aggregates once to avoid N+1 in serializer (get_review_count, get_average_rating).
                now = django_timezone.now()
                review_count_sub = Review.objects.filter(product=OuterRef('pk')).values('product').annotate(total=Count('id')).values('total')[:1]
                average_rating_sub = Review.objects.filter(product=OuterRef('pk')).values('product').annotate(avg=Avg('rating')).values('avg')[:1]
                queryset = queryset.annotate(
                    review_count=Coalesce(Subquery(review_count_sub), Value(0), output_field=IntegerField()),
                    average_rating=Coalesce(Subquery(average_rating_sub), Value(None), output_field=DecimalField(max_digits=4, decimal_places=2)),
                )

                # Use prefetched available units for accurate brand-aware counts/prices.
                # Avoid annotations with ManyToMany brand filters that can yield zero counts on PostgreSQL.
                available_units_filter = Q(
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    available_online=True,
                    quantity__gt=0,
                )
                if brand:
                    available_units_filter &= (Q(brands=brand) | Q(brands__isnull=True))

                available_units_prefetch = Prefetch(
                    'inventory_units',
                    queryset=InventoryUnit.objects.filter(available_units_filter).select_related('product_color'),
                    to_attr='available_units_list'
                )

                # Prefetch bundles for list (has_active_bundle, bundle_price_preview) to avoid N+1.
                bundle_date_filter = (
                    Q(start_date__isnull=True) | Q(start_date__lte=now),
                    Q(end_date__isnull=True) | Q(end_date__gte=now),
                )
                bundles_qs = Bundle.objects.filter(
                    is_active=True,
                    show_in_listings=True
                ).filter(*bundle_date_filter).prefetch_related('items__product')
                if brand:
                    bundles_qs = bundles_qs.filter(brand=brand)
                bundles_prefetch = Prefetch('bundles', queryset=bundles_qs, to_attr='active_bundles_list')

                queryset = queryset.only(
                    'id',
                    'product_name',
                    'brand',
                    'model_series',
                    'product_type',
                    'slug',
                    'product_video_url',
                    'is_published',
                    'is_discontinued',
                ).prefetch_related(
                    primary_images_prefetch,
                    available_units_prefetch,
                    'tags',
                    bundles_prefetch,
                )

                # Filter to products with at least one available unit (quantity > 0).
                product_units_filter = Q(
                    inventory_units__sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    inventory_units__available_online=True,
                    inventory_units__quantity__gt=0,
                )
                if brand:
                    product_units_filter &= (Q(inventory_units__brands=brand) | Q(inventory_units__brands__isnull=True))

                queryset = queryset.filter(product_units_filter).distinct()
                return apply_public_ordering(queryset)

            if is_detail:
                # Detail path: prefetch filtered units and primary images and annotate aggregates
                available_units_prefetch = Prefetch(
                    'inventory_units',
                    queryset=InventoryUnit.objects.filter(available_units_filter).select_related('product_color'),
                    to_attr='available_units_list'
                )
                queryset = queryset.prefetch_related(
                    available_units_prefetch,
                    primary_images_prefetch
                )

                unit_base = InventoryUnit.objects.filter(
                    product_template=OuterRef('pk'),
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    available_online=True
                )
                if brand:
                    unit_base = unit_base.filter(Q(brands=brand) | Q(brands__isnull=True))

                unit_count_sub = unit_base.values('product_template').annotate(
                    total=Count('id')
                ).values('total')[:1]
                unit_qty_sub = unit_base.values('product_template').annotate(
                    total=Coalesce(Sum('quantity'), Value(0))
                ).values('total')[:1]
                min_price_sub = unit_base.order_by('selling_price').values('selling_price')[:1]
                max_price_sub = unit_base.order_by('-selling_price').values('selling_price')[:1]

                queryset = queryset.annotate(
                    available_units_count=Case(
                        When(
                            product_type=Product.ProductType.ACCESSORY,
                            then=Coalesce(Subquery(unit_qty_sub), Value(0)),
                        ),
                        default=Coalesce(Subquery(unit_count_sub), Value(0)),
                        output_field=IntegerField(),
                    ),
                    min_price=Coalesce(Subquery(min_price_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    max_price=Coalesce(Subquery(max_price_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    compare_at_min_price=Coalesce(Subquery(compare_min_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    compare_at_max_price=Coalesce(Subquery(compare_max_sub), Value(None), output_field=DecimalField(max_digits=10, decimal_places=2)),
                    review_count=Coalesce(Subquery(review_count_sub), Value(0), output_field=IntegerField()),
                    average_rating=Coalesce(Subquery(average_rating_sub), Value(None), output_field=DecimalField(max_digits=4, decimal_places=2)),
                )
                # Do not enforce available_units_count on detail view to match slug behavior.
                return queryset

            # Prefetch available units with brand filtering
            available_units_prefetch = Prefetch(
                'inventory_units',
                queryset=InventoryUnit.objects.filter(available_units_filter).select_related('product_color'),
                to_attr='available_units_list'
            )

            # Annotate with aggregated data to avoid N+1 queries
            queryset = queryset.prefetch_related(
                available_units_prefetch,
                primary_images_prefetch
            )
            
            # Annotate with unit counts and prices
            # NOTE: Brand filtering for units in annotations is complex with ManyToMany
            # Units with no brands should be available to all brands, but brands__isnull=True
            # doesn't work in ManyToMany annotations. Instead, we'll:
            # 1. Count all available units (brand filtering handled by prefetch and serializer)
            # 2. The prefetch already filters units by brand correctly
            # 3. The serializer will use the prefetched available_units_list
            units_filter = Q(
                inventory_units__sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                inventory_units__available_online=True
            )
            # Don't filter by brand in annotation - let prefetch handle it
            # This ensures units with no brands are included (they're available to all brands)
            
            # #region agent log - Before annotations
            try:
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H4",
                        "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(before_annotate)",
                        "message": "Before annotations",
                        "data": {
                            "queryset_exists": queryset.exists(),
                            "has_brand": brand is not None
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except: pass
            # #endregion
            
            # For accessories, sum quantities; for phones/laptops/tablets, count units
            try:
                # #region agent log - Before annotation calculation
                try:
                    # Check a sample product's units before annotation
                    sample_before = queryset.first()
                    if sample_before:
                        total_units_all = sample_before.inventory_units.count()
                        matching_units = sample_before.inventory_units.filter(
                            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                            available_online=True
                        )
                        if brand:
                            matching_units = matching_units.filter(Q(brands=brand) | Q(brands__isnull=True))
                        matching_count = matching_units.count()
                        if sample_before.product_type == Product.ProductType.ACCESSORY:
                            matching_qty = matching_units.aggregate(total=Sum('quantity'))['total'] or 0
                        else:
                            matching_qty = matching_count
                        os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H4",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(before_annotation_calc)",
                                "message": "Before annotation calculation - manual check",
                                "data": {
                                    "product_id": sample_before.id,
                                    "product_name": sample_before.product_name,
                                    "product_type": sample_before.product_type,
                                    "total_units_all": total_units_all,
                                    "matching_units_count": matching_count,
                                    "expected_available_units_count": matching_qty,
                                    "brand_filter": str(brand) if brand else None
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                except Exception as e:
                    try:
                        os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H4",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(before_annotation_calc_error)",
                                "message": "Error in before annotation check",
                                "data": {"error": str(e)},
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except: pass
                # #endregion
                
                # Calculate annotation - but note: this may not count correctly due to ManyToMany complexity
                # The serializer will use prefetched available_units_list for accurate counts
                # NOTE: We don't annotate brand_count anymore since we use direct relationship checks
                # PostgreSQL handles ManyToMany Count annotations differently than SQLite
                # This avoids PostgreSQL-specific issues with annotation evaluation
                
                # For available_units_count, min_price, max_price: 
                # PostgreSQL has issues with ManyToMany annotation filters
                # The serializer will use prefetched available_units_list for accurate values
                # We don't add annotations here - they cause PostgreSQL evaluation issues
                # The serializer calculates everything from prefetched data, which is more reliable
                # This avoids PostgreSQL-specific annotation issues that work fine in SQLite
                
                # Log queryset count (no annotations to log)
                import logging
                logger = logging.getLogger(__name__)
                try:
                    count = queryset.count()
                    logger.info(f"QUERYSET_COUNT: Queryset has {count} products after prefetch (no annotations)")
                    if count > 0:
                        sample = queryset.values('id', 'product_name')[:1]
                        if sample:
                            p = list(sample)[0]
                            logger.info(f"QUERYSET_SAMPLE: Product {p['id']} ({p['product_name']})")
                except Exception as e:
                    logger.error(f"QUERYSET_COUNT_ERROR: {str(e)}", exc_info=True)
                
                # #region agent log - After prefetch - verify queryset
                try:
                    sample_after = queryset.first()
                    if sample_after:
                        prefetched_count = len(sample_after.available_units_list) if hasattr(sample_after, 'available_units_list') else 0
                        os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H4",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(after_prefetch)",
                                "message": "After prefetch - verification",
                                "data": {
                                    "product_id": sample_after.id,
                                    "product_name": sample_after.product_name,
                                    "prefetched_units_count": prefetched_count,
                                    "queryset_exists": queryset.exists()
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                except Exception as e:
                    try:
                        os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H4",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(after_prefetch_error)",
                                "message": "Error verifying prefetch",
                                "data": {"error": str(e)},
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except: pass
                # #endregion
            except Exception as e:
                # #region agent log - Annotation exception
                try:
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H1,H4",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(annotate_exception)",
                            "message": "Exception during annotations",
                            "data": {"error": str(e), "traceback": traceback.format_exc()},
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
                # #endregion
                raise
            
            # #region agent log - Check prefetched data after all filtering
            try:
                import json, time, os
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                # Get first few products and check their prefetched units
                # Use values() to avoid full object evaluation
                sample_products_data = list(queryset.values('id', 'product_name', 'product_type')[:5])
                prefetch_data = []
                for p in sample_products_data:
                    try:
                        product_obj = queryset.filter(id=p['id']).first()
                        prefetched_count = len(product_obj.available_units_list) if (product_obj and hasattr(product_obj, 'available_units_list')) else 0
                        prefetch_data.append({
                            "product_id": p['id'],
                            "product_name": p['product_name'],
                            "product_type": p['product_type'],
                            "prefetched_units_count": prefetched_count,
                        })
                    except Exception as e:
                        prefetch_data.append({
                            "product_id": p.get('id'),
                            "error": str(e)
                        })
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H4",
                        "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(check_prefetch)",
                        "message": "Check prefetched data after all filtering",
                        "data": {
                            "prefetch_data": prefetch_data,
                            "queryset_count": queryset.count()
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception as e:
                try:
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H4",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(check_prefetch_error)",
                            "message": "Error checking prefetch",
                            "data": {"error": str(e)},
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
            # #endregion
            
            # #region agent log - Before brand filtering
            try:
                before_brand_exists = queryset.exists()
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H2",
                        "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(before_brand_filter)",
                        "message": "Before brand filtering",
                        "data": {
                            "exists": before_brand_exists,
                            "brand": str(brand),
                            "will_filter": brand is not None
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except: pass
            # #endregion
            
            # Brand filtering
            # When a specific brand is requested, show products for that brand, global products, or products with no brand
            # When no brand is specified, show all published products (not just global ones)
            if brand and not is_detail:
                # PostgreSQL vs SQLite: ManyToMany annotations and NULL checks work differently
                # Use direct relationship checks that work in both databases
                # Show products that:
                # 1. Have this brand assigned (Q(brands=brand))
                # 2. Are global (Q(is_global=True)) - available to all brands
                # Since all current products are is_global=True, this should match all products
                queryset = queryset.filter(
                    Q(brands=brand) | Q(is_global=True)
                ).distinct()
            # No brand filter - show all published products (including those with brands assigned)
            # This ensures accessories and other products are visible even when no brand is specified
            
            # #region agent log - After brand filtering
            try:
                after_brand_exists = queryset.exists()
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H2",
                        "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(after_brand_filter)",
                        "message": "After brand filtering",
                        "data": {
                            "exists": after_brand_exists,
                            "brand": str(brand)
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except: pass
            # #endregion
            
            # Additional filters
            product_type = self.request.query_params.get('type')
            if product_type:
                queryset = queryset.filter(product_type=product_type)
            
            brand_filter = self.request.query_params.get('brand_filter')
            if brand_filter:
                queryset = queryset.filter(brand__icontains=brand_filter)
            
            # Price range filtering
            min_price = self.request.query_params.get('min_price')
            max_price = self.request.query_params.get('max_price')
            if min_price:
                try:
                    queryset = queryset.filter(min_price__gte=float(min_price))
                except (ValueError, TypeError):
                    pass
            if max_price:
                try:
                    queryset = queryset.filter(max_price__lte=float(max_price))
                except (ValueError, TypeError):
                    pass
            
            # Promotion filtering
            promotion_id = self.request.query_params.get('promotion')
            if promotion_id:
                # #region agent log - Before promotion filtering
                try:
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H3",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(before_promotion)",
                            "message": "Before promotion filtering",
                            "data": {
                                "promotion_id": promotion_id,
                                "brand": str(brand),
                                "brand_is_none": brand is None,
                                "queryset_exists": queryset.exists()
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
                # #endregion
                try:
                    if brand is None:
                        # #region agent log - Promotion with None brand
                        try:
                            os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                            with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "H3",
                                    "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(promotion_none_brand)",
                                    "message": "Promotion query with None brand - will fail",
                                    "data": {"promotion_id": promotion_id},
                                    "timestamp": int(time.time() * 1000)
                                }) + "\n")
                        except: pass
                        # #endregion
                        queryset = queryset.none()
                    else:
                        promotion = Promotion.objects.get(id=int(promotion_id), brand=brand, is_active=True)
                        # Check if promotion is currently active (within date range)
                        from django.utils import timezone
                        now = timezone.now()
                        if promotion.start_date <= now <= promotion.end_date:
                            # Filter by promotion's products or product_types
                            if promotion.products.exists():
                                # Filter by specific products
                                queryset = queryset.filter(id__in=promotion.products.values_list('id', flat=True))
                            elif promotion.product_types:
                                # Filter by product type
                                queryset = queryset.filter(product_type=promotion.product_types)
                            else:
                                # No products or product_types specified - return empty
                                queryset = queryset.none()
                        else:
                            # Promotion not currently active - return empty
                            queryset = queryset.none()
                except (Promotion.DoesNotExist, ValueError, TypeError) as e:
                    # #region agent log - Promotion exception
                    try:
                        os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H3",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(promotion_exception)",
                                "message": "Promotion query exception",
                                "data": {
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                    "promotion_id": promotion_id,
                                    "brand": str(brand)
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except: pass
                    # #endregion
                    # Invalid promotion ID - return empty
                    queryset = queryset.none()
                except Exception as e:
                    # #region agent log - Unexpected promotion exception
                    try:
                        os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                        with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H1,H3",
                                "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(promotion_unexpected)",
                                "message": "Unexpected exception in promotion filtering",
                                "data": {
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                    "traceback": traceback.format_exc()
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except: pass
                    # #endregion
                    raise
            
            # Apply ordering manually (stable pagination; avoid placeholder ordering)
            queryset = apply_public_ordering(queryset)
            
            # Apply search filter (OrderingFilter is handled above)
            for backend in self.filter_backends:
                if hasattr(backend, 'filter_queryset') and backend != filters.OrderingFilter:
                    queryset = backend().filter_queryset(self.request, queryset, self)
            
            # Log final queryset count
            import logging
            logger = logging.getLogger(__name__)
            try:
                # #region agent log - Test queryset evaluation before count
                try:
                    import json, time, os
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    # Try to evaluate queryset to see if it fails in PostgreSQL
                    try:
                        test_eval = list(queryset.values('id', 'product_name')[:3])
                        eval_success = True
                        eval_error = None
                    except Exception as eval_err:
                        test_eval = []
                        eval_success = False
                        eval_error = str(eval_err)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H1,H2,H3,H4,H5",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(before_count)",
                            "message": "Testing queryset evaluation before count()",
                            "data": {
                                "eval_success": eval_success,
                                "eval_error": eval_error,
                                "test_products": test_eval,
                                "brand": str(brand) if brand else None
                            },
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
                # #endregion
                
                final_count = queryset.count()
                logger.info(f"FINAL_COUNT: {final_count} products after all filtering")
                if final_count > 0:
                    sample_data = list(queryset.values('id', 'product_name')[:1])
                    if sample_data:
                        p = sample_data[0]
                        logger.info(f"FINAL_SAMPLE: Product {p['id']} ({p['product_name']})")
                else:
                    logger.warning(f"FINAL_COUNT_ZERO: No products returned! Initial queryset existed but all were filtered out.")
                    # #region agent log - Why products were filtered out
                    try:
                        # Check why products were filtered - get sample products that passed initial filter but failed later
                        initial_queryset = Product.objects.filter(is_discontinued=False, is_published=True)
                        sample_products = list(initial_queryset.values('id', 'product_name')[:5])
                        for prod_data in sample_products:
                            prod = Product.objects.get(id=prod_data['id'])
                            all_units = prod.inventory_units.all()
                            unit_statuses = {}
                            for unit in all_units:
                                key = f"{unit.sale_status}_online_{unit.available_online}"
                                unit_statuses[key] = unit_statuses.get(key, 0) + 1
                            logger.error(f"[PRODUCT_DEBUG] Product {prod.id} ({prod.product_name}): {len(all_units)} units, statuses={unit_statuses}")
                    except Exception as e:
                        logger.error(f"[PRODUCT_DEBUG] Error checking filtered products: {e}")
                    # #endregion
            except Exception as e:
                logger.error(f"FINAL_COUNT_ERROR: {str(e)}", exc_info=True)
            
            # #region agent log - Final queryset before return
            try:
                final_exists = queryset.exists()
                final_count = queryset.count()
                # Get sample products with their available_units_count to see why they might not be showing
                sample_products = []
                if final_exists:
                    try:
                        # Get first 5 products with their annotations and prefetched units
                        products_data = list(queryset.values('id', 'product_name', 'available_units_count', 'min_price', 'max_price', 'product_type')[:5])
                        for p in products_data:
                            # Get the actual product object to check prefetched units
                            product_obj = queryset.filter(id=p['id']).first()
                            prefetched_count = 0
                            if product_obj and hasattr(product_obj, 'available_units_list'):
                                prefetched_count = len(product_obj.available_units_list)
                            
                            sample_products.append({
                                'id': p['id'],
                                'product_name': p['product_name'],
                                'product_type': p['product_type'],
                                'annotated_available_units_count': p['available_units_count'],
                                'prefetched_units_count': prefetched_count,
                                'min_price': float(p['min_price']) if p['min_price'] is not None else None,
                                'max_price': float(p['max_price']) if p['max_price'] is not None else None,
                            })
                    except Exception as e:
                        sample_products = [{"error": str(e), "traceback": traceback.format_exc()}]
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H5",
                        "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(final)",
                        "message": "Final queryset before return",
                        "data": {
                            "final_exists": final_exists,
                            "final_count": final_count,
                            "sample_products": sample_products,
                            "ordering_param": self.request.query_params.get('ordering', 'none')
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception as e:
                try:
                    os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                    with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H1",
                            "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(final_exception)",
                            "message": "Exception checking final queryset",
                            "data": {"error": str(e), "traceback": traceback.format_exc()},
                            "timestamp": int(time.time() * 1000)
                        }) + "\n")
                except: pass
            # #endregion
            
            return queryset
        except Exception as e:
            # #region agent log - Top level exception
            try:
                os.makedirs("/tmp/affordable-gadgets-debug", exist_ok=True)
                with open("/tmp/affordable-gadgets-debug/debug.log", "a") as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H1",
                        "location": "inventory/views_public.py:PublicProductViewSet.get_queryset(top_level_exception)",
                        "message": "Top level exception in get_queryset",
                        "data": {
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "traceback": traceback.format_exc()
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except: pass
            # #endregion
            # Return empty queryset to prevent 500 error, but log the exception
            from inventory.models import Product
            return Product.objects.none()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['brand'] = getattr(self.request, 'brand', None)
        context['request'] = self.request
        return context
    
    @extend_schema(methods=['GET'], responses=PublicInventoryUnitSerializer(many=True))
    @action(detail=True, methods=['get'])
    def units(self, request, pk=None):
        """Get available units for a product with interest count."""
        # Get product by pk, bypassing queryset filters to ensure we can access any published product
        # This is important for accessories and products that might not match brand filters
        try:
            product = Product.objects.get(pk=pk, is_published=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=404)
        
        brand = getattr(request, 'brand', None)
        
        units = product.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        ).select_related('product_color', 'product_template').prefetch_related('images')
        
        if brand:
            units = units.filter(Q(brands=brand) | Q(brands__isnull=True))
        
        # Order by storage_gb to ensure consistent ordering
        units = units.order_by('storage_gb', 'selling_price')
        
        serializer = PublicInventoryUnitSerializer(units, many=True, context={'request': request, 'brand': brand})
        return Response(serializer.data)


@extend_schema_view(
    recognize=extend_schema(
        methods=['GET'],
        parameters=[
            OpenApiParameter(
                name='phone',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
            )
        ],
        responses=OpenApiTypes.OBJECT,
    ),
)
class CartViewSet(_SilkProfileMixin, viewsets.ModelViewSet):
    """Cart management."""
    serializer_class = CartSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        brand = getattr(self.request, 'brand', None)
        
        if not brand:
            return Cart.objects.none()
        
        # For list view, only show non-submitted carts
        if self.action == 'list':
            queryset = Cart.objects.filter(brand=brand, is_submitted=False)
            session_key = self.request.session.session_key or self.request.META.get('HTTP_X_SESSION_KEY', '')
            customer_phone = self.request.data.get('customer_phone') or self.request.query_params.get('phone')
            
            if customer_phone:
                queryset = queryset.filter(customer_phone=customer_phone)
            elif session_key:
                queryset = queryset.filter(session_key=session_key)
            else:
                # No session or phone - return empty for list view
                return Cart.objects.none()
            return queryset
        
        # For detail/action views (retrieve, items, checkout), allow access to submitted carts by ID
        # This allows frontend to refresh cart after checkout
        return Cart.objects.filter(brand=brand)
    
    @extend_schema(request=CartCreateSerializer, responses=CartSerializer)
    def create(self, request):
        """Create or get existing cart."""
        brand = getattr(request, 'brand', None)
        if not brand:
            # Get brand code from header for better error message
            brand_code = request.headers.get('X-Brand-Code', 'Not provided')
            return Response({
                'error': 'Brand is required',
                'detail': f'Brand code "{brand_code}" not found or inactive. Please ensure the brand exists and is active in the system.',
                'brand_code': brand_code
            }, status=status.HTTP_400_BAD_REQUEST)
        
        session_key = request.session.session_key or request.META.get('HTTP_X_SESSION_KEY', '')
        customer_phone = request.data.get('customer_phone', '')
        
        try:
            cart = CartService.get_or_create_cart(session_key, customer_phone, brand)
            serializer = self.get_serializer(cart)
            return Response(serializer.data)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error creating cart: {str(e)}', exc_info=True)
            return Response({
                'error': 'Failed to create cart',
                'detail': str(e) if settings.DEBUG else 'An error occurred while creating the cart'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    @extend_schema(request=CartItemCreateSerializer, responses=CartItemSerializer)
    def items(self, request, pk=None):
        """Add item to cart."""
        cart = self.get_object()
        inventory_unit_id = request.data.get('inventory_unit_id')
        quantity = request.data.get('quantity', 1)
        promotion_id = request.data.get('promotion_id')
        unit_price = request.data.get('unit_price')
        
        try:
            unit = InventoryUnit.objects.get(id=inventory_unit_id)
            cart_item = CartService.add_item_to_cart(
                cart, 
                unit, 
                quantity,
                promotion_id=promotion_id,
                unit_price=unit_price
            )
            serializer = CartItemSerializer(cart_item)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except InventoryUnit.DoesNotExist:
            return Response({'error': 'Inventory unit not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='bundles')
    @extend_schema(request=CartBundleCreateSerializer, responses=CartSerializer)
    def bundles(self, request, pk=None):
        """Add a bundle to cart."""
        cart = self.get_object()
        serializer = CartBundleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bundle_id = serializer.validated_data['bundle_id']
        main_unit_id = serializer.validated_data.get('main_inventory_unit_id')
        bundle_item_ids = serializer.validated_data.get('bundle_item_ids')
        if bundle_item_ids is not None and len(bundle_item_ids) == 0:
            return Response({'error': 'Select at least one bundle item'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            bundle = Bundle.objects.get(id=bundle_id)
            created_items, group_id = CartService.add_bundle_to_cart(
                cart,
                bundle,
                main_inventory_unit_id=main_unit_id,
                bundle_item_ids=bundle_item_ids
            )
            cart.refresh_from_db()
            response = CartSerializer(cart).data
            response['bundle_group_id'] = str(group_id)
            response['bundle_item_ids'] = [item.id for item in created_items]
            return Response(response, status=status.HTTP_201_CREATED)
        except Bundle.DoesNotExist:
            return Response({'error': 'Bundle not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>\\d+)')
    @extend_schema(
        parameters=[OpenApiParameter('item_id', OpenApiTypes.INT, OpenApiParameter.PATH)],
        responses=OpenApiTypes.OBJECT,
    )
    def remove_item(self, request, pk=None, item_id=None):
        """Remove one item from cart (reduce quantity by 1, or delete if quantity is 1)."""
        from inventory.models import CartItem
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            cart = self.get_object()
            logger.info(f"Removing item {item_id} from cart {cart.id}")
        except Exception as e:
            logger.error(f"Cart lookup failed: {str(e)}")
            return Response({
                'error': 'Cart not found',
                'detail': str(e) if settings.DEBUG else None
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            cart_item = CartItem.objects.get(id=item_id, cart=cart)
            
            # If quantity > 1, reduce by 1; otherwise delete the item
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
                logger.info(f"Reduced quantity of item {item_id} in cart {cart.id} to {cart_item.quantity}")
                serializer = CartItemSerializer(cart_item)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                cart_item.delete()
                logger.info(f"Item {item_id} removed from cart {cart.id} (quantity was 1)")
                return Response(status=status.HTTP_204_NO_CONTENT)
        except CartItem.DoesNotExist:
            logger.error(f"Cart item {item_id} not found in cart {cart.id}")
            return Response({
                'error': 'Cart item not found',
                'item_id': item_id,
                'cart_id': cart.id
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error removing item: {str(e)}")
            return Response({
                'error': str(e),
                'item_id': item_id,
                'cart_id': cart.id
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    @extend_schema(request=CheckoutSerializer, responses=CheckoutResponseSerializer)
    def checkout(self, request, pk=None):
        """Checkout cart (convert to Lead)."""
        import logging
        import json
        logger = logging.getLogger(__name__)
        
        # Debug: Log the raw request
        logger.info(f"Checkout request - Method: {request.method}, Content-Type: {request.content_type}")
        logger.info(f"Request data type: {type(request.data)}, Data: {request.data}")
        # Note: Cannot access request.body after DRF has parsed request.data
        
        try:
            cart = self.get_object()
            logger.info(f"Cart found: {cart.id}, brand: {cart.brand}, submitted: {cart.is_submitted}")
        except Exception as e:
            logger.error(f"Cart lookup failed: {str(e)}")
            return Response({
                'error': 'Cart not found',
                'detail': str(e) if settings.DEBUG else None,
                'cart_id': pk
            }, status=status.HTTP_404_NOT_FOUND)
        
        if cart.is_submitted:
            return Response({
                'error': 'Cart already submitted',
                'cart_id': cart.id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log received data
        logger.info(f"Checkout request data: {request.data}")
        
        # Normalize empty strings to None for optional fields
        data = dict(request.data)
        if 'customer_email' in data:
            email_value = data['customer_email']
            if email_value is None or (isinstance(email_value, str) and not email_value.strip()):
                data['customer_email'] = None
        if 'delivery_address' in data:
            address_value = data['delivery_address']
            if address_value is None or (isinstance(address_value, str) and not address_value.strip()):
                data['delivery_address'] = None
        if 'delivery_county' in data:
            county_value = data['delivery_county']
            if county_value is None or (isinstance(county_value, str) and not county_value.strip()):
                data['delivery_county'] = None
        if 'delivery_ward' in data:
            ward_value = data['delivery_ward']
            if ward_value is None or (isinstance(ward_value, str) and not ward_value.strip()):
                data['delivery_ward'] = None
        
        # Ensure required fields are present
        if 'customer_name' not in data or not data.get('customer_name'):
            return Response({
                'error': 'customer_name is required',
                'errors': {'customer_name': ['This field is required.']},
                'data_received': data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if 'customer_phone' not in data or not data.get('customer_phone'):
            return Response({
                'error': 'customer_phone is required',
                'errors': {'customer_phone': ['This field is required.']},
                'data_received': data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CheckoutSerializer(data=data)
        if not serializer.is_valid():
            logger.error(f"Serializer validation failed: {serializer.errors}")
            return Response({
                'error': 'Validation failed',
                'errors': serializer.errors,
                'data_received': data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        delivery_fee, _ = get_delivery_fee(
            serializer.validated_data.get('delivery_county'),
            serializer.validated_data.get('delivery_ward')
        )

        try:
            lead = CartService.checkout_cart(
                cart,
                serializer.validated_data['customer_name'],
                serializer.validated_data['customer_phone'],
                serializer.validated_data.get('customer_email') or None,
                serializer.validated_data.get('delivery_address') or None,
                serializer.validated_data.get('delivery_county'),
                serializer.validated_data.get('delivery_ward'),
                delivery_fee,
                serializer.validated_data.get('delivery_window_start'),
                serializer.validated_data.get('delivery_window_end'),
                serializer.validated_data.get('delivery_notes')
            )
            
            logger.info(f"Lead created successfully: {lead.lead_reference}")
            
            return Response({
                'message': 'Thank you! A salesperson will contact you shortly.',
                'lead_reference': lead.lead_reference,
                'lead': LeadSerializer(lead).data
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            logger.error(f"ValueError during checkout: {str(e)}")
            return Response({
                'error': str(e),
                'cart_id': cart.id
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            logger.error(f"Exception during checkout: {str(e)}\n{traceback.format_exc()}")
            return Response({
                'error': str(e),
                'detail': traceback.format_exc() if settings.DEBUG else 'An error occurred during checkout',
                'cart_id': cart.id
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    @extend_schema(
        methods=['GET'],
        parameters=[
            OpenApiParameter(
                name='phone',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
            )
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def recognize(self, request):
        """Check if customer is returning (by phone)."""
        phone = request.query_params.get('phone')
        if not phone:
            return Response({'error': 'Phone is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = CustomerService.recognize_customer(phone)
            return Response(result)
        except Exception as e:
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f'Error recognizing customer: {str(e)}\n{traceback.format_exc()}')
            return Response({
                'error': 'Failed to recognize customer',
                'detail': str(e) if settings.DEBUG else 'An error occurred while recognizing customer',
                'customer': None,
                'is_returning_customer': False,
                'is_returning': False,
                'message': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(request=ReviewOtpRequestSerializer, responses=OpenApiTypes.OBJECT)
class ReviewOtpView(APIView):
    """Send OTP for review verification."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ReviewOtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        result = OtpService.send_review_otp(phone)
        if not result.get("sent"):
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            if result.get("error") and "Unable to send" in result.get("error", ""):
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return Response(result, status=status_code)
        return Response(result)


@extend_schema(request=OrderOtpRequestSerializer, responses=OpenApiTypes.OBJECT)
class OrderOtpView(APIView):
    """Send OTP for order history verification."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OrderOtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']

        result = OtpService.send_order_otp(phone)
        if not result.get("sent"):
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            if result.get("error") and "Unable to send" in result.get("error", ""):
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return Response(result, status=status_code)
        return Response(result)


@extend_schema(request=OrderHistoryRequestSerializer, responses=OpenApiTypes.OBJECT)
class PublicOrderHistoryView(APIView):
    """Return orders for a customer after OTP verification."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OrderHistoryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']

        if not OtpService.verify_order_otp(phone, otp):
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        customer = Customer.objects.filter(phone=phone).first()
        if not customer:
            return Response({'orders': []})

        brand = getattr(request, 'brand', None)
        orders = (
            Order.objects
            .filter(customer=customer)
            .prefetch_related('order_items', 'order_items__inventory_unit__product_template')
            .order_by('-created_at')
        )
        if brand:
            orders = orders.filter(brand=brand)

        orders_serializer = PublicOrderSerializer(orders, many=True)
        return Response({'orders': orders_serializer.data})


@extend_schema(request=ReviewEligibilityRequestSerializer, responses=OpenApiTypes.OBJECT)
class ReviewEligibilityView(APIView):
    """Return eligible purchased items for review."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ReviewEligibilityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']

        if not OtpService.verify_review_otp(phone, otp):
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        customer = Customer.objects.filter(phone=phone).first()
        if not customer:
            return Response({'customer': None, 'eligible_items': []})

        brand = getattr(request, 'brand', None)
        order_items = (
            OrderItem.objects
            .filter(
                order__customer=customer,
                order__status__in=[Order.StatusChoices.PAID, Order.StatusChoices.DELIVERED],
                inventory_unit__product_template__isnull=False
            )
            .select_related('order', 'inventory_unit__product_template')
            .order_by('-order__created_at')
        )
        if brand:
            order_items = order_items.filter(order__brand=brand)

        eligible_items = []
        seen_products = set()
        for item in order_items:
            product = item.inventory_unit.product_template
            if not product or product.id in seen_products:
                continue
            if Review.objects.filter(customer=customer, product=product).exists():
                continue
            eligible_items.append({
                'product_id': product.id,
                'product_name': product.product_name,
                'product_slug': product.slug or '',
                'order_id': item.order.order_id,
                'order_item_id': item.id,
                'purchase_date': item.order.created_at.date() if item.order.created_at else None
            })
            seen_products.add(product.id)

        items_serializer = ReviewEligibilityItemSerializer(eligible_items, many=True)
        return Response({
            'customer': {
                'name': customer.name or '',
                'phone': customer.phone or '',
                'email': customer.email or '',
                'delivery_address': customer.delivery_address or ''
            },
            'eligible_items': items_serializer.data
        })


@extend_schema(request=PublicReviewSubmitSerializer, responses=ReviewSerializer)
class PublicReviewSubmitView(APIView):
    """Create a verified review for a purchased product."""
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = PublicReviewSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        phone = data['phone']
        otp = data['otp']
        if not OtpService.verify_review_otp(phone, otp):
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        customer = Customer.objects.filter(phone=phone).first()
        if not customer:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        order_item = (
            OrderItem.objects
            .filter(
                id=data['order_item_id'],
                order__customer=customer,
                order__status__in=[Order.StatusChoices.PAID, Order.StatusChoices.DELIVERED]
            )
            .select_related('order', 'inventory_unit__product_template')
            .first()
        )
        if not order_item or not order_item.inventory_unit:
            return Response({'error': 'Order item not found.'}, status=status.HTTP_404_NOT_FOUND)

        product = order_item.inventory_unit.product_template
        if not product or product.id != data['product_id']:
            return Response({'error': 'Order item does not match product.'}, status=status.HTTP_400_BAD_REQUEST)

        if Review.objects.filter(customer=customer, product=product).exists():
            return Response({'error': 'You have already reviewed this product.'}, status=status.HTTP_400_BAD_REQUEST)

        review_payload = {
            'product': product.id,
            'rating': data['rating'],
            'comment': data['comment'],
            'review_image': data.get('review_image'),
            'video_url': data.get('video_url')
        }

        review_serializer = ReviewSerializer(data=review_payload, context={'request': request})
        review_serializer.is_valid(raise_exception=True)
        review = review_serializer.save(customer=customer)

        if not review.purchase_date or not review.product_condition:
            update_fields = []
            if not review.purchase_date and order_item.order.created_at:
                review.purchase_date = order_item.order.created_at.date()
                update_fields.append('purchase_date')
            if not review.product_condition and order_item.inventory_unit:
                review.product_condition = order_item.inventory_unit.get_condition_display()
                update_fields.append('product_condition')
            if update_fields:
                review.save(update_fields=update_fields)

        return Response(ReviewSerializer(review, context={'request': request}).data, status=status.HTTP_201_CREATED)


@extend_schema(
    parameters=[
        OpenApiParameter('min_price', OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
        OpenApiParameter('max_price', OpenApiTypes.NUMBER, OpenApiParameter.QUERY),
        OpenApiParameter('page', OpenApiTypes.INT, OpenApiParameter.QUERY),
        OpenApiParameter('page_size', OpenApiTypes.INT, OpenApiParameter.QUERY),
    ],
    responses=PublicProductSerializer(many=True),
)
class PhoneSearchByBudgetView(generics.ListAPIView):
    """
    GET: Allows customers to search for available phone Products 
    within a specified budget range.
    Returns Products (not individual units) with price ranges.
    
    Query Params required:
    - min_price (required, decimal)
    - max_price (required, decimal)
    
    Example URL: /api/v1/public/phone-search/?min_price=15000&max_price=30000
    """
    serializer_class = PublicProductSerializer
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

        # 1. Start with published phone products
        queryset = Product.objects.filter(
            is_published=True,
            is_discontinued=False,
            product_type='PH'  # Phone products only
        )
        
        # 2. Filter products that have available units within the price range
        # Get products that have at least one unit matching the criteria
        queryset = queryset.filter(
            inventory_units__sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            inventory_units__available_online=True,
            inventory_units__selling_price__gte=min_price,
            inventory_units__selling_price__lte=max_price
        ).distinct()
        
        # 3. Filter by brand if specified (for multi-brand support)
        brand = getattr(self.request, 'brand', None)
        if brand:
            queryset = queryset.filter(
                Q(brands=brand) | Q(is_global=True) | Q(brands__isnull=True)
            ).distinct()
        
        # 4. Optimize queryset with annotations for price ranges
        queryset = queryset.annotate(
            available_units_count=Count(
                'inventory_units',
                filter=Q(
                    inventory_units__sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    inventory_units__available_online=True,
                    inventory_units__selling_price__gte=min_price,
                    inventory_units__selling_price__lte=max_price
                )
            ),
            min_price=Min(
                'inventory_units__selling_price',
                filter=Q(
                    inventory_units__sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    inventory_units__available_online=True,
                    inventory_units__selling_price__gte=min_price,
                    inventory_units__selling_price__lte=max_price
                )
            ),
            max_price=Max(
                'inventory_units__selling_price',
                filter=Q(
                    inventory_units__sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    inventory_units__available_online=True,
                    inventory_units__selling_price__gte=min_price,
                    inventory_units__selling_price__lte=max_price
                )
            )
        ).filter(available_units_count__gt=0)  # Only products with available units in range
        
        # 5. Prefetch related data for optimization
        queryset = queryset.prefetch_related(
            Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_primary=True).order_by('display_order', 'id'),
                to_attr='primary_images_list'
            )
        )
        
        return queryset.order_by('-available_units_count', 'product_name')
    
    def get_serializer_context(self):
        """Add brand context to serializer"""
        context = super().get_serializer_context()
        context['brand'] = getattr(self.request, 'brand', None)
        return context


class PublicWishlistViewSet(_SilkProfileMixin, viewsets.ModelViewSet):
    """Public wishlist API (session or customer-phone based)."""
    serializer_class = PublicWishlistItemSerializer
    permission_classes = [permissions.AllowAny]
    http_method_names = ['get', 'post', 'delete']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        context['brand'] = getattr(self.request, 'brand', None)
        return context

    def _get_customer_and_session(self, request):
        customer_phone = request.data.get('customer_phone') or request.query_params.get('customer_phone')
        session_key = (
            request.data.get('session_key')
            or request.query_params.get('session_key')
            or request.headers.get('X-Session-Key')
        )
        customer = None
        if customer_phone:
            customer = Customer.objects.filter(phone=customer_phone).first()
        return customer, session_key

    def get_queryset(self):
        customer, session_key = self._get_customer_and_session(self.request)
        brand = getattr(self.request, 'brand', None)
        queryset = WishlistItem.objects.select_related('product').order_by('-created_at')
        if brand:
            queryset = queryset.filter(Q(brand=brand) | Q(brand__isnull=True))
        if customer:
            queryset = queryset.filter(customer=customer)
        elif session_key:
            queryset = queryset.filter(session_key=session_key)
        else:
            return WishlistItem.objects.none()
        return queryset.prefetch_related(
            Prefetch(
                'product__images',
                queryset=ProductImage.objects.filter(is_primary=True),
                to_attr='primary_images_list'
            )
        )

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'detail': 'product_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(pk=int(product_id))
        except (Product.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Invalid product_id.'}, status=status.HTTP_400_BAD_REQUEST)

        customer_phone = request.data.get('customer_phone') or request.query_params.get('customer_phone')
        session_key = (
            request.data.get('session_key')
            or request.query_params.get('session_key')
            or request.headers.get('X-Session-Key')
        )
        if not customer_phone and not session_key:
            return Response({'detail': 'customer_phone or session_key is required.'}, status=status.HTTP_400_BAD_REQUEST)

        customer = None
        if customer_phone:
            customer, _ = CustomerService.get_or_create_customer(
                name='',
                phone=customer_phone,
                email=None,
                delivery_address=None
            )

        brand = getattr(self.request, 'brand', None)
        item, created = WishlistItem.objects.get_or_create(
            customer=customer,
            session_key=None if customer else session_key,
            product=product,
            brand=brand
        )
        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='by-product')
    def delete_by_product(self, request):
        product_id = request.data.get('product_id') or request.query_params.get('product_id')
        if not product_id:
            return Response({'detail': 'product_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid product_id.'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(product_id=product_id)
        queryset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicDeliveryRateViewSet(_SilkProfileMixin, viewsets.ReadOnlyModelViewSet):
    """Public delivery rates lookup."""
    serializer_class = PublicDeliveryRateSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = DeliveryRate.objects.filter(is_active=True)
        county = self.request.query_params.get('county')
        ward = self.request.query_params.get('ward')
        if county:
            queryset = queryset.filter(county__iexact=county)
        if ward:
            queryset = queryset.filter(ward__iexact=ward)
        return queryset.order_by('county', 'ward')


class PublicPromotionPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter('page_size', OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter('display_location', OpenApiTypes.STR, OpenApiParameter.QUERY),
        ]
    )
)
class PublicPromotionViewSet(_SilkProfileMixin, viewsets.ReadOnlyModelViewSet):
    def get_serializer_context(self):
        """Add request to serializer context for absolute URL building."""
        context = super().get_serializer_context()
        context['request'] = self.request
        context['brand'] = getattr(self.request, 'brand', None)
        return context
    """Public promotion ViewSet."""
    serializer_class = PublicPromotionSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = PublicPromotionPagination
    
    def get_queryset(self):
        brand = getattr(self.request, 'brand', None)
        if not brand:
            return Promotion.objects.none()
        
        # Get only currently active promotions
        from django.utils import timezone
        now = timezone.now()
        queryset = Promotion.objects.filter(
            brand=brand,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        )

        display_location_param = self.request.query_params.get('display_location')
        if display_location_param:
            locations = [
                location.strip()
                for location in display_location_param.split(',')
                if location.strip()
            ]
            if locations:
                location_query = Q(display_locations=[]) | Q(display_locations__isnull=True)
                for location in locations:
                    location_query |= Q(display_locations__contains=[location])
                queryset = queryset.filter(location_query)
        
        return queryset


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, OpenApiParameter.QUERY),
            OpenApiParameter('product', OpenApiTypes.INT, OpenApiParameter.QUERY),
        ]
    )
)
class PublicBundleViewSet(_SilkProfileMixin, viewsets.ReadOnlyModelViewSet):
    """Public bundle ViewSet."""
    serializer_class = PublicBundleSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        context['brand'] = getattr(self.request, 'brand', None)
        return context
    
    def get_queryset(self):
        brand = getattr(self.request, 'brand', None)
        if not brand:
            return Bundle.objects.none()
        
        from django.utils import timezone
        now = timezone.now()
        queryset = Bundle.objects.filter(
            brand=brand,
            is_active=True
        ).select_related('main_product').prefetch_related('items')
        
        # Date window filtering (if set)
        queryset = queryset.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now),
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        
        main_product_id = self.request.query_params.get('product')
        if main_product_id:
            queryset = queryset.filter(main_product_id=main_product_id)
        
        return queryset

