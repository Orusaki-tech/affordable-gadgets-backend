"""
Startup script to check and apply migration 0027 if needed.
This can be called from wsgi.py or as a separate startup script.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

def check_and_apply_migration_0027():
    """
    Check if migration 0027 has been applied, and apply it if not.
    This is safe to run multiple times.
    """
    try:
        with connection.cursor() as cursor:
            # Check if column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'inventory_order' 
                AND column_name = 'idempotency_key'
            """)
            column_exists = cursor.fetchone() is not None
            
            if column_exists:
                logger.info("✅ Migration 0027 already applied - idempotency_key column exists")
                return True
            
            logger.info("Migration 0027 not applied - attempting to apply via direct SQL...")
            
            # Apply directly via SQL (more reliable than management command)
            try:
                with connection.cursor() as cursor:
                    # Add the column
                    cursor.execute("""
                        ALTER TABLE inventory_order 
                        ADD COLUMN idempotency_key VARCHAR(255) NULL
                    """)
                    logger.info("  ✓ Column added")
                    
                    # Create unique index (partial index for NULL values)
                    cursor.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS inventory_order_idempotency_key_idx 
                        ON inventory_order(idempotency_key) 
                        WHERE idempotency_key IS NOT NULL
                    """)
                    logger.info("  ✓ Unique index created")
                    
                    # Mark migration as applied in Django's migration table
                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES ('inventory', '0027_add_idempotency_key_to_order', NOW())
                        ON CONFLICT DO NOTHING
                    """)
                    logger.info("  ✓ Migration record added")
                    
                    logger.info("✅ Migration 0027 applied successfully via direct SQL")
                    return True
            except Exception as sql_error:
                # Check if error is because column already exists (race condition)
                error_msg = str(sql_error).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    logger.info("✅ Column already exists (likely applied by another process)")
                    return True
                logger.error(f"Failed to apply migration via SQL: {sql_error}")
                return False
                    
    except Exception as e:
        logger.error(f"Error checking/applying migration 0027: {e}")
        return False

if __name__ == '__main__':
    # Can be run as standalone script
    success = check_and_apply_migration_0027()
    sys.exit(0 if success else 1)
