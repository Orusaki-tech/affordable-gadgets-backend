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
router.register(r'wishlist', views_public.PublicWishlistViewSet, basename='public-wishlist')
router.register(r'delivery-rates', views_public.PublicDeliveryRateViewSet, basename='public-delivery-rate')
# Add accessories endpoint (read-only for public)
router.register(r'accessories-link', views.ProductAccessoryViewSet, basename='public-accessory')
# Add reviews endpoint (read-only for public)
router.register(r'reviews', views.ReviewViewSet, basename='public-review')

urlpatterns = [
    path('reviews/otp/', views_public.ReviewOtpView.as_view(), name='public-review-otp'),
    path('reviews/eligibility/', views_public.ReviewEligibilityView.as_view(), name='public-review-eligibility'),
    path('reviews/submit/', views_public.PublicReviewSubmitView.as_view(), name='public-review-submit'),
    path('', include(router.urls)),
    # Budget search endpoint
    path('phone-search/', views_public.PhoneSearchByBudgetView.as_view(), name='public-phone-search-budget'),
]

