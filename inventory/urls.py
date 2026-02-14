from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from . import views

# Initialize the DefaultRouter
# The router automatically generates URL patterns for your ViewSets
router = DefaultRouter()

# --- 1. Register ModelViewSets (CRUD Endpoints) ---

# Core Inventory and Catalog Endpoints (Read-Only/Admin)
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'images', views.ProductImageViewSet, basename='product-image')
router.register(r'unit-images', views.InventoryUnitImageViewSet, basename='unit-image')
router.register(r'units', views.InventoryUnitViewSet, basename='inventory-unit') # Admin-only

# Sales and Reviews Endpoints (Mixed Permissions)
router.register(r'reviews', views.ReviewViewSet, basename='review')
router.register(r'orders', views.OrderViewSet, basename='order') # Customer-filtered
router.register(r'order-items', views.OrderItemViewSet, basename='order-item') # Admin-only
router.register(r'delivery-rates', views.DeliveryRateViewSet, basename='delivery-rate')

# Lookup Tables Endpoints (Read-Only/Admin)
router.register(r'colors', views.ColorViewSet, basename='color')
router.register(r'sources', views.UnitAcquisitionSourceViewSet, basename='acquisition-source')
router.register(r'accessories-link', views.ProductAccessoryViewSet, basename='product-accessory')
router.register(r'tags', views.TagViewSet, basename='tag')

# Admin Management Endpoints (Admin-only)
router.register(r'admin-roles', views.AdminRoleViewSet, basename='admin-role')
router.register(r'admins', views.AdminViewSet, basename='admin')

# Request Management Endpoints
router.register(r'reservation-requests', views.ReservationRequestViewSet, basename='reservation-request')
router.register(r'return-requests', views.ReturnRequestViewSet, basename='return-request')
router.register(r'unit-transfers', views.UnitTransferViewSet, basename='unit-transfer')
router.register(r'notifications', views.NotificationViewSet, basename='notification')

# Inventory Manager Tools
router.register(r'reports', views.ReportsViewSet, basename='reports')
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-logs')
router.register(r'stock-alerts', views.StockAlertsViewSet, basename='stock-alerts')

# Brand & Lead Management
router.register(r'brands', views.BrandViewSet, basename='brand')
router.register(r'leads', views.LeadViewSet, basename='lead')
router.register(r'promotion-types', views.PromotionTypeViewSet, basename='promotion-type')
router.register(r'promotions', views.PromotionViewSet, basename='promotion')
router.register(r'bundles', views.BundleViewSet, basename='bundle')
router.register(r'bundle-items', views.BundleItemViewSet, basename='bundle-item')


# --- 2. Define Custom GenericAPIView Paths ---

# These endpoints handle unique actions or single-object retrieval/update.
# Create receipt pattern before urlpatterns
# Use re_path with strict regex to ensure it matches before router patterns
# Pattern: orders/{uuid}/receipt/ (must match exactly, no trailing variations)
receipt_pattern = re_path(
    r'^orders/(?P<order_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/receipt/$',
    views.OrderReceiptView.as_view(),
    name='order-receipt'
)

# Bulk-destroy must be registered before router so it isn't matched as detail pk="bulk-destroy"
product_bulk_destroy = path(
    'products/bulk-destroy/',
    views.ProductViewSet.as_view({'post': 'bulk_destroy'}),
    name='product-bulk-destroy',
)

urlpatterns = [
    # IMPORTANT: Explicit routes for custom actions must come BEFORE router.urls
    # to ensure they match before the router's generic routes
    # --- Order Receipt Endpoint (Clean implementation) ---
    receipt_pattern,
    product_bulk_destroy,
    # Include all generated routes from the DefaultRouter
    path('', include(router.urls)),
    
    # --- Account & Auth Endpoints ---
    path('register/', views.CustomerRegistrationView.as_view(), name='customer-register'),
    path('login/', views.CustomerLoginView.as_view(), name='customer-login'),
    path('logout/', views.CustomerLogoutView.as_view(), name='customer-logout'),
    path('verify-email/', views.CustomerEmailVerificationView.as_view(), name='customer-verify-email'),
    path('verify-email/resend/', views.CustomerResendVerificationView.as_view(), name='customer-verify-email-resend'),

    # Profile Endpoints (Read/Update authenticated user's profile)
    path('profiles/customer/', views.CustomerProfileView.as_view(), name='customer-profile'),
    path('profiles/admin/', views.AdminProfileView.as_view(), name='admin-profile'),

    # --- Discovery & Search Endpoints (Public access) ---
    # ADDED: Allows customers to search for available inventory units based on a budget range.
    path('phone-search/', views.PhoneSearchByBudgetView.as_view(), name='phone-search-budget'),

    # Utility Endpoint (Public access for price calculation)
    path('utils/discount-calculator/', views.DiscountCalculatorView.as_view(), name='discount-calculator'),
    # Public available units (global discovery)
    path('units/available/', views.PublicAvailableUnitsView.as_view(), name='public-available-units'),
    
    # --- Pesapal Payment Endpoints ---
    path('pesapal/ipn/', views.PesapalIPNView.as_view(), name='pesapal-ipn'),
    
    # --- Admin Utility Endpoints ---
    path('admin/fix-product-visibility/', views.FixProductVisibilityView.as_view(), name='fix-product-visibility'),
]
