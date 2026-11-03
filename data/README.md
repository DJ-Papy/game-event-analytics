# Data source

**Player Analytics Event Stream Data** (livestream events from a mobile game), Kaggle.

- URL: https://www.kaggle.com/datasets/zburns/player-analytics-dataset
- Licence: CC BY 4.0, as shown on the Kaggle page on the download date. Only aggregated tables and documentation are published here; no raw event is redistributed.
- Downloaded on: 2026-11-01
- Format: 68 Parquet files, about 3.3 GB, in `data/raw/player_analytics/` (not committed: too large for git)
- Content: about 71 million events, 71,679 players, about 275,700 sessions, from 2025-02-28 to 2025-04-10.

## Known issue

`part-00049-….parquet` has a valid header but no footer, so DuckDB cannot read it (file truncated).
It is skipped in all analyses. The drop in daily active players on 2025-03-27 (about 1,400 against
3,500-4,500 on other days) is **not explained**: the files are not in chronological order, so there is no
evidence that the truncated file is the cause. The same file size was found when downloading again, so the
defect is probably in the source dataset itself.
