"""Middleware for brand context."""
from inventory.models import Brand
import logging

logger = logging.getLogger(__name__)


class BrandContextMiddleware:
    """Extract brand from request."""
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        brand_code = None
        brand = None
        
        # Priority 1: Header
        if 'X-Brand-Code' in request.headers:
            brand_code = request.headers['X-Brand-Code']
        
        # Priority 2: Domain-based detection
        elif request.get_host():
            host = request.get_host()
            # Remove port if present
            host = host.split(':')[0]
            
            try:
                # Try to match by ecommerce_domain (exact or contains)
                brand = Brand.objects.filter(
                    ecommerce_domain__icontains=host,
                    is_active=True
                ).first()
                
                if brand:
                    brand_code = brand.code
                    logger.debug(f'Brand detected from domain: {host} -> {brand_code}')
            except Exception as e:
                logger.warning(f'Error detecting brand from domain {host}: {str(e)}')
        
        # Priority 3: Query parameter
        if not brand_code and 'brand' in request.GET:
            brand_code = request.GET.get('brand')
        
        # Resolve brand from code
        if brand_code:
            try:
                request.brand = Brand.objects.get(code=brand_code, is_active=True)
            except Brand.DoesNotExist:
                # Log warning with more details
                logger.warning(
                    f'Brand code "{brand_code}" not found or inactive. '
                    f'Available brands: {list(Brand.objects.filter(is_active=True).values_list("code", flat=True))}'
                )
                request.brand = None
            except Brand.MultipleObjectsReturned:
                # Shouldn't happen due to unique constraint, but handle it
                logger.error(f'Multiple brands found with code "{brand_code}"')
                request.brand = Brand.objects.filter(code=brand_code, is_active=True).first()
        else:
            request.brand = None
        
        return self.get_response(request)

