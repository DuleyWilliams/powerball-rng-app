import streamlit as st
import pandas as pd

from generator import generate_tickets, load_draws
from fetch_tn_powerball import update_numbers
from analytics import (
    hot_numbers,
    cold_numbers,
    hot_powerballs,
    repeated_pairs,
    score_tickets
)
from charts import (
    hot_numbers_chart,
    cold_numbers_chart,
    powerball_chart
)
from condensation import condense_tickets

from gap_analysis import (
    white_ball_gap_analysis,
    powerball_gap_analysis
)


st.set_page_config(
    page_title="Powerball RNG Engine",
    layout="wide"
)

st.title("Powerball RNG Engine")
st.caption("Weighted generator based on your saved historical draw data.")

draws = load_draws()

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
        tickets = generate_tickets(ticket_count)
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
        candidate_tickets = generate_tickets(candidate_pool_size)
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