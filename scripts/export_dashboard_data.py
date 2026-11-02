"""Export the small aggregated tables used by the Power BI dashboard.

Power BI never reads the 71 million events: it reads the few small CSV files written here.
Usage (from the project root, with the virtual environment active):

    python scripts/export_dashboard_data.py

Output: dashboard/data/*.csv. Definitions are the same as in notebooks 01 to 05.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.proportion import proportion_confint

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from load_events import connect_events  # noqa: E402

OUT = ROOT / "dashboard" / "data"
OUT.mkdir(parents=True, exist_ok=True)
LAST_FULL_DAY = "2025-04-09"          # the data ends on 2025-04-10 at 20:37
GAP_DAY = "2025-03-27"                # unexplained drop in active players

con, readable, unreadable = connect_events(str(ROOT / "data" / "raw" / "player_analytics" / "*.parquet"))
print(len(readable), "readable files,", len(unreadable), "unreadable")


def save(df, name):
    df.to_csv(OUT / name, index=False)
    print(f"{name}: {len(df)} rows")


def wilson(retained, players):
    lo, hi = proportion_confint(retained, players, method="wilson")
    return round(100 * lo, 1), round(100 * hi, 1)


# ---- base tables -------------------------------------------------------------------------
con.execute("""
    CREATE OR REPLACE TABLE new_players AS
    SELECT user_id,
           CAST(MIN(ts) AS DATE)                  AS cohort_day,
           ANY_VALUE(NULLIF(client_platform, '')) AS platform,
           ANY_VALUE(NULLIF(country_code, ''))    AS country
    FROM events WHERE event_name = 'firstOpen' GROUP BY 1
""")
con.execute("CREATE OR REPLACE TABLE active_days AS SELECT DISTINCT user_id, CAST(ts AS DATE) AS day FROM events")
con.execute("""
    CREATE OR REPLACE TABLE ads AS
    SELECT user_id, CAST(ts AS DATE) AS day, event_properties['adFormat'] AS ad_format,
           TRY_CAST(REPLACE(REPLACE(COALESCE(event_properties['amount'], event_properties['value']), ',', '.'), '/', '.') AS DOUBLE) AS amount_usd
    FROM events WHERE event_name = 'adImpression'
""")
con.execute("""
    CREATE OR REPLACE TABLE sessions AS
    SELECT user_session_id, user_id, MIN(ts) AS started_at,
           DATE_DIFF('second', MIN(ts), MAX(ts)) AS duration_s
    FROM events WHERE user_session_id <> '' GROUP BY 1, 2
""")

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
def retention(n, by=None):
    sel = f"p.{by} AS segment," if by else "'all' AS segment,"
    grp = "GROUP BY 1" if by else "GROUP BY 1"
    df = con.execute(f"""
        SELECT {sel} COUNT(*) AS players, COUNT(a.user_id) AS retained
        FROM new_players p
        LEFT JOIN active_days a ON a.user_id = p.user_id AND a.day = p.cohort_day + {n}
        WHERE p.cohort_day + {n} <= DATE '{LAST_FULL_DAY}' AND p.cohort_day + {n} <> DATE '{GAP_DAY}'
        {grp}
    """).df()
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
STEPS = ["gameOpened", "tokenCashout", "deviceUnlocked", "zoneUnlocked", "purchaseCompleted"]
names = ", ".join(f"'{s}'" for s in STEPS)
con.execute(f"""
    CREATE OR REPLACE TABLE firsts_new AS
    SELECT e.user_id, e.event_name, MIN(e.ts) AS t
    FROM events e JOIN new_players p USING (user_id)
    WHERE e.event_name IN ({names}) GROUP BY 1, 2
""")
con.execute("CREATE OR REPLACE TABLE funnel_new AS SELECT user_id, t, 1 AS step FROM firsts_new WHERE event_name = ?", [STEPS[0]])
for k in range(1, len(STEPS)):
    con.execute(f"""
        INSERT INTO funnel_new
        SELECT f.user_id, f.t, {k + 1} FROM firsts_new f
        JOIN funnel_new p ON p.user_id = f.user_id AND p.step = {k} AND f.t >= p.t
        WHERE f.event_name = '{STEPS[k]}'
    """)
fun = con.execute("SELECT step AS step_order, COUNT(*) AS players FROM funnel_new GROUP BY 1 ORDER BY 1").df()
fun["event"] = STEPS[: len(fun)]
fun["pct_of_first"] = (100 * fun["players"] / fun["players"].iloc[0]).round(1)
fun["note"] = ""
fun.loc[fun["event"] == "purchaseCompleted", "note"] = "Android only"
save(fun[["step_order", "event", "players", "pct_of_first", "note"]], "funnel_new_players.csv")

# ---- advertising -------------------------------------------------------------------------
fmt = con.execute("""
    SELECT ad_format, COUNT(*) AS impressions, ROUND(SUM(amount_usd), 0) AS revenue_usd,
           ROUND(AVG(amount_usd) * 1000, 1) AS ecpm_usd
    FROM ads GROUP BY 1 ORDER BY 3 DESC
""").df()
save(fmt, "ads_by_format.csv")

con.execute(f"""
    CREATE OR REPLACE TABLE day0 AS
    SELECT p.user_id,
           COALESCE(a.inter, 0) AS inter_day0,
           COALESCE(pl.play_events, 0) AS play_events,
           (d1.user_id IS NOT NULL) AS retained_d1
    FROM new_players p
    LEFT JOIN (SELECT user_id, day, COUNT(*) AS inter FROM ads WHERE ad_format = 'INTER' GROUP BY 1, 2) a
           ON a.user_id = p.user_id AND a.day = p.cohort_day
    LEFT JOIN (SELECT e.user_id, COUNT(*) AS play_events
               FROM events e JOIN new_players q ON q.user_id = e.user_id AND CAST(e.ts AS DATE) = q.cohort_day
               WHERE e.event_name NOT LIKE '\\_%' ESCAPE '\\'
                 AND e.event_name NOT IN ('adImpression', 'adsStart', 'adsReturned', 'interstitialLifecycle',
                                          'rvLifecycle', 'rvRewardClaim', 'appBackground', 'appFocus')
               GROUP BY 1) pl ON pl.user_id = p.user_id
    LEFT JOIN active_days d1 ON d1.user_id = p.user_id AND d1.day = p.cohort_day + 1
    WHERE p.cohort_day + 1 <= DATE '{LAST_FULL_DAY}'
      AND p.cohort_day NOT IN (DATE '2025-03-26', DATE '{GAP_DAY}')
""")
con.execute("""
    CREATE OR REPLACE TABLE day0_q AS
    SELECT *, NTILE(4) OVER (ORDER BY play_events) AS play_quartile FROM day0
""")
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
