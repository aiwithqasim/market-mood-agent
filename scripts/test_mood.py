import os

from mood.score import compute_mood_score
from mood.signals import get_mood_signals

TICKER = os.environ["TARGET_TICKERS"].split(",")[0].strip()


def main():
    signals = get_mood_signals(TICKER)
    score, label = compute_mood_score(
        signals["volatility"], signals["volume_anomaly"], signals["momentum_pct"]
    )
    print(f"ticker:          {signals['ticker']}")
    print(f"run_date:        {signals['run_date']}")
    print(f"volatility:      {signals['volatility']:.5f}")
    print(f"volume_anomaly:  {signals['volume_anomaly']:.5f}")
    print(f"momentum_pct:    {signals['momentum_pct']:.3f}")
    print(f"mood_score:      {score:.3f}")
    print(f"mood_label:      {label}")


if __name__ == "__main__":
    main()
