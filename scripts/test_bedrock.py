import os

from mood.art import generate_art
from mood.narrative import generate_narrative
from mood.score import compute_mood_score
from mood.signals import get_mood_signals

TICKER = os.environ["TARGET_TICKERS"].split(",")[0].strip()
OUTPUT_PATH = "/opt/airflow/logs/test_art.png"


def main():
    signals = get_mood_signals(TICKER)
    score, label = compute_mood_score(
        signals["volatility"], signals["volume_anomaly"], signals["momentum_pct"]
    )
    print(f"mood_score: {score:.3f}  mood_label: {label}")

    narrative = generate_narrative(TICKER, score, label, signals)
    print(f"narrative: {narrative}")

    image_bytes = generate_art(narrative, label)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(image_bytes)
    print(f"image saved: {OUTPUT_PATH} ({len(image_bytes)} bytes)")


if __name__ == "__main__":
    main()
