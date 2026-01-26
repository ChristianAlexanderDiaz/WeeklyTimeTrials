-- Migration 002: Add Shrooms/Shroomless Categories and 1v1 Duel System
-- This migration adds support for differentiating between shrooms/shroomless trials
-- and implements a complete 1v1 duel system for player-vs-player challenges

-- ============================================================================
-- PHASE 1: Add Category Support to Weekly Trials
-- ============================================================================

-- Add category column to weekly_trials
ALTER TABLE weekly_trials
ADD COLUMN category VARCHAR(20) DEFAULT 'shrooms' NOT NULL;

-- Add constraint to validate category values
ALTER TABLE weekly_trials
ADD CONSTRAINT chk_category CHECK (category IN ('shrooms', 'shroomless'));

-- Drop the old unique constraint for active trials
DROP INDEX IF EXISTS unique_active_trial_per_guild_track;

-- Create new unique constraint that includes category
-- This allows separate shrooms and shroomless trials on the same track
CREATE UNIQUE INDEX unique_active_trial_per_guild_track_category
ON weekly_trials(guild_id, track_name, category) WHERE status = 'active';

-- ============================================================================
-- PHASE 2: Create 1v1 Duel System Tables
-- ============================================================================

-- Challenges 1v1 table
-- Stores head-to-head challenges between two players
CREATE TABLE challenges_1v1 (
    id SERIAL PRIMARY KEY,
    challenge_number INTEGER NOT NULL,          -- Sequential challenge number for display
    guild_id BIGINT NOT NULL,                   -- Discord server ID
    track_name VARCHAR(100) NOT NULL,           -- Track for the duel
    creator_user_id BIGINT NOT NULL,            -- User who created the challenge
    opponent_user_id BIGINT NOT NULL,           -- User who was challenged
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP,                      -- When opponent accepted
    start_date TIMESTAMP,                       -- When duel became active
    end_date TIMESTAMP,                         -- When duel expires/ended
    winner_user_id BIGINT,                      -- Winner (NULL if tie or incomplete)

    -- Constraints
    CONSTRAINT chk_1v1_status CHECK (status IN ('pending', 'accepted', 'active', 'completed', 'declined', 'expired')),
    CONSTRAINT chk_different_users CHECK (creator_user_id != opponent_user_id)
);

-- Challenge 1v1 times table
-- Stores time submissions for 1v1 duels
CREATE TABLE challenge_1v1_times (
    id SERIAL PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES challenges_1v1(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,                    -- Discord user ID
    time_ms INTEGER NOT NULL,                   -- Submitted time in milliseconds
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT chk_positive_time_1v1 CHECK (time_ms > 0),
    CONSTRAINT unique_user_per_challenge UNIQUE (challenge_id, user_id)
);

-- ============================================================================
-- PHASE 3: Create Indexes for Performance
-- ============================================================================

-- Index for finding duels by guild and status (common query)
CREATE INDEX idx_challenges_1v1_guild_status ON challenges_1v1(guild_id, status);

-- Index for finding duels involving specific users (for autocomplete)
CREATE INDEX idx_challenges_1v1_users ON challenges_1v1(creator_user_id, opponent_user_id);

-- Index for finding times by challenge and ordering by time
CREATE INDEX idx_challenge_1v1_times_challenge ON challenge_1v1_times(challenge_id, time_ms);

-- Index for finding duels by challenge number (for display)
CREATE INDEX idx_challenges_1v1_challenge_number ON challenges_1v1(challenge_number);

-- ============================================================================
-- PHASE 4: Add Comments for Documentation
-- ============================================================================

COMMENT ON TABLE challenges_1v1 IS 'Stores 1v1 head-to-head time trial challenges between two players';
COMMENT ON TABLE challenge_1v1_times IS 'Stores time submissions for 1v1 duel challenges';

COMMENT ON COLUMN weekly_trials.category IS 'Challenge category: shrooms (items allowed) or shroomless (no items)';
COMMENT ON COLUMN challenges_1v1.status IS 'pending: awaiting acceptance, active: in progress, completed: finished, declined: rejected, expired: timed out';
COMMENT ON COLUMN challenges_1v1.winner_user_id IS 'User ID of winner, NULL if tie or no submissions';
COMMENT ON COLUMN challenge_1v1_times.time_ms IS 'Time in milliseconds for precise comparison';

-- ============================================================================
-- Rollback Instructions (run these if migration needs to be reversed)
-- ============================================================================

-- To rollback this migration, run:
-- DROP TABLE IF EXISTS challenge_1v1_times CASCADE;
-- DROP TABLE IF EXISTS challenges_1v1 CASCADE;
-- DROP INDEX IF EXISTS unique_active_trial_per_guild_track_category;
-- CREATE UNIQUE INDEX unique_active_trial_per_guild_track ON weekly_trials(guild_id, track_name) WHERE status = 'active';
-- ALTER TABLE weekly_trials DROP CONSTRAINT IF EXISTS chk_category;
-- ALTER TABLE weekly_trials DROP COLUMN IF EXISTS category;
