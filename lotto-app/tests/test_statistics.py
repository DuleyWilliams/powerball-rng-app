import statistics as pystats

import pytest
from scipy.stats import chisquare, hypergeom

from analytics_engine.statistics import (
    expected_white_ball_frequency,
    expected_powerball_frequency,
    white_ball_frequency_distribution,
    powerball_frequency_distribution,
    white_ball_chi_square,
    powerball_chi_square,
    white_ball_sum_statistics,
    odd_even_distribution,
    low_high_distribution,
    frequency_by_range,
)

# 3 draws, hand-verified below. Same shape convention as other analytics tests:
# [ball1..ball5, powerball].
DRAWS = [
    [1, 2, 3, 4, 5, 10],
    [1, 2, 6, 7, 8, 10],
    [9, 10, 11, 12, 13, 20],
]


def test_expected_white_ball_frequency():
    assert expected_white_ball_frequency(DRAWS) == pytest.approx((3 * 5) / 69)
    assert expected_white_ball_frequency([]) == 0.0


def test_expected_powerball_frequency():
    assert expected_powerball_frequency(DRAWS) == pytest.approx(3 / 26)
    assert expected_powerball_frequency([]) == 0.0


def test_white_ball_frequency_distribution_shape_and_known_values():
    rows = white_ball_frequency_distribution(DRAWS)
    by_number = {row.number: row for row in rows}

    assert len(rows) == 69
    assert by_number[1].observed_count == 2
    assert by_number[14].observed_count == 0

    expected_count = (3 * 5) / 69
    assert by_number[1].expected_count == pytest.approx(expected_count)
    assert by_number[1].deviation == pytest.approx(2 - expected_count)

    # Confidence interval must bracket the observed proportion and stay in [0, 1].
    row = by_number[1]
    assert 0.0 <= row.ci_lower <= row.observed_proportion <= row.ci_upper <= 1.0


def test_powerball_frequency_distribution_known_values():
    rows = powerball_frequency_distribution(DRAWS)
    by_number = {row.number: row for row in rows}

    assert len(rows) == 26
    assert by_number[10].observed_count == 2
    assert by_number[20].observed_count == 1
    assert by_number[1].observed_count == 0


def test_white_ball_chi_square_matches_scipy_and_reports_dof():
    observed = [f.observed_count for f in white_ball_frequency_distribution(DRAWS)]
    expected_stat, expected_p = chisquare(f_obs=observed, f_exp=[sum(observed) / len(observed)] * len(observed))

    result = white_ball_chi_square(DRAWS)

    assert result.statistic == pytest.approx(expected_stat)
    assert result.p_value == pytest.approx(expected_p)
    assert result.degrees_of_freedom == 68
    assert result.is_significant == (expected_p < 0.05)


def test_powerball_chi_square_matches_scipy_and_reports_dof():
    observed = [f.observed_count for f in powerball_frequency_distribution(DRAWS)]
    expected_stat, expected_p = chisquare(f_obs=observed, f_exp=[sum(observed) / len(observed)] * len(observed))

    result = powerball_chi_square(DRAWS)

    assert result.statistic == pytest.approx(expected_stat)
    assert result.p_value == pytest.approx(expected_p)
    assert result.degrees_of_freedom == 25


def test_chi_square_handles_empty_draws_without_crashing():
    result = white_ball_chi_square([])
    assert result.statistic == 0.0
    assert result.p_value == 1.0
    assert result.is_significant is False


def test_white_ball_sum_statistics_known_values():
    sums = [15, 24, 55]  # 1+2+3+4+5, 1+2+6+7+8, 9+10+11+12+13
    result = white_ball_sum_statistics(DRAWS, bucket_width=20)

    assert result.sample_size == 3
    assert result.minimum == 15
    assert result.maximum == 55
    assert result.mean == pytest.approx(pystats.mean(sums))
    assert result.std_dev == pytest.approx(pystats.stdev(sums))
    assert result.median == pystats.median(sums)
    assert sum(bucket.count for bucket in result.buckets) == 3

    lower, upper = result.confidence_interval_95
    assert lower < result.mean < upper


def test_white_ball_sum_statistics_empty_draws():
    result = white_ball_sum_statistics([])
    assert result.sample_size == 0
    assert result.buckets == []


def test_odd_even_distribution_known_values_and_expected_matches_hypergeom():
    # [1,2,3,4,5] -> 3 odd; [1,2,6,7,8] -> 2 odd; [9,10,11,12,13] -> 3 odd
    rows = odd_even_distribution(DRAWS)
    by_odd_count = {int(row.label.split()[0]): row for row in rows}

    assert by_odd_count[3].observed_count == 2
    assert by_odd_count[2].observed_count == 1
    assert by_odd_count[0].observed_count == 0

    expected_3 = 3 * hypergeom.pmf(3, 69, 35, 5)
    assert by_odd_count[3].expected_count == pytest.approx(expected_3)


def test_low_high_distribution_known_values():
    # All three draws' white balls are entirely <= 35, so low_count == 5 every time.
    rows = low_high_distribution(DRAWS)
    by_low_count = {int(row.label.split()[0]): row for row in rows}

    assert by_low_count[5].observed_count == 3
    assert by_low_count[0].observed_count == 0

    expected_5 = 3 * hypergeom.pmf(5, 69, 35, 5)
    assert by_low_count[5].expected_count == pytest.approx(expected_5)


def test_frequency_by_range_known_values():
    rows = frequency_by_range(DRAWS, bucket_width=10)
    by_label = {row.label: row for row in rows}

    assert by_label["1-10"].observed_count == 12
    assert by_label["11-20"].observed_count == 3
    assert by_label["21-30"].observed_count == 0

    total_slots = 3 * 5
    assert by_label["1-10"].expected_count == pytest.approx(total_slots * 10 / 69)
    # Last bucket only spans 61-69 (9 numbers), not a full decade.
    assert by_label["61-69"].range_max == 69
    assert by_label["61-69"].expected_count == pytest.approx(total_slots * 9 / 69)
