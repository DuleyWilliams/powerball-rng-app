"""Plotly chart builders for the visual analytics section of the dashboard."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data.repository import Draw
from analytics_engine.frequency import hot_numbers, cold_numbers, hot_powerballs
from analytics_engine.statistics import SumStatistics


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


def sum_distribution_chart(sum_stats: SumStatistics) -> go.Figure:
    df = pd.DataFrame(
        [{"Range": bucket.label, "Count": bucket.count} for bucket in sum_stats.buckets]
    )

    return px.bar(
        df,
        x="Range",
        y="Count",
        title="White Ball Sum Distribution (Historical)",
    )
