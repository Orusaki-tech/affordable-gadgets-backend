"""
Django management command to manually apply migration 0027
if it cannot be run through normal migration process.

Usage:
    python manage.py apply_idempotency_migration
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Manually apply migration 0027 to add idempotency_key column to Order model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write('Checking if idempotency_key column exists...')
        
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
                self.stdout.write(
                    self.style.SUCCESS('✅ Column idempotency_key already exists!')
                )
                return
            
            self.stdout.write('Column does not exist. Applying migration...')
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN: Would execute the following:')
                )
                self.stdout.write('  - ALTER TABLE inventory_order ADD COLUMN idempotency_key VARCHAR(255) NULL;')
                self.stdout.write('  - CREATE UNIQUE INDEX inventory_order_idempotency_key_idx ON inventory_order(idempotency_key) WHERE idempotency_key IS NOT NULL;')
                return
            
            try:
                # Add the column
                cursor.execute("""
                    ALTER TABLE inventory_order 
                    ADD COLUMN idempotency_key VARCHAR(255) NULL
                """)
                self.stdout.write('  ✓ Column added')
                
                # Check if index already exists
                cursor.execute("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE schemaname = 'public' 
                    AND tablename = 'inventory_order' 
                    AND indexname = 'inventory_order_idempotency_key_idx'
                """)
                index_exists = cursor.fetchone() is not None
                
                if not index_exists:
                    # Create unique index (partial index for NULL values)
                    cursor.execute("""
                        CREATE UNIQUE INDEX inventory_order_idempotency_key_idx 
                        ON inventory_order(idempotency_key) 
                        WHERE idempotency_key IS NOT NULL
                    """)
                    self.stdout.write('  ✓ Unique index created')
                else:
                    self.stdout.write('  ✓ Index already exists')
                
                # Update Django migration state (mark migration as applied)
                try:
                    from django.db.migrations.recorder import MigrationRecorder
                    recorder = MigrationRecorder(connection)
                    # Check if migration record exists
                    cursor.execute("""
                        SELECT id 
                        FROM django_migrations 
                        WHERE app = 'inventory' 
                        AND name = '0027_add_idempotency_key_to_order'
                    """)
                    migration_exists = cursor.fetchone() is not None
                    
                    if not migration_exists:
                        # Insert migration record
                        cursor.execute("""
                            INSERT INTO django_migrations (app, name, applied)
                            VALUES ('inventory', '0027_add_idempotency_key_to_order', NOW())
                        """)
                        self.stdout.write('  ✓ Migration record added to django_migrations')
                    else:
                        self.stdout.write('  ✓ Migration record already exists')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠ Could not update migration state: {e}')
                    )
                    self.stdout.write('  You may need to run: python manage.py migrate --fake inventory 0027')
                
                self.stdout.write(
                    self.style.SUCCESS('\n✅ Migration 0027 applied successfully!')
                )
                
            except OperationalError as e:
                self.stdout.write(
                    self.style.ERROR(f'\n❌ Error applying migration: {e}')
                )
                self.stdout.write('\nYou may need to run this with database admin privileges.')
                raise
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'\n❌ Unexpected error: {e}')
                )
                raise

