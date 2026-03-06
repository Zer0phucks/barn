-- Adds CBC extraction-linked fields directly to existing bills rows.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'primary_resident_name'
    ) THEN
        ALTER TABLE bills ADD COLUMN primary_resident_name TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'primary_resident_age'
    ) THEN
        ALTER TABLE bills ADD COLUMN primary_resident_age TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'deceased_count'
    ) THEN
        ALTER TABLE bills ADD COLUMN deceased_count INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'important_notes'
    ) THEN
        ALTER TABLE bills ADD COLUMN important_notes TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'cbc_source_image_name'
    ) THEN
        ALTER TABLE bills ADD COLUMN cbc_source_image_name TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'bills' AND column_name = 'cbc_extracted_address'
    ) THEN
        ALTER TABLE bills ADD COLUMN cbc_extracted_address TEXT;
    END IF;
END $$;
