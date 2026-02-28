"""
Middleware for brand context and request timing (cold start vs in-app time).
"""

import logging
import time

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(MiddlewareMixin):
    """
    Record when the request first hits Django and add X-Processing-Ms to the response.
    Use this to tell cold start from slow query:
    - Browser "Waiting for server response" = total TTFB (cold start + Django).
    - X-Processing-Ms = time spent inside Django only.
    - Cold start ≈ TTFB - X-Processing-Ms (time before Django received the request).
    """

    def process_request(self, request):
        request._timing_start = time.perf_counter()
        return None

    def process_response(self, request, response):
        if hasattr(request, "_timing_start"):
            ms = int((time.perf_counter() - request._timing_start) * 1000)
            response["X-Processing-Ms"] = str(ms)
        return response


class BrandContextMiddleware(MiddlewareMixin):
    """
    Middleware to set brand context from X-Brand-Code header.
    Sets request.brand to the Brand instance if found and active.
    """

    def process_request(self, request):
        """Set brand context from X-Brand-Code header."""
        from inventory.models import Brand

        brand_code = request.headers.get("X-Brand-Code", "").strip()
        request.brand = None

        if brand_code:
            try:
                brand = Brand.objects.filter(code=brand_code, is_active=True).first()
                if brand:
                    request.brand = brand
            except Exception as e:
                logger.warning(f"Error loading brand '{brand_code}': {e}")

        return None
