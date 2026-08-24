import os

import pandas as pd
import streamlit as st

from mood.persist import get_s3_client
from mood.signals import get_connection

st.set_page_config(page_title="Market Mood Agent", page_icon="🎨", layout="wide")

TICKER = os.environ["TARGET_TICKERS"].split(",")[0].strip()

MOOD_EMOJI = {
    "euphoric": "🌞",
    "calm": "🌊",
    "anxious": "😬",
    "volatile": "⚡",
    "bearish": "🐻",
}


@st.cache_data(ttl=300)
def load_history(ticker: str) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_date, mood_score, mood_label, narrative, image_s3_key,
               predicted_next_day_vol, actual_next_day_vol, accuracy_delta
        FROM MOOD_HISTORY
        WHERE ticker = %s
        ORDER BY run_date
        """,
        (ticker,),
    )
    cols = [
        "run_date", "mood_score", "mood_label", "narrative", "image_s3_key",
        "predicted_next_day_vol", "actual_next_day_vol", "accuracy_delta",
    ]
    return pd.DataFrame(cur.fetchall(), columns=cols)


@st.cache_data(ttl=3600)
def load_image(image_s3_key: str) -> bytes:
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=os.environ["S3_BUCKET"], Key=image_s3_key)
    return obj["Body"].read()


def main():
    st.title(f"Market Mood Agent — {TICKER}")
    st.caption(
        "Daily AI-generated mood score, narrative, and abstract art, "
        "with next-day accuracy tracking"
    )

    df = load_history(TICKER)
    if df.empty:
        st.warning("No mood history yet — run the DAG or backfill script first.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Mood score over time")
        st.line_chart(df.set_index("run_date")["mood_score"])
    with col2:
        st.subheader("Accuracy over time")
        accuracy_df = df.dropna(subset=["accuracy_delta"])
        if not accuracy_df.empty:
            st.line_chart(accuracy_df.set_index("run_date")["accuracy_delta"])
        else:
            st.info("No accuracy data yet — need at least 2 days of history.")

    st.subheader("Daily gallery")
    for _, row in df.sort_values("run_date", ascending=False).iterrows():
        with st.container(border=True):
            cols = st.columns([1, 2])
            with cols[0]:
                if row["image_s3_key"]:
                    st.image(load_image(row["image_s3_key"]), use_container_width=True)
                else:
                    st.caption("(no art generated for this day)")
            with cols[1]:
                emoji = MOOD_EMOJI.get(row["mood_label"], "❔")
                st.markdown(
                    f"### {row['run_date']} — {emoji} {row['mood_label'].upper()} "
                    f"(score: {row['mood_score']:.3f})"
                )
                st.write(row["narrative"])
                if row["accuracy_delta"] is not None:
                    st.caption(
                        f"Predicted next-day vol: {row['predicted_next_day_vol']:.5f} · "
                        f"Actual: {row['actual_next_day_vol']:.5f} · "
                        f"Delta: {row['accuracy_delta']:.5f}"
                    )


if __name__ == "__main__":
    main()
