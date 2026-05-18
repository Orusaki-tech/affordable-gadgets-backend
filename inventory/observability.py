"""
Observability module: Prometheus metrics, structured logging helpers, Sentry init.
"""

import os
import json
import logging
import time
from functools import wraps
from threading import Lock

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

# ── Prometheus Metrics ────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ["method", "endpoint", "status_code", "brand"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "brand"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

ORDERS_TOTAL = Counter(
    "orders_total", "Total orders placed", ["status", "payment_method", "brand"]
)

PAYMENTS_TOTAL = Counter(
    "payments_total", "Total payment attempts", ["method", "status", "brand"]
)

ACTIVE_USERS = Gauge("active_users", "Number of active / recently-seen users")

INSTANCES_ACTIVE = Gauge("app_instances_active", "Number of Django app instances")
INSTANCES_ACTIVE.set(1)

# ── Business Metrics ────────────────────────────────────────────────────

REVENUE_TOTAL = Gauge(
    "revenue_total",
    "Total revenue from completed payments",
    ["brand", "product_type"],
)

GROSS_MARGIN_TOTAL = Gauge(
    "gross_margin_total",
    "Gross margin (revenue - cost of goods sold)",
    ["brand", "product_type"],
)

LEADS_TOTAL = Gauge(
    "leads_total",
    "Total leads count by status",
    ["brand", "status"],
)

LEAD_CONVERSION_TOTAL = Gauge(
    "lead_conversion_total",
    "Total lead conversions",
    ["brand"],
)

CARTS_TOTAL = Gauge(
    "carts_total",
    "Total carts by status",
    ["brand", "status"],
)

CUSTOMERS_TOTAL = Gauge(
    "customers_total",
    "Total customers registered",
    ["brand"],
)

INVENTORY_VALUE = Gauge(
    "inventory_value_total",
    "Total inventory value by status",
    ["brand", "status"],
)

DELIVERY_SLA_TOTAL = Gauge(
    "delivery_sla_total",
    "Delivery SLA (on-time vs late)",
    ["brand", "result"],
)

SALESPERSON_TOTAL = Gauge(
    "salesperson_performance_total",
    "Salesperson performance metrics",
    ["brand", "salesperson", "metric"],
)

# ── Gauge Refresh ────────────────────────────────────────────────────────

_last_refresh = 0.0
_refresh_lock = Lock()
_REFRESH_COOLDOWN = 60  # seconds — max once per 60s per worker


def refresh_business_metrics():
    """Refresh business metric gauges from the database.
    
    Rate-limited to once per 60 seconds per worker process.
    Reuses existing queries from reports.py where possible.
    """
    global _last_refresh
    now = time.time()
    if now - _last_refresh < _REFRESH_COOLDOWN:
        return
    if not _refresh_lock.acquire(blocking=False):
        return
    try:
        _last_refresh = now
        from django.db.models import Sum, Count, Q, F, DecimalField
        from django.db.models.functions import Coalesce
        from decimal import Decimal
        from inventory.models import (
            Brand, Order, Cart, Customer, Lead,
            InventoryUnit, PesapalPayment, Product,
        )

        brand_codes = list(Brand.objects.filter(is_active=True).values_list("code", flat=True))
        if not brand_codes:
            brand_codes = ["AFFORDABLE_GADGETS"]

        for bc in brand_codes:
            # Resolve brand name for Product.brand (CharField, not FK)
            try:
                brand_name = Brand.objects.get(code=bc).name
            except Brand.DoesNotExist:
                brand_name = bc.title()

            # Revenue from COMPLETED payments
            rev = (
                PesapalPayment.objects.filter(
                    order__brand__code=bc, status="COMPLETED"
                ).aggregate(total=Coalesce(Sum("amount"), Decimal("0")))["total"]
            )
            REVENUE_TOTAL.labels(brand=bc, product_type="all").set(float(rev))

            # Gross margin: revenue - cost of goods sold for SOLD units
            sold_cost = (
                InventoryUnit.objects.filter(
                    sale_status="SD", product_template__brand=brand_name
                ).aggregate(total=Coalesce(Sum("cost_of_unit"), Decimal("0")))["total"]
            )
            sold_revenue = (
                InventoryUnit.objects.filter(
                    sale_status="SD", product_template__brand=brand_name
                ).aggregate(total=Coalesce(Sum("selling_price"), Decimal("0")))["total"]
            )
            margin = float(sold_revenue) - float(sold_cost)
            GROSS_MARGIN_TOTAL.labels(brand=bc, product_type="all").set(margin)

            # Leads by status
            for status_code in ["NEW", "CONTACTED", "CONVERTED", "CLOSED", "EXPIRED"]:
                cnt = Lead.objects.filter(brand__code=bc, status=status_code).count()
                LEADS_TOTAL.labels(brand=bc, status=status_code).set(cnt)

            # Lead conversions
            conv_cnt = Lead.objects.filter(brand__code=bc, status="CONVERTED").count()
            LEAD_CONVERSION_TOTAL.labels(brand=bc).set(conv_cnt)

            # Carts by status
            all_carts = Cart.objects.filter(brand__code=bc).count()
            submitted = Cart.objects.filter(brand__code=bc, is_submitted=True).count()
            CARTS_TOTAL.labels(brand=bc, status="total").set(all_carts)
            CARTS_TOTAL.labels(brand=bc, status="submitted").set(submitted)

            # Customers
            cust_cnt = Customer.objects.filter(
                Q(orders__brand__code=bc) | Q(lead__brand__code=bc)
            ).distinct().count()
            CUSTOMERS_TOTAL.labels(brand=bc).set(cust_cnt)

            # Inventory value by status
            for status_code in ["AV", "SD", "RS", "RT", "PP"]:
                val = (
                    InventoryUnit.objects.filter(
                        sale_status=status_code, product_template__brand=brand_name
                    ).aggregate(total=Coalesce(Sum("selling_price"), Decimal("0")))["total"]
                )
                INVENTORY_VALUE.labels(brand=bc, status=status_code).set(float(val))

            # Delivery SLA
            delivered_orders = Order.objects.filter(
                brand__code=bc, status="Delivered"
            )
            total_delivered = delivered_orders.count()
            on_time = delivered_orders.filter(
                delivered_at__lte=F("delivery_window_end")
            ).count() if hasattr(Order, "delivered_at") else 0
            late = total_delivered - on_time
            DELIVERY_SLA_TOTAL.labels(brand=bc, result="on_time").set(on_time)
            DELIVERY_SLA_TOTAL.labels(brand=bc, result="late").set(late)

            # Salesperson performance
            from inventory.reports import get_salesperson_performance
            perf = get_salesperson_performance(days=30)
            for sp in perf:
                sp_name = sp.get("salesperson_name", "unknown")
                SALESPERSON_TOTAL.labels(
                    brand=bc, salesperson=sp_name, metric="reservations_requested"
                ).set(sp.get("reservations_requested", 0))
                SALESPERSON_TOTAL.labels(
                    brand=bc, salesperson=sp_name, metric="reservations_approved"
                ).set(sp.get("reservations_approved", 0))
                SALESPERSON_TOTAL.labels(
                    brand=bc, salesperson=sp_name, metric="approval_rate"
                ).set(sp.get("approval_rate", 0))
    except Exception:
        logger = logging.getLogger(__name__)
        logger.debug("Failed to refresh business metrics", exc_info=True)
    finally:
        _refresh_lock.release()


# ── Metrics View ────────────────────────────────────────────────────

def metrics_view(request):
    """GET /metrics/ → Prometheus scrape endpoint."""
    from django.http import HttpResponse

    try:
        from inventory.middleware import refresh_active_users_metric
        refresh_active_users_metric()
    except Exception:
        pass

    try:
        refresh_business_metrics()
    except Exception:
        pass

    return HttpResponse(
        generate_latest(REGISTRY),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )

# ── Structured Logging ────────────────────────────────────────────────


_REQUEST_FIELDS = ("request_id", "user_id", "brand_code", "method", "path")


class JSONFormatter(logging.Formatter):
    """Output log records as newline-delimited JSON.

    Includes request context fields (request_id, user_id, brand_code, method, path)
    when the RequestContextFilter is active.
    """

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
        for field in _REQUEST_FIELDS:
            val = getattr(record, field, None)
            if val is not None:
                payload[field] = val
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


# ── OpenTelemetry Initialisation ────────────────────────────────────────


def init_opentelemetry() -> bool:
    """Initialise OpenTelemetry tracing (export to GCP Cloud Trace).

    Environment variables:
      OTEL_ENABLED          — set to "true" to enable (default: true)
      OTEL_SERVICE_NAME     — service name in traces (default: "ag-api")
      OTEL_SAMPLE_RATE      — trace sample rate 0-1 (default: 0.1)
    """
    if os.environ.get("OTEL_ENABLED", "true").lower() != "true":
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.gcp_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        project_id = os.environ.get(
            "OTEL_GCP_PROJECT_ID"
        ) or os.environ.get("GOOGLE_CLOUD_PROJECT")
        service_name = os.environ.get("OTEL_SERVICE_NAME", "ag-api")
        sample_rate = float(os.environ.get("OTEL_SAMPLE_RATE", "0.1"))

        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name}),
            sampler=trace.sampling.ParentBased(
                trace.sampling.TraceIdRatioBased(sample_rate)
            ),
        )
        exporter = CloudTraceSpanExporter(project_id=project_id)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        return True
    except Exception as exc:
        logging.getLogger(__name__).warning("OpenTelemetry init failed: %s", exc)
        return False


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
