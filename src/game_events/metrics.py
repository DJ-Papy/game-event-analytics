"""Player metrics on the base tables: retention, funnel, next-day return by ad exposure.

Rates are in percent, with a 95% Wilson interval (reliable for small groups and rates near 0).
"""
import pandas as pd
from statsmodels.stats.proportion import proportion_confint

from . import config
from .queries import run_sql

DIMENSIONS = ("platform", "country")
EXPOSURE_COLUMNS = ("inter_day0", "rewarded_day0")
EXPOSURE_BUCKETS = (("0", "= 0"), ("1-2", "BETWEEN 1 AND 2"), ("3-5", "BETWEEN 3 AND 5"), ("6+", ">= 6"))


def wilson_pct(successes, trials):
    """95% Wilson interval of successes / trials, in percent, rounded to 0.1."""
    lo, hi = proportion_confint(successes, trials, method="wilson")
    return round(100 * lo, 1), round(100 * hi, 1)


def add_rate(df, successes, trials, name="pct"):
    """Add the rate successes / trials (in %) and its Wilson interval (ci_low, ci_high)."""
    df = df.copy()
    df[name] = (100 * df[successes] / df[trials]).round(1)
    ci = [wilson_pct(s, n) for s, n in zip(df[successes], df[trials], strict=True)]
    df["ci_low"] = [c[0] for c in ci]
    df["ci_high"] = [c[1] for c in ci]
    return df


def retention(con, day_n, dimension="all", activity="any_event"):
    """Day-N retention of new players (sql/02_retention.sql).

    dimension: 'all', 'platform' or 'country'.
    activity: 'any_event' (any event that day) or 'session_start' (a session opened that day).
    """
    df = run_sql(con, "02_retention.sql", day_n=day_n, dimension=dimension, activity=activity,
                 last_full_day=config.LAST_FULL_DAY, gap_day=config.GAP_DAY).df()
    df = add_rate(df[df["players"] > 0], "retained", "players")
    df.insert(0, "day_n", day_n)
    return df.reset_index(drop=True)


def retention_curve(con, days=range(1, 15), activity="any_event"):
    """Overall retention for each day in `days` (one row per day)."""
    curve = pd.concat([retention(con, n, activity=activity) for n in days], ignore_index=True)
    return curve.drop(columns="segment")


def retention_by(con, dimension, days=(1, 7, 14), min_players=config.MIN_SEGMENT_PLAYERS, top=None):
    """Retention by platform or country, for segments with at least `min_players` new players
    (overall and on the measured day). `top` keeps only the largest segments."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"dimension must be one of {DIMENSIONS}")
    sizes = con.execute(f"""
        SELECT {dimension} AS segment, COUNT(*) AS n
        FROM new_players GROUP BY 1 HAVING COUNT(*) >= ? ORDER BY n DESC
    """, [min_players]).df()
    keep = sizes["segment"].tolist()[:top] if top else sizes["segment"].tolist()
    parts = []
    for n in days:
        d = retention(con, n, dimension)
        parts.append(d[d["segment"].isin(keep) & (d["players"] >= min_players)])
    out = pd.concat(parts, ignore_index=True)
    out.insert(0, "dimension", dimension)
    return out


def funnel(con, population="new"):
    """Funnel over config.FUNNEL_STEPS (sql/03_funnel.sql).

    population: 'new' (players with a firstOpen in the window) or 'all' (every player seen).
    """
    if population == "new":
        con.execute("CREATE OR REPLACE TEMP VIEW funnel_population AS SELECT user_id, platform FROM new_players")
    elif population == "all":
        con.execute("""
            CREATE OR REPLACE TEMP VIEW funnel_population AS
            SELECT user_id, ANY_VALUE(NULLIF(client_platform, '')) AS platform FROM events GROUP BY user_id
        """)
    else:
        raise ValueError("population must be 'new' or 'all'")
    df = run_sql(con, "03_funnel.sql").df()
    df["pct_of_previous"] = (100 * df["players"] / df["players"].shift(1)).round(1)
    df["pct_of_first"] = (100 * df["players"] / df["players"].iloc[0]).round(1)
    df["pct_of_first_android"] = (100 * df["android_players"] / df["android_players"].iloc[0]).round(1)
    return df


def d1_by_exposure(con, column="inter_day0", where="", complete=True):
    """Next-day return of new players by number of ads seen on day 0 (table day0_q, sql/04).

    where: optional SQL filter on day0_q, e.g. "play_quartile = 4".
    complete: also list the buckets with no player (as empty rows).
    """
    if column not in EXPOSURE_COLUMNS:
        raise ValueError(f"column must be one of {EXPOSURE_COLUMNS}")
    cases = " ".join(f"WHEN {column} {cond} THEN '{label}'" for label, cond in EXPOSURE_BUCKETS)
    df = con.execute(f"""
        SELECT CASE {cases} END AS bucket, COUNT(*) AS players, SUM(retained_d1::INT) AS retained
        FROM day0_q {"WHERE " + where if where else ""}
        GROUP BY 1
    """).df()
    df = add_rate(df, "retained", "players", name="d1_pct")
    labels = [label for label, _ in EXPOSURE_BUCKETS]
    df = df.set_index("bucket").reindex(labels).reset_index()
    if not complete:
        return df.dropna(subset=["players"]).astype({"players": int, "retained": int})
    return df.astype({"players": "Int64", "retained": "Int64"})
