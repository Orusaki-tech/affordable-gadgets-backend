"""
Startup migration check for migration 0027 (idempotency_key column).
This module is imported by wsgi.py on startup to ensure the migration is applied.
Also runs product visibility fixes on startup.
"""
import logging
from django.db import connection

logger = logging.getLogger(__name__)


def check_and_apply_migration_0027():
    """
    Check if migration 0027 (idempotency_key column) exists, and apply it if needed.
    This is called on startup in production to ensure the column exists.
    """
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
    Fix product visibility issues on startup.
    This ensures products are visible on the frontend by:
    - Setting units to AVAILABLE and available_online=True
    - Publishing products
    - Fixing brand visibility (making products global if they have no brand assignment)
    """
    try:
        from django.core.management import call_command
        logger.info("🔍 Running product visibility fix on startup...")
        call_command('fix_product_visibility', '--fix', verbosity=0)
        logger.info("✅ Product visibility fix completed")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Could not fix product visibility on startup: {e}")
        # Don't fail startup - just log the warning
        return False

