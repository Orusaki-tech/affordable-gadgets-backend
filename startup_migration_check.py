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
            
            logger.info("Migration 0027 not applied - attempting to apply...")
            
            # Try to apply the migration using the management command
            try:
                call_command('apply_idempotency_migration')
                logger.info("✅ Migration 0027 applied successfully via management command")
                return True
            except Exception as cmd_error:
                logger.warning(f"Management command failed: {cmd_error}. Trying direct SQL...")
                
                # Fallback: Apply directly via SQL
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            ALTER TABLE inventory_order 
                            ADD COLUMN idempotency_key VARCHAR(255) NULL
                        """)
                        
                        cursor.execute("""
                            CREATE UNIQUE INDEX IF NOT EXISTS inventory_order_idempotency_key_idx 
                            ON inventory_order(idempotency_key) 
                            WHERE idempotency_key IS NOT NULL
                        """)
                        
                        # Mark migration as applied
                        cursor.execute("""
                            INSERT INTO django_migrations (app, name, applied)
                            VALUES ('inventory', '0027_add_idempotency_key_to_order', NOW())
                            ON CONFLICT DO NOTHING
                        """)
                        
                        logger.info("✅ Migration 0027 applied successfully via direct SQL")
                        return True
                except Exception as sql_error:
                    logger.error(f"Failed to apply migration via SQL: {sql_error}")
                    return False
                    
    except Exception as e:
        logger.error(f"Error checking/applying migration 0027: {e}")
        return False

if __name__ == '__main__':
    # Can be run as standalone script
    success = check_and_apply_migration_0027()
    sys.exit(0 if success else 1)
