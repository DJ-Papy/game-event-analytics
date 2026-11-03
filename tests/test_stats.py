import pytest

from game_events import stats


def test_sample_size_for_two_points_of_d1():
    assert stats.sample_size_per_variant(0.383, 0.02) == 9361
    assert stats.sample_size_per_variant(0.383, 0.02, alpha=0.025) == 11336


def test_minimum_detectable_effect_with_1000_players():
    assert stats.minimum_detectable_effect(0.383, 1000) == pytest.approx(0.062, abs=5e-4)


def test_sample_ratio_mismatch():
    assert stats.srm_pvalue([1105, 1093, 1131]) == pytest.approx(0.712, abs=1e-3)
    assert stats.srm_pvalue([44700, 45489]) < 0.01


def test_newcombe_difference_matches_published_result():
    # AdsConfig_iOS, D1: Variant-B 408 / 1,028 against control 391 / 1,022 -> +1.4 points (-2.8 to +5.6)
    diff, lo, hi = stats.diff_vs_control(408, 1028, 391, 1022)
    assert (round(diff, 1), round(lo, 1), round(hi, 1)) == (1.4, -2.8, 5.6)
