-- Phase 7: Add confluence scoring columns to setups table.
-- Run via: python journal/migrations/run.py

ALTER TABLE setups ADD COLUMN confluence_score REAL;
ALTER TABLE setups ADD COLUMN confluence_score_breakdown TEXT;
ALTER TABLE setups ADD COLUMN min_score_required REAL;
