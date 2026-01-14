"""
Middleware for brand context.
"""
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class BrandContextMiddleware(MiddlewareMixin):
    """
    Middleware to set brand context from X-Brand-Code header.
    Sets request.brand to the Brand instance if found and active.
    """
    def process_request(self, request):
        """Set brand context from X-Brand-Code header."""
        from inventory.models import Brand
        
        brand_code = request.headers.get('X-Brand-Code', '').strip()
        request.brand = None
        
        if brand_code:
            try:
                brand = Brand.objects.filter(code=brand_code, is_active=True).first()
                if brand:
                    request.brand = brand
            except Exception as e:
                logger.warning(f"Error loading brand '{brand_code}': {e}")
        
        return None
