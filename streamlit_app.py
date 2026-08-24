import os

import pandas as pd
import streamlit as st

from mood.persist import get_s3_client
from mood.signals import get_connection

st.set_page_config(page_title="Market Mood Agent", page_icon="🎨", layout="wide")

TICKER = os.environ.get("TARGET_TICKERS", "SPY").split(",")[0].strip()
DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() == "true"

MOOD_EMOJI = {
    "euphoric": "🌞",
    "calm": "🌊",
    "anxious": "😬",
    "volatile": "⚡",
    "bearish": "🐻",
}

DEMO_ROWS = [
    {
        "run_date": "2026-08-10",
        "mood_score": -0.14329451799438808,
        "mood_label": "anxious",
        "narrative": (
            "Investors are treading lightly today, with a barely perceptible edge of "
            "unease hanging over the S&P 500 as its mood score inches closer to the "
            "bearish mark. The air is thick with cautious optimism, barely masked by "
            "the scant uptick in momentum, while an unusual quietness in trading "
            "volume hints at a market holding its breath."
        ),
        "image_path": "img/mood_anxious_2026-08-10.png",
        "predicted_next_day_vol": 0.010223253596387968,
        "actual_next_day_vol": 0.010503005750175478,
        "accuracy_delta": -0.00027975215378750994,
    },
    {
        "run_date": "2026-08-14",
        "mood_score": -0.12183602196771025,
        "mood_label": "anxious",
        "narrative": (
            "Today, SPY's mood is a cautious whisper, with an anxious undertone "
            "barely holding back the tides of uncertainty. Investors tread lightly, "
            "their eyes darting between muted gains and the subtle chill of reduced "
            "trading volume, all set against a backdrop of unusually low volatility. "
            "The air is thick with trepidation, as if the slightest breeze could "
            "shift the market's fragile balance."
        ),
        "image_path": "img/mood_anxious_2026-08-14.png",
        "predicted_next_day_vol": 0.007382080160527397,
        "actual_next_day_vol": 0.00684083699796479,
        "accuracy_delta": 0.0005412431625626069,
    },
    {
        "run_date": "2026-08-21",
        "mood_score": -0.06335322495011592,
        "mood_label": "calm",
        "narrative": (
            "Today, the S&P 500 index (SPY) exudes a tranquil calmness, with "
            "investors exhibiting a slightly hesitant yet composed demeanor. The "
            "market's gentle ebb, accompanied by a subdued trading volume, suggests "
            "a day of passive reflection rather than fervent action. A mild downward "
            "drift in momentum further underscores the quiet, contemplative nature "
            "of today's trading session."
        ),
        "image_path": "img/mood_calm_2026-08-21.png",
        "predicted_next_day_vol": 0.004938320228770954,
        "actual_next_day_vol": None,
        "accuracy_delta": None,
    },
]


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


def load_demo_history() -> pd.DataFrame:
    return pd.DataFrame(DEMO_ROWS)


def render_gallery_row(row, image) -> None:
    with st.container(border=True):
        cols = st.columns([1, 2])
        with cols[0]:
            if image is not None:
                st.image(image, use_container_width=True)
            else:
                st.caption("(no art generated for this day)")
        with cols[1]:
            emoji = MOOD_EMOJI.get(row["mood_label"], "❔")
            st.markdown(
                f"### {row['run_date']} - {emoji} {row['mood_label'].upper()} "
                f"(score: {row['mood_score']:.3f})"
            )
            st.write(row["narrative"])
            if row["accuracy_delta"] is not None:
                st.caption(
                    f"Predicted next-day vol: {row['predicted_next_day_vol']:.5f} · "
                    f"Actual: {row['actual_next_day_vol']:.5f} · "
                    f"Delta: {row['accuracy_delta']:.5f}"
                )


def main():
    st.title(f"Market Mood Agent - {TICKER}")
    st.caption(
        "Daily AI-generated mood score, narrative, and abstract art, "
        "with next-day accuracy tracking"
    )

    use_demo = DEMO_MODE
    df = pd.DataFrame()
    if not use_demo:
        try:
            df = load_history(TICKER)
        except Exception:
            use_demo = True

    if use_demo:
        st.info(
            "Showing 3 real sample days (live Snowflake/S3 connection not configured "
            "for this deployment). See the full README for how to run this against "
            "live data."
        )
        df = load_demo_history()

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
        if use_demo:
            image = row["image_path"]
        else:
            image = load_image(row["image_s3_key"]) if row["image_s3_key"] else None
        render_gallery_row(row, image)


if __name__ == "__main__":
    main()
