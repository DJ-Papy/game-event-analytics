"""Aggregated tables for the Power BI dashboard (dashboard/data/*.csv).

Power BI never reads the 71 million events, only these small files. Every figure comes from the
same functions as the notebooks, so the dashboard and the analysis cannot drift apart.
"""
import pandas as pd

from . import config, experiment, metrics
from .queries import build_day0_exposure, build_experiment_players


def _save(df, out_dir, name):
    df.to_csv(out_dir / name, index=False)
    print(f"  {name}: {len(df)} rows")


def daily_table(con):
    df = con.execute("""
        WITH dau AS (SELECT day, COUNT(*) AS active_players FROM active_days GROUP BY 1),
             ses AS (SELECT CAST(started_at AS DATE) AS day, COUNT(*) AS sessions FROM sessions GROUP BY 1),
             nw  AS (SELECT cohort_day AS day, COUNT(*) AS new_players FROM new_players GROUP BY 1),
             rev AS (SELECT day, SUM(amount_usd) AS ad_revenue_usd, COUNT(*) AS ad_impressions FROM ads GROUP BY 1)
        SELECT d.day, d.active_players, s.sessions, COALESCE(n.new_players, 0) AS new_players,
               r.ad_impressions, ROUND(r.ad_revenue_usd, 0) AS ad_revenue_usd
        FROM dau d
        LEFT JOIN ses s USING (day) LEFT JOIN nw n USING (day) LEFT JOIN rev r USING (day)
        ORDER BY 1
    """).df()
    day = df["day"].astype(str)
    df["note"] = ""
    df.loc[day.isin(config.PARTIAL_DAYS), "note"] = "partial day"
    df.loc[day == config.GAP_DAY, "note"] = "unexplained drop"
    return df


def exposure_table(con):
    """D1 by interstitials seen on day 0, for all new players and within each activity quartile."""
    build_day0_exposure(con)
    parts = []
    for q in (None, 1, 2, 3, 4):
        d = metrics.d1_by_exposure(con, "inter_day0", where="" if q is None else f"play_quartile = {q}", complete=False)
        d.insert(0, "group", "all new players" if q is None else f"activity quartile {q}")
        parts.append(d[["group", "bucket", "players", "d1_pct", "ci_low", "ci_high"]])
    out = pd.concat(parts, ignore_index=True)
    out["bucket"] = pd.Categorical(out["bucket"], [label for label, _ in metrics.EXPOSURE_BUCKETS], ordered=True)
    return out.sort_values(["group", "bucket"]).reset_index(drop=True)


def experiment_table(con):
    """Per variant: players and D1 from the join day, interstitials per player on the join day."""
    build_experiment_players(con)
    d1 = experiment.experiment_retention(con, days=(1,))
    d1 = d1[["variant", "players", "pct"]].rename(columns={"pct": "d1_pct"})
    ads = experiment.ads_per_player(con, 0, config.LAST_FULL_DAY)
    inter = ads.groupby("variant", as_index=False)["interstitials"].mean().round(2)
    return d1.merge(inter.rename(columns={"interstitials": "interstitials_day0"}), on="variant")


def kpi_table(con, daily, curve):
    events, players, sessions = con.execute("""
        SELECT COUNT(*), COUNT(DISTINCT user_id), COUNT(DISTINCT user_session_id) FILTER (WHERE user_session_id <> '')
        FROM events
    """).fetchall()[0]
    median_min = con.execute("SELECT QUANTILE_CONT(duration_s, 0.5) / 60 FROM sessions").fetchall()[0][0]
    revenue = float(daily["ad_revenue_usd"].sum())
    pct = curve.set_index("day_n")["pct"]
    return pd.DataFrame([dict(
        events=int(events), players=int(players), sessions=int(sessions),
        new_players=int(daily["new_players"].sum()),
        d1_pct=pct[1], d7_pct=pct[7], d14_pct=pct[14],
        median_session_min=round(median_min, 1), ad_revenue_usd=int(revenue),
        ad_revenue_per_active_player_day=round(revenue / daily["active_players"].sum(), 3))])


def export_dashboard(con, out_dir=config.DASHBOARD_DATA):
    """Write every CSV read by dashboard/game-event-analytics.pbix. Needs the base tables."""
    out_dir.mkdir(parents=True, exist_ok=True)
    daily = daily_table(con)
    _save(daily, out_dir, "daily.csv")

    curve = metrics.retention_curve(con)
    _save(curve.drop(columns="retained"), out_dir, "retention_curve.csv")

    segments = pd.concat([metrics.retention_by(con, d) for d in metrics.DIMENSIONS], ignore_index=True)
    _save(segments.drop(columns="retained"), out_dir, "retention_segments.csv")

    # new columns go at the end so that the existing Power BI queries keep working
    fun = metrics.funnel(con, population="new")
    fun["note"] = ""
    fun.loc[fun["event"] == "purchaseCompleted", "note"] = "Android only"
    _save(fun[["step_order", "event", "players", "pct_of_first", "note", "android_players", "pct_of_first_android"]],
          out_dir, "funnel_new_players.csv")

    fmt = con.execute("""
        SELECT ad_format, COUNT(*) AS impressions, ROUND(SUM(amount_usd), 0) AS revenue_usd,
               ROUND(AVG(amount_usd) * 1000, 1) AS ecpm_usd
        FROM ads GROUP BY 1 ORDER BY 3 DESC
    """).df()
    _save(fmt, out_dir, "ads_by_format.csv")

    _save(exposure_table(con), out_dir, "ads_exposure_d1.csv")
    _save(experiment_table(con), out_dir, "experiment_ads_config.csv")
    _save(kpi_table(con, daily, curve), out_dir, "kpis.csv")
