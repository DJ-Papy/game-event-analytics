-- Base tables, built once per session on the `events` view (game_events.data.connect_events).
-- Every metric of the project reads these tables, so each definition lives in one place.

-- New players: a firstOpen event inside the window. The window starts on 2025-02-28, so
-- "first seen" would also include players installed before it. One player has two
-- firstOpen events (reinstall): the earliest one defines the cohort.
CREATE OR REPLACE TABLE new_players AS
SELECT
  user_id,
  CAST(MIN(ts) AS DATE)                  AS cohort_day,
  ANY_VALUE(NULLIF(client_platform, '')) AS platform,
  ANY_VALUE(NULLIF(country_code, ''))    AS country
FROM events
WHERE event_name = 'firstOpen'
GROUP BY user_id;

-- Active days: any event counts. session_started flags the days with a _sessionStart,
-- used to check that server-side events (no session id) do not inflate retention.
CREATE OR REPLACE TABLE active_days AS
SELECT
  user_id,
  CAST(ts AS DATE)                      AS day,
  BOOL_OR(event_name = '_sessionStart') AS session_started
FROM events
GROUP BY user_id, CAST(ts AS DATE);

-- Ad impressions. The revenue key was renamed from `value` to `amount` on 2025-03-29, and
-- some devices write the decimal separator as a comma or a slash.
CREATE OR REPLACE TABLE ads AS
SELECT
  user_id,
  user_session_id,
  ts,
  CAST(ts AS DATE)                                                AS day,
  client_platform                                                 AS platform,
  event_properties['adFormat']                                    AS ad_format,
  event_properties['adSource']                                    AS ad_source,
  event_properties['amount'] IS NOT NULL                          AS has_amount_key,
  event_properties['value'] IS NOT NULL                           AS has_value_key,
  COALESCE(event_properties['amount'], event_properties['value']) AS amount_text,
  TRY_CAST(REPLACE(REPLACE(amount_text, ',', '.'), '/', '.') AS DOUBLE) AS amount_usd
FROM events
WHERE event_name = 'adImpression';

-- Sessions. 10.4% of events have an empty session id (server-side events) and cannot be
-- attached to a session. No end-of-session event exists, so the duration is the time
-- between the first and the last event and may include time in the background.
CREATE OR REPLACE TABLE sessions AS
SELECT
  user_session_id,
  user_id,
  MIN(ts)                               AS started_at,
  MAX(ts)                               AS ended_at,
  DATE_DIFF('second', MIN(ts), MAX(ts)) AS duration_s,
  COUNT(*)                              AS n_events
FROM events
WHERE user_session_id <> ''
GROUP BY user_session_id, user_id;
