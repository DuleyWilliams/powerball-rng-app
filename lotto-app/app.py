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

st.set_page_config(
    page_title="Powerball RNG Engine",
    layout="wide"
)

st.title("Powerball RNG Engine")
st.caption("Weighted generator based on your saved historical draw data.")

col1, col2 = st.columns(2)

with col1:
    ticket_count = st.number_input(
        "How many tickets?",
        min_value=1,
        max_value=50,
        value=5
    )

    if st.button("Generate Numbers"):
        tickets = generate_tickets(ticket_count)
        draws = load_draws()

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

draws = load_draws()

st.subheader("Current Dataset")
st.write(f"Total drawings loaded: {len(draws)}")

if draws:
    history_df = pd.DataFrame(
        draws,
        columns=["Ball 1", "Ball 2", "Ball 3", "Ball 4", "Ball 5", "Powerball"]
    )

    st.dataframe(history_df.head(100), width="stretch")

st.divider()

st.header("Draw Analytics")

if draws:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Hot White Balls")
        st.dataframe(
            pd.DataFrame(hot_numbers(draws), columns=["Number", "Times Drawn"]),
            width="stretch"
        )

    with col2:
        st.subheader("Cold White Balls")
        st.dataframe(
            pd.DataFrame(cold_numbers(draws), columns=["Number", "Times Drawn"]),
            width="stretch"
        )

    with col3:
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
    st.warning("No draw data loaded yet.")