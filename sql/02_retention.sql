-- Day-N retention of new players, overall or by segment.
-- Parameters: $day_n, $dimension ('all' | 'platform' | 'country'),
--             $activity ('any_event' | 'session_start'), $last_full_day, $gap_day.
--
-- Retained on day N = active exactly N days after the cohort day.
-- Only cohorts whose day N is fully observed are counted, and day N never falls on the
-- data gap: in both cases missing data would be read as churn.
SELECT
  CASE CAST($dimension AS VARCHAR)
    WHEN 'platform' THEN p.platform
    WHEN 'country'  THEN p.country
    ELSE 'all'
  END              AS segment,
  COUNT(*)         AS players,
  COUNT(a.user_id) AS retained
FROM new_players p
LEFT JOIN active_days a
       ON a.user_id = p.user_id
      AND a.day = p.cohort_day + CAST($day_n AS INTEGER)
      AND (CAST($activity AS VARCHAR) = 'any_event' OR a.session_started)
WHERE p.cohort_day + CAST($day_n AS INTEGER) <= CAST($last_full_day AS DATE)
  AND p.cohort_day + CAST($day_n AS INTEGER) <> CAST($gap_day AS DATE)
GROUP BY segment
ORDER BY segment;
