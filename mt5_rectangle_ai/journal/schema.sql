CREATE TABLE IF NOT EXISTS setups (
    setup_id TEXT PRIMARY KEY,

    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    setup_time TEXT NOT NULL,
    setup_date TEXT NOT NULL,
    session TEXT,

    timeframe_setup TEXT DEFAULT 'M15',
    timeframe_entry TEXT DEFAULT 'M1',

    state TEXT NOT NULL,
    final_status TEXT,

    ema_primary_period INTEGER,
    ema_secondary_period INTEGER,
    ema_primary_value REAL,
    ema_secondary_value REAL,
    price_vs_ema TEXT,
    ema_slope_points REAL,
    trend_direction TEXT,
    trend_valid INTEGER,

    marked_level_type TEXT,
    marked_level_price REAL,
    marked_level_time TEXT,
    clean_structure INTEGER,
    structure_score INTEGER,
    level_age_candles INTEGER,
    level_already_swept INTEGER,

    inside_imbalance INTEGER,
    imbalance_type TEXT,
    imbalance_low REAL,
    imbalance_high REAL,
    imbalance_distance_points REAL,

    level_is_session_high_low INTEGER,
    related_session TEXT,
    related_session_level TEXT,
    session_level_distance_points REAL,

    m15_trigger_time TEXT,
    m15_open REAL,
    m15_high REAL,
    m15_low REAL,
    m15_close REAL,
    m15_tick_volume INTEGER,

    sweep_valid INTEGER,
    sweep_depth_points REAL,
    wick_size_points REAL,
    wick_to_range_ratio REAL,
    close_position REAL,

    rectangle_low REAL,
    rectangle_high REAL,
    rectangle_size_points REAL,

    ai_enabled INTEGER,
    ai_score INTEGER,
    ai_decision TEXT,
    ai_model TEXT,
    ai_prompt_version TEXT,

    m1_flip_confirmed INTEGER DEFAULT 0,
    m1_flip_time TEXT,
    m1_flip_close REAL,
    m1_wait_candles INTEGER,

    risk_approved INTEGER,
    risk_block_reason TEXT,
    execution_attempted INTEGER DEFAULT 0,
    order_sent INTEGER DEFAULT 0,

    htf_bias TEXT,
    htf_bos_level REAL,
    htf_last_swing_high REAL,
    htf_last_swing_low REAL,
    htf_swing_midpoint REAL,

    swept_level_type TEXT,
    liquidity_pool_touches INTEGER,

    ob_origin_time TEXT,
    ob_high REAL,
    ob_low REAL,
    ob_timeframe TEXT,
    ob_mitigation_count INTEGER,
    ob_fvg_overlap INTEGER,
    ob_rectangle_overlap INTEGER,

    skip_reason TEXT,
    skip_stage TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_reviews (
    review_id TEXT PRIMARY KEY,
    setup_id TEXT NOT NULL,

    provider TEXT,
    model TEXT,
    prompt_version TEXT,

    input_json TEXT NOT NULL,
    raw_response TEXT,
    parsed_json TEXT,

    confidence_score INTEGER,
    decision TEXT,
    reasoning TEXT,

    response_valid INTEGER,
    error_message TEXT,
    latency_ms INTEGER,

    created_at TEXT NOT NULL,

    FOREIGN KEY (setup_id) REFERENCES setups(setup_id)
);

CREATE TABLE IF NOT EXISTS m1_events (
    event_id TEXT PRIMARY KEY,
    setup_id TEXT NOT NULL,

    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,

    m1_time TEXT NOT NULL,
    m1_open REAL,
    m1_high REAL,
    m1_low REAL,
    m1_close REAL,
    m1_tick_volume INTEGER,

    rectangle_low REAL,
    rectangle_high REAL,

    close_above_rectangle INTEGER,
    close_below_rectangle INTEGER,
    touched_rectangle INTEGER,
    entered_rectangle INTEGER,

    flip_confirmed INTEGER,
    event_type TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (setup_id) REFERENCES setups(setup_id)
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    setup_id TEXT NOT NULL,

    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,

    mt5_order_id TEXT,
    mt5_deal_id TEXT,
    mt5_position_id TEXT,

    entry_time TEXT,
    entry_price REAL,
    requested_entry_price REAL,
    sl REAL,
    tp REAL,

    lot_size REAL,
    risk_money REAL,
    risk_percent REAL,
    planned_rr REAL,

    sl_distance_points REAL,
    tp_distance_points REAL,

    spread_at_entry_points REAL,
    slippage_points REAL,
    commission REAL,
    swap REAL,

    exit_time TEXT,
    exit_price REAL,
    exit_reason TEXT,

    gross_pnl_money REAL,
    net_pnl_money REAL,
    pnl_r REAL,

    max_favorable_excursion_points REAL,
    max_adverse_excursion_points REAL,
    max_favorable_r REAL,
    max_adverse_r REAL,

    duration_minutes REAL,

    status TEXT NOT NULL,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (setup_id) REFERENCES setups(setup_id)
);

CREATE TABLE IF NOT EXISTS trade_events (
    event_id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL,
    setup_id TEXT NOT NULL,

    event_time TEXT NOT NULL,
    event_type TEXT NOT NULL,
    price REAL,
    volume REAL,

    mt5_raw_json TEXT,
    message TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY (trade_id) REFERENCES trades(trade_id),
    FOREIGN KEY (setup_id) REFERENCES setups(setup_id)
);

CREATE TABLE IF NOT EXISTS screenshots (
    screenshot_id TEXT PRIMARY KEY,

    setup_id TEXT,
    trade_id TEXT,

    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,

    screenshot_type TEXT NOT NULL,
    file_path TEXT NOT NULL,

    chart_time TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (setup_id) REFERENCES setups(setup_id),
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

CREATE TABLE IF NOT EXISTS daily_stats (
    stat_date TEXT PRIMARY KEY,

    total_setups INTEGER,
    mechanical_valid_setups INTEGER,
    ai_approved_setups INTEGER,
    ai_rejected_setups INTEGER,

    rectangles_activated INTEGER,
    m1_flips_confirmed INTEGER,
    trades_opened INTEGER,

    wins INTEGER,
    losses INTEGER,
    breakevens INTEGER,

    gross_pnl_money REAL,
    net_pnl_money REAL,
    total_r REAL,

    avg_ai_score REAL,
    avg_win_ai_score REAL,
    avg_loss_ai_score REAL,

    best_symbol TEXT,
    worst_symbol TEXT,
    best_session TEXT,
    worst_session TEXT,

    max_drawdown_money REAL,
    max_drawdown_r REAL,

    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS system_events (
    event_id TEXT PRIMARY KEY,

    event_time TEXT NOT NULL,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT,
    raw_json TEXT,

    created_at TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS ai_training_view AS
SELECT
    s.setup_id,
    s.symbol,
    s.session,
    s.direction,
    s.trend_valid,
    s.ema_slope_points,
    s.structure_score,
    s.inside_imbalance,
    s.level_is_session_high_low,
    s.sweep_depth_points,
    s.wick_size_points,
    s.wick_to_range_ratio,
    s.close_position,
    s.rectangle_size_points,
    s.ai_score,
    s.ai_decision,
    s.m1_flip_confirmed,
    CASE WHEN t.trade_id IS NOT NULL THEN 1 ELSE 0 END AS trade_taken,
    t.pnl_r,
    s.final_status
FROM setups s
LEFT JOIN trades t ON s.setup_id = t.setup_id;
