MOMENTUM_NORMALIZER = 10.0
VOLATILITY_NORMALIZER = 0.03

WEIGHT_MOMENTUM = 0.5
WEIGHT_VOLATILITY = 0.3
WEIGHT_VOLUME_ANOMALY = 0.2

VOLATILE_THRESHOLD = 0.75
EUPHORIC_THRESHOLD = 0.4
BEARISH_THRESHOLD = -0.4
ANXIOUS_THRESHOLD = -0.1


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_mood_score(volatility: float, volume_anomaly: float, momentum_pct: float) -> tuple[float, str]:
    normalized_momentum = _clip(momentum_pct / MOMENTUM_NORMALIZER)
    normalized_volatility = _clip(volatility / VOLATILITY_NORMALIZER, 0.0, 1.0)
    normalized_volume_anomaly = _clip(volume_anomaly)

    momentum_direction = 1.0 if normalized_momentum >= 0 else -1.0

    score = _clip(
        WEIGHT_MOMENTUM * normalized_momentum
        - WEIGHT_VOLATILITY * normalized_volatility
        + WEIGHT_VOLUME_ANOMALY * normalized_volume_anomaly * momentum_direction
    )

    if normalized_volatility > VOLATILE_THRESHOLD:
        label = "volatile"
    elif score >= EUPHORIC_THRESHOLD:
        label = "euphoric"
    elif score <= BEARISH_THRESHOLD:
        label = "bearish"
    elif score <= ANXIOUS_THRESHOLD:
        label = "anxious"
    else:
        label = "calm"

    return score, label
