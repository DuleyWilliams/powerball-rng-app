from datetime import date

import plotly.graph_objects as go

from data.repository import DatedDraw
from analytics_engine.statistics import white_ball_sum_statistics
from analytics_engine.charts import (
    white_ball_frequency_heatmap,
    powerball_frequency_heatmap,
    white_ball_gap_chart,
    powerball_gap_chart,
    sum_distribution_chart,
    odd_even_distribution_chart,
    low_high_distribution_chart,
    range_frequency_chart,
    recent_draws_timeline_chart,
    pair_frequency_heatmap,
)

# Same 3-draw fixture used in test_statistics.py / test_frequency.py, hand-verified there.
DRAWS = [
    [1, 2, 3, 4, 5, 10],
    [1, 2, 6, 7, 8, 10],
    [9, 10, 11, 12, 13, 20],
]


def test_white_ball_frequency_heatmap_grid_and_known_value():
    fig = white_ball_frequency_heatmap(DRAWS)

    assert len(fig.data) == 1
    assert fig.data[0].type == "heatmap"

    z = fig.data[0].z
    text = fig.data[0].text

    assert len(z) == 10  # ceil(69 / 7 columns)
    assert len(z[0]) == 7
    assert z[0][0] == 2  # white ball 1, observed twice
    assert text[0][0] == "1"


def test_powerball_frequency_heatmap_grid_and_known_value():
    fig = powerball_frequency_heatmap(DRAWS)

    z = fig.data[0].z
    text = fig.data[0].text

    assert len(z) == 2  # ceil(26 / 13 columns)
    assert len(z[0]) == 13
    assert z[0][9] == 2  # powerball 10, observed twice
    assert text[0][9] == "10"


def test_white_ball_gap_chart_orders_by_number_and_flags_never_seen():
    fig = white_ball_gap_chart(DRAWS)
    x = list(fig.data[0].x)

    assert x == list(range(1, 70))

    idx_1 = x.index(1)
    idx_14 = x.index(14)

    assert fig.data[0].y[idx_1] == 0  # seen in the most recent draw
    assert fig.data[0].y[idx_14] == len(DRAWS)  # never seen -> plotted at sample size
    assert fig.data[0].customdata[idx_14] == "Never Seen"


def test_powerball_gap_chart_orders_by_number():
    fig = powerball_gap_chart(DRAWS)
    x = list(fig.data[0].x)

    assert x == list(range(1, 27))

    idx_10 = x.index(10)
    idx_1 = x.index(1)

    assert fig.data[0].y[idx_10] == 0
    assert fig.data[0].y[idx_1] == len(DRAWS)
    assert fig.data[0].customdata[idx_1] == "Never Seen"


def test_sum_distribution_chart_has_bars_and_mean_line():
    sum_stats = white_ball_sum_statistics(DRAWS)
    fig = sum_distribution_chart(sum_stats)

    assert len(fig.data) == 1
    assert sum(fig.data[0].y) == 3
    assert len(fig.layout.shapes) >= 2  # mean vline + confidence-interval vrect


def test_sum_distribution_chart_handles_empty_draws():
    fig = sum_distribution_chart(white_ball_sum_statistics([]))

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_odd_even_distribution_chart_has_observed_and_expected_traces():
    fig = odd_even_distribution_chart(DRAWS)
    trace_names = {trace.name for trace in fig.data}

    assert trace_names == {"Observed", "Expected"}

    observed = next(trace for trace in fig.data if trace.name == "Observed")
    assert sum(observed.y) == len(DRAWS)


def test_low_high_distribution_chart_has_observed_and_expected_traces():
    fig = low_high_distribution_chart(DRAWS)
    observed = next(trace for trace in fig.data if trace.name == "Observed")

    assert sum(observed.y) == len(DRAWS)


def test_range_frequency_chart_observed_sums_to_total_white_slots():
    fig = range_frequency_chart(DRAWS)
    observed = next(trace for trace in fig.data if trace.name == "Observed")

    assert sum(observed.y) == len(DRAWS) * 5


def test_recent_draws_timeline_chart_plots_known_sums_in_order():
    dated_draws = [
        DatedDraw(draw_date=date(2020, 1, 1), balls=[1, 2, 3, 4, 5, 6]),
        DatedDraw(draw_date=date(2020, 1, 4), balls=[7, 8, 9, 10, 11, 12]),
    ]

    fig = recent_draws_timeline_chart(dated_draws)

    assert len(fig.data) >= 1
    all_y = [y for trace in fig.data for y in trace.y]
    assert list(all_y) == [15, 45]


def test_recent_draws_timeline_chart_handles_no_dated_draws():
    fig = recent_draws_timeline_chart([])

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_pair_frequency_heatmap_is_symmetric_with_known_pair_count():
    fig = pair_frequency_heatmap(DRAWS)
    x = list(fig.data[0].x)
    z = fig.data[0].z

    i, j = x.index(1), x.index(2)

    assert z[i][j] == 2  # (1, 2) appears together in the first two draws
    assert z[j][i] == 2
    assert z[i][i] == 0
