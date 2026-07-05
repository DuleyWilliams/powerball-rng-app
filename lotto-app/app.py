import streamlit as st
import pandas as pd

from data.migration import migrate_json_to_sqlite
from data.repository import get_all_draws, database_statistics
from services.ticket_service import generate_tickets, filter_tickets
from services.update_service import update_numbers
from analytics_engine.frequency import (
    hot_numbers,
    cold_numbers,
    hot_powerballs,
    repeated_pairs,
)
from analytics_engine.scoring import score_tickets
from analytics_engine.charts import (
    hot_numbers_chart,
    cold_numbers_chart,
    powerball_chart,
    sum_distribution_chart,
)
from analytics_engine.condensation import condense_tickets
from analytics_engine.gaps import (
    white_ball_gap_analysis,
    powerball_gap_analysis,
)
from analytics_engine.statistics import (
    expected_white_ball_frequency,
    expected_powerball_frequency,
    white_ball_chi_square,
    powerball_chi_square,
    white_ball_sum_statistics,
    odd_even_distribution,
    low_high_distribution,
    frequency_by_range,
)


st.set_page_config(
    page_title="Powerball RNG Engine",
    layout="wide"
)

st.title("Powerball RNG Engine")
st.caption("Weighted generator based on your saved historical draw data.")
st.caption("Powerball drawings are independent random events — nothing here predicts future draws.")

# SQLite is the primary data source; numbers.json (if present) is
# migrated in automatically and idempotently on every startup.
migration_summary = migrate_json_to_sqlite()

draws = get_all_draws()

st.subheader("Data Platform Status")

stats = database_statistics()

status_col1, status_col2, status_col3, status_col4, status_col5 = st.columns(5)
status_col1.metric("Database Rows", stats.total_rows)
status_col2.metric("Latest Draw Date", stats.latest_draw_date.isoformat() if stats.latest_draw_date else "—")
status_col3.metric("Oldest Draw Date", stats.oldest_draw_date.isoformat() if stats.oldest_draw_date else "—")

if migration_summary.source_found:
    migration_status = f"{migration_summary.migrated} migrated / {migration_summary.skipped} present"
else:
    migration_status = "No numbers.json found"
status_col4.metric("Migration Status", migration_status)

status_col5.metric("Last Update", stats.last_updated_at if stats.last_updated_at else "Never")

st.divider()

col1, col2 = st.columns(2)

with col1:
    ticket_count = st.number_input(
        "How many tickets?",
        min_value=1,
        max_value=50,
        value=5
    )

    candidate_pool_size = st.number_input(
        "Candidate pool size for condensation",
        min_value=100,
        max_value=10000,
        value=1000,
        step=100
    )

    if st.button("Generate Numbers"):
        tickets, rejected_tickets = filter_tickets(generate_tickets(ticket_count))
        scored = score_tickets(tickets, draws)

        scored_rows = []

        for item in scored:
            ticket = item["ticket"]
            scored_rows.append([
                ticket[0],
                ticket[1],
                ticket[2],
                ticket[3],
                ticket[4],
                ticket[5],
                item["score"],
                item["odd_even"],
                item["low_high"],
                item["sum"]
            ])

        df = pd.DataFrame(
            scored_rows,
            columns=[
                "Ball 1",
                "Ball 2",
                "Ball 3",
                "Ball 4",
                "Ball 5",
                "Powerball",
                "Score",
                "Odd / Even",
                "Low / High",
                "White Ball Sum"
            ]
        )

        st.subheader("Generated Tickets Ranked")
        st.dataframe(df, width="stretch")

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download Tickets CSV",
            data=csv,
            file_name="generated_powerball_tickets.csv",
            mime="text/csv"
        )

    if st.button("Generate Condensed Tickets"):
        candidate_tickets, rejected_tickets = filter_tickets(generate_tickets(candidate_pool_size))
        scored_candidates = score_tickets(candidate_tickets, draws)

        condensed_rows = condense_tickets(
            scored_candidates,
            target_count=ticket_count
        )

        if condensed_rows:
            condensed_df = pd.DataFrame(condensed_rows)

            st.subheader("Condensed Ticket Set")
            st.caption(
                "Generated from a larger candidate pool, then reduced for stronger coverage and less overlap."
            )

            st.dataframe(condensed_df, width="stretch")

            condensed_csv = condensed_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download Condensed Tickets CSV",
                data=condensed_csv,
                file_name="condensed_powerball_tickets.csv",
                mime="text/csv"
            )
        else:
            st.warning("No condensed tickets generated. Try increasing the candidate pool size.")

with col2:
    st.subheader("Update Data")

    if st.button("Fetch Latest TN Powerball"):
        try:
            result = update_numbers()
            st.success(result["message"])
            st.write("Latest:", result["latest"])
        except Exception as error:
            st.error(f"Update failed: {error}")

st.divider()

st.subheader("Current Dataset")
st.write(f"Total drawings loaded: {len(draws)}")

if draws:
    history_df = pd.DataFrame(
        draws,
        columns=["Ball 1", "Ball 2", "Ball 3", "Ball 4", "Ball 5", "Powerball"]
    )

    st.dataframe(history_df.head(100), width="stretch")
else:
    st.warning("No draw data loaded yet.")

st.divider()

st.header("Draw Analytics")

if draws:
    stat_col1, stat_col2, stat_col3 = st.columns(3)

    with stat_col1:
        st.subheader("Hot White Balls")
        st.dataframe(
            pd.DataFrame(hot_numbers(draws), columns=["Number", "Times Drawn"]),
            width="stretch"
        )

    with stat_col2:
        st.subheader("Cold White Balls")
        st.dataframe(
            pd.DataFrame(cold_numbers(draws), columns=["Number", "Times Drawn"]),
            width="stretch"
        )

    with stat_col3:
        st.subheader("Hot Powerballs")
        st.dataframe(
            pd.DataFrame(hot_powerballs(draws), columns=["Powerball", "Times Drawn"]),
            width="stretch"
        )

    st.subheader("Most Repeated White Ball Pairs")

    pairs = repeated_pairs(draws)

    pair_rows = [
        [f"{pair[0]} + {pair[1]}", count]
        for pair, count in pairs
    ]

    st.dataframe(
        pd.DataFrame(pair_rows, columns=["Pair", "Times Seen"]),
        width="stretch"
    )
else:
    st.warning("No analytics data available yet.")

st.divider()

st.divider()

st.header("Number Gap Analysis")

if draws:
    gap_col1, gap_col2 = st.columns(2)

    with gap_col1:
        st.subheader("White Ball Gaps")
        st.caption("Numbers ranked by how many drawings have passed since they last appeared.")

        white_gap_df = pd.DataFrame(white_ball_gap_analysis(draws))
        st.dataframe(white_gap_df.head(20), width="stretch")

    with gap_col2:
        st.subheader("Powerball Gaps")
        st.caption("Powerballs ranked by how many drawings have passed since they last appeared.")

        powerball_gap_df = pd.DataFrame(powerball_gap_analysis(draws))
        st.dataframe(powerball_gap_df.head(20), width="stretch")
else:
    st.warning("No gap data available yet.")

st.header("Visual Analytics")

if draws:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.plotly_chart(
            hot_numbers_chart(draws),
            width="stretch"
        )

        st.plotly_chart(
            cold_numbers_chart(draws),
            width="stretch"
        )

    with chart_col2:
        st.plotly_chart(
            powerball_chart(draws),
            width="stretch"
        )
else:
    st.warning("No chart data available yet.")

st.divider()

st.header("Statistical Analysis")
st.warning(
    "Historical analysis only. Powerball drawings are independent random events — "
    "nothing in this section predicts or improves the odds of future draws."
)

if draws:
    st.metric("Total Sample Size (Draws)", len(draws))

    expected_col1, expected_col2 = st.columns(2)
    expected_col1.metric("Expected Frequency per White Ball", f"{expected_white_ball_frequency(draws):.2f}")
    expected_col2.metric("Expected Frequency per Powerball", f"{expected_powerball_frequency(draws):.2f}")

    st.subheader("Chi-Square Goodness-of-Fit")
    st.caption(
        "Tests whether historical frequencies are consistent with a uniform random "
        "draw. A significant result describes the sample collected so far — it does "
        "not predict future draws."
    )

    white_chi = white_ball_chi_square(draws)
    pb_chi = powerball_chi_square(draws)

    chi_square_df = pd.DataFrame([
        {
            "Pool": "White Balls",
            "Chi-Square Statistic": round(white_chi.statistic, 3),
            "Degrees of Freedom": white_chi.degrees_of_freedom,
            "p-value": round(white_chi.p_value, 4),
            "Significant (alpha=0.05)": white_chi.is_significant,
        },
        {
            "Pool": "Powerball",
            "Chi-Square Statistic": round(pb_chi.statistic, 3),
            "Degrees of Freedom": pb_chi.degrees_of_freedom,
            "p-value": round(pb_chi.p_value, 4),
            "Significant (alpha=0.05)": pb_chi.is_significant,
        },
    ])
    st.dataframe(chi_square_df, width="stretch")
    st.caption(white_chi.interpretation)
    st.caption(pb_chi.interpretation)

    st.subheader("White Ball Sum Distribution")

    sum_stats = white_ball_sum_statistics(draws)

    sum_col1, sum_col2, sum_col3 = st.columns(3)
    sum_col1.metric("Mean Sum", f"{sum_stats.mean:.1f}")
    sum_col2.metric("Median Sum", f"{sum_stats.median:.1f}")
    sum_col3.metric("Std Dev", f"{sum_stats.std_dev:.1f}")
    st.caption(
        f"95% confidence interval for the mean sum: "
        f"{sum_stats.confidence_interval_95[0]:.1f} - {sum_stats.confidence_interval_95[1]:.1f}"
    )

    st.plotly_chart(sum_distribution_chart(sum_stats), width="stretch")

    dist_col1, dist_col2 = st.columns(2)

    with dist_col1:
        st.subheader("Odd / Even Distribution")
        odd_even_df = pd.DataFrame([
            {"Pattern": row.label, "Observed": row.observed_count, "Expected": round(row.expected_count, 2)}
            for row in odd_even_distribution(draws)
        ])
        st.dataframe(odd_even_df, width="stretch")

    with dist_col2:
        st.subheader("Low / High Distribution")
        low_high_df = pd.DataFrame([
            {"Pattern": row.label, "Observed": row.observed_count, "Expected": round(row.expected_count, 2)}
            for row in low_high_distribution(draws)
        ])
        st.dataframe(low_high_df, width="stretch")

    st.subheader("Frequency by Number Range")
    range_df = pd.DataFrame([
        {
            "Range": row.label,
            "Observed": row.observed_count,
            "Expected": round(row.expected_count, 2),
            "Deviation": round(row.deviation, 2),
        }
        for row in frequency_by_range(draws)
    ])
    st.dataframe(range_df, width="stretch")
else:
    st.warning("No statistical data available yet.")
