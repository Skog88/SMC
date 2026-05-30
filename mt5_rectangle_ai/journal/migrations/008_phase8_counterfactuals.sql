-- Phase 8: Add counterfactuals and confluence_breakdown tables.
-- Run via: python journal/migrations/run.py

CREATE TABLE IF NOT EXISTS counterfactuals (
    id TEXT PRIMARY KEY,
    setup_id TEXT NOT NULL,
    skip_reason TEXT NOT NULL,
    planned_entry REAL,
    planned_sl REAL,
    planned_tp REAL,
    planned_rr REAL,
    hypothetical_outcome TEXT,
    hypothetical_pnl_r REAL,
    monitoring_end_time TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (setup_id) REFERENCES setups(setup_id)
);

CREATE TABLE IF NOT EXISTS confluence_breakdown (
    id TEXT PRIMARY KEY,
    setup_id TEXT NOT NULL,
    criterion TEXT NOT NULL,
    value REAL NOT NULL,
    weight REAL NOT NULL,
    contribution REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (setup_id) REFERENCES setups(setup_id)
);
