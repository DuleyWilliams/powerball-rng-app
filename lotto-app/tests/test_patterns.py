from core.patterns import (
    analyze_pattern,
    is_weak_pattern,
    has_duplicate_white_balls,
    odd_even_label,
    low_high_label,
)


def test_analyze_pattern_counts_known_ticket():
    pattern = analyze_pattern([2, 6, 26, 39, 68])

    assert pattern.odd_count == 1
    assert pattern.even_count == 4
    assert pattern.low_count == 3
    assert pattern.high_count == 2
    assert pattern.white_sum == 141
    assert pattern.consecutive_pairs == 0


def test_odd_even_and_low_high_labels():
    pattern = analyze_pattern([2, 6, 26, 39, 68])

    assert odd_even_label(pattern) == "1 odd / 4 even"
    assert low_high_label(pattern) == "3 low / 2 high"


def test_is_weak_pattern_false_for_balanced_ticket():
    pattern = analyze_pattern([2, 6, 26, 39, 68])
    assert is_weak_pattern(pattern) is False


def test_is_weak_pattern_true_for_all_odd():
    pattern = analyze_pattern([3, 15, 45, 63, 67])
    assert pattern.odd_count == 5
    assert is_weak_pattern(pattern) is True


def test_is_weak_pattern_true_for_all_low():
    pattern = analyze_pattern([3, 10, 18, 26, 34])
    assert pattern.low_count == 5
    assert is_weak_pattern(pattern) is True


def test_is_weak_pattern_true_for_sum_too_low():
    pattern = analyze_pattern([1, 5, 9, 13, 36])
    assert pattern.white_sum == 64
    assert is_weak_pattern(pattern) is True


def test_is_weak_pattern_true_for_sum_too_high():
    pattern = analyze_pattern([30, 50, 58, 64, 69])
    assert pattern.white_sum == 271
    assert is_weak_pattern(pattern) is True


def test_is_weak_pattern_true_for_too_many_consecutive_pairs():
    pattern = analyze_pattern([10, 11, 12, 13, 50])
    assert pattern.consecutive_pairs == 3
    assert is_weak_pattern(pattern) is True


def test_has_duplicate_white_balls():
    assert has_duplicate_white_balls([1, 2, 3, 4, 4]) is True
    assert has_duplicate_white_balls([1, 2, 3, 4, 5]) is False
