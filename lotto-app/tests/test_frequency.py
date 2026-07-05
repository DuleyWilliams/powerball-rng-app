from analytics_engine.frequency import (
    hot_numbers,
    cold_numbers,
    hot_powerballs,
    repeated_pairs,
)

DRAWS = [
    [1, 2, 3, 4, 5, 10],
    [1, 2, 6, 7, 8, 10],
    [9, 10, 11, 12, 13, 20],
]


def test_hot_numbers_ranks_most_frequent_first():
    assert hot_numbers(DRAWS, limit=2) == [(1, 2), (2, 2)]


def test_cold_numbers_ranks_least_frequent_first():
    assert cold_numbers(DRAWS, limit=3) == [(14, 0), (15, 0), (16, 0)]


def test_hot_powerballs_ranks_most_frequent_first():
    assert hot_powerballs(DRAWS, limit=1) == [(10, 2)]


def test_repeated_pairs_finds_pair_seen_across_draws():
    assert repeated_pairs(DRAWS, limit=1) == [((1, 2), 2)]
