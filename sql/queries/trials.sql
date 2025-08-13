-- SQL queries for weekly trial management
-- These queries handle creating, updating, and retrieving trial information

-- Get next trial number for a guild
-- Used when creating new trials to ensure sequential numbering
SELECT COALESCE(MAX(trial_number), 0) + 1 as next_trial_number
FROM weekly_trials 
WHERE guild_id = %s;

-- Create a new weekly trial
-- Inserts a new challenge with goal times and duration
INSERT INTO weekly_trials (
    trial_number, 
    track_name, 
    gold_time_ms, 
    silver_time_ms, 
    bronze_time_ms, 
    end_date, 
    guild_id
) VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id, trial_number;

-- Get active trials for a guild
-- Returns all currently active trials that accept submissions
SELECT 
    id,
    trial_number,
    track_name,
    gold_time_ms,
    silver_time_ms,
    bronze_time_ms,
    start_date,
    end_date,
    status
FROM weekly_trials 
WHERE guild_id = %s 
    AND status = 'active'
ORDER BY trial_number DESC;

-- Get active trial by track name
-- Used to find a specific active trial for time submission
SELECT 
    id,
    trial_number,
    gold_time_ms,
    silver_time_ms,
    bronze_time_ms,
    start_date,
    end_date
FROM weekly_trials 
WHERE guild_id = %s 
    AND track_name = %s 
    AND status = 'active'
LIMIT 1;

-- Get trial information for leaderboard display
-- Returns trial details needed for leaderboard formatting
SELECT 
    id,
    trial_number,
    track_name,
    gold_time_ms,
    silver_time_ms,
    bronze_time_ms,
    status,
    start_date,
    end_date
FROM weekly_trials 
WHERE guild_id = %s 
    AND track_name = %s
ORDER BY trial_number DESC
LIMIT 1;

-- End a trial manually (admin command)
-- Changes status from 'active' to 'ended'
UPDATE weekly_trials 
SET status = 'ended', 
    end_date = CURRENT_TIMESTAMP 
WHERE guild_id = %s 
    AND track_name = %s 
    AND status = 'active'
RETURNING id, trial_number, track_name;

-- Mark expired trials
-- Automatically changes 'active' to 'expired' when end_date is reached
UPDATE weekly_trials 
SET status = 'expired' 
WHERE status = 'active' 
    AND end_date IS NOT NULL 
    AND end_date < CURRENT_TIMESTAMP
RETURNING id, trial_number, track_name;

-- Clean up old expired trials
-- Deletes trials that have been expired for more than specified days
DELETE FROM weekly_trials 
WHERE status = 'expired' 
    AND end_date < CURRENT_TIMESTAMP - INTERVAL '%s days'
RETURNING id, trial_number, track_name;

-- Count active trials for a guild
-- Used to enforce max concurrent trials limit
SELECT COUNT(*) as active_count
FROM weekly_trials 
WHERE guild_id = %s 
    AND status = 'active';

-- Get all trials for a guild (admin overview)
-- Returns complete trial history for administrative purposes
SELECT 
    id,
    trial_number,
    track_name,
    gold_time_ms,
    silver_time_ms,
    bronze_time_ms,
    status,
    start_date,
    end_date,
    (SELECT COUNT(*) FROM player_times WHERE trial_id = weekly_trials.id) as submission_count
FROM weekly_trials 
WHERE guild_id = %s
ORDER BY trial_number DESC;

-- Get track names for active trials (for autocomplete)
-- Returns list of track names that currently accept submissions
SELECT DISTINCT track_name
FROM weekly_trials 
WHERE guild_id = %s 
    AND status = 'active'
ORDER BY track_name;