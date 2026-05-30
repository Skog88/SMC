-- Phase 1: Add HTF bias columns to setups table.
-- Safe to run on existing databases — ALTER TABLE IF NOT EXISTS column is not
-- supported in SQLite, so each ADD COLUMN is guarded by a try/ignore pattern
-- in the Python migration runner. Run via: python journal/migrations/run.py

ALTER TABLE setups ADD COLUMN htf_bias TEXT;
ALTER TABLE setups ADD COLUMN htf_bos_level REAL;
ALTER TABLE setups ADD COLUMN htf_last_swing_high REAL;
ALTER TABLE setups ADD COLUMN htf_last_swing_low REAL;
ALTER TABLE setups ADD COLUMN htf_swing_midpoint REAL;
