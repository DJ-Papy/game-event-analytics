-- First day of each new player: ad exposure, activity, and return on day 1.
-- Parameters: $last_full_day, $gap_day. Creates day0_q (one row per new player).
--
-- Players who play more see more ads and come back more, so exposure is only compared
-- within activity quartiles (gameplay events on day 0, from active_days).
-- user_id breaks NTILE ties so that quartiles are identical from one run to the next.
-- Cohorts whose day 0 or day 1 is the data gap are excluded.
CREATE OR REPLACE TABLE day0_q AS
WITH ads_by_day AS (
  SELECT
    user_id,
    day,
    COUNT(*) FILTER (WHERE ad_format = 'INTER')    AS inter,
    COUNT(*) FILTER (WHERE ad_format = 'REWARDED') AS rewarded
  FROM ads
  GROUP BY user_id, day
),
day0 AS (
  SELECT
    p.user_id,
    p.cohort_day,
    COALESCE(a.inter, 0)          AS inter_day0,
    COALESCE(a.rewarded, 0)       AS rewarded_day0,
    COALESCE(d0.sessions, 0)      AS sessions_day0,
    COALESCE(d0.play_events, 0)   AS play_events,
    (d1.user_id IS NOT NULL)      AS retained_d1
  FROM new_players p
  LEFT JOIN ads_by_day a   ON a.user_id = p.user_id AND a.day = p.cohort_day
  LEFT JOIN active_days d0 ON d0.user_id = p.user_id AND d0.day = p.cohort_day
  LEFT JOIN active_days d1 ON d1.user_id = p.user_id AND d1.day = p.cohort_day + 1
  WHERE p.cohort_day + 1 <= CAST($last_full_day AS DATE)
    AND p.cohort_day NOT IN (CAST($gap_day AS DATE) - 1, CAST($gap_day AS DATE))
)
SELECT *, NTILE(4) OVER (ORDER BY play_events, user_id) AS play_quartile
FROM day0;
