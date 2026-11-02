# Tracking plan (observed from the data)

This plan describes what the game **actually tracks**, as seen in 70.9 million events from 71,679 players (2025-02-28 to 2025-04-10). It was built from the files `event_inventory.csv`, `event_properties.csv` and `user_properties.csv`, produced by `python -m game_events inventory` (also run in `notebooks/04_tracking_inventory.ipynb`).

**Counts.** Distinct counts quoted in this plan are exact (full scan for event properties, seeded 1% sample for player properties). The `approx_distinct_values` column of `event_properties.csv` is a fast estimate and can differ by a few percent.

**Reading rule.** Names, volumes, properties and dates are observed. The column *Inferred trigger* and the *Use* column are interpretations of the event names and properties: the game's code and design documents were not available, so they must be confirmed with the game team.

## 1. What every event carries

| Field | Content | Note |
|---|---|---|
| `event_id` | Unique event id | No duplicate found on 2025-03-15 |
| `event_name` | One of 66 names | See section 3 |
| `ts` | Event time (UTC assumed) | Cast from the raw `event_timestamp` text |
| `user_id` | Player id | 71,679 distinct |
| `user_session_id` | Session id | **Empty for 10.4% of events** (see section 4) |
| `user_session_count` | Session counter | Not reliable: changes within a session, 0 on many first events |
| `client_platform`, `country_code` | Device platform, country | 31,977 rows without platform |
| `event_properties` | Text map of event-specific properties | All values are text |
| `user_properties_custom` | Text map of player attributes | See below |

Other raw columns: `event_receive_time` (dates before `ts` in the rows inspected: do not use), `processing_time`, `user_session_issued_at`.

### Player properties (`user_properties_custom`, 1% sample of events)

| Property | Filled on | Distinct values | Note |
|---|---|---|---|
| `currentMap` | 99.8% | 7 | Current map of the player |
| `appVersion` | 99.6% | 19 | Used to follow releases |
| `noAdsOwned`, `robotOwned` | 99.6% | 2 | Ownership flags |
| `fbInstallationId`, `adjustId` | 99.6% | about 54,000 in the sample | Third-party identifiers: do not publish |
| `dbChurnPrediction` | 24.2% | 23,860 | Looks like a predicted score; only on some events |
| `dbPurchasePrediction` | 1.4% | 648 | Looks like a predicted score; rare |

The two prediction properties are not fully documented: check how they are computed before using them as features of an analysis, since they may already use player behaviour.

## 2. Events by domain

Volumes are events (players). *Inferred trigger* and *Use* are interpretations.

### Session and app lifecycle

| Event | Volume | Main properties | Inferred trigger | Use |
|---|---|---|---|---|
| `_sessionStart` | 286,686 (71,574) | `session_id`, `identity_id`, `session_origin` | A session opens (platform service) | Session counts |
| `_identityCreate` | 51,743 (50,881) | `identity_id` | An identity is created | Install check (compared with `firstOpen`) |
| `firstOpen` | 48,308 (48,307) | none | First launch after install | **New-player cohorts** |
| `gameOpened` | 258,690 (68,881) | none | The game is opened | Start of play |
| `gameClosed` | 32,851 (10,168) | none | The game is closed | Only 12.7% of `gameOpened`: not a reliable session end |
| `appBackground`, `appFocus` | 4.2 M, 3.6 M | `timeStamp`, `onAppBackground` / `onAppFocus` | App goes to background / returns | Away time; keeps sessions open |
| `_propertiesUpdate` | 412,485 (33,495) | none | Player properties updated | Starts 2025-03-24 |
| `notificationPermission` | 277 (213) | `response`, `requestPoint` | Permission prompt answered | Rare |
| `screenViewed` | 25,875 (8,500) | `screenName`, `screenBefore` | A screen is displayed | Navigation (few players) |

### Core loop (customers, devices, money)

| Event | Volume | Main properties | Inferred trigger | Use |
|---|---|---|---|---|
| `tokenCashout` | 9.4 M (64,318) | `moneyId`, `mapId`, token counts, `moneyEarned`, `moneyInWallet`, `dayState`, `numberOfDay` | Tokens are cashed out | Core activity, earnings |
| `transferMoney` | 3.9 M (63,927) | `transferMoney`, `remainingMoneyInStack`, `totalMoneyInStack` | Money moves from stack to wallet | Core activity |
| `lostCustomer` | 6.6 M (58,866) | `numberOfBrokenDevices`, `numberOfUnlockDevices`, `moneyInWallet` | A customer leaves | Friction in the loop |
| `badCustomerEntered`, `badCustomerResult` | 1.8 M, 2.1 M | `day`, `slapped` | A difficult customer appears / is dealt with | Mini-event engagement |
| `deviceBroken`, `deviceRepair` | 3.2 M, 3.0 M | `deviceId`, `deviceLevel`, timestamps, `moneyInWallet` | A device breaks / is repaired | Difficulty and economy |
| `endOfDay`, `endOfNight` | 876 K, 836 K | `numberOfDay` / `numberOfNight`, money, customers, `internetConnection` | A game day / night ends | Pace, in-game progress |

### Progression

| Event | Volume | Main properties | Inferred trigger | Use |
|---|---|---|---|---|
| `deviceUnlocked`, `deviceUpgrade` | 893 K, 1.8 M | `deviceId`, `deviceLevel`, `progressCount`, `prestigeLevel`, `mapId` | A device is unlocked / upgraded | Funnel steps |
| `unlockProgression`, `upgradeProgression` | 1.0 M, 1.8 M | `progressCount`, `totalProgressCount`, `prestigeLevel` | Progress counters change | Progress measure |
| `zoneUnlocked` | 137,472 (57,007) | `zoneId`, `mapId`, `numberOfDay`, `prestigeLevel` | A zone opens | Funnel step |
| `helperUnlocked`, `playerAbilityClaimed` | 64,743; 184,939 | `helperId`, `claimType`; `playerLevel`, `centerLevel` | Helper / ability obtained | Optional features |
| `achievementUpdated`, `achievementClaimed` | 3.5 M; 155,432 | `achievement_id` | Achievement progress / claimed | Always without session id |
| `gamerRoadClaimed` | 42,029 (12,256) | `rewardLevel`, `gamerRoadLevel`, `rewardType` | A pass reward is claimed | Pass usage |
| `boosterClaimed`, `offerClaim` | 291 K; 388 K | `boosterType` / `rewardType`, `claimType`, `gemInWallet` | A booster or offer is claimed (often via rewarded video) | Reward use |
| `skinOpened`, `skinActivated` | 184 K; 50 K | `openedSkin`, `activatedSkin` | Skin screen / skin chosen | Cosmetics |
| `buttonClick` | 312,980 (45,362) | `buttonName` (45 values), `mapId`, `dayState` | A button is pressed | UI use |
| `hapticOnOff`, `musicOnOff`, `soundOnOff` | 19 K, 13 K, 13 K | `...State`, `timeStamp` | A setting is toggled | Settings |

### Economy

| Event | Volume | Main properties | Inferred trigger | Use |
|---|---|---|---|---|
| `currencyGranted`, `currencySpent` | 1.9 M; 1.5 M | `currency_id` (10 values), `source` | Currency earned / spent | Economy balance; always without session id |
| `itemsGranted` | 234,525 | `item_id`, `source` | Items given | Always without session id |
| `energyModifierGranted` | 429 | `energy_modifier_id`, `duration_sec`, `source` | A no-ads energy modifier is granted | Linked to the no-ads purchase |

### Advertising

| Event | Volume | Main properties | Inferred trigger | Use |
|---|---|---|---|---|
| `adImpression` | 1.9 M (59,698) | `adFormat` (INTER / REWARDED), `adSource` (9), `adUnitName`, `currency`, revenue under `value` then `amount`, `placement` | An ad is displayed and paid | **Revenue and exposure** |
| `adsStart`, `adsReturned` | 1.78 M each | `adType`, `mapId`, `timeStamp` | An interstitial starts / the player returns | Time spent in ads |
| `interstitialLifecycle`, `rvLifecycle` | 5.1 M; 4.5 M | `state`, `errorInfo`, `id` | Ad load / display states | Delivery quality |
| `rvRewardClaim` | 498,847 (28,327) | `adPlacement` (87), `tRvInSession`, `tPlacementInSession`, `mapId` | Reward given after a rewarded video | **Starts 2025-03-12** |

### Purchases

| Event | Volume | Main properties | Inferred trigger | Use |
|---|---|---|---|---|
| `purchaseCompleted` | 1,639 (935) | `productName` (16), `sku`, `amount`, `currency` (20), `amountInUsd` (empty), `source` | An in-app purchase completes | Purchases (Android only: see section 3); the receipt fields must never be published |
| `inAppPurchase` | 411 (264) | same properties | Same kind of event | **Last seen 2025-03-21**, probably replaced by `purchaseCompleted` (not verified) |
| `starterPack`, `superStarterPack`, `specialPack`, `standardPack`, `gem1` to `gem6`, `robot`, `robot3Days`, `noAds`, `noAds24Hours`, `noAds24HoursOffer`, `gamerRoadPremium` | 15 to 926 each | none observed beyond the name | One event per product | Product-named events: see section 4 |

### Experiments

| Event | Volume | Main properties | Inferred trigger | Use |
|---|---|---|---|---|
| `_experimentJoin` | 3,379 (3,329) | `experiment_name`, `experiment_variant_name` (3 variants), phase and variant ids | A player is assigned to an experiment | A/B analysis; starts 2025-03-07. One experiment seen: `AdsConfig_iOS` |

## 3. Quality findings (observed)

1. **No session id on 10.4% of events.** `achievementUpdated`, `currencyGranted`, `currencySpent`, `itemsGranted`, `achievementClaimed`, `_identityCreate`, `_experimentJoin` and `energyModifierGranted` always have an empty `user_session_id`. These events cannot be attached to a session without a time join.
2. **A property was renamed during the window.** The ad revenue is under `value` on 69.6% of impressions (from 2025-02-28) and under `amount` on 30.4% (from 2025-03-24). The two never appear together in the data checked. A query that reads only `amount` loses most of the revenue.
3. **Numbers are text, in several formats.** Decimal separators are a dot, a comma or a slash; `amount` can use scientific notation. Every numeric property needs cleaning before use.
4. **`amountInUsd` is empty on every purchase.** Purchase amounts come in 20 currencies, so revenue from purchases cannot be summed without exchange rates.
5. **`adImpression.placement` is always empty.** Where the ad was shown cannot be recovered from this event (`rvRewardClaim.adPlacement` has 87 values, but exists only from 2025-03-12).
6. **Free-text error messages.** `errorInfo` has about 450 distinct values, many of them network messages in several languages.
7. **Product names used as event names.** Sixteen events (`gem1`, `noAds24Hours`, `starterPack`, ...) are named after a product, while `purchaseCompleted` already exists. Whether they duplicate `purchaseCompleted` is not verified: compare counts before summing purchases.
8. **Events added or stopped inside the window.** `_experimentJoin` (from 2025-03-07), `rvRewardClaim` (2025-03-12), `_propertiesUpdate` (2025-03-24), `inAppPurchase` (stops 2025-03-21). Comparisons across these dates mix different tracking.
9. **A data gap on 2025-03-27.** Active players fall by about 60% in every app version. The cause is not known.
10. **App closing is poorly tracked.** `gameClosed` has about 13% of the volume of `gameOpened`, and sessions have no end event, so a session's length is the gap between its first and last event (background time may be included).
11. **Purchases are tracked for Android only in `purchaseCompleted` and `inAppPurchase`.** Both events only appear with the platform `Android` (store `GooglePlay`). iPhone players (14,285 new players) have none, yet product-named events exist for them (1,014 events from 557 players, against 3,684 events from 934 players on Android). The funnel and any purchase rate based on `purchaseCompleted` therefore ignore iPhone purchases. What the product-named events mean exactly is not documented.
12. **Timestamps.** `event_receive_time` is earlier than `ts` in the rows inspected, which is unexpected for a reception time; and several events carry their own `timeStamp` property whose unit was not checked.

## 4. Events and properties to add

Five or six solid proposals rather than a long list. Names follow the convention in section 5.

| Proposal | Trigger | Properties | Question it answers |
|---|---|---|---|
| `tutorialStep` | Each step of the first-time experience | `step_id`, `step_name`, `result` | Where do new players stall? The observed funnel shows 95% reaching the first zone, so its steps do not discriminate. |
| `sessionEnd` | App closed or session timed out | `reason`, `duration_s` | Reliable session length, without background time. |
| `offerShown` | An offer or purchase popup is displayed | `offer_id`, `placement`, `price_usd` | Conversion of offers. Today only the purchase (1.5% of new players) is visible, not the number of players who saw an offer. |
| `adOpportunity` | A moment where an ad could be shown | `format`, `placement`, `shown` (true / false), `reason_not_shown` | Ad frequency, eligibility and revenue lost; fixes the empty `placement`. |
| Normalised purchase | `purchaseCompleted` | `amount_usd` always filled, a single event with `product_id` | Revenue by product; retire product-named events. |
| Experiment variant on the player | `user_properties_custom` | `experiment_variant` | Analyse an A/B test without joining on `_experimentJoin`. |

Also: a single, documented decimal format for amounts, and one session id on every event (or an explicit `session_id` property on server-side events).

## 5. Naming convention (proposal)

- One style for events (lower camel case already covers 52 of 66 names) and one for properties (the current mix includes `timeStamp`, `timestamp`, `session_id`, `numberOfDay`).
- A leading underscore for platform events only (`_sessionStart`, `_identityCreate`, `_experimentJoin`, `_propertiesUpdate`), as today.
- Product, level or zone identifiers go in a property, not in the event name.
- Numbers as numbers, flags as booleans; free text only where unavoidable.

## 6. Limits of this plan

- Built from one six-week window; events or properties that never fire in it are invisible.
- Property lists are complete for events (full scan) and sampled at 1% for player properties.
- Example values are given only for low-cardinality properties; no identifiers or receipts are stored in `docs/`.
