"""Journal reporting queries — mechanical stats + 6 self-learning reports."""

from __future__ import annotations

import sqlite3


# ── Original queries (kept) ───────────────────────────────────────────────────

def setup_counts_by_status(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT state AS status, COUNT(*) AS count FROM setups GROUP BY state ORDER BY count DESC"
    ).fetchall()


def trades_by_symbol(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT symbol, COUNT(*) AS trades, AVG(pnl_r) AS avg_r FROM trades GROUP BY symbol"
    ).fetchall()


def setups_by_final_status(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT final_status, COUNT(*) AS count FROM setups GROUP BY final_status ORDER BY count DESC"
    ).fetchall()


# ── Report 1 — Criterion Win Rate ─────────────────────────────────────────────

def criterion_win_rate(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Win rate of completed trades split by each Claude checklist criterion.

    For each criterion, compares win rate when Claude answered yes vs no.
    Only includes setups that reached a completed trade with a pnl_r outcome.
    """
    criteria = ["clean_sweep", "liquidity_pool", "fvg_present", "ob_visible",
                "htf_confirmed", "draw_visible", "would_trade"]
    rows = []
    for criterion in criteria:
        result = connection.execute(
            f"""
            SELECT
                '{criterion}' AS criterion,
                ar.{criterion}  AS criterion_value,
                COUNT(t.trade_id) AS trade_count,
                SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) AS wins,
                ROUND(
                    100.0 * SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) /
                    NULLIF(COUNT(t.trade_id), 0), 1
                ) AS win_rate_pct,
                ROUND(AVG(t.pnl_r), 3) AS avg_r
            FROM ai_reviews ar
            JOIN setups s ON ar.setup_id = s.setup_id
            JOIN trades t ON s.setup_id = t.setup_id
            WHERE t.pnl_r IS NOT NULL
              AND ar.{criterion} IS NOT NULL
            GROUP BY ar.{criterion}
            ORDER BY criterion_value DESC
            """
        ).fetchall()
        rows.extend(result)
    return rows


# ── Report 2 — Score Distribution ────────────────────────────────────────────

def score_distribution(
    connection: sqlite3.Connection,
    bucket_size: float = 10.0,
) -> list[sqlite3.Row]:
    """Histogram of confluence_score for winners vs losers.

    Bucketed into bands of bucket_size points. Identifies the natural
    minimum score threshold from actual trade outcomes.
    """
    return connection.execute(
        f"""
        SELECT
            CAST(ROUND(s.confluence_score / {bucket_size}) * {bucket_size} AS INTEGER) AS score_bucket,
            COUNT(t.trade_id) AS trade_count,
            SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN t.pnl_r <= 0 THEN 1 ELSE 0 END) AS losses,
            ROUND(
                100.0 * SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) /
                NULLIF(COUNT(t.trade_id), 0), 1
            ) AS win_rate_pct,
            ROUND(AVG(t.pnl_r), 3) AS avg_r,
            ROUND(SUM(t.pnl_r), 2) AS total_r
        FROM setups s
        JOIN trades t ON s.setup_id = t.setup_id
        WHERE s.confluence_score IS NOT NULL
          AND t.pnl_r IS NOT NULL
        GROUP BY score_bucket
        ORDER BY score_bucket
        """
    ).fetchall()


# ── Report 3 — Counterfactual Cost ───────────────────────────────────────────

def counterfactual_cost(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """For each skip reason: how many rejections were actually profitable?

    Shows which filter is over-filtering by measuring the cost of each rejection.
    hypothetical_outcome must be resolved (TP_HIT / SL_HIT / EXPIRED) to be counted.
    """
    return connection.execute(
        """
        SELECT
            cf.skip_reason,
            COUNT(*) AS total_rejected,
            SUM(CASE WHEN cf.hypothetical_outcome = 'TP_HIT' THEN 1 ELSE 0 END) AS would_have_won,
            SUM(CASE WHEN cf.hypothetical_outcome = 'SL_HIT' THEN 1 ELSE 0 END) AS would_have_lost,
            SUM(CASE WHEN cf.hypothetical_outcome = 'EXPIRED' THEN 1 ELSE 0 END) AS expired,
            SUM(CASE WHEN cf.hypothetical_outcome = 'OPEN' THEN 1 ELSE 0 END) AS still_open,
            ROUND(
                100.0 * SUM(CASE WHEN cf.hypothetical_outcome = 'TP_HIT' THEN 1 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN cf.hypothetical_outcome IN ('TP_HIT','SL_HIT') THEN 1 ELSE 0 END), 0),
                1
            ) AS hypothetical_win_rate_pct,
            ROUND(AVG(cf.hypothetical_pnl_r), 3) AS avg_hypothetical_r,
            ROUND(SUM(cf.hypothetical_pnl_r), 2) AS total_hypothetical_r
        FROM counterfactuals cf
        GROUP BY cf.skip_reason
        ORDER BY total_rejected DESC
        """
    ).fetchall()


# ── Report 4 — Kill Zone Performance ─────────────────────────────────────────

def kill_zone_performance(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Win rate, average R, and setup count inside vs outside each kill zone."""
    return connection.execute(
        """
        SELECT
            COALESCE(s.kill_zone_name, 'none') AS kill_zone,
            s.in_kill_zone,
            COUNT(t.trade_id) AS trade_count,
            SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) AS wins,
            ROUND(
                100.0 * SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) /
                NULLIF(COUNT(t.trade_id), 0), 1
            ) AS win_rate_pct,
            ROUND(AVG(t.pnl_r), 3) AS avg_r,
            ROUND(SUM(t.pnl_r), 2) AS total_r
        FROM setups s
        JOIN trades t ON s.setup_id = t.setup_id
        WHERE t.pnl_r IS NOT NULL
        GROUP BY kill_zone, s.in_kill_zone
        ORDER BY s.in_kill_zone DESC, trade_count DESC
        """
    ).fetchall()


# ── Report 5 — Swept Level Type Performance ───────────────────────────────────

def swept_level_performance(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Win rate and average R broken down by swept_level_type.

    Reveals whether double_top / session_high sweeps outperform single_swing.
    """
    return connection.execute(
        """
        SELECT
            COALESCE(s.swept_level_type, 'unknown') AS swept_level_type,
            COUNT(t.trade_id) AS trade_count,
            SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) AS wins,
            ROUND(
                100.0 * SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) /
                NULLIF(COUNT(t.trade_id), 0), 1
            ) AS win_rate_pct,
            ROUND(AVG(t.pnl_r), 3) AS avg_r,
            ROUND(SUM(t.pnl_r), 2) AS total_r
        FROM setups s
        JOIN trades t ON s.setup_id = t.setup_id
        WHERE t.pnl_r IS NOT NULL
        GROUP BY s.swept_level_type
        ORDER BY win_rate_pct DESC
        """
    ).fetchall()


# ── Report 6 — Prompt Version Comparison ─────────────────────────────────────

def prompt_version_comparison(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Side-by-side accuracy of each Claude criterion per prompt version.

    For each (prompt_version, criterion), shows how often Claude said yes/no
    and the resulting trade win rate — identifies which criteria are unreliable
    across versions so the next prompt version can correct them.
    """
    criteria = ["clean_sweep", "liquidity_pool", "fvg_present", "ob_visible",
                "htf_confirmed", "draw_visible", "would_trade"]
    rows = []
    for criterion in criteria:
        result = connection.execute(
            f"""
            SELECT
                ar.prompt_version,
                '{criterion}' AS criterion,
                COUNT(*) AS review_count,
                SUM(ar.{criterion}) AS answered_yes,
                ROUND(100.0 * SUM(ar.{criterion}) / NULLIF(COUNT(*), 0), 1) AS yes_rate_pct,
                COUNT(t.trade_id) AS trades_taken,
                SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) AS wins,
                ROUND(
                    100.0 * SUM(CASE WHEN t.pnl_r > 0 THEN 1 ELSE 0 END) /
                    NULLIF(COUNT(t.trade_id), 0), 1
                ) AS win_rate_pct,
                ROUND(AVG(t.pnl_r), 3) AS avg_r
            FROM ai_reviews ar
            JOIN setups s ON ar.setup_id = s.setup_id
            LEFT JOIN trades t ON s.setup_id = t.setup_id AND t.pnl_r IS NOT NULL
            WHERE ar.prompt_version IS NOT NULL
              AND ar.{criterion} IS NOT NULL
            GROUP BY ar.prompt_version
            ORDER BY ar.prompt_version, criterion
            """
        ).fetchall()
        rows.extend(result)
    return rows
