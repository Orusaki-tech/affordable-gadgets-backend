"""Public API URLs for e-commerce frontend."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views_public
from . import views

router = DefaultRouter()
router.register(r'products', views_public.PublicProductViewSet, basename='public-product')
router.register(r'cart', views_public.CartViewSet, basename='public-cart')
router.register(r'promotions', views_public.PublicPromotionViewSet, basename='public-promotion')
router.register(r'bundles', views_public.PublicBundleViewSet, basename='public-bundle')
# Add accessories endpoint (read-only for public)
router.register(r'accessories-link', views.ProductAccessoryViewSet, basename='public-accessory')
# Add reviews endpoint (read-only for public)
router.register(r'reviews', views.ReviewViewSet, basename='public-review')

urlpatterns = [
    path('', include(router.urls)),
    # Budget search endpoint
    path('phone-search/', views_public.PhoneSearchByBudgetView.as_view(), name='public-phone-search-budget'),
]

