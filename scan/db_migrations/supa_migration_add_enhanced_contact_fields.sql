-- Add enhanced contact fields to bills table if they don't exist
DO $$ 
BEGIN 
    -- Add prop_ownership_type column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bills' AND column_name = 'prop_ownership_type') THEN
        ALTER TABLE bills ADD COLUMN prop_ownership_type TEXT;
    END IF;

    -- Add prop_last_sale_date column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bills' AND column_name = 'prop_last_sale_date') THEN
        ALTER TABLE bills ADD COLUMN prop_last_sale_date TEXT;
    END IF;

    -- Add prop_occupancy_type column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bills' AND column_name = 'prop_occupancy_type') THEN
        ALTER TABLE bills ADD COLUMN prop_occupancy_type TEXT;
    END IF;

    -- Add owner_mobile_phone column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bills' AND column_name = 'owner_mobile_phone') THEN
        ALTER TABLE bills ADD COLUMN owner_mobile_phone TEXT;
    END IF;

    -- Add owner_details_url column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bills' AND column_name = 'owner_details_url') THEN
        ALTER TABLE bills ADD COLUMN owner_details_url TEXT;
    END IF;

    -- Add property_search_url column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'bills' AND column_name = 'property_search_url') THEN
        ALTER TABLE bills ADD COLUMN property_search_url TEXT;
    END IF;

END $$;
