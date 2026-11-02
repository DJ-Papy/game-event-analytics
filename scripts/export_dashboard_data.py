"""Export the small aggregated tables used by the Power BI dashboard.

Power BI never reads the 71 million events: it reads the few small CSV files written here.
Usage (from the project root, with the virtual environment active):

    python scripts/export_dashboard_data.py

Output: dashboard/data/*.csv. The main definitions (new players, active days, retention,
funnel, first-day ad exposure) are read from the files in sql/, so that the dashboard and
the SQL shown in the repository are the same code. Results match notebooks 01 to 05.
"""
import sys
from pathlib import Path

import pandas as pd
from statsmodels.stats.proportion import proportion_confint

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from load_events import connect_events  # noqa: E402

SQL = ROOT / "sql"
OUT = ROOT / "dashboard" / "data"
OUT.mkdir(parents=True, exist_ok=True)
LAST_FULL_DAY = "2025-04-09"          # the data ends on 2025-04-10 at 20:37
GAP_DAY = "2025-03-27"                # unexplained drop in active players
DATES = {"last_full_day": LAST_FULL_DAY, "gap_day": GAP_DAY}

con, readable, unreadable = connect_events(str(ROOT / "data" / "raw" / "player_analytics" / "*.parquet"))
print(len(readable), "readable files,", len(unreadable), "unreadable")


def run_sql(file_name, params=None):
    """Run one file of sql/ (with named parameters such as $day_n) and return the result."""
    query = (SQL / file_name).read_text(encoding="utf-8")
    return con.execute(query, params) if params else con.execute(query)


def save(df, name):
    df.to_csv(OUT / name, index=False)
    print(f"{name}: {len(df)} rows")


def wilson(retained, players):
    lo, hi = proportion_confint(retained, players, method="wilson")
    return round(100 * lo, 1), round(100 * hi, 1)


# ---- base tables: new_players, active_days, ads, sessions ---------------------------------
run_sql("01_base_tables.sql")

# ---- daily table -------------------------------------------------------------------------
daily = con.execute("""
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
daily["note"] = ""
daily.loc[daily["day"].astype(str) == "2025-02-28", "note"] = "partial day"
daily.loc[daily["day"].astype(str) == "2025-04-10", "note"] = "partial day"
daily.loc[daily["day"].astype(str) == GAP_DAY, "note"] = "unexplained drop"
save(daily, "daily.csv")


# ---- retention ---------------------------------------------------------------------------
def retention(n, dimension="all"):
    df = run_sql("02_retention.sql", {**DATES, "day_n": n, "dimension": dimension}).df()
    df = df[df["players"] > 0].copy()
    df["pct"] = (100 * df["retained"] / df["players"]).round(1)
    ci = [wilson(r, p) for r, p in zip(df["retained"], df["players"])]
    df["ci_low"] = [c[0] for c in ci]
    df["ci_high"] = [c[1] for c in ci]
    df.insert(0, "day_n", n)
    return df.drop(columns="retained")


save(pd.concat([retention(n) for n in range(1, 15)], ignore_index=True).drop(columns="segment"), "retention_curve.csv")

parts = []
for dim in ("platform", "country"):
    top = con.execute(f"SELECT {dim} FROM new_players GROUP BY 1 HAVING COUNT(*) >= 500").df()[dim].tolist()
    for n in (1, 7, 14):
        d = retention(n, dim)
        d = d[d["segment"].isin(top) & (d["players"] >= 500)]
        d.insert(0, "dimension", dim)
        parts.append(d)
save(pd.concat(parts, ignore_index=True), "retention_segments.csv")

# ---- funnel for new players --------------------------------------------------------------
# New columns are added at the end so that the existing Power BI query keeps working.
fun = run_sql("03_new_player_funnel.sql").df()
fun["pct_of_first"] = (100 * fun["players"] / fun["players"].iloc[0]).round(1)
fun["note"] = ""
fun.loc[fun["event"] == "purchaseCompleted", "note"] = "Android only"
fun["pct_of_first_android"] = (100 * fun["android_players"] / fun["android_players"].iloc[0]).round(1)
save(fun[["step_order", "event", "players", "pct_of_first", "note", "android_players", "pct_of_first_android"]],
     "funnel_new_players.csv")

# ---- advertising -------------------------------------------------------------------------
fmt = con.execute("""
    SELECT ad_format, COUNT(*) AS impressions, ROUND(SUM(amount_usd), 0) AS revenue_usd,
           ROUND(AVG(amount_usd) * 1000, 1) AS ecpm_usd
    FROM ads GROUP BY 1 ORDER BY 3 DESC
""").df()
save(fmt, "ads_by_format.csv")

run_sql("04_ad_exposure_day0.sql", DATES)
labels = ["0", "1-2", "3-5", "6+"]
rows = []
for q in (None, 1, 2, 3, 4):
    where = "" if q is None else f"WHERE play_quartile = {q}"
    d = con.execute(f"""
        SELECT CASE WHEN inter_day0 = 0 THEN '0' WHEN inter_day0 <= 2 THEN '1-2'
                    WHEN inter_day0 <= 5 THEN '3-5' ELSE '6+' END AS bucket,
               COUNT(*) AS players, SUM(retained_d1::INT) AS retained
        FROM day0_q {where} GROUP BY 1
    """).df()
    for _, r in d.iterrows():
        lo, hi = wilson(int(r.retained), int(r.players))
        rows.append(dict(group="all new players" if q is None else f"activity quartile {q}", bucket=r.bucket,
                         players=int(r.players), d1_pct=round(100 * r.retained / r.players, 1), ci_low=lo, ci_high=hi))
exp = pd.DataFrame(rows)
exp["bucket"] = pd.Categorical(exp["bucket"], labels, ordered=True)
save(exp.sort_values(["group", "bucket"]), "ads_exposure_d1.csv")

# ---- experiment AdsConfig_iOS ------------------------------------------------------------
con.execute("""
    CREATE OR REPLACE TABLE exp_players AS
    SELECT user_id, CAST(MIN(ts) AS DATE) AS join_day, ARG_MIN(event_properties['experiment_variant_name'], ts) AS variant
    FROM events WHERE event_name = '_experimentJoin' AND event_properties['experiment_name'] = 'AdsConfig_iOS'
    GROUP BY 1
""")
ex = con.execute(f"""
    SELECT p.variant, COUNT(*) AS players,
           ROUND(100.0 * COUNT(d1.user_id) / COUNT(*), 1) AS d1_pct
    FROM exp_players p
    LEFT JOIN active_days d1 ON d1.user_id = p.user_id AND d1.day = p.join_day + 1
    WHERE p.join_day + 1 <= DATE '{LAST_FULL_DAY}' AND p.join_day + 1 <> DATE '{GAP_DAY}'
    GROUP BY 1 ORDER BY 1
""").df()
ia = con.execute(f"""
    SELECT p.variant, ROUND(COUNT(a.user_id) * 1.0 / COUNT(DISTINCT p.user_id), 2) AS interstitials_day0
    FROM exp_players p
    LEFT JOIN (SELECT user_id, day FROM ads WHERE ad_format = 'INTER') a ON a.user_id = p.user_id AND a.day = p.join_day
    WHERE p.join_day <> DATE '{GAP_DAY}' GROUP BY 1
""").df()
save(ex.merge(ia, on="variant"), "experiment_ads_config.csv")

# ---- headline numbers --------------------------------------------------------------------
tot = con.execute("""
    SELECT COUNT(*) AS events, COUNT(DISTINCT user_id) AS players, COUNT(DISTINCT user_session_id) FILTER (WHERE user_session_id <> '') AS sessions
    FROM events
""").df().iloc[0]
curve = pd.read_csv(OUT / "retention_curve.csv").set_index("day_n")
med = con.execute("SELECT QUANTILE_CONT(duration_s, 0.5) / 60 AS m FROM sessions").fetchone()[0]
rev = float(daily["ad_revenue_usd"].sum())
kpi = pd.DataFrame([dict(
    events=int(tot.events), players=int(tot.players), sessions=int(tot.sessions),
    new_players=int(daily["new_players"].sum()),
    d1_pct=curve.loc[1, "pct"], d7_pct=curve.loc[7, "pct"], d14_pct=curve.loc[14, "pct"],
    median_session_min=round(med, 1), ad_revenue_usd=int(rev),
    ad_revenue_per_active_player_day=round(rev / daily["active_players"].sum(), 3))])
save(kpi, "kpis.csv")
print("done")
