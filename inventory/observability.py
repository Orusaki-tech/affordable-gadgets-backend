"""
Observability module: Prometheus metrics, structured logging helpers, Sentry init.
"""

import os
import json
import logging
import time
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

# ── Prometheus Metrics ────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)

CACHE_HITS = Counter("cache_hits_total", "Total cache hits")
CACHE_MISSES = Counter("cache_misses_total", "Total cache misses")

ORDERS_TOTAL = Counter(
    "orders_total", "Total orders placed", ["status", "payment_method"]
)

PAYMENTS_TOTAL = Counter(
    "payments_total", "Total payment attempts", ["method", "status"]
)

ACTIVE_USERS = Gauge("active_users", "Number of active / recently-seen users")

INSTANCES_ACTIVE = Gauge("app_instances_active", "Number of Django app instances").set(1)

# ── Metrics View ────────────────────────────────────────────────────

def metrics_view(request):
    """GET /metrics/ → Prometheus scrape endpoint."""
    from django.http import HttpResponse

    return HttpResponse(
        generate_latest(REGISTRY),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )

# ── Structured Logging ────────────────────────────────────────────────


class JSONFormatter(logging.Formatter):
    """Output log records as newline-delimited JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }
        if record.exc_info and record.exc_info[0]:
            payload["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        return json.dumps(payload, default=str)


class StructLoggerAdapter(logging.LoggerAdapter):
    """Adapter that lets callers pass `extra=dict(...)` for JSON fields."""

    def process(self, msg, kwargs):
        extra_fields = kwargs.pop("extra", {})
        if isinstance(extra_fields, dict) and extra_fields:
            kwargs["extra"] = {"extra_fields": extra_fields}
        return msg, kwargs


def get_logger(name: str) -> StructLoggerAdapter:
    """Shorthand:  logger = get_logger(__name__)  then  logger.info("msg", extra={"key": val})."""
    return StructLoggerAdapter(logging.getLogger(name), {})


# ── Sentry Initialisation ──────────────────────────────────────────────


def init_sentry(dsn: str | None = None) -> bool:
    """Initialise Sentry SDK.  Return True when configured."""
    dsn = dsn or os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                DjangoIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            send_default_pii=False,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.05")),
            release=os.environ.get("RELEASE_VERSION", "unknown"),
            environment=os.environ.get("DJANGO_ENV", "development"),
        )
        return True
    except Exception as exc:
        logging.getLogger(__name__).warning("Sentry init failed: %s", exc)
        return False


# ── Timing Context Manager ─────────────────────────────────────────────


class Timer:
    """Context manager / decorator for measuring duration seconds."""

    def __init__(self):
        self.start: float | None = None
        self.elapsed: float = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.perf_counter() - (self.start or 0)
        return False

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper
