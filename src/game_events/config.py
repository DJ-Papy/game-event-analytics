"""Project settings: paths, analysis window and thresholds used by every module and notebook."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("GAME_EVENTS_ROOT", Path(__file__).resolve().parents[2]))

RAW_EVENTS = ROOT / "data" / "raw" / "player_analytics" / "*.parquet"
SQL_DIR = ROOT / "sql"
DASHBOARD_DATA = ROOT / "dashboard" / "data"
DOCS = ROOT / "docs"

# Analysis window. The data runs from 2025-02-28 05:58 to 2025-04-10 20:37 (UTC assumed).
FIRST_DAY = "2025-02-28"
LAST_FULL_DAY = "2025-04-09"
PARTIAL_DAYS = ("2025-02-28", "2025-04-10")

# 2025-03-27: active players fall by about 60% in every app version, cause unknown.
# A retention or exposure measured on that day would look like churn, so it is excluded.
GAP_DAY = "2025-03-27"

# Day used for the duplicate check (an exact check on all 71M ids needs too much memory).
DUPLICATE_CHECK_DAY = "2025-03-15"

# Segments below this size give unstable rates and are not reported.
MIN_SEGMENT_PLAYERS = 500

FUNNEL_STEPS = ("gameOpened", "tokenCashout", "deviceUnlocked", "zoneUnlocked", "purchaseCompleted")

EXPERIMENT = "AdsConfig_iOS"
CONTROL_VARIANT = "Control-Variant"

DUCKDB_MEMORY_LIMIT = "2GB"
