"""
Middleware for brand context and URL resolution debugging.
"""
import json
import time
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


class URLResolutionDebugMiddleware:
    """
    Middleware to debug URL resolution for receipt endpoint.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # #region agent log
        if 'receipt' in request.path:
            # NOTE: Render logs often don't show structured "extra", so embed key fields in the message.
            logger.info(
                f"DEBUG[A] middleware: receipt request detected "
                f"path={request.path} method={request.method} full_path={request.get_full_path()}",
                extra={'hypothesisId': 'A', 'location': 'inventory/middleware.py:__call__'},
            )
        # #endregion
        
        response = self.get_response(request)
        
        # #region agent log
        if 'receipt' in request.path:
            resolver_match = getattr(request, 'resolver_match', None)
            matched = 'YES' if resolver_match else 'NO'
            route = (resolver_match.route[:50] + '...') if resolver_match and resolver_match.route else 'NONE'
            url_name = resolver_match.url_name if resolver_match else 'NONE'
            # Short log message so key info shows in Render
            logger.info(f"DEBUG[A] after_resolution matched={matched} route={route} url_name={url_name} status={response.status_code}")
        # #endregion
        
        return response
