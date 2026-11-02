-- =====================================================================
-- First-day ad exposure, first-day activity and D1 return of new players
-- Engine: DuckDB | Needs: events view, new_players, ads, active_days
-- Parameters: $last_full_day ('2025-04-09'), $gap_day ('2025-03-27')
-- Creates the table day0_q, one row per new player.
-- =====================================================================

-- Exposure  = interstitials seen on the first day.
-- Activity  = gameplay events on the first day (platform events starting
--             with "_", ad events and app background/focus are not gameplay).
-- Outcome   = active the next day (D1).
-- Players who play more see more ads and come back more: the activity
-- quartile (NTILE) is used to compare players with a similar level of play.
-- Many players have the same number of events: user_id breaks the ties, so
-- that a player always falls in the same quartile from one run to the next.
-- Cohorts whose day 0 or day 1 is the data gap are left out.
CREATE OR REPLACE TABLE day0_q AS
WITH inter_day0 AS (
  SELECT user_id, day, COUNT(*) AS inter
  FROM ads
  WHERE ad_format = 'INTER'
  GROUP BY user_id, day
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
    COALESCE(a.inter, 0)          AS inter_day0,
    COALESCE(pl.play_events, 0)   AS play_events,
    (d1.user_id IS NOT NULL)      AS retained_d1
  FROM new_players p
  LEFT JOIN inter_day0 a  ON a.user_id = p.user_id AND a.day = p.cohort_day
  LEFT JOIN play_day0 pl  ON pl.user_id = p.user_id
  LEFT JOIN active_days d1 ON d1.user_id = p.user_id AND d1.day = p.cohort_day + 1
  WHERE p.cohort_day + 1 <= CAST($last_full_day AS DATE)
    AND p.cohort_day NOT IN (CAST($gap_day AS DATE) - 1, CAST($gap_day AS DATE))
)
SELECT *, NTILE(4) OVER (ORDER BY play_events, user_id) AS play_quartile
FROM day0;
