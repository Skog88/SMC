-- Phase 3: Add liquidity pool classification columns to setups table.
-- Run via: python journal/migrations/run.py

ALTER TABLE setups ADD COLUMN swept_level_type TEXT;
ALTER TABLE setups ADD COLUMN liquidity_pool_touches INTEGER;
