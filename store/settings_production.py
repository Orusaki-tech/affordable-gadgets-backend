"""
Production settings for Django store project.
This file contains production-specific configurations.
IMPORTANT: This file imports from .settings, so it must be imported AFTER base settings are defined.
"""
import os
from .settings import *  # Import all base settings first

# Security settings
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set in production")

# Parse ALLOWED_HOSTS from environment variable
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '').split(',') if host.strip()]

# Automatically add Render domain if RENDER_EXTERNAL_HOSTNAME is set (Render provides this)
# This is the actual hostname Render assigns to your service
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

# If ALLOWED_HOSTS is still empty, raise an error
if not ALLOWED_HOSTS:
    raise ValueError(
        "ALLOWED_HOSTS environment variable must be set in production. "
        "On Render, you can set it to your service domain (e.g., affordable-gadgets-backend.onrender.com) "
        "or it will be auto-detected from RENDER_EXTERNAL_HOSTNAME if available."
    )

# Database (use PostgreSQL in production)
# Support both DATABASE_URL (Render/Heroku style) and individual DB_* variables
from urllib.parse import urlparse

database_url = os.environ.get('DATABASE_URL', '').strip()
if database_url:
    # Parse DATABASE_URL: postgresql://user:password@host:port/dbname
    # or postgres://user:password@host:port/dbname
    try:
        parsed = urlparse(database_url)
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': parsed.path[1:],  # Remove leading '/'
                'USER': parsed.username,
                'PASSWORD': parsed.password,
                'HOST': parsed.hostname,
                'PORT': parsed.port or '5432',
                'OPTIONS': {
                    'connect_timeout': 10,
                },
            }
        }
    except Exception as e:
        # Fall back to individual variables if DATABASE_URL parsing fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f'Failed to parse DATABASE_URL: {e}. Falling back to individual DB_* variables.')
        database_url = None

if not database_url:
    # Use individual environment variables
    db_host = os.environ.get('DB_HOST', 'localhost')
    
    # Extract hostname if DB_HOST contains a full URL or connection string
    # Handle cases like: "postgresql://user:pass@host:port/db" or just "hostname"
    if '://' in db_host or '@' in db_host:
        # It's a URL, try to parse it
        try:
            parsed = urlparse(db_host if '://' in db_host else f'postgresql://{db_host}')
            db_host = parsed.hostname or db_host.split('@')[-1].split(':')[0] if '@' in db_host else db_host
        except:
            # If parsing fails, try to extract hostname manually
            if '@' in db_host:
                db_host = db_host.split('@')[-1].split(':')[0]
            elif ':' in db_host and not db_host.startswith('postgres'):
                db_host = db_host.split(':')[0]
    
    # Clean up hostname - remove any trailing slashes, paths, or invalid characters (like parentheses)
    db_host = db_host.strip().rstrip('/').rstrip(')').rstrip('(').split('/')[0].split('?')[0]
    
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME'),
            'USER': os.environ.get('DB_USER'),
            'PASSWORD': os.environ.get('DB_PASSWORD'),
            'HOST': db_host,
            'PORT': os.environ.get('DB_PORT', '5432'),
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }

# Static files (use Cloudinary for production)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# For production with Silk enabled, use local filesystem for static files
# This ensures Silk's UI renders correctly. Cloudinary CDN is still used for media files.
# If Silk is not enabled, use Cloudinary for static files (CDN benefits)
# Note: SILKY_ENABLED is imported from base settings via 'from .settings import *'
if SILKY_ENABLED:
    # Use local filesystem storage when Silk is enabled (ensures Silk UI works)
    # Static files will be served directly via the URL pattern in urls.py
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    # Use Cloudinary for all static files if Silk is not enabled (CDN benefits)
    STATICFILES_STORAGE = 'cloudinary_storage.storage.StaticCloudinaryStorage'

# Media files (use Cloudinary - explicitly ensure it's set)
MEDIA_URL = '/media/'
# Ensure Cloudinary is used for all media file uploads
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Security headers
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS settings (restrict in production)
# Must include both frontend domains:
# 1. E-commerce frontend (shwari-phones/Next.js)
# 2. Admin frontend (inventory-management-frontend/React)
# Format: https://domain1.com,https://domain2.com
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
# Filter out empty strings from split
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS if origin.strip()]

# Allow Vercel preview deployments (dynamic URLs)
# Vercel preview URLs follow pattern: https://*-git-*-*-*.vercel.app
# Production URLs: https://*.vercel.app
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*-git-.*-.*-.*\.vercel\.app$",
    r"^https://affordable-gadgets-frontend.*\.vercel\.app$",
]

CORS_ALLOW_CREDENTIALS = True

# Allow common headers your API uses (including idempotency headers)
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',  # Required for Token Authentication (Authorization: Token <key>)
    'content-type',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-brand-code',  # Required for brand-based filtering
    'idempotency-key',  # Required for order idempotency
    'x-idempotency-key',  # Alternative idempotency key header
]

# Remove any wildcard CORS settings
CORS_ALLOW_ALL_ORIGINS = False

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'inventory': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Ensure logs directory exists
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

