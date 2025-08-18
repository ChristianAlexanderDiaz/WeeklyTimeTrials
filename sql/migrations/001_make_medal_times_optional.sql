-- Migration: Make medal time columns optional in weekly_trials table
-- This allows creating challenges without medal requirements

-- Drop the existing constraint that requires medal time ordering
ALTER TABLE weekly_trials DROP CONSTRAINT IF EXISTS chk_times;

-- Make medal time columns nullable
ALTER TABLE weekly_trials ALTER COLUMN gold_time_ms DROP NOT NULL;
ALTER TABLE weekly_trials ALTER COLUMN silver_time_ms DROP NOT NULL;
ALTER TABLE weekly_trials ALTER COLUMN bronze_time_ms DROP NOT NULL;

-- Add new constraint that validates medal time ordering only when all are provided
ALTER TABLE weekly_trials ADD CONSTRAINT chk_times_optional 
    CHECK (
        -- Either all medal times are NULL (no medal requirements)
        (gold_time_ms IS NULL AND silver_time_ms IS NULL AND bronze_time_ms IS NULL)
        OR
        -- Or all medal times are provided and properly ordered
        (gold_time_ms IS NOT NULL AND silver_time_ms IS NOT NULL AND bronze_time_ms IS NOT NULL 
         AND bronze_time_ms >= silver_time_ms AND silver_time_ms >= gold_time_ms)
    );

-- Update comments to reflect the new nullable behavior
COMMENT ON COLUMN weekly_trials.gold_time_ms IS 'Gold medal goal time in milliseconds (optional)';
COMMENT ON COLUMN weekly_trials.silver_time_ms IS 'Silver medal goal time in milliseconds (optional)'; 
COMMENT ON COLUMN weekly_trials.bronze_time_ms IS 'Bronze medal goal time in milliseconds (optional)';