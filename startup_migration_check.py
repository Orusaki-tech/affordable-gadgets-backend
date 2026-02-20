"""
Migration and product-visibility helpers for use in build scripts or cron only.

Do NOT import or call these from wsgi.py or AppConfig.ready() — that causes
"Accessing the database during app initialization" and "Apps aren't loaded yet".

- Migration 0027 (idempotency_key): handled in build.sh during deploy.
- Product visibility fix: run via build.sh or cron (see build.sh).
"""
import logging
from django.db import connection

logger = logging.getLogger(__name__)


def check_and_apply_migration_0027():
    """
    Check if migration 0027 (idempotency_key column) exists, and apply it if needed.
    Intended for build scripts. If called during app startup (apps not ready), does nothing.
    """
    try:
        from django.apps import apps
        if not apps.ready:
            return False
    except Exception:
        return False
    try:
        with connection.cursor() as cursor:
            # Check if column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'inventory_order' 
                AND column_name = 'idempotency_key'
            """)
            
            column_exists = cursor.fetchone() is not None
            
            if column_exists:
                logger.info("✅ Migration 0027 already applied - idempotency_key column exists")
                return True
            else:
                logger.info("⚠️  Migration 0027 not applied - idempotency_key column missing")
                logger.info("   Attempting to apply migration via management command...")
                
                # Try to apply via management command
                try:
                    from django.core.management import call_command
                    call_command('apply_idempotency_migration', verbosity=1)
                    logger.info("✅ Migration 0027 applied successfully via management command")
                    return True
                except Exception as cmd_error:
                    logger.warning(f"⚠️  Could not apply migration via command: {cmd_error}")
                    logger.warning("   Migration will need to be applied manually or via build script")
                    return False
                    
    except Exception as e:
        logger.warning(f"⚠️  Could not check migration 0027: {e}")
        # Don't fail startup - just log the warning
        return False


def fix_product_visibility_on_startup():
    """
    Fix product visibility issues. Intended for build scripts or cron only.
    If called during app/worker startup (e.g. from a start script), does nothing
    to avoid "Apps aren't loaded yet" and DB-at-init warnings.
    """
    try:
        from django.apps import apps
        if not apps.ready:
            # Called during WSGI/gunicorn load; skip to avoid DB before apps ready.
            return False
    except Exception:
        return False
    try:
        from django.core.management import call_command
        logger.info("🔍 Running product visibility fix...")
        call_command('fix_product_visibility', '--fix', verbosity=0)
        logger.info("✅ Product visibility fix completed")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Could not fix product visibility: {e}")
        return False

