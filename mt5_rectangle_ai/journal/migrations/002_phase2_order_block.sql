-- Phase 2: Add Order Block columns to setups table.
-- Run via: python journal/migrations/run.py

ALTER TABLE setups ADD COLUMN ob_origin_time TEXT;
ALTER TABLE setups ADD COLUMN ob_high REAL;
ALTER TABLE setups ADD COLUMN ob_low REAL;
ALTER TABLE setups ADD COLUMN ob_timeframe TEXT;
ALTER TABLE setups ADD COLUMN ob_mitigation_count INTEGER;
ALTER TABLE setups ADD COLUMN ob_fvg_overlap INTEGER;
ALTER TABLE setups ADD COLUMN ob_rectangle_overlap INTEGER;
