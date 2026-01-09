# How to Apply Migration 0027 on Render

This migration adds the `idempotency_key` column to the `inventory_order` table.

## Method 1: Using Render Shell (Recommended)

1. Go to your Render dashboard
2. Select your backend service
3. Click on "Shell" tab (or use the "Open Shell" button)
4. Run the following command:

```bash
python manage.py migrate inventory 0027
```

## Method 2: Using Raw SQL (If Method 1 doesn't work)

1. Go to your Render dashboard
2. Select your PostgreSQL database service
3. Click on "Connect" or "Info" to get connection details
4. Connect to your database using a PostgreSQL client (psql, pgAdmin, etc.)
5. Run the SQL script from `apply_migration_0027.sql`

Or use Render's database shell:
1. Go to your PostgreSQL service in Render
2. Click on "Connect" → "External Connection"
3. Use the connection string to connect with psql or your preferred client
4. Run the SQL commands from `apply_migration_0027.sql`

## Method 3: Using Django Management Command (One-off Task)

If Render supports one-off tasks, create a one-off task with:

```bash
python manage.py migrate inventory 0027
```

## Method 4: Manual SQL Execution via Django Shell

1. Open Render Shell (as in Method 1)
2. Run:

```python
python manage.py shell
```

Then in the shell:

```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'inventory_order' 
                AND column_name = 'idempotency_key'
            ) THEN
                ALTER TABLE inventory_order 
                ADD COLUMN idempotency_key VARCHAR(255) NULL;
                
                CREATE UNIQUE INDEX inventory_order_idempotency_key_idx 
                ON inventory_order(idempotency_key) 
                WHERE idempotency_key IS NOT NULL;
            END IF;
        END $$;
    """)
    print("Migration applied successfully!")
```

## Verification

After applying the migration, verify it worked:

```python
python manage.py shell
```

Then:

```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'inventory_order' 
        AND column_name = 'idempotency_key'
    """)
    result = cursor.fetchone()
    if result:
        print("✅ Column exists!")
    else:
        print("❌ Column does not exist")
```

## Troubleshooting

If you get a "column already exists" error:
- The migration may have already been applied
- Check using the verification script above

If you get permission errors:
- Make sure you're using the database user with ALTER TABLE permissions
- Check your database connection credentials
