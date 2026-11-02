-- First day of each new player: ad exposure, activity, and return on day 1.
-- Parameters: $last_full_day, $gap_day. Creates day0_q (one row per new player).
--
-- Players who play more see more ads and come back more, so exposure is only compared
-- within activity quartiles. Activity = gameplay events on day 0 (platform events
-- starting with "_", ad events and app background/focus excluded).
-- user_id breaks NTILE ties so that quartiles are identical from one run to the next.
-- Cohorts whose day 0 or day 1 is the data gap are excluded.
CREATE OR REPLACE TABLE day0_q AS
WITH ads_day0 AS (
  SELECT
    user_id,
    day,
    COUNT(*) FILTER (WHERE ad_format = 'INTER')    AS inter,
    COUNT(*) FILTER (WHERE ad_format = 'REWARDED') AS rewarded
  FROM ads
  GROUP BY user_id, day
),
sessions_day0 AS (
  -- sessions with at least one event on day 0 (a session can span midnight)
  SELECT e.user_id, COUNT(DISTINCT e.user_session_id) AS sessions
  FROM events e
  JOIN new_players q
    ON q.user_id = e.user_id
   AND CAST(e.ts AS DATE) = q.cohort_day
  WHERE e.user_session_id <> ''
  GROUP BY e.user_id
),
play_day0 AS (
  SELECT e.user_id, COUNT(*) AS play_events
  FROM events e
  JOIN new_players q
    ON q.user_id = e.user_id
   AND CAST(e.ts AS DATE) = q.cohort_day
  WHERE e.event_name NOT LIKE '\_%' ESCAPE '\'
    AND e.event_name NOT IN ('adImpression', 'adsStart', 'adsReturned', 'interstitialLifecycle',
                             'rvLifecycle', 'rvRewardClaim', 'appBackground', 'appFocus')
  GROUP BY e.user_id
),
day0 AS (
  SELECT
    p.user_id,
    p.cohort_day,
    COALESCE(a.inter, 0)        AS inter_day0,
    COALESCE(a.rewarded, 0)     AS rewarded_day0,
    COALESCE(s.sessions, 0)     AS sessions_day0,
    COALESCE(pl.play_events, 0) AS play_events,
    (d1.user_id IS NOT NULL)    AS retained_d1
  FROM new_players p
  LEFT JOIN ads_day0 a       ON a.user_id = p.user_id AND a.day = p.cohort_day
  LEFT JOIN sessions_day0 s  ON s.user_id = p.user_id
  LEFT JOIN play_day0 pl     ON pl.user_id = p.user_id
  LEFT JOIN active_days d1   ON d1.user_id = p.user_id AND d1.day = p.cohort_day + 1
  WHERE p.cohort_day + 1 <= CAST($last_full_day AS DATE)
    AND p.cohort_day NOT IN (CAST($gap_day AS DATE) - 1, CAST($gap_day AS DATE))
)
SELECT *, NTILE(4) OVER (ORDER BY play_events, user_id) AS play_quartile
FROM day0;
