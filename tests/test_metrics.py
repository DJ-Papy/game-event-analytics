from game_events import metrics
from game_events.queries import build_day0_exposure


def test_new_players_exclude_players_without_first_open(small_con):
    players = {r[0] for r in small_con.execute("SELECT user_id FROM new_players").fetchall()}
    assert players == {"A", "B", "C", "D", "E"}


def test_d1_counts_only_observable_cohorts_and_skips_the_gap(small_con):
    d1 = metrics.retention(small_con, 1).iloc[0]
    # D (day 1 = data gap) and E (day 1 after the last full day) are not counted
    assert (d1.players, d1.retained, d1.pct) == (3, 2, 66.7)


def test_strict_activity_ignores_server_side_events(small_con):
    d1 = metrics.retention(small_con, 1, activity="session_start").iloc[0]
    assert (d1.players, d1.retained) == (3, 1)        # B only had a server-side event


def test_retention_by_platform(small_con):
    df = metrics.retention_by(small_con, "platform", days=(1,), min_players=1)
    got = {r.segment: (r.players, r.retained) for r in df.itertuples()}
    assert got == {"Android": (2, 1), "IPhonePlayer": (1, 1)}


def test_funnel_requires_steps_in_order(small_con):
    df = metrics.funnel(small_con, population="new")
    assert df["players"].tolist() == [3, 2, 2, 1, 1]          # B cashed out before opening the game
    assert df["android_players"].tolist() == [2, 2, 2, 1, 1]
    assert df["pct_of_first"].tolist() == [100.0, 66.7, 66.7, 33.3, 33.3]


def test_funnel_all_players(small_con):
    assert metrics.funnel(small_con, population="all")["players"].tolist() == [3, 2, 2, 1, 1]


def test_ad_revenue_parsing(small_con):
    got = dict(small_con.execute("SELECT amount_text, amount_usd FROM ads").fetchall())
    assert got == {"0,0141": 0.0141, "0/0096": 0.0096, "1.5E-03": 0.0015, "abc": None}


def test_d1_by_exposure(small_con):
    build_day0_exposure(small_con)
    df = metrics.d1_by_exposure(small_con, "inter_day0").set_index("bucket")
    assert (df.loc["0", "players"], df.loc["0", "d1_pct"]) == (1, 100.0)
    assert (df.loc["1-2", "players"], df.loc["1-2", "d1_pct"]) == (2, 50.0)
    assert df.loc["6+"].isna()["players"]                     # empty bucket listed when complete=True


def test_activity_quartiles_are_reproducible(small_con):
    build_day0_exposure(small_con)
    first = small_con.execute("SELECT user_id, play_quartile FROM day0_q ORDER BY user_id").fetchall()
    build_day0_exposure(small_con)
    assert small_con.execute("SELECT user_id, play_quartile FROM day0_q ORDER BY user_id").fetchall() == first


def test_wilson_interval_matches_published_d1():
    # D1 before the gap was excluded: 16,554 of 45,353 new players, published as 36.1-36.9%
    assert metrics.wilson_pct(16554, 45353) == (36.1, 36.9)
