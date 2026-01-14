-- SQL script to manually apply migration 0027_add_idempotency_key_to_order
-- This adds the idempotency_key column to the inventory_order table

-- Check if column already exists (PostgreSQL)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'inventory_order' 
        AND column_name = 'idempotency_key'
    ) THEN
        -- Add the column
        ALTER TABLE inventory_order 
        ADD COLUMN idempotency_key VARCHAR(255) NULL;
        
        -- Create unique index
        CREATE UNIQUE INDEX inventory_order_idempotency_key_idx 
        ON inventory_order(idempotency_key) 
        WHERE idempotency_key IS NOT NULL;
        
        -- Add comment
        COMMENT ON COLUMN inventory_order.idempotency_key IS 
        'Idempotency key to prevent duplicate orders from retries or double-clicks';
        
        RAISE NOTICE 'Column idempotency_key added successfully';
    ELSE
        RAISE NOTICE 'Column idempotency_key already exists';
    END IF;
END $$;

