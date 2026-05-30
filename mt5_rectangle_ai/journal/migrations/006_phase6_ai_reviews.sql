-- Phase 6: Add v3 SMC checklist columns to ai_reviews table.
-- Existing rows keep confidence_score (v2). New rows populate all fields.
-- Run via: python journal/migrations/run.py

ALTER TABLE ai_reviews ADD COLUMN prompt_version TEXT;
ALTER TABLE ai_reviews ADD COLUMN confluence_count INTEGER;
ALTER TABLE ai_reviews ADD COLUMN clean_sweep INTEGER;
ALTER TABLE ai_reviews ADD COLUMN liquidity_pool INTEGER;
ALTER TABLE ai_reviews ADD COLUMN fvg_present INTEGER;
ALTER TABLE ai_reviews ADD COLUMN ob_visible INTEGER;
ALTER TABLE ai_reviews ADD COLUMN htf_confirmed INTEGER;
ALTER TABLE ai_reviews ADD COLUMN draw_visible INTEGER;
ALTER TABLE ai_reviews ADD COLUMN would_trade INTEGER;
ALTER TABLE ai_reviews ADD COLUMN rejection_reason TEXT;
