-- Mario Kart World Time Trial Bot Database Schema
-- This schema stores weekly time trial challenges and player submissions

-- Enable UUID extension for future use if needed
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Weekly time trials table
-- Stores information about each weekly challenge
CREATE TABLE weekly_trials (
    id SERIAL PRIMARY KEY,
    trial_number INTEGER NOT NULL,           -- Sequential trial number (1, 2, 3, ...)
    track_name VARCHAR(100) NOT NULL,        -- Mario Kart World track name
    gold_time_ms INTEGER NOT NULL,           -- Gold medal goal time in milliseconds
    silver_time_ms INTEGER NOT NULL,         -- Silver medal goal time in milliseconds  
    bronze_time_ms INTEGER NOT NULL,         -- Bronze medal goal time in milliseconds
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,                      -- When challenge ends (NULL = active)
    status VARCHAR(20) DEFAULT 'active',     -- 'active', 'expired', 'ended'
    guild_id BIGINT NOT NULL,                -- Discord server ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_status CHECK (status IN ('active', 'expired', 'ended')),
    CONSTRAINT chk_times CHECK (bronze_time_ms >= silver_time_ms AND silver_time_ms >= gold_time_ms)
);

-- Player times table  
-- Stores time submissions from Discord users
CREATE TABLE player_times (
    id SERIAL PRIMARY KEY,
    trial_id INTEGER NOT NULL REFERENCES weekly_trials(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,                 -- Discord user ID (permanent identifier)
    time_ms INTEGER NOT NULL,                -- Submitted time in milliseconds
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_positive_time CHECK (time_ms > 0),
    CONSTRAINT unique_user_per_trial UNIQUE (trial_id, user_id)  -- One time per user per trial
);

-- Bot managers table (optional - for learning SQL relationships)
-- Tracks users with special bot permissions
CREATE TABLE bot_managers (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,                 -- Discord user ID with manager permissions
    guild_id BIGINT NOT NULL,                -- Discord server ID  
    granted_by BIGINT,                       -- User ID who granted the permission
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT unique_manager_per_guild UNIQUE (user_id, guild_id)
);

-- Unique constraint for active trials only
-- This allows unlimited ended/expired trials per track but only 1 active trial per track
CREATE UNIQUE INDEX unique_active_trial_per_guild_track ON weekly_trials(guild_id, track_name) WHERE status = 'active';

-- Performance indexes
-- These indexes speed up common query patterns

-- Speed up leaderboard queries (most common operation)
CREATE INDEX idx_player_times_trial_time ON player_times(trial_id, time_ms);

-- Speed up user lookup queries  
CREATE INDEX idx_player_times_user_id ON player_times(user_id);

-- Speed up active trial lookups
CREATE INDEX idx_weekly_trials_status_guild ON weekly_trials(status, guild_id);

-- Speed up track-specific queries
CREATE INDEX idx_weekly_trials_track_name ON weekly_trials(track_name);

-- Speed up trial number lookups for naming
CREATE INDEX idx_weekly_trials_trial_number ON weekly_trials(trial_number);

-- Composite index for common admin queries
CREATE INDEX idx_weekly_trials_guild_status_track ON weekly_trials(guild_id, status, track_name);

-- Comments on tables for documentation
COMMENT ON TABLE weekly_trials IS 'Stores weekly Mario Kart World time trial challenges';
COMMENT ON TABLE player_times IS 'Stores time submissions from Discord users for each trial';
COMMENT ON TABLE bot_managers IS 'Tracks users with special bot management permissions';

-- Comments on important columns
COMMENT ON COLUMN weekly_trials.trial_number IS 'Sequential number for "Weekly Time Trial #N" naming';
COMMENT ON COLUMN weekly_trials.status IS 'active: accepting submissions, expired: read-only, ended: manually closed';
COMMENT ON COLUMN player_times.user_id IS 'Discord user ID - permanent identifier, names resolved dynamically';
COMMENT ON COLUMN player_times.time_ms IS 'Time in milliseconds for precise comparison and sorting';