-- Phase 5: Add premium/discount zone columns to setups table.
-- Run via: python journal/migrations/run.py

ALTER TABLE setups ADD COLUMN zone_type TEXT;
ALTER TABLE setups ADD COLUMN distance_from_midpoint_pct REAL;
