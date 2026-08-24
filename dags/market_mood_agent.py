import base64
import os
from datetime import datetime

from airflow.decorators import dag, task

TICKER = os.environ["TARGET_TICKERS"].split(",")[0].strip()

default_args = {"owner": "market-mood-agent", "retries": 1}


@dag(
    dag_id="market_mood_agent",
    description="Daily mood score + AI narrative + AI art for a stock ticker, with next-day accuracy tracking",
    schedule="30 21 * * 1-5",
    start_date=datetime(2026, 8, 1),
    catchup=False,
    default_args=default_args,
    tags=["market-mood-agent"],
)
def market_mood_agent():

    @task
    def query_mood_signals() -> dict:
        from mood.signals import get_mood_signals

        signals = get_mood_signals(TICKER)
        signals["run_date"] = signals["run_date"].isoformat()
        return signals

    @task
    def compute_mood_score(signals: dict) -> dict:
        from mood.score import compute_mood_score as _compute_mood_score

        score, label = _compute_mood_score(
            signals["volatility"], signals["volume_anomaly"], signals["momentum_pct"]
        )
        return {"score": score, "label": label}

    @task
    def generate_narrative(signals: dict, mood: dict) -> str:
        from mood.narrative import generate_narrative as _generate_narrative

        return _generate_narrative(TICKER, mood["score"], mood["label"], signals)

    @task
    def generate_art(narrative: str, mood: dict) -> str:
        from mood.art import generate_art as _generate_art

        image_bytes = _generate_art(narrative, mood["label"])
        return base64.b64encode(image_bytes).decode()

    @task
    def persist(signals: dict, mood: dict, narrative: str, image_b64: str) -> None:
        from mood.persist import upload_image, upload_metrics, upsert_mood_history

        run_date = signals["run_date"]
        image_bytes = base64.b64decode(image_b64)

        image_key = upload_image(TICKER, run_date, image_bytes)
        upload_metrics(TICKER, run_date, signals, mood, narrative)
        upsert_mood_history(
            TICKER, run_date, signals, mood, narrative, image_key, signals["volatility"]
        )

    @task
    def score_yesterday(signals: dict) -> None:
        from mood.persist import get_previous_predicted, update_accuracy

        row = get_previous_predicted(TICKER, signals["run_date"])
        if row is None:
            return

        prev_run_date, predicted_next_day_vol = row
        actual_next_day_vol = signals["volatility"]
        accuracy_delta = predicted_next_day_vol - actual_next_day_vol
        update_accuracy(TICKER, prev_run_date, actual_next_day_vol, accuracy_delta)

    signals = query_mood_signals()
    mood = compute_mood_score(signals)
    narrative = generate_narrative(signals, mood)
    image_b64 = generate_art(narrative, mood)
    persist(signals, mood, narrative, image_b64) >> score_yesterday(signals)


market_mood_agent()
