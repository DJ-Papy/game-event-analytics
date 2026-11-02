"""End-to-end: the command line on a reproducible random dataset, and the CSV contract with Power BI."""
import pandas as pd
import pytest

from game_events.__main__ import main
from game_events.checks import run_checks
from game_events.data import connect_events
from game_events.queries import build_base_tables

# Columns read by dashboard/game-event-analytics.pbix: renaming or reordering them breaks the report.
DASHBOARD_CONTRACT = {
    "daily.csv": ["day", "active_players", "sessions", "new_players", "ad_impressions", "ad_revenue_usd", "note"],
    "retention_curve.csv": ["day_n", "players", "pct", "ci_low", "ci_high"],
    "retention_segments.csv": ["dimension", "day_n", "segment", "players", "pct", "ci_low", "ci_high"],
    "funnel_new_players.csv": ["step_order", "event", "players", "pct_of_first", "note",
                               "android_players", "pct_of_first_android"],
    "ads_by_format.csv": ["ad_format", "impressions", "revenue_usd", "ecpm_usd"],
    "ads_exposure_d1.csv": ["group", "bucket", "players", "d1_pct", "ci_low", "ci_high"],
    "experiment_ads_config.csv": ["variant", "players", "d1_pct", "interstitials_day0"],
    "kpis.csv": ["events", "players", "sessions", "new_players", "d1_pct", "d7_pct", "d14_pct",
                 "median_session_min", "ad_revenue_usd", "ad_revenue_per_active_player_day"],
}


@pytest.fixture(scope="module")
def exported(random_data, tmp_path_factory):
    out = tmp_path_factory.mktemp("dashboard")
    assert main(["build", "--data", random_data, "--out", str(out)]) == 0
    return out


@pytest.mark.parametrize("name", sorted(DASHBOARD_CONTRACT))
def test_dashboard_contract(exported, name):
    assert pd.read_csv(exported / name).columns.tolist() == DASHBOARD_CONTRACT[name]


def test_funnel_never_increases(exported):
    funnel = pd.read_csv(exported / "funnel_new_players.csv")
    assert funnel["players"].is_monotonic_decreasing
    assert funnel["android_players"].is_monotonic_decreasing


def test_rates_are_valid(exported):
    curve = pd.read_csv(exported / "retention_curve.csv")
    assert curve["pct"].between(0, 100).all()
    assert (curve["ci_low"] <= curve["pct"]).all() and (curve["pct"] <= curve["ci_high"]).all()


def test_gap_day_is_flagged(exported):
    daily = pd.read_csv(exported / "daily.csv")
    assert daily.loc[daily["day"] == "2025-03-27", "note"].item() == "unexplained drop"


def test_checks_report_the_truncated_file(random_data):
    con, readable, unreadable = connect_events(random_data)
    build_base_tables(con)
    report = run_checks(con, readable, unreadable).set_index("check")
    assert report.loc["readable Parquet files", "status"] == "warning"
    assert "part-00049" in report.loc["readable Parquet files", "detail"]
    assert (report["status"] != "error").all()


def test_inventory_hides_high_cardinality_values(random_data, tmp_path):
    assert main(["inventory", "--data", random_data, "--out", str(tmp_path)]) == 0
    props = pd.read_csv(tmp_path / "event_properties.csv", keep_default_na=False)
    assert set(props.loc[props["approx_distinct_values"] > 20, "example"]) <= {""}
    for name in ("event_inventory.csv", "user_properties.csv"):
        assert (tmp_path / name).exists()
