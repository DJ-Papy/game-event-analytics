-- =====================================================================
-- Base tables for the analysis
-- Engine: DuckDB | Source: the `events` view over the Parquet files
--         (created by scripts/load_events.py, one row per event)
-- Run this file first: 02, 03 and 04 read the tables it creates.
-- =====================================================================


-- 1. New players
-- The window starts on 2025-02-28, so "first seen" is not "installed".
-- A new player is a player with a firstOpen event (the install event)
-- inside the window. One player has two (reinstall): the earliest is kept.
CREATE OR REPLACE TABLE new_players AS
SELECT
  user_id,
  CAST(MIN(ts) AS DATE)                  AS cohort_day,
  ANY_VALUE(NULLIF(client_platform, '')) AS platform,
  ANY_VALUE(NULLIF(country_code, ''))    AS country
FROM events
WHERE event_name = 'firstOpen'
GROUP BY user_id;


-- 2. Active days
-- A player is active on a day if they have at least one event that day.
-- notebooks/02_cohort_retention.ipynb compares this with a stricter
-- definition (a _sessionStart event that day).
CREATE OR REPLACE TABLE active_days AS
SELECT DISTINCT user_id, CAST(ts AS DATE) AS day
FROM events;


-- 3. Ad impressions with their estimated revenue (USD)
-- The revenue is stored as text, under the key `value` until late March and
-- under `amount` afterwards (renamed property). Some devices write the decimal
-- separator as a comma or a slash: both become a dot before the cast.
-- TRY_CAST returns NULL instead of failing on an unparsable value.
CREATE OR REPLACE TABLE ads AS
SELECT
  user_id,
  CAST(ts AS DATE)             AS day,
  event_properties['adFormat'] AS ad_format,
  TRY_CAST(
    REPLACE(REPLACE(COALESCE(event_properties['amount'], event_properties['value']), ',', '.'), '/', '.')
    AS DOUBLE)                 AS amount_usd
FROM events
WHERE event_name = 'adImpression';


-- 4. Sessions
-- A session is one user_session_id. 10.4% of events have an empty id
-- (server-side events): they cannot belong to a session and are left out.
-- Duration = time between the first and the last event of the session.
CREATE OR REPLACE TABLE sessions AS
SELECT
  user_session_id,
  user_id,
  MIN(ts)                               AS started_at,
  DATE_DIFF('second', MIN(ts), MAX(ts)) AS duration_s
FROM events
WHERE user_session_id <> ''
GROUP BY user_session_id, user_id;
