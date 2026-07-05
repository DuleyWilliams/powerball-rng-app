"""Statistical analysis engine.

Everything in this module is HISTORICAL ANALYSIS ONLY. Powerball
drawings are independent random events — nothing here predicts,
forecasts, or improves the odds of future draws. Chi-square tests and
confidence intervals describe how closely *past* drawings match the
uniform-random distribution the game is designed to produce; they say
nothing about what will be drawn next.
"""

import math
import statistics as stats
from collections import Counter
from dataclasses import dataclass

from scipy.stats import chisquare, hypergeom

from core.config import WHITE_BALL_MIN, WHITE_BALL_MAX, WHITE_BALL_COUNT, POWERBALL_MIN, POWERBALL_MAX, LOW_HIGH_SPLIT
from core.patterns import analyze_pattern
from data.repository import Draw
from analytics_engine.frequency import get_frequency

_WHITE_BALL_POOL_SIZE = WHITE_BALL_MAX - WHITE_BALL_MIN + 1  # 69
_POWERBALL_POOL_SIZE = POWERBALL_MAX - POWERBALL_MIN + 1     # 26
_LOW_COUNT = LOW_HIGH_SPLIT - WHITE_BALL_MIN + 1              # 35 numbers are "low"

_MIN_POSSIBLE_SUM = sum(range(WHITE_BALL_MIN, WHITE_BALL_MIN + WHITE_BALL_COUNT))
_MAX_POSSIBLE_SUM = sum(range(WHITE_BALL_MAX - WHITE_BALL_COUNT + 1, WHITE_BALL_MAX + 1))

_Z_95 = 1.96  # normal-approximation critical value for a 95% confidence interval


@dataclass(frozen=True)
class NumberFrequency:
    number: int
    observed_count: int
    expected_count: float
    observed_proportion: float
    expected_proportion: float
    deviation: float
    ci_lower: float
    ci_upper: float


@dataclass(frozen=True)
class ChiSquareResult:
    statistic: float
    degrees_of_freedom: int
    p_value: float
    alpha: float
    is_significant: bool
    interpretation: str


@dataclass(frozen=True)
class SumDistributionBucket:
    label: str
    range_min: int
    range_max: int
    count: int
    proportion: float


@dataclass(frozen=True)
class SumStatistics:
    sample_size: int
    mean: float
    std_dev: float
    minimum: int
    maximum: int
    median: float
    confidence_interval_95: tuple[float, float]
    buckets: list[SumDistributionBucket]


@dataclass(frozen=True)
class CategoricalDistributionRow:
    label: str
    observed_count: int
    expected_count: float
    deviation: float


@dataclass(frozen=True)
class RangeFrequency:
    label: str
    range_min: int
    range_max: int
    observed_count: int
    expected_count: float
    deviation: float


def _proportion_confidence_interval(count: int, n: int) -> tuple[float, float]:
    """Normal-approximation (Wald) 95% CI on an observed proportion."""
    if n <= 0:
        return (0.0, 0.0)

    p = count / n
    margin = _Z_95 * math.sqrt(p * (1 - p) / n)
    return (max(0.0, p - margin), min(1.0, p + margin))


def _hypergeometric_expected_counts(total_draws: int, category_size: int) -> list[float]:
    """Expected counts for k=0..5 successes when drawing 5 of 69 numbers
    without replacement, category_size of which count as a "success"
    (used for odd/even and low/high, which are both 35/34 splits of the
    69-number pool).
    """
    return [
        total_draws * hypergeom.pmf(k, _WHITE_BALL_POOL_SIZE, category_size, WHITE_BALL_COUNT)
        for k in range(WHITE_BALL_COUNT + 1)
    ]


def expected_white_ball_frequency(draws: list[Draw]) -> float:
    """Expected number of appearances per white ball under a uniform,
    unbiased draw, given the sample size."""
    if not draws:
        return 0.0
    return (len(draws) * WHITE_BALL_COUNT) / _WHITE_BALL_POOL_SIZE


def expected_powerball_frequency(draws: list[Draw]) -> float:
    if not draws:
        return 0.0
    return len(draws) / _POWERBALL_POOL_SIZE


def white_ball_frequency_distribution(draws: list[Draw]) -> list[NumberFrequency]:
    freq = get_frequency(draws)["white_frequency"]
    total_slots = len(draws) * WHITE_BALL_COUNT
    expected_count = expected_white_ball_frequency(draws)
    expected_proportion = 1 / _WHITE_BALL_POOL_SIZE

    rows = []
    for number in range(WHITE_BALL_MIN, WHITE_BALL_MAX + 1):
        observed_count = freq.get(number, 0)
        observed_proportion = observed_count / total_slots if total_slots else 0.0
        ci_lower, ci_upper = _proportion_confidence_interval(observed_count, total_slots)

        rows.append(NumberFrequency(
            number=number,
            observed_count=observed_count,
            expected_count=expected_count,
            observed_proportion=observed_proportion,
            expected_proportion=expected_proportion,
            deviation=observed_count - expected_count,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
        ))

    return rows


def powerball_frequency_distribution(draws: list[Draw]) -> list[NumberFrequency]:
    freq = get_frequency(draws)["powerball_frequency"]
    total_slots = len(draws)
    expected_count = expected_powerball_frequency(draws)
    expected_proportion = 1 / _POWERBALL_POOL_SIZE

    rows = []
    for number in range(POWERBALL_MIN, POWERBALL_MAX + 1):
        observed_count = freq.get(number, 0)
        observed_proportion = observed_count / total_slots if total_slots else 0.0
        ci_lower, ci_upper = _proportion_confidence_interval(observed_count, total_slots)

        rows.append(NumberFrequency(
            number=number,
            observed_count=observed_count,
            expected_count=expected_count,
            observed_proportion=observed_proportion,
            expected_proportion=expected_proportion,
            deviation=observed_count - expected_count,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
        ))

    return rows


def _chi_square_goodness_of_fit(observed: list[int], subject: str, alpha: float = 0.05) -> ChiSquareResult:
    total = sum(observed)
    degrees_of_freedom = len(observed) - 1

    if total == 0:
        return ChiSquareResult(
            statistic=0.0, degrees_of_freedom=degrees_of_freedom, p_value=1.0,
            alpha=alpha, is_significant=False,
            interpretation="No draws available for analysis.",
        )

    expected = total / len(observed)
    statistic, p_value = chisquare(f_obs=observed, f_exp=[expected] * len(observed))
    is_significant = bool(p_value < alpha)

    interpretation = (
        f"Observed {subject} frequencies show a statistically significant deviation "
        f"from uniform randomness (p={p_value:.4f} < alpha={alpha}). This describes the "
        f"historical sample only — it does not predict future draws."
        if is_significant else
        f"Observed {subject} frequencies are consistent with uniform randomness "
        f"(p={p_value:.4f} >= alpha={alpha}); no statistically significant deviation detected."
    )

    return ChiSquareResult(
        statistic=float(statistic), degrees_of_freedom=degrees_of_freedom,
        p_value=float(p_value), alpha=alpha, is_significant=is_significant,
        interpretation=interpretation,
    )


def white_ball_chi_square(draws: list[Draw], alpha: float = 0.05) -> ChiSquareResult:
    observed = [f.observed_count for f in white_ball_frequency_distribution(draws)]
    return _chi_square_goodness_of_fit(observed, "white-ball", alpha=alpha)


def powerball_chi_square(draws: list[Draw], alpha: float = 0.05) -> ChiSquareResult:
    observed = [f.observed_count for f in powerball_frequency_distribution(draws)]
    return _chi_square_goodness_of_fit(observed, "powerball", alpha=alpha)


def white_ball_sum_statistics(draws: list[Draw], bucket_width: int = 20) -> SumStatistics:
    sums = [sum(draw[:5]) for draw in draws]
    n = len(sums)

    if n == 0:
        return SumStatistics(
            sample_size=0, mean=0.0, std_dev=0.0, minimum=0, maximum=0,
            median=0.0, confidence_interval_95=(0.0, 0.0), buckets=[],
        )

    mean = stats.mean(sums)
    std_dev = stats.stdev(sums) if n > 1 else 0.0
    median = stats.median(sums)
    standard_error = std_dev / math.sqrt(n) if n > 0 else 0.0
    confidence_interval = (mean - _Z_95 * standard_error, mean + _Z_95 * standard_error)

    buckets = []
    start = _MIN_POSSIBLE_SUM
    while start <= _MAX_POSSIBLE_SUM:
        end = min(start + bucket_width - 1, _MAX_POSSIBLE_SUM)
        count = sum(1 for s in sums if start <= s <= end)
        buckets.append(SumDistributionBucket(
            label=f"{start}-{end}", range_min=start, range_max=end,
            count=count, proportion=count / n,
        ))
        start = end + 1

    return SumStatistics(
        sample_size=n, mean=mean, std_dev=std_dev, minimum=min(sums), maximum=max(sums),
        median=median, confidence_interval_95=confidence_interval, buckets=buckets,
    )


def odd_even_distribution(draws: list[Draw]) -> list[CategoricalDistributionRow]:
    counts = Counter(analyze_pattern(draw[:5]).odd_count for draw in draws)
    expected = _hypergeometric_expected_counts(len(draws), category_size=_LOW_COUNT)  # 35 odd numbers, same split size as "low"

    return [
        CategoricalDistributionRow(
            label=f"{k} odd / {WHITE_BALL_COUNT - k} even",
            observed_count=counts.get(k, 0),
            expected_count=expected[k],
            deviation=counts.get(k, 0) - expected[k],
        )
        for k in range(WHITE_BALL_COUNT + 1)
    ]


def low_high_distribution(draws: list[Draw]) -> list[CategoricalDistributionRow]:
    counts = Counter(analyze_pattern(draw[:5]).low_count for draw in draws)
    expected = _hypergeometric_expected_counts(len(draws), category_size=_LOW_COUNT)

    return [
        CategoricalDistributionRow(
            label=f"{k} low / {WHITE_BALL_COUNT - k} high",
            observed_count=counts.get(k, 0),
            expected_count=expected[k],
            deviation=counts.get(k, 0) - expected[k],
        )
        for k in range(WHITE_BALL_COUNT + 1)
    ]


def frequency_by_range(draws: list[Draw], bucket_width: int = 10) -> list[RangeFrequency]:
    freq = get_frequency(draws)["white_frequency"]
    total_slots = len(draws) * WHITE_BALL_COUNT

    rows = []
    start = WHITE_BALL_MIN
    while start <= WHITE_BALL_MAX:
        end = min(start + bucket_width - 1, WHITE_BALL_MAX)
        observed = sum(freq.get(n, 0) for n in range(start, end + 1))
        bucket_size = end - start + 1
        expected = total_slots * bucket_size / _WHITE_BALL_POOL_SIZE if total_slots else 0.0

        rows.append(RangeFrequency(
            label=f"{start}-{end}", range_min=start, range_max=end,
            observed_count=observed, expected_count=expected, deviation=observed - expected,
        ))
        start = end + 1

    return rows
