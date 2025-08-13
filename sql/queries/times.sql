-- SQL queries for player time management
-- These queries handle time submissions, updates, and retrievals

-- Check if user already has a time for a trial
-- Used to determine if we should INSERT or UPDATE
SELECT 
    id,
    time_ms,
    submitted_at,
    updated_at
FROM player_times 
WHERE trial_id = %s 
    AND user_id = %s;

-- Insert a new time submission
-- Creates a new time record for a user in a trial
INSERT INTO player_times (trial_id, user_id, time_ms)
VALUES (%s, %s, %s)
RETURNING id, submitted_at;

-- Update existing time submission (if new time is faster)
-- Updates user's time and sets updated_at timestamp
UPDATE player_times 
SET time_ms = %s,
    updated_at = CURRENT_TIMESTAMP
WHERE trial_id = %s 
    AND user_id = %s
    AND time_ms > %s  -- Only update if new time is faster
RETURNING id, updated_at;

-- Insert or update time (UPSERT)
-- Handles both new submissions and improvements in one query
INSERT INTO player_times (trial_id, user_id, time_ms)
VALUES (%s, %s, %s)
ON CONFLICT (trial_id, user_id)
DO UPDATE SET 
    time_ms = EXCLUDED.time_ms,
    updated_at = CURRENT_TIMESTAMP
WHERE player_times.time_ms > EXCLUDED.time_ms  -- Only if new time is faster
RETURNING id, time_ms, updated_at, 
    (CASE WHEN updated_at = submitted_at THEN 'inserted' ELSE 'updated' END) as action;

-- Remove user's time from a trial
-- Deletes a user's submission from a specific trial
DELETE FROM player_times 
WHERE trial_id = %s 
    AND user_id = %s
RETURNING id, time_ms;

-- Get user's current time for a trial
-- Returns user's submitted time for display or comparison
SELECT 
    time_ms,
    submitted_at,
    updated_at
FROM player_times 
WHERE trial_id = %s 
    AND user_id = %s;

-- Get leaderboard for a trial
-- Returns all times sorted by performance with ranking
SELECT 
    ROW_NUMBER() OVER (ORDER BY time_ms ASC) as rank,
    user_id,
    time_ms,
    submitted_at,
    updated_at,
    CASE 
        WHEN time_ms <= (SELECT gold_time_ms FROM weekly_trials WHERE id = %s) THEN 'gold'
        WHEN time_ms <= (SELECT silver_time_ms FROM weekly_trials WHERE id = %s) THEN 'silver'  
        WHEN time_ms <= (SELECT bronze_time_ms FROM weekly_trials WHERE id = %s) THEN 'bronze'
        ELSE 'none'
    END as medal
FROM player_times 
WHERE trial_id = %s
ORDER BY time_ms ASC;

-- Get leaderboard with trial information
-- Returns leaderboard data along with trial details for display
SELECT 
    wt.trial_number,
    wt.track_name,
    wt.gold_time_ms,
    wt.silver_time_ms,
    wt.bronze_time_ms,
    wt.status,
    pt.rank,
    pt.user_id,
    pt.time_ms,
    pt.submitted_at,
    pt.medal
FROM weekly_trials wt
LEFT JOIN (
    SELECT 
        trial_id,
        ROW_NUMBER() OVER (ORDER BY time_ms ASC) as rank,
        user_id,
        time_ms,
        submitted_at,
        CASE 
            WHEN time_ms <= (SELECT gold_time_ms FROM weekly_trials WHERE id = player_times.trial_id) THEN 'gold'
            WHEN time_ms <= (SELECT silver_time_ms FROM weekly_trials WHERE id = player_times.trial_id) THEN 'silver'
            WHEN time_ms <= (SELECT bronze_time_ms FROM weekly_trials WHERE id = player_times.trial_id) THEN 'bronze'
            ELSE 'none'
        END as medal
    FROM player_times
    WHERE trial_id = %s
) pt ON wt.id = pt.trial_id
WHERE wt.id = %s
ORDER BY pt.rank ASC NULLS LAST;

-- Get user's rank in a trial
-- Returns where a specific user ranks in the leaderboard
SELECT 
    rank,
    total_participants
FROM (
    SELECT 
        user_id,
        ROW_NUMBER() OVER (ORDER BY time_ms ASC) as rank,
        COUNT(*) OVER () as total_participants
    FROM player_times 
    WHERE trial_id = %s
) ranked_times
WHERE user_id = %s;

-- Get fastest time for a trial
-- Returns the current best time submission
SELECT 
    user_id,
    time_ms,
    submitted_at
FROM player_times 
WHERE trial_id = %s
ORDER BY time_ms ASC
LIMIT 1;

-- Get recent time submissions across all trials
-- Returns recent activity for monitoring/admin purposes
SELECT 
    pt.user_id,
    pt.time_ms,
    pt.submitted_at,
    wt.trial_number,
    wt.track_name,
    wt.guild_id
FROM player_times pt
JOIN weekly_trials wt ON pt.trial_id = wt.id
WHERE wt.guild_id = %s
ORDER BY pt.submitted_at DESC
LIMIT %s;

-- Get user's personal times across all trials
-- Returns a user's complete submission history
SELECT 
    wt.trial_number,
    wt.track_name,
    pt.time_ms,
    pt.submitted_at,
    pt.updated_at,
    (
        SELECT COUNT(*) + 1 
        FROM player_times pt2 
        WHERE pt2.trial_id = pt.trial_id 
            AND pt2.time_ms < pt.time_ms
    ) as rank,
    (
        SELECT COUNT(*) 
        FROM player_times pt3 
        WHERE pt3.trial_id = pt.trial_id
    ) as total_participants
FROM player_times pt
JOIN weekly_trials wt ON pt.trial_id = wt.id
WHERE pt.user_id = %s 
    AND wt.guild_id = %s
ORDER BY wt.trial_number DESC;