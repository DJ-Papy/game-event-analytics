-- =====================================================================
-- Funnel of new players over the core progression
-- Engine: DuckDB | Needs: events view, new_players (01_base_tables.sql)
-- =====================================================================

-- Steps: gameOpened -> tokenCashout -> deviceUnlocked -> zoneUnlocked
--        -> purchaseCompleted.
-- A player reaches step k if they reached step k-1 and their first event
-- of step k happened at or after their first event of step k-1.
-- purchaseCompleted is only tracked on Android (docs/tracking_plan.md),
-- so the Android counts are given next to the totals.

WITH firsts AS (
  -- first time of each step, one row per new player (pivot with FILTER)
  SELECT
    e.user_id,
    MIN(e.ts) FILTER (WHERE e.event_name = 'gameOpened')        AS t1,
    MIN(e.ts) FILTER (WHERE e.event_name = 'tokenCashout')      AS t2,
    MIN(e.ts) FILTER (WHERE e.event_name = 'deviceUnlocked')    AS t3,
    MIN(e.ts) FILTER (WHERE e.event_name = 'zoneUnlocked')      AS t4,
    MIN(e.ts) FILTER (WHERE e.event_name = 'purchaseCompleted') AS t5
  FROM events e
  JOIN new_players p USING (user_id)
  WHERE e.event_name IN ('gameOpened', 'tokenCashout', 'deviceUnlocked',
                         'zoneUnlocked', 'purchaseCompleted')
  GROUP BY e.user_id
),

reached AS (
  -- last step reached in order (a NULL comparison counts as "not reached")
  SELECT
    f.user_id,
    p.platform,
    CASE
      WHEN t1 IS NULL                     THEN 0
      WHEN NOT COALESCE(t2 >= t1, FALSE)  THEN 1
      WHEN NOT COALESCE(t3 >= t2, FALSE)  THEN 2
      WHEN NOT COALESCE(t4 >= t3, FALSE)  THEN 3
      WHEN NOT COALESCE(t5 >= t4, FALSE)  THEN 4
      ELSE 5
    END AS last_step
  FROM firsts f
  JOIN new_players p USING (user_id)
),

steps(step_order, event) AS (
  VALUES (1, 'gameOpened'), (2, 'tokenCashout'), (3, 'deviceUnlocked'),
         (4, 'zoneUnlocked'), (5, 'purchaseCompleted')
)

SELECT
  s.step_order,
  s.event,
  COUNT(*) FILTER (WHERE r.last_step >= s.step_order)                          AS players,
  COUNT(*) FILTER (WHERE r.last_step >= s.step_order AND r.platform = 'Android') AS android_players
FROM steps s
CROSS JOIN reached r
GROUP BY s.step_order, s.event
ORDER BY s.step_order;
