"""
WSGI config for store project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')

# Check and apply migration 0027 on startup (only in production)
# This ensures the idempotency_key column exists even if migration wasn't run
if os.environ.get('DJANGO_ENV') == 'production':
    try:
        import sys
        from pathlib import Path
        # Add project root to path
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from startup_migration_check import check_and_apply_migration_0027, fix_product_visibility_on_startup
        check_and_apply_migration_0027()
        # Fix product visibility issues on startup
        fix_product_visibility_on_startup()
    except Exception as e:
        # Don't fail startup if migration check fails - log and continue
        import logging
        logging.getLogger(__name__).warning(f"Could not run startup checks: {e}")

application = get_wsgi_application()
