"""Data quality checks, run before any export. An 'error' stops the pipeline."""
from pathlib import Path

import pandas as pd

from . import config


def run_checks(con, readable, unreadable):
    """Return one row per check: check, result, status ('ok' | 'warning' | 'error'), detail."""
    rows = []

    def add(check, result, status, detail=""):
        rows.append(dict(check=check, result=result, status=status, detail=detail))

    add("readable Parquet files", f"{len(readable)} of {len(readable) + len(unreadable)}",
        "ok" if not unreadable else "warning",
        ", ".join(Path(f).name for f in unreadable) + (" skipped" if unreadable else ""))

    n_events, null_user, null_ts, no_session = con.execute("""
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE user_id IS NULL OR user_id = ''),
               COUNT(*) FILTER (WHERE ts IS NULL),
               COUNT(*) FILTER (WHERE user_session_id IS NULL OR user_session_id = '')
        FROM events
    """).fetchall()[0]
    add("events without player id", f"{null_user:,}", "ok" if null_user == 0 else "error")
    add("events without timestamp", f"{null_ts:,}", "ok" if null_ts == 0 else "error")
    add("events without session id", f"{100 * no_session / n_events:.1f}%", "ok",
        "server-side events, excluded from session metrics")

    events_day, distinct_day = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT event_id) FROM events WHERE CAST(ts AS DATE) = CAST(? AS DATE)",
        [config.DUPLICATE_CHECK_DAY],
    ).fetchall()[0]
    add(f"duplicate event ids on {config.DUPLICATE_CHECK_DAY}", f"{events_day - distinct_day:,}",
        "ok" if events_day == distinct_day else "warning")

    dau = con.execute("""
        SELECT CAST(ts AS DATE) AS day, COUNT(DISTINCT user_id) AS players
        FROM events GROUP BY 1 ORDER BY 1
    """).df()
    full_days = dau[~dau["day"].astype(str).isin(config.PARTIAL_DAYS)]
    drops = full_days[full_days["players"] < 0.5 * full_days["players"].median()]["day"].astype(str).tolist()
    expected = [config.GAP_DAY]
    add("days with less than half the median active players", ", ".join(drops) or "none",
        "ok" if drops == expected else "warning", f"expected: {', '.join(expected)} (config.GAP_DAY)")

    impressions, usable = con.execute("SELECT COUNT(*), COUNT(amount_usd) FROM ads").fetchall()[0] \
        if _has_table(con, "ads") else (0, 0)
    if impressions:
        share = 100 * usable / impressions
        add("ad impressions with a usable revenue", f"{share:.1f}%", "ok" if share >= 99 else "warning",
            "revenue under `value` before 2025-03-29, `amount` after")

    return pd.DataFrame(rows)


def _has_table(con, name):
    return con.execute("SELECT COUNT(*) FROM duckdb_tables() WHERE table_name = ?", [name]).fetchall()[0][0] > 0
