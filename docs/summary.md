# Game Event Analytics: one-page summary

**Question.** Where do new players drop off, and does advertising help or hurt their return?
**Data.** 71 M events from a mobile game, 71,679 players, 28 Feb – 10 Apr 2025 (public Kaggle dataset, CC BY 4.0).

## What we found

1. **Most new players do not come back, although almost all of them get through the core progression.** 94.5% reach the first new zone, but only 37.0% return the next day (D1), 6.7% after a week (D7), 2.9% after two weeks (D14). The sample is large (about 44,000 players at D1), so the D1 figure is precise (36.6–37.5%). *Confidence: high.*
2. **iPhone players stay a little longer than Android players.** D1: 40.5% vs 35.6%. D7: 7.5% vs 6.4%. By D14 the gap is within the margin of error, so we do not conclude anything there. *Confidence: medium (the platforms may attract different players).*
3. **Players who see more interstitial ads on day 0 come back more, but this is not proof that ads help.** Heavy players see more ads *and* return more. When we compare players with similar activity, the gap shrinks a lot (most active quartile: 51.9% with no ad vs 58.6% with 6+ ads). We cannot say whether ads help or hurt. *Confidence: low for any causal claim.*
4. **Rewarded video earns about twice as much per impression as interstitials** (about $29 vs $14 per 1,000 views, network estimate). Total estimated ad revenue: $38,417, about $0.23 per active player per day.

## What we recommend

1. **Run a properly sized A/B test on interstitial frequency for new players.** The existing test (AdsConfig_iOS, about 1,000 players per variant) shows 38.3% / 38.3% / 39.7% D1 retention: it cannot separate the variants. Detecting a 2-point difference in D1 with 80% power needs about 9,400 players per variant (11,300 when two variants are compared with the control), against about 1,000 today (notebook 05).
2. **Fix three tracking gaps before the next analysis:** purchases are only recorded on Android, 10.4% of events have no session id, and the active-player count drops sharply on 27 March with no known cause.

## Limits to keep in mind

- Six weeks of data only: no long-term retention, no seasonality.
- Retention is measured on players with a first-open event, on days that are fully observed. A player counts as active on a day with any event; requiring a new session that day would lower D1 to 34.9%, only because sessions that continue past midnight would no longer count.
- Ad revenue is an ad-network estimate, and its level shifts by about 27% when the field was renamed in late March (real change or measurement change: not established).
- 27 March is a data gap of unknown cause; it is excluded from retention calculations.
- Purchases are tracked on Android only: 2.1% of Android new players buy; iPhone purchases are not visible.
