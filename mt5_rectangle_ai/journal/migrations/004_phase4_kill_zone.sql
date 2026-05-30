-- Phase 4: Add kill zone columns to setups table.
-- Run via: python journal/migrations/run.py

ALTER TABLE setups ADD COLUMN in_kill_zone INTEGER;
ALTER TABLE setups ADD COLUMN kill_zone_name TEXT;
