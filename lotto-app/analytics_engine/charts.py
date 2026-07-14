"""Plotly chart builders for the dashboard.

Every function here takes plain data in and returns a plotly Figure —
no Streamlit calls, no direct SQLite access. Historical analysis only:
none of these charts predict or improve the odds of future draws.
"""

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.config import WHITE_BALL_MIN, WHITE_BALL_MAX
from data.repository import Draw, DatedDraw
from analytics_engine.frequency import hot_numbers, cold_numbers, hot_powerballs, repeated_pairs
from analytics_engine.gaps import white_ball_gap_analysis, powerball_gap_analysis
from analytics_engine.statistics import (
    SumStatistics,
    white_ball_frequency_distribution,
    powerball_frequency_distribution,
    odd_even_distribution,
    low_high_distribution,
    frequency_by_range,
)


def hot_numbers_chart(draws: list[Draw]) -> go.Figure:
    df = pd.DataFrame(
        hot_numbers(draws),
        columns=["Number", "Times Drawn"],
    )

    return px.bar(
        df,
        x="Number",
        y="Times Drawn",
        title="Hot White Balls",
    )


def cold_numbers_chart(draws: list[Draw]) -> go.Figure:
    df = pd.DataFrame(
        cold_numbers(draws),
        columns=["Number", "Times Drawn"],
    )

    return px.bar(
        df,
        x="Number",
        y="Times Drawn",
        title="Cold White Balls",
    )


def powerball_chart(draws: list[Draw]) -> go.Figure:
    df = pd.DataFrame(
        hot_powerballs(draws),
        columns=["Powerball", "Times Drawn"],
    )

    return px.bar(
        df,
        x="Powerball",
        y="Times Drawn",
        title="Powerball Frequency",
    )


def _number_grid_heatmap(rows: list, number_attr: str, count_attr: str, columns: int, title: str) -> go.Figure:
    """Shared builder for the white-ball/powerball frequency heatmaps —
    lays numbers out left-to-right, top-to-bottom in a fixed-width grid.
    """
    total = len(rows)
    grid_rows = math.ceil(total / columns)

    z = [[None] * columns for _ in range(grid_rows)]
    text = [[""] * columns for _ in range(grid_rows)]

    for index, row in enumerate(rows):
        r, c = divmod(index, columns)
        z[r][c] = getattr(row, count_attr)
        text[r][c] = str(getattr(row, number_attr))

    fig = go.Figure(go.Heatmap(
        z=z,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 11},
        colorscale="YlOrRd",
        hovertemplate="Number: %{text}<br>Observed count: %{z}<extra></extra>",
        showscale=True,
    ))
    fig.update_layout(
        title=title,
        xaxis={"visible": False},
        yaxis={"visible": False, "autorange": "reversed"},
    )
    return fig


def white_ball_frequency_heatmap(draws: list[Draw]) -> go.Figure:
    rows = white_ball_frequency_distribution(draws)
    return _number_grid_heatmap(rows, "number", "observed_count", columns=7, title="White Ball Frequency Heatmap")


def powerball_frequency_heatmap(draws: list[Draw]) -> go.Figure:
    rows = powerball_frequency_distribution(draws)
    return _number_grid_heatmap(rows, "number", "observed_count", columns=13, title="Powerball Frequency Heatmap")


def _gap_chart(gap_rows: list[dict], number_key: str, total_draws: int, title: str) -> go.Figure:
    numbers = [row[number_key] for row in gap_rows]
    raw_values = [row["Drawings Since Last Seen"] for row in gap_rows]

    # "Never Seen" has no numeric gap; plot it at the sample size (the
    # largest gap that's actually meaningful for this history) and
    # label it explicitly on hover so it isn't mistaken for a real value.
    values = [v if isinstance(v, int) else total_draws for v in raw_values]
    labels = [str(v) if isinstance(v, int) else "Never Seen" for v in raw_values]

    order = sorted(range(len(numbers)), key=lambda i: numbers[i])
    numbers = [numbers[i] for i in order]
    values = [values[i] for i in order]
    labels = [labels[i] for i in order]

    fig = go.Figure(go.Bar(
        x=numbers, y=values, customdata=labels,
        hovertemplate="Number: %{x}<br>Drawings since last seen: %{customdata}<extra></extra>",
    ))
    fig.update_layout(title=title, xaxis_title="Number", yaxis_title="Drawings Since Last Seen")
    return fig


def white_ball_gap_chart(draws: list[Draw]) -> go.Figure:
    return _gap_chart(white_ball_gap_analysis(draws), "Number", len(draws), "White Ball Gap Distribution")


def powerball_gap_chart(draws: list[Draw]) -> go.Figure:
    return _gap_chart(powerball_gap_analysis(draws), "Powerball", len(draws), "Powerball Gap Distribution")


def sum_distribution_chart(sum_stats: SumStatistics) -> go.Figure:
    if not sum_stats.buckets:
        return go.Figure()

    midpoints = [(bucket.range_min + bucket.range_max) / 2 for bucket in sum_stats.buckets]
    widths = [bucket.range_max - bucket.range_min + 1 for bucket in sum_stats.buckets]
    labels = [bucket.label for bucket in sum_stats.buckets]
    counts = [bucket.count for bucket in sum_stats.buckets]

    fig = go.Figure(go.Bar(
        x=midpoints, y=counts, width=widths, customdata=labels,
        hovertemplate="Sum range: %{customdata}<br>Draws: %{y}<extra></extra>",
    ))

    fig.add_vline(
        x=sum_stats.mean, line_dash="dash", line_color="firebrick",
        annotation_text=f"Mean: {sum_stats.mean:.1f}", annotation_position="top",
    )
    fig.add_vrect(
        x0=sum_stats.confidence_interval_95[0], x1=sum_stats.confidence_interval_95[1],
        fillcolor="firebrick", opacity=0.12, line_width=0,
        annotation_text="95% CI (mean)", annotation_position="bottom left",
    )

    fig.update_layout(
        title="White Ball Sum Distribution (Historical)",
        xaxis_title="White Ball Sum", yaxis_title="Number of Draws",
    )
    return fig


def _observed_vs_expected_chart(rows: list, title: str, x_title: str) -> go.Figure:
    df = pd.DataFrame(
        [{"Category": row.label, "Type": "Observed", "Count": row.observed_count} for row in rows]
        + [{"Category": row.label, "Type": "Expected", "Count": row.expected_count} for row in rows]
    )

    fig = px.bar(df, x="Category", y="Count", color="Type", barmode="group", title=title)
    fig.update_layout(xaxis_title=x_title, yaxis_title="Number of Draws")
    return fig


def odd_even_distribution_chart(draws: list[Draw]) -> go.Figure:
    return _observed_vs_expected_chart(odd_even_distribution(draws), "Odd / Even Distribution", "Odd / Even Split")


def low_high_distribution_chart(draws: list[Draw]) -> go.Figure:
    return _observed_vs_expected_chart(low_high_distribution(draws), "Low / High Distribution", "Low / High Split")


def range_frequency_chart(draws: list[Draw]) -> go.Figure:
    return _observed_vs_expected_chart(frequency_by_range(draws), "Frequency by Number Range", "Number Range")


def recent_draws_timeline_chart(dated_draws: list[DatedDraw]) -> go.Figure:
    if not dated_draws:
        return go.Figure()

    df = pd.DataFrame([
        {"Draw Date": d.draw_date, "White Ball Sum": sum(d.balls[:5]), "Powerball": d.balls[5]}
        for d in dated_draws
    ])

    fig = px.scatter(
        df, x="Draw Date", y="White Ball Sum", color="Powerball",
        title="Recent Draw Timeline", color_continuous_scale="Viridis",
    )
    fig.update_traces(mode="lines+markers")
    return fig


def pair_frequency_heatmap(draws: list[Draw]) -> go.Figure:
    pool = list(range(WHITE_BALL_MIN, WHITE_BALL_MAX + 1))
    size = len(pool)
    matrix = [[0] * size for _ in range(size)]

    for (n1, n2), count in repeated_pairs(draws, limit=None):
        i, j = n1 - WHITE_BALL_MIN, n2 - WHITE_BALL_MIN
        matrix[i][j] = count
        matrix[j][i] = count

    fig = go.Figure(go.Heatmap(
        z=matrix, x=pool, y=pool, colorscale="Blues",
        hovertemplate="Pair: %{x} + %{y}<br>Times seen together: %{z}<extra></extra>",
    ))
    fig.update_layout(
        title="White Ball Pair Frequency Heatmap",
        xaxis_title="White Ball", yaxis_title="White Ball",
    )
    return fig
