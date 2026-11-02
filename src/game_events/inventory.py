"""Tracking inventory: what the game actually records, as observed in the data.

Writes the three CSV files used to write docs/tracking_plan.md. Example values are kept only for
low-cardinality properties (20 values or fewer), so that no identifier or receipt is published.
"""
import re

from . import config

MAX_DISTINCT_FOR_EXAMPLE = 20
USER_PROPERTIES_SAMPLE = "1 PERCENT (bernoulli, 42)"   # repeated on every event: a seeded 1% sample is enough


def naming_style(name):
    """Classify an event name, to measure how consistent the naming convention is."""
    if name.startswith("_"):
        return "system (leading underscore)"
    if re.search(r"\d", name):
        return "contains a digit"
    if re.fullmatch(r"[a-z]+", name):
        return "single lowercase word"
    if re.fullmatch(r"[a-z]+([A-Z][a-z0-9]+)+", name):
        return "camelCase"
    return "other"


def event_inventory(con):
    """One row per event name: volume, players, first and last day, share without session id."""
    df = con.execute("""
        SELECT event_name,
               COUNT(*)                AS events,
               COUNT(DISTINCT user_id) AS players,
               MIN(CAST(ts AS DATE))   AS first_day,
               MAX(CAST(ts AS DATE))   AS last_day,
               ROUND(100.0 * COUNT(*) FILTER (WHERE user_session_id = '') / COUNT(*), 1) AS pct_without_session
        FROM events
        GROUP BY 1
        ORDER BY events DESC
    """).df()
    return df


def event_properties(con, inventory):
    """One row per event and property key: coverage, approximate cardinality, first and last day.
    Scans every row (a few minutes on the full data)."""
    df = con.execute("""
        SELECT event_name,
               k                        AS property,
               COUNT(*)                 AS n_events,
               APPROX_COUNT_DISTINCT(v) AS approx_distinct_values,
               MIN(day)                 AS first_day,
               MAX(day)                 AS last_day,
               ANY_VALUE(LEFT(v, 40))   AS example
        FROM (SELECT event_name,
                     CAST(ts AS DATE)                     AS day,
                     UNNEST(map_keys(event_properties))   AS k,
                     UNNEST(map_values(event_properties)) AS v
              FROM events)
        GROUP BY 1, 2
    """).df()
    df = df.merge(inventory[["event_name", "events"]], on="event_name")
    df["pct_of_event"] = (100 * df["n_events"] / df["events"]).round(1)
    df.loc[df["approx_distinct_values"] > MAX_DISTINCT_FOR_EXAMPLE, "example"] = ""
    return df.drop(columns="events").sort_values(["event_name", "n_events"], ascending=[True, False])


def user_properties(con):
    """Player properties (user_properties_custom) on a seeded 1% sample of events."""
    con.execute(f"CREATE OR REPLACE TEMP TABLE ev_sample AS "
                f"SELECT user_properties_custom FROM events USING SAMPLE {USER_PROPERTIES_SAMPLE}")
    n_sample = con.execute("SELECT COUNT(*) FROM ev_sample").fetchall()[0][0]
    df = con.execute("""
        SELECT k                        AS property,
               COUNT(*)                 AS n_in_sample,
               APPROX_COUNT_DISTINCT(v) AS approx_distinct_values,
               ANY_VALUE(LEFT(v, 40))   AS example
        FROM (SELECT UNNEST(map_keys(user_properties_custom))   AS k,
                     UNNEST(map_values(user_properties_custom)) AS v
              FROM ev_sample)
        GROUP BY 1
        ORDER BY 2 DESC
    """).df()
    df["pct_of_events"] = (100 * df["n_in_sample"] / n_sample).round(1)
    df.loc[df["approx_distinct_values"] > MAX_DISTINCT_FOR_EXAMPLE, "example"] = ""
    return df, n_sample


def build_inventory(con, out_dir=config.DOCS):
    """Write event_inventory.csv, event_properties.csv and user_properties.csv to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    events = event_inventory(con)
    props = event_properties(con, events)
    users, _ = user_properties(con)
    events.to_csv(out_dir / "event_inventory.csv", index=False)
    props.to_csv(out_dir / "event_properties.csv", index=False)
    users.to_csv(out_dir / "user_properties.csv", index=False)
    return events, props, users
