-- Funnel over the core progression, for the players of the view `funnel_population`
-- (user_id, platform), created by game_events.metrics.funnel.
--
-- A step counts only if its first occurrence comes at or after the first occurrence of the
-- previous step. purchaseCompleted is tracked on Android only, hence the Android counts.
WITH firsts AS (
  SELECT
    e.user_id,
    MIN(e.ts) FILTER (WHERE e.event_name = 'gameOpened')        AS t1,
    MIN(e.ts) FILTER (WHERE e.event_name = 'tokenCashout')      AS t2,
    MIN(e.ts) FILTER (WHERE e.event_name = 'deviceUnlocked')    AS t3,
    MIN(e.ts) FILTER (WHERE e.event_name = 'zoneUnlocked')      AS t4,
    MIN(e.ts) FILTER (WHERE e.event_name = 'purchaseCompleted') AS t5
  FROM events e
  JOIN funnel_population USING (user_id)
  WHERE e.event_name IN ('gameOpened', 'tokenCashout', 'deviceUnlocked',
                         'zoneUnlocked', 'purchaseCompleted')
  GROUP BY e.user_id
),

reached AS (
  SELECT
    f.user_id,
    p.platform,
    CASE
      WHEN t1 IS NULL                    THEN 0
      WHEN NOT COALESCE(t2 >= t1, FALSE) THEN 1
      WHEN NOT COALESCE(t3 >= t2, FALSE) THEN 2
      WHEN NOT COALESCE(t4 >= t3, FALSE) THEN 3
      WHEN NOT COALESCE(t5 >= t4, FALSE) THEN 4
      ELSE 5
    END AS last_step
  FROM firsts f
  JOIN funnel_population p USING (user_id)
),

steps(step_order, event) AS (
  VALUES (1, 'gameOpened'), (2, 'tokenCashout'), (3, 'deviceUnlocked'),
         (4, 'zoneUnlocked'), (5, 'purchaseCompleted')
)

SELECT
  s.step_order,
  s.event,
  COUNT(*) FILTER (WHERE r.last_step >= s.step_order)                            AS players,
  COUNT(*) FILTER (WHERE r.last_step >= s.step_order AND r.platform = 'Android') AS android_players
FROM steps s
CROSS JOIN reached r
GROUP BY s.step_order, s.event
ORDER BY s.step_order;
