-- =====================================================================
-- Day-N retention of new players, for one value of N
-- Engine: DuckDB | Needs: new_players, active_days (01_base_tables.sql)
-- Parameters:
--   $day_n          number of days after the first day (1, 7, 14, ...)
--   $dimension      'all', 'platform' or 'country'
--   $last_full_day  last fully observed day ('2025-04-09')
--   $gap_day        day with missing data ('2025-03-27')
-- =====================================================================

-- A player is retained on day N if they are active exactly N days after
-- their first day (cohort_day). Two filters keep the rate honest:
--   * only cohorts whose day N is fully observed are counted, otherwise
--     recent players would look like churn;
--   * day N must not fall on the data gap, for the same reason.
-- COUNT(a.user_id) only counts the players found by the LEFT JOIN.
SELECT
  CASE CAST($dimension AS VARCHAR)
    WHEN 'platform' THEN p.platform
    WHEN 'country'  THEN p.country
    ELSE 'all'
  END                AS segment,
  COUNT(*)           AS players,
  COUNT(a.user_id)   AS retained
FROM new_players p
LEFT JOIN active_days a
       ON a.user_id = p.user_id
      AND a.day = p.cohort_day + CAST($day_n AS INTEGER)
WHERE p.cohort_day + CAST($day_n AS INTEGER) <= CAST($last_full_day AS DATE)
  AND p.cohort_day + CAST($day_n AS INTEGER) <> CAST($gap_day AS DATE)
GROUP BY segment
ORDER BY segment;
