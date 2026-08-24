import os

from mood.art import generate_art
from mood.narrative import generate_narrative
from mood.persist import update_accuracy, upload_image, upload_metrics, upsert_mood_history
from mood.score import compute_mood_score
from mood.signals import get_mood_signals, list_trading_dates

TICKER = os.environ["TARGET_TICKERS"].split(",")[0].strip()
BACKFILL_DAYS = 10
ART_DAYS = 3


def main():
    dates = list_trading_dates(TICKER)[-BACKFILL_DAYS:]
    if len(dates) < 2:
        print(f"Not enough trading days for {TICKER} to backfill (found {len(dates)})")
        return

    art_indices = {
        round(i * (len(dates) - 1) / (ART_DAYS - 1)) for i in range(ART_DAYS)
    } if len(dates) >= ART_DAYS else set(range(len(dates)))

    results = []
    for i, run_date in enumerate(dates):
        signals = get_mood_signals(TICKER, lookback_days=30, as_of_date=run_date)
        signals["run_date"] = run_date
        score, label = compute_mood_score(
            signals["volatility"], signals["volume_anomaly"], signals["momentum_pct"]
        )
        mood = {"score": score, "label": label}
        narrative = generate_narrative(TICKER, score, label, signals)

        image_key = None
        if i in art_indices:
            image_bytes = generate_art(narrative, label)
            image_key = upload_image(TICKER, run_date, image_bytes)

        upload_metrics(TICKER, run_date, signals, mood, narrative)
        upsert_mood_history(
            TICKER, run_date, signals, mood, narrative, image_key, signals["volatility"]
        )
        results.append(signals)
        print(f"{run_date}: score={score:.3f} label={label} art={'yes' if image_key else 'no'}")

    for i in range(len(results) - 1):
        predicted_next_day_vol = results[i]["volatility"]
        actual_next_day_vol = results[i + 1]["volatility"]
        accuracy_delta = predicted_next_day_vol - actual_next_day_vol
        update_accuracy(TICKER, results[i]["run_date"], actual_next_day_vol, accuracy_delta)

    print(f"Backfilled {len(dates)} trading days, {len(art_indices)} with art, "
          f"{len(results) - 1} with accuracy_delta")


if __name__ == "__main__":
    main()
