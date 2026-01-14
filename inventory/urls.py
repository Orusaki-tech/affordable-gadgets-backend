from django.urls import path, include
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


# --- 2. Define Custom GenericAPIView Paths ---

# These endpoints handle unique actions or single-object retrieval/update.
urlpatterns = [
    # IMPORTANT: Explicit routes for custom actions must come BEFORE router.urls
    # to ensure they match before the router's generic routes
    # --- Order Receipt Endpoint (Clean implementation) ---
    path('orders/<uuid:order_id>/receipt/', views.OrderReceiptView.as_view(), name='order-receipt'),
    
    # Include all generated routes from the DefaultRouter
    path('', include(router.urls)),
    
    # --- Account & Auth Endpoints ---
    path('register/', views.CustomerRegistrationView.as_view(), name='customer-register'),
    path('login/', views.CustomerLoginView.as_view(), name='customer-login'),
    path('logout/', views.CustomerLogoutView.as_view(), name='customer-logout'),

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
]
