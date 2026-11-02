-- Players of one experiment, with the variant of their first join. Parameter: $experiment.
-- joins and variants_seen check for contamination: a player who saw two variants would
-- make the comparison unreliable.
CREATE OR REPLACE TABLE exp_players AS
SELECT
  user_id,
  MIN(ts)                                                     AS join_ts,
  CAST(MIN(ts) AS DATE)                                       AS join_day,
  ARG_MIN(event_properties['experiment_variant_name'], ts)    AS variant,
  COUNT(*)                                                    AS joins,
  COUNT(DISTINCT event_properties['experiment_variant_name']) AS variants_seen
FROM events
WHERE event_name = '_experimentJoin'
  AND event_properties['experiment_name'] = CAST($experiment AS VARCHAR)
GROUP BY user_id;
