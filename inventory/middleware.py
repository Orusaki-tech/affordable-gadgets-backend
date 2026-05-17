"""
Middleware for brand context, request timing, structured logging, and Prometheus instrumentation.
"""

import logging
import threading
import time
from re import compile as re_compile
from uuid import uuid4

# Active user tracking: {user_id: last_seen_timestamp}
# Process-local; Prometheus sums across workers for a reasonable approximation.
_ACTIVE_USERS: dict[int, float] = {}
_ACTIVE_USER_TTL = 300  # 5 minutes

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# ── Structured logging context ────────────────────────────────────────

_request_context = threading.local()


class RequestContextFilter(logging.Filter):
    """Injects request context (request_id, user_id, brand, etc.) into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = getattr(_request_context, "current", None)
        record.request_id = ctx.get("request_id") if ctx else None
        record.user_id = ctx.get("user_id") if ctx else None
        record.brand_code = ctx.get("brand_code") if ctx else None
        record.method = ctx.get("method") if ctx else None
        record.path = ctx.get("path") if ctx else None
        return True


class LogContextMiddleware:
    """Attaches request_id, user_id, brand to every structured log record for this request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid4())
        _request_context.current = {
            "request_id": request.request_id,
            "method": request.method,
            "path": request.path_info,
        }

        response = self.get_response(request)

        ctx = _request_context.current
        if ctx:
            if getattr(request, "user", None) and request.user.is_authenticated:
                ctx["user_id"] = request.user.id
            if getattr(request, "brand", None):
                ctx["brand_code"] = request.brand.code
            logger.info("request_completed", extra={"extra_fields": {
                "status_code": response.status_code,
            }})

        _request_context.current = None
        return response

_loading_brand = threading.local()


def _purge_stale_users():
    """Remove users whose last activity exceeds the TTL."""
    now = time.time()
    stale = [uid for uid, ts in list(_ACTIVE_USERS.items()) if now - ts > _ACTIVE_USER_TTL]
    for uid in stale:
        _ACTIVE_USERS.pop(uid, None)


def refresh_active_users_metric():
    """Set the active_users Prometheus gauge (called from metrics_view)."""
    _purge_stale_users()
    try:
        from inventory.observability import ACTIVE_USERS
        ACTIVE_USERS.set(len(_ACTIVE_USERS))
    except Exception:
        pass


# Patterns to normalise URL paths for metrics labels
_PATH_PARAM_PATTERN = re_compile(r"/\d+/")
_PATH_UUID_PATTERN = re_compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/"
)


def _normalise_path(path: str) -> str:
    """Replace dynamic segments (IDs, UUIDs) with placeholders for metric labels."""
    p = _PATH_UUID_PATTERN.sub("/:id/", path)
    p = _PATH_PARAM_PATTERN.sub("/:id/", p)
    return p


class RequestTimingMiddleware(MiddlewareMixin):
    """
    Record Django processing time; optionally emit Prometheus metrics.
    Adds X-Processing-Ms to every response.
    """

    def process_request(self, request):
        request._timing_start = time.perf_counter()
        return None

    def process_response(self, request, response):
        if not hasattr(request, "_timing_start"):
            return response

        ms = int((time.perf_counter() - request._timing_start) * 1000)
        response["X-Processing-Ms"] = str(ms)

        # Prometheus metrics
        self._record_metrics(request, response, ms)
        return response

    def _record_metrics(self, request, response, ms: int):
        try:
            from inventory.observability import (
                HTTP_REQUESTS_TOTAL,
                HTTP_REQUEST_DURATION_SECONDS,
            )

            method = request.method or "GET"
            endpoint = _normalise_path(request.path_info)
            status = str(response.status_code)

            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(ms / 1000)

            # Track authenticated users
            if getattr(request, "user", None) and request.user.is_authenticated:
                _ACTIVE_USERS[request.user.id] = time.time()
        except Exception:
            logger.debug("Failed to record Prometheus metrics", exc_info=True)


class BrandContextMiddleware(MiddlewareMixin):
    """
    Middleware to set brand context from X-Brand-Code header.
    Falls back to the default brand (AFFORDABLE_GADGETS) when no header is provided.
    Sets request.brand to the Brand instance if found and active.
    """

    DEFAULT_BRAND_CODE = "AFFORDABLE_GADGETS"

    def process_request(self, request):
        """Set brand context from X-Brand-Code header."""
        brand_code = request.headers.get("X-Brand-Code", "").strip()
        request.brand = None

        if not brand_code:
            brand_code = self.DEFAULT_BRAND_CODE

        # Avoid re-entrancy: if we're already loading brand (e.g. import/ORM triggered middleware again), skip
        if getattr(_loading_brand, "active", False):
            return None

        _loading_brand.active = True
        try:
            from inventory.models import Brand

            brand = Brand.objects.filter(code=brand_code, is_active=True).first()
            if not brand and brand_code == self.DEFAULT_BRAND_CODE:
                brand, _ = Brand.objects.get_or_create(
                    code=self.DEFAULT_BRAND_CODE,
                    defaults={"name": "Affordable Gadgets KE", "is_active": True},
                )
            if brand:
                request.brand = brand
        except RecursionError:
            logger.warning(
                "Error loading brand '%s': maximum recursion depth exceeded (re-entrancy guard will prevent repeat)",
                brand_code,
            )
        except Exception as e:
            logger.warning(f"Error loading brand '{brand_code}': {e}")
        finally:
            _loading_brand.active = False

        return None
