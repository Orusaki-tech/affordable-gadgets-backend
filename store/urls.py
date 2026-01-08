from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework.authtoken import views as authtoken_views
from django.views.generic import TemplateView
from django.views.static import serve as static_serve
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from django.http import JsonResponse
from inventory import views as inventory_views

def api_root(request):
    """Root endpoint providing API information."""
    return JsonResponse({
        'name': 'Affordable Gadgets API',
        'version': '1.0.0',
        'description': 'Django REST API for Affordable Gadgets e-commerce platform',
        'endpoints': {
            'admin': '/admin/',
            'api_documentation': '/api/schema/swagger-ui/',
            'api_schema': '/api/schema/',
            'public_api': '/api/v1/public/',
            'inventory_api': '/api/inventory/',
        },
        'documentation': {
            'swagger_ui': '/api/schema/swagger-ui/',
            'redoc': '/api/schema/redoc/',
            'openapi_schema': '/api/schema/',
        }
    })

urlpatterns = [
    # 0. Root endpoint
    path('', api_root, name='api-root'),
    
    # 1. Django Admin Interface
    path('admin/', admin.site.urls),
    path('api/auth/token/login/', inventory_views.AdminTokenLoginView.as_view()),

    # 2. Authentication Endpoints (Placeholder for user login, registration, etc.)
    # In a real-world scenario, you would use a library like Djoser or built-in DRF Auth views.
    path('api/auth/', include('rest_framework.urls')), 

    # 3. Primary Inventory API Module
    # All inventory-related endpoints start with 'api/inventory/'
    path('api/inventory/', include('inventory.urls')),
    
    # 4. Public E-commerce API
    # Public endpoints for e-commerce frontends
    path('api/v1/public/', include('inventory.urls_public')), 

    # 4. API Documentation (drf-spectacular generated)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # 5. Legacy API Documentation (ReDoc - using static file)
    path('api/docs/', TemplateView.as_view(template_name='redoc.html'), name='api-docs'),

    # 6. Serve OpenAPI file (development convenience - can be auto-generated)
    re_path(r'^openapi\.yaml$', lambda request: static_serve(request, 'openapi.yaml', document_root=settings.BASE_DIR)),
]

# Serve media files in development (Cloudinary handles in production)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
