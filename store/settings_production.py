"""
Production settings for Django store project.
This file contains production-specific configurations.
IMPORTANT: This file imports from .settings, so it must be imported AFTER base settings are defined.
"""

import os
from urllib.parse import parse_qsl, urlparse

from store.database_urls import database_config_from_url

from .settings import *  # noqa: F403 - Import all base settings first

# Security settings
DEBUG = False
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set in production")

# Parse ALLOWED_HOSTS from environment variable
ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("ALLOWED_HOSTS", "").split(",") if host.strip()
]

# Automatically add Render domain if RENDER_EXTERNAL_HOSTNAME is set (Render provides this)
# This is the actual hostname Render assigns to your service
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

# If ALLOWED_HOSTS is still empty, raise an error
if not ALLOWED_HOSTS:
    raise ValueError(
        "ALLOWED_HOSTS environment variable must be set in production. "
        "On Render, you can set it to your service domain (e.g., affordable-gadgets-backend.onrender.com) "
        "or it will be auto-detected from RENDER_EXTERNAL_HOSTNAME if available."
    )

# Frontend URL used in outbound emails (verification/reset/payment redirects).
# In production this must always be an explicit public HTTPS URL.
frontend_base_url = os.environ.get("FRONTEND_BASE_URL", "").strip()
if not frontend_base_url:
    raise ValueError("FRONTEND_BASE_URL environment variable must be set in production")
if "localhost" in frontend_base_url or "127.0.0.1" in frontend_base_url:
    raise ValueError("FRONTEND_BASE_URL cannot point to localhost/127.0.0.1 in production")
FRONTEND_BASE_URL = frontend_base_url.rstrip("/")

# Database (use PostgreSQL in production)
# Support both DATABASE_URL (Render/Heroku style) and individual DB_* variables
database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url:
    # Parse DATABASE_URL: postgresql://user:password@host:port/dbname
    # or postgres://user:password@host:port/dbname
    try:
        parsed = urlparse(database_url)
        # Carry URL query params (e.g. ?sslmode=require) into Django DB OPTIONS.
        db_options = {
            "connect_timeout": 10,
            "statement_timeout": int(os.environ.get("DB_STATEMENT_TIMEOUT", "30000")),
        }
        for key, value in parse_qsl(parsed.query, keep_blank_values=False):
            db_options[key] = value

        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": parsed.path[1:],  # Remove leading '/'
                "USER": parsed.username,
                "PASSWORD": parsed.password,
                "HOST": parsed.hostname,
                "PORT": parsed.port or "5432",
                "CONN_MAX_AGE": int(os.environ.get("CONN_MAX_AGE", "300") or "300"),
                "OPTIONS": db_options,
            }
        }
    except Exception as e:
        # Fall back to individual variables if DATABASE_URL parsing fails
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to parse DATABASE_URL: {e}. Falling back to individual DB_* variables."
        )
        database_url = None

if not database_url:
    # Use individual environment variables
    db_host = os.environ.get("DB_HOST", "localhost")

    # Extract hostname if DB_HOST contains a full URL or connection string
    # Handle cases like: "postgresql://user:pass@host:port/db" or just "hostname"
    if "://" in db_host or "@" in db_host:
        # It's a URL, try to parse it
        try:
            parsed = urlparse(db_host if "://" in db_host else f"postgresql://{db_host}")
            db_host = (
                parsed.hostname or db_host.split("@")[-1].split(":")[0]
                if "@" in db_host
                else db_host
            )
        except Exception:
            # If parsing fails, try to extract hostname manually
            if "@" in db_host:
                db_host = db_host.split("@")[-1].split(":")[0]
            elif ":" in db_host and not db_host.startswith("postgres"):
                db_host = db_host.split(":")[0]

    # Clean up hostname - remove any trailing slashes, paths, or invalid characters (like parentheses)
    db_host = db_host.strip().rstrip("/").rstrip(")").rstrip("(").split("/")[0].split("?")[0]

    # Default sslmode: require for remote hosts, disable for local
    _local_hosts = ("localhost", "127.0.0.1", "0.0.0.0")
    _sslmode = "disable" if db_host in _local_hosts else os.environ.get("DB_SSLMODE", "require")

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME"),
            "USER": os.environ.get("DB_USER"),
            "PASSWORD": os.environ.get("DB_PASSWORD"),
            "HOST": db_host,
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("CONN_MAX_AGE", "300") or "300"),
            "OPTIONS": {
                "connect_timeout": 10,
                "sslmode": _sslmode,
                "statement_timeout": int(os.environ.get("DB_STATEMENT_TIMEOUT", "30000")),
            },
        }
    }

# Cloud SQL clone / backup for merge_from_restore_db and audit_blog_recovery.
_restore_url = os.environ.get("RESTORE_DATABASE_URL", "").strip()
if _restore_url:
    DATABASES["restore"] = database_config_from_url(  # noqa: F405
        _restore_url, conn_max_age=int(os.environ.get("CONN_MAX_AGE", "300") or "300")
    )

# Static files (use Cloudinary for production)
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # noqa: F405

# For production with Silk enabled, use local filesystem for static files
# This ensures Silk's UI renders correctly. Cloudinary CDN is still used for media files.
# If Silk is not enabled, use Cloudinary for static files (CDN benefits)
# Note: SILKY_ENABLED is imported from base settings via 'from .settings import *'
if SILKY_ENABLED:  # noqa: F405
    # Use local filesystem storage when Silk is enabled (ensures Silk UI works)
    # Static files will be served directly via the URL pattern in urls.py
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    # Use Cloudinary for all static files if Silk is not enabled (CDN benefits)
    STATICFILES_STORAGE = "cloudinary_storage.storage.StaticCloudinaryStorage"

# Media files (use Cloudinary - explicitly ensure it's set)
MEDIA_URL = "/media/"
# Ensure Cloudinary is used for all media file uploads
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# CSRF: in production, trust only HTTPS origins (override dev list from base settings).
# Set CSRF_TRUSTED_ORIGINS env to e.g. https://api.example.com,https://admin.example.com
_csrf_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(",") if o.strip()]
if not CSRF_TRUSTED_ORIGINS and render_hostname:
    CSRF_TRUSTED_ORIGINS = [f"https://{render_hostname}"]
if FRONTEND_BASE_URL and FRONTEND_BASE_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(FRONTEND_BASE_URL)
for _origin in ("https://www.affordable-gadgetske.com", "https://affordable-gadgetske.com"):
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)

# Security headers
# When behind a reverse proxy that terminates SSL (e.g. Railway, Render), trust X-Forwarded-Proto
# so Django does not redirect HTTP->HTTPS on every request (avoids ERR_TOO_MANY_REDIRECTS).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Default to False on Railway: the edge already serves HTTPS; enabling redirect can cause
# ERR_TOO_MANY_REDIRECTS if X-Forwarded-Proto is missing on some requests (e.g. from browser).
_ssl_redirect = os.environ.get("SECURE_SSL_REDIRECT", "").lower()
if _ssl_redirect == "" and os.environ.get("RAILWAY_ENVIRONMENT"):
    SECURE_SSL_REDIRECT = False
else:
    SECURE_SSL_REDIRECT = _ssl_redirect != "false" and _ssl_redirect != "0"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS settings (restrict in production)
# Must include both frontend domains:
# 1. E-commerce frontend (shwari-phones/Next.js)
# 2. Admin frontend (inventory-management-frontend/React)
# Format: https://domain1.com,https://domain2.com
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]

# If CORS_ALLOWED_ORIGINS is not provided, default to known production domains.
# This prevents a deploy misconfig from silently breaking the storefront.
_default_cors = {
    "https://www.affordable-gadgetske.com",
    "https://affordable-gadgetske.com",
}
if FRONTEND_BASE_URL:
    _default_cors.add(FRONTEND_BASE_URL)
if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = sorted(_default_cors)
else:
    # Ensure storefront domains are always present.
    CORS_ALLOWED_ORIGINS = sorted(set(CORS_ALLOWED_ORIGINS).union(_default_cors))

# Allow Vercel preview deployments (dynamic URLs) and production custom domain
# Vercel preview URLs follow pattern: https://*-git-*-*-*.vercel.app
# Production URLs: https://*.vercel.app, https://www.affordable-gadgetske.com
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*-git-.*-.*-.*\.vercel\.app$",
    r"^https://affordable-gadgets-frontend.*\.vercel\.app$",
    r"^https://affordable-gadgets-admin.*\.vercel\.app$",
    r"^https://(www\.)?affordable-gadgetske\.com$",
]

CORS_ALLOW_CREDENTIALS = True

# Allow common headers your API uses (including idempotency headers)
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",  # Required for Token Authentication (Authorization: Token <key>)
    "cache-control",  # Required when frontend sends no-cache to avoid stale error responses
    "content-type",
    "origin",
    "pragma",  # Required when frontend sends Pragma: no-cache
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-brand-code",  # Required for brand-based filtering
    "x-session-key",  # Anonymous session tracking (cart, wishlist, analytics)
    "idempotency-key",  # Required for order idempotency
    "x-idempotency-key",  # Alternative idempotency key header
    "ngrok-skip-browser-warning",  # Required when frontend uses ngrok free-tier; CORS preflight must allow it
]

# Remove any wildcard CORS settings
CORS_ALLOW_ALL_ORIGINS = False

# If the public site uses a session-based cart, browsers treat these cookies as cross-site.
# Without SameSite=None (and Secure), the cart session cookie won't be sent.
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

# Cache: use Redis in production when REDIS_URL is set (e.g. Railway Redis add-on).
# This makes product list cache survive restarts and cold starts; first request after
# cold start is still slow until the service is warm.
_redis_url = os.environ.get("REDIS_URL", "").strip()
if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {"socket_connect_timeout": 5},
            "KEY_PREFIX": "ag",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ag-default",
        }
    }

# ── Logging ─────────────────────────────────────────────────────────
# In production, use JSON structured logging for easier ingestion by
# Cloud Logging / Loki / Datadog / etc.
_use_json_logging = os.environ.get("JSON_LOGGING", "true").lower() == "true"

if _use_json_logging:
    from inventory.middleware import RequestContextFilter
    from inventory.observability import JSONFormatter

    _json_fmt = JSONFormatter()
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_context": {"()": RequestContextFilter},
        },
        "formatters": {
            "json": {"()": lambda: _json_fmt},
            "simple": {"format": "{levelname} {message}", "style": "{"},
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["request_context"],
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "inventory": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }
else:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "file": {
                "level": "INFO",
                "class": "logging.FileHandler",
                "filename": os.path.join(BASE_DIR, "logs", "django.log"),  # noqa: F405
                "formatter": "verbose",
            },
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
        "loggers": {
            "django": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "inventory": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)  # noqa: F405

# ── Observability ─────────────────────────────────────────────────────
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
OBSERVABILITY_ENABLED = os.environ.get("OBSERVABILITY_ENABLED", "true").lower() == "true"
