import pytest

from game_events.data import connect_events
from game_events.queries import build_base_tables

from .factory import event, random_events, write_parquet

T0 = "2025-03-01 10:00:00"


def small_events():
    """Hand-made players whose retention, funnel and revenue are known exactly."""
    return [
        # A: Android, comes back on day 1, goes through the whole funnel, sees 2 interstitials on day 0
        event("A", "firstOpen", T0, "sA1"),
        event("A", "gameOpened", "2025-03-01 10:01:00", "sA1"),
        event("A", "tokenCashout", "2025-03-01 10:02:00", "sA1"),
        event("A", "deviceUnlocked", "2025-03-01 10:03:00", "sA1"),
        event("A", "zoneUnlocked", "2025-03-01 10:04:00", "sA1"),
        event("A", "purchaseCompleted", "2025-03-01 10:05:00", "sA1"),
        event("A", "adImpression", "2025-03-01 10:06:00", "sA1", props={"adFormat": "INTER", "value": "0,0141"}),
        event("A", "adImpression", "2025-03-01 10:07:00", "sA1", props={"adFormat": "INTER", "value": "0/0096"}),
        event("A", "_sessionStart", "2025-03-02 09:00:00", "sA2"),
        # B: iPhone, only a server-side event on day 1 (no session), cashes out before opening the game
        event("B", "firstOpen", T0, "sB1", platform="IPhonePlayer", country="US"),
        event("B", "tokenCashout", "2025-03-01 09:59:00", "sB1", platform="IPhonePlayer", country="US"),
        event("B", "gameOpened", "2025-03-01 10:01:00", "sB1", platform="IPhonePlayer", country="US"),
        event("B", "adImpression", "2025-03-01 10:06:00", "sB1", platform="IPhonePlayer", country="US",
              props={"adFormat": "REWARDED", "amount": "1.5E-03"}),
        event("B", "achievementUpdated", "2025-03-02 09:00:00", "", platform="IPhonePlayer", country="US"),
        # C: Android, never comes back, stops at the third step
        event("C", "firstOpen", T0, "sC1"),
        event("C", "gameOpened", "2025-03-01 10:01:00", "sC1"),
        event("C", "tokenCashout", "2025-03-01 10:02:00", "sC1"),
        event("C", "deviceUnlocked", "2025-03-01 10:03:00", "sC1"),
        event("C", "adImpression", "2025-03-01 10:06:00", "sC1", props={"adFormat": "INTER", "amount": "abc"}),
        # D: day 1 falls on the data gap -> excluded from D1
        event("D", "firstOpen", "2025-03-26 10:00:00", "sD1"),
        event("D", "_sessionStart", "2025-03-27 10:00:00", "sD2"),
        # E: day 1 is not fully observed -> excluded from D1
        event("E", "firstOpen", "2025-04-09 10:00:00", "sE1"),
        # F: no firstOpen (installed before the window) -> not a new player
        event("F", "_sessionStart", T0, "sF1"),
    ]


@pytest.fixture
def small_con(tmp_path):
    write_parquet(small_events(), tmp_path / "part-00000.parquet")
    con, _, _ = connect_events(tmp_path / "*.parquet")
    build_base_tables(con)
    return con


@pytest.fixture(scope="session")
def random_data(tmp_path_factory):
    """Glob of a reproducible random dataset (two files plus one truncated file)."""
    folder = tmp_path_factory.mktemp("events")
    rows = random_events()
    half = len(rows) // 2
    write_parquet(rows[:half], folder / "part-00000.parquet")
    write_parquet(rows[half:], folder / "part-00001.parquet")
    raw = (folder / "part-00000.parquet").read_bytes()
    (folder / "part-00049.parquet").write_bytes(raw[: len(raw) // 2])
    return str(folder / "*.parquet")
